"""
API and utilities for accessing the information that was
originally in sensor_cfg.py, proc_cfg.py and uhdas_cfg.py,
now being transferred to matching toml files.

"""
# format: black

import copy
import pathlib

import toml

from pycurrents.system import Bunch

# Most sensor_cfg.py files include the following:
_sensor_top_level_varnames = (
    "ignore_ADCPs",
    "ignore_other_sensors",
    "use_publishers",
    "shipabbrev",  # switched to "shipkey" in toml
    "common_opts",
    "oswh_opts",  # not required
)


def _read_sensor_cfg_py(fname, publishers=None, execute_lastlines=True):
    fpath = pathlib.Path(fname)
    with open(fpath) as f:
        lines = f.readlines()
    if publishers is not None:
        for i, line in enumerate(lines):
            if line.startswith("use_publishers"):
                if publishers:
                    line = "use_publishers = True"
                else:
                    line = "use_publishers = False"
                lines[i] = line
                break
    if not execute_lastlines:
        for i, line in enumerate(lines):
            if "DO NOT CHANGE" in line:
                del lines[i:]
                break

    return Bunch().from_pystring("".join(lines))


def _sensor_to_toml_string(fname):
    orig = _read_sensor_cfg_py(fname, execute_lastlines=False)
    newdict = dict(ignore_sensors=[])  # At the top.

    # top level
    for name in _sensor_top_level_varnames:
        if name in orig:
            if name == "common_opts":
                s = orig[name]
                newdict[name] = s.replace(f"-f {orig['shipabbrev']} ", "")
            elif name == "shipabbrev":
                newdict["shipkey"] = orig["shipabbrev"]
            elif name in ("ignore_ADCPs", "ignore_other_sensors", "oswh_opts"):
                pass
            else:
                newdict[name] = orig[name]

    sensors = orig.sensors
    ADCPs = orig.ADCPs
    publishers = orig.publishers

    # Add items from each ADCP dictionary entry to its matching sensor dict.
    # The matching relies on the sensors being in the same order.
    adcp_keys = []
    for a, s in zip(ADCPs, sensors[: len(ADCPs)]):
        inst = s["instrument"]
        # Undo the substitution of oswh_opts from executing the pyfile?
        # No, leave it in; oswh_opts doesn't really belong as a top-level item.
        # if inst.startswith("os") or inst.startswith("wh"):
        #     s["opt"] = s["opt"].replace(orig.oswh_opts, "").lstrip()
        s.update(a)
        adcp_keys.append(s["subdir"])

    newdict["adcp_keys"] = adcp_keys

    # Add each augmented sensor dict, keyed by subdir.
    sensor_d = {}
    for s in sensors:
        sensor_d[s["subdir"]] = s

    # Save the order, since toml is not guaranteed to maintain dict order.
    newdict["sensor_keys"] = list(sensor_d.keys())

    # Change the "ignore" lists to contain keys (subdir), not instruments,
    # and consolidate in a single list initialized at the top.
    for inst in orig.ignore_ADCPs + orig.ignore_other_sensors:
        for key in sensor_d:
            if sensor_d[key]["instrument"] == inst:
                newdict["ignore_sensors"].append(key)

    # Add items from each publisher dict to its matching sensor keyed by
    # subdir.
    publisher_keys = []
    for p in publishers:
        sensor_d[p["subdir"]].update(p)
        publisher_keys.append(p["subdir"])

    newdict["sensor_d"] = sensor_d
    newdict["publisher_keys"] = publisher_keys

    # In sensor_cfg.py, there is at most one speedlog; toml could have more.
    # The py speedlog_config uses "instrument" as the key; use "subdir".
    if "speedlog_config" in orig:
        newdict["speedlog_d"] = {}
        speedlog = orig.speedlog_config
        for key in newdict["adcp_keys"]:
            if speedlog["instrument"] == sensor_d[key]["instrument"]:
                speedlog["subdir"] = key
                break
        if "subdir" not in speedlog:
            raise RuntimeError("speedlog instrument is not found")
        newdict["speedlog_d"][key] = speedlog

    # The pubVL block, if present, is similar to speedlog.
    if "pubVL_config" in orig:
        newdict["pubVL_d"] = {}
        pubVL = orig.pubVL_config
        for key in newdict["adcp_keys"]:
            if pubVL["instrument"] == sensor_d[key]["instrument"]:
                pubVL["subdir"] = key
                break
        if "subdir" not in pubVL:
            raise RuntimeError("pubVL instrument is not found")
        newdict["pubVL_d"][key] = pubVL

    return toml.dumps(newdict)


def sensor_to_toml(fname):
    fpath = pathlib.Path(fname)
    if not fpath.exists():
        raise ValueError(f"file {fname} is not found")
    with open(fpath.with_suffix(".toml"), "w") as f:
        f.write(_sensor_to_toml_string(fpath))


