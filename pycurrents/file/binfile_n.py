
'''
Binfile class for numpy.

'''
import warnings

import numpy as np
import numpy.ma as ma
from pycurrents.num import rangeslice
from pycurrents.file.binfile import binfile_s, EmptyBinfileError
import pycurrents.system.pathops as pathops

class binfile_n(binfile_s):
    """
    Binfile class that writes from, and reads into, an ndarray.
    """
    def __init__(self, filename, alias=None, **kwargs):
        """
        alias : dictionary, key is name in binfile, value is new name

        filename and kwargs are passed directly to binfile_s initializer.
        """
        "%s" % binfile_s.__init__.__doc__
        binfile_s.__init__(self, filename, **kwargs)
        dtype = '%s%s' % (self.byteorder, self.type)
        self.dtype_orig = np.dtype(dtype)  # original byte order
        self.dtype = np.dtype(self.type)   # native byte order
        if alias is not None:
            self.columns = [alias.get(key, key) for key in self.columns]
        self.rdtype = np.dtype({'names':self.columns,
                                'formats': [self.dtype]*self.ncolumns})
        self._records = None


    def _get_records(self):
        """
        Read the whole file, returned as a recarray.
        """
        if self._records is None:
            a, n = self.read_n()
            self._records = a.view(type=np.recarray, dtype=self.rdtype).ravel()
        return self._records

    records = property(_get_records)

    def read_n(self, n = None):
        """
        Read up to n records, or to end of file if n is *None*.

        Returns ndarray, number of records read.
        """
        n = self.number_to_read(n)
        a = np.fromfile(self.file, dtype=self.dtype_orig,
                                    count=(n*self.ncolumns))
        self.cursor += n
        a.shape = (n, self.ncolumns)
        a = np.asarray(a, dtype=self.dtype)
        return a, n

    def __next__(self):
        'return a 1-D array--the next row'
        a, n = self.read_n(1)
        if n == 0:
            raise StopIteration
        a.shape = (self.ncolumns,)
        return a

    def write(self, a):
        s = np.asarray(a, dtype=self.dtype).tobytes()
        nrec = binfile_s.write(self, s)
        return nrec


