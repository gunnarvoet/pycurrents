"""
Calculate the index distance or time interval between a point
and the nearest transition from True to False or vice-versa.

"""

cimport numpy as np
import numpy as np

import cython

cdef extern from "math.h":
    double fabs(double)

@cython.boundscheck(False)
def mask_nonincreasing(_arr):
    """
    Given a 1-D sequence or masked array, return a 1-D float64 masked array
    in which the unmasked values are monotonically increasing.
    """
    cdef np.int64_t N = len(_arr)
    cdef np.uint64_t i, i0
    cdef np.float64_t last
    cdef np.ndarray[np.uint8_t, ndim=1] bmask = np.empty((N,), dtype=np.uint8)
    cdef np.ndarray[np.float64_t, ndim=1] dat
    cdef np.ndarray[np.uint8_t, ndim=1] omask

    _arr = np.asanyarray(_arr, dtype=np.float64)

    if _arr.ndim != 1:
        raise ValueError("Only 1-D arrays are permitted.")

    if np.ma.isMaskedArray(_arr):
        mask = _arr.mask
        dat = _arr.data
    else:
        mask = False
        dat = _arr

    if not isinstance(mask, np.ndarray):
        if mask:
            return _arr # all masked already; nothing more to do
        else:
            bmask[0] = 0
            last = dat[0]
            for i in range(1, N):
                if dat[i] > last:
                    last = dat[i]
                    bmask[i] = 0
                else:
                    bmask[i] = 1

    else:
        omask = mask.astype(np.uint8)
        i0 = 0
        while i0 < N and omask[i0]:
            bmask[i0] = 1
            i0 += 1
        if i0 < N:
            bmask[i0] = 0
            last = dat[i0]
            for i in range(i0+1, N):
                if omask[i] or dat[i] <= last:
                    bmask[i] = 1
                else:
                    bmask[i] = 0
                    last = dat[i]

    return np.ma.array(dat, mask=bmask)


@cython.boundscheck(False)
def neighbor_count(_arr):
    """
    Calculate the distance to the nearest True/False boundary.

    Input: sequence that can be converted to a 1-D boolean ndarray

    Returns: integer ndarray of the same length as the input.

    Positive numbers are the number of indices to the nearest
    neighbor that is True; negative numbers are the number of
    indices to the nearest neighbor that is False, plus 1.  The
    array is treated as if points beyond the ends are True.

    If the input is a mask from a masked array, the positive numbers
    are the depth within the masked region, negative numbers are the
    depth (smallest number of valid neighbors) within the unmasked region.

    Example::

        >>> b = [0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1]
        >>> neighbor_count(b)
        array([ 0, -1, -1,  0,  1,  2,  3,  2,  1,  0, -1,  0,  1,  2,  3])
        >>> b.reverse()
        >>> neighbor_count(b)
        array([ 3,  2,  1,  0, -1,  0,  1,  2,  3,  2,  1,  0, -1, -1,  0])

    """
    cdef np.int64_t N = len(_arr)
    cdef np.uint64_t i, ii
    cdef np.int64_t k
    cdef np.int64_t k0
    cdef np.uint8_t a, aprev
    cdef np.ndarray[np.int64_t, ndim=1] count = np.empty((N,), dtype=np.int64)
    cdef np.ndarray[np.uint8_t, ndim=1] arr

    arr = np.asarray(_arr, dtype=np.uint8)

    aprev = 1
    k = N - 1
    for i in range(N):
        a = arr[i]
        if aprev and not a:      # start of good range
            k = 0
        elif a and not aprev:    # start of bad range
            k = 1
        else:
            if a:                # continue bad range
                k += 1
            else:
                k -= 1           # continue good range
        count[i] = k
        aprev = a

    aprev = 1
    #for i in range(N-1, -1, -1):    ### evidently not yet supported
    for ii in range(N):
        i = N - 1 - ii
        a = arr[i]
        if aprev and not a:      # start of good range
            k = 0
        elif a and not aprev:    # start of bad range
            k = 1
        else:
            if a:                # continue bad range
                k += 1
            else:
                k -= 1           # continue good range
        if k == 0 or k == 1:
            count[i] = k
        else:
            k0 = count[i]
            if  ((k < 0 and (k > k0 or k > -k0))
                    or (k > 1 and (k < k0 or k < -k0))):
                count[i] = k

        aprev = a

    return count


