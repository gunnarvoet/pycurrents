"""
Specialized module for speeding up ADCP bottom bounce detection.

Given a model bump shape, taken here as a Blackman window, w, and
a corresponding set of amplitudes, d, as a function of depth cell,
the bump coefficient is <w'd'> / <w'w'>, where the prime indicates
deviation from the mean over the interval, and the <> is the
averaging operator over the interval.

The bump width is scaled to increase with range from the instrument.

"""


import numpy as np
cimport numpy as np
cimport cython

# Pre-calculate a list of Blackman filter weights used as the
# target bump shape.  The
# i'th element of the list is the set of weights for
# half-width i+1.  The zero points at the end are included.

weights = list()
for nhw in np.arange(1, 50):
    x = (np.linspace(-1, 1, nhw*2+1, endpoint=True)*np.pi)
    w = 0.42 + 0.5*np.cos(x) + 0.08 * np.cos(2*x)
    weights.append(w)
nweights = len(weights)

@cython.boundscheck(False)
def bump_coeff(amp,
               np.ndarray[np.float64_t, ndim=1] d,
               beam_angle):
    """
    Detect amplitude peaks characteristic of a bottom reflection.

    Signature::

        bc = bump_coeff(amp, d, beam_angle)

    Arguments:

        *amp*:
            2-D or 3-D ndarray or masked array of amplitudes;
            (nprofs, ndepths) or (nprofs, ndepths, nbeams)
            where nbeams = 4.
        *d*:
            1-D float64 ndarray of depths in cell units, not meters;
        *beam_angle*:
            beam angle in degrees

    Returns:

        *bc*:
            float64 ndarray with dimensions of *amp*; positive
            values for amplitude peaks, negative for dips.

    """
    cdef int nprofs, nbins
    cdef unsigned int i, j, jj, k, h
    cdef unsigned int j0, jj0
    cdef unsigned int jjmax
    cdef unsigned int jw
    cdef np.ndarray[np.float64_t, ndim=1] weight
    cdef int ng
    cdef double dval, wval
    cdef double dsum, wsum, dwsum, wwsum
    cdef unsigned int h_prev = 0

    cdef np.ndarray[np.float64_t, ndim=2] amp2
    cdef np.ndarray[np.uint8_t, ndim=2] amp_mask2
    cdef np.ndarray[np.float64_t, ndim=2] b2

    cdef np.ndarray[np.float64_t, ndim=3] amp3
    cdef np.ndarray[np.uint8_t, ndim=3] amp_mask3
    cdef np.ndarray[np.float64_t, ndim=3] b3

    if amp.ndim == 2:
        amp2 = np.ma.getdata(amp)
        amp_mask2 = np.ma.getmaskarray(amp).astype(np.uint8)
        with_beams = False
    else:
        amp3 = np.ma.getdata(amp)
        amp_mask3 = np.ma.getmaskarray(amp).astype(np.uint8)
        with_beams = True

    nprofs, nbins = amp.shape[:2]

    #  integer half-width of model bump as a function of depth:
    hw = np.round((1 - np.cos(beam_angle * np.pi/180.0)) * d + 1)
    hw = np.maximum(1, hw.astype(int))

    j0 = hw[0]
    if with_beams:
        b3 = np.zeros((nprofs, nbins, 4), dtype=np.float64)
        for j in range(j0, nbins):     # central depth index
            h = hw[j]                     # half-width
            jjmax = j+h+1                 # one past deepest depth index
            if jjmax > nbins:
                jjmax = nbins
            if h_prev != h:
                weight = weights[min(h-1, nweights-1)]
            for i in range(nprofs):
                for k in range(4):
                    ng = 0
                    wsum = 0
                    dsum = 0
                    wwsum = 0
                    dwsum = 0
                    jw = 0

                    jj0 = j-h
                    for jj in range(jj0, jjmax):   # loop over weights
                        if ~amp_mask3[i, jj, k]:
                            wval = weight[jw]
                            wsum += wval
                            wwsum += wval*wval
                            dval = amp3[i, jj, k]
                            dsum += dval
                            dwsum += dval * wval
                            ng += 1
                        jw += 1
                    if ng > 1:
                        b3[i,j,k] = ((dwsum - dsum * wsum /ng)
                                        / (wwsum - wsum*wsum/ng))
        return  b3

    else:
        b2 = np.zeros((nprofs, nbins), dtype=np.float64)

        for j in range(j0, nbins):
            h = hw[j]
            jjmax = j+h+1
            if jjmax > nbins:
                jjmax = nbins
            if h_prev != h:
                weight = weights[h-1]
            for i in range(nprofs):
                ng = 0
                wsum = 0
                dsum = 0
                wwsum = 0
                dwsum = 0
                jw = 0

                jj0 = j-h
                for jj in range(jj0, jjmax):
                    if ~amp_mask2[i, jj]:
                        wval = weight[jw]
                        wsum += wval
                        wwsum += wval*wval
                        dval = amp2[i, jj]
                        dsum += dval
                        dwsum += dval * wval
                        ng += 1
                    jw += 1
                if ng > 1:
                    b2[i, j] = ((dwsum - dsum * wsum /ng)
                                    / (wwsum - wsum*wsum/ng))

        return  b2



