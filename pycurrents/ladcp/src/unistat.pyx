"""
LADCP shear method calculations.

Some of this (along with the corresponding ustatp.c pieces) may
be general enough to land in pycurrents.num
"""

import numpy as np
cimport numpy as np

cimport cython

np.import_array()  # needed only if a PyArray_* function is used,
                   # but it doesn't hurt

cdef extern from "ustatp.h":
    # We may want to move these into the Shearcalc class.
    int index_less(double d, double dstart, double dz)
    int index_more(double d, double dstart, double dz)
    int index_closest(double d, double dstart, double dz)

    void regrid(double *zo, double *fo, double *zn, double *fn,
                        int m, int n, int *n0_ptr, int *nout_ptr)

    ctypedef struct UNISTAT_TYPE:
        int n, n_increments
        double *sum
        double *sumsq
        double *min
        double *max
        int *npts
        int *imin
        int *imax

    void zero_unistat(UNISTAT_TYPE *u)

    void update_unistat_piece(UNISTAT_TYPE *s,
                            double *array,
                            unsigned char *mask,
                            int i0,  #/* starting index into unistat arrays */
                            int na)  #/* number of points in the array */

    void update_unistat_nomask(UNISTAT_TYPE *s,
                            double *array,
                            int i0,
                            int na)


cdef class Unistat:
    """
    Interface to the old CODAS profile statistics accumulator code.

    All array allocation is done here by making ndarrays.
    """
    cdef UNISTAT_TYPE ustat
    cdef readonly int ngrid
    cdef readonly np.ndarray sum
    cdef readonly np.ndarray sumsq
    cdef readonly np.ndarray min
    cdef readonly np.ndarray max
    cdef readonly np.ndarray imin
    cdef readonly np.ndarray imax
    cdef readonly np.ndarray npts

    def __init__(self, int n):
        # Using __init__, not __cinit__ because we need ndarray attributes
        self.ngrid = n

        self.ustat.n = n
        self.ustat.n_increments = 0

        cdef np.ndarray[np.double_t] sum
        sum = np.zeros((n,), dtype=np.float64)
        self.ustat.sum = <double *>sum.data
        self.sum = sum

        cdef np.ndarray[np.double_t, ndim=1] sumsq
        sumsq = np.zeros((n,), dtype=np.float64)
        self.ustat.sumsq = <double *>sumsq.data
        self.sumsq = sumsq

        cdef np.ndarray[np.double_t, ndim=1] min
        min = np.zeros((n,), dtype=np.float64)
        self.ustat.min = <double *>min.data
        self.min = min

        cdef np.ndarray[np.double_t, ndim=1] max
        max = np.zeros((n,), dtype=np.float64)
        self.ustat.max = <double *>max.data
        self.max = max

        cdef np.ndarray[np.npy_int, ndim=1] imin
        imin = np.zeros((n,), dtype=np.int32)
        self.ustat.imin = <int *>imin.data
        self.imin = imin

        cdef np.ndarray[np.npy_int, ndim=1] imax
        imax = np.zeros((n,), dtype=np.int32)
        self.ustat.imax = <int *>imax.data
        self.imax = imax

        # To use weights instead of number of points,
        # change the following to a double, and add
        # a field for sum of squared weights.
        cdef np.ndarray[np.npy_int, ndim=1] npts
        npts = np.zeros((n,), dtype=np.int32)
        self.ustat.npts = <int *>npts.data
        self.npts = npts

        self.clear()

    cdef clear(self):
        zero_unistat(&self.ustat)

    cdef _update(self, double *array,
                      unsigned char *mask,
                      int i0,
                      int na):
        update_unistat_piece(&self.ustat, array, mask, i0, na)

    def update(self, array, i0):
        array = np.ma.asarray(array, dtype=np.float64)
        cdef np.ndarray _array = array
        cdef np.ndarray _mask = np.ma.getmaskarray(array)
        if array.ndim != 1:
            raise ValueError("Only 1-D arrays are supported.")
        self._update(<double *>_array.data,
                     <unsigned char *>_mask.data,
                     i0, array.size)

    property n_updates:

        def __get__(self):
            return self.ustat.n_increments

    property mean:

        def __get__(self):
            mask = self.npts == 0
            x = np.ma.array(self.sum, mask=mask, copy=False)
            return x / self.npts

    property std:

        def __get__(self):
            mask = self.npts == 0
            x = np.ma.array(self.sumsq, mask=mask, copy=False)
            return np.ma.sqrt( x / self.npts - self.mean**2)

