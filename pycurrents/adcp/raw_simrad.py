"""
Classes and functions for the Simrad zmq datagram.

The goal is to end up with something that is plug-compatible with Multiread
for use in full processing.

Simrad vessel coordinates:

z is positive down
x is forward
y is starboard

beam velocities: positive for water moving away from instrument (downward)

"""
# using ruff format

from datetime import date, datetime, timedelta
import logging

import numpy as np

from pycurrents.adcp.adcp_specs import Sonar

from pycurrents.adcp.raw_base import (
    Bunch,
    PrettyTuple,
    FileBase,
    make_ilist,
    IncompleteFileError,
)

# Standard logging
_log = logging.getLogger(__name__)

__all__ = [
    "FileSimradEC",
    # "wintime_to_dday",
    # "wintime_to_datetime",
    "subsample_ppd",
    # "beam_to_xyde",
    # "xyde_to_xyze",
    # "matrix_I_to_V",
    # "xyde_to_shipOctopus",
    # "beam_to_shipOctopus",
    "ec_intensity_to_dB",
    "ec_intensity_to_RDI_counts",
    "ec_dB_to_RDI_counts",
]



# A top_layout_1 was used briefly in the early testing days before being replaced.

top_layout_2 = [
    # "Header"
    ("datagram_id", np.uint32),
    ("datagram_size", np.uint32),
    ("datagram_version", np.uint32),
    ("software_version", np.byte, (40,)),
    # "Variable Leader"
    ("ping_number", np.uint32),
    ("ping_time", np.uint64),
    ("latitude", np.float32),
    ("longitude", np.float32),
    ("heading", np.float32),
    ("course", np.float32),
    ("speed_over_ground", np.float32),
    ("heave", np.float32),
    ("pitch", np.float32),
    ("roll", np.float32),
    # "Fixed Leader"
    ("beam_count", np.uint32),
    ("sample_count", np.uint32),
    ("sample_interval", np.float32),
    ("start_time_first_sample_relative_transducer", np.float32),
    ("pulse_duration", np.float32),
    ("sub_pulse_duration", np.float32),
    ("lag_interval", np.float32),
    ("pulse_type", np.uint8),
    ("transmit_mode", np.uint8),
    ("transmit_power", np.uint16),
    ("frequency_start", np.uint32),
    ("frequency_stop", np.uint32),
    ("sound_speed", np.float32),
    ("absorption_coefficient", np.float32),
    ("one_way_transducer_gain", np.float32),
    ("two_way_equivalent_beam_angle", np.float32),
    ("array_to_vessel_matrix", np.float32, (4, 4)),
    ("mru_to_vessel_matrix", np.float32, (4, 4)),
]

dgram_top_layouts = {2: top_layout_2}

dgram_vl_layouts = {2: top_layout_2[4:14]}
dgram_fl_layouts = {2: top_layout_2[14:]}

# The header layout and dtype should not change:
dgram_header_layout = top_layout_2[:4]
header_dtype = np.dtype(dgram_header_layout)

# The "parts" are the array sections that follow the "top".
part_header_layout = [
    ("part_id", np.uint16),
    ("part_version", np.uint16),
    ("part_size", np.uint32),  # Includes this header.
]

part_header_dtype = np.dtype(part_header_layout)


# Fixed (unless part_version changes; not likely during test cruise)
part_dtype_dict = {
    1: np.int16,
    2: np.int16,
    3: np.uint8,
}


_dt_unix_usec = np.int64(134774) * 86400 * 1000000
_date_1970 = date(1970, 1, 1)
_datetime_1601 = datetime(1601, 1, 1)


def wintime_to_dday(wintime, yearbase):
    """
    Convert Windows NT time to decimal days.

    wintime may be a scalar or an array of integers.
    """
    usec_1970 = wintime // 10 - _dt_unix_usec  # microseconds since 1970
    sec, usec = np.divmod(usec_1970, 1000000)
    offset_1970 = (date(yearbase, 1, 1) - _date_1970).days
    dday = sec / 86400.0 - offset_1970 + usec / (1000000 * 86400)
    return dday


