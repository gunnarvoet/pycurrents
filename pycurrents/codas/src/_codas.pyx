'''
Cython interface to the CODAS C library.

'''
cimport c_codas

from libc.string cimport strncpy
from libc.errno cimport errno
cimport numpy

import numpy
from pycurrents.codas.codasmask import badval_dict, masked_codas

from pycurrents.data.navcalc import unwrap_lon

# Numpy must be initialized
numpy.import_array()

from os import strerror
from datetime import datetime
from textwrap import dedent
from warnings import warn

# We want access to some named codes in dbsource/dbcommon.c.
cdef extern c_codas.NAME_LIST_ENTRY_TYPE ERROR_CODE[52]
error_code_from_name = {e["name"].decode("ascii"): e["code"] for e in ERROR_CODE}
error_name_from_code = {e["code"]: e["name"].decode("ascii") for e in ERROR_CODE}

cdef extern c_codas.NAME_LIST_ENTRY_TYPE DATA_CODE[26]
data_code_from_name = {e["name"].decode("ascii"): e["code"] for e in DATA_CODE}
data_name_from_code = {e["code"]: e["name"].decode("ascii") for e in DATA_CODE}

# And from include/value_lst.h:
cdef extern c_codas.NAME_LIST_ENTRY_TYPE VALUE_CODE[12]
value_code_from_name = {e["name"].decode("ascii"): e["code"] for e in VALUE_CODE}
value_name_from_code = {e["code"]: e["name"].decode("ascii") for e in VALUE_CODE}


def to_str(b):
    """
    Py2/Py3 compatibility: convert b from <char *> to native string
    """
    return str(bytes(b).decode('ascii'))

class CodasError(Exception):
    """
    Base exception, for convenience and simplicity in "except" catches.
    """

class CodasValueError(ValueError, CodasError):
    """
    Exception, typically for invalid arguments in Codas calls.
    """
    pass

class CodasRuntimeError(RuntimeError, CodasError):
    """
    Exception for miscellaneous errors inside Codas calls.
    """
    pass

class CodasRangeError(ValueError, CodasError):
    """
    Request for a data range that does not intersect DB contents.
    """
    pass

class CodasRangeBeforeStart(CodasRangeError):
    pass

class CodasRangeAfterEnd(CodasRangeError):
    pass

class CodasNoDataError(ValueError, CodasError):
    """
    Request for a data type that is not in the database.
    """
    pass

class CodasUnrecognizedRange(CodasRangeError):
    def __init__(self, r=None, rtype=None):
        self.r = r
        self.rtype = rtype

    def __str__(self):
        out = ("Range parameter input, %s, does not match given"
               " or inferred range type, %s" % (self.r, self.rtype))
        return out

cdef extern from "getadcp.h":
    ctypedef struct ADCP_PROFILE_SET:
        void *blkprf                     # int
        void *time          # short
        void *lgb           # short
        void *mab           # short

        void *pf      # unsigned char
        void *pg      # unsigned char
        void *a       # unsigned char
        void *sw      # unsigned char
        void *ra      # unsigned char

        void *d          # float
        void *u          # float
        void *v          # float
        void *w          # float
        void *e          # float

        void *U_ship   # float
        void *V_ship   # float
        void *heading  # float

        void *tr_temp           # float
        void *snd_spd_used      # float
        void *best_snd_spd      # float

        void    *watrk_hd_misalign   # float
        void    *watrk_scale_factor  # float

        void    *botrk_hd_misalign   # float
        void    *botrk_scale_factor  # float

        void    *last_temp                # float
        void    *last_heading             # float

        void    *mn_pitch
        void    *mn_roll
        void    *std_pitch
        void    *std_roll

        void *U_bt                         # float
        void *V_bt                         # float
        void *D_bt                         # float

        void *dday          # double
        void *lon           # double
        void *lat           # double

        void *lon_dir          # double
        void *lat_dir          # double

        void *resid_stats                # float
        void *tseries_stats              # float
        void *tseries_diffstats              # float

        void *pgs_sample                  # short
        void *num_bins         # short

        int year_base


    ctypedef union ADCP_PROFILE_SET_UNION:
        ADCP_PROFILE_SET aps
        (void *)ptrs[44]

    int get_data(ADCP_PROFILE_SET *aps, int nprofs, int nbins, int txy_only)

ctypedef union DATA_LIST_ENTRY_NAME_U:
    c_codas.DATA_LIST_ENTRY_TYPE entry
    char name[20]

cdef c_codas.RANGE_TYPE c_range(r, rtype):
    cdef c_codas.BLOCK_RANGE_TYPE br
    cdef c_codas.BLKPRF_RANGE_TYPE bpr
    cdef c_codas.DAY_RANGE_TYPE dr
    cdef c_codas.TIME_RANGE_TYPE tr
    cdef c_codas.RANGE_TYPE range
    try:
        if rtype == 'block_profile':
            bp0, bp1 = r
            bpr.start.block = bp0[0]
            bpr.start.profile = bp0[1]
            bpr.end.block = bp1[0]
            bpr.end.profile = bp1[1]
            range.ru.blkprf = bpr
            range.type = c_codas.BLKPRF_RANGE
        elif rtype == 'block':
            br.start, br.end = r
            range.ru.block = br
            range.type = c_codas.BLOCK_RANGE
        elif rtype == 'day':
            dr.yearbase, dr.start, dr.end = r
            range.ru.day = dr
            range.type = c_codas.DAY_RANGE
        elif rtype == 'ymdhms':
            s, e = r
            tr.start.year = s.year
            tr.start.month = s.month
            tr.start.day = s.day
            tr.start.hour = s.hour
            tr.start.minute = s.minute
            tr.start.second = s.second
            tr.end.year = e.year
            tr.end.month = e.month
            tr.end.day = e.day
            tr.end.hour = e.hour
            tr.end.minute = e.minute
            tr.end.second = e.second
            range.ru.time = tr
            range.type = c_codas.TIME_RANGE
        else:
            msg = ["unrecognized range type string: %s" % rtype,
                   "valid strings: block, block_profile, day, ymdhms"]
            raise CodasValueError('\n'.join(msg))
    except:
        raise CodasUnrecognizedRange(r=r, rtype=rtype)
    return range

