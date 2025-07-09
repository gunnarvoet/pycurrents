#!/usr/bin/env python
"""
Simple script to generate .raw.log.bin files from .raw.log files.

    make_rawlogbin.py <list of .raw.log files>

Output will be in the same directory as the .raw.log files.

"""


import os
import sys

import numpy as np

from pycurrents.file.binfile_n import binfile_n

for fname in sys.argv[1:]:

    print(fname)
    dest = os.path.join(fname + '.bin')
    if os.path.exists(dest):
        print('output file %s exists; skipping' % dest)
        continue

    columns = ['unix_dday',
               'offset',
               'n_bytes',
               'pingnum',
               'instrument_dday',
               'monotonic_dday']

    dat = np.loadtxt(fname)

    if dat.shape[1] == 5:
        newdat = np.zeros((dat.shape[0], 6), dtype=float)
        newdat[:, :5] = dat
        # Fake monotonic time: use instrument time instead.
        t = dat[:, -1]
        if (np.diff(t) <= 0).any():
            raise RuntimeError('Instrument time is not monotonic;'
                               ' cannot use it as monotonic time substitute.')
        newdat[:, 5] = t
        dat = newdat
    elif dat.shape[1] == 7:  # after adding support for $PYRTM, May 2017
        columns.append('yearbase')

    bf = binfile_n(dest, columns=columns, mode='w', name='ser_bin_log')
    bf.write(dat)
    bf.close()
    print('wrote %s' % dest)
