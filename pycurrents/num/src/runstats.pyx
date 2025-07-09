'''
This is kept as a module separate from pyringbuf so that the
latter does not depend on numpy.
'''

cimport numpy
import numpy
from numpy import ma

numpy.import_array()

include "c_ringbuf.pxi"


def _runstats0(data, nrb):
    '''
    Simpler precursor; keep in case we want the simple
    version for some reason.
    '''

    cdef numpy.ndarray c_data
    cdef numpy.ndarray c_dmean
    cdef numpy.ndarray c_dstd
    cdef numpy.ndarray c_dmin
    cdef numpy.ndarray c_dmax
    cdef numpy.ndarray c_dmedian
    cdef numpy.ndarray c_ng

    if not nrb%2:
        raise ValueError("window size must be odd")
    data = ma.array(data, dtype=numpy.float64).filled(numpy.nan)
    if data.ndim != 1:
        raise ValueError("data must be 1-D for now")
    nd = data.shape[0]

    dmean = numpy.empty_like(data)
    dstd = numpy.empty_like(data)
    dmin = numpy.empty_like(data)
    dmax = numpy.empty_like(data)
    dmedian = numpy.empty_like(data)
    ng = numpy.empty(data.shape, dtype=numpy.int_)

    c_data = data
    c_dmean = dmean
    c_dstd = dstd
    c_dmin = dmin
    c_dmax = dmax
    c_dmedian = dmedian
    c_ng = ng

    c_runstats(nrb, nd, <double *>c_data.data,
                        <double *>c_dmean.data,
                        <double *>c_dstd.data,
                        <double *>c_dmin.data,
                        <double *>c_dmax.data,
                        <double *>c_dmedian.data,
                        <int *>c_ng.data)
    return dmean, dstd, dmin, dmax, dmedian, ng

