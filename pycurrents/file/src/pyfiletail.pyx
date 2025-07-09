''' pyfiletail.pyx Cython interface to filetail.c

    This yields a Filetail class.

    At least in python versions 2.3 and 2.4, there seems to be a
    subtle bug in the file io routines, such that using readlines()
    with python's file object very occasionally corrupts the data,
    adding a space character.  This bug motivated the Filetail class,
    but it has additional advantages: it works equally well with
    readline(), readlines(), and read(N).

    python Setup.py build_ext --inplace

    EF 2006/03/11
'''

from os import strerror
import io

cimport cpython

cdef extern from "errno.h":
    int errno

cdef extern from "filetail.h":
    ctypedef struct filetail:
        #    We are not accessing anything directly from pyrex.
        #int N
        #int i_oldest
        #int i_next
        #int bad_line
        #int fd
        #int owned_file
        #int  position
        #char *filename
        #char *buf
        #char *outbuf
        #struct stat st
        pass

    filetail *new_filetail(int N)
    void dealloc_filetail(filetail *ft)
    int open_filetail(filetail *ft, char *fname)
    int connect_filetail(filetail *ft, int fd)
    void close_filetail(filetail *ft)
    char *read_line(filetail *ft)
    int read_bytes(filetail *ft, int n)
    char *get_outbuf(filetail *ft)

cdef class Filetail:
    """A file object suitable only for 'tail'-style reading.

    The constructor takes two args or kwargs:
        filename=None     A file name or a file object to be
                          read using the Filetail.
        N=1024            buffer size; The maximum chunk size for
                          reading the file is one less than this.

    When using readline() or readlines(), any lines longer than
    the chunk size (N-1) will be silently discarded.

    Ordinarily, the constructor would be called with either
    no arguments, or with only a filename.  If called with no
    arguments, the open(filename) method can be used later instead.

    Unlike a file object, a Filetail object can be opened
    with a file, closed, reopened with another file, etc.

    Like a file object, a Filetail object can be used as a
    line-oriented iterater.

    Attempted read operations never block.

    Example:

    from time import sleep
    from pyfiletail import Filetail

    f = Filetail('test')        #
    bb = f.read(32)             # return the first 32 bytes
    line1 = f.readline()        # return the following line
    all_lines = f.readlines()   # return the remaining lines in a list
    idle_count = 0
    while 1:                    # keep reading lines as they are
        line = f.readline()     #   appended to the file by another
        if line == "":          #   program, until there is a
            idle_count += 1     #   1-second interval with nothing added
            if idle_count > 10:
                break
            sleep(0.1)
    f.close()                   #


    """

    cdef filetail *ft_ptr
    cdef char *outbuf
    cdef int N
    cdef int max_chunk
    cdef object filename

    def __cinit__(self, filename = None, N=1024):
        if not (isinstance(N, int) and N > 10):
            raise TypeError, "Filetail buffer size must be integer > 10"
        self.ft_ptr = new_filetail(N)
        self.outbuf = get_outbuf(self.ft_ptr)
        self.N = N
        self.max_chunk = N-1

    def __init__(self, filename = None, N=1024):
        self.filename = filename
        if filename is not None:
            self.open(filename)

    def __dealloc__(self):
        dealloc_filetail(self.ft_ptr)

    def __next__(self):
        line = self.readline()
        if line == "":
            raise StopIteration
        return line

    def __iter__(self):
        return self

    def open(self, filename):
        '''Open filename for sequential reading only.
        filename can be a file object or a file name string.
        '''
        cdef int ret
        if isinstance(filename, int):   # e.g., file descriptor from mkstemp
            ret = connect_filetail(self.ft_ptr, filename)
        elif isinstance(filename, io.IOBase):
            fd = filename.fileno()
            ret = connect_filetail(self.ft_ptr, fd)
        else:
            _filename = bytes(filename, 'ascii')
            ret = open_filetail(self.ft_ptr, _filename)
        if ret == -1:
            raise IOError, "[Errno %d] %s: '%s'" % (errno,
                                strerror(errno), filename)
        self.filename = filename

    def close(self):
        if self.filename is not None:
            close_filetail(self.ft_ptr)
        self.filename = None

    def readline(self):
        '''Read one full line from file.  If a full line is
        not available, return an empty string.  Max line
        length is 1 less than the buffer size.
        '''
        cdef char *buf
        buf = read_line(self.ft_ptr)
        return buf

    def read(self, n):
        '''Read n bytes from file.  n must be at least 1 smaller
        than the buffer size; larger values will be clipped.
        '''
        cdef int nr
        n = min(n, self.max_chunk)
        nr = read_bytes(self.ft_ptr, n)
        if nr == -1:
            raise IOError, "File is not open"
        if nr == 0:
            return ""
        s = cpython.PyBytes_FromStringAndSize(self.outbuf, nr)
        return s


    def readlines(self):
        '''Return a list with all full lines remaining to be read
        when readlines is called.  Each line must be at least 1 smaller
        than the buffer size, but there is no restriction on the
        number of lines.
        '''
        lines = []
        while 1:
            line = self.readline()
            if line:
                lines.append(line)
            else:
                break
        return lines