c_codas.set_msg_stdout(0)  # suppress printing to stdout
                           # later we can enable bigbuf and
                           # scoop up the messages, if desired.
                           # A wrapper for c_codas.get_msg will be needed.


def type_of_range(r):
    type_ = None
    if len(r) == 2:
        if hasattr(r[0], 'year'):
            type_ = 'ymdhms'
        else:
            try:
                if len(r[0]) == 2 and len(r[1]) == 2:
                    type_ = 'block_profile'
            except TypeError:
                type_ = 'block'
    elif len(r) == 3:
        type_ = 'day'
    else:
        type_ = None
    if type_ is None:
        raise CodasValueError('Cannot recognize type of range input: %s' % r)
    return type_

codas_type_dict = {
                  c_codas.BYTE_VALUE_CODE    : numpy.int8,
                  c_codas.UBYTE_VALUE_CODE   : numpy.uint8,
                  c_codas.CHAR_VALUE_CODE    : numpy.character,
                  c_codas.SHORT_VALUE_CODE   : numpy.int16,
                  c_codas.USHORT_VALUE_CODE  : numpy.uint16,
                  c_codas.LONG_VALUE_CODE    : numpy.int32,
                  c_codas.ULONG_VALUE_CODE   : numpy.uint32,
                  c_codas.FLOAT_VALUE_CODE   : numpy.float32,
                  c_codas.DOUBLE_VALUE_CODE  : numpy.float64,
                  c_codas.COMPLEX_VALUE_CODE : numpy.complex64,
                  c_codas.TEXT_VALUE_CODE    : numpy.bytes_,
                  c_codas.STRUCT_VALUE_CODE  : numpy.object_
                  }

def to_date(yearbase, dday):
    """
    Convert decimal day to *YMDHMS*

    Signature::

        YMDHMS = to_date(yearbase, dday)

    Arguments:

        *yearbase*
            Integer year for time origin.
        *dday*
            Time in days since start of *yearbase*;
            float or 1-D sequence of floats.

    Returns:

        *YMDHMS*
            Calendar date and time as a numpy uint16 array,
            shape (6,) if *dday* is a scalar, or
            shape (n,6) if *dday* is a sequence.

    """
    cdef numpy.ndarray c_arr
    cdef numpy.ndarray c_dday
    cdef int ii, n, nr
    cdef int c_yearbase
    cdef double *dptr

    dday = numpy.asarray(dday, dtype=float, order='C')
    ret_1D = (dday.ndim == 0)
    dday.shape = (dday.size,)
    nr = dday.size
    c_dday = dday
    ymdhms = numpy.empty(shape=(dday.size, 6), dtype=numpy.uint16)
    c_arr = ymdhms
    c_yearbase = yearbase
    n = 12
    dptr = <double *>c_dday.data
    for ii from 0 <= ii < nr:
        c_codas.yd_to_ymdhms_time(
                        dptr[ii],
                        c_yearbase,
                        <c_codas.YMDHMS_TIME_TYPE*>&(c_arr.data[ii*n]))
    if ret_1D:
        ymdhms.shape = (6,)
    return ymdhms


