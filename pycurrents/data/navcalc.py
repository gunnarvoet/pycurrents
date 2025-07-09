"""
Navigation-related calculations, including converting between
meters and degrees, and velocity from time series of positions.
"""

import numpy as np
import numpy.ma as ma

# numpy 1.3 ma does not have a diff; 1.4 does, but it
# is simply using the numpy.diff, which works fine with
# masked arrays.  Hence, we just use np.diff.


def wrap(x, min=0, copy=True):
    """
    Wrap a sequence of angles in degrees to a 360-degree range.

    The range starts with *min*.

    The *copy* kwarg is ignored, and will eventually be removed.

    Returns a new array of the same type as the input.
    """
    x = np.array(x, dtype=float, subok=True, copy=True)
    if min == 0:
        x %= 360
    else:
        x -= min
        x %= 360
        x += min
    return x

def unwrap(lon, centered=False, copy=True):
    """
    Unwrap a sequence of longitudes or headings in degrees.

    Optionally center it as close to zero as possible

    The *copy* kwarg is ignored, and will eventually be removed.

    Returns a new array of the same type (e.g. masked) as its input.
    """
    masked_input = ma.isMaskedArray(lon)
    if masked_input:
        fill_value = lon.fill_value
        # masked_invalid loses the original fill_value (ma bug, 2011/01/20)
    lon = np.ma.masked_invalid(lon).astype(float)
    if lon.ndim != 1:
        raise ValueError("Only 1-D sequences are supported")
    if lon.shape[0] < 2:
        return lon
    x = lon.compressed()
    if len(x) < 2:
        return lon
    w = np.zeros(x.shape[0]-1, int)
    ld = np.diff(x)
    np.putmask(w, ld > 180, -1)
    np.putmask(w, ld < -180, 1)
    x[1:] += (w.cumsum() * 360.0)

    if centered:
        x -= 360 * np.round(x.mean() / 360.0)

    if lon.mask is ma.nomask:
        lon[:] = x
    else:
        lon[~lon.mask] = x
    if masked_input:
        lon.fill_value = fill_value
        return lon
    else:
        return lon.filled(np.nan)

def unwrap_lon(lon, copy=True):
    """
    Unwrap a sequence of longitudes and center it as close to the
    prime meridian as possible.

    The *copy* kwarg is ignored, and will eventually be removed.

    Returns a masked array only of the input is a masked array.
    """
    return unwrap(lon, centered=True)


def lonlat_metrics(alat):
    """
    For given latitudes, return meters per degree lon, m per deg lat

    Reference: American Practical Navigator, Vol II, 1975 Edition, p 5
    """
    rlat = alat*np.pi/180
    hx = 111415.13 * np.cos(rlat) - 94.55 * np.cos(3 * rlat)
    hy = 111132.09 - 566.05 * np.cos(2 * rlat) + 1.2 * np.cos(4 * rlat)
    return hx, hy

def diffxy_from_lonlat(lon, lat, pad=True):
    """
    Given lon, lat in degrees, return dx, dy in meters.

    If pad is True, the first element of the returned
    arrays will be masked, and the length of the arrays
    will be the length of the inputs; otherwise the returned
    arrays will be shorter by one.

    Masked arrays are always returned. (This may change.)

    From EF lon_to_m.m and lat_to_m.m
    """
    lon = ma.masked_invalid(lon).ravel().astype(float)
    lat = ma.masked_invalid(lat).ravel().astype(float)
    alat = (lat[1:]+lat[:-1])/2
    hx, hy = lonlat_metrics(alat)
    dlon = np.diff(lon)
    dlat = np.diff(lat)

    if pad:
        dx = ma.masked_all(lon.shape, dtype=float)
        dy = ma.masked_all(lat.shape, dtype=float)
        dx[1:] = dlon * hx
        dy[1:] = dlat * hy
    else:
        dx = dlon * hx
        dy = dlat * hy

    return dx, dy

def difflonlat_from_diffxylat(x, y, alat):
    """
    Convert increments x, y in meters to degrees, for latitude alat.

    lat can be a scalar or an array with the dimensions of x and y.

    From EF m_to_lon.m and m_to_lat.m
    """
    hx, hy = lonlat_metrics(alat)
    dlon = x / hx
    dlat = y / hy
    return dlon, dlat

