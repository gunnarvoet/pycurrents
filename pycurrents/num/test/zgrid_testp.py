
import matplotlib.pyplot as plt
import numpy as np
from pycurrents.num.grid import zgrid

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

zmask = np.zeros(X.shape, dtype=np.double)
zmask[:4,:4] = 1#e100

zout = zgrid(zmask, Xx,
                                      Yy,
                                      Zz,
                                      origin=(0,0),
                                      deltas=((x[1]-x[0]), (y[1]-y[0])),
                                      biharmonic=0.5,
                                      interp=2,
                                      y_weight=0.5
                                      )

#print Zz
#print zout

zzout = np.ma.masked_where(zout > 1e34, zout)

plt.subplot(2,2,1)
plt.pcolormesh(X, Y, Z)
plt.title('original')
plt.subplot(2,2,2)
plt.pcolormesh(Xx, Yy, Zz)
plt.title('subsampled')
plt.subplot(2,2,3)
plt.pcolormesh(X, Y, zzout)
plt.title('interpolated')
plt.show()
