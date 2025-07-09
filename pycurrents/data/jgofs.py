"""
    Handle 'JGOFS' underway data format as provided on NBP and LMG
"""

import logging
import glob
import gzip
import numpy as np

from pycurrents import codas

_log = logging.getLogger()    # maybe use pycurrents helper later
logging.basicConfig()

## Note: starting in 2009, another field seems to have been added,
## so we need to find out what it is, and make the reading handle
## it when present.

names = ['dday', 'lat', 'lon', 'spd', 'hdop', 'hdg', 'cmg', 'PAR',
         'SST', 'SSC', 'SSS', 'depth', 'windspeed', 'wind_dir',
         'airT', 'relhum', 'baro', 'fluorometry', 'PSP', 'PIR']

dtrec = np.dtype({'names': names, 'formats': [np.float64]*20})
dti = np.dtype(np.uint16)
dtf = np.dtype(np.float64)


# The editing limits, maxvals and minvals, must have matching
# keys.  They could be condensed into a single dictionary.
# The most important is maxvals, because it catches the use
# of magic numbers like 999.99 that were used as flags in
# the earlier files; NAN was used later.

maxvals = dict(PAR=9000,
               lat=90,
               lon=180,
               spd=10,
               hdg=360,
               cmg=360,
               SST=35,
               SSS=40,
               SSC=20,
               depth=8000,
               windspeed=90,
               wind_dir=360,
               airT=40,
               relhum=120,
               baro=1050,
               fluorometry=900,  # guess: bad is probably 999.99
               PSP=9000,
               PIR=900,  # bad might be 9999.99, but 900 will do
               )

minvals = dict(PAR=0,
               lat=-90,
               lon=-180,
               spd=0,
               hdg=0,
               cmg=0,
               SST=-3,
               SSS=10,
               SSC=0,
               depth=0,
               windspeed=0,
               wind_dir=0,
               airT=-100,
               relhum=10,
               baro=900,
               fluorometry=0,
               PSP=1,
               PIR=0,
               )


class JGOFSFile:
    def __init__(self, fname, yearbase=None, masked=True):
        self.fname = fname
        self.yearbase = yearbase
        self._masked = masked
        self._load()             # sets self.array, self.recs

    def _load(self):
        '''
        Load a file, make two ndarray views: first as a 2-D array,
        second as a 1-D array of records.
        Gzipped or unzipped files are handled.
        If yearbase is not specified, it will be taken from the first record.
        '''
        dlist = []
        tlist = []
        vlist = []
        fname = self.fname
        if fname.endswith('gz'):
            f = gzip.open(fname)
        else:
            f = open(fname, mode='rb')
        count = 0
        for line in f:
            count += 1
            try:
                ## int conversion interprets leading 0 as octal;
                ## use float as a workaround
                d = np.fromstring(line[:8], dtype=dtf, sep='/')
                t = np.fromstring(line[9:17], dtype=dtf, sep=':')
                v = np.fromstring(line[18:], dtype=dtf, sep=' ')[:20]
                if len(v) < 20:
                    n = len(v)
                    v1 = np.empty((20,), float)
                    v1[:n] = v
                    v1[n:] = np.nan
                    v = v1
            except:
                _log.exception('reading line %d', count)
                continue  # Or bail out here?
            dlist.append(d)
            tlist.append(t)
            vlist.append(v)
        n = len(vlist)
        dt = np.empty((n, 6), dtype=dti)
        dtmp = np.array(dlist, dtype=dti)
        ttmp = np.array(tlist, dtype=dti)
        dt[:, :3] = dtmp[:, ::-1]
        dt[:, 3:] = ttmp
        dt[:, 0] += 2000
        if self.yearbase is None:
            self.yearbase = dt[0, 0]
        dday = codas.to_day(self.yearbase, dt)
        out = np.empty((n, 20), dtype=dtf)
        out[:, 0] = dday
        vtmp = np.array(vlist, dtype=dtf)
        out[:, 1:18] = vtmp[:, :17]
        out[:, 18:] = vtmp[:, 18:]

        for i, name in enumerate(names):
            if name not in maxvals:   # minvals must match maxvals
                continue
            col = out[:, i]
            np.putmask(col, (col > maxvals[name]) | (col < minvals[name]),
                       np.nan)

        if self._masked:
            out = np.ma.masked_invalid(out)

        self.array = out
        recs = out.view(dtype=dtrec)
        self.recs = recs.ravel()


def load(fname, yearbase=None, masked=True):
    """
    Return a record view of the data in a file.
    """
    return JGOFSFile(fname, yearbase=yearbase, masked=masked).recs


def load_list(flist, yearbase=None, masked=True):
    """
    Return a record view of the data in a list of files.
    """
    blist = []
    for fname in flist:
        jf = JGOFSFile(fname, yearbase=yearbase, masked=masked)
        yearbase = jf.yearbase
        blist.append(jf.array)
    if masked:
        out = np.ma.vstack(blist)
    else:
        out = np.vstack(blist)
    ii = np.argsort(out[:, 0])
    ret = out[ii].view(dtrec).ravel()
    ret.yearbase = yearbase
    return ret


def load_glob(fglob, yearbase=None, masked=True):
    """
    Return a structured array view of the data in a glob of files.

    The yearbase is attached as an attribute.
    """
    flist = glob.glob(fglob)
    return load_list(flist, yearbase=yearbase, masked=masked)


def txy_from_dir(dirname, yearbase, subsample=1):
    """
    Get a simple t,x,y array from all files in a directory.

    This was developed independently of everything above, and
    consequently duplicates quite a bit of code.  It needs
    to be rewritten and integrated properly.
    """
    filelist = glob.glob(dirname + '/*.dat')
    linelist = []
    for fname in filelist:
        with open(fname) as newreadf:
            morelines = newreadf.readlines()
        linelist.extend(morelines)
    if subsample > 1:
        linelist = linelist[::subsample]
    txy = np.empty((len(linelist), 3), dtype=float)
    ymdhms = np.empty((len(linelist), 6), dtype=int)
    for ii, line in enumerate(linelist):
        dmy, hms, slat, slon = line.split(None, 4)[:4]
        dmyhms = dmy.split('/') + hms.split(':')
        dd, mm, yy, hh, mi, ss = [int(s) for s in dmyhms]
        ymdhms[ii] = yy + 2000, mm, dd, hh, mi, ss
        txy[ii, 1] = float(slon)
        txy[ii, 2] = float(slat)
    txy[:, 0] = codas.to_day(yearbase, ymdhms)
    ii = np.argsort(txy[:, 0])
    return txy[ii]
