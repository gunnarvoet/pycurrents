"""
Calculations related to singular value decomposition, including
EOFs, and calculations of ellipse parameters.

"""
import numpy as np

class EOF:
    def __init__(self, arr):
        """
        *arr* is an array of at least 2 dimensions.
        The first dimension is time-like, all others are
        concatenated and considered space-like.

        Initialization creates attributes u, s, v directly from
        a call to np.linalg.svd.

        The columns of u are the time series and the rows of v are
        the spatial EOFs. The amplitudes are in the 1-D array s,
        the length of which is the minimum of the time and space
        dimensions.

        If the dimensionality of *arr* is greater than 2, then
        the attribute v_reshaped will contain the EOFs reshaped
        to match the spatial dimensions of *arr*.

        No space or time mean is removed.

        """
        self.arr = arr.copy()
        self.input_ndim = self.arr.ndim
        self.input_shape = self.arr.shape
        self.arr = self.arr.reshape(self.arr.shape[0], -1)
        self.svd()

    def svd(self):
        self.u, self.s, self.v = np.linalg.svd(self.arr, full_matrices=False)
        self.reshape_v()

    def reshape_v(self):
        if self.input_ndim > 2:
            shape = [self.v.shape[0]]
            shape.extend(self.input_shape[1:])
            self.v_reshaped = self.v.reshape(shape)
        else:
            self.v_reshaped = self.v

    def reshape(self, a):
        if self.input_ndim == 2:
            return a
        return np.reshape(a, self.input_shape)

    def reconstruction(self, N):
        """
        Returns the sum of the first N eofs.
        """
        sl = slice(0, N)
        S = np.diag(self.s[sl])
        recon = np.dot(self.u[:, sl], np.dot(S, self.v[sl]))
        return self.reshape(recon)

    def subset(self, sub):
        """
        sub is a list of eofs to include, or a single eof
        """
        if not np.iterable(sub):
            sub = [sub]
        S = np.diag(self.s[sub])
        recon = np.dot(self.u[:,sub], np.dot(S, self.v[sub]))
        return self.reshape(recon)

    def percent_var(self):
        ss = self.s ** 2
        return 100 * ss / np.sum(ss)

class EOF_masked(EOF):
    """
    Use the method of Beckers and Rixen, 2003, to calculate
    eofs from gappy data, and to use those eofs to fill the
    gaps.

    The filled array is in the *arr_filled* attribute, and
    the number of EOFs used in the filling is in *nfuncs*.
    Other attributes and methods are as in the EOF class.

    Beckers, J. M. and M. Rixen, 2003.  EOF calculations and
    data filling from incomplete oceanographic datasets.
    J. Atmos. Oceanic Technol., 20, 1839--1856.

    """
    def __init__(self, arr, nfuncs=10, niters=10, tol=0.01):
        """
        *nfuncs* is the maximum number of EOFs that may be used to fill gaps

        *niters* is the maximum number of iterations for the filling

        *tol* is the tolerance for fractional difference in mean squared
        value of interpolated regions, below which the iteration is
        considered to have converged.
        """
        self._nfuncs = nfuncs
        self.nfuncs = None # will be replaced by number used
        self.niters = niters
        self.tol = tol
        EOF.__init__(self, arr)

    def svd(self):
        self.mask = np.ma.getmaskarray(self.arr)
        ijgood = np.nonzero(~self.mask)
        # set aside 5% of the good values:
        ngood = len(ijgood[0])
        ntest = int(0.05 * ngood)
        self.log = ["ntest is %s" % ntest]
        isel = np.random.randint(0, high=ngood-1, size=ntest)
        self.test_samples = (ijgood[0][isel], ijgood[1][isel])
        self.testmask = np.zeros_like(self.mask)
        self.testmask[self.test_samples] = True

        arrf = self.arr.filled(0)
        arrf_orig = arrf.copy()
        testvals = arrf_orig[self.testmask]
        np.putmask(arrf, self.testmask, 0)
        mask = np.ma.mask_or(self.testmask, self.mask)

        testerrsq0 = (testvals**2).mean()
        self.log.append("initial mean squared test values %s" % testerrsq0)
        iterkw = dict(niters=self.niters, tol=self.tol)

        for nfuncs in range(1, self._nfuncs+1):
            arrf = self.iterate(arrf, mask, nfuncs, **iterkw)
            testdiff = arrf[self.testmask] - testvals
            testerrsq = (testdiff**2).mean()
            errsqdiff = testerrsq0 - testerrsq
            testerrsq0 = testerrsq
            self.log.append("nfuncs, test, test diff: %s %s %s" %
                                        (nfuncs, testerrsq, errsqdiff))
            if nfuncs > 1 and errsqdiff < 0:
                # Stop here--it is getting worse.
                break

        if nfuncs < self._nfuncs:
            # The last value of nfuncs was worse, so back up.
            nfuncs -= 1

        self.log.append("using %d eofs" % nfuncs)
        arrf_final = arrf_orig.copy()
        arrf_final[self.mask] = arrf[self.mask]
        arrf_final = self.iterate(arrf_final, self.mask, nfuncs)
        self.u, self.s, self.v = np.linalg.svd(arrf_final, full_matrices=False)
        self.arr_filled = arrf_final
        self.nfuncs = nfuncs
        self.reshape_v()

    def iterate(self, arr, mask, nfuncs, niters=10, tol=0.01):
        if not mask.any():
            return arr
        fill_msq = (arr[mask]**2).mean()
        for i in range(niters):
            eof = EOF(arr)
            recon = eof.reconstruction(nfuncs)
            arr[mask] = recon[mask]
            new_fill_msq = (recon[mask]**2).mean()
            self.log.append("iterate: %s %s" % (i, new_fill_msq))
            improvement = abs(new_fill_msq - fill_msq) / max(fill_msq, new_fill_msq)
            if i > 0 and improvement < tol:
                break
            fill_msq = new_fill_msq
        return arr

