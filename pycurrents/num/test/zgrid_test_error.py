# manual test of error handling

import numpy as np
from pycurrents.num.grid import zgrid, regrid

x = np.linspace(0, 2*np.pi, 20)
y = np.linspace(0, 2*np.pi, 20)


X, Y = np.meshgrid(x, y)
Z = np.sin(X)*np.sin(3*Y)


Xstr = 0.01 #500 #0.002
X *= Xstr
x *= Xstr


Ystr = 1#0.01
Y *= Ystr
y *= Ystr

Xx = X[::2,::2]
Yy = Y[::2,::2]
Zz = Z[::2,::2]

zmask = np.ones(X.shape, dtype=np.double)
#zmask[:4,:4] = 1#e100

## Test zgrid directly, or the regrid interface.

if True:
    zout = zgrid(zmask, Xx,
                                      Yy,
                                      Zz,
                                      origin=(0,0),
                                      deltas=((x[1]-x[0]), (y[1]-y[0])),
                                      biharmonic=0.5,
                                      interp=2,
                                      y_weight=0.5
                                      )
else:
    rout = regrid(x, y, Z*np.nan, x, y)
