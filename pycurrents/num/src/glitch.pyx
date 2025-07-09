"""
Detect and mask isolated glitches or clusters of glitches.
"""

cimport numpy as np
cimport cython
import numpy as np
import numpy.ma as ma


@cython.boundscheck(False)
cdef double abstwodiff(double *data,
                        unsigned int i0, unsigned int i1, unsigned int i2):
    cdef double x = data[i0] + data[i2] - 2 * data[i1]
    # avoid python abs function
    if x > 0:
        return x
    else:
        return -x

@cython.boundscheck(False)
def glitch(arr, thresh):
    """
    mask = glitch(arr, thresh)

    Locate extreme outliers while allowing jumps.

    *arr* is a sequence or masked array; do not use NaN.
    Where three consecutive second differences exceed *thresh*
    in magnitude, mask out the middle point (the glitch) among
    the 5 used to calculate those differences.  Repeat with
    the updated mask, advancing when the middle point is no longer
    judged a glitch.

    *thresh* may be a constant or an array the same length as *arr*

    Return a mask, True where glitches are found and at any
    positions that were originally masked.  If the input is a
    masked array, its mask is not changed.

    This routine does not presently detect problems with the first
    or last two points in the series.
    """

    cdef unsigned int i0, i1, i2, i3, i4, n
    cdef int cond0, cond1, cond2
    cdef int idif
    cdef double _thresh
    cdef int _thresh_is_array
    cdef np.ndarray[np.double_t, ndim=1, mode='c'] _athresh

    arr = np.asanyarray(arr, dtype=float, order='C')
    if arr.ndim == 0:
        arr = arr.reshape(1)
    if arr.ndim != 1:
        raise ValueError("Only 1-D arrays are supported")

    if np.iterable(thresh):
        thresh = np.asarray(thresh, dtype=float)
        if thresh.ndim == 0:
            thresh = thresh.reshape(1)
        if not thresh.shape == arr.shape:
            raise ValueError("thresh array must match data array")

        _athresh = thresh
        _thresh_is_array = 1
    else:
        _thresh = thresh
        _thresh_is_array = 0

    # Until cython supports numpy booleans, we have to use the uint8 equiv.
    _mask = np.array(ma.getmaskarray(arr), dtype=np.uint8, copy=True)

    if _mask.shape[0] - _mask.sum() < 5:
        return _mask
    cdef np.ndarray[np.uint8_t, ndim=1, mode='c'] mask = _mask
    cdef np.ndarray[np.double_t, ndim=1, mode='c'] data = ma.getdata(arr)

    n = data.shape[0]

    i0 = 0
    i4 = 0
    idif = 0

    while i4 < n:
        while mask[i0]:
            i0 += 1
        i1 = i0 + 1
        while mask[i1]:
            i1 += 1
        i2 = i1 + 1
        while mask[i2]:
            i2 += 1
        i3 = i2 + 1
        while mask[i3]:
            i3 += 1
        i4 = i3 + 1
        while i4 < n and mask[i4]:
            i4 += 1

        if _thresh_is_array:
            _thresh = _athresh[i2]

        if idif < 2:
            cond0 = abstwodiff(<double *>data.data, i0, i1, i2) > _thresh
            cond1 = abstwodiff(<double *>data.data, i1, i2, i3) > _thresh
        else:
            cond0 = cond1
            cond1 = cond2
        cond2 = abstwodiff(<double *>data.data, i2, i3, i4) > _thresh

        idif += 1

        while i4 < n:

            if cond2 and cond1 and cond0:
                mask[i2] = True
                i2 = i1 + 1
                while mask[i2]:
                    i2 += 1
                i3 = i2 + 1
                while mask[i3]:
                    i3 += 1
                i4 = i3 + 1
                while i4 < n and mask[i4]:
                    i4 += 1

                if _thresh_is_array:
                    _thresh = _athresh[i2]

                cond0 = abstwodiff(<double *>data.data, i0, i1, i2) > _thresh
                cond1 = abstwodiff(<double *>data.data, i1, i2, i3) > _thresh
                cond2 = abstwodiff(<double *>data.data, i2, i3, i4) > _thresh

            else:
                break

        i0 += 1

    return np.asarray(mask, dtype=bool)


