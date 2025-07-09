"""
Date-time routines ported from CODAS.
"""

cimport c_time
cimport numpy
import numpy
numpy.import_array()

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
        c_time.yd_to_ymdhms_time(
                        dptr[ii],
                        c_yearbase,
                        <c_time.YMDHMS_TIME_TYPE*>&(c_arr.data[ii*n]))
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
    cdef int ii, n, nr
    c_yearbase = yearbase
    if len(args) == 1:
        d = numpy.asarray(args[0], dtype=numpy.uint16, order='C')
        if d.ndim == 1:
            c_arr = d
            return c_time.year_day(<c_time.YMDHMS_TIME_TYPE*>c_arr.data,
                                                                   c_yearbase)
        elif d.ndim == 2:
            if d.shape[1] != 6:
                raise ValueError(
                    "ymdhms time array must have 6 columns, but shape is: %s"
                    % d.shape)
            c_arr = d
            dday = numpy.empty(shape=(d.shape[0],), dtype=float)
            c_dday = dday
            dday_ptr = <double *>c_dday.data
            n = 12 # bytes per row
            nr = d.shape[0]
            for ii from 0 <= ii < nr:
                dday_ptr[ii] = c_time.year_day(
                                <c_time.YMDHMS_TIME_TYPE*>&(c_arr.data[ii*n]),
                                c_yearbase)
            return dday
        else:
            raise ValueError(
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
        raise ValueError("invalid argument list; see docstring")
