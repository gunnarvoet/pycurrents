# cython: language_level=3
'''
Wrapper for interpolation routine: linear and nearest-neighbor.

The underlying C code was originally developed for a mex file, in our
early Matlab days.  It has since been modified, and the nearest-neighbor
variant added.

This linear interpolation routine probably will be slower than np.interp
in most real cases; but it can be faster if the y table array has a
large number of columns, because np.interp operates only on a single
column.  Applying it to multiple columns requires something like::

    func = lambda y: np.interp(xnew, xold, y)
    ynew = np.apply_along_axis(func, 0, yold)

This wrapper could be improved by calling np.interp in the 1-D case, and
possibly even in the N-D case when the number of columns etc. is smaller than
some threshold.

Another alternative is scipy.interpolate.interp1d, which handles N-D yold
and has options for various styles of interpolation.  It also requires a
wrapper like this one to handle various missing value scenarios. It looks
complicated, and possibly slower than one might expect--though maybe no
worse than the code here.
'''

import numpy as np

from cpython cimport PyLong_AsVoidPtr

cdef extern from "interp1.h":
    ctypedef struct arr1:
        double *data
        int n
        int stride

    ctypedef struct arr2:
        double *data
        int nr, nc
        int rstride, cstride

    int regridli(arr1* zo, arr2* fo, arr1* zn, arr2* fn, double max_dz)
    int regridnear(arr1* zo, arr2* fo, arr1* zn, arr2* fn, double max_dz)

_error_msg = {1: "The first argument needs more than one valid element",
              2: "The first argument is not monotonic",
              3: "The first argument has duplicate values",
              4: "The first argument has a NaN",
              }

class NanError(ValueError):
    pass

class NonuniformError(ValueError):
    pass

def interp1(x_old, y_old, x_new, masked='auto', axis=0,
            method='linear',
            max_dx=0):
    '''
    linear interpolation between rows in a table

    Arguments:
        x_old   1-D array of original abcissas
        y_old   N-D array of original table rows;
                    if it is N-D, the 'axis' dimension
                    must match the length of x_old; see 'axis'
                    kwarg, below.
        x_new   1-D array of x values for which the interpolated
                    table rows from y_old will be found

    kwargs:
        masked  'auto' (default) | True | False
                If 'auto', a masked array will be returned if
                any input is masked, otherwise NaNs will indicate
                missing values; if True, a masked array will
                always be returned; if False, an ordinary array
                with NaNs if necessary will be returned.
                Values of 1e100 or larger in y_old will be treated
                the same as NaNs.
        axis    0 (default) | 1; if y_old is N-D, then axis=0 means
                the table rows are the rows in y_old; axis=1 means
                the table rows are taken as the columns in y_old; etc.
        method  'linear' (default) | 'nearest'
        max_dx  maximum interval over which interpolation is done;
                if 0 (default), no checking will be done.

    Returns:
        y_new, the table interpolated from y_old at locations x_new

    Raises:
        ValueError for misshapen inputs
        NonuniformError, a subclass of ValueError,
            if the first argument is not strictly
            increasing or strictly decreasing

    x_old can be masked or not, with or without nans.  If there are
    masked or nan values, they, and the corresponding rows in y_old,
    will be stripped out before interpolation. Apart from any invalid
    values, x_old must be strictly increasing or strictly decreasing.

    No extrapolation is done.  Any values that cannot be interpolated
    are marked as invalid, either with the mask or with a NaN.

    '''
    try:
        return interp1_core(x_old, y_old, x_new, masked=masked,
                                axis=axis, method=method, max_dx=max_dx)
    except NanError:
        # The point of this is that even if x_old is a masked array
        # it could have a nan in the unmasked part, but we expect
        # this to be rare.  Therefore, instead of always including
        # the overhead of checking, we let interp find the problem,
        # and then correct it here if found.
        x_old1 = np.ma.filled(x_old, np.nan)
        cond = ~np.isnan(x_old1)
        x_old2 = np.compress(cond, x_old1)
        y_old2 = np.compress(cond, np.ma.filled(y_old, np.nan), axis=axis)
        ret = interp1_core(x_old2, y_old2, x_new, masked=False,
                           axis=axis, method=method, max_dx=max_dx)
        ma_input = (np.ma.isMaskedArray(x_old)
                    or np.ma.isMaskedArray(x_new)
                    or np.ma.isMaskedArray(y_old))
        if masked == True or ma_input:
            ret = np.ma.masked_invalid(ret)
        return ret