def to_day(yearbase, *args):
    """
    Return CODAS decimal day for one or more date-times.

    Signatures::

        dday = to_day(yearbase, YMDHMS)
        dday = to_day(yearbase, year, month, day, hour, minute, seconds)

    Arguments:

        *yearbase*
            Integer year from the start of which time in days
            is returned.
        *YMDHMS*:
            1-D (length 6) or 2-D (Nx6) sequence (not masked) of
            integers.
            Columns are *year*, *month*, *day*,
            *hour*, *minute*, *seconds*.
        *year*, *month*, *day*, *hour*, *minute*, *seconds*
            Integers or 1-D sequences; all are
            optional except the first; all 1-D sequences must
            have the same length, but sequences and scalars may
            be mixed.

    Returns:

        *dday*
            If a single *YMDHMS* or set of scalar args is provided,
            *dday* is returned as a scalar; otherwise a 1-D array of
            floats is returned.

    """
    cdef numpy.ndarray c_arr
    cdef numpy.ndarray c_dday
    cdef double *dday_ptr
    cdef int c_yearbase
    #cdef c_codas.YMDHMS_TIME_TYPE tbuf
    cdef int ii, n, nr
    c_yearbase = yearbase
    if len(args) == 1:
        d = numpy.asarray(args[0], dtype=numpy.uint16, order='C')
        if d.ndim == 1:
            c_arr = d
            return c_codas.year_day(<c_codas.YMDHMS_TIME_TYPE*>c_arr.data,
                                                                   c_yearbase)
        elif d.ndim == 2:
            if d.shape[1] != 6:
                raise CodasValueError(
                    "ymdhms time array must have 6 columns, but shape is: %s"
                    % d.shape)
            c_arr = d
            dday = numpy.empty(shape=(d.shape[0],), dtype=float)
            c_dday = dday
            dday_ptr = <double *>c_dday.data
            n = 12 # bytes per row
            nr = d.shape[0]
            for ii from 0 <= ii < nr:
                dday_ptr[ii] = c_codas.year_day(
                                <c_codas.YMDHMS_TIME_TYPE*>&(c_arr.data[ii*n]),
                                c_yearbase)
            return dday
        else:
            raise CodasValueError(
                "ymdhms time array must have 1 or 2 dimensions, but ndim is: %s"
                % d.ndim)
    elif len(args) <=6 and len(args) > 0:
        nargs = len(args)
        a = []
        nrec = 1
        isarray = False
        for arg in args:
            arg = numpy.asarray(arg, dtype=numpy.uint16)
            n = arg.size
            if arg.ndim > 0:
                isarray = True
            if arg.ndim > 1:
                arg.shape = (arg.size,)
            nrec = max(nrec, n)
            a.append(arg)
        newarg = numpy.zeros(shape=(nrec, 6), dtype=numpy.uint16)
        newarg[:,1:3] = 1 # default month, day are 1, not 0
        for j, col in enumerate(a):
            newarg[:,j] = col
        if not isarray:
            newarg.shape = (newarg.size,)
        return to_day(yearbase, newarg)

    else:
        raise CodasValueError("invalid argument list; see docstring")

db_handles = dict()
for _i in range(1,6):
    db_handles[_i] = True

class ProfileDict(dict):
    """
    Class providing both attribute and dictionary access to data.

    It is specialized for handling variables from a CODAS ADCP
    database.  As variables are added or removed using dictionary
    access, their names are added to, or removed from, the
    :attr:`names`.

    """

    def __init__(self, arraydict, nprofs, nbins):
        dict.__init__(self)
        self.__dict__ = self  # R. Kern trick to provide attribute access
        self.nprofs = int(nprofs)
        self.nbins = int(nbins)
        self.names = list(arraydict.keys())

    def __str__(self):
        strl = ["Dictionary of variables from a CODAS database"]
        strl.append("    with %d profiles, %d depths." % (self.nprofs, self.nbins))
        strl.append("Variables are:")
        for i0 in range(0, len(self.names), 3):
            names = self.names[i0:(i0+3)]
            fmt = '  %-20s' * len(names)
            strl.append(fmt % tuple(names))
        return '\n'.join(strl)

    def __setitem__(self, key, value):
        if key not in self.names:
            self.names.append(key)
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        if key in self.names:
            self.names.remove(key)
        dict.__delitem__(self, key)

cdef _tbuf_to_datetime(c_codas.YMDHMS_TIME_TYPE tbuf):
    if tbuf.second & 0x8000:
        _sec = (tbuf.second & 0x7fff) // 100
        _microsec = (tbuf.second & 0x7fff) * 10000 - _sec * 1000000
    else:
        _sec = tbuf.second
        _microsec = 0
    return datetime(tbuf.year, tbuf.month, tbuf.day,
                    tbuf.hour, tbuf.minute, _sec, _microsec)