def wintime_to_datetime(wintime):
    """
    Convert a scalar uint64 wintime to a datetime.datetime.
    """
    return _datetime_1601 + timedelta(microseconds=int(wintime // 10))


# For the time being, we are assuming that FileSimradEC might have to deal with
# files in which all record lengths except for the first are the same length.
# Therefore we are using "starts" and "lengths" arrays.  Generating these
# arrays is slow, given the size of the files.  Pickling for the cache would
# also be slow if we didn't speed it up by truncating "starts" and "lengths"
# upon pickling, and restoring them on unpickling.  All of this is subject to
# review as the EC interface matures.  (It turns out that at least one existing
# file violates the assumption, so we retain the ability to include the full
# arrays when needed.)


class FileSimradEC(FileBase):
    class Header:
        def __init__(self):
            pass

        def read(self, fobj):
            try:
                head = np.fromfile(fobj, dtype=header_dtype, count=1)[0]
            except IndexError:
                raise IncompleteFileError("Failed to read header")

            if head["datagram_id"] not in (101, 102):
                raise RuntimeError("Did not find expected datagram_id")
            self.datagram_version = head["datagram_version"]
            self.software_version = (
                head["software_version"]
                .tobytes()
                .split(b"\x00", maxsplit=1)[0]
                .decode("utf8")
            )
            self.top_dtype = np.dtype(dgram_top_layouts[self.datagram_version])
            self.VariableLeader_dtype = np.dtype(
                dgram_vl_layouts[self.datagram_version]
            )
            self.FixedLeader_dtype = np.dtype(dgram_fl_layouts[self.datagram_version])

    def __init__(self, fname, sonar=None, trim=False, yearbase=None):
        id_names = [
            (-1, "FixedLeader"),
            (-2, "VariableLeader"),
            (1, "Velocity"),
            (2, "Intensity"),
            (3, "Correlation"),
            (0xFFFF, "EOD"),
        ]
        self.vardict = dict(id_names)
        self.id_dict = dict([(var, id) for id, var in id_names])

        self.sonar = Sonar(sonar)
        self._i_first = None  # Will be changed to 0 or 1.
        FileBase.__init__(
            self, fname, inst=self.sonar.model, trim=trim, yearbase=yearbase
        )

    def __getstate__(self):
        state = self.__dict__.copy()
        if self.nprofs > 2:
            if (np.diff(self.lengths[1:]) != 0).any():
                _log.warning("Lengths beyond the first are not identical.")
            else:
                state["starts"] = state["starts"][:2]
                state["lengths"] = state["lengths"][:2]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if self.nprofs > 2 and len(self.lengths) == 2:
            self.lengths = np.empty((self.nprofs,), np.int64)
            self.lengths[:2] = state["lengths"]
            self.lengths[2:] = self.lengths[1]
            self.starts = np.empty((self.nprofs,), np.int64)
            self.starts[0] = state["starts"][0]
            self.starts[1:] = self.lengths[:-1].cumsum()

    def _open_base(self):
        # Modified from FileBase.open to handle different first length.
        try:
            self.fobj = open(self.fname, "rb")
            self.header.read(self.fobj)
            self.refresh_nprofs()
            self.opened = True
        except IncompleteFileError:
            self.fobj.close()
            self.fobj = None
            self.opened = False

    def open(self):
        # FileBase.open(self)
        self._open_base()
        if not self.opened:
            return
        top_dtype = self.header.top_dtype
        ens = self.get_ens(self._i_first)
        top = np.frombuffer(ens, dtype=top_dtype, count=1)
        top = Bunch.from_structured(top)
        wintime = top.ping_time
        dt = wintime_to_datetime(wintime)
        if self.yearbase is None:
            self.yearbase = dt.year
        # TODO: fix varnames list--check for availability in file?
        self.available_varnames = [
            "FixedLeader",
            "VariableLeader",
            "Velocity",
            "Intensity",
            "Correlation",
        ]
        self.dtstr = dt.strftime("%Y/%m/%d %H:%M:%S")
        self.NBeams = top.beam_count
        self.NCells = top.sample_count
        self.dtype_dict = dict(
            [(self.vardict[id], dt) for id, dt in part_dtype_dict.items()]
        )
        self.dtype_dict["FixedLeader"] = self.header.FixedLeader_dtype
        self.dtype_dict["VariableLeader"] = self.header.VariableLeader_dtype
        dp = self.decode_dparams(top)
        for k, v in dp.items():
            setattr(self, k, v)
        self.sonar.pingtype = {1: "cw", 2: "fm"}[top.pulse_type]

        # List of tuples that identify basic config--probably only one for EC.
        self.configs = [self.configtuple()]
        freq = (top.frequency_start + top.frequency_stop) / 2
        kHz = int(np.round(freq / 1000))
        angle = np.rad2deg(np.arcsin(50 * top.sound_speed / freq))
        # For compatibility with RDI code:
        self.sysconfig = Bunch(kHz=kHz, angle=angle, convex=False, up=False)
        self.sonar.frequency = kHz
        self.includes_watertrack = True

    def configtuple(self):
        """
        Return a tuple identifying a configuration.

        A minimal set of parameters is used to decide whether
        files are similar enough to be concatenated.
        """
        # The outer round is needed with Py3 to get a nice result with str().
        pulse = round(round(self.Pulse / self.CellSize, 1) * self.CellSize, 3)
        return PrettyTuple(
            (self.sonar.pingtype, self.NCells, self.CellSize, self.Blank, pulse)
        )

    def refresh_nprofs(self):
        self.find_starts_and_lengths()
        self.nprofs = len(self.starts)

    def find_starts_and_lengths(self):
        if not hasattr(self, "starts"):
            self.starts = []
            self.lengths = []
            ii = 0
        else:
            self.starts = list(self.starts)
            self.lengths = list(self.lengths)
            ii = self.starts[-1] + self.lengths[-1]
        while True:
            self.fobj.seek(ii)
            try:
                ID, length = np.fromfile(self.fobj, dtype=np.uint32, count=2)
            except ValueError:
                break
            if ID not in (101, 102):
                break
            self.starts.append(ii)
            self.lengths.append(length)
            ii += length
        if len(self.lengths) > 1 and self.lengths[0] != self.lengths[1]:
            if self._i_first is None:
                _log.warning(
                    "First length is %s, second is %s.",
                    self.lengths[0],
                    self.lengths[1],
                )
            self._i_first = 1
        else:
            self._i_first = 0
        self.starts = np.array(self.starts)
        self.lengths = np.array(self.lengths)

    def _unpack(self, ens, varnames):
        raw = Bunch()
        top_dtype = self.header.top_dtype

        raw["top"] = np.frombuffer(ens, dtype=top_dtype, count=1)[0]
        raw["nbeams"] = raw.top["beam_count"]
        raw["ncells"] = raw.top["sample_count"]
        array_vars = [v for v in varnames if not v.endswith("Leader")]
        if not array_vars:
            return raw
        array_size = raw.ncells * raw.nbeams
        array_shape = (raw.ncells, raw.nbeams)

        offset = top_dtype.itemsize
        while True:
            part_head = np.frombuffer(
                ens, dtype=part_header_dtype, count=1, offset=offset
            )[0]
            id = part_head["part_id"]
            if id == 0xFFFF:
                break
            varname = self.vardict[id]
            if id not in part_dtype_dict or varname not in varnames:
                offset += part_head["part_size"]
                # could warn for the first case
                continue
            offset += part_header_dtype.itemsize
            dtype = np.dtype(part_dtype_dict[id])
            var = np.frombuffer(ens, dtype=dtype, count=array_size, offset=offset)
            raw[varname] = var.reshape(array_shape)
            offset += array_size * dtype.itemsize
        return raw

    def _readvar(self, raw, varname):
        if self.header.datagram_version not in (2,):
            raise NotImplementedError("only datagram version 2 is supported")
        # Workaround for numpy 1.13:
        top = np.atleast_1d(raw.top)
        if varname == "VariableLeader":
            #  return raw.top[['ping_number', 'ping_time']]
            return top[list(self.header.VariableLeader_dtype.names)][0]
        if varname == "FixedLeader":
            #  return raw.top[list(raw.top.dtype.names[6:])]
            return top[list(self.header.FixedLeader_dtype.names)][0]
        return raw[varname]

    # Start with the same API as FileBBWHOS; trim later.
    def readprofs(
        self, start=0, stop=None, step=1, ilist=None, ends=None, varlist=None, ping=None
    ):
        """
        Read the octopus datagrams with no translations or conversions.
        It is assumed that there are no changes in number of cells within
        the file except possibly from the first to the remainder.
        """
        # if ping is not None:
        #    self.select_ping(ping)

        # Ensure we don't try to read the first profile if its length is wrong.
        start = max(start, self._i_first)

        if varlist == "all":
            varlist = [
                "FixedLeader",
                "VariableLeader",
                "Velocity",
                "Intensity",
                "Correlation",
            ]

        ilist = make_ilist(
            self.nprofs, start=start, stop=stop, step=step, ilist=ilist, ends=ends
        )
        nprofs = len(ilist)
        self.nsamples = nprofs
        pd = Bunch(ilist=ilist)
        for varname in varlist:
            dtype = self.dtype_dict[varname]
            if varname.endswith("Leader"):
                var = np.empty((nprofs,), dtype=dtype)
            else:
                var = np.empty((nprofs, self.NCells, self.NBeams), dtype=dtype)
            pd[varname] = var
        for ii, ind in enumerate(ilist):
            ens = self.get_ens(ind)
            raw = self._unpack(ens, varlist)
            for varname in varlist:
                pd[varname][ii] = self._readvar(raw, varname)

        return pd

    @staticmethod
    def decode_dparams(FL):
        c_nom = 1500
        f0 = 0.5 * (FL.frequency_start + FL.frequency_stop)
        lambda0 = 1e-2
        alpha = np.arcsin(c_nom / (2 * lambda0 * f0))
        dzdt = 0.5 * c_nom * np.cos(alpha)  # for 2-way travel
        # FL.pulse_duration is actually a measure of cell size, not pulse...
        _pulse = dzdt * FL.pulse_duration
        # Nominal cell size is rounded to 2, 4, 8, 16
        cell = 2 ** np.round(np.log2(_pulse))
        # Kongsberg-only: use of lag in bin1dist calculation;
        if FL.pulse_type == 1:  # CW
            lag = FL.lag_interval
            pulse_duration = FL.pulse_duration
        else:  # FM
            lag = FL.sub_pulse_duration
            n_subs = np.floor(FL.pulse_duration / FL.sub_pulse_duration)
            pulse_duration = n_subs * FL.sub_pulse_duration
        pulse = np.round(dzdt * pulse_duration, 2)  # Actual pulse, rounded to cm.
        depth_interval = dzdt * FL.sample_interval
        # RDI-style definition of blank: pause between transmit end and receive start.
        blank = dzdt * (FL.start_time_first_sample_relative_transducer - pulse_duration)
        blank = np.round(blank, 2)  # rounded to the nearest cm
        bin1dist = dzdt * (FL.start_time_first_sample_relative_transducer + lag / 2)
        bin1dist = np.round(bin1dist, 2)  # Also rounded to the cm.
        dp = {}
        dp["NCells"] = FL.sample_count
        dp["NBeams"] = FL.beam_count
        dp["NPings"] = 1
        dp["CellSize"] = cell
        dp["Pulse"] = pulse
        dp["Blank"] = blank
        dp["Bin1Dist"] = bin1dist
        dp["depth_interval"] = depth_interval
        return dp

    def read(self, **kw):
        kw.setdefault("varlist", "all")
        if kw["varlist"] != "all":
            vl = list(kw.pop("varlist"))  # make sure it is a new list
            if "FixedLeader" not in vl:
                vl.append("FixedLeader")
            if "VariableLeader" not in vl:
                vl.append("VariableLeader")
            kw["varlist"] = vl
        pd = self.readprofs(**kw)
        ppd = Bunch(sonar=self.sonar)  # to be returned full of goodies
        # retain access to everything in original form:
        ppd.raw = pd

        ppd.dday = wintime_to_dday(pd.VariableLeader["ping_time"], self.yearbase)
        ppd.ens_num = pd.VariableLeader["ping_number"]

        # Note assumption here that all the FixedLeaders are identical;
        # need to check this.
        ppd.FL = Bunch.from_structured(pd.FixedLeader)
        ppd.update(self.decode_dparams(ppd.FL))
        ppd.dep = np.arange(ppd.NCells) * ppd.depth_interval + ppd.Bin1Dist

        ppd.VL = pd["VariableLeader"]
        ppd.XducerDepth = 0  # Do we need this in ppd? Or can we set it to None?
        ppd.sysconfig = self.sysconfig
        # Temperature is not supplied yet, but it is expected by pingavg.
        ppd.temperature = np.zeros(ppd.VL.shape, np.float32)

        if "Velocity" in pd:
            ppd.vel = np.ma.masked_equal(pd["Velocity"], -32768).astype(float)
            ppd.vel /= 1000.0  # mm/s to m/s
            ppd.split("vel")
            # Add dummy bt_vel etc. at least until we develop a BT algorithm.
            ppd.bt_vel = np.ma.zeros((self.nsamples, self.NBeams), dtype=float)
            ppd.bt_vel.mask = True
            ppd.bt_depth = ppd.bt_vel.copy()

        if "Intensity" in pd:
            ppd.intensity_dB = ec_intensity_to_dB(pd["Intensity"])
            ppd.amp = ec_dB_to_RDI_counts(ppd.intensity_dB)
            ppd.split("amp")
        if "Correlation" in pd:
            ppd.cor = pd["Correlation"]
            ppd.split("cor")

        return ppd


def subsample_ppd(ppd):
    """
    Approximate the RDI style of non-overlapping cells.
    Ensure a maximum of 128 cells.

    This *modifies* its input in place and returns None.

    This is needed for data collected prior to EK80 version 24.6.0.0, and
    potentially for subsequent data collected using the decimation option
    rather than the samples-per-cell option.
    """
    dz_orig = ppd.dep[1] - ppd.dep[0]
    step = int(round(ppd.CellSize / dz_orig))
    stop = min(128 * step, ppd.NCells)
    dslice = slice(0, stop, step)
    ppd.dep = ppd.dep[dslice]
    ppd.NCells = len(ppd.dep)
    ppd.nbins = ppd.NCells  # Yes, we have this duplication...

    for k, v in list(ppd.items()):
        if k.startswith("bt_"):
            continue
        if k.endswith("K"):
            ppd.pop(k)
            continue
        if k[-1] in ("1", "2", "3", "4"):
            ppd.pop(k)
            continue
        if isinstance(v, np.ndarray):
            if v.ndim == 2:
                ppd[k] = v[:, dslice].copy()
            elif v.ndim == 3:
                ppd[k] = v[:, dslice, :].copy()


def beam_to_xyde(beamvels, beamangle, masked=True):
    """
    Transform from beam to XYZE.
    If beam 1 points forward, this will be forward/starboard/down/error.
    """
    a = 1 / (2 * np.sin(np.deg2rad(beamangle)))
    b = 1 / (4 * np.cos(np.deg2rad(beamangle)))
    d = a / np.sqrt(2)
    mat = np.array([[a, -a, 0, 0], [0, 0, a, -a], [b, b, b, b], [d, d, -d, -d]])
    beamvels = np.ma.filled(beamvels, np.nan)
    xyde = np.einsum("...k,lk->...l", beamvels, mat, optimize=True)
    # or tensordot(beamvels, mat, axes=([-1], [-1]))
    if masked:
        xyde = np.ma.masked_invalid(xyde)
    return xyde


def xyde_to_xyze(xyde):
    """
    Transform from Octopus xyze (FSDE: forward, starboard, down, error)
    to RDI (SFUE: starboard, forward, up, error).
    These can be either instrument coordinates or ship
    coordinates.

    This transform is its own inverse.

    """
    xyze = xyde.copy()
    xyze[..., 0] = xyde[..., 1]
    xyze[..., 1] = xyde[..., 0]
    xyze[..., 2] *= -1  # switch down to up
    return xyze


def cosd(theta):
    return np.cos(np.radians(theta))


def sind(theta):
    return np.sin(np.radians(theta))


def matrix_I_to_V(yaw, pitch, roll):
    """
    Return the instrument-to-vessel rotation matrix for the
    Octopus coordinate system.

    Arguments yaw, pitch, roll are in degrees.
    """
    # fmt: off
    R_yaw = np.array([[cosd(yaw),  -sind(yaw), 0],
                      [sind(yaw),  cosd(yaw),  0],
                      [0,          0,          1]])

    R_pitch = np.array([[cosd(pitch),    0,  sind(pitch)],
                        [0,              1,            0],
                        [-sind(pitch),   0,  cosd(pitch)]])

    R_roll = np.array([[1,               0,           0],
                       [0,      cosd(roll), -sind(roll)],
                       [0,      sind(roll), cosd(roll)]])
    # fmt: on

    # Rotation matrix Instrument-to-Vessel coordinate system
    R_VI = R_yaw @ R_pitch @ R_roll
    return R_VI


def xyde_to_shipOctopus(xyde, yaw, pitch, roll, masked=True):
    """
    Transform Octopus instrument to Octopus vessel coordinates.
    Error velocity is carried over, so the output has the same
    dimensions as the input (ntimes, ndepths, nv) or (n, nv),
    where nv can be 3 or 4.

    yaw, pitch, roll are scalars.

    Use masked=True if xyde is masked; in this case the output
    will also be masked.
    """
    R_VI = matrix_I_to_V(yaw, pitch, roll)
    if masked:
        xyde = np.ma.masked_invalid(xyde)
    xyzeV = xyde.copy()
    xyzeV[..., :3] = np.einsum("...i,ji->...,j", xyde[..., :3], R_VI, optimize=True)
    # Or, even faster, tensordot(xyde[..., :3], R_VI, axes=([-1], [-1]))
    if masked:
        xyzeV = np.ma.masked_invalid(xyzeV)
    return xyzeV


def beam_to_shipOctopus(beamvels, beamangle, yaw, pitch, roll, masked=True):
    """
    Full transform, beam to vessel, all in Octopus coordinates.
    """
    xyde = beam_to_xyde(beamvels, beamangle, masked=False)
    shipOctopus = xyde_to_shipOctopus(xyde, yaw, pitch, roll, masked=False)
    if masked:
        shipOctopus = np.ma.masked_invalid(shipOctopus)
    return shipOctopus


# The following conversion factor was given as a note in a Simrad datagram
# description draft dated 2018-09-24, as clarified in a subsequent email with
# Sverre: the note just says "log(2)", but it should be "log10(2)".
_intensity_dB_scale = (10 * np.log10(2) / 256).astype(np.float32)


def ec_intensity_to_dB(intensity):
    """
    Convert EC echo intensity int16 values from the datagram to dB.
    """
    return intensity * _intensity_dB_scale


def ec_intensity_to_RDI_counts(intensity, offset_counts=380, dtype=np.float32):
    """
    Convert EC echo intensity int16 values from the datagram to a rough
    approximation to the amplitude counts from RDI ADCPs.

    The returned array is floating point
    """
    return (intensity * _intensity_dB_scale / 0.45 + offset_counts).astype(dtype)


def ec_dB_to_RDI_counts(intensity_dB, offset_counts=380):
    """
    Convert EC echo intensity in dB to a rough approximation to the amplitude
    counts from RDI ADCPs.

    Returns a uint8 array after clipping to the valid range.  Clipping appears
    to be very rare, but high values (>255) do occur.
    """
    counts_float = intensity_dB / 0.45 + offset_counts
    counts_clipped = np.clip(counts_float, 0, 255)
    return counts_clipped.astype(np.uint8)