class BinfileSet:
    '''
    Array views of a concatenated set of binfiles.

    The initializer scans a set of binfiles and sets
    various properties, including start and end records
    of each file, into attributes.  The full data set,
    or selected slices, are read as needed, when accessed
    via other attributes.

    Of course, the binfiles must
    all be of the same kind; this is checked loosely by looking
    at the name.

    Attributes:
        filenames: list of filenames that are not empty
        emptyfilenames: list of filenames that are empty
        allfilenames: list of filenames used in initialization
        name: header name field
        columns: names of the binfile columns
        ncolumns: number of columns
        starts: structured array of first record from each file
        ends: same, for the last record of each file
        array: simple ndarray of the concatenated binfile contents
        records: view of the array with named columns
        slicevars: the (start, stop, step) tuple that would
                    slice the present subset out of the whole array.
        slicevardict: the dictionary corresponding to the above, for
                    use in an argument list that specifies start, stop
                    and step as kwargs.

        Attribute access to columns is provided, but there are
        no entries in the dict, so they don't show up with ipython
        and tab key.  This is like the case for recarrays.

    Methods:
        set_slice: when accessing array, records or columns,
                   index into the complete data set using these
                   values.

        set_range: Use a monotonic column (normally time) to select
                   a range.

    Starts and ends, along with filenames, etc. are always generated
    upon instance creation; reading all the data is done only when it
    is accessed via the array, records, or column-name attributes, and
    then only on the first access.

    '''
    def __init__(self, filenames, masked=False, alias=None,
                        start=0, stop=None, step=1,
                        cname=None):
        '''
        filenames : list of binfile names, a single name, or a glob

        masked : Boolean

        alias : dictionary, key is name in binfile, value is new name

        start, stop, step: the usual python slicing parameters applied
                           to the whole concatenated data set.

        cname: column name to be used for time range selection.
            This must be specified either here or in the call
            to set_range.

        ValueError will be raised (by make_filelist) if a glob
        is supplied and no files are found.

        '''

        filenames = pathops.make_filelist(filenames)
        self.allfilenames = filenames
        self.masked = masked
        self.cname = cname

        self.filenames = []
        self.emptyfilenames = []
        nrecs = []
        starts = []
        ends = []
        _initialized = False
        for f in filenames:
            try:
                b = binfile_n(f)
            except EmptyBinfileError:
                warnings.warn("Skipping empty binfile '%s'" % f, UserWarning)
                b = None
                count = 0
            if b is not None:
                if not _initialized:
                    self.ncolumns = b.ncolumns
                    self.dtype = np.dtype(b.type)
                    if alias is not None:
                        self.columns = [alias.get(key, key)
                                        for key in b.columns]
                    else:
                        self.columns = b.columns
                    self.name = b.name
                    _initialized = True
                if b.name != self.name:
                    raise ValueError(
                        "binfile header names don't match: '%s' vs '%s'"
                                                        % (b.name, self.name))
                count = b.count()
            if count > 0:
                nrecs.append(count)
                starts.append(next(b))
                b.seek(-1, whence=2)
                ends.append(b.read(1)[0])
                self.filenames.append(f)
            else:
                self.emptyfilenames.append(f)
            if b is not None:
                b.close()

        if not _initialized:
            return

        self.starts = np.array(starts, self.dtype)
        self.ends = np.array(ends, self.dtype)

        if masked:
            self.starts = np.ma.masked_invalid(self.starts)
            self.ends = np.ma.masked_invalid(self.ends)

        # workaround for py2/py3 numpy, ma; columns are unicode.
        _columns = [str(col) for col in self.columns]
        self.rdtype = np.dtype({'names':_columns,
                                'formats': [self.dtype]*len(self.columns)})
        self.starts = self.starts.view(self.rdtype).ravel()
        self.ends = self.ends.view(self.rdtype).ravel()

        # counts, start/stop for each file within complete
        # concatenation of files, ignoring start, stop, step:
        self.nrec = np.array(nrecs, int)
        boundaries = self.nrec.cumsum()
        self.istop = boundaries
        try:
            self.nrows = boundaries[-1]
            self.istart = np.zeros_like(boundaries)
            self.istart[1:] = boundaries[:-1]
        except IndexError:
            # nrec is empty, boundaries is an empty array
            self.nrows = 0
            self.istart = boundaries

        self.set_range()
        self.set_slice(start, stop, step)

    def set_slice(self, start=0, stop=None, step=1, from_range=False):
        step = step or 1
        start = start or 0
        self.step = step
        self.start = start
        self.stop = stop
        self._from_range = from_range

        if start < 0:
            start += self.nrows

        # Now consider start, stop, step.
        isubstart = start - self.istart
        neg = isubstart < 0
        isubstart[neg] %= step

        # Start index for slicing a file:
        self.isubstart = isubstart

        if stop is None:
            stop = self.nrows
        if stop < 0:
            stop += self.nrows

        self.isubstop = np.minimum(self.istop, stop) - self.istart

        # Stop index for slicing a file:
        self.isubstop = np.maximum(self.isubstop, 0)

        # Number of rows in each slice:
        self.nsub = np.maximum(-((-self.isubstop + self.isubstart)//step), 0)
        # The minus signs in the above allow us to essentially round up
        # by taking advantage of python division, which truncates to the
        # left.  C division tends to truncate toward 0.

        # Total rows after concatenating slices:
        self.nsubrows = self.nsub.sum()

        # Actual positive indices into full array.
        self._start = start
        self._stop = stop

        # The following will be modified in get_array
        # to reflect any time range that was set.
        self._rangestart = self._start
        self._rangestop = self._stop

        self._array = None
        self._records = None

    def set_range(self, ddrange='all', step=1, cname=None):
        """
        cname is e.g., 'm_dday' : column name of time variable to use
        Normally it would be set when instantiating, and not
        needed here.

        for ddrange, see pycurrents.num.nptools.rangeslice

        """
        if cname is None:
            cname = self.cname

        self._range = ddrange
        self.rangename = cname

        if ddrange == 'all':
            self.set_slice()
            return

        if cname is None:
            raise ValueError(
                "set_range requires cname as a kwarg here or at initialization")

        if (ddrange[0] > self.ends[cname][-1] or
            ddrange[1] < self.starts[cname][0]):
            self.set_slice(0, 0, from_range=True)
            #raise ValueError("%s is out of range" % (ddrange,))
            return

        # Indices of first, last file that we need:
        ii0 = np.searchsorted(self.ends[cname], ddrange[0])
        ii1 = np.searchsorted(self.starts[cname], ddrange[1]) - 1
        # Indices
        i0 = self.istart[ii0]
        i1 = self.istop[ii1]
        self.set_slice(i0, i1, step, from_range=True)
        # Note: the last stage of indexing is done inside get_array
        # using self._range.
        # Going through set_slice looks convoluted; refactoring
        # may be in order.  It seems like we should be able to
        # take advantage of ii0 and ii1 directly.

    def __getattr__(self, a):
        # The first check below is needed so that a BinfileSet can be
        # unpickled. Othersise, during unpickling, __getattr__ is called before
        # the columns attribute has been restored, leading to infinite
        # recursion.
        if "columns" in self.__dict__ and a in self.columns:
            return self._get_records()[a]
        else:
            raise AttributeError(a)

    def get_array(self):
        if self._array is None:
            _array = np.empty((self.nsubrows, len(self.columns)),
                                                    dtype=self.dtype)
            i0 = 0
            i1 = 0
            for i, f in enumerate(self.filenames):
                if self.nsub[i] > 0:
                    i1 += self.nsub[i]
                    b = binfile_n(f)
                    # specify n so that this will work even if data are accreting.
                    a = b.read(n=self.nrec[i])
                    sl = slice(self.isubstart[i], self.isubstop[i], self.step)
                    _array[i0:i1] = a[sl]
                    b.close()
                    i0 = i1
            if self.masked:
                m = np.zeros(_array.shape, dtype=bool)
                _array = ma.array(_array, mask=m, shrink=False)
            if  self._from_range:
                icol = self.columns.index(self.rangename)
                sl = rangeslice(_array[:,icol], self._range)
                self._rangestart = self._start + sl.start * self.step
                self._rangestop = (self._rangestart +
                                    (sl.stop - sl.start) * self.step)
                _array = _array[sl]
            self._array = _array
        return self._array
    array = property(get_array)

    def get_slicevars(self):
        self.get_array()
        return self._rangestart, self._rangestop, self.step
    slicevars = property(get_slicevars)

    def get_slicevardict(self):
        start, stop, step = self.get_slicevars()
        return dict(start=start, stop=stop, step=step)
    slicevardict = property(get_slicevardict)


    def _get_records(self):
        if self._records is None:
            self.get_array()
            self._records = self._array.view(dtype=self.rdtype).ravel()
        return self._records

    records = property(_get_records)

    # There seems to be no point in actually using the recarray
    # and MaskedRecords views, but they are left here as an
    # illustration in case some advantage in using them turns up.
    #
    #if masked:
    #    from numpy.ma import mrecords
    #    self.attr = self.records.view(mrecords.MaskedRecords)
    #else:
    #    self.attr = self.records.view(np.recarray)

class BinfileSetCache:
    """
    An instance of this class acts like the BinfileSet __init__ method,
    except that repeated calls with the same list of filenames
    returns a cached instance instead of making a new one.  No more
    than one instance is kept in the cache.

    Identification of the cached instance is based entirely on the
    filenames, which must be a sequence, not a glob; the kwargs are
    not checked. There is also no checking of whether the files were
    updated since the instance was cached.
    """
    def __init__(self):
        self.cached = {}

    def __call__(self, filenames, **kw):
        fnames = tuple(filenames)
        try:
            bs = self.cached[fnames]
        except KeyError:
            bs = BinfileSet(fnames, **kw)
            self.cached = {}
            self.cached[fnames] = bs
        return bs

