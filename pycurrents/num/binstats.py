"""
Module provides a translation of our corresponding Matlab function.

This needs work, possibly a Cython re-write.

"""
import numpy as N
from numpy import ma as MA


def binstats(x,y, segends=None, avgtype='mean'):
    """
    Calculate statistics of *y* in bins based on *x*.

    *x*, *y* are 1-D sequences, possibly masked

    Keyword arguments:

        *segends*
            sequence of points used to divide *x* into segments
        *avgtype*
            'mean' (default) | 'median' | 'min' | 'max'


    Returns 4 1-D arrays of length len(*segends*)-1:

        *binpt*
            ndarray, midpoint of *x* bin
        *binmean*
            masked array, mean or other statistic
        *binstd*
            masked array, standard deviation
        *binn*
            ndarray, number of points

   """


   # rewrite in Cython to use user-specified time ranges


    # order of choice:
    #segends, stepi, astep, numsegs

    y = MA.asarray(y)

    if avgtype not in ('mean', 'median', 'min', 'max'):
        raise ValueError("avgtype must be mean, median, min, or max")

    if segends is not None:
        if len(segends) < 2:
            raise ValueError("segends must be abcissa points")
        binends = segends

    func = {'mean': N.mean, 'median': N.median,
            'min': N.amin, 'max': N.max}[avgtype]

    nbounds = len(binends)
    nsegs = nbounds - 1


    binpt   = N.zeros((nsegs,), dtype=N.float64)       # middle of bin
    binmean = N.zeros((nsegs,), dtype=N.float64)        # average of y in bin
    binstd  = N.zeros((nsegs,), dtype=N.float64)        # std of y in bin
    binn    = N.zeros((nsegs,), dtype=N.int32)        # num good pts in bin

    for iseg in range(nsegs):
        try:
            indbool = (x >= binends[iseg]) & (x < binends[iseg + 1])
            binpt[iseg] = x[indbool].mean()
            yseg = y[indbool].compressed()
            binn[iseg] = nys = len(yseg)
            if nys > 0:
                binmean[iseg] = func(yseg)
                binstd[iseg] = N.std(yseg)
        except:
            pass

    binmean = MA.array(binmean, mask=(binn == 0))
    binstd = MA.array(binstd, mask=(binn < 2))

    return binpt, binmean, binstd, binn
