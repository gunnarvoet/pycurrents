"""
Calculate linear baroclinic normal modes for hydrostatic stratified flow
with constant depth.  The rigid lid and Boussinesq approximations are
used.  The input must be buoyancy frequency squared on a uniform depth,
pressure, or z grid.

The normal entry point is the single function modes(); see the
docstring for instructions.

This is all new as of June, 2013, so it is experimental and highly
subject to change.

TODO: add the eigenvalue calculation for a layer model.

TODO: improve the docstrings.

Note: scipy is required.

"""
import numpy as np

try:
    import scipy.linalg as linalg
    from scipy.optimize import brentq
except ImportError:
    raise ImportError("scipy is required by the modes module")

from pycurrents.data._modes import _rk4_single
from pycurrents.system import Bunch

class Modes:
    """
    Linear normal mode calculation via the shooting method.
    """

    nsteps = 50

    def __init__(self, z, bvfsq, bc_zero_w=True):
        """
        Set bc_zero_w to False to get the "modes" with
        zero u at the bottom instead of zero w.
        """
        self.z = np.asarray(z).astype(np.float64)
        self.bvfsq = np.ma.filled(bvfsq, 0).astype(np.float64)

        self._bvfsq = self.bvfsq[::-1]
        self._z = self.z[::-1]

        self.nd = self.z.size
        if (self.z.ndim != 1 or self.bvfsq.ndim != 1 or
            self.z.shape != self.bvfsq.shape):
            raise ValueError("z and bvfsq must be 1-D arrays of the same size")

        self.bc_zero_w = bc_zero_w
        if bc_zero_w:
            self.rk4_kw = {}
        else:
            self.rk4_kw = dict(w0=1.0, p0=0.0)

    def _func(self, c):
        w, u = _rk4_single(self._z, self._bvfsq, c, **self.rk4_kw)
        return w[-1]

    def find_next_mode(self, c0, step=1.2):
        c0 = float(c0)
        w, u = _rk4_single(self._z, self._bvfsq, c0, **self.rk4_kw)
        s0 = np.sign(w[-1])
        modenum = int((np.diff(np.sign(u)) != 0).sum())
        modenum = max(modenum, 1)

        for i in range(1, self.nsteps):
            c1 = c0 * modenum / (modenum + step)
            w, _ = _rk4_single(self._z, self._bvfsq, c1, **self.rk4_kw)
            s1 = np.sign(w[-1])
            if s1 != s0:
                break
            c0 = c1

        if i == self.nsteps - 1:
            raise RuntimeError("could not find next mode")

        c = brentq(self._func, c0, c1)
        w, u = _rk4_single(self._z, self._bvfsq, c, **self.rk4_kw)
        modenum = int((np.diff(np.sign(u)) != 0).sum())
        self._c = c
        self._w = w
        self._u = u
        self._modenum = modenum
        self._nsearch = i

    def find_first_mode(self):
        c = 10
        self.find_next_mode(c, step=0.5)
        for i in range(1, self.nsteps):
            if self._modenum == 1:
                break
            c *= self._modenum  # estimate mode 1 c
            c *= 1.2 ** i       # start a bit larger
            self.find_next_mode(c, step=0.2)

        if i == self.nsteps - 1:
            raise RuntimeError("could not find mode 1")

    def __call__(self, nmodes):
        self.c = np.empty((nmodes,), np.float64)
        self.w = np.empty((self.nd, nmodes), np.float64)
        self.u = np.empty((self.nd, nmodes), np.float64)
        self.nodes = np.empty((nmodes,), np.int64)

        for i in range(nmodes):
            if self.bc_zero_w:
                step = 1.2
            else:
                step = 0.5
            if i == 0:
                self.find_first_mode()
            else:
                self.find_next_mode(self._c * 0.99999, step=step)
                # If we skipped ahead, back up and start again,
                # with a very small step to ensure we don't miss.
                if self._modenum != self.nodes[i-1] + 1:
                    self.find_next_mode(self.c[i-1] * 0.9999,
                                        step=step/5.0)
            self.c[i] = self._c
            self.nodes[i] = self._modenum
            self.u[:, i] = self._u[::-1]
            self.w[:, i] = self._w[::-1]

        usgn = np.sign(self.u[0])  # top
        wsgn = usgn

        self.w /= (np.sqrt((self.w ** 2).mean(axis=0)) * wsgn)

        self.u /= (np.sqrt((self.u ** 2).mean(axis=0)) * usgn)

        return Bunch(c=self.c, u=self.u, w=self.w, n=self.nodes)