cdef class Shearcalc:
    """
    This is the shear calculation and averaging engine.

    Instantiation sets up the grid and allocates working memory.
    The calculation is then done in the __call__() method.

    New calculations can be done by calling clear() first.

    Calculation output is accessed via attributes.
    """
    cdef double *_ush
    cdef double *_vsh
    cdef double *_wsh
    cdef double *_dsh
    cdef double *_ugrid
    cdef double *_vgrid
    cdef double *_wgrid
    cdef double *_dgrid
    cdef int *_sh_i0
    cdef int *_sh_i1
    cdef readonly double dstart, dz
    cdef readonly int ndgrid
    cdef readonly int ncells
    cdef readonly int nsh
    cdef UNISTAT_TYPE *ustats_ptr
    cdef UNISTAT_TYPE *vstats_ptr
    cdef UNISTAT_TYPE *wstats_ptr

    cdef readonly Unistat ustat, vstat, wstat
    cdef readonly np.ndarray dgrid, ugrid, vgrid, wgrid
    cdef readonly np.ndarray ush, vsh, wsh, dsh
    cdef readonly np.ndarray sh_i0, sh_i1

    def __init__(self, double dstart, double dz, int ndgrid, int ncells):
        """
        ncells is max number of adcp depth cells, for setting size of
        shear working arrays.
        """
        self.dstart = dstart
        self.dz = dz
        self.ndgrid = ndgrid
        self.ncells = ncells

        cdef Unistat ustat
        ustat = Unistat(ndgrid)
        self.ustats_ptr = &(ustat.ustat)
        self.ustat = ustat

        cdef Unistat vstat
        vstat = Unistat(ndgrid)
        self.vstats_ptr = &(vstat.ustat)
        self.vstat = vstat

        cdef Unistat wstat
        wstat = Unistat(ndgrid)
        self.wstats_ptr = &(wstat.ustat)
        self.wstat = wstat

        cdef np.ndarray[np.double_t] dgrid
        dgrid = np.arange(ndgrid, dtype=np.float64) * dz + dstart
        self._dgrid = <double *>dgrid.data
        self.dgrid = dgrid

        cdef np.ndarray[np.double_t] ugrid
        ugrid = np.zeros((ndgrid,), dtype=np.float64)
        self._ugrid = <double *>ugrid.data
        self.ugrid = ugrid

        cdef np.ndarray[np.double_t] vgrid
        vgrid = np.zeros((ndgrid,), dtype=np.float64)
        self._vgrid = <double *>vgrid.data
        self.vgrid = vgrid

        cdef np.ndarray[np.double_t] wgrid
        wgrid = np.zeros((ndgrid,), dtype=np.float64)
        self._wgrid = <double *>wgrid.data
        self.wgrid = wgrid

        cdef np.ndarray[np.double_t] ush
        ush = np.zeros((ncells,), dtype=np.float64)
        self._ush = <double *>ush.data
        self.ush = ush

        cdef np.ndarray[np.double_t] vsh
        vsh = np.zeros((ncells,), dtype=np.float64)
        self._vsh = <double *>vsh.data
        self.vsh = vsh

        cdef np.ndarray[np.double_t] wsh
        wsh = np.zeros((ncells,), dtype=np.float64)
        self._wsh = <double *>wsh.data
        self.wsh = wsh

        cdef np.ndarray[np.double_t] dsh
        dsh = np.zeros((ncells,), dtype=np.float64)
        self._dsh = <double *>dsh.data
        self.dsh = dsh

        cdef np.ndarray[np.npy_int] sh_i0
        sh_i0 = np.zeros((ncells,), dtype=np.int32)
        self._sh_i0 = <int *>sh_i0.data
        self.sh_i0 = sh_i0

        cdef np.ndarray[np.npy_int] sh_i1
        sh_i1 = np.zeros((ncells,), dtype=np.int32)
        self._sh_i1 = <int *>sh_i1.data
        self.sh_i1 = sh_i1

    def clear(self):
        self.ustat.clear()
        self.vstat.clear()
        self.wstat.clear()


    def __call__(self, enue, flag, depth, int max_step=10):
        """
        *enue* is the (time, depth, component) masked array from a Profile.
        *flag* is the (time, depth) flag or mask from subsequent editing
        *depth* is the (time, depth) array of actual bin depths
        """
        cdef np.ndarray[np.npy_ubyte, ndim=2] mask
        cdef np.ndarray[np.float_t, ndim=2] u, v, w, d
        cdef int nt, nd
        cdef int i
        cdef int grid_n

        nt, nd = enue.shape[:2]
        # Use of "any" in the following should be overkill;
        # we expect u, v, and w to have the same mask.  We want
        # to ignore masked e, otherwise we disallow 3-beam solutions.
        mask_uvw = np.ma.getmaskarray(enue)[..., :3].any(axis=-1)

        # Include any additional editing in "flag".
        # Switch to uint8 for interface to cython and C.
        mask = np.logical_or(mask_uvw, flag).astype(np.uint8)

        # Note: simply using the enue.data attribute seems to confuse the
        # cython compiler; it thinks it is getting the "data" buffer from
        # a plain ndarray.
        # There may be no need for the cdef...
        cdef np.ndarray[np.float_t, ndim=3] dat = np.ma.getdata(enue)
        u = np.ascontiguousarray(dat[:,:,0])
        v = np.ascontiguousarray(dat[:,:,1])
        w = np.ascontiguousarray(dat[:,:,2])
        d = np.ascontiguousarray(depth)

        for i in range(nt):
            self.uv_to_shear(<double *>&u[i,0],
                             <double *>&v[i,0],
                             <double *>&w[i,0],
                             <double *>&d[i,0],
                             <unsigned char *>&mask[i,0],
                             nd, max_step)
            # the old shear editing could go here, given a
            # Shearcalc instance from a previous pass, or just
            # the saved ustat means and the previous grid
            grid_n = self.grid_shear()

    cdef uv_to_shear(self, double *u, double *v, double *w, double *d,
                            unsigned char *u_flag, int nbins, int max_step):
        """
        nbins must be less than ncells, and less than or equal to the
        size of each of the arrays passed in.
        """
        cdef int i, i0i, i1i, idn, nsh
        cdef double dd

        # Sweep through the flags to find adjacent pairs of good
        # values for calculating shear, skipping gaps.
        i0i = i1i = 0
        for i in range(nbins):
            if u_flag[i]:
                continue
            if i0i > 0:
                self._sh_i1[i1i] = i
                i1i += 1
            if i < nbins - 1:
                self._sh_i0[i0i] = i
                i0i += 1
        nsh = i1i

        idn = 0
        for i in range(nsh):
            # skip the uplooker support; later, put it in based on merge.c
            #idn = i
            if self._sh_i1[i] - self._sh_i0[i] > max_step:
                continue
            dd = d[self._sh_i1[i]] - d[self._sh_i0[i]]
            if dd == 0:
                continue
            self._ush[idn] = (u[self._sh_i1[i]] - u[self._sh_i0[i]]) / dd;
            self._vsh[idn] = (v[self._sh_i1[i]] - v[self._sh_i0[i]]) / dd;
            self._wsh[idn] = (w[self._sh_i1[i]] - w[self._sh_i0[i]]) / dd;
            self._dsh[idn] = 0.5 * (d[self._sh_i1[i]] + d[self._sh_i0[i]]);
            idn += 1

        self.nsh = idn

    cdef int grid_shear(self):
        """
        After calling uv_to_shear, this interpolates the piecewise-linear
        shear profile onto the appropriate segment of the new grid,
        and adds it to the unistat objects.
        """
        cdef int i1, grid_i0, grid_n
        cdef int nsh = self.nsh
        cdef int n0, n_out # for regrid output variables; not used,
                           # but may be needed for debugging

        # We can probably calculate these indices much more efficiently.
        grid_i0 = index_more( self.dsh[0], self.dstart, self.dz)
        i1      = index_less( self.dsh[self.nsh-1], self.dstart, self.dz)
        if i1 > self.ndgrid - 1:
            i1 = self.ndgrid - 1
        grid_n = 1 + i1 - grid_i0

        if grid_n > 0:
            regrid(self._dsh, self._ush, self._dgrid+grid_i0,
                                        self._ugrid, nsh, grid_n,
                                        &n0, &n_out)
            regrid(self._dsh, self._vsh, self._dgrid+grid_i0,
                                        self._vgrid, nsh, grid_n,
                                        &n0, &n_out)
            regrid(self._dsh, self._wsh, self._dgrid+grid_i0,
                                        self._wgrid, nsh, grid_n,
                                        &n0, &n_out)

        else:
            grid_n = 0

        # Always update, even if grid_n is 0, so that the indices
        # of max and min will be correct for the whole array.

        update_unistat_nomask(self.ustats_ptr, self._ugrid,
                                                grid_i0, grid_n)
        update_unistat_nomask(self.vstats_ptr, self._vgrid,
                                                grid_i0, grid_n)
        update_unistat_nomask(self.wstats_ptr, self._wgrid,
                                                grid_i0, grid_n)

        return grid_n

