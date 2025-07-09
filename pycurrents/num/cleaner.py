"""
Functions for detecting 1-D data outliers and for using
interpolation to replace masked points.

Functionality is starting out quite similar--but not identical--to our
Matlab glitch.m and cleaner.m.

The low-level core is the glitch routine, imported here from
a module in cython.

We may want to redesign the API.  The pure function approach
has the disadvantage of not providing access to some calculated
quantities of potential interest, such as the multiglitch threshold.


"""
import numpy as np
import numpy.ma as ma

from pycurrents.num.glitch import glitch
from pycurrents.num.grid import interp1
from pycurrents.num.runstats import Runstats

def cleaner(arr, masked=True, **kw):
    """
    Return arr with glitches and pre-masked areas filled in.
    The *masked* kwarg is passed to fillmasked, the other
    kwargs are passed to multiglitch. fillmasked is
    used with the resulting mask.

    This is a convenience function; if you want the intermediate
    mask, then call multiglitch and fillmasked separately.
    """
    arr = ma.array(arr, dtype=float, copy=True).ravel()
    mask = multiglitch(arr, **kw)
    arr = fillmasked(ma.masked_where(mask, arr, copy=False), masked=masked)
    return arr

def multiglitch(arr, threshold=None, factor=2, order=1, window=None):
    """
    Given a possibly masked array, return a mask updated to remove glitches.

    This is an extension of the underlying glitch routine; it includes
    an optional automatic determination of the glitch threshold, and
    it applies the glitch detector multiple times to decimated
    data so as to be able to handle short runs of points displaced
    from the desired curve.

    threshold: trigger value used by glitch for 3 successive second
               differences.  Default is *None*, in which case it
               is calculated based on the value of *factor*.
               It may be an array matching *arr*, with a slowly
               varying threshold criterion.

    factor: threshold is set to *factor* times an estimated median
            absolute value of second differences

    window: if not None, and if threshold is None, then instead of
           calculating the median absolute value from the whole series,
           it will be calculated over this window, so the threshold
           will change along the array.

    order: number of glitch passes on subsampled data slices.
           If order is 3, for example, there will be 3 passes, each
           working with every third point. Default is 1.

    """
    arr = ma.array(arr, dtype=float)
    if arr.ndim != 1:
        raise ValueError("Input array must be 1-D")
    mask = ma.getmaskarray(arr)
    if threshold is None:
        if window is None:
            ad2 = np.abs(np.diff(arr.compressed(), n=2))
            step = max(1, arr.shape[0]//500)
            threshold = np.median(ad2[::step]) * factor
        else:
            ad2 = np.ma.abs(np.ma.diff(arr, 2))
            if window % 2 == 0:   # Ensure it is odd.
                window += 1
            rs = Runstats(ad2, window)
            threshold = np.empty(arr.shape, dtype=float)
            threshold[1:-1] = rs.median * factor
            threshold[0] = threshold[1]
            threshold[-1] = threshold[-2]
            if np.ma.is_masked(threshold):
                threshold = fillmasked(threshold, masked=False)
            # If arr was constant over an interval, there were
            # no glitches, so any non-zero threshold will do.
            threshold[threshold == 0] = 1
    if order == 1:
        mask = glitch(arr, threshold)
    else:
        for i in range(order):
            s = slice(i, None, order)
            if np.iterable(threshold):
                mask[s] |= glitch(arr[s], threshold[s])
            else:
                mask[s] |= glitch(arr[s], threshold)
    return mask

def outliers(arr, stdthresh, stdwindow, medwindow=None):
    """
    Return a mask with arr outliers.

    Points are masked if they exceed the median within *medwindow*
    by *stdthresh* times the standard deviation calculated within
    *stdwindow*.  If *medwindow* is None, it is set equal to
    *stdwindow*.

    If arr is a masked array, the output mask will include the
    originally masked points.
    """

    arr = np.asanyarray(arr)
    if np.ma.isMA(arr):
        _abs = np.ma.abs
    else:
        _abs = np.abs
    rs = Runstats(arr, stdwindow, masked=True)
    if medwindow is None:
        rsmed = rs
    else:
        rsmed = Runstats(arr, medwindow)
    mask = _abs(arr - rsmed.median) > stdthresh * rs.std
    return mask.filled(True)

def fillmasked(arr, x=None, masked=True, nancheck=False, **kw):
    """
    Return array with masked elements filled by
    linear interolation.

    *arr* must be a 1-D sequence

    If *nancheck* is True, nan values in arr are masked.
    Default is False.

    *x* must be None (default) or a monotonically increasing
    non-masked sequence matching *arr*.

    If masked is True (default), a masked array will be returned,
    and only internal points will be filled;  masked end points
    may be present.

    If masked is False, np.interp is used with 'left' and 'right'
    keywords passed through.  This will return an ndarray.  By
    default, np.interp will use the closest valid points to fill
    masked end points.

    """
    if nancheck:
        arr = ma.masked_invalid(arr)
    else:
        arr = ma.array(arr, dtype=float, copy=True)
    if arr.ndim != 1:
        raise ValueError("Input array must be 1-D")
    mask = ma.getmaskarray(arr)
    goodm = np.logical_not(mask)
    if x is None:
        x = np.arange(arr.shape[0], dtype=float)
    else:
        x = np.asarray(x)
        if x.shape != arr.shape:
            raise ValueError("shapes of x and arr must match")
        if (np.diff(x) <= 0).any():
            raise ValueError("x is not monotonically increasing")
    if masked:
        arr[mask] = interp1(x[goodm], arr[goodm], x[mask], masked=True)
        return arr

    out = arr.data.copy()
    out[mask] = np.interp(x[mask], x[goodm], out[goodm], **kw)
    return out

