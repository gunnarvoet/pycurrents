
import numpy as np
import numpy.ma as ma
import matplotlib.pyplot as plt

from pycurrents.num import Runstats

z = np.arange(48)
z.shape = (4,12)

zz = ma.masked_where(z > 42, z)
zzs = Runstats(zz, 3, axis=0)
print('data:')
print(zzs.data)
print('mean')
print(zzs.mean)
print('median')
print(zzs.median)
print('ngood')
print(zzs.ngood)

zzs = Runstats(zz, 3, axis=1)
print('data:')
print(zzs.data)
print('mean')
print(zzs.mean)
print('median')
print(zzs.median)
print('ngood')
print(zzs.ngood)

z = np.random.randn(50, 2)
x = np.linspace(0, 10, 50)
z[:,0] += 5 * np.cos(x)
z[:,1] += 5 * np.sin(x)
zs = Runstats(z, 5, axis=0)
zmf = zs.medfilt(1)

plt.subplot(1,1,1)
ll = plt.plot(x, z[:,0], x, zmf[:,0], x, zs.median[:,0], 'ro')
plt.setp(ll[0], lw=5)
plt.setp(ll[1], lw=2, color='orange')
plt.legend(('raw', 'medfilt', 'median'))
plt.show()


