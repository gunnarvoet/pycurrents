#!/usr/bin/env python

"""
    Time range selector widget for picking time ranges corresponding
    to latitude or longitude sections, etc.

    Data and selections are managed with an instance of the
    RangeSet class that is independent of the TxySelector widget.

    Other usage: filename should have columns of time, x, y

        txyselect.py filename

    Without any arguments, dummy data are used.


"""

import sys

import numpy as np

from pycurrents.plot.txyselect import test


if __name__ == '__main__':
    if '--help' in sys.argv:
        print(__doc__)
        sys.exit()

    if len(sys.argv) == 1:
        t = np.arange(0.0, 10.0, 300.0/86400)
        x = -120.0 + np.sin(2*np.pi*t/10)
        y = 20.0 + np.exp(-t*3.)*np.cos(3*np.pi*t/10)
        selections = [[0.1, 1.15], [2, 4.4]]
    else:
        t,x,y = np.loadtxt(sys.argv[1], unpack=True)
        selections=None

    rs = test(t,x,y,selections)
    print('final selections as time ranges:\n')
    for r in rs.ranges:
        print(r)
    print('\nfinal selections as slices:\n')
    for s in rs.slices:
        print(s)
