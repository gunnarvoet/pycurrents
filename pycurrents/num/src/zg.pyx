# -*- Mode: Python -*-  Not really, but close enough
'''
Wrapper for ancient contour support routines.
'''

cimport numpy
import numpy

import logging

log = logging.getLogger(__name__)

# Numpy must be initialized
numpy.import_array()

cdef extern from "msgmaker.h":
    void set_msg_stderr(int tf)
    void set_msg_bigbuf(int tf)
    #int get_msg(char *msg_ptr, int n)
    void reset_msg()
    char *get_msg_buf()

def read_msg():
    msg = get_msg_buf()
    msg = msg.decode('ascii')
    reset_msg()
    return msg

set_msg_stderr(0)
set_msg_bigbuf(1)


cdef extern from "zgrid.h":
   int zgrid_(int nx, int ny,
            double *z_out,
            double x1, double y1,
            double dx, double dy,
            int n,
            double *x_in, double *y_in, double *z_in,
            double dxdyratio, double cay, int nrng,
            int idbug)

def zgrid(_zm,
            _xin,
            _yin,
            _zin,
            origin=(0,0),
            deltas=(1,1),
            y_weight = 1,
            biharmonic=1,
            interp=2):
    '''
    zout = zgrid(zmask, xin, yin, zin,
            origin=(0,0),
            deltas=(1,1),
            y_weight = 1,
            biharmonic=1,
            interp=2):

    Regrid data to a uniform grid using a combination of Laplacian
    and biharmonic interpolation.

    zmask is a mask array of shape (ny,nx): data filling and
            interpolation will occur only where zmask is nonzero

    xin, yin, zin are sequences or arrays with the data to be regridded

    origin and deltas are sequences defining the new grid:
            x[i] = origin[0] + i * deltas[0]
            y[i] = origin[1] + i * deltas[1]

    y_weight governs the weight of the y dimension relative to the
            x dimension in the interpolation.  For example, if a
            single grid point needs to be interpolated, setting
            y_weight to a value greater than 1 will cause the
            interpolation to be primarily in y--that is, based on
            the points above and below the missing point.  With
            non-zero biharmonic interpolation, too large a deviation
            of y_weight from 1 can prevent the algorithm from
            converging.

    biharmonic is a coefficient multiplying the biharmonic term
            in the equation; 0 yields pure Laplacian interpolation,
            increasing positive values yield a greater biharmonic
            component.

    interp is the distance in number of grid points over which data
            will be interpolated or extrapolated.

    Notes:

    zgrid is a thin wrapper for a C translation of very old Fortran
    code written by Roger Lukas.  The translation was done initially
    with f2c but has been heavily modified.

    zgrid is intended to be used with at least one more layer of
    wrapping.  Typically one would do something like this:

        use blank.py to calculate a blanking polygon from x_in, y_in,
            and z_in;
        use mask_from_poly to generate zmask from this blanking
            polygon
        call zgrid
        convert zout into a masked array

    The returned array, zout, is a modification of the input array,
    zmask, so do not try to use the same zmask for multiple calls
    to zgrid; instead, make a copy each time.

    '''
    cdef numpy.ndarray zm, xin, yin, zin
    cdef double x0, y0, dx, dy
    cdef int nx, ny
    cdef numpy.npy_intp nn

    zm = numpy.PyArray_ContiguousFromAny(_zm, numpy.NPY_DOUBLE, 2, 2)
    xin = numpy.PyArray_ContiguousFromAny(_xin, numpy.NPY_DOUBLE, 1, 2)
    yin = numpy.PyArray_ContiguousFromAny(_yin, numpy.NPY_DOUBLE, 1, 2)
    zin = numpy.PyArray_ContiguousFromAny(_zin, numpy.NPY_DOUBLE, 1, 2)
    nn = numpy.PyArray_SIZE(xin)
    if not (nn == numpy.PyArray_SIZE(yin)
                and nn == numpy.PyArray_SIZE(zin)):
        raise ValueError("xin, yin, zin must have the same length")
    nx = zm.shape[1]
    ny = zm.shape[0]
    x0, y0 = origin
    dx, dy = deltas

    ret = zgrid_(nx, ny, <double *> zm.data, x0, y0, dx, dy,
                 nn,
                 <double *>xin.data, <double *>yin.data, <double *>zin.data,
                 y_weight, biharmonic, interp, 0) # last arg is idbug
    msgout = read_msg()
    if ret == 0 and msgout:
        log.info(msgout)
    if ret != 0:
        raise RuntimeError(msgout)
    return zm