def interp1_core(x_old, y_old, x_new, masked='auto', axis=0,
                 method='linear',
                 max_dx=0):

    cdef arr1 xo, xn
    cdef arr2 yo, yn

    if method not in ['linear', 'nearest']:
        raise ValueError("method must be 'linear' or 'nearest'")

    x_old = np.asanyarray(x_old, np.float64).ravel()
    x_new = np.asanyarray(x_new, np.float64)
    x_new.shape = (x_new.size,)   # ensure 1-D without copying
    y_old = np.asanyarray(y_old, np.float64)

    if y_old.ndim == 1:
        y_old = y_old[:, np.newaxis]
        oneD = True
    else:
        oneD = False
        if axis != 0:
            y_old = y_old.swapaxes(0, axis)
        y_old_swapped_shape = y_old.shape

    y_old_shape_2d = (y_old.shape[0], y_old.size // y_old.shape[0])

    if y_old.shape[0] != x_old.shape[0]:
        raise ValueError(
            "size of x, %d, does not match number of table rows, %d"
            % (x_old.shape[0], y_old.shape[0]))

    if masked == 'auto':
        masked = (np.ma.isMaskedArray(x_old)
                    or np.ma.isMaskedArray(x_new)
                    or np.ma.isMaskedArray(y_old))

    if np.ma.isMaskedArray(x_old):
        if np.ma.is_masked(x_old):
            oldmask = np.ma.getmaskarray(x_old)
            y_old = y_old[~oldmask]
            y_old_shape_2d = (y_old.shape[0], y_old_shape_2d[1])
        x_old = x_old.compressed()

    if np.ma.isMaskedArray(y_old):
        y_old = y_old.filled(1e100)

    newmask = None
    if np.ma.isMaskedArray(x_new):
        if np.ma.is_masked(x_new):
            newmask = np.ma.getmask(x_new)
        x_new = x_new.compressed()

    x_old = np.ascontiguousarray(x_old)
    y_old = np.ascontiguousarray(y_old).reshape(y_old_shape_2d)
    x_new = np.ascontiguousarray(x_new)

    nr_old, nc_old = y_old_shape_2d
    nr_new = x_new.shape[0]
    y_new = np.empty(shape=(nr_new, nc_old), dtype=np.float64)

    xo.data = <double *> PyLong_AsVoidPtr(x_old.__array_interface__['data'][0])
    xo.n = nr_old
    xo.stride = x_old.strides[0] // 8

    xn.data = <double *> PyLong_AsVoidPtr(x_new.__array_interface__['data'][0])
    xn.n = nr_new
    xn.stride = x_new.strides[0] // 8

    yo.data = <double *> PyLong_AsVoidPtr(y_old.__array_interface__['data'][0])
    yo.nr = nr_old
    yo.nc = nc_old
    yo.rstride = y_old.strides[0] // 8
    yo.cstride = y_old.strides[1] // 8

    yn.data = <double *> PyLong_AsVoidPtr(y_new.__array_interface__['data'][0])
    yn.nr = nr_new
    yn.nc = nc_old  # new and old have same number of columns
    yn.rstride = y_new.strides[0] // 8
    yn.cstride = y_new.strides[1] // 8

    if method == 'linear':
        ret = regridli(&xo, &yo, &xn, &yn, max_dx)
    else:
        ret = regridnear(&xo, &yo, &xn, &yn, max_dx)

    if ret == 4:
        raise NanError("Nan in first argument")
    if ret in (2, 3):
        raise NonuniformError("Invalid input: %s" % _error_msg[ret])

    if ret == 1:
        y_new.fill(1e100)

    mask = np.ma.make_mask(np.greater(y_new, 0.999e100),
                           copy=False, shrink=True)
    if masked:
        y_new = np.ma.array(y_new, mask=mask, copy=0)
    elif mask is not np.ma.nomask:
        np.putmask(y_new, mask, np.nan)

    if newmask is not None:
        if masked:
            f = np.ma.masked_all((newmask.size, nc_old), dtype=np.double)
        else:
            f = np.empty((newmask.size, nc_old), dtype=np.double)
            f.fill(np.nan)
        f[~newmask] = y_new
        y_new = f
        nr_new = newmask.size

    if oneD:
        y_new.shape = (nr_new,)
    else:
        y_new_swapped_shape = [nr_new] + list(y_old_swapped_shape[1:])
        y_new = y_new.reshape(y_new_swapped_shape)
        if axis != 0:
            y_new = y_new.swapaxes(0, axis)
    return y_new