def diffxy_from_difflonlat(dlon, dlat, alat):
    """
    Convert increments dlon, dlat in degrees to meters, for latitude alat.

    alat can be a scalar or an array with the dimensions of dlon and dlat.

    """
    hx, hy = lonlat_metrics(alat)
    dx = dlon * hx
    dy = dlat * hy
    return dx, dy

def lonlat_inside_km_radius(lons, lats, pos, kmrad):
    """
    Return a boolean array with True where the positions
    specified by *lons*, *lats* are less than *kmrad* kilometers
    from the point *pos* (a lon, lat pair).
    """
    dlon = np.asanyarray(lons) - pos[0]
    dlat = np.asanyarray(lats) - pos[1]
    dx, dy = diffxy_from_difflonlat(dlon, dlat, pos[1])
    kmdist = np.sqrt(dx**2 + dy**2) / 1000.0
    return kmdist < kmrad

def great_circle_distance(lon0, lat0, lon1, lat1, a=6378e3):
    """
    Calculate the great circle distance.

    lon0, lat0, lon1, lat1 must be broadcastable sequences of
    longitudes and latitudes in degrees.

    Distance is returned in meters, or in whatever units are used
    for the radius, *a* (default: earth equatorial radius in m).

    """
    lon0 = np.deg2rad(lon0)
    lat0 = np.deg2rad(lat0)
    lon1 = np.deg2rad(lon1)
    lat1 = np.deg2rad(lat1)
    cos, sin = np.cos, np.sin
    d = a * np.arccos(cos(lat0) * cos(lat1) * cos(lon0 - lon1)
                      + sin(lat0) * sin(lat1))
    return d

def great_circle_waypoints(lon0, lat0, lon1, lat1, fractions=None, a=6378e3):
    """
    Waypoints at fractional locations along a great circle.

    Formula from http://williams.best.vwh.net/avform.htm#Intermediate
    """
    if fractions is None:
        fractions = np.linspace(0, 1, 101)
    f = fractions
    d = great_circle_distance(lon0, lat0, lon1, lat1, a) / a
    lon0_deg = lon0
    lon0 = np.deg2rad(lon0)
    lat0 = np.deg2rad(lat0)
    lon1 = np.deg2rad(lon1)
    lat1 = np.deg2rad(lat1)
    A = np.sin((1-f)*d)/np.sin(d)
    B = np.sin(f*d)/np.sin(d)
    x = A * np.cos(lat0) * np.cos(lon0) +  B * np.cos(lat1) * np.cos(lon1)
    y = A * np.cos(lat0) * np.sin(lon0) +  B * np.cos(lat1) * np.sin(lon1)
    z = A * np.sin(lat0) +  B * np.sin(lat1)
    lat = np.arctan2(z, np.hypot(x, y))
    lon = np.arctan2(y, x)
    lon = np.rad2deg(lon)
    lon = unwrap_lon(lon - lon0_deg) + lon0_deg
    lat = np.rad2deg(lat)
    return lon, lat


def uv_from_txy(dday, lon, lat, pad=True):
    """
    Return u, v calculated with first differences.

    If pad is True, the outputs will be the same length
    as the inputs, and the first value will be masked;
    that is, velocity i is calculated from points i-1 and i.

    The lon argument must already be unwrapped.
    """
    dx, dy = diffxy_from_lonlat(lon, lat, pad=pad)
    dday = np.asanyarray(dday)
    if pad:
        dt = ma.zeros(dday.shape, dtype=dday.dtype)
        dt[0] = ma.masked
        dt[1:] = np.diff(dday) * 86400
    else:
        dt = np.diff(dday) * 86400
    u = dx / dt
    v = dy / dt
    return u, v

def uv_from_txy_centered(dday, lon, lat, fill_ends=True):
    """
    Return u, v calculated with centered differences, on the
    same grid as the input.

    If fill_ends is True (default) then the end points will
    be filled with the nearest first differences; otherwise
    they will be masked.

    The lon argument must already be unwrapped.
    """
    dx, dy = diffxy_from_lonlat(lon, lat, pad=False)
    dday = np.asanyarray(dday)
    dt = np.diff(dday) * 86400

    u = ma.zeros(dday.shape, dtype=dday.dtype)
    v = ma.zeros(dday.shape, dtype=dday.dtype)

    denom = (dt[1:] + dt[:-1])
    u[1:-1] = (dx[1:] + dx[:-1]) / denom
    v[1:-1] = (dy[1:] + dy[:-1]) / denom

    if fill_ends:
        u[0] = dx[0] / dt[0]
        v[0] = dy[0] / dt[0]
        u[-1] = dx[-1] / dt[-1]
        v[-1] = dy[-1] / dt[-1]
    else:
        u[0] = v[0] = u[-1] = v[-1] = np.ma.masked

    return u, v


