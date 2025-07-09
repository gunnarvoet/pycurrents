"""
The type of calculation involved in the equation of state
generates many temporary arrays if done in numpy.  Here we
use cython to sweep through the input arrays in a single pass.
The speed-up tends to be a factor of 2-4 or so.  The original
motivation was that I was running out of memory when trying
to do calculations on TSG data; but it now seems that something
else, still unidentified, was causing that problem, so
moving these calculations to cython was not really necessary.

"""

cimport cython
from libc.math cimport (fabs, sqrt)

import numpy as np
cimport numpy as np

cdef double _atg_scalar(double S, double T, double P):
    cdef double DS, a

    DS = S - 35.0
    a = ((((-2.1687E-16*T+1.8676E-14)*T-4.6206E-13)*P
          +((2.7759E-12*T-1.1351E-10)*DS+((-5.4481E-14*T
          +8.733E-12)*T-6.7795E-10)*T+1.8741E-8))*P
          +(-4.2393E-8*T+1.8932E-6)*DS
          +((6.6228E-10*T-6.836E-8)*T+8.5258E-6)*T+3.5803E-5)

    return a


@cython.boundscheck(False)
def _atg(np.ndarray[np.float64_t, ndim=1] S,
        np.ndarray[np.float64_t, ndim=1] T,
        np.ndarray[np.float64_t, ndim=1] P):
    cdef unsigned int i, n
    cdef np.ndarray[np.float64_t, ndim=1] out
    n = S.shape[0]
    out = np.empty((n,), dtype=np.float64)

    for i in range(n):
        out[i] = _atg_scalar(S[i], T[i], P[i])

    return out



cdef double _theta_scalar(double S, double T, double P, double PR):
    cdef double H, XK, Q, th

    H = PR - P
    XK = H * _atg_scalar(S,T,P)
    T = T + 0.5*XK
    Q = XK
    P = P + 0.5*H
    XK = H*_atg_scalar(S,T,P)
    T = T + 0.29289322*(XK-Q)
    Q = 0.58578644*XK + 0.121320344*Q
    XK = H*_atg_scalar(S,T,P)
    T = T + 1.707106781*(XK-Q)
    Q = 3.414213562*XK - 4.121320344*Q
    P = P + 0.5*H
    XK = H*_atg_scalar(S,T,P)
    th = T + (XK-2.0*Q)/6.0
    return th

@cython.boundscheck(False)
def _theta(np.ndarray[np.float64_t, ndim=1] S,
        np.ndarray[np.float64_t, ndim=1] T,
        np.ndarray[np.float64_t, ndim=1] P,
        np.ndarray[np.float64_t, ndim=1] PR):
    cdef unsigned int i, n
    cdef np.ndarray[np.float64_t, ndim=1] out
    n = S.shape[0]
    out = np.empty((n,), dtype=np.float64)

    for i in range(n):
        out[i] = _theta_scalar(S[i], T[i], P[i], PR[i])

    return out



