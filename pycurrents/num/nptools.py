"""
Functions, wrappers, etc. to facilitate numpy programming.

ma_angle (no longer needed)

loadtxt_, loadtxt_no_warn

rangeslice, lon_rangeslices, lonslice_array, lonslice_arrays

Flags

"""
import logging
import warnings

import numpy as np

_log = logging.getLogger(__name__)


def ma_angle(arg, deg=False):
    """
    masked array version of np.angle; strangely missing from ma.
    (Obsolete; I added it, and it is in at least numpy 1.7.)

    This always returns a masked array; it could be modified to
    do so only if the input is masked.
    """
    arg = np.asanyarray(arg)
    mask = np.ma.getmaskarray(arg)
    ret = np.ma.array(np.angle(arg, deg), mask=mask)
    return ret


def loadtxt_no_warn(*args, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return np.loadtxt(*args, **kwargs)


def loadtxt_(*args, **kwargs):
    """
    Trap no-data condition in np.loadtxt, and return empty array.
    For any other exception, log the exception, and return empty array.
    """

    try:
        return loadtxt_no_warn(*args, **kwargs)
    except IOError:
        pass
    # FIXME: find a more systematic way to exclude/skip badly formatted line
    except ValueError:  # case where first line has the wrong format
        return loadtxt_no_warn(*args, skiprows=1, **kwargs)
    except Exception as ex:
        _log.exception(f"Unexpected exception from loadtxt: {ex}")
    dtype = kwargs.get('dtype', float)
    ndmin = max(kwargs.get('ndmin', 1), 1)
    return np.zeros((0,), dtype) if ndmin == 1 else np.zeros((0, 1), dtype)


def rangeslice(arr, *args, step=None, range_=None):
    '''
    Return the slice that includes a range within a monotonic sequence.

    The range is specified by one or two arguments, best understood
    by example for the case where the sequence is time, say in decimal
    days:
    * A pair of arguments will be start time (inclusive) and end
      time (exclusive).
    * A single argument may denote:
        * days from start, if positive
        * days from end, if negative
        * the full range, if the argument is the string 'all'

    The sequence can be integer, floating point, or np.datetime64.
    If using np.datetime64 the start and end must also be datetime64;
    if range_ is a scalar it must be timedelta64.

    If the sequence is monotonic but decreasing, the 'start' and 'end'
    of the range are still intepreted as the lowest and highest value,
    respectively.

    Parameters
    ----------
    arr : array-like
        1-D monotonic sequence
    arg1, [arg2] : str | number, [number]
        Range specifiers (see above)
    step : int, optional
        The step attribute of the returned slice object.

    Returns
    -------
    slice object

    Raises
    ------
    ValueError
        If the array is not monotonic or there are too many or too
        few arguments.

    Notes
    -----
    If there is no slice of *arr* that brackets the requested
    *range_*, then slice(0, 0, step) is returned.  Test for this
    with, for example::

        if sl.start == sl.stop:
            raise ValueError("Out of range")

    If the input array has zero length, slice(0, 0, step) is returned.

    Returned slices always have numeric values for start and stop,
    since they are designed for a particular array.  This allows one
    to retrieve the start and stop values and manipulate them, as is
    required by BinfileSet.

    The original signature, now deprecated, is::

      rangeslice(arr, range_=range_)

    '''
    arr = np.asarray(arr)
    n = len(arr)
    if n == 0:
        return slice(0, 0, step)
    increasing = True
    if n > 1:
        diffs = np.diff(arr)
        if np.less_equal(diffs, 0, casting='unsafe').all():
            increasing = False
            arr = arr[::-1]
        elif np.less(diffs, 0, casting='unsafe').any():
            raise ValueError("rangeslice input must be monotonic")
    if range_ is not None:
        warnings.warn("The 'range_' kwarg is deprecated.")
        if len(args):
            raise ValueError("With a 'range_' kwarg given there should be no"
                             " additional range arguments.")
    else:  # preferred signature
        if len(args) == 2:
            range_ = args
        elif len(args) == 1:
            range_ = args[0]
        else:
            raise ValueError("Rangeslice requires one or two range args.")

    if range_ is None or (isinstance(range_, str) and range_ == 'all'):
        return slice(0, n, step)

    if not np.iterable(range_):
        if np.less(range_, 0, casting='unsafe'):
            istart = np.searchsorted(arr, arr[-1] + range_, side='right')
            istop = n
        else:
            istop = np.searchsorted(arr, arr[0] + range_)
            istart = 0
    else:
        if arr[0] > range_[1] or arr[-1] < range_[0]:
            return slice(0, 0, step)
        istart, istop = np.searchsorted(arr, range_)

    if not increasing:
        istart, istop = (n - istop, n - istart)
    return slice(istart, istop, step)


def lon_rangeslices(lon, limits, step=1):
    """
    Provide new lon array and slices for `limits` in a global `lon` array.

    Unlike :func:`~pycurrents.num.rangeslice`, this handles ranges that
    span the wrap-around point by supplying two slices.

    Parameters
    ----------
    lon : array_like
        1-D monotonic sequence of longitudes spanning the globe,
        typically either 0 to 360 or -180 to 180 (non-overlapping),
        such as is supplied with global data products on a uniform
        lon-lat grid.
    limits : array_like
        1-D, [west, east] longitudes specifying a section of `lon`,
        inclusive on the left and exclusive on the right.  West
        longitude may be given as negative (e.g., -90) or positive
        (e.g., 270).
    step : int
        Slice object step.

    Returns
    -------
    lonseg : ndarray
        1-D array of monotonic longitudes within the specified `limits`.
    lonsl1 : slice object
        The slice of `lon` providing the `lonseg`, or the western part
        of it if `limits` spans the array edge.
    lonsl2 : {``slice``, ``None``}
        If `limits` spans the array edge this is the eastern slice;
        otherwise, it is ``None``.

    """
    nlon = len(lon)
    xlon = np.hstack((lon - 360, lon, lon + 360))
    west, east = limits
    if east < west:  # e.g., limits = (165, -165) for 165E to 165W
        east += 360
    xsl = rangeslice(xlon, west, east)
    start = xsl.start % nlon
    stop = xsl.stop % nlon
    if stop > start:
        lonsl = slice(start, stop, step)
        newlon = lon[lonsl]
        return newlon, lonsl, None

    # It's split
    lonsl1 = slice(start, None, step)
    start = (nlon - start) % step
    lonsl2 = slice(start, stop, step)
    newlon = np.hstack((lon[lonsl1], lon[lonsl2] + 360))
    if newlon[-1] >= 360:
        newlon -= 360
    return newlon, lonsl1, lonsl2


def _step_from_slices(slices, axis):
    # Helper for following functions.
    if slices is not None:
        step_or_slice = slices[axis]
        if step_or_slice is None:
            step = 1
        elif isinstance(step_or_slice, slice):
            step = step_or_slice.step
        else:
            step = step_or_slice
    else:
        step = 1
    return step


def extract_with_lonslices(arr, lonsl1, lonsl2,
                           slices=None, axis=-1):
    """
    Helper for `lonslice_array` and `lonslice_arrays`.
    """
    def insert_slice(slices, sl, axis):
        step = _step_from_slices(slices, axis)
        slices = list(slices)
        sl = slice(sl.start, sl.stop, step)
        slices[axis] = sl
        return tuple(slices)

    if slices is None:
        slices = tuple([slice(None)] * arr.ndim)
    slices1 = insert_slice(slices, lonsl1, axis)
    if lonsl2 is None:
        return arr[slices1]
    left = arr[slices1]
    slices2 = insert_slice(slices, lonsl2, axis)
    right = arr[slices2]
    if np.ma.isMA(left) or np.ma.isMA(right):
        return np.ma.concatenate((left, right), axis=axis)
    try:
        lon_name = arr.dims[axis]
    except AttributeError:
        pass
    else:
        import xarray
        return xarray.concat((left, right), dim=lon_name)

    return np.concatenate((left, right), axis=axis)


def lonslice_array(arr, lon, limits, slices=None, axis=-1):
    """
    Extract a longitude range from an `arr` and its `lon` array.

    This may involve concatenating subarrays from the end and
    the start of each original array.

    Parameters
    ----------
    arr : array_like
        N-D array with `axis` corresponding to `lon`.
    lon : array_like
        1-D monotonic sequence of longitudes spanning the globe,
        typically either 0 to 360 or -180 to 180 (non-overlapping),
        such as is supplied with global data products on a uniform
        lon-lat grid.
    limits : array_like
        1-D, [west, east] longitudes specifying a section of `lon`,
        inclusive on the left and exclusive on the right.  West
        longitude may be given as negative (e.g., -90) or positive
        (e.g., 270).
    slices : {``None``, indexing ``tuple``}, optional
        If not ``None`` this must have an entry for each dimension
        of `arr`.  Each entry other than that for `axis` must be
        a valid ``slice`` object or scalar index. The entry for
        `axis` may be None, an int to specify the step, or a slice
        object from which the step attribute will be used.
    axis : int, optional
        Longitude dimension of `arr`; default is -1, the right-most
        dimension.

    Returns
    -------
    arrsub: ndarray
        N-D subarray of `arr` with the selected longitude `limits`,
        and with other dimensions sliced based on `slices`.
    lonsub : ndarray
        1-D array of monotonic longitudes within the specified *limits*.

    See Also
    --------
    lonslice_arrays : operates on a sequence of arrays

    """
    step = _step_from_slices(slices, axis)
    lonsub, lonsl1, lonsl2 = lon_rangeslices(lon, limits, step=step)
    arrsub = extract_with_lonslices(arr, lonsl1, lonsl2,
                                    slices=slices, axis=axis)
    try:
        lon_name = arrsub.dims[axis]
    except AttributeError:
        pass
    else:
        arrsub[lon_name] = lonsub
    return arrsub, lonsub


def lonslice_arrays(arrs, lon, limits, slices=None, axis=-1):
    """
    Extract a longitude range from each array in `arrs`, and `lon`.

    This may involve concatenating subarrays from the end and
    the start of each original array.

    Parameters
    ----------
    arrs : sequence
        Sequence of N-D arrays with `axis` corresponding to `lon`.
    lon : array_like
        1-D monotonic sequence of longitudes spanning the globe,
        typically either 0 to 360 or -180 to 180 (non-overlapping),
        such as is supplied with global data products on a uniform
        lon-lat grid.
    limits : array_like
        1-D, [west, east] longitudes specifying a section of `lon`,
        inclusive on the left and exclusive on the right.  West
        longitude may be given as negative (e.g., -90) or positive
        (e.g., 270).
    slices : {``None``, indexing ``tuple``}, optional
        If not ``None`` this must have an entry for each dimension
        of `arr`.  Each entry other than that for `axis` must be
        a valid ``slice`` object or scalar index.  The entry for
        `axis` may be None, an int to specify the step, or a slice
        object from which the step attribute will be used.
    axis : int, optional
        Longitude dimension of `arr`; default is -1, the right-most
        dimension.

    Returns
    -------
    arrsubs: sequence
        For each array in `arrs`, this holds the N-D subarray with
        the selected longitude `limits`,
        and with other dimensions sliced based on `slices`.
    lonsub : ndarray
        1-D array of monotonic longitudes within the specified *limits*.

    """
    step = _step_from_slices(slices, axis)
    lonsub, lonsl1, lonsl2 = lon_rangeslices(lon, limits, step=step)
    arrsubs = []
    for arr in arrs:
        subarr = extract_with_lonslices(arr, lonsl1, lonsl2,
                                        slices=slices, axis=axis)
        arrsubs.append(subarr)
        try:
            lon_name = subarr.dims[axis]
        except AttributeError:
            pass
        else:
            subarr[lon_name] = lonsub

    return arrsubs, lonsub


class Flags:
    """
    Manage an array of flags, with input/output as flags or masks.
    The use of ndarrays is assumed; there is no automatic conversion.
    """
    def __init__(self, shape=None, flags=None, nbytes=1, names=None):
        """
        Initialization from an existing array of flags:

            flags = Flags(flags=origflags, names=['a', 'b', 'c'])

        With no initial flag array, initialize for adding masks:

            flags = Flags(shape=(100, 45), names=['a', 'b', 'c'])

        *nbytes* is optional; if omitted, it will
        be determined by the length of the *names* sequence.

        """
        n = len(names)
        bits = max(nbytes*8, n)
        self.names = names
        self.bit_from_name = dict(zip(names, range(n)))
        self.name_from_bit = dict(zip(range(n), names))

        if flags is not None:
            bits = max(bits, 8*flags.itemsize)

        if bits < 9:
            nbytes = 1
        elif bits < 17:
            nbytes = 2
        elif bits < 33:
            nbytes = 4
        else:
            nbytes = 8

        self.dtype = {1:np.uint8, 2:np.uint16,
                            4:np.uint32, 8:np.uint64}[nbytes]
        self.nbytes = nbytes
        if flags is None:
            self.flags = np.zeros(shape, dtype=self.dtype)
        else:
            self.flags = np.array(flags, dtype=self.dtype, copy=True)

    def addflags(self, flags, index_obj=None):
        if index_obj is None:
            target = self.flags
        else:
            target = self.flags[index_obj]
        target |= flags

    def addmask(self, mask, name, index_obj=None):
        if index_obj is None:
            target = self.flags
        else:
            target = self.flags[index_obj]
        bit = self.bit_from_name[name]
        if mask.itemsize == self.nbytes:
            target |= (mask.view(self.dtype) << bit)
        else:
            target |= (mask.astype(self.dtype) << bit)

    def tomask(self, names='all'):
        if names == 'all':
            return self.flags != 0
        bitmask = 0
        for name in names:
            bitmask |= (1 << self.bit_from_name[name])
        bitmask = np.array(bitmask, dtype=self.dtype)
        return (self.flags & bitmask) != 0

    def tonames(self, num):
        """
        Given a single flag value, return the list of flag names.
        """
        names = [n for n in self.names
                    if (num & (1 << self.bit_from_name[n]))]
        return names

    def maxflag(self, names='all'):
        '''
        max possible flag
        '''
        mf = 0
        if names == 'all':
            names = self.names
        for name in names:
            mf += 2**self.bit_from_name[name]

        return mf

# I rescued this from matplotlib.cbook prior to removal; it seems like
# a useful utility to have available.
def unmasked_index_ranges(mask, compressed=True):
    """
    Find index ranges where *mask* is *False*.

    *mask* will be flattened if it is not already 1-D.

    Returns Nx2 :class:`numpy.ndarray` with each row the start and stop
    indices for slices of the compressed :class:`numpy.ndarray`
    corresponding to each of *N* uninterrupted runs of unmasked
    values.  If optional argument *compressed* is *False*, it returns
    the start and stop indices into the original :class:`numpy.ndarray`,
    not the compressed :class:`numpy.ndarray`.  Returns *None* if there
    are no unmasked values.

    Example::

      y = ma.array(np.arange(5), mask = [0,0,1,0,0])
      ii = unmasked_index_ranges(ma.getmaskarray(y))
      # returns array [[0,2,] [2,4,]]

      y.compressed()[ii[1,0]:ii[1,1]]
      # returns array [3,4,]

      ii = unmasked_index_ranges(ma.getmaskarray(y), compressed=False)
      # returns array [[0, 2], [3, 5]]

      y.filled()[ii[1,0]:ii[1,1]]
      # returns array [3,4,]

    Prior to the transforms refactoring, this was used to support
    masked arrays in Line2D.
    """
    mask = mask.reshape(mask.size)
    m = np.concatenate(((1,), mask, (1,)))
    indices = np.arange(len(mask) + 1)
    mdif = m[1:] - m[:-1]
    i0 = np.compress(mdif == -1, indices)
    i1 = np.compress(mdif == 1, indices)
    assert len(i0) == len(i1)
    if len(i1) == 0:
        return None  # Maybe this should be np.zeros((0,2), dtype=int)
    if not compressed:
        return np.concatenate((i0[:, np.newaxis], i1[:, np.newaxis]), axis=1)
    seglengths = i1 - i0
    breakpoints = np.cumsum(seglengths)
    ic0 = np.concatenate(((0,), breakpoints[:-1]))
    ic1 = breakpoints
    return np.concatenate((ic0[:, np.newaxis], ic1[:, np.newaxis]), axis=1)