def spd_cog_from_uv(u, v):
    spd = np.ma.sqrt(u**2 + v**2)
    cog = 90 - np.ma.arctan2(v, u) * (180.0/np.pi)
    cog = np.ma.remainder(cog, 360)
    return spd, cog

def lonlat_shifted(lon, lat, heading, starboard=0, forward=0):
    """
    Return *lon*, *lat* shifted to a position *starboard* meters
    to starboard, and *forward* meters forward of their original
    values, on a platform with a given *heading* in compass
    degrees.
    """
    coffset = starboard + 1j * forward
    itheta = heading * (-1j*np.pi/180.0)
    cdxdy = coffset * np.exp(itheta)
    hx, hy = lonlat_metrics(lat)
    newlon = lon + cdxdy.real / hx
    newlat = lat + cdxdy.imag / hy
    return newlon, newlat

def xducer_offset(dday, lon, lat, uref, vref, h, ndiff=2):
    """
    Estimate the offset of an ADCP transducer relative to a GPS antenna.

    *dday*, *lon*, *lat* are end-of-ensemble time and position.

    *uref*, *vref* are measured ref layer velocity relative to the ship.

    *h* is end-of-ensemble heading.

    *ndiff* is the number of difference operations applied to
    the estimated velocity when fitting the offset.

    All input arrays must be 1-D and have the same length.  They may
    be masked or they may use NaNs.  As much as possible, they should
    constitute a single continuous time series; do not compress them
    to remove internal gaps and glitches.

    Returns: *dx*, *dy*, *signal*.

    *dx* and *dy* are the starboard
    and forward offsets in meters of the transducer relative to the
    gps antenna. *signal* is a measure of the amount of information
    available from changes in the ship's course.

    """
    if np.ma.count(uref) < 4:
        return 0, 0, 0

    arr = np.ma.vstack((dday, lon, lat, uref, vref, h))
    arr = np.ma.masked_invalid(arr)
    jbad = np.any(arr.mask, axis=0)
    arr[:,jbad] = np.ma.masked

    u, v = uv_from_txy(arr[0], arr[1], arr[2], pad=False)
    uraw = u + uref[1:]
    vraw = v + vref[1:]

    h = h*(np.pi/180.0)
    dt = np.ma.diff(dday) * 86400
    ch = np.ma.diff(np.cos(h)) / dt
    sh = np.ma.diff(np.sin(h)) / dt

    urawd = np.ma.diff(uraw, n=ndiff)
    vrawd = np.ma.diff(vraw, n=ndiff)
    chd = np.ma.diff(ch, n=ndiff)
    shd = np.ma.diff(sh, n=ndiff)

    denom = np.ma.dot(chd, chd) + np.ma.dot(shd, shd)
    a = -1 / denom
    dx = a * (np.ma.dot(urawd, chd) - np.ma.dot(vrawd, shd))
    dy = a * (np.ma.dot(urawd, shd) + np.ma.dot(vrawd, chd))
    signal = denom * np.ma.median(dt)**2

    return dx, dy, signal


def pretty_llstr(fl, ptype, googlestr=False):
    '''
    return classic nautical  "deg frac N" for lon or lat

    fl is floating point lon or lat
    ptype (position type) is 'lat' or 'lon'
    '''
    #
    # TODO: add unicode for deg and minute symbols
    #
    if fl == 0.0:
        if googlestr:
            return '00%%2000.0'
        else:
            return '00 00.00'
    #
    wrapped = np.remainder(np.remainder(fl,360)+180,360)-180
    #
    letter = {'lat': {-1:'S', 1:'N'},
              'lon': {-1:'W', 1:'E'}}[ptype][np.sign(wrapped)]
    fla = np.abs(wrapped)
    deg = np.floor(fla)
    frac = fla - deg
    #
    if googlestr:
        return '%d%%20%7.5f%s' % (deg, 60*frac, letter)
    else:
        return '%3d %7.5f %s' % (deg, 60*frac, letter)
