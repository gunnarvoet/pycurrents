"""
Various routines for seawater calculations.

Some are very old, typically translated from our
old matlab code, which is in turn translated from
FORTRAN; periodic additions and updates may be made.

A new addition is gamma_a, the rational function approximation
to gamma_n.

Another is a calculation of viscosity based on
Sharkawy, M.H., J. H. Lienhard V, and S.M. Zubair (2010)
"Thermophysical properties of seawater: a review of existing
correlations and data", Desalination and Water Treatment,
16, 354-380.  doi no. 10.5004/dwt.2010.1079.

Most of the core calculations are now done in a cython extension
module.  This improves the speed and reduces memory usage, but might
not actually be worth the extra complexity.

A decorator is used on the main functions to handle broadcasting
and masks.  This enables the core routines to use simple loops over
1-D arrays.
"""
import numpy as np
from pycurrents.data import _sw
import functools

from pycurrents.num import bl_filt, Blackman_filter

class match_args_return_n:
    """
    Function decorator to homogenize input arguments and to
    make the output match the original input with respect to
    scalar versus array, and masked versus ndarray.

    The function to be decorated must have one or more outputs
    that are all the same dimensions as the broadcast inputs.
    """
    def __init__(self, nout=1):
        """
        *nout* is the number of output arguments
        """
        self.nout = nout

    def __call__(self, func):
        """
        This is the actual decorator, taking the function
        to be decorated as its argument.
        """
        @functools.wraps(func)
        def newfunc(*args, **kw):
            p = kw.get('p', None)
            args = list(args)
            if p is not None:
                args.append(p)
            P = kw.get('P', None)
            if P is not None:
                args.append(P)
            self.array = np.any([hasattr(a, '__iter__') for a in args])

            self.masked = False
            for i, arg in enumerate(args):
                arg = np.asanyarray(arg, dtype=float, order='C')
                if np.ma.isMA(arg):
                    arg = arg.filled(np.nan)
                    self.masked = True
                args[i] = np.atleast_1d(arg)
            newargs = np.broadcast_arrays(*args)
            self.shape = newargs[0].shape
            newargs = [arg.ravel() for arg in newargs]
            if P is not None:
                kw['P'] = newargs.pop()
            if p is not None:
                kw['p'] = newargs.pop()
            rets = func(*newargs, **kw)
            if self.nout == 1:
                rets = [rets]
            else:
                rets = list(rets)
            for i, ret in enumerate(rets):
                ret.shape = self.shape
                if self.masked:
                    ret = np.ma.masked_invalid(ret, np.nan)
                if not self.array:
                    ret = ret[0]
                rets[i] = ret
            if self.nout == 1:
                return rets[0]
            else:
                return tuple(rets)
        newfunc.__wrapped__ = func
        return newfunc


def to_IPTS68(T):
    return T * 1.00024

@match_args_return_n(1)
def atg(S, T, P):
    """
    ADIABATIC TEMPERATURE GRADIENT DEG C PER DECIBAR
    REF: BRYDEN,H.,1973,DEEP-SEA RES.,20,401-408

    UNITS:
          PRESSURE        P        DECIBARS
          TEMPERATURE     T        DEG CELSIUS (IPTS-68)
          SALINITY        S        (IPSS-78)
          ADIABATIC       ATG      DEG. C/DECIBAR

    CHECKVALUE: ATG=3.255976E-4 C/DBAR FOR S=40 (IPSS-78),
    T=40 DEG C,P0=10000 DECIBARS
    """
    return _sw._atg(S, T, P)

@match_args_return_n(1)
def theta(S,T,P,PR):
    """
    Potential temperature

    to compute local potential temperature at *PR*
    using Bryden 1973 polynomial for adiabatic lapse rate
    and Runge-Kutta 4-th order integration algorithm.
    ref: Bryden,H., 1973, Deep-Sea Res., 20, 401-408
    Fofonoff, N., 1977, Deep-Sea Res., 24, 489-491

    units:
          pressure        P        decibars
          temperature     T        deg celsius (ipts-68)
          salinity        S        (ipss-78)
          reference prs   PR       decibars
          potential temp. theta    deg celsius

    checkvalue: theta= 36.89073 c,s=40 (ipss-78),t0=40 deg c,
    p0=10000 decibars,pr=0 decibars

    """
    return _sw._theta(S, T, P, PR)

