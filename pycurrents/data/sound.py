"""
Functions for calculations related to acoustics.

All z values are defined positive down.

Functions:
    attenuation
    db_to_linear
    linear_to_db
    noise_floor
    remove_noise
    trim_bottom

Classes:
    Attenuator

"""
import numpy as np

def attenuation(f=None, z=0, T=20.0, S=35.0, pH=8.0):
    """
    Attenuation of sound in db/m based on the simplified
      formula of Ainslie and McColm (1998)

          f is frequency in kHz
          z is depth in m  (default is 0)
          T is temperature in deg-C  (default is 20)
          S is salinity in PSU       (default is 35)
          pH is pH (default is 8, a typical value in for seawater)

        Arguments must be broadcastable against each other.

      Based on the 99/06/15 matlab script by  J. Walter and E. Firing

      Reference: Ainslie, M.A. and J. G. McColm, 1998. A simplified
      formula for viscous and chemical absorption in sea water.
      Journal of the Acoustical Society of America, 103, 1671-72.
    """
    if f is None:
        raise ValueError("Frequency must be specified.")

    f, Z, T, S, pH = [np.asanyarray(var, dtype=float)
                                        for var in  [f, z, T, S, pH]]

    f1 = 0.78 * np.sqrt(S/35.0) * np.exp(T/26.0)
    f2 = 42.0 * np.exp(T/17.0)

    fsq = f**2

    alpha1 = 0.106 * np.exp((pH-8)/0.56) * f1 /(fsq + f1**2)
    alpha2 = 0.52 * (1+T/43.0) * (S/35.0) * np.exp(-Z/6000.0)
    alpha2 *= f2 / (fsq + f2**2)
    alpha3 = 0.00049 * np.exp(-(T/27.0 + Z/17000.0))

    alpha = (fsq/1000) * (alpha1+alpha2+alpha3)
    return alpha

class Attenuator:
    """
    Calculate transmission loss from spreading and attenuation.

    Initialize with:
        f: frequency in kHz
        z: depth, or monotonic sequence of depths
        T: temperature(s) at corresponding depth(s)
        S: corresponding salinity or salinities (optional)
        pH: corresponding acidity or acidities. (optional)

    Frequency is required.
    For quick and dirty calculations, supply in addition the depth and
    temperature.
    For good calculations, if the range of depths and temperatures is
    significant, supply T(z) profile.
    At ADCP frequencies the calculation is not sensitive to S or pH, so
    they can be left at default values.

    Methods:
        TL_from_range
        TL
    The latter is the one typically used with ADCP data.

    """
    def __init__(self, f=None, *, z=0, T=20.0, **kw):
        if f is None:
            raise ValueError("Frequency must be specified.")
        z = np.asarray(z, dtype=float)
        T = np.asarray(T, dtype=float)
        if z.shape != T.shape or z.ndim > 1:
            raise ValueError("z, T must be scalar or 1-D, with same dimensions")
        if z.size == 1:
            self.scalar = True
            self.alpha = attenuation(f, z, T, **kw)
        else:
            self.scalar = False
            if z[0] != 0:
                self.z_alpha = np.zeros((z.size+2,), dtype= float)
                self.T_alpha = np.zeros_like(self.z_alpha)
                self.z_alpha[1:-1] = z
                self.T_alpha[1:-1] = T
                self.T_alpha[0] = T[0]
            else:
                self.z_alpha = np.zeros((z.size+1,), dtype= float)
                self.T_alpha = np.zeros_like(self.z_alpha)
                self.z_alpha[:-1] = z
                self.T_alpha[:-1] = T
            self.z_alpha[-1] = 10000
            self.T_alpha[-1] = 0
            self.alpha = attenuation(f, self.z_alpha, self.T_alpha, **kw)
            # For transmission loss, we need the integral of alpha dz.
            int_alpha = np.zeros_like(self.alpha)
            dz = np.diff(self.z_alpha)
            alphabar = 0.5 * (self.alpha[1:] + self.alpha[:-1])
            int_alpha[1:] = np.add.accumulate(dz * alphabar)
            self.int_alpha = int_alpha

    def alphabar(self, z, z0):
        """
        Calculate average attenuation coefficient between depth z0 and depths in z.

        z0 must be a scalar, but z can have any shape
        """
        if self.scalar:
            return self.alpha
        zvec = np.array(z, dtype=float)  # Copy, because we modify it.
        zvec[zvec == z0] += 0.01 # fudge to remove singularities
        int_alpha_z0 = np.interp(z0, self.z_alpha, self.int_alpha)
        int_alpha_zvec = np.interp(zvec, self.z_alpha, self.int_alpha)
        alpha = (int_alpha_zvec - int_alpha_z0) / (zvec - z0)
        return alpha

    def TL_from_range(self, r, z0, *, beam_angle=None, direction='down'):
        """
        Return the 2-way transmission loss.

            r: ranges
            z0: transducer depth
            beam_angle: in degrees (required)
            direction: transducer is looking 'up' or 'down'

        See also: TL

        """
        # Note: here and in TL, we are using a kwarg for beam_angle
        # to improve code readability; but we are not giving it a
        # default value because that would make it too easy to
        # forget to specify it; the result would be correct for
        # the OS, but wrong for the WH (if we used 30 degrees,
        # for example).
        if beam_angle is None:
            raise ValueError("beam_angle is required")
        r = np.asarray(r, dtype=float)
        sgn = {'down':1, 'up':-1}[direction]
        zvec = z0 + r * sgn * np.cos(np.deg2rad(beam_angle))
        loss = 20 * np.log10(r) + 2 * self.alphabar(zvec, z0) * r
        return loss

    def TL(self, z, z0, *, beam_angle=None, cellfrac=0.25, axis=-1):
        """
        Return the 2-way transmission loss in db.

            z: bin depths, positive down
            z0: transducer depth
            beam_angle: in degrees
            cellfrac: this is multiplied by cell size and added
                        to cell center position to get position
                        where amplitude is sampled; default is
                        0.25, for BB.  Same for other instruments?
            axis: dimension along which depth increases

        """
        if beam_angle is None:
            raise ValueError("beam_angle is required")
        zvec = np.asarray(z, dtype=float)
        if zvec.size >1:
            ind = [slice(None)] * zvec.ndim
            ind[axis] = slice(0, 2)
            dz = np.diff(zvec[tuple(ind)], axis=axis)
        else:
            dz = 0
        r = np.abs(zvec + (dz*cellfrac - z0)) / np.cos(np.deg2rad(beam_angle))
        loss = 20 * np.log10(r) + 2 * self.alphabar(zvec, z0) * r
        return loss