class DB(object):
    """
    CODAS ADCP database access class.

    The :meth:`__str__` returns information about the database.

    The useful methods include:

    -    :meth:`get_profiles`
    -    :meth:`get_variable`
    -    :meth:`get_range_length`

    Making an instance of the class opens the database;
    deleting the instance closes it.  Owing to the hardware
    and software constraints when CODAS was written, it uses
    a single global table of pointers to database instances
    (structures), and a global index into that array to
    determine which database to operate on.  Hence we
    cannot easily make a database an extension type, but
    instead have to use a module-level dictionary to track
    available slots in the table of pointers.

    """

    def __init__(self, dbname, yearbase=None, sdfile=None, read_only=True):
        """
        signature::

            db = DB(dbname, yearbase=None)

        argument:

            *dbname*
                CODAS database name

        keyword argument:

            *yearbase*:
                *None* | yearbase to be used for *dday* array.
                If *None*, it will be the year of the first
                profile in the database.
            *sdfile*:
                *None* | name of a structure definition file.
                This will be needed only in rare cases where a
                database is missing the definition for a structure.

        """

        cdef c_codas.YMDHMS_TIME_TYPE tbuf
        cdef unsigned int _n
        cdef c_codas.BLKPRF_INDEX_TYPE bp
        cdef int ierr = 0 # initialized to suppress warning
        self.dbname = dbname
        if isinstance(dbname, str):
            dbname = dbname.encode('ascii')  # bytes, for entry to C
        for i_db, available in db_handles.iteritems():
            if available:
                db_handles[i_db] = False
                break
        if not available:
            raise CodasRuntimeError(
                "Maximum of 5 DB instances; can't make another")
        self.i_db = i_db
        self.read_only = read_only
        mode = 0 if read_only else 1
        #        mode = c_codas.READ_ONLY if read_only else c_codas.READ_WRITE
        res = c_codas.dbopen_cnf(self.i_db, dbname, mode, 1)
        if res < 0:
            db_handles[i_db] = False
            raise IOError("Can't open database %s" % self.dbname)
        _n = 12
        c_codas.dbget_cnf(c_codas.TIME, <void *>&tbuf, &_n, "Getting first TIME")
        self.ymdhms_start = _tbuf_to_datetime(tbuf)
        if yearbase is None:
            yearbase = self.ymdhms_start.year
        self.yearbase = yearbase
        self.dday_start = c_codas.year_day(&tbuf, yearbase)
        res = c_codas.db_last(&bp)
        self.bp_end = (bp.block, bp.profile)
        res = c_codas.dbsrch_cnf(c_codas.BLOCK_PROFILE_SEARCH, <void *>&bp)
        _n = 12
        c_codas.dbget_cnf(c_codas.TIME, <void *>&tbuf, &_n, "Getting last TIME")
        self.ymdhms_end = _tbuf_to_datetime(tbuf)
        self.dday_end = c_codas.year_day(&tbuf, yearbase)

        self.nprofs = self.get_range_length(((0,0), self.bp_end),
                                                    rtype='block_profile')
        if sdfile is not None:
            c_codas.DBLOADSD(sdfile.encode("ascii"), &ierr)
            if ierr:
                raise CodasRuntimeError(
                    "Cannot load structure def file %s" % sdfile)

        self.search_bp()  # start at the beginning

    def __del__(self):
        c_codas.dbset_cnf(self.i_db)
        c_codas.dbclose_cnf()
        db_handles[self.i_db] = True

    def __str__(self):
        c_codas.dbset_cnf(self.i_db)
        d = self.__dict__.copy()
        d['b_end'] = self.bp_end[0]
        d['p_end'] = self.bp_end[1]
        d['t_start'] = self.ymdhms_start.isoformat(' ')
        d['t_end'] = self.ymdhms_end.isoformat(' ')
        d['dday_diff'] = self.dday_end - self.dday_start
        str_ = '''
        dbname:   %(dbname)s
            start time:          %(t_start)s
            end time:            %(t_end)s
            decimal day range:   %(yearbase)d,  %(dday_start).5f to %(dday_end).5f
            duration:            %(dday_diff).5f days
            number of profiles:  %(nprofs)d
            last block, profile: %(b_end)d, %(p_end)d
            variables with data:
        ''' % d
        str_ = dedent(str_)
        strlst = [str_]
        vlist = self.get_variable_names()
        for i in range(0, len(vlist), 3):
            vl = vlist[i:i+3]
            strlst.append("%-20s"*len(vl) % tuple(vl))
        strlst.append('')
        return '\n'.join(strlst)

    def move(self, nsteps):
        c_codas.dbset_cnf(self.i_db)
        return c_codas.dbmove_cnf(nsteps)

    def search_bp(self, block=0, profile=0):
        cdef c_codas.BLKPRF_INDEX_TYPE bp
        bp.block = block
        bp.profile = profile
        c_codas.dbset_cnf(self.i_db)
        return c_codas.dbsrch_cnf(c_codas.BLOCK_PROFILE_SEARCH, <char *>&bp)

    @property
    def block_profile(self):
        cdef c_codas.BLKPRF_INDEX_TYPE bp
        cdef unsigned int n = sizeof(bp)
        c_codas.dbset_cnf(self.i_db)
        c_codas.dbget_cnf(data_code_from_name["BLOCK_PROFILE_INDEX"], <char *>&bp, &n, "getting BP index")
        return bp.block, bp.profile

    def get_numpy_bytes(self, data_id_or_name):
        cdef unsigned int n = 0
        c_codas.dbset_cnf(self.i_db)
        if isinstance(data_id_or_name, str):
            try:
                id = data_code_from_name[data_id_or_name]
            except KeyError:
                dle = self.get_data_list_entry(data_id_or_name)
                id = dle['index']
        else:
            id = data_id_or_name
        if id > 301:
            raise CodasRuntimeError(f"Data ID {id} is not supported by this method.")
        err = c_codas.dbget_cnf(id, <void *>NULL, &n, "getting size")
        if err:
            raise CodasRuntimeError(f"getting size of var {data_id_or_name}")
        if n == 0:
            raise CodasNoDataError(f"There is no data for var {data_id_or_name}")
        buf = numpy.empty((n,), dtype=numpy.int8)
        cdef char [:] cbuf = buf  # memoryview...
        err = c_codas.dbget_cnf(id, &cbuf[0], &n, "getting data")
        if err:
            raise CodasRuntimeError(f"getting bytes for var {data_id_or_name}")
        return buf

    def get_ymdhms(self):
        return self.get_numpy_bytes("TIME").view(numpy.uint16)

    def get_depth_range(self):
        return self.get_numpy_bytes("DEPTH_RANGE").view(numpy.int16)

    def get_dmsh_position(self):
        return self.get_numpy_bytes("POSITION").view(numpy.int16)

    def get_range(self, ddrange=None, startdd=None, ndays=None, r=None):
        """
        Find the time range as specified in a variety of ways.
        See :meth:`get_profiles` for an explanation of the kwargs.

        """
        if ddrange is not None:
            try:
                startdd, d1 = ddrange
                ndays = d1 - startdd
            except TypeError:
                ndays = ddrange
                startdd = None
        if ndays is not None:
            if ndays >= 0:
                if startdd is None:
                    d0 = self.dday_start
                else:
                    d0 = startdd
                r = (self.yearbase, d0, d0+ndays)
            elif ndays < 0:
                if startdd is None:
                    d1 = self.dday_end
                else:
                    d1 = startdd
                r = (self.yearbase, d1+ndays, d1)
        if r is None:
            r = ((0,0), self.bp_end)
        return r


    def get_arraydict(self, nprofs, nbins, txy_only):

        if txy_only:
            return {'blkprf': (0, (nprofs, 2), numpy.intc),
                    'ymdhms' : (1, (nprofs, 6), numpy.int16),
                    'dday' : (33, (nprofs,), numpy.float64),
                    'lon' : (36, (nprofs,), numpy.float64),
                    'lat' : (37, (nprofs,), numpy.float64),
                    }

        else:
            return {'blkprf': (0, (nprofs, 2), numpy.intc),
                    'ymdhms' : (1, (nprofs, 6), numpy.int16),
                    'lgb' : (2, (nprofs,), numpy.int16),
                    'mab' : (3, (nprofs,), numpy.int16),
                    'pflag' : (4, (nprofs,nbins), numpy.uint8),
                    'pg' : (5, (nprofs,nbins), numpy.uint8),
                    'amp' : (6, (nprofs,nbins), numpy.uint8),
                    'swcor' : (7, (nprofs,nbins), numpy.uint8),
                    'ra' : (8, (nprofs,nbins, 4), numpy.uint8),
                    'depth' : (9, (nprofs, nbins), numpy.float32),
                    'umeas' : (10, (nprofs, nbins), numpy.float32),
                    'vmeas' : (11, (nprofs, nbins), numpy.float32),
                    'w' : (12, (nprofs, nbins), numpy.float32),
                    'e' : (13, (nprofs, nbins), numpy.float32),
                    'uship' : (14, (nprofs,), numpy.float32),
                    'vship' : (15, (nprofs,), numpy.float32),
                    'heading' : (16, (nprofs,), numpy.float32),
                    'tr_temp' : (17, (nprofs,), numpy.float32),
                    'snd_spd_used' : (18, (nprofs,), numpy.float32),
                    'best_snd_spd' : (19, (nprofs,), numpy.float32),
                    'watrk_hd_misalign'  : (20, (nprofs,), numpy.float32),
                    'watrk_scale_factor' : (21, (nprofs,), numpy.float32),
                    'botrk_hd_misalign'  : (22, (nprofs,), numpy.float32),
                    'botrk_scale_factor' : (23, (nprofs,), numpy.float32),
                    'last_temp'          : (24, (nprofs,), numpy.float32),
                    'last_heading'       : (25, (nprofs,), numpy.float32),
                    #    float *mn_pitch, *mn_roll, *std_pitch, *std_roll,
                    #    added 2017/10/22
                    'mn_pitch'           : (26, (nprofs,), numpy.float32),
                    'mn_roll'            : (27, (nprofs,), numpy.float32),
                    'std_pitch'          : (28, (nprofs,), numpy.float32),
                    'std_roll'           : (29, (nprofs,), numpy.float32),

                    'u_bt'               : (30, (nprofs,), numpy.float32),
                    'v_bt'               : (31, (nprofs,), numpy.float32),
                    'd_bt'               : (32, (nprofs,), numpy.float32),
                    'dday' : (33, (nprofs,), numpy.float64),
                    'lon_raw' : (34, (nprofs,), numpy.float64),
                    'lat_raw' : (35, (nprofs,), numpy.float64),
                    'lon' : (36, (nprofs,), numpy.float64),
                    'lat' : (37, (nprofs,), numpy.float64),
                    'resid_stats' : (38, (nprofs, 6, nbins), numpy.float32),
                    'tseries_stats' : (39, (nprofs, 7), numpy.float32),
                    'tseries_diffstats' : (40, (nprofs, 4), numpy.float32),
                    'pgs_sample' : (41, (nprofs,), numpy.int16),
                    'num_bins' : (42, (nprofs,), numpy.int16),
                    'e_std' : (43, (nprofs, nbins), numpy.float32),
                    }



    def get_profiles(self, ddrange=None,
                           startdd=None, ndays=None,
                           r=None,
                           nbins=None, txy_only=False):
        """
        Get the same set of variables that getmat.c does, plus
        last_temp, last_heading, mn_pitch, mn_roll, std_pitch,
        std_roll.

        Variables are returned as a dictionary of numpy masked
        arrays, except for pflag, blkprf, ymdhms, pgs_sample, and dday,
        which are ndarrays, and yearbase which is a python int.
        Most array shapes are (Nprofiles, Ndepths);
        the profile axis is always first.  Arrays are C-contiguous.

        Signatures::

            pd = db.get_profiles(ddrange=None,
                                 nbins=None,
                                 txy_only=False)

            pd = db.get_profiles(startdd=None, ndays=None,
                                 nbins=None,
                                 txy_only=False)

            pd = db.get_profiles(r=None,
                                 nbins=None,
                                 txy_only=False)

        The first of these may be preferred, because it uses the
        same method of specifying a range as rangeslice; we
        are trying to standardize on this simple convention.
        If one wants a single profile, however, the second
        signature with ndays=None is more convenient.


        Keyword arguments:

            *ddrange*
                *None* | ndays | (startdd, enddd)
                if ndays > 0, take first ndays;
                if ndays < 0, take last |ndays|

        If *ddrange* is *None*, then *startdd* and *ndays* are checked:

            *startdd*
                *None* | dday origin of time range
            *ndays*
                *None* | dday span of time range

                ========     ============    ===============================
                startdd      ndays           result
                ========     ============    ===============================
                None         scalar > 0      from start to start + ndays
                scalar       scalar > 0      from startdd to startdd + ndays

                None         scalar < 0      from end - ndays to end
                scalar       scalar < 0      from startdd - ndays to startdd

                scalar       scalar = 0      get first profile on
                                             or after startdd
                ========     ============    ===============================

        If *ddrange* is *None* and *ndays* is *None*, then *r* is checked:

            *r*
                If *None*, all profiles in the database will be
                returned.

                Otherwise, a range is given in one of three
                styles accepted by :meth:`get_range_length`:

                ================     ==========================================
                type                 format
                ================     ==========================================
                block                (b0, b1)
                block_profile        ((b0,p0), (b1,p1))
                day                  (yearbase, dday0, dday1)
                ymdhms               (ymdhms0, ymdhms1)
                                     where each is a datetime instance
                                     or any other object with attributes
                                     year, month, day, hour, minute, second
                ================     ==========================================

        Remaining keyword arguments:

            *nbins*
                *None* | integer number of depth bins to get.

                If *None*, it will be set to the maximum number of
                bins in the database.

            *txy_only*
                If *True*, only blkprf, ymdhms, dday, lon, and lat
                will be included in the output.

        Note: most of the variables are self-explanatory and match
        getmat, but there is one exception: LON, LAT from getmat
        correspond to lon_raw, lat_raw here, and come from the
        NAVIGATION Structure.  LON_END, LAT_END from getmat correspond
        to lon, lat here, and come from the codas block directory;
        they are put there by putnav.

        """
        cdef ADCP_PROFILE_SET_UNION aps_u
        cdef c_codas.RANGE_TYPE range_
        cdef numpy.ndarray _u
        cdef unsigned int _n
        cdef float floatbuf[1]  # dummy for query call to dbget_f

        r = self.get_range(ddrange=ddrange, startdd=startdd, ndays=ndays, r=r)
        rtype = type_of_range(r)
        nprofs = self.get_range_length(r, rtype)
        range_ = c_range(r, rtype)
        c_codas.dbset_cnf(self.i_db)
        if nbins is None:
            nbins = self.get_nbins()

        aps_u.aps.year_base = self.yearbase

        arraydict = self.get_arraydict(nprofs, nbins, txy_only)
        vardict = ProfileDict(arraydict, nprofs, nbins)
        for key, val in arraydict.iteritems():
            # Use zeros instead of empty; may be better in case of error.
            a = numpy.zeros(*val[1:])
            vardict[key] = a
            _u = a
            aps_u.ptrs[val[0]] = _u.data
        c_codas.goto_start_of_range(&range_)
        np = get_data(&aps_u.aps, nprofs, nbins, txy_only)
        if np != nprofs:
            warn("Return from get_data was %d when %d was expected." %
                                                            (np, nprofs))
        if not txy_only:
            # resid_stats is not in a convenient order, so we
            # will rearrange it.
            # It is most efficient to do this before masking.
            rs = vardict['resid_stats'].transpose((0,2,1))
            vardict['resid_stats'] = numpy.array(rs, copy=True, order='C')

        for key in arraydict.keys():
            if key not in ['pflag', 'blkprf', 'ymdhms', 'dday',
                           'pgs_sample', 'num_bins']:
                vardict[key] = masked_codas(vardict[key])
        # Whenever there is a "dday" type of variable, there should
        # be a corresponding "yearbase" next to it:
        vardict['yearbase'] = self.yearbase
        vardict['lon'] = unwrap_lon(vardict['lon'])
        if not txy_only:
            vardict['lon_raw'] = unwrap_lon(vardict['lon_raw'])
            # Now convert
            dt = numpy.dtype(dict(names=['uu', 'uv', 'vv', 'ff', 'fp', 'pp'],
                               formats=['f4']*6))
            rs = vardict['resid_stats']
            rs_struc = rs.view(dtype=dt)
            rs_struc.shape = rs_struc.shape[:-1]
            vardict['resid_stats'] = rs_struc

        return vardict


    def get_range_length(self, r, rtype=None):
        """
        Signature::

            n = db.get_range_length(r, rtype=None)

        Given a range *r* of specified type, return the number of
        profiles in the range.  If *rtype* is *None*,
        the type will be auto-detected from *r*.

        ================     ==========================================
        rtype                format
        ================     ==========================================
        block                (b0, b1)
        block_profile        ((b0,p0), (b1,p1))
        day                  (yearbase, dday0, dday1)
        ymdhms               (ymdhms0, ymdhms1)
                             where each is a datetime instance
                             or any other object with attributes
                             year, month, day, hour, minute, second
        ================     ==========================================


        """
        cdef c_codas.RANGE_TYPE range_
        if rtype is None:
            rtype = type_of_range(r)
        range_ = c_range(r, rtype)
        c_codas.dbset_cnf(self.i_db)
        nprofs = c_codas.count_range(&range_)
        if nprofs > 0:
            return nprofs

        if nprofs == -2:
            raise CodasRangeBeforeStart("range is %s" % (r,))
        elif nprofs == -4:
            raise CodasRangeAfterEnd("range is %s" % (r,))
        else:
            raise CodasRuntimeError(
                "count_range failed with error %s, range is %s" %
                                (nprofs, r))

    def get_data_list_entry(self, name):
        cdef DATA_LIST_ENTRY_NAME_U dl
        cdef unsigned int n_
        _name = name[:20].encode('ascii')
        strncpy(dl.name, <char *>_name, 20)
        n_ = 56
        c_codas.dbset_cnf(self.i_db)
        ret = c_codas.dbget_cnf(c_codas.DATA_LIST_ENTRY, <void *>&dl, &n_,
                                "Getting data list entry")
        if ret != 0:
            raise CodasValueError("Could not find data type with name %s" % name)

        dle = {'index': dl.entry.index,
               'value_type': dl.entry.value_type,
               'access_type': dl.entry.access_type,
               'name': to_str(<char *>dl.entry.name),
               'units': to_str(<char *>dl.entry.units),
               'offset': dl.entry.offset,
               'scale': dl.entry.scale}
        return dle

    def get_variable_names(self, withdata=True, access="all"):
        cdef char buf[2000]
        cdef int ret
        cdef int codas_code
        cdef unsigned int n_

        if withdata:
            codas_code = c_codas.NAMES_WITH_DATA
        else:
            codas_code = c_codas.DATA_LIST_NAMES
        n_ = 2000
        c_codas.dbset_cnf(self.i_db)
        ret = c_codas.dbget_cnf(codas_code, <void *>buf, &n_,
                                "Getting variable names")
        if ret != 0:
            raise CodasValueError("Could not get variable names")
        varnamestr = buf.decode('ascii')
        varnames = varnamestr.split()
        if access == "all":
            return varnames
        if access == "block":
            return [var for var in varnames if self.get_data_list_entry(var)["access_type"] == 1]
        if access == "profile":
            return [var for var in varnames if self.get_data_list_entry(var)["access_type"] == 2]
        raise ValueError("access must be one of 'all', 'block', or 'profile'")

    def get_structure_def(self, name):
        cdef char buf[2000]
        cdef c_codas.STRUCT_DEF_ENTRY_TYPE *sde
        cdef unsigned int n_
        _name = name[:20].encode('ascii')
        strncpy(buf, <char *>_name, 20)
        n_ = 2000
        c_codas.dbset_cnf(self.i_db)
        ret = c_codas.dbget_cnf(c_codas.STRUCTURE_DEF, <void *>buf, &n_,
                                "Getting structure definition")
        if ret != 0:
            raise CodasValueError("Could not find structure def with name %s" % name)
        sde = <c_codas.STRUCT_DEF_ENTRY_TYPE *>buf
        nelem = sde[0].hdr.nelem
        sdlist = []
        for i in range(nelem):
            sde = sde + 1
            sdlist.append({'name': to_str(<char *>sde.elem.name),
                           'units': to_str(<char *>sde.elem.units),
                           'value_type': sde.elem.value_type,
                           'count': sde.elem.count})
        return sdlist

    def dtype_from_sdlist(self, sdlist):
        dtlist = []
        for elem in sdlist:
            evt = elem['value_type']
            if evt == c_codas.STRUCT_VALUE_CODE:
                sub_sdlist = self.get_structure_def(elem['name'])
                vt = self.dtype_from_sdlist(sub_sdlist)
            else:
                vt = codas_type_dict[evt]
            if elem['count'] == 1:
                dtlist.append((elem['name'], vt))
            else:
                shape = (elem['count'],)
                dtlist.append((elem['name'], vt, shape))
        dtype = numpy.dtype(dtlist)
        return dtype

    def get_nbins(self):
        """
        Return the maximum number of depth bins in the database.

        This is done by reading all DEPTH variables, assuming a
        maximum of 128, and then checking the mask to find the actual
        max.
        """
        d = self.get_variable("DEPTH", nbins=128)
        return d.count(axis=1).max()

    def get_variable(self, name, r=None, nbins=None, masked=True):
        """
        Return an array with any variable specified by *name*.
        Dimensions are (nprofs, nbins)

        See :meth:`get_profiles` for descriptions of *r* and *nbins*.

        Use :meth:`get_range` to calculate *r* from *ddrange* or *startdd* and *ndays*.

        If *masked* is *True* (default), a masked array will be
        returned.

        """
        cdef c_codas.RANGE_TYPE range_
        cdef numpy.ndarray _u
        cdef numpy.ndarray c_arr
        cdef unsigned int _n, _nbytes
        cdef int i, ret
        cdef float floatbuf[1]
        cdef char *dptr
        if r is None:
            r = ((0,0), self.bp_end)
        rtype = type_of_range(r)
        nprofs = self.get_range_length(r, rtype)
        range_ = c_range(r, rtype)
        c_codas.dbset_cnf(self.i_db)
        dle = self.get_data_list_entry(name)
        ind = dle['index']
        c_codas.goto_start_of_range(&range_)
        if dle['value_type'] == c_codas.STRUCT_VALUE_CODE:
            sdlist = self.get_structure_def(dle['name'])
            dt = self.dtype_from_sdlist(sdlist)
            _n = 0
            ret = c_codas.dbget_cnf(ind, <void *> NULL, &_n,
                                            "getting structure nbytes")
            if ret != 0:
                raise CodasRuntimeError("Reading %s" % name)
            if _n == 0:
                raise CodasValueError("Structure %s is absent" % name)
            nbytes = _n
            arr = numpy.empty((nprofs,), dt)
            c_arr = arr
            dptr = <char *> c_arr.data
            for i from 0 <= i < nprofs:
                if i > 0:
                    c_codas.dbmove_cnf(1)
                _n = nbytes
                ret = c_codas.dbget_cnf(ind, <void *>&dptr[i*_n], &_n,
                                                "getting structure")
                if _n != nbytes:
                    raise CodasValueError("Structure %s is absent" % name)
                if ret != 0:
                    raise CodasRuntimeError("Reading %s" % name)
            return arr
        elif dle['value_type'] > c_codas.COMPLEX_VALUE_CODE:
            raise CodasValueError("Unsupported variable type %s for variable %s"
                                                % (dle['value_type'], name))
        if dle['offset'] != 0.0 or abs(dle['scale'] - 1.0) > 1e-5:
            if nbins is None:
                _n = 0
                c_codas.dbget_f_cnf(ind, floatbuf, &_n, "getting ndepths")
                if _n == 0:
                    raise CodasValueError("Array %s is absent" % name)
                nbins = _n
            arr = numpy.empty((nprofs, nbins), dtype=numpy.float32)
            arr.fill(1e38)
            c_arr = arr
            dptr = c_arr.data
            for i from 0 <= i < nprofs:
                if i > 0:
                    c_codas.dbmove_cnf(1)
                _n = nbins
                ret = c_codas.dbget_f_cnf(ind, &((<float *>dptr)[i*_n]), &_n,
                                                "getting float data")
                if ret != 0:
                    raise CodasRuntimeError("Reading %s" % name)
            if masked:
                return masked_codas(arr)
            else:
                return arr
        else:
            dt = codas_type_dict[dle['value_type']]
            item_nbytes = numpy.empty((1,), dt).itemsize
            if nbins is None:
                _n = 0
                c_codas.dbget_cnf(ind, <void *>floatbuf, &_n, "getting nbytes")
                if _n == 0:
                    raise CodasValueError("Array %s is absent" % name)
                nbytes = _n
                nbins = nbytes // item_nbytes
            else:
                nbytes = nbins * item_nbytes
            arr = numpy.empty((nprofs, nbins), dtype=dt)
            arr.fill(badval_dict[dt])
            c_arr = arr
            dptr = <char *> c_arr.data
            for i from 0 <= i < nprofs:
                if i > 0:
                    c_codas.dbmove_cnf(1)
                _n = nbytes
                ret = c_codas.dbget_cnf(ind, &dptr[i*_n], &_n,
                                                "getting array data")
                if ret != 0:
                    raise CodasRuntimeError("Reading %s" % name)
            if masked:
                return masked_codas(arr)
            else:
                return arr

    def put_array(self, name, arr, r=None):
        """
        Write an array `arr` specified by `name`.
        Dimensions are (nprofs, nbins)

        See :meth:`get_profiles` for a description of `r`.

        """
        cdef c_codas.RANGE_TYPE range_
        cdef numpy.ndarray _u
        cdef numpy.ndarray c_arr
        cdef unsigned int _n, _nbytes, _nbad
        cdef int i, ret
        cdef float floatbuf[1]
        cdef char *dptr
        if self.read_only:
            raise CodasValueError("Cannot write to read-only database.")
        if r is None:
            r = ((0,0), self.bp_end)
        rtype = type_of_range(r)
        nprofs = self.get_range_length(r, rtype)
        if arr.shape[0] != nprofs:
            raise CodasValueError("Mismatch between array shape and range length")
        range_ = c_range(r, rtype)
        c_codas.dbset_cnf(self.i_db)
        dle = self.get_data_list_entry(name)
        ind = dle['index']
        c_codas.goto_start_of_range(&range_)
        if dle['value_type'] == c_codas.STRUCT_VALUE_CODE:
            raise CodasValueError("Cannot write to structure")
        elif dle['value_type'] > c_codas.COMPLEX_VALUE_CODE:
            raise CodasValueError("Unsupported variable type %s for variable %s"
                                                % (dle['value_type'], name))


        if dle['offset'] != 0.0 or abs(dle['scale'] - 1.0) > 1e-5:
            # Let CODAS handle offset and scale.
            _n = 0
            c_codas.dbget_f_cnf(ind, floatbuf, &_n, "getting ndepths")
            if _n == 0:
                raise CodasValueError("Array %s is absent" % name)
            nbins = _n
            arr = arr.astype(numpy.float32)
            arr = numpy.ma.filled(arr, 1e38)
            c_arr = arr
            dptr = c_arr.data
            for i from 0 <= i < nprofs:
                if i > 0:
                    c_codas.dbmove_cnf(1)
                _n = nbins
                ret = c_codas.dbput_f_cnf(ind, &((<float *>dptr)[i*_n]), &_n,
                                               &_nbad,
                                                "putting float data")
                if ret != 0:
                    raise CodasRuntimeError("Putting %s" % name)
        else:
            dt = codas_type_dict[dle['value_type']]
            item_nbytes = numpy.empty((1,), dt).itemsize
            _n = 0
            c_codas.dbget_cnf(ind, <void *>floatbuf, &_n, "getting nbytes")
            if _n == 0:
                raise CodasValueError("Array %s is absent" % name)
            nbytes = _n
            nbins = nbytes // item_nbytes
            arr = arr.astype(dt)
            arr = numpy.ma.filled(arr, badval_dict[dt])
            c_arr = arr
            dptr = <char *> c_arr.data
            for i from 0 <= i < nprofs:
                if i > 0:
                    c_codas.dbmove_cnf(1)
                _n = nbytes
                ret = c_codas.dbput_cnf(ind, &dptr[i*_n], &_n,
                                                "getting array data")
                if ret != 0:
                    raise CodasRuntimeError("Putting %s" % name)


