"""
Use Wirth's k_smallest algorithm to provide a fast median.

http://ndevilla.free.fr/median/median/index.html
"""

cimport numpy as np
import numpy as np

import cython

cdef extern from "med_wirth.h":
    int kth_smallest_i(int* a, int n, int k)
    long int kth_smallest_l(long int* a, int n, int k)
    float kth_smallest_f(float* a, int n, int k)
    double kth_smallest_d(double* a, int n, int k)

def median(arr, axis=None):
    """
    Use Wirth's fast algorithm to compute median along specified axis.

    *arr* may be any 1-D or 2-D sequence, including a masked array.

    Support for more dimensions may be added later.

    If *axis* is None, the median of the flattened array will be
    returned.

    Unlike np.median, this returns an integer if *arr* is integer.
    Consequently, if the number of elements along the specified axis
    is odd, it will return the lower of the two middle numbers for
    integer arguments.  For floating point arguments, it will return
    the average, like np.median.

    """
    cdef np.ndarray _arr
    cdef double tmp
    cdef int n, k, i, nout
    cdef int even

    arr = np.asanyarray(arr)
    if axis is None:
        arr = arr.ravel()
    if arr.ndim > 2:
        raise NotImplementedError("only 1 or 2 dimensions are supported now")
    if arr.dtype.kind not in "uif":
        raise ValueError("arr must be integer or floating point")

    masked = False
    if np.ma.isMA(arr):
        masked = True

    dtype = arr.dtype
    if arr.dtype.kind in "ui":
        if arr.dtype.itemsize == 8:
            dtype = np.int64
        else:
            dtype = np.int32

    if arr.ndim == 1:
        if masked:
            arr = arr.compressed()
            if not arr.dtype == dtype:
                arr = arr.astype(dtype)
        else:
            arr = arr.astype(dtype)

        n = arr.shape[0]
        if n == 0:
            if masked:
                return np.ma.masked
            else:
                if dtype == np.int32:
                    return 0
                else:
                    return np.nan

        _arr = arr

        if n & 1:
            k = n//2
            even = 0
        else:
            k = n//2 - 1
            even = 1
        if dtype == np.float64:
            tmp = kth_smallest_d(<double *>_arr.data, n, k)
            if even:
                tmp += kth_smallest_d(<double*>_arr.data, n, k+1)
                tmp *= 0.5
            return tmp
        elif dtype == np.float32:
            tmp = kth_smallest_f(<float *>_arr.data, n, k)
            if even:
                tmp += kth_smallest_f(<float*>_arr.data, n, k+1)
                tmp *= 0.5
            return tmp
        elif dtype == np.int64:
            return  kth_smallest_l(<long *>_arr.data, n, k)
        else:
            return kth_smallest_i(<int *>_arr.data, n, k)

    # Must be 2-D

    # Always work on the last axis.
    if axis == 0:
        arr = arr.T
    nout = arr.shape[0]

    if masked:
        aout = np.ma.zeros((nout,), dtype=dtype)
        for i in range(nout):
            a = arr[i].compressed()
            _arr = a
            n = a.shape[0]
            if n == 0:
                aout[i] = np.ma.masked
                continue
            elif n == 1:
                aout[i] = a[0]
                continue

            if n & 1:
                k = n//2
                even = 0
            else:
                k = n//2 - 1
                even = 1
            if dtype == np.float64:
                tmp = kth_smallest_d(<double *>_arr.data, n, k)
                if even:
                    tmp += kth_smallest_d(<double*>_arr.data, n, k+1)
                    tmp *= 0.5
                aout[i] = tmp
            elif dtype == np.float32:
                tmp = kth_smallest_f(<float *>_arr.data, n, k)
                if even:
                    tmp += kth_smallest_f(<float*>_arr.data, n, k+1)
                    tmp *= 0.5
                aout[i] = tmp
            elif dtype == np.int64:
                aout[i] =  kth_smallest_l(<long *>_arr.data, n, k)
            else:
                aout[i] =  kth_smallest_i(<int *>_arr.data, n, k)

    else:
        aout = np.zeros((nout,), dtype=dtype)
        arr =  np.array(arr, dtype=dtype, copy=True, order='C')
        n = arr.shape[1]
        if n == 0:
            if arr.dtype.kind == 'f':
                aout[:] = np.nan
            else:
                aout[:] = 0 # debatable...
            return aout
        if n == 1:
            aout[:] = arr[:]
            return aout

        if n & 1:
            k = n//2
            even = 0
        else:
            k = n//2 - 1
            even = 1

        _arr = arr
        for i in range(nout):
            if dtype == np.float64:
                tmp = kth_smallest_d(<double *>_arr.data + i*n, n, k)
                if even:
                    tmp += kth_smallest_d(<double*>_arr.data + i*n, n, k+1)
                    tmp *= 0.5
                aout[i] = tmp
            elif dtype == np.float32:
                tmp = kth_smallest_f(<float *>_arr.data + i*n, n, k)
                if even:
                    tmp += kth_smallest_f(<float*>_arr.data + i*n, n, k+1)
                    tmp *= 0.5
                aout[i] = tmp
            elif dtype == np.int64:
                aout[i] =  kth_smallest_l(<long *>_arr.data, n, k)
            else:
                aout[i] =  kth_smallest_i(<int *>_arr.data, n, k)

    return aout