def db_to_linear(db):
    """
    Convert log scale in db to a linear scale.
    """
    return 10**(db / 10)


def linear_to_db(a):
    """
    Convert an amplitude on a linear scale to log scale in db.
    """
    return 10 * np.log10(a)


def noise_floor(a, *, bottom_n_bins=6, func=np.mean, axis=-1):
    """
    Estimate the noise floor from the deepest ADCP amplitudes.

    Parameters
    ----------
    a : array_like
        Amplitude array in counts or db.

    bottom_n_bins : integer, optional
        Number of bins at the bottom from which the noise will be calculated.

    func : callable, optional
        Function like `np.mean` (default) or `np.min` that operates on the
        specified `axis` of an array, reducing the dimension of that `axis` to
        1, typically via a `keepdims=True` argument.

    axis : integer, optional
        Axis of `a` along which depth increases.  It defaults to `-1` to match
        the 1-D case, and the typical 2-D case for processed ADCP data, in
        which depth increases along the second axis.

    Returns
    -------
    noise : float array
        The estimated noise floor, with a shape broadcastable to `a`.
    """
    a = np.asarray(a)
    ind = [slice(None)] * a.ndim
    ind[axis] = slice(-bottom_n_bins, None)
    return func(a[tuple(ind)], axis=axis, keepdims=True)


def remove_noise(a, noise, *, minSNR=3):
    """
    Remove the estimated contribution of noise.

    Parameters
    ----------
    a : array or masked array
        Amplitude in db

    noise : array or masked array
        Noise floor in db.  Shape is broadcastable to `a`.

    minSNR : scalar, optional
        Signal-to-noise ratio below which the output will be masked.

    Returns
    -------
    a_masked : masked array
        Amplitude in db from `a`, corrected for estimated `noise`, and masked
        for low SNR.
    """
    am = np.ma.masked_less_equal(a, noise)
    am_minus = linear_to_db(db_to_linear(am) - db_to_linear(noise))
    return np.ma.masked_less(am_minus, minSNR)


def trim_bottom(a, *, axis=-1):
    """
    Mask out depths below which there are fewer than 3 unmasked values.

    Parameters
    ----------
    a : masked array
        Amplitude array to which editing has been applied with a mask.

    axis : integer, optional
        Axis of `a` along which depth increases.

    Returns
    -------
    a_trimmed : masked array
        Copy of `a` but with isolated points masked out at the end of the
        range.
    """
    nd = a.shape[axis]
    goodmask = ~np.ma.getmaskarray(a)
    ind = [slice(None)] * a.ndim
    ind[axis] = slice(None, -2)
    slidemask = goodmask[tuple(ind)]
    ind[axis] = slice(1, -1)
    slidemask &= goodmask[tuple(ind)]
    ind[axis] = slice(2, None)
    slidemask &= goodmask[tuple(ind)]
    ind = [np.newaxis] * a.ndim
    ind[axis] = slice(None)
    indices = np.arange(2, nd)[tuple(ind)] * slidemask
    ibottom = indices.max(axis = axis, keepdims=True)
    bottom_mask = np.arange(nd)[tuple(ind)] > ibottom
    return np.ma.array(a, mask=bottom_mask)