def _fullarray(bvfsq):
    nd = len(bvfsq)
    A = np.zeros((nd, nd), np.float64)
    A.flat[::nd+1] = -2
    A.flat[1::nd+1] = 1
    A.flat[nd::nd+1] = 1
    A[0, 0] = -1
    A[0, 1] = 0
    A[-1, -2] = 0
    A[-1, -1] = -1
    B = np.zeros_like(A)
    B.flat[::nd+1] = -bvfsq
    B[0, 0] = B[-1, -1] = 0

    e, v = linalg.eig(B, b=A)

    return e, v

def modes_matrix(z, bvfsq, nmodes=None):
    dz = z[1] - z[0]
    bvfsq = np.ma.filled(bvfsq, 0)

    e, v = _fullarray(bvfsq)

    i = np.argsort(e.real)[::-1]
    e = e[i].real
    w = v[:, i].real
    i_nonzero = e > 0
    if not i_nonzero.all():
        e = e[i_nonzero]
        w = w[:, i_nonzero]

    if nmodes is not None:
        e = e[:nmodes]
        w = w[:, :nmodes]

    w /= np.sqrt((w ** 2).mean(axis=0))

    c = np.sqrt(e) * abs(dz)

    p = np.zeros_like(w)
    p[1:-1] = (w[2:] - w[:-2])
    p[0] = p[1]
    p[-1] = p[-2]
    p -= p.mean(axis=0)
    p /= np.sqrt((p ** 2).mean(axis=0))

    if dz < 0:
        psgn = np.sign(p[0])
        wsgn = - psgn  # because dz is negative
    else:
        psgn = np.sign(p[-1])
        wsgn = psgn
    w *= wsgn
    p *= psgn

    return Bunch(c=c, u=p, w=w)

def modes(z, bvfsq, nmodes=None, method='shooting'):
    """
    Calculate linear normal modes for continuous stratification,
    flat bottom, usually with the hydrostatic approximation.
    To calculate the modes without the non-hydrostatic
    approximation, supply N**2 - omega**2 as bvfsq.

    z and bvfsq are the z coordinate (positive upwards) and
    corresponding squared Brunt Vaisala frequency, arranged
    from the shallowest depth downwards.  The z grid should be
    uniform, or very nearly so (e.g., calculating it from a
    uniform pressure grid is fine).  bvfsq may be a masked
    array, in which case masked values will be treated as zero.


    nmodes is the number of modes to be returned.  By default
    it will be 50 for the shooting method, and all for the
    matrix method.

    method defaults to 'shooting', which works best with finely-resolved
    BVF.  To use the 'matrix' method instead, you may need to
    subsample your z and bvfsq arrays.  To prevent excessive
    slowdowns, or a possible crash, there is an arbitrary hard
    limit of 1000 points.

    Returns: a Bunch with a 1-D array 'c' containing the gravity
    wave phase speeds in m/s; and 2-D arrays 'u' and 'w' in which
    the columns are the mode shapes for horizontal and vertical
    velocity components, respectively.  They are normalized to
    unit standard deviation, and to have the first (surface)
    element of 'u' be positive.

    Note: the calculation of high modes is unreliable by any
    method because they are not well-resolved on the discrete
    and uniform grid used here.

    """
    if method not in ('shooting', 'matrix'):
        raise ValueError("method must be 'shooting' or 'matrix'")

    nd = len(bvfsq)
    if nd > 1000 and method == 'matrix':
        raise ValueError('The input exceeds the maximum of 1000 points' +
                         ' allowed for the matrix method')

    if method == 'shooting':
        if nmodes is None:
            nmodes = 50
        nmodes = min(nmodes, nd - 1)

        m = Modes(z, bvfsq)
        return m(nmodes)

    return modes_matrix(z, bvfsq, nmodes)

def layer_modes(h, rho):
    """
    Calculate normal modes using the Lighthill matrix method.

    Given a set of discrete layers of thickness h and potential
    density rho, return a Bunch with attributes c for the wave
    speed and u for the pressure and velocity eigenvectors
    (as columns in the matrix).  A constant value of 9.8 is
    used for g.

    This returns the barotropic mode along with the baroclinic.
    """

    A = h * rho / rho[:, np.newaxis]
    H = np.tile(h, (len(h), 1))
    ind = np.arange(len(h))
    cond = ind >= ind[:, np.newaxis]
    A = np.where(cond, H, A)

    e, v = linalg.eig(A)

    i = np.argsort(e.real)[::-1]
    e = e[i].real
    i_nonzero = e > 0
    e = e[i_nonzero]
    u = v[:, i[i_nonzero]].real

    u /= np.sqrt(((u ** 2) * h[:, np.newaxis]).sum(axis=0) / h.sum() )
    u *= np.sign(u[0])

    c = np.sqrt(9.8 * e)

    return Bunch(c=c, u=u)
