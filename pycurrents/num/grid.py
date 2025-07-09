'''
1-D and 2-D regridding routines

interp1: 1-D linear interpolation using the same codas
            routine that is in our table1 mex file, but
            with the Matlab (TM) interp1 style of interface.

zgrid: 2-D interpolation routine originally written in
            Fortran by Roger Lukas, using nearest-neighbor
            followed by Laplacian/spline interpolation.

regrid: wrapper for zgrid

blank: helper function; generate a blanking polygon from a mask.

'''
import logging
import warnings

import numpy as np

from pycurrents.num.utility import points_inside_poly
from pycurrents.num.zg import zgrid
from pycurrents.num.int1 import interp1
# Silence pyflakes:
(interp1, )

_log = logging.getLogger(__name__)


def blank(x, y, M, spread=0):
    '''
    Generate a blanking polygon from a mask.

    This is mainly a specialized helper for zgrid; see below.

    x and y are the abcissa (x) and ordinate (y) of the grid;
    they are 1-dimensional.
    M is the mask for that grid, nonzero (True) where blanked,
    zero (False) where data are valid.  For example if one is
    contouring a masked array, z, then one can use
        M = np.ma.getmaskarray(z)
    M.shape = len(y), len(x) or (ny, nx)
    The orientation of M matches the convention used in contour,
    pcolor, etc.

    Returns xp, yp, the coordinates of the blanking polygon.

    This function is somewhat specialized for use in contouring
    oceanographic profile datasets such as CTD or ADCP profiles,
    with depth as the ordinate and time or distance as the abcissa.
    In other words, depth increases with the row index.

    In comparison to the Matlab function from which this originated,
    the order of the first two arguments and the returned arguments
    have been swapped.

    The "spread" kwarg is new; the Matlab function was equivalent
    to a value of spread=1, but the default here is 0.  The value
    is the number of gridpoints to the left and right of a given
    column by which the value in that column will be propagated,
    if it exceeds the original value.
    '''
    abc = np.asarray(x, dtype=np.double).flatten()
    ord = np.asarray(y, dtype=np.double).flatten()
    nr, nc = M.shape
    if len(abc) != nc or len(ord) != nr:
        raise ValueError("M.shape must be (len(ord), len(abc))")
    ii = abc.argsort(kind='heapsort')
    abc = abc[ii]
    M = M[:,ii]

    # dord and dabc are used to push the polygon out a bit, to
    # avoid unwanted blanking due to roundoff.
    dord = np.min(np.abs(np.diff(ord)))*0.01
    # assuming ord is depth, positive downward.
    # abc is increasing; it has been sorted.
    dabc = np.min(np.abs(np.diff(abc)))*0.01

    ORD = np.repeat(ord[:,np.newaxis], nc, 1)

    ORD[M.astype(bool)] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        ordmax = np.nanmax(ORD, axis=0) + dord
        ordmin = np.nanmin(ORD, axis=0) - dord
    ii = np.isnan(ordmax)
    ordmax[ii] = np.nanmax(ordmin)
    ordmin[ii] = ordmax[ii] - dord
    for i in range(spread):
        ordmax[1:-1] = np.max(np.vstack((ordmax[:-2], ordmax[1:-1], ordmax[2:])))
        ordmin[1:-1] = np.min(np.vstack((ordmin[:-2], ordmin[1:-1], ordmin[2:])))

    abc[0] = abc[0] - dabc
    abc[-1] = abc[-1] + dabc

    ordb = np.hstack((ordmax, ordmin[::-1], ordmax[0]))
    abcb = np.hstack((abc, abc[::-1], abc[0]))

    return abcb, ordb


def regrid(xin, yin, zin, xout, yout, zmask=None ,
                  y_weight=1,  biharmonic=1, interp=2, useblank=True):
    """
    xin, yin are 1-D arrays of input coordinates
    zin.shape should be (len(yin), len(xin))
        If zin is a masked
        array, only the unmasked points will be used.
    xout, yout are coordinates to grid the output
          MUST BE monotonic and evenly spaced; only
          the number of points in each array and the
          first two values are used.
    optional arguments (see docstring for zgrid):
        name             what                   default
        zmask:       False = unflagged, True = flagged (like maskedarray)
                     applied in in addition to any mask found from zin
        y_weight     weight of ygrid vs xgrid    1
        biharmonic   0=Laplacian, >0 is biharmonic      1
        interp       interp distance in gridpts  2
        useblank        True or False; probably temporary, allow
                     one to turn off use of the blanking polygon
    """

    ## input

    if len(xout) <= 2 or len(yout) <= 2:
        zout = np.ma.array(np.zeros((len(yout), len(xout)), dtype=float),
                                                                mask=True)
        return zout

    # input arguments will be converted to double in cython, so no need here.
    X, Y = np.meshgrid(xin, yin)

    mask = np.ma.getmaskarray(zin)
    zin = np.ma.getdata(zin)  # masked values will be discarded below

    if zmask is not None:
        mask |= zmask

    keepmask = ~(mask.ravel())
    Xin = np.compress(keepmask, X.ravel())
    Yin = np.compress(keepmask, Y.ravel())
    zin = np.compress(keepmask, zin.ravel())

    # for zgrid
    dx = xout[1]-xout[0]
    dy = yout[1]-yout[0]

    bpolyx, bpolyy = blank(xin,yin, mask.astype(np.int64))
    # can't have Infs in polygon edges; when would we?
    # should we raise an exception?
    bpx = np.compress(~np.isinf(bpolyy), bpolyx)
    bpy = np.compress(~np.isinf(bpolyy), bpolyy)

    Xo, Yo = np.meshgrid(xout, yout)
    Xo = Xo.ravel()
    Yo = Yo.ravel()
    _outmask = points_inside_poly(
        np.hstack((Xo[:, np.newaxis], Yo[:, np.newaxis])),
        np.hstack((bpx[:, np.newaxis], bpy[:, np.newaxis]))
    )
    _outmask.shape = len(yout), len(xout)
    outmask = (_outmask != 1)
    if not useblank:
        outmask[:] = False

    try:
        zout = zgrid(outmask, Xin, Yin, zin,
            origin=(xout[0], yout[0]),
            deltas=(dx, dy),
            y_weight=y_weight,
            biharmonic=biharmonic,
            interp=interp)
    except RuntimeError as err:
        zout = np.ma.array(np.zeros(_outmask.shape, dtype=float), mask=True)
        _log.warning(f'{err}    Returning all values masked.')
        return zout

    zout_ma = np.ma.masked_greater(zout, 1e36)

    return zout_ma
