'''
'''
import os
import numpy as np
from pycurrents.adcp.uhdasfile import parse_filename
import pycurrents.system.pathops as pathops
from pycurrents.codas import to_day, to_date
from pycurrents.num import rangeslice



class FileParts:
    """
    Parse a UHDAS filename or list of filenames from a directory.
    A glob string can also be used.  Files must be one of the
    following types:

        ADCP raw file::

            /home/data/ km1011/ raw/ os38/ km2010_184_50400.raw
                 1        2      3    4    6   7   8    9    11

        other raw file::

            /home/data/ km1011/ raw/ posmv/ km2010_184_50400.pmv
                 1        2      3      5    6   7   8    9   11


        rbin file::

            /home/data/ km1011/ rbin/ posmv/ km2010_184_50400.gps.rbin
                 1        2      3      5    6   7   8    9   10   11

        gbin file::

            /home/data/ km1011/ gbin/ os38/ posmv/ km2010_184_50400.gps.gbin
                 1        2      3     4      5    6   7   8    9   10   11

    The fields (instance attributes) are named:
        1 path_to_cruise
        2 cruisename
        3 rdir
        4 adcpdir
        5 instdir
        6 shipabbrev
        7 year
        8 day
        9 seconds
        10 message
        11 suffix

    When a given field is absent from a message type, it's attribute
    is an empty string. To show the fields::

        fp = FileParts('km2010_184_50400.gps.gbin')
        print fp

    If a file is gzipped and has the '.gz' extension, that extension
    will be ignored.  Note that a glob intended to include
    gzipped and non-zipped files will typically end in '*'.

    Attributes:
        + dday: ndarray of decimal days corresponding to filename times
        + date: ndarray, Nx6, of dates as returned by
          :func:`pycurrents.codas.to_date`

    Methods:
        + :meth:`table`

    """
    def __init__(self, fnames, yearbase=None):
        filelist = pathops.make_filelist(fnames)
        fname = filelist[0]
        self.filelist = filelist
        self.names = []
        self.basenames = []
        for f in filelist:
            p, n = os.path.split(f)
            self.names.append(n)
            self.basenames.append(n.split('.')[0])

        #initialize
        self.path_to_cruise = ''
        self.cruisename = ''
        self.rdir = ''
        self.instdir = ''
        self.adcpdir = ''

        parts = []
        p0 = os.path.abspath(fname)

        bailout = 100
        count = 0
        while True:
            p0, p1 = os.path.split(p0)
            count += 1
            if p1 == '' or count > bailout:
                if p0:
                    parts.insert(0, p0)
                break
            else:
                parts.insert(0,p1)
        if count > bailout:
            raise RuntimeError('too many path elements in %s' % (fname))

        fname = parts[-1]
        base, ext = os.path.splitext(fname)
        if ext == '.gz':
            base, ext = os.path.splitext(base)
        self.suffix = ext[1:]
        if ext in ['.raw', '.rbin', '.gbin']:
            base, ext2 = os.path.splitext(base)
            self.message = ext2[1:]
        (self.shipabbrev, self.year,
                self.day, self.seconds) = parse_filename(base)
        if yearbase is None:
            self.yearbase = self.year
        else:
            self.yearbase = yearbase


        try:
            if ext == '.raw':
                self.adcpdir = parts[-2]
            else:
                self.instdir = parts[-2]
            ofs = 0
            if ext == '.gbin':
                self.adcpdir = parts[-3]
                ofs = -1
            self.rdir = parts[-3 + ofs]
            self.cruisename = parts[-4 + ofs]
            self.path_to_cruise = os.path.join(*parts[:(-4+ofs)])
        except IndexError:
            pass

        self._dday = None
        self._date = None

    def __str__(self):
        lines = [
          'path_to_cruise = %s' % self.path_to_cruise,
          'cruisename     = %s' % self.cruisename ,
          'rdir           = %s' % self.rdir       ,
          'instdir        = %s' % self.instdir    ,
          'adcpdir        = %s' % self.adcpdir    ,
          'shipabbrev     = %s' % self.shipabbrev ,
          'year           = %s' % self.year       ,
          'day            = %s' % self.day        ,
          'seconds        = %s' % self.seconds    ,
          'message        = %s' % self.message    ,
          'suffix         = %s' % self.suffix,
          ]
        return '\n'.join(lines) + '\n'


    def get_dday(self):
        if self._dday is None:
            nfiles = len(self.filelist)              # here and in CODAS:
            date = np.zeros((nfiles, 6), np.uint16) # maybe change to int16
            for i, f in enumerate(self.filelist):
                sa, yr, d, s = parse_filename(os.path.split(f)[1])
                date[i] = to_date(yr, d + s / 86400.0)
            self._dday = to_day(self.yearbase, date)
            self._date = date
        return self._dday
    dday = property(get_dday)

    def get_date(self):
        if self._date is None:
            self.get_dday()
        return self._date
    date = property(get_date)

    def subslice(self, *args):
        """
        see subset
        """
        sl = rangeslice(self.dday, *args)
        if sl.start > 0:
            sl = slice(sl.start-1, sl.stop)
        return sl

    def subset(self, *args):
        """
        Given start and end decimal days, or any other range specification
        accepted by :func:`pycurrents.num.nptools.rangeslice`,
        return the list of files
        that will contain that time range, based on the file names.

        There is no guarantee that the entire time range requested will
        be included, and no warning when it is not.
        """
        return self.filelist[self.subslice(*args)]

    def table(self, ext=True):
        """
        Return a multi-line string tabulating dday, date, filename

        If *ext* is *True*, the filename will include extensions.
        """
        lines = []
        if ext:
            flist = self.names
        else:
            flist = self.basenames
        for i, fn in enumerate(flist):
            dat = [self.dday[i]] + list(self.date[i]) + [fn]
            dat = tuple(dat)
            lines.append('%12.5f  %4d-%02d-%02d %02d:%02d:%02d  %s' % dat)
        return '\n'.join(lines) + '\n'

    def logbinlist(self, abs=True):
        """
        Return the list of .log.bin files corresponding to the
        list of raw files used in __init__.
        """
        if self.rdir != 'raw':
            raise ValueError(
                "logbinlist requires FileParts initialized with *.raw")
        lbl = [f + '.log.bin' for f in self.filelist]
        if abs:
            lbl = [os.path.abspath(f) for f in lbl]
        return lbl

    def rbinlist(self, inst, msg):
        """
        Return the list of rbin files for *inst* and *msg* corresponding
        to the files used in __init__.
        """
        rlist = []
        for name in self.basenames:
            fn = os.path.join(self.path_to_cruise, self.cruisename,
                                            'rbin', inst, name)
            rlist.append("%s.%s.rbin" % (fn, msg))
        return rlist