class Runstats(object):
    '''
    Calculate running statistics of an array.

    See __init__ docstring for arguments and attributes.

    Useful methods:
        medfilt: returns median-filtered data

    '''
    def __init__(self, data, nwin, axis=-1, masked='auto', min_ng=1):
        '''
        args:
            data: a sequence or ndarray or masked array of up to 3 dimensions.
                    NaN may be used to indicate bad values; Nan is used
                    internally for this.
            nwin: odd integer; length of the window for statistics

        kwargs:
            axis: integer; axis over which the stats are calculated.
                    Default (-1) is the last axis, but it is best
                    to always be explicit if the array is not 1-D.

            masked='auto' : True|False|'auto' determines the output;
                    if True, output will be a masked array;
                    if False, output will be an ndarray with nan used
                                as a bad flag if necessary;
                    if 'auto', output will match input
                    (The ng output is an ndarray in any case.)

            min_ng=1 : if the output is masked, the mask will be
                    where ng < min_ng


        sets attributes:
            data: input as C-order double-precision array,
                            masked if requested
            double precision arrays with the same shape as data:
                mean
                std
                min
                max
                median
            integer array, same shape:
                ngood: the number of valid points within the window

        '''
        cdef numpy.ndarray c_data
        cdef numpy.ndarray c_dmean
        cdef numpy.ndarray c_dstd
        cdef numpy.ndarray c_dmin
        cdef numpy.ndarray c_dmax
        cdef numpy.ndarray c_dmedian
        cdef numpy.ndarray c_ng
        cdef int stride
        cdef int nd
        cdef int c_nwin
        cdef int i, j, k
        cdef int ni, nj, nk
        cdef int ofs

        c_nwin = nwin

        if not nwin%2:
            raise ValueError("window size must be odd")
        if hasattr(data, 'mask'):
            data = data.astype(numpy.float64).filled(numpy.nan)
            data = numpy.ascontiguousarray(data)
            masked_in = True
        else:
            data = numpy.asarray(data, order='C', dtype=numpy.float64)
            masked_in = False
        if data.ndim > 3:
            raise ValueError("Too many dimensions: 3-D max")

        if axis < 0:
            axis = data.ndim + axis
        if axis not in range(data.ndim):
            raise ValueError("Invalid axis for this input array")
        nd = data.shape[axis]

        if masked == True or (masked == 'auto' and masked_in):
            _nanout = False
        else:
            _nanout = True


        dmean = numpy.empty_like(data)
        dstd = numpy.empty_like(data)
        dmin = numpy.empty_like(data)
        dmax = numpy.empty_like(data)
        dmedian = numpy.empty_like(data)
        ng = numpy.empty(data.shape, dtype=numpy.int32)

        c_data = data
        c_dmean = dmean
        c_dstd = dstd
        c_dmin = dmin
        c_dmax = dmax
        c_dmedian = dmedian
        c_ng = ng

        stride = c_data.strides[axis]
        if data.ndim == 1:
            c_runstats(c_nwin, nd, <double *>c_data.data,
                                <double *>c_dmean.data,
                                <double *>c_dstd.data,
                                <double *>c_dmin.data,
                                <double *>c_dmax.data,
                                <double *>c_dmedian.data,
                                <int *>c_ng.data)
        elif data.ndim == 2:
            ni, nj = data.shape
            if axis == 0:
                for j from 0 <= j < nj:
                    ofs = j
                    c_runstats2(c_nwin, nd, stride//8, ofs,
                                        <double *>c_data.data,
                                        <double *>c_dmean.data,
                                        <double *>c_dstd.data,
                                        <double *>c_dmin.data,
                                        <double *>c_dmax.data,
                                        <double *>c_dmedian.data,
                                        <int *>c_ng.data)
            else:
                for i from 0 <= i < ni:
                    ofs = i*nj
                    c_runstats2(c_nwin, nd, stride//8, ofs,
                                        <double *>c_data.data,
                                        <double *>c_dmean.data,
                                        <double *>c_dstd.data,
                                        <double *>c_dmin.data,
                                        <double *>c_dmax.data,
                                        <double *>c_dmedian.data,
                                        <int *>c_ng.data)
        else:  #data.ndim ==3
            ni, nj, nk = data.shape
            if axis == 0:
                for j from 0 <= j < nj:
                    for k from 0 <= k < nk:
                        ofs = j*nk + k
                        c_runstats2(c_nwin, nd, stride//8, ofs,
                                            <double *>c_data.data,
                                            <double *>c_dmean.data,
                                            <double *>c_dstd.data,
                                            <double *>c_dmin.data,
                                            <double *>c_dmax.data,
                                            <double *>c_dmedian.data,
                                            <int *>c_ng.data)
            elif axis == 1:
                for i from 0 <= i < ni:
                    for k from 0 <= k < nk:
                        ofs = i*nj*nk + k
                        c_runstats2(c_nwin, nd, stride//8, ofs,
                                            <double *>c_data.data,
                                            <double *>c_dmean.data,
                                            <double *>c_dstd.data,
                                            <double *>c_dmin.data,
                                            <double *>c_dmax.data,
                                            <double *>c_dmedian.data,
                                            <int *>c_ng.data)
            else:
                for i from 0 <= i < ni:
                    for j from 0 <= j < nj:
                        ofs = i*nj*nk + j*nk
                        c_runstats2(c_nwin, nd, stride//8, ofs,
                                            <double *>c_data.data,
                                            <double *>c_dmean.data,
                                            <double *>c_dstd.data,
                                            <double *>c_dmin.data,
                                            <double *>c_dmax.data,
                                            <double *>c_dmedian.data,
                                            <int *>c_ng.data)

        if not _nanout:
            _mask = ng.__lt__(min_ng)
            dmean = ma.array(dmean, mask=_mask)
            dstd = ma.array(dstd, mask=_mask)
            dmin = ma.array(dmin, mask=_mask)
            dmax = ma.array(dmax, mask=_mask)
            dmedian = ma.array(dmedian, mask=_mask)
            odata = ma.masked_invalid(data)
        else:
            odata = data

        self._nanout = _nanout
        self.data = odata
        self.mean = dmean
        self.std = dstd
        self.min = dmin
        self.max = dmax
        self.median = dmedian
        self.ngood = ng

    def medfilt(self, tol):
        '''
        Apply median filter to data

        rs.medfilt(tol)

        argument: tol (float)

        Returns an array in which points deviating from the median
        by tol are replaced with the median.  Missing values are
        treated as exceeding the tolerance.
        '''
        dev = ma.masked_invalid((self.data - self.median).__abs__())
        # 2016/04/17 Numpy 1.10: with our without masked array,
        # a RuntimeWarning is generated if an invalid value is used
        # in a comparison.  Here we ensure invalid points are "bad"
        # so that they are not re-inserted into the array of medians.
        goodmask = (dev.filled(tol) < tol)
        dmfilt = self.median.copy()
        dmfilt[goodmask] = self.data[goodmask]
        return dmfilt



