"""
Provides :func:`loadmatbunch` for more convenient access to the
data in Matlab .mat files, and :func:`savematbunch` for safely
saving a Bunch or dictionary with variables that might be masked
arrays.

Time conversion routines for Matlab's obsolete but common "datenum"
are also included:

    - `datenum_to_day`
    - `datenum_to_mpl` (Note: this is for matplotlib's *old* datenum-like variable.)
Also *datenum_to_day* and *datenum_to_mpl* for
converting MATLAB datenums to decimal days and matplotlib
datenums, respectively.
"""
import datetime
import warnings

import numpy as np
import scipy.io as sio
from matplotlib import dates

from pycurrents.system import Bunch

def crunch(arr, masked=True):
    """
    Handle all arrays that are not Matlab structures.
    """
    if arr.size == 1:
        arr = arr.item()  # Returns the contents.
        return arr

    # The following squeeze is discarding some information;
    # we might want to make it optional.
    arr = arr.squeeze()

    if masked and arr.dtype.kind == 'f':  # check for complex also
        arrm = np.ma.masked_invalid(arr)
        if arrm.count() < arrm.size:
            arr = arrm
        else:
            arr = np.array(arr) # copy to force a read
    else:
        arr = np.array(arr)
    return arr

def structured_to_bunch(arr, masked=True):
    """
    Recursively move through the structure tree, creating
    a Bunch for each structure.  When a non-structure is
    encountered, process it with crunch().
    """
    # A single "void" object comes from a Matlab structure.
    # Each Matlab structure field corresponds to a field in
    # a numpy structured dtype.
    if arr.dtype.kind == 'V' and arr.shape == (1,1):
        b = Bunch()
        x = arr[0,0]
        for name in x.dtype.names:
            b[name] = structured_to_bunch(x[name], masked=masked)
        return b

    return crunch(arr, masked=masked)

def _showmatbunch(b, elements=None, origin=None):
    if elements is None:
        elements = []
    if origin is None:
        origin = ''
    items = list(b.items())
    for k, v in items:
        _origin = "%s.%s" % (origin, k)
        if isinstance(v, Bunch):
            _showmatbunch(v, elements, _origin)
        else:
            if isinstance(v, (str, str)):
                slen = len(v)
                if slen < 50:
                    entry = v
                else:
                    entry = 'string, %d characters' % slen
            elif isinstance(v, np.ndarray):
                if np.ma.isMA(v):
                    entry = 'masked array, shape %s, dtype %s' % (v.shape, v.dtype)
                else:
                    entry = 'ndarray, shape %s, dtype %s' % (v.shape, v.dtype)
            else:
                entry = '%s %s' % (type(v).__name__, v)
            elements.append((_origin, entry))
    elements.sort()
    return elements

def showmatbunch(b):
    """
    Show the contents of a matfile as it has been, or would be, loaded
    by loadmatbunch.

    *b* can be either the name of a matfile or the output of loadmatbunch.

    Returns a multi-line string suitable for printing.
    """
    if isinstance(b, (str, str)):
        b = loadmatbunch(b)
    elist = _showmatbunch(b)
    names = [n for n, v in elist]
    namelen = min(40, max([len(n) for n in names]))
    str_fmt = "{0!s:<{namelen}} : {1!s}\n"
    strlist = [str_fmt.format(n[1:], v, namelen=namelen) for (n, v) in elist]
    return ''.join(strlist)


def loadmatbunch(fname, masked=True, uint16_codec=None):
    """
    Wrapper for loadmat that dereferences (1,1) object arrays,
    optionally converts floating point arrays to masked arrays, and uses
    nested Bunch objects in place of the matlab structures.

    *uint16_codec* defaults to 'ascii', the behavior for old
    files and for PY2.  If you think your file is using utf-8
    then set this kwarg to 'utf-8'.
    """
    if uint16_codec is None:
        uint16_codec = 'ascii'
    out = Bunch()
    fobj = open(fname, 'rb')
    try:
        xx = sio.loadmat(fobj, uint16_codec=uint16_codec)
    except TypeError:
        # It's not a version 5 file, so the kwarg is not recognized.
        xx = sio.loadmat(fobj)
    keys = [k for k in xx.keys() if not k.startswith("__")]
    for k in keys:
        out[k] = structured_to_bunch(xx[k], masked=masked)
    fobj.close()
    return out

def _for_mat(input):
    d = dict()
    for k, v in input.items():
        if isinstance(v, np.ma.MaskedArray):
            if v.dtype.kind == "c":
                d[k] = np.ma.filled(v, np.nan + 1j * np.nan)
            elif v.dtype.kind == "f":
                d[k] = np.ma.filled(v, np.nan)
            else:
                if np.ma.is_masked(v):
                    warnings.warn("Converting %s to float" % k)
                    d[k] = np.ma.filled(v.astype(float), np.nan)
                else:
                    d[k] = v.filled()
        elif v is None:
            d[k] = 'None'
        elif isinstance(v, dict):
            d[k] = _for_mat(v)
        else:
            d[k] = v
    return d

def savematbunch(filename, vardict):
    """
    Write variables to a matfile.

    Parameters
    ----------
    filename : str
        path to output matfile, with or without '.mat'
    vardict : dict or dict-like (e.g. Bunch)
        container with arrays and other variables

    Arrays that are floating point and masked will be filled with
    nan before being saved; integer masked arrays with any masked
    element will be converted to floating point so that nan can
    be used to replace the masked values.
    """
    d = _for_mat(vardict)
    sio.savemat(filename, d, oned_as='row')


# It seems hard to avoid unwanted truncation with microseconds, so that option
# is omitted.
_units_per_day = {"s": 86400, "ms": 86400 * 1e3}
_unix_epoch_datenum = 719529
_unix_epoch_dt64 = np.datetime64("1970-01-01")
_mpl_epoch_dt64 = np.datetime64(dates.get_epoch())


def datenum_to_dt64(datenums, units="s"):
    dn_frac, dn_int = np.modf(datenums)
    delta_days = (dn_int - _unix_epoch_datenum).astype("timedelta64[D]")
    delta_frac = np.round(dn_frac * _units_per_day[units]).astype(f"timedelta64[{units}]")
    return np.datetime64("1970-01-01", units) + delta_days + delta_frac

def dt64_to_datenum(dt):
    dt = np.asanyarray(dt)
    return dt.astype("datetime64[ms]").astype(float) / _units_per_day["ms"] + _unix_epoch_datenum

def datenum_to_day(dnum, yearbase):
    "Convert MATLAB datenum(s) to decimal day relative to a yearbase."
    return np.asanyarray(dnum) - (366 + datetime.date(yearbase, 1, 1).toordinal())

def day_to_datenum(dday, yearbase):
    return np.asanyarray(dday) + (366 + datetime.date(yearbase, 1, 1).toordinal())

def datenum_to_mpl(dnum):
    "Convert MATLAB datenum(s) to matplotlib datenum(s)."
    dt64 = datenum_to_dt64(dnum, units="s")
    return (dt64 - (_mpl_epoch_dt64 - _unix_epoch_dt64)).astype(float) / _units_per_day["s"]