@cython.boundscheck(False)
def neighbor_span(_arr, _dday):
    """
    Similar to neighbor_count, but the second argument provides
    the measure of distance.

    """

    cdef np.int64_t N = len(_arr)
    cdef np.uint64_t i, ii
    cdef np.float64_t k, t
    cdef np.float64_t k0
    cdef np.uint8_t a, aprev
    cdef np.ndarray[np.uint8_t, ndim=1] arr
    cdef np.ndarray[np.float64_t, ndim=1] dday
    cdef np.ndarray[np.float64_t, ndim=1] count

    if len(_dday) != N:
        raise ValueError("inputs must have same size; found %d, %d"
                          % (N, len(_dday)))


    arr0 = np.asarray(_arr, dtype=np.uint8)
    dday0 = np.asarray(_dday, dtype=np.float64)

    if arr0.ndim != 1 or dday0.ndim != 1:
        raise ValueError("inputs must be 1-D")

    # As of 2011/01/09, if we don't use the intermediate step of
    # making the ndarrays and then checking their dimensions,
    # we can get a segfault or other memory access error
    # when trying to run the function after
    # it has raised an exception once.

    arr = arr0
    dday = dday0

    count = np.empty((N,), dtype=np.float64)


    aprev = 1
    k = 1e100
    for i in range(N):
        a = arr[i]
        if aprev and not a:      # start of good range
            k = dday[i]
        elif a and not aprev and i>0:
            k = dday[i-1]        # time of last good
        if a:
            count[i] = dday[i] - k
        else:
            count[i] = k - dday[i]
        aprev = a

    aprev = 1
    for ii in range(N):
        i = N - 1 - ii
        a = arr[i]
        if aprev and not a:      # start of good range
            k = dday[i]
        elif a and not aprev and i<N:
            k = dday[i+1]        # time of last good

        if a:
            t = k - dday[i]
        else:
            t = dday[i] - k

        k0 = count[i]
        if  (fabs(t) < fabs(k0)):
            count[i] = t
        aprev = a

    return count

def expand_mask(mask, margin):
    """
    newmask = expand_mask(mask, margin)

    Extends masked zones (True values) within mask by *margin* points
    on each side.

    Example::

        >>> expand_mask([0,0,0,0,1,1,1,1,0,0,0], 1)

        array([ True, False, False,  True,  True,  True,  True,  True,  True,
               False,  True], dtype=bool)

    Note that at present the edges are treated as if masked outside
    the range of the array, so expanding the mask always masks end
    points.  This may be change by a future option or new default.

    """

    return neighbor_count(mask) >= (1 - margin)

