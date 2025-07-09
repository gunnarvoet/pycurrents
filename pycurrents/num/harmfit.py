"""
Least squares fit to mean, trend, harmonics; and complex demodulation.

The fit part is inspired by, but not identical to, our matlab
harmcrv/harmfit pair.

"""
import numpy as np

from pycurrents.num import bl_filt, Blackman_filter
from pycurrents.system import Bunch


def harmcrv(t, periods, t0=None):
    periods = np.asarray(periods)
    if t0 is None:
        t0 = t.mean()
    nparams = 2 + 2 * len(periods)
    mtimes = len(t)
    a = np.ones((mtimes, nparams), dtype=np.complex128)
    a[:,-1] = t - t0 # trend in last column
    freqs = (2 * np.pi) / periods
    for i, freq in enumerate(freqs):
        phase = (1j * freq) * t
        a[:, 2*i] = np.exp(phase)
        a[:, 2*i+1] = np.exp(-phase)

    return a, freqs


class HarmonicFit:
    """
    Once initialized, properties provide access to calculated
    quantities:
      *a* (Mtimes, 2 * Kperiods + 1 or 2) is the model array.
        The first 2 * Kperiods entries are the harmonics; the next
        entry is 1, for the mean; and if a trend is included, the
        last column is the trend.
      *x* (2 * Kperiods + 1 or 2, Nlocations) is the set of fit coefficients.
      *f* (Mtimes, Nlocations) is the fit
      *r* (Mtimes, Nlocations) are the residuals.
    """

    def __init__(self, t, u, periods, min_frac=0.8, trend=True):
        """
        *t* array, (Mtimes,)
        *u* array, (Mtimes,) or (Mtimes, Nlocations)
        *periods* sequence of Kperiods harmonic periods
        """
        self.min_frac = min_frac
        self.trend = trend
        self.u = np.asanyarray(u)
        self.masked = np.ma.isMA(self.u)
        self.one_d = False
        if self.u.ndim == 1:
            self._u = self.u.reshape((self.u.shape[0], 1))
            self.one_d = True
        else:
            self._u = self.u
        self.t = np.asarray(t)
        self.periods = np.asarray(periods)
        self.nfreqs = len(self.periods)
        self.nharm = 2 * self.nfreqs
        self.i_mean = self.nharm
        a, self.freqs = harmcrv(self.t, self.periods)
        self.isreal = self.u.dtype.kind == 'f'
        if self.isreal:
            for j in range(self.nfreqs):
                c = a[:, 2*j].copy()
                a[:,2*j] = c.real     # cos
                a[:,2*j+1] = c.imag   # sin
            a = a.real
        self._a = a
        self._x = None
        self._f = None
        self._r = None

        self.t0 = self.t.mean()

    @property
    def a(self):
        if self.trend:
            return self._a
        else:
            return self._a[:, :-1]

    @property
    def x(self):
        if self._x is None:
            a = self.a
            if self.masked:
                if self.isreal:
                    dtype = np.float64
                else:
                    dtype = np.complex128
                x = np.ma.zeros((a.shape[1], self._u.shape[1]), dtype=dtype)
                for j in range(x.shape[1]):
                    uu = self._u[:,j]
                    frac = uu.count() / float(uu.size)
                    if frac >= self.min_frac:
                        mask = uu.mask
                        aa = a.compress(np.logical_not(mask), axis=0)
                        x[:, j] = np.linalg.lstsq(
                            aa, uu.compressed(), rcond=-1)[0]  # temporary, until numpy>1.14 (then use None)
                    else:
                        x[:, j] = np.ma.masked
            else:
                x = np.linalg.lstsq(a, self._u, rcond=-1)[0]  # temporary, until numpy>1.14 (then use None)
            if self.one_d:
                x.shape = (x.shape[0],)
            self._x = x
        return self._x

    @property
    def f(self):
        if self._f is None:
            if self.masked:
                self._f = np.ma.dot(self.a, self.x)
            else:
                self._f = np.dot(self.a, self.x)
        return self._f

    @property
    def r(self):
        if self._r is None:
            self._r = self.u - self.f
        return self._r

    @property
    def xmean(self):
        return self.x[self.i_mean]

    def fit_some(self, iharm, mean=False, trend=False):
        """
        Return the fit to harmonics with indices iharm.
        """
        n = self.nharm + 1
        if trend:
            if not self.trend:
                raise ValueError("Trend was not calculated")
            n += 1
        cond = np.zeros((n,), dtype=bool)
        for i in iharm:
            cond[2*i] = True
            cond[2*i+1] = True
        if mean:
            cond[self.i_mean] = True
        if trend:
            cond[-1] = True
        a = self.a[:,cond]
        x = self.x[cond]
        if self.masked:
            return np.ma.dot(a, x)
        return np.dot(a, x)