cdef void _svan_scalar(double S, double T, double P, double *sv, double *sig):
    # Minor inefficiency in leaving these inside here...
    cdef double R3500 = 1028.1063
    cdef double R4 = 4.8314e-4
    cdef double DR350 = 28.106331

    cdef double SR, R1, R2, R3, SIG, V350P, SVA, SIGMA, SVAN,
    cdef double A, B, C, D, AW, BW, A1, B1, KW, K0, DK, K35, GAM, PK,
    cdef double DR35P, DVAN

    # R4 IS REFERED TO AS  C  IN MILLERO AND POISSON 1981
    # CONVERT PRESSURE TO BARS AND TAKE SQUARE ROOT SALINITY.
    P /= 10.0
    SR = sqrt(fabs(S))  # Odd; should never have negative S anyway.

    # PURE WATER DENSITY AT ATMOSPHERIC PRESSURE
    #   BIGG P.H.,(1967) BR. J. APPLIED PHYSICS 8 PP 521-537.

    R1 = (((((6.536332E-9*T-1.120083E-6)*T+1.001685E-4)*T
                                  - 9.095290E-3)*T+6.793952E-2)*T-28.263737)
    # SEAWATER DENSITY ATM PRESS. COEFFICIENTS INVOLVING SALINITY
    #  R2 = A   IN NOTATION OF MILLERO AND POISSON 1981
    R2 = (((5.3875E-9*T-8.2467E-7)*T+7.6438E-5)*T-4.0899E-3)*T +8.24493E-1

    # R3 = B  IN NOTATION OF MILLERO AND POISSON 1981
    R3 = (-1.6546E-6*T+1.0227E-4)*T-5.72466E-3

    # INTERNATIONAL ONE-ATMOSPHERE EQUATION OF STATE OF SEAWATER
    SIG = (R4 * S + R3 * SR + R2) * S + R1

    # SPECIFIC VOLUME AT ATMOSPHERIC PRESSURE
    V350P = 1.0 / R3500
    SVA = -SIG * V350P / (R3500+SIG)

    if P == 0.0:
        SIGMA = SIG+DR350

        # SCALE SPECIFIC VOL. ANAMOLY TO NORMALLY REPORTED UNITS
        SVAN = SVA * 1.0E+8
        sv[0] = SVAN
        sig[0] = SIGMA
        return


    #******  NEW HIGH PRESSURE EQUATION OF STATE FOR SEAWATER ********
    #***
    #       MILLERO, ET AL , 1980 DSR 27A, PP 255-264
    #              CONSTANT NOTATION FOLLOWS ARTICLE

    #COMPUTE COMPRESSION TERMS
    E = (9.1697E-10*T+2.0816E-8)*T-9.9348E-7
    BW = (5.2787E-8*T-6.12293E-6)*T+3.47718E-5
    B = BW + E*S

    D = 1.91075E-4
    C = (-1.6078E-6*T-1.0981E-5)*T+2.2838E-3
    AW = ((-5.77905E-7*T+1.16092E-4)*T+1.43713E-3)*T-0.1194975
    A = (D*SR + C)*S + AW

    B1 = (-5.3009E-4*T+1.6483E-2)*T+7.944E-2
    A1 = ((-6.1670E-5*T+1.09987E-2)*T-0.603459)*T+54.6746
    KW = (((-5.155288E-5*T+1.360477E-2)*T-2.327105)*T + 148.4206)*T-1930.06
    K0 = (B1*SR + A1)*S + KW


    # EVALUATE PRESSURE POLYNOMIAL

    #   K EQUALS THE SECANT BULK MODULUS OF SEAWATER
    #   DK=K(S,T,P)-K(35,0,P)
    #   K35=K(35,0,P)

    DK = (B*P + A)*P + K0
    K35  = (5.03217E-5*P+3.359406)*P+21582.27
    GAM = P / K35
    PK = 1.0 - GAM
    SVA = SVA * PK + (V350P+SVA)*P*DK/(K35*(K35+DK))


    # SCALE SPECIFIC VOL. ANAMOLY TO NORMALLY REPORTED UNITS
    SVAN = SVA * 1.0E+8
    V350P = V350P*PK

    #  COMPUTE DENSITY ANAMOLY WITH RESPECT TO 1000.0 KG/M**3
    #   1) DR350: DENSITY ANAMOLY AT 35 (IPSS-78), 0 DEG. C AND 0 DECIBARS
    #   2) DR35P: DENSITY ANAMOLY 35 (IPSS-78), 0 DEG. C ,  PRES. VARIATION
    #   3) DVAN : DENSITY ANAMOLY VARIATIONS INVOLVING SPECFIC VOL. ANAMOLY

    DR35P = GAM / V350P
    DVAN = SVA / (V350P*(V350P+SVA))
    SIGMA = DR350+DR35P-DVAN
    sv[0] = SVAN
    sig[0] = SIGMA
    return

@cython.boundscheck(False)
def _svan(np.ndarray[np.float64_t, ndim=1] S,
        np.ndarray[np.float64_t, ndim=1] T,
        np.ndarray[np.float64_t, ndim=1] P):
    cdef unsigned int i, n
    cdef np.ndarray[np.float64_t, ndim=1] sv, sig
    n = S.shape[0]
    sv = np.empty((n,), dtype=np.float64)
    sig = np.empty((n,), dtype=np.float64)

    for i in range(n):
        _svan_scalar(S[i], T[i], P[i], &sv[i], &sig[i])

    return sv, sig

cdef double _gamma_a_scalar(double s, double th):

    cdef double pn, pd
    # Calculating and saving the integer powers cuts
    # the runtime by a factor of 10.
    cdef double th2, th3, th4, s2, sth  #, s1p5
    th2 = th*th
    th3 = th2*th
    th4 = th3*th
    sth = s * th
    s2 = s*s
    # Strangely, it runs fastest with s**1.5 in place in
    # the pd expression; any attempt to precalculate it
    # slows it down by 20%.
    #s1p5 = s**1.5# sqrt(s) * s
    pn = (  1.0023063688892480e3
          + 2.2280832068441331e-1 * th
          + 8.1157118782170051e-2 * th2
          - 4.3159255086706703e-4 * th3
          - 1.0304537539692924e-4 * s
          - 3.1710675488863952e-3 * sth
          - 1.7052298331414675e-7 * s2)

    pd = (  1.0
          + 4.3907692647825900e-5 * th
          + 7.8717799560577725e-5 * th2
          - 1.6212552470310961e-7 * th3
          - 2.3850178558212048e-9 * th4
          - 5.1268124398160734e-4 * s
          + 6.0399864718597388e-6 * sth
          - 2.2744455733317707e-9 * s * th3
          - 3.6138532339703262e-5 * s**1.5
          - 1.3409379420216683e-9 * s**1.5 * th2)

    return pn/pd

@cython.boundscheck(False)
def _gamma_a(np.ndarray[np.float64_t, ndim=1] S,
        np.ndarray[np.float64_t, ndim=1] T):
    cdef unsigned int i, n
    cdef np.ndarray[np.float64_t, ndim=1] ga
    n = S.shape[0]
    ga = np.empty((n,), dtype=np.float64)

    for i in range(n):
        ga[i] = _gamma_a_scalar(S[i], T[i])

    return ga