@cython.boundscheck(False)
def segments(mask, n=0):
    """
    seglist = segments(mask, n=0)

    Divide a Boolean array into segments with consecutive False values.

    Parameters
    ----------
    mask : array-like
        Sequence that can be converted to a 1-D boolean ndarray.
    n : int, optional
        If nonzero, break segments so that they have no more than *n*
        values.  Default is 0, meaning no limit.  Minimum non-zero
        value is 2.

    Returns
    -------
    array, (nsegs, 2)
         Each row gives the start (inclusive) and stop (exclusive)
         of a segment.

    When applied to the mask from a masked array, this provides the
    segments with valid values.

    """
    cdef np.int64_t N = len(mask)
    cdef np.int64_t i, i0, i1, iseg
    cdef np.int64_t inseg
    cdef np.int64_t nmax
    cdef np.ndarray[np.int8_t, ndim=1] arr
    cdef np.ndarray[np.int64_t, ndim=2] buf

    buf = np.empty((N//2+1, 2), dtype=np.int64)
    arr = np.asarray(mask, dtype=np.int8)
    if n != 0 and not (n >= 2):
        raise ValueError("n must be 0 or >=2")
    nmax = n
    inseg = 0
    iseg = 0

    for i in range(N):
        if arr[i] == 0:  # In a segment.
            if inseg == 0:  # At the start.
                i0 = i
            inseg += 1
            if inseg == nmax:  # It's big enough.
                buf[iseg, 0] = i0
                buf[iseg, 1] = i + 1
                iseg += 1
                inseg = 0
        else:
            if inseg > 0:
                buf[iseg, 0] = i0
                buf[iseg, 1] = i
                iseg += 1
                inseg = 0
    if inseg > 0:
        buf[iseg, 0] = i0
        buf[iseg, 1] = N
        iseg += 1

    return np.array(buf[:iseg], copy=True)


@cython.boundscheck(False)
def segment_lengths(_arr):
    """
    lengths = segment_lengths(mask)

    Calculate lengths of sequences of False or True.

    Parameters
    ----------
    mask : array-like
        Sequence that can be converted to a 1-D boolean ndarray.

    Returns
    -------
    integer array the same length as *mask*
         Each entry in mask is replaced by the length of the sequence of
         consecutive True, if the entry is True, and minus the length of
         the sequence of consecutive False, if the mask is False.

    Example::

        >>> m = [0,0,0, 1, 1, 1, 0, 0, 1, 0]
        >>> segment_lengths(m)
        array([ 3,  3,  3, -3, -3, -3,  2,  2, -1,  1])

    """
    cdef np.int64_t N = len(_arr)
    cdef np.uint64_t i, ii, i0, countF, countT
    cdef np.ndarray[np.uint8_t, ndim=1] arr
    cdef np.ndarray[np.int64_t, ndim=1] out

    arr = np.asarray(_arr, dtype=np.uint8)
    out = np.zeros((int(N),), dtype=np.int64)
    countF = 0
    countT = 0

    for i in range(N):
        if arr[i] != 0:            # True mask: "bad"
            countT += 1
            if i == 0 or countF:  # starting a True segment
                if countF:   # end a False segment
                    for ii in range(i0, i):
                        out[ii] = countF
                    countF = 0
                i0 = i
        else:
            countF += 1
            if i == 0 or countT:  # starting a False segment
                if countT:   # end a True segment
                    for ii in range(i0, i):
                        out[ii] = -countT
                    countT = 0
                i0 = i

    if countT:
        for ii in range(i0, N):
            out[ii] = -countT
    elif countF:
        for ii in range(i0, N):
            out[ii] = countF
    return out


## The following is a cython replacement for the custom pnpoly
## wrapper in matplotlib, which may go away.

cdef extern from "_pnpoly.h":
    int pnpoly(int npol, double *xv, double *yv, double x, double y)

@cython.boundscheck(False)
def points_inside_poly(xypoints, xyverts):
    """
    mask = points_inside_poly(xypoints, xyverts)

    Return a boolean ndarray, True for points inside the polygon.

    *xypoints*
        a sequence of N x,y pairs. It may be a masked array, in which
        case a masked array will be returned.
    *xyverts*
        sequence of x,y vertices of the polygon.  It need not be
        closed.  It must not be a masked array.
    *mask*   an ndarray of length N.

    A point on the boundary may be treated as inside or outside.
    See `pnpoly <http://www.ecse.rpi.edu/Homepages/wrf/Research/Short_Notes/pnpoly.html>`_

    This was taken from matplotlib.nxutils, but the C wrapper
    has been replaced with a cython-generated wrapper.  It probably
    could be made more efficient by reducing copying, and by moving
    more functionality to the C level.
    Unlike the original, this version handles a masked array for the
    first argument.
    """
    cdef np.ndarray[np.float_t, ndim=2] xyp
    cdef np.ndarray[np.float_t, ndim=1] xv, yv
    cdef unsigned int i

    _xyp = np.asanyarray(xypoints, dtype=np.float64)
    if _xyp.ndim == 1:
        _xyp = _xyp[np.newaxis, :]
    _xyv = np.asarray(xyverts, dtype=np.float64)
    if _xyv.ndim == 1:
        _xyv = _xyv[np.newaxis, :]
    if _xyp.ndim > 2 or _xyv.ndim > 2:
        raise ValueError("Too many dimensions")
    if _xyp.shape[1] != 2 or _xyv.shape[1] != 2:
        raise ValueError("Last dimension of inputs must be 2")

    if np.ma.isMA(_xyp):
        _mask = np.ma.getmaskarray(_xyp)
        _mask = np.logical_or(_mask[:,0], _mask[:,1])
        _xyp = _xyp.filled(0)
    else:
        _mask = None


    npts = _xyp.shape[0]
    npol = _xyv.shape[0]
    cdef np.ndarray[np.uint8_t, ndim=1] mask = np.zeros((npts,), dtype=np.uint8)
    xv = np.ascontiguousarray(_xyv[:,0])
    yv = np.ascontiguousarray(_xyv[:,1])
    xyp = _xyp

    for i in range(npts):
        mask[i] = pnpoly(npol, <double *>xv.data, <double *>yv.data,
                                                    xyp[i,0], xyp[i,1])

    if _mask is not None:
        return np.ma.array(mask, mask=_mask, dtype=bool,
                            copy=False, shrink=True)
    else:
        return np.asarray(mask, dtype=bool)

