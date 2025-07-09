"""
Tools for working with output from the Hallberg Isopycnal Model, the
original C version.
"""

import os
import glob
import re

from netCDF4 import Dataset, MFDataset


pat = r'(\D+)(\d+)\.(\w+)(.*)'
fname_re = re.compile(pat)

def filenametime(fname):
    head, tail = os.path.split(fname)
    prefix, t_int, t_dec, tail = fname_re.match(tail).groups()
    time = '.'.join([t_int, t_dec])
    return float(time)

def file_times(dir='./', prefix='avfld'):
    fnames = glob.glob(os.path.join(dir, prefix + "*.nc"))
    fnames = sorted(fnames, key=filenametime)
    out = []
    for fname in fnames:
        nf = Dataset(fname)
        t = nf.variables['Time']
        out.append((fname, t[0], t[-1]))
        nf.close()
    return out


class Output:
    def __init__(self, dir="./", prefix="avfld"):
        self._prefix = prefix
        fnames = glob.glob(os.path.join(dir, prefix + "*.nc"))
        self.fnames = sorted(fnames, key=self.filetime)
        self.mfd = MFDataset(self.fnames)
        for key, item in self.mfd.variables.items():
            if item.ndim == 1:
                item = item[:]
            setattr(self, key, item)

    def filetime(self, fname):
        head, tail = os.path.split(fname)
        parts = tail[len(self._prefix):].split('.')
        time = '.'.join(parts[:2])
        return float(time)
