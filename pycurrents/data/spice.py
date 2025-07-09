'''
Calculate spiciness according to Flament, 2002.

Progress in Oceanography
Volume 54, 2002, Pages 493-501.

A state variable for characterizing water masses and
their diffusive stability: spiciness

http://www.satlab.hawaii.edu/spice/

This code is adapted from spice.c and spice.m on the above site.

This is likely to be moved and/or consolidated with other
seawater code.

'''
import numpy as np
b = np.empty((6,5), dtype=float)

b[0, 0] = 0
b[0, 1] = 7.7442e-001
b[0, 2] = -5.85e-003
b[0, 3] = -9.84e-004
b[0, 4] = -2.06e-004

b[1, 0] = 5.1655e-002
b[1, 1] = 2.034e-003
b[1, 2] = -2.742e-004
b[1, 3] = -8.5e-006
b[1, 4] = 1.36e-005

b[2, 0] = 6.64783e-003
b[2, 1] = -2.4681e-004
b[2, 2] = -1.428e-005
b[2, 3] = 3.337e-005
b[2, 4] = 7.894e-006

b[3, 0] = -5.4023e-005
b[3, 1] = 7.326e-006
b[3, 2] = 7.0036e-006
b[3, 3] = -3.0412e-006
b[3, 4] = -1.0853e-006

b[4, 0] = 3.949e-007
b[4, 1] = -3.029e-008
b[4, 2] = -3.8209e-007
b[4, 3] = 1.0012e-007
b[4, 4] = 4.7133e-008

b[5, 0] = -6.36e-010
b[5, 1] = -1.309e-009
b[5, 2] = 6.048e-009
b[5, 3] = -1.1409e-009
b[5, 4] = -6.676e-010


def spice(t, s):
    t = np.asarray(t, dtype=np.float64)
    s = np.asarray(s, dtype=np.float64) - 35.0
    sp = 0.0
    T = np.ones_like(t)
    for i in range(6):
        S = np.ones_like(s)
        for j in range(5):
            sp += b[i,j] * T * S
            S *= s
        T *= t
    return sp

