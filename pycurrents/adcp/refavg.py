'''
Replacement for refavg.m

It can be sped up more if necessary.
'''

import numpy as np
import numpy.ma as ma

def refavg(u, dslice=None, n_iterations=4, diagnostic=False):
    '''
    Decompose a set of profiles into a single profile times a fn of time.

    arguments:
        u               masked array, shape = ntimes, ndepths
        dslice          slice object for selecting reference layer
                            default (None) uses all depth bins
        n_iterations    default 4

    returns masked arrays:
        tser            time series, shape = ntimes,
        dprof           depth profile, shape = ndepths,
        resid           residuals, shape = ntimes, ndepths

    Note: tser and dprof are normalized such that the tser mean is zero.

    '''
    nt, nd = u.shape
    if dslice is None:
        dslice = slice(nd)
    uu = ma.array(u, copy=True)
    dprof = ma.zeros((nd,), dtype=float)
    tser = ma.zeros((nt,), dtype=float)

    for it in range(n_iterations):
        delts= uu[:, dslice].mean(axis=1)
        uu -= delts[:, np.newaxis]
        tser += delts
        deld = uu.mean(axis=0)
        uu -= deld
        dprof += deld
        if diagnostic:
            resid = u - dprof - tser[:, np.newaxis]
            print("rms: %f    mean: %f" % (ma.sqrt((resid**2).sum()),
                                                 resid.mean()))
    tsmean = tser.mean()
    tser -= tsmean
    dprof += tsmean
    resid = u - dprof - tser[:, np.newaxis]
    return tser, dprof, resid


def ufake(shape, ampt, ampd, amptr, ampdr, noise=0):
    '''
    ufake(shape, ampt, ampd, amptr, ampdr, noise=0)

    Generate a set of u profiles that match
    the form assumed by refavg: that is, a single function
    of z (f; down a column) times a single function of time
    (g; increasing with column number)

       shape  2-d array with size of u matrix
       ampt  magnitude of the non-random part of the time dependence;
                 it is a step function, ampt in the middle third,
                 zero elsewhere.
       ampd  magnitude of the non-random part of the depth function, a
                 half-cosine
       amptr random noise amplitude in the time function
       ampdr                               depth function
       noise    Additional random noise; if nonzero,
                then the profiles do not exactly match the
                refavg ideal form.

    To simulate the case where the depth range is reduced when
    the ship is underway (middle third), the bottom half of the
    profile is masked during the middle third.

    '''
    nt, nd = shape
    u = np.zeros(shape, dtype=float)

    tt = np.zeros((nt,), dtype=float)
    ii = slice(int(round(nt/3.0)), int(round(2*nt/3.0)))
    tt[ii] = ampt
    tt = tt + np.random.randn(nt) * amptr

    d = np.arange(nd).astype(float)/nd
    dd = ampd * np.cos(d*np.pi) + ampdr * np.random.randn(nd)

    u = dd[np.newaxis,:] + tt[:,np.newaxis]
    if noise:
        u += noise * np.random.randn(nt, nd)

    jj = slice(int(round(nd/2)),nd)
    mask = np.zeros(shape, dtype=bool)
    mask[ii,jj] = True
    u = ma.array(u, mask=mask)
    return u, tt, dd

def test(nt=100, nd=60, n_iterations=4):
    """
    Simple illustration, and test of required number of
    iterations.  4 works well.
    This could be augmented to allow additional parameter
    inputs for more extensive testing.
    """
    import matplotlib.pyplot as plt

    u, tt, dd = ufake((nt, nd), 4, 0.5, 0.1, 0.1, 0.05)
    # Normalize tt, dd so that mean of tt is zero.
    ttm = tt.mean()
    tt -= ttm
    dd += ttm
    tser, dprof, resid = refavg(u, n_iterations=n_iterations, diagnostic=True)
    fig = plt.figure(figsize=(8,10))

    ax = fig.add_subplot(3,2,1)
    im = ax.pcolorfast(u.T)
    ax.invert_yaxis()
    ax.set_title('raw velocity')
    fig.colorbar(im, ax=ax)

    ax = fig.add_subplot(3,2,2)
    ax.plot(dprof, np.arange(nd), label='calc')
    ax.plot(dd, np.arange(nd), 'r-', label='orig')
    ax.legend(loc='best')
    ax.invert_yaxis()
    ax.set_title('depth variation')

    ax = fig.add_subplot(3,2,3)
    ax.plot(tser, label='calc')
    ax.plot(tt, 'r-', label='orig')
    ax.legend(loc='best')
    ax.set_title('time series')

    ax = fig.add_subplot(3,2,4)
    im = ax.pcolorfast(resid.T)
    ax.invert_yaxis()
    ax.set_title('residual')
    fig.colorbar(im, ax=ax)

    ax = fig.add_subplot(3,2,5)
    ax.plot(dprof-dd, np.arange(nd))
    ax.invert_yaxis()
    ax.set_title('dprof error')

    ax = fig.add_subplot(3,2,6)
    ax.plot(tser-tt)
    ax.set_title('tser error')

    plt.show()
    print("mean resid is", resid.mean())