def demod(dday, u, hours, nfilt, axis=0, min_fraction=0.5):
    """
    Complex demodulation of a real series, *u*,
    on a grid, *dday*, at the frequency with a period of
    *hours*.  The low-pass filter is Blackman with a
    half-width of *nfilt* points.

    *u* may be 1-d or 2-d

    Returns a Bunch with *amp* being the complex amplitude
    on the dday grid, *vel* the reconstructed real series,
    and *frac* the fraction of the Blackman window with data.
    """
    if u.ndim == 2 and dday.ndim == 1 and axis == 0:
        dday = dday[:, np.newaxis]
    m = np.exp((-1j*2*np.pi*24.0/hours) * dday)
    mr, frac = bl_filt(u*m.real, nfilt, axis=axis, min_fraction=min_fraction)
    mi = bl_filt(u*m.imag, nfilt, axis=axis, min_fraction=min_fraction)[0]
    camp = 2 * (mr + 1j * mi)
    reconstructed = (camp * np.conj(m)).real
    return Bunch(hours=hours, amp=camp, vel=reconstructed, frac=frac, m=m)


def demod2(t, u, period, hwidth=2.0, axis=0, min_fraction=0.5, masked=None):
    """
    Complex demodulation of a real series, *u*,
    on a uniform grid, *t*, at the frequency with a given *period*
    in the same units as *t*. The low-pass filter is Blackman
    with a half-width of *hwidth* times the period.

    *u* may be n-d, with *axis* specifying the *t* dimension.

    Returns a Bunch with *amp* being the (real) amplitude
    on the dday grid, *angle_deg* the phase in degrees,
    *reconstructed* the reconstructed real series,
    *frac* the fraction of the Blackman window with data, and
    *n_hwidth* the integer half-width parameter used in bl_filt.

    This is an experimental replacement for the earlier dmod.
    It is almost certainly superceded by complex_demodulation().
    """
    dt = (t[-1] - t[0]) / (len(t) - 1)
    n_hwidth = int(round(hwidth * period / dt))

    harmonic = np.exp((-1j*2*np.pi/period) * t)

    if u.ndim > 1:
        ind = [None] * u.ndim
        ind[axis] = slice(None)
    harmonic = harmonic[tuple(ind)]

    amp, frac = Blackman_filter(u * harmonic, n_hwidth,
                                axis=axis,
                                min_fraction=min_fraction,
                                masked=masked)

    camp = 2 * amp
    reconstructed = (camp * harmonic.conj()).real

    if np.ma.is_masked(amp):
        _angle = np.ma.angle
    else:
        _angle = np.angle

    return Bunch(period=period,
                 hwidth=hwidth,
                 complex_amp=camp,
                 amp=camp.real,
                 angle_deg=_angle(camp, deg=True),
                 reconstructed=reconstructed,
                 n_hwidth=n_hwidth,
                 frac=frac)


def complex_demodulation(t, u, period,
                         hwidth=2.0,
                         axis=0,
                         min_fraction=0.5,
                         masked=None):
    """
    Complex demodulation of a real or complex series, *u*,
    on a uniform grid, *t*, at the frequency with a given *period*
    in the same units as *t*. The low-pass filter is Blackman
    with a half-width of *hwidth* times the period.

    *u* may be n-d, with *axis* specifying the *t* dimension.

    Returns a Bunch with the *reconstructed* time series based
    on the demodulation, and *frac* the fraction of the filter
    with data.  If the input is real, the return includes
        *complex_amp*  the complex amplitude
        *amp*  the (real) amplitude
        *angle* the phase in degrees

    If the input is complex, the return includes
        *ccw* the CCW complex amplitude
        *cw* the CW complex amplitude
        *ellipse* the output of ellipse_params.

    This is an experimental replacement for the earlier dmod and demodc.
    """

    _is_complex = u.dtype.kind == 'c'

    dt = (t[-1] - t[0]) / (len(t) - 1)
    n_hwidth = int(round(hwidth * period / dt))

    out = Bunch(period=period,
                 hwidth=hwidth,
                 n_hwidth=n_hwidth)

    # CW rotation of harmonic to isolate CCW part of input
    harmonic = np.exp((-1j*2*np.pi/period) * t)
    # CCW rotation, to isolate CW part of input, or reconstruct CCW part
    harmonic_ccw = harmonic.conj()

    if u.ndim > 1:
        ind = [None] * u.ndim
        ind[axis] = slice(None)
        harmonic = harmonic[tuple(ind)]
        harmonic_ccw = harmonic_ccw[tuple(ind)]

    amp, frac = Blackman_filter(u * harmonic, n_hwidth,
                                axis=axis,
                                min_fraction=min_fraction,
                                masked=masked)

    if _is_complex:
        ampcw, frac = Blackman_filter(u * harmonic_ccw, n_hwidth,
                                      axis=axis,
                                      min_fraction=min_fraction,
                                      masked=masked)
        reconstructed = (amp * harmonic_ccw + ampcw * harmonic)

        out.update(ccw=amp,
                   cw=ampcw,
                   ellipse=ellipse_params(amp, ampcw))
    else:
        camp = 2 * amp
        reconstructed = (camp * harmonic_ccw).real

        if np.ma.is_masked(amp):
            _angle = np.ma.angle
        else:
            _angle = np.angle

        out.update(complex_amp=camp,
                   amp=np.abs(camp),
                   angle_deg=_angle(camp, deg=True))

    out.update(reconstructed=reconstructed,
               frac=frac)
    return out


