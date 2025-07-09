"""
Blackman filtering.
"""
import numpy as np
import numpy.ma as ma
# scipy is imported by Blackman_filter if a long window is used.


def bl_filt(y, half_width, axis=1, min_fraction=0):
    '''
    Apply Blackman filter.

    args:
        y:             array or masked array to be filtered; 1-D or 2-D
        half_width:    integer specification of filter length;
                           there are 2*half_width-1 non-zero filter
                           window values
        axis:          1 (default) or 0; axis to filter if y is 2-D
                           1 filters the rows; 0 the columns
        min_fraction:  float in range 0-1; mask output where
                           filter fraction is less than or equal to
                           min_fraction
    returns:
        yf:            masked array, filtered version of y
        ww:            fraction of integrated window with data in y


    Note: unless min_fraction is 1, yf may include interpolated values.

    (The Matlab blackman.m returns the two zero end-weights; that is,
    blackman(7) returns 7 values, of which the first and last are zero.
    Our bl_filt.m)

    A masked array is always returned, even if y is not masked.

    This function is obsolete; use Blackman_filter instead.

    '''
    y = ma.masked_invalid(y)
    #--- generate weights array for given width ---

    nf = half_width * 2 + 1

    x = np.linspace(-1, 1, nf, endpoint=True)*np.pi
    x = x[1:-1]
    w = 0.42 + 0.5 * np.cos(x) + 0.08 * np.cos(2*x)

    badmask = ma.getmaskarray(y)
    goodmask = (~badmask).astype(float)
    ynm = y.filled(0)

    if y.ndim == 1:
        ytop = np.convolve(ynm, w, mode='same')
        ybot = np.convolve(goodmask, w, mode='same')
    elif y.ndim == 2 and axis in [0,1]:
        nr, nc = y.shape
        ytop = np.zeros_like(ynm)
        ybot = np.zeros((nr,nc), dtype=float)
        if axis == 1:
            for ii in range(nr):
                ytop[ii] = np.convolve(ynm[ii], w, mode='same')
                ybot[ii] = np.convolve(goodmask[ii], w, mode='same')
        else:
            for jj in range(nc):
                ytop[:,jj] = np.convolve(ynm[:,jj], w, mode='same')
                ybot[:,jj] = np.convolve(goodmask[:,jj], w, mode='same')
    else:
        raise ValueError("Only 1 or 2-dimensional arrays are supported.")

    ww = ybot / sum(w)
    yf = ma.masked_where(ww < min_fraction, ytop)
    yf /= ybot


    return yf, ww


def Blackman_weights(half_width, exclude='ends'):
    """
    *exclude* = 'ends' (default) to return only nonzero values;
                'left' to chop off the left-hand zero value;
                'right' to chop off the right-hand zero value;
                'none' to include left and right zero values.
    """

    nf = half_width * 2 + 1

    x = np.linspace(-1, 1, nf, endpoint=True) * np.pi
    if exclude == 'ends':
        x = x[1:-1]
    elif exclude == 'left':
        x = x[1:]
    elif exclude == 'right':
        x = x[:-1]
    elif exclude != 'none':
        raise ValueError(
            "'exclude' kwarg must be 'ends', 'left', 'right', or 'none'")

    w = 0.42 + 0.5 * np.cos(x) + 0.08 * np.cos(2*x)
    return w

def Blackman_filter(y, half_width, axis=-1, min_fraction=0, masked=None):
    """
    Apply Blackman filter.

    args:
        y:             array or masked array to be filtered; 1-D or 2-D
        half_width:    integer specification of filter length;
                           there are 2*half_width-1 non-zero filter
                           window values
        axis:          -1 (default) axis to filter
        min_fraction:  float in range 0-1; mask (or nan) output where
                           filter fraction is less than or equal to
                           min_fraction

        masked:         None (default) to return masked array
                        only if y is masked; True or False to
                        force return of masked or ndarray.
    returns:
        yf:            ndarray or masked array, filtered version of y
        ww:            fraction of integrated window with data in y


    Note: unless min_fraction is 1, yf may include interpolated values.
    """

    y_is_ma = ma.isMA(y)

    ym = ma.masked_invalid(y)

    badmask = ma.getmaskarray(ym)
    goodmask = (~badmask).astype(float)
    ynm = ym.filled(0)

    w = Blackman_weights(half_width, exclude='ends')
    if half_width > 100:
        import scipy.signal as sig
        def _convolve(y):
            return sig.fftconvolve(y, w, mode='same')
    else:
        def _convolve(y):
            return np.convolve(y, w, mode='same')

    ytop = np.apply_along_axis(_convolve, axis, ynm)
    ybot = np.apply_along_axis(_convolve, axis, goodmask)

    ww = ybot / w.sum()
    yf = ma.masked_where(ww < min_fraction, ytop)
    yf /= ybot

    if masked is None:
        if y_is_ma:
            return yf, ww
        else:
            return yf.filled(np.nan), ww

    if not masked:
        return yf.filled(np.nan), ww

    return yf, ww



