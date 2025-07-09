import numpy as np
cimport numpy as np
cimport cython

# This 2-D version might not be needed at all.  If it is
# to be used, it needs to be updated to match the 1-D version
# in the handling of nsq.
@cython.boundscheck(False)
cpdef _rk4(np.ndarray[np.double_t, ndim=1] z,
           np.ndarray[np.double_t, ndim=1] bvfsq,
           np.ndarray[np.double_t, ndim=1] c,
           wp0=(0, 1)):
    cdef int nd = z.shape[0]
    cdef int nc = c.shape[0]
    cdef np.ndarray[np.double_t, ndim=2] w = np.empty((nc, nd),
                                                      dtype=np.float64)
    cdef np.ndarray[np.double_t, ndim=2] p = np.empty((nc, nd),
                                                      dtype=np.float64)
    cdef np.ndarray[np.double_t, ndim=1] ccinv_array = np.empty((nc,),
                                                       dtype=np.float64)

    cdef unsigned int i, j, jm
    cdef double h, h2, h6
    cdef double nsq
    cdef double wm, pm
    cdef double k1w, k1p, k2w, k2p, k3w, k3p, k4w, k4p

    w[:, 0], p[:, 0] = wp0

    for i in range(nc):
        ccinv_array[i] = c ** -2

    for j in range(1, nd):
        jm = <unsigned int> (j - 1)
        h = z[j] - z[jm]
        h2 = h / 2.0
        h6 = h / 6.0
        nsq = bvfsq[j]   # hold constant; we could interpolate

        for i in range(nc):
            ccinv = ccinv_array[i]
            wm = w[i, jm]
            pm = p[i, jm]

            k1w = pm * ccinv
            k1p = -wm * nsq

            k2w = (pm + h2 * k1p) * ccinv
            k2p = - nsq * (wm + h2 * k1w)

            k3w = (pm + h2 * k2p) * ccinv
            k3p = - nsq * (wm + h2 * k2w)

            k4w = (pm + h * k3p) * ccinv
            k4p = - nsq * (wm + h * k3w)

            w[i, j] = wm + h6 * (k1w + 2 * k2w + 2 * k3w + k4w)
            p[i, j] = pm + h6 * (k1p + 2 * k2p + 2 * k3p + k4p)

    return w, p


@cython.boundscheck(False)
cpdef _rk4_single(np.ndarray[np.double_t, ndim=1] z,
                  np.ndarray[np.double_t, ndim=1] bvfsq,
                  double c,
                  double w0=0,
                  double p0=1):

    cdef int nd = z.shape[0]
    cdef np.ndarray[np.double_t, ndim=1] w = np.empty((nd,), dtype=np.float64)
    cdef np.ndarray[np.double_t, ndim=1] p = np.empty((nd,), dtype=np.float64)

    cdef unsigned int j, jm
    cdef double h, h2, h6
    cdef double ccinv
    cdef double wm, pm
    cdef double k1w, k1p, k2w, k2p, k3w, k3p, k4w, k4p
    cdef double nsqjm, nsqmid, nsqj

    w[0] = w0
    p[0] = p0
    ccinv = c ** -2

    for j in range(1, nd):
        jm = <unsigned int> (j - 1)
        h = z[j] - z[jm]
        h2 = h / 2.0
        h6 = h / 6.0
        nsqjm = bvfsq[jm]
        nsqj = bvfsq[j]
        nsqmid =  (nsqj + nsqjm) / 2.0

        wm = w[jm]
        pm = p[jm]

        k1w = pm * ccinv
        k1p = - nsqjm * wm

        k2w = (pm + h2 * k1p) * ccinv
        k2p = - nsqmid * (wm + h2 * k1w)

        k3w = (pm + h2 * k2p) * ccinv
        k3p = - nsqmid * (wm + h2 * k2w)

        k4w = (pm + h * k3p) * ccinv
        k4p = - nsqj * (wm + h * k3w)

        w[j] = wm + h6 * (k1w + 2 * k2w + 2 * k3w + k4w)
        p[j] = pm + h6 * (k1p + 2 * k2p + 2 * k3p + k4p)

    return w, p