@match_args_return_n(2)
def svansig(S, T, P):
    """
    SVAN, SIGMA = _svan(S,T,P)

    SPECIFIC VOLUME ANOMALY (STERIC ANOMALY) BASED ON 1980 EQUATION
    OF STATE FOR SEAWATER AND 1978 PRACTICAL SALINITY SCALE.
    REFERENCES
    MILLERO, ET AL (1980) DEEP-SEA RES.,27A,255-264
    MILLERO AND POISSON 1981,DEEP-SEA RES.,28A PP 625-629.
    BOTH ABOVE REFERENCES ARE ALSO FOUND IN UNESCO REPORT 38 (1981)
    ***
    UNITS:
          PRESSURE        P        DECIBARS
          TEMPERATURE     T        DEG CELSIUS (IPTS-68)
          SALINITY        S        (IPSS-78)
          SPEC. VOL. ANA. SVAN     M**3/KG *1.0E-8
          DENSITY ANA.    SIGMA    KG/M**3
    ***
    CHECK VALUE: SVAN=981.3021 E-8 M**3/KG.  FOR S = 40 (IPSS-78) ,
    T = 40 DEG C, P= 10000 DECIBARS.
    CHECK VALUE: SIGMA = 59.82037  KG/M**3 FOR S = 40 (IPSS-78) ,
    T = 40 DEG C, P= 10000 DECIBARS.
    """
    return _sw._svan(S, T, P)

def sigma(S, T, P):
    """
    Returns density anomaly.  See *svansig* for details.
    """
    return svansig(S, T, P)[1]

def svan(S, T, P):
    """
    Returns specific volume anomaly in centiliters per ton.
    See *svansig* for details.
    """
    return svansig(S, T, P)[0]

def sigma_theta(S, T, P, PR=0):
    """
    Return potential density anomaly relative to pressure *PR*,
    which defaults to 0.
    """
    th = theta(S, T, P, PR)
    return sigma(S, th, PR)

@match_args_return_n(1)
def bvfsq(S, T, P, lat=30, half_width=None, T_is_potential=False):
    """
    If half_width is not None, it is the Blackman filter
    half width for smoothing the N**2 estimates.

    If you have potential temperature referenced to the surface as
    your T input, instead of in-situ temperature, use the
    kwarg T_is_potential=True.  Note: this is simply using the
    potential temperature function in reverse to convert to in-situ
    temperature, so use it only if you don't already have in-situ
    temperature.

    """
    out = np.ma.zeros(S.shape, np.float64)
    out[:] = np.ma.masked
    if T_is_potential:
        # reverse the potential temperature calculation.
        T = theta(S, T, 0, P)
    upper = sigma_theta(S[...,:-2], T[...,:-2], P[...,:-2], P[...,1:-1])
    lower = sigma_theta(S[...,2:], T[...,2:], P[...,2:], P[...,1:-1])
    z = - depth(P, lat=lat)
    dz = z[...,2:] - z[...,:-2]
    out[...,1:-1] = (lower - upper) / dz
    out *= (-gravity(lat) / (sigma(S, T, P) + 1000))
    if half_width is not None:
        if S.ndim > 2:
            raise ValueError("bl_filt only handles 1-D and 2-D")
        out, _ = bl_filt(out, half_width, axis=1, min_fraction=0.5)
    return out