class SensorCfg:
    def __init__(self, fname):
        fpath = pathlib.Path(fname)
        if fpath.suffix == ".toml":
            with open(fname) as f:
                self.toml = f.read()
        elif fpath.suffix == ".py":
            self.toml = _sensor_to_toml_string(fname)
        else:
            raise ValueError(
                f"fname suffix must be '.toml' or '.py', not {fpath.suffix}"
            )
        self._base = None
        self._config = None
        self._short_config = None

    @property
    def base(self):
        "Unmodified dictionary from the toml."
        if self._base is None:
            self._base = toml.loads(self.toml)
            sensor_d = {
                key: self._base["sensor_d"][key] for key in self._base["sensor_keys"]
            }
            self._base["sensor_d"] = sensor_d
        return self._base

    @property
    def config(self):
        "Bunch with config dictionaries and lists."
        if self._config is None:
            self._config, self._short_config = self._make_config()
        return self._config

    @property
    def short_config(self):
        "Bunch with only the top level and the dictionaries."
        if self._short_config is None:
            self._config, self._short_config = self._make_config()
        return self._short_config

    def _make_config(self, use_publishers=None):
        self._pubs, self._subs = self._make_publishers_subscribers()
        config = Bunch(copy.deepcopy(self.base))
        for key in config.ignore_sensors:
            del config.sensor_d[key]
            config.sensor_keys.remove(key)
            if key in config.adcp_keys:
                config.adcp_keys.remove(key)
            if key in config.publisher_keys:
                config.publisher_keys.remove(key)
            if "speedlog_d" in config and key in config.speedlog_d:
                del config.speedlog_d[key]
            if "pubVL_d" in config and key in config.pubVL_d:
                del config.pubVL_d[key]

        key_speedlog = None
        if "speedlog_d" in config:
            for key, d in config.speedlog_d.items():
                sensor = config.sensor_d[key]
                # Maybe improve: check for existing -Z option.
                sensor["opt"] += f" -Z {d['zmq_from_bin']}"
                key_speedlog = key
        if "pubVL_d" in config:
            for key, d in config.pubVL_d.items():
                if key != key_speedlog:
                    sensor = config.sensor_d[key]
                    sensor["opt"] += f" -Z {d['zmq_from_bin']}"

        if use_publishers is not None:
            config.use_publishers = use_publishers
        if config.use_publishers:
            for key in config.publisher_keys:
                config.sensor_d[key] = self._subs[key]
        else:
            config.publisher_keys = []
        config.publisher_d = {key: self._pubs[key] for key in config.publisher_keys}
        short_config = config.copy()
        config.ADCPs = [config.sensor_d[key] for key in config.adcp_keys]
        config.sensors = list(config.sensor_d.values())
        config.publishers = list(config.publisher_d.values())
        # Quick fix: currently we never have more than one speedlog or pub_VL.
        if "speedlog_d" in config and config.speedlog_d:
            config.speedlog_config = list(config.speedlog_d.values())[0]
        if "pubVL_d" in config and config.pubVL_d:
            config.pubVL_config = list(config.pubVL_d.values())[0]
        return config, short_config

    def _make_publishers_subscribers(self):
        """
        Regardless of whether use_publishers is True, we can go ahead and make
        dictionaries for publishers and subscribers, with extraneous fields
        removed.
        """
        publishers = {}
        subscribers = {}
        for key in self.base["publisher_keys"]:
            sensor = self.base["sensor_d"][key]
            sub = sensor.copy()
            pub = sensor.copy()
            for fieldname in ("baud", "sample_opts", "autopilot_msg", "pub_addr"):
                if fieldname in sub:
                    del sub[fieldname]
            sub["format"] = "zmq_ascii"
            sub["device"] = sensor["pub_addr"]
            sub["opt"] = ""  # The publisher handles time tagging and checking.
            # The following renaming is needed by zmq_publisher until we make
            # a full transition to the new style.  Then pub["opt"] can also
            # be set to sensor["sample_opts"], which can be removed from pub.
            # This would make the code for starting a publisher more similar to
            # that for a native listener or a subscriber.
            pub["in_device"] = sensor["device"]
            del pub["device"]
            del pub["opt"]  # not used by make_publishers
            # Ideally we might have "sample_opts" be only the extra one, so
            # that
            # pub["opt"] = f'{sensor["opt"]} {sensor["sample_opts"]}'
            # and make_publishers would use pub["opt"], not pub["sample_opts"].
            # autopilot_msg is not actually used, but it might be helpful
            # to keep it for documentation.

            subscribers[key] = sub
            publishers[key] = pub

        return publishers, subscribers


def _restore_None_list(seq):
    out = list()
    for element in seq:
        if element == "None":
            out.append(None)
        elif isinstance(element, list):
            out.append(_restore_None_list(element))
        elif isinstance(element, dict):
            out.append(_restore_None(element))
        else:
            out.append(element)
    return out


def _restore_None(d):
    out = {}
    for key, val in d.items():
        if val == "None":
            val = None
        elif isinstance(val, list):
            val = _restore_None_list(val)
        elif isinstance(val, dict):
            val = _restore_None(val)
        out[key] = val
    return out


