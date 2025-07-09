"""
Date and time conversions and utilities.
"""

import datetime

import numpy as np

from pycurrents.data._time import to_day, to_date  # NOQA
(to_day, to_date)  # placate pyflakes


def dt64_to_ymdhms(dt):
    """
    Convert numpy datetime64 scalar or array to YMDHMS.

    If *dt* is a scalar, a 1-D array of 6 uint16 will be returned;
    otherwise, a 2-D array of shape (n, 6).

    The time is truncated to the second.
    """
    if np.iterable(dt):
        dt = np.asarray(dt)
    return to_date(1970, dt.astype("<M8[s]").astype(int) / 86400)


def day_to_dt64(yearbase, dday):
    """
    Convert decimal day to numpy datetime64 with ms precision.
    """
    epoch = np.datetime64("%04s-01-01" % yearbase, 'ms')
    if np.iterable(dday):
        dday = np.asarray(dday)
        td = (dday * 86400000).astype("<m8[ms]")
    else:
        td = np.timedelta64(int(dday * 86400000), 'ms')
    return epoch + td


def dt64_to_day(yearbase, dt):
    """
    Convert datetime64 to days from start of yearbase.
    """
    if np.iterable(dt):
        dt = np.asarray(dt)
    epoch = np.datetime64(f"{yearbase:04d}-01-01")
    return (dt - epoch).astype("<m8[ms]").astype(float) / 86400000


def ddtime(yearbase, datestring):
    '''
    Convert a single datestring to decimal day.

    Parameters
    ----------
    yearbase : int
        4-digit year
    datestring : string
        Date and time in format "yyyy/mm/dd hh:mm:ss" or "yy/mm/dd hh:mm:ss"

    Returns
    -------
    float
        Time in days since the start of the `yearbase` year.
    '''
    fmt1 = "%Y/%m/%d %H:%M:%S"
    fmt2 = "%y/%m/%d %H:%M:%S"
    try:
        dt = datetime.datetime.strptime(datestring, fmt1)
    except ValueError:
        dt = datetime.datetime.strptime(datestring, fmt2)
    return to_day(yearbase, dt.year, dt.month, dt.day, dt.hour,
                  dt.minute, dt.second)