###@match_args_return_n(1)
def bvfsq2(S, T, P, lat=30, half_width=None, T_is_potential=False,
           axis=-1):
    """
    Calculate N**2 using simple differences.

    S and T must have the same shape; P must be 1-D, with length equal
    to that of the specified axis of S and T.

    If half_width is not None, it is the Blackman filter
    half width for smoothing the N**2 estimates.

    axis is the depth axis.

    If you have potential temperature referenced to the surface as
    your T input, instead of in-situ temperature, use the
    kwarg T_is_potential=True.  Note: this is simply using the
    potential temperature function in reverse to convert to in-situ
    temperature, so use it only if you don't already have in-situ
    temperature.

    """
    outshape = list(S.shape)
    outshape[axis] -= 1
    out = np.ma.masked_all(outshape, np.float64)

    P_mid = np.diff(P)
    Pbroad = [None] * S.ndim
    Pbroad[axis] = slice(None)
    P_nd = P[tuple(Pbroad)]
    P_mid_nd = P_mid[tuple(Pbroad)]

    sel_base = [slice(None)] * S.ndim
    sel_p = sel_base.copy()
    sel_m = sel_base.copy()
    sel_p[axis] = slice(-1)
    sel_m[axis] = slice(1, None)

    if T_is_potential:
        # reverse the potential temperature calculation.
        T = theta(S, T, 0, P_nd)
    upper = sigma_theta(S[sel_p], T[sel_p], P_nd[sel_p], P_mid_nd)
    lower = sigma_theta(S[sel_m], T[sel_m], P_nd[sel_m], P_mid_nd)
    dz = - np.diff(depth(P, lat=lat))

    out = (lower - upper) / dz
    out *= (-gravity(lat) / (sigma(S, T, P_nd)[sel_p] + 1000))
    if half_width is not None:
        out, _ = Blackman_filter(out, half_width, axis=1, min_fraction=0.5)

    return out


@match_args_return_n(1)
def gamma_a(s, t, p=None):
    """
    Rational function approximation of neutral density.

    The arguments are Salinity, Temperature, and Pressure.  The
    approximation based on potential temperature is used.

    If the pressure argument is absent, t will be interpreted as
    potential temperature.

    From the Table 1 caption (after translating to ascii):
    "A check value is gamma_a(35, 20) = 1024.59416751197 kg m^-3."

    From McDougall & Jackett, 2005, "The material derivative of neutral
    density", J. Marine Res., 63, 159-185.

    Gamma_a is considered a modest improvement over sigma-2, still
    quite inferior to gamma_n, but much faster to calculate.
    """
    from pycurrents.data.seawater import theta

    if p is None:
        th = t
    else:
        th = theta(s, t, p, 0)

    return _sw._gamma_a(s, th)

def press(z):
    """
    crude pressure estimate as function of depth only

    This computes pressure in decibars, given the depth in meters.           *
    Formula is from the GEOSECS operation group (See computer routine
    listings in the El Nino Watch Data Reports).

    """
    z = np.asanyarray(z)
    if np.ma.isMA(z):
        sqrt = np.ma.sqrt
    else:
        sqrt = np.sqrt
    C1=  2.398599584e05
    C2=  5.753279964e10
    C3=  4.833657881e05
    ARG = C2 -  C3 * z
    p = C1 - sqrt( ARG )
    return p

def depth2(p, lat):
    """
    Less crude depth estimate as a function of pressure and latitude.

    The formula is from Saunders, 1981.

    Saunders, P. M., 1981: Practical conversion of pressure to
    depth.  J. Phys. Oceanogr. 11, 573-574.
    """
    phi = np.deg2rad(lat)
    c1 = (5.92 + 5.25 * np.sin(phi) ** 2) * 1e-3
    c2 = 2.21e-6
    return (1 - c1) * p - c2 * p**2

def press2(z, lat):
    """
    Inverse of depth2.
    """
    phi = np.deg2rad(lat)
    c1 = (5.92 + 5.25 * np.sin(phi) ** 2) * 1e-3
    c2 = 2.21e-6
    a = 1 - c1
    cc = z**2 / a**2
    bb = 2 * z / a - a / c2
    eps = -0.5 * (bb + np.sqrt(bb**2 - 4 * cc))
    return z/a + eps

def gravity(lat, P=0):
    """
    GRAVITY VARIATION WITH LATITUDE: ANON (1970) BULLETIN GEODESIQUE
    """
    lat = np.asanyarray(lat)
    X = np.sin(np.deg2rad(lat))**2
    GR = 9.780318*(1.0+(5.2788E-3+2.36E-5*X)*X) + 1.092E-6*P
    return GR