@cython.boundscheck(False)
def velocity_deviation(enue,
                       np.ndarray[np.uint8_t, ndim=2] flag,
                       np.ndarray[np.double_t, ndim=2] depth,
                       np.ndarray[np.double_t, ndim=2] uvwgrid,
                       np.ndarray[np.npy_int, ndim=1] npts,
                       double dstart, double dz, int ndgrid):
    """
    Calculate the deviation of each ping velocity from the gridded profile.

    The mean over the common depth range is subtracted from each
    profile before calculating the deviation.

    Instead of linear interpolation, nearest-neighbor interpolation
    is used to find the gridded estimate corresponding to each
    cell of each ping.

    Returns the 3-D array of deviations and the 1-D array with
    the number of valid depths.
    """

    cdef unsigned int i, j, k
    cdef unsigned int jj
    cdef unsigned int nt, ncells
    nt = enue.shape[0]
    ncells = enue.shape[1]

    cdef np.ndarray[np.double_t, ndim=3] devs
    devs = np.zeros((nt, ncells, 3), dtype=float)

    cdef np.ndarray[np.npy_int, ndim=1] ngood
    ngood = np.zeros(nt, dtype=np.int32)

    cdef np.ndarray[np.uint8_t, ndim=2] mask
    mask = (np.ma.getmaskarray(enue).sum(axis=-1).astype(np.uint8) | flag)

    # Note: simply using the enue.data attribute seems to confuse the
    # cython compiler; it thinks it is getting the "data" buffer from
    # a plain ndarray.
    cdef np.ndarray[np.double_t, ndim=3] dat = np.ma.getdata(enue)
    cdef double sumprof[3]
    cdef double sumgrid[3]
    cdef int n

    for i in range(nt):
        for k in range(3):
            sumprof[k] = 0
            sumgrid[k] = 0
        n = 0

        # First pass: calculate matching depth-averages.
        for j in range(ncells):
            if mask[i,j] != 0:
                continue
            jj = index_closest(depth[i,j], dstart, dz)
            if jj < 0 or jj >= ndgrid:
                continue
            for k in range(3):
                sumprof[k] += dat[i,j,k]
                sumgrid[k] += uvwgrid[jj,k]
            n += 1
        if n == 0:
            continue

        ngood[i] = n
        for k in range(3):
            sumprof[k] /= n
            sumgrid[k] /= n

        # Second pass: calculate the deviations of the
        # vertically-demeaned profiles.
        for j in range(ncells):
            if mask[i,j] != 0:
                continue
            jj = index_closest(depth[i,j], dstart, dz)
            if jj < 0 or jj >= ndgrid:
                continue
            for k in range(3):
                devs[i, j, k] = ((dat[i,j,k] - sumprof[k]) -
                                (uvwgrid[jj,k] - sumgrid[k]))
    return devs, ngood

