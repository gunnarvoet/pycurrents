"""
Approximate calculation of sunrise and sunset times.
This is a vectorized implementation of the algorithm
from the US Naval Observatory as presented in
http://edwilliams.org/sunrise_sunset_algorithm.htm.
"""

import datetime

import numpy as np

from pycurrents import codas
from pycurrents.num import rangeslice

_rad_per_deg = np.pi / 180

def _cosd(x):
    return np.cos(x * _rad_per_deg)

def _sind(x):
    return np.sin(x * _rad_per_deg)

def _tand(x):
    return np.tan(x * _rad_per_deg)

def _atand(x):
    return np.arctan(x) / _rad_per_deg

def _acosd(x):
    return np.arccos(x) / _rad_per_deg

def suntimes(lon, lat, datespec, yearbase=None, adjust_sunset=False,
             zenith=90.8):
    """
    Calculate UTC sunrise, sunset times for given location and UTC day.

    Parameters
    ----------
    lon, lat : scalar or 1-D sequences
        Longitude, latitude in degrees
    datespec : datetime, date, or decimal day, scalar or 1-D sequence
        UTC dates. If a datetime or floating-point decimal day is
        given, it will be truncated to the date or the integer part
        of the decimal day.  If a date or datetime is given, *lon*
        and *lat* must be scalars.
    yearbase : None or int
        If *datespec* is a decimal day scalar or sequence, *yearbase*
        gives the epoch. Otherwise it is ignored.
    adjust_sunset : bool, optional, default is False
        If True, a day will be added to the sunset time when needed
        to make the sunset follow the sunrise; otherwise, sunrise
        and sunset will always be within the UTC day given by *datespec*,
        so their order varies with location and day.
    zenith : float, optional
        Solar zenith angle in degrees defining sunrise and sunset.

    Returns
    -------
    ndarray or list
        If any of *lon*, *lat*, or *datespec* is not a scalar, a 2-D
        ndarray will be returned with sunrise decimal days in the
        first row and sunsets in the second.
        Otherwise a sequence of two elements, sunrise and sunset,
        will be returned in a 1-D ndarray of float if *datespec*
        is a decimal day, or a list of 2 datetimes otherwise.
        Missing values are filled with NaN if float, or None otherwise.

    Notes
    -----
    This is a vectorized implementation of the algorithm
    from the US Naval Observatory as presented in
    http://edwilliams.org/sunrise_sunset_algorithm.htm.

    Examples
    --------
    >>> suntimes(-158, 21, [30, 120, 210], yearbase=2018)
    array([[ 30.71489023, 120.66788159, 210.67031451],
           [ 30.18188688, 120.20605684, 210.21616456]])

    >>> suntimes(-158, 21, [30, 120, 210], yearbase=2018, adjust_sunset=True)
    array([[ 30.71489023, 120.66788159, 210.67031451],
           [ 31.18188688, 121.20605684, 211.21616456]])

    >>> suntimes(-158, 80, [30, 120, 210], yearbase=2018, adjust_sunset=True)
    array([[nan, nan, nan],
           [nan, nan, nan]])

    >>> from datetime import date
    >>> suntimes(-158, 21, date(2018, 1, 31))
    [datetime.datetime(2018, 1, 31, 17, 9, 26, 515783),
     datetime.datetime(2018, 1, 31, 4, 21, 55, 26569)]

    """
    if isinstance(datespec, (datetime.date, datetime.datetime)):
        if not (np.isscalar(lon) and np.isscalar(lat)):
            raise ValueError(
                "lon, lat must be scalars when datespec is datetime or date")
        date = datespec
        day = date.day
        month = date.month
        year = date.year
        N = (date.toordinal()
             - datetime.date(year, 1, 1).toordinal() + 1)
        using_datetime=True

    else:
        dday = datespec
        if not (np.isscalar(lon) and np.isscalar(lat) and np.isscalar(dday)):
            lon, lat, dday = np.broadcast_arrays(lon, lat, dday)
            if lon.ndim != 1:
                raise ValueError("lon, lat, dday must be scalar or 1-D")
        if yearbase is None:
            raise ValueError("yearbase kwarg must be given with dday datespec")
        year, month, day = codas.to_date(yearbase, dday).T[:3]
        ybdays = codas.to_day(yearbase, year, 1, 1)
        N = np.floor(dday) - ybdays + 1
        using_datetime=False

    # 1. first calculate the day of the year
    #    done above (N)

    # 2. convert the longitude to hour value and calculate
    #    an approximate time
    lngHour = lon / 15

    offsets = np.array([6, 18], dtype=float)  # rise, set
    if not using_datetime and np.ndim(lon) == 1:
        offsets = offsets[:, np.newaxis]
    t = N + (offsets - lngHour) / 24

    # 3. calculate the Sun's mean anomaly
    M = (0.9856 * t) - 3.289

    # 4. calculate the Sun's true longitude
    L = M + (1.916 * _sind(M)) + (0.020 * _sind(2 * M)) + 282.634
    L %= 360

    # 5a. calculate the Sun's right ascension

    RA = _atand(0.91764 * _tand(L))
    RA %= 360

    # 5b. right ascension value needs to be in the same quadrant as L
    Lquadrant  = (L//90) * 90
    RAquadrant = (RA//90) * 90
    RA = RA + (Lquadrant - RAquadrant)

    # 5c. right ascension value needs to be converted into hours
    RA /= 15

    # 6. calculate the Sun's declination
    sinDec = 0.39782 * _sind(L)
    cosDec = np.cos(np.arcsin(sinDec))

    # 7a. calculate the Sun's local hour angle
    cosH = (_cosd(zenith) - (sinDec * _sind(lat))) / (cosDec * _cosd(lat))

    # NaN the values where the sun never rises.
    cosH[(cosH > 1) | (cosH < -1)] = np.nan

    # 7b. finish calculating H and convert into hours

    H = _acosd(cosH)
    H[0] = 360 - H[0]

    H /= 15

    #8. calculate local mean time of rising/setting
    T = H + RA - (0.06571 * t) - 6.622

    #9. adjust back to UTC
    UT = (T - lngHour) % 24  # Time of day, UTC, in hours.

    dday_offset = UT / 24

    if using_datetime:
        if np.isnan(t).any():
            return [None, None]
        out = []
        d0 = datetime.datetime(year, month, day)
        for t in dday_offset:
            out.append(d0 + datetime.timedelta(days=t))
        if adjust_sunset and out[1] < out[0]:
            out[1] += datetime.timedelta(days=1)
    else:
        d0 = np.floor(dday)
        out = d0 + dday_offset
        if adjust_sunset:
            LOD = np.diff(out, axis=0).squeeze()
            with np.errstate(invalid='ignore'):
                if out.ndim == 2:
                    out[1][LOD < 0] += 1
                else:
                    if LOD < 0:
                        out[1] += 1

    return out


def daily_suntimes(lon, lat, dday, yearbase):
    sr, ss = suntimes(lon, lat, dday, yearbase=yearbase)
    d0, d1 = np.floor(dday[0]), np.ceil(dday[-1])
    days = np.arange(d0, d1)
    out = np.full((2, len(days)), np.nan)
    for i, day in enumerate(days):
        dsl = rangeslice(dday, day, day+1)
        isr = np.argmin(np.abs(dday[dsl] - sr[dsl]))
        iss = np.argmin(np.abs(dday[dsl] - ss[dsl]))
        out[:, i] = [sr[dsl][isr], ss[dsl][iss]]
    # Disallow dday[0] and dday[-1] because the true values are
    # most likely off the ends.
    out[out == dday[0]] = np.nan
    out[out == dday[-1]] = np.nan
    return out