def demodc(dday, uiv, hours, nfilt, axis=0, min_fraction=0.5):
    """
    Complex demodulation of a complex series, *uiv*,
    on a grid, *dday*, at the frequency with a period of
    *hours*.  The low-pass filter is Blackman with a
    half-width of *nfilt* points.

    *uiv* may be 1-d or 2-d

    Returns a Bunch with *ccw* and *cw* the complex amplitudes
    on the dday grid, *vel* the reconstructed complex series,
    and *frac* the fraction of the Blackman window with data.
    """
    if uiv.ndim == 2 and dday.ndim == 1 and axis == 0:
        dday = dday[:, np.newaxis]
    mccw = np.exp((-1j*2*np.pi*24.0/hours) * dday)
    mcw = np.exp((1j*2*np.pi*24.0/hours) * dday)
    dmodccw, frac = bl_filt(uiv * mccw, nfilt, axis=axis,
                                            min_fraction=min_fraction)
    dmodcw = bl_filt(uiv * mcw, nfilt, axis=axis, min_fraction=min_fraction)[0]
    reconstructed = dmodccw * np.conj(mccw) + dmodcw * np.conj(mcw)
    return Bunch(hours=hours, ccw=dmodccw, cw=dmodcw, vel=reconstructed,
                    frac=frac, mccw=mccw, mcw=mcw)


def ellipse_params(ccw, cw, wrap_start=0):
    """
    Given *ccw* and *cw* complex amplitudes, calculate ellipse
    parameters and return them in a Bunch.

    *wrap_start* specifies the bottom of the 180-degree range
    for the *angle* attribute, since ellipse orientation is only
    specified mod 180.

    Keys and attributes:

    *major*     semi-major axis
    *minor*     semi-minor axis
    *e*         eccentricity
    *angle*     semi-major axis orientation, degrees CCW from the real axis
    *tphase*    corresponding temporal phase in degrees
    *cwfrac*    fraction of total variance in CW component
    *cwphase*   phase in degrees of CW component
    *ccwphase*  phase in degrees of CCW component
    """

    if np.ma.isMA(ccw):
        _sqrt = np.ma.sqrt
        _angle = np.ma.angle
    else:
        _sqrt = np.sqrt
        _angle = np.angle
        # np.abs works for masked arrays, returning a masked array

    major = np.abs(ccw) + np.abs(cw)
    minor = np.abs(np.abs(ccw) - np.abs(cw))
    eccentricity = _sqrt(major**2 - minor**2) / major
    theta = 0.5 * (_angle(ccw, True) + _angle(cw, True))
    theta = (theta + wrap_start) % 180 - wrap_start
    tphase = 0.5 * (_angle(cw, True) - _angle(ccw, True))
    cwfrac = np.abs(cw)**2 / (np.abs(ccw)**2 + np.abs(cw)**2)
    cwphase = _angle(cw, True)
    ccwphase = _angle(ccw, True)
    out = Bunch(major=major, minor=minor, e=eccentricity, angle=theta,
                 tphase=tphase, cwfrac=cwfrac,
                 cwphase=cwphase, ccwphase=ccwphase)
    return out


###
def test_data():
    t = np.arange(-50, 50.01)
    u = 1.1 + t / 25.0 + 1.2 * np.cos(2 * np.pi * t / 12)
    v = 0.9 + 0.1*t / 25 + 1.5 * np.sin(2 * np.pi * t / 23.9)
    uv = np.vstack((u, v)).T
    return uv, t / 24.0       # time in days


def test_complex():
    """
    ccw semidiurnal, cw diurnal
    """
    t = np.arange(-50, 50.01)
    u = 1 + t / 25 + 1.2 * np.exp(1j * 2*np.pi * t / 12)
    v = 1 + t / 25 + 1.2 * np.exp(-1j * 2*np.pi * t / 24)
    uv = np.vstack((u, v)).T
    return uv, t / 24.0       # time in days