def _replace_None_list(seq):
    out = list()
    for element in seq:
        if element is None:
            out.append("None")
        elif isinstance(element, list):
            out.append(_replace_None_list(element))
        elif isinstance(element, dict):
            out.append(_replace_None(element))
        else:
            out.append(element)
    return out


def _replace_None(d):
    out = {}
    for key, val in d.items():
        if val is None:
            val = "None"
        elif isinstance(val, list):
            val = _replace_None_list(val)
        elif isinstance(val, dict):
            val = _replace_None(val)
        out[key] = val
    return out


def _tuple_to_list(d):
    """
    In a dictionary, convert tuples to lists, to match what a round-trip
    py->toml->py would do.
    """
    out = {}
    for key, val in d.items():
        if isinstance(val, list):
            newlist = []
            for elem in val:
                newelem = list(elem) if isinstance(elem, tuple) else elem
                newlist.append(newelem)
            val = newlist
        elif isinstance(val, dict):
            val = _tuple_to_list(val)
        elif isinstance(val, tuple):
            val = list(val)
        out[key] = val
    return out


def get_cfg(fname):
    """
    Read a configuration file, python or toml.

    It can handle sensor_cfg.*, uhdas_cfg.*, and proc_cfg.*.
    If the extension is missing, it will look first for a file with
    .toml extension, and fall back with .py.

    Parameters
    ----------
    fname: str or pathlib.Path
        The filename must end with "sensor_cfg" or "_sensor" if it is of the
        sensor_cfg variety; otherwise it will be assumed to be simple data
        requiring no execution.

    Returns
    -------
    Bunch
        The data dictionary from the file.

    See Also
    --------
    SensorCfg : a class providing more info about a sensor_cfg-type file

    """
    fpath = pathlib.Path(fname)
    if fpath.suffix not in ("", ".py", ".toml"):
        raise ValueError(
            f"fname suffix must be '', '.toml' or '.py', not {fpath.suffix}"
        )
    if fpath.suffix == "":
        for suffix in (".toml", ".py"):
            _fpath = fpath.with_suffix(suffix)
            if _fpath.exists():
                fpath = _fpath
                break
    if fpath.suffix == "" or not fpath.exists():
        raise ValueError(f"Cannot find toml or py file from {fname}")
    if fpath.stem.endswith("sensor_cfg") or fpath.stem.endswith("_sensor"):
        return Bunch(_tuple_to_list(SensorCfg(fpath).config))
    if fpath.suffix == ".toml":
        return Bunch(_restore_None(toml.load(fpath)))
    return Bunch(_tuple_to_list(Bunch().from_pyfile(fpath)))


def find_cfg_files(configdir, priority="toml"):
    """
    Within a config directory, find sensor, uhdas, and proc cfg files.

    Parameters
    ----------
    configdir: str or pathlib.Path
    priority: {"toml", "py"}

    Returns
    -------
    Bunch
        For each key in ("sensor", "uhdas", "proc"), the value is None or a
        pathlib.Path object with the corresponding cfg file.
    """
    if priority not in ("toml", "py"):
        raise ValueError(f"priority must be 'toml' or 'py', not {priority}")
    priority_ext = f".{priority}"
    configpath = pathlib.Path(configdir)
    exts = (".py", ".toml")
    out = Bunch()
    for kind in ("sensor", "uhdas", "proc"):
        # For adcp/config require the generic name.
        paths = [p for p in configpath.glob(f"{kind}_cfg.*") if p.suffix in exts]
        if not paths:
            # Must be raw/config: "{cruise}_{kind}.*".
            paths = [p for p in configpath.glob(f"*_{kind}.*") if p.suffix in exts]
        if not paths:
            out[kind] = None
            continue
        if len(paths) == 1:
            out[kind] = paths[0]
        elif len(paths) == 2:
            if paths[0].suffix == priority_ext:
                out[kind] = paths[0]
            else:
                out[kind] = paths[1]
        else:
            raise RuntimeError(f"Too many candidates: {paths}")
    return out


def get_cfgs(configdir, priority="toml"):
    """
    Within a config directory, read sensor, uhdas, and proc cfg files.

    Parameters
    ----------
    configdir: str or pathlib.Path
    priority: {"toml", "py"}

    Returns
    -------
    Bunch
        For each key in ("sensor", "uhdas", "proc"), the value is None or a
        Bunch with the data structure from the corresponding cfg file.
    """
    fpathdict = find_cfg_files(configdir, priority)
    out = Bunch()
    for kind, path in fpathdict.items():
        if path is not None:
            out[kind] = get_cfg(path)
        else:
            out[kind] = None
    return out


def simple_py_to_toml(fname):
    """
    Convert a simple Python data-only file to a toml file.

    This is intended for uhdas_cfg.py and proc_cfg.py.
    """
    fname = pathlib.Path(fname)
    out_fname = fname.with_suffix(".toml")
    b = Bunch().from_pyfile(fname)
    toml.dump(_replace_None(b), open(out_fname, "w"))
