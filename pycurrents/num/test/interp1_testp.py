import numpy as np
import matplotlib.pyplot as plt
from pycurrents.num.grid import interp1

x = np.arange(0, 10, 0.2)[::-1]
y = np.sin(x)

xn = np.arange(-0.25, 6, 0.13)
yn = interp1(x, y, xn, masked=True)

fig, axs = plt.subplots(nrows=2, sharex=True, sharey=True)
ax = axs[0]
ax.plot(x, y, 'ro')
ax.plot(xn, yn, 'g+')

x2 = np.ma.array(x)
x2[(x2 > 2) & (x2 < 3)] = np.ma.masked
yn2 = interp1(x2, y, xn, masked=True, max_dx=0.3)

ax = axs[1]
ax.plot(x2, y, 'ro')
ax.plot(xn, yn2, 'g+')

plt.show()

