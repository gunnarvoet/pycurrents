
'''
Provides the functionality of mstdgap.m, though with a different interface.
Additional classes and or functions may be added.
'''
import numpy as np
import numpy.ma as ma

class Stats:
    '''
    Calculate standard statistics while ignoring data gaps, which
    may be indicated by nan values and/or by masked array input.

    Usages:
        1) (m, s, n, med) = Stats(y)(median=True)
        2) Sy = Stats(y)
           m = Sy.mean      # mean
           s = Sy.std       # standard deviation
           n = Sy.N         # number of valid points
           med = Sy.median  # median
           ydm = Sy.demeaned  # de-meaned input array

    In the first case we call the instance to get all the statistics at
    once; in the second we access the statistics as attributes.  In
    the latter case, subsequent accesses are cheap because the value
    is stored in the instance.  Each statistic is calculated
    only the first time it is requested.

    Caution: the outputs are references to arrays that may be needed
    for subsequent calculations, so don't modify them unless you
    have already done all calculations.

    For usage (1), the argument median=True results in all four
    statistics; median=False, the default, calculates and outputs
    only the first three.

    The constructor has the following keyword arguments and defaults:
        axis=None : specifies the axis along which the stats are calculated;
                    if None, they are calculated for the flattened array.
        squeeze=True: stats for an N-dimensional input have N-1
                dimensions if True, N dimensions if False.
                If False, the stats are broadcastable to the dimensions
                of the input array.
                The case axis=None is an exception; then a scalar
                or masked array scalar is returned regardless of
                the value of squeeze.
                See also the broadcastable method.
        masked='auto' : True|False|'auto' determines the output;
                if True, output will be a masked array;
                if False, output will be an ndarray with nan used
                            as a bad flag if necessary;
                if 'auto', output will match input, except that
                            an ndarray will be returned if nothing
                            is masked.
                (The N attribute is an ndarray in any case.)
        biased=False : set to True for biased estimate of sample std.
                In the biased estimate, the sum of squares is divided
                by N; in the unbiased estimated, by N-1.

    '''
    def __init__(self, y, axis=None, squeeze=True, masked='auto', biased=False):
        '''
        See the class docstring.
        '''
        y = np.array(y, copy=True, subok=True, dtype=float)
        self._biased = biased
        self._squeeze = squeeze
        _masked_input = ma.isMaskedArray(y)
        self._kwmasked = masked
        self._nanout = not (masked or
                            (masked == 'auto' and _masked_input))
        ydata = ma.getdata(y)
        mask = ~np.isfinite(ydata)
        m = ma.getmask(y)
        if m is not ma.nomask:
            mask = np.logical_or(mask, m)
        fullmask = mask
        if not np.any(mask):
            mask = ma.nomask
        self._mask = mask
        self._yf = ydata
        self._axis = axis
        if axis is None:
            self._yf = self._yf.ravel()
            if self._mask is not ma.nomask:
                self._mask = self._mask.ravel()
        elif axis >= self._yf.ndim:
            raise ValueError("axis =  %d; must be less than y.ndim which is %d"
                                        % (axis, self._yf.ndim))
        if self._mask is not ma.nomask:
            np.putmask(self._yf, self._mask, 0)
        self._mean = None
        self._std = None
        self._median = None
        self._N = np.asarray((~fullmask).sum(axis=axis))
        if axis is not None:
            self.b_shape = list(self._yf.shape)   # broadcastable shape
            self.b_shape[self._axis] = 1
        else:
            self.b_shape = (1,)

    def __call__(self, median=False):
        if median:
            return self.mean, self.std, self.N, self.median
        else:
            return self.mean, self.std, self.N

    def broadcastable(self, x):
        '''
        Change the shape of a summary statistic (mean, N, std,
        or median) so that it is broadcastable to the shape of
        the input array.  This is needed only if the class
        constructor was called with squeeze=False.
        '''
        try:
            if x.ndim < 1:
                return x
        except AttributeError:  # presumably a scalar
            return x
        return x.view().reshape(*self.b_shape)

    def _process_shape(self, x):
        if not self._squeeze:
            return x.view().reshape(*self.b_shape)
        if x.size == 1 and x.ndim == 1:
            return x[0]
        return x

    def _process_format(self, x):
        if self._nanout:
            try:
                x = x.filled(np.nan) # also works on masked array scalars
            except AttributeError:
                pass
        elif self._kwmasked == 'auto':
            try:
                if x.mask is ma.nomask:
                    x = ma.getdata(x)
            except AttributeError:
                pass
        return x

    def get_N(self):
        return self._process_shape(self._N)
    N = property(get_N)

    def calc_mean(self):
        if self._mean is None:
            m = ma.divide(self._yf.sum(axis=self._axis), self._N)
            self._mean = m
        return self._mean

    def get_mean(self):
        m = self.calc_mean()
        m = self._process_shape(self._process_format(m))
        return m
    mean = property(get_mean)

    def calc_std(self):
        if self._std is None:
            if self._biased:
                n = self._N
            else:
                n = self._N-1
            m = self.broadcastable(ma.filled(self.calc_mean(), 0))
            ss = (self._yf - m)**2
            if self._mask is not ma.nomask:
                np.putmask(ss, self._mask, 0)
            self._std = np.sqrt(ma.divide(ss.sum(axis=self._axis), n))
        return self._std

    def get_std(self):
        s = self.calc_std()
        s = self._process_shape(self._process_format(s))
        return s
    std = property(get_std)

    def calc_median(self):
        if self._median is None:
            y = self._yf.copy()
            if self._mask is not ma.nomask:
                np.putmask(y, self._mask, np.inf)
            ysort = np.sort(y, axis=self._axis)
            if self._axis is None:
                axis = 0
            else:
                axis = self._axis
            ii = np.indices(ysort.shape)[axis]
            ngood = self.broadcastable(self._N)
            i0 = (ngood-1)//2
            i1 = ngood//2
            cond = np.logical_or(i0==ii, i1==ii)
            m0 = np.zeros_like(ysort)
            np.putmask(m0, cond, ysort)
            n = cond.sum(axis=axis)
            m = m0.sum(axis=axis)/n
            m = ma.masked_where(n<1, m)
            self._median = m
        return self._median

    def get_median(self):
        m = self.calc_median()  # can return a scalar
        m = self._process_shape(self._process_format(m))
        return m
    median = property(get_median)


    def get_demeaned(self):
        m = self.broadcastable(self.calc_mean())
        y = self._yf - m
        if self._mask is not ma.nomask:
            if self._nanout:
                np.putmask(y, self._mask, np.nan)
            else:
                y = ma.array(y, mask=self._mask)
        return y
    demeaned = property(get_demeaned)