def depth(P, lat=30):
    """
    DEPTH IN METERS FROM PRESSURE IN DECIBARS USING
    SAUNDERS AND FOFONOFF'S METHOD.
    DEEP-SEA RES., 1976,23,109-111.
    FORMULA REFITTED FOR 1980 EQUATION OF STATE
    ***
    UNITS:
          PRESSURE        P        DECIBARS
          LATITUDE        LAT      DEGREES
          DEPTH           DEPTH    METERS
    ***
    CHECKVALUE: DEPTH = 9712.653 M FOR P=10000 DECIBARS, LATITUDE=30 DEG
        ABOVE FOR STANDARD OCEAN: T=0 DEG. CELSUIS ; S=35 (IPSS-78)
    ***
    """
    P = np.asanyarray(P)
    GR = gravity(lat, P)
    DEPTH = (((-1.82E-15*P+2.279E-10)*P-2.2512E-5)*P+9.72659)*P
    d = DEPTH / GR
    return d


"""
Attempting to improve on press() by analytically calculating
an inverse to the polynomial used by depth() yields poorer
accuracy than using the completely different formulation in
press()

a = -1.82E-15
b = 2.279E-10
c = -2.2512E-5
d = 9.72659

h = 1.0/d
g = -c/d**3
f = 2 * c**2 / d**5
e = -6 * c**3 / d**7
def press2(D, lat=30):
    D = np.asanyarray(D)
    GR = gravity(lat, D) # should be P, but close enough
    D = D * GR
    P = (((e * D + f) * D + g) * D + h) * D
    return P
"""




def salinity(C, T, P):
    """
    PSS salinity from the IEEE Journal of Oceanic Engineering,
    OE-5, No. 1, January 1980, p. 14, as reproduced in Seabird
    application note #14.

    Conductivity is in Siemens per meter, consistent with present
    Seabird practice.

    T is IPTS68

    """
    A1 = 2.070e-5
    A2 = -6.370e-10
    A3 = 3.989e-15

    B1 = 3.426e-2
    B2 = 4.464e-4
    B3 = 4.215e-1
    B4 = -3.107e-3

    c0 = 6.766097e-1
    c1 = 2.00564e-2
    c2 = 1.104259e-4
    c3 = -6.9698e-7
    c4 = 1.0031e-9

    a0 = 0.0080
    a1 = -0.1692
    a2 = 25.3851
    a3 = 14.0941
    a4 = -7.0261
    a5 = 2.7081

    b0 = 0.0005
    b1 = -0.0056
    b2 = -0.0066
    b3 = -0.0375
    b4 = 0.0636
    b5 = -0.0144

    k = 0.0162

    R = C / 4.2914    # conductivity ratio

    Rpnum = np.polyval([A3, A2, A1], P) * P
    Rpdenom = np.polyval([B2, B1, 1], T) + B3 * R + B4 * R * T
    Rp = 1 + Rpnum / Rpdenom

    rT = np.polyval([c4, c3, c2, c1, c0], T)

    RT = R / (Rp * rT)

    sq_RT = np.sqrt(RT)

    Sa = np.polyval([a5, a4, a3, a2, a1, a0], sq_RT)
    Sb = np.polyval([b5, b4, b3, b2, b1, b0], sq_RT)
    Tfac = (T - 15) / (1 + k * (T - 15))

    S = Sa + Tfac * Sb

    return S

def mu_fresh(T):
    """
    Freshwater dynamic viscosity based on equation 23 in
    Sharkawy et al., 2010.
    """
    mu = 4.2844e-5 + 1.0 / (0.157 * (T + 64.993 ) ** 2 - 91.296)
    return mu

def mu_salt(S, T):
    """
    Saltwater dynamic viscosity based on equation 22 in
    Sharkawy et al., 2010.
    """
    S /= 1000.0
    A = np.polyval([-9.52e-5, 1.998e-2, 1.541], T)
    B = np.polyval([4.724e-4, -7.561e-2, 7.974], T)
    mu = mu_fresh(T) * (1 + A * S + B * S **2)
    return mu

def nu(S, T, P=0):
    """
    kinematic viscosity based on dynamic viscosity from
    Sharkawy et al., 2010.
    """
    return mu_salt(S, T) / (1000 + sigma(S, T, P))

def nu_poly(S=35, degree=3):
    """
    Returns a polynomial approximation to nu at P=0,
    for the given salinity and of the given order, for the
    temperature range from 0-30.
    """
    T = np.linspace(0, 30, 100)
    yy = nu(S, T, 0)
    return np.polyfit(T, yy, degree)