####

def std_ellipse_from_vcv(uu, vv, uv):
    """
    Calculate the ellipse radii and angle from a variance-covariance matrix.
    """
    if any(map(np.ma.isMA, (uu, vv, uv))):
        sqrt = np.ma.sqrt
        arctan2 = np.ma.arctan2
    else:
        sqrt = np.sqrt
        arctan2 = np.arctan2

    pm = sqrt((uu - vv)**2 + 4 * uv**2)

    lambda1 = 0.5 * (uu + vv + pm)
    lambda2 = 0.5 * (uu + vv - pm)
    lambda2 = np.ma.clip(lambda2, 0, None)  # returns ndarray if not masked
    phi = arctan2(lambda1 - uu, uv)  # arctan2(y, x)

    return sqrt(lambda1), sqrt(lambda2), phi


def std_ellipse_from_vel(u, v, axis=0):
    """
    *u*, *v* are sequences in which the first dimension is time-like

    Returns (smaj, smin, ang) where smaj, smin are the semi-major
    and -minor axes of the std ellipse, and ang is the math angle,
    radians CCW from the x-axis.

    The calculation does not include a DOF bias correction.
    """
    mnkw = dict(axis=axis, keepdims=True)
    u = np.asanyarray(u).astype(float)
    u = u - u.mean(**mnkw)
    v = np.asanyarray(v).astype(float)
    v = v - v.mean(**mnkw)
    # No ddof bias correction...
    uu = (u**2).mean(**mnkw)
    vv = (v**2).mean(**mnkw)
    uv = (u*v).mean(**mnkw)

    return std_ellipse_from_vcv(uu, vv, uv)





##############################################################

def testvars():
    t = np.linspace(0.0, 10.0, 50)
    x = np.linspace(0.0, 25.0, 250)
    mt = len(t)
    nx = len(x)

    z = np.sin(t)[:, np.newaxis] * np.cos(3*x)
    z += 0.5 * np.sin(2*t)[:, np.newaxis] * np.cos(5*x)
    z += 0.3 * np.sin(3.5*t)[:, np.newaxis] * np.cos(6.5*x)
    z += 0.25 * np.random.normal(size=(mt, nx))

    z -= z.mean(axis=0)
    return t, x, z

def test():
    t, x, z = testvars()

    eof = EOF(z)
    return eof

def test3():
    t, x, z = testvars()

    mask = np.zeros(z.shape, dtype=bool)
    mask[5:20, 50:70] = True
    mask[15:30, 150:200] = True
    mask[0:25, 210:240] = True
    z[mask] = 0

    eof = EOF_masked(np.ma.array(z, mask=mask))
    return eof

def test4():
    # like test3, but 3-D instead of 2-D
    t, x, z = testvars()

    mask = np.zeros(z.shape, dtype=bool)
    mask[5:20, 50:70] = True
    mask[15:30, 150:200] = True
    mask[0:25, 210:240] = True
    z[mask] = 0

    zz = z.reshape([z.shape[0], 50, 5])

    eof = EOF_masked(np.ma.array(zz, mask=mask))
    return eof


