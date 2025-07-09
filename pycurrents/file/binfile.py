#!/usr/bin/env python

''' Binfile class, with read and write methods.
    (Write methods are incomplete.)

    A binfile is a very simple file format for storing 2-D arrays
    of double precision numbers, with a minimal self-describing
    ascii header.

   See also comments at bottom.

   2005/03/25
   Added append support.

'''
import os
import sys
import stat
import struct
import array
from optparse import OptionParser

from pycurrents.system.misc import sleep as safesleep

class BinfileError(Exception):
    def __init__(self, fname, msg=None):
        if msg is None:
            msg = "Error in binfile %s" % fname
        super().__init__(msg)
        self.fname = fname

class EmptyBinfileError(BinfileError):
    def __init__(self, fname):
        msg = "Binfile '%s' is empty" % fname
        super().__init__(fname, msg=msg)


_str = '''Binfile %(name)s with %(IOmethod)s IO, mode %(mode)s,
    byteorder %(byteorder)s,
    %(count)d records of %(ncolumns)d fields:
        '''

# String byteorder as returned by sys.byteorder, indexed by '<' or '>'
_sbyteorder = {'<': 'little', '>': 'big'}
# The reverse:
_cbyteorder = {'little': '<', 'big': '>'}
# System byteorder as a character:
_sysbyteorder = _cbyteorder[sys.byteorder]

_pytype = {'i1':'b', 'u1':'B', 'i2':'h', 'u2':'H', 'i4':'i', 'u4':'I',
           'f4':'f', 'f8':'d'}

class binfile_s:
    """
    Binfile base class.

    Uses Python byte strings for input/output. Does not change
    byte order.  That is left to subclasses.

    See the binfile subclass in this
    module, and the binfile_n subclass in the binfile_n module.

    """
    def __init__(self, filename,
                    mode = 'r',
                    name = 'anon',
                    columns = [],
                    type = 'f8',
                    timeout = 0.0,
                    interval = 0.1,
                    runflag = None):
        self.filename = filename
        if mode not in 'rwa':
            raise ValueError("mode must be r, w, or a")
        self.mode = mode   # Logical mode; not necessarily actual mode.
        if mode == 'a':
            mode = 'a+'     # ...so we can read the header.
        if not mode.endswith('b'):
            mode += 'b'
        self.file = open(filename, mode)
        self.fileno = self.file.fileno()
        self.name = name
        self.columns = columns
        self.ncolumns = len(columns)
        if mode == 'w' and self.ncolumns == 0:
            raise ValueError("Use columns kwarg to name one or more columns")
        self.byteorder = sys.byteorder
        self.type = type
        self.nl_header = self.ncolumns + 2 # first line, columns, byteorder
        if 'r' in self.mode:
            try:
                self._read_header()
            except:
                self.file.close()
                raise
        elif 'a' in self.mode:
            try:
                self.file.seek(0)
                self._read_header()
                self.file.seek(0,2)
            except:
                self.file.seek(0)
                self._write_header()
        else:
            self._write_header()
        self.typelen = int(self.type[1])
        self.record_length = self.typelen * self.ncolumns
        self.cursor = 0  # for sequential reading of single records
        if 'a' in self.mode:
            self.cursor = self.count()
        if self.byteorder == _sysbyteorder:
            prefix = '@'
        else:
            prefix = self.byteorder
        self._fmt = prefix + '%d' + _pytype[self.type]
        self.record_fmt = self._fmt % self.ncolumns
        self.IOmethod = 'string'
        self._fstr = _str + '\n        '.join(self.columns) + '\n'
        self.interval = interval
        self.nloops = int(timeout / interval)
        if runflag is not None:
            self.runflag = runflag
        else:
            self.runflag = lambda : True

    def __iter__(self):
        return self

    def __str__(self):
        d = self.__dict__.copy()
        d['count'] = self.count()
        return self._fstr % d

    def close(self):
        self.file.close()
        self.file = None

    def _read_header(self):
        line1 = self.file.readline().decode('ascii')
        fields = line1.split()
        if len(fields) == 0:
            raise EmptyBinfileError(self.filename)
        self.ncolumns = int(fields[0])
        self.nl_header = int(fields[1])
        self.name = str(fields[2])  # str for PY2
        self.columns = []
        for ii in range(self.ncolumns):
            line = self.file.readline().decode('ascii')
            column = str(line.split(None, 1)[0])  # str for PY2: remove unicode
            self.columns.append(column)
        nleft = self.nl_header - self.ncolumns - 1
        if nleft:
            dtypestring = self.file.readline().decode('ascii').strip()
            dtypestring = str(dtypestring)  # str for PY2
            if dtypestring in _cbyteorder:
                self.byteorder = _cbyteorder[dtypestring]
                self.type = 'f8'
            else:
                self.byteorder = dtypestring[0]
                self.type = dtypestring[1:]
            nleft -= 1
            #assert nleft == 0
        for ii in range(nleft):   # nleft = 0 with present version.
            self.file.readline()
        self.offset = self.file.tell()

    def _write_header(self):
        line = '%d %d %s\n' % (self.ncolumns, self.nl_header, self.name)
        self.file.write(line.encode('ascii'))
        for r in self.columns:
            self.file.write(r.encode('ascii') + b'\n')
        self.byteorder = _sysbyteorder
        line = '%s%s\n' % (self.byteorder, self.type)
        self.file.write(line.encode('ascii'))
        self.file.flush()
        self.offset = self.file.tell()

    def write(self, s):
        nrec = len(s) // self.record_length
        if nrec * self.record_length != len(s):
            raise ValueError(
                "String length %d is not a multiple of record length, %d" %
                                                  (len(s), self.record_length))
        self.file.write(s)
        self.file.flush()
        if 'a' in self.mode:  # always writes to end of file
            self.cursor = int((self.file.tell() - self.offset)
                                                    // self.record_length)
        else:
            self.cursor += nrec
        return nrec

    def seek(self, index, whence=0):
        nrec = self.count()
        if whence == 0:        # relative to start
            irec = index
        elif whence == 1:      # relative to cursor
            irec = self.cursor + index
        elif whence == 2:      # relative to end
            if index > 0:       # index should be negative
                raise IndexError
            irec = nrec + index
        else:
            raise ValueError
        irec = min(irec, nrec)
        irec = max(irec, 0)
        self.file.seek(self.offset + irec * self.record_length)
        self.cursor = irec

    def __next__(self):
        s, n = self.read_n(1)
        if n == 0:
            raise StopIteration
        return s

    def number_to_read(self, n):
        """
        Return the minimum of *n* and the number of available records.

        If in realtime mode, with self.nloops > 0, wait for new records.
        """
        iloop = self.nloops
        n_available = self.count() - self.cursor
        while n_available == 0 and iloop != 0 and self.runflag():
            safesleep(self.interval)
            n_available = self.count() - self.cursor
            iloop -= 1
        if n is None:   # Or we could just set it to a large number.
            n = n_available
        else:
            n = min(n, n_available)
        return n

    def read_n(self, n = None):
        '''Read n records, or to end of file.
           Returns byte string, number of records read.
        '''
        n = self.number_to_read(n)
        s = self.file.read(n * self.record_length)
        self.cursor += n
        return s, n

    def read(self, n = None):
        '''Analogous to file object read; returns available
           file contents up to n records.
           Also see read_n, which will often be more useful.
        '''
        s, n = self.read_n(n)
        return s

    def count(self):
        ''' Return the number of complete records in the file. '''
        if self.mode != 'r':
            self.file.flush()
        nbytes = os.fstat(self.fileno)[stat.ST_SIZE]
        return int((nbytes - self.offset) // self.record_length)

class binfile(binfile_s):
    '''Uses lists for input/output, takes care of byte order'''
    def __init__(self, *args, **kwargs):
        binfile_s.__init__(self, *args, **kwargs)
        self.IOmethod = "list"

    def read_n(self, n = None):
        '''Read n records, or to end of file. '''
        s, nrec = binfile_s.read_n(self, n)
        return struct.unpack(self._fmt % (self.ncolumns * nrec) , s), nrec

    def write(self, rec):
        s = struct.pack(self._fmt % len(rec), *rec)
        return binfile_s.write(self, s)

class binfile_a(binfile_s):
    '''Uses arrays for input/output, does not handle foreign byte order'''
    def __init__(self, *args, **kwargs):
        binfile_s.__init__(self, *args, **kwargs)
        self.IOmethod = "array"

    def read_n(self, n = None):
        '''Read n records, or to end of file. '''
        s, nrec = binfile_s.read_n(self, n)
        a = array.array('d')
        a.frombytes(s)
        return a, n

    def write(self, rec):
        '''this one does not do byte-swapping...'''
        return binfile_s.write(self, rec.tobytes())



####################################################



def main():

    parser = OptionParser()
    parser.add_option("-e", "--ends", action="store_true", dest="ends",
                      help="print first, last record", default=False)
    parser.add_option("-c", "--columns",
                      action="store_true", dest="header", default=False,
                      help="print header, including column labels")

    parser.add_option("-a", "--all",
                      action="store_true", dest="all", default=False,
                      help="print all records")

    (options, args) = parser.parse_args()


    for fn in args:
        b = binfile(fn)
        fmt = " %12.6g" * b.ncolumns
        if options.header:
            print(b)
        if options.ends:
            print(fmt % b.read(1))
            b.seek(-1, 2)
            print(fmt % b.read(1))
        if options.all:
            b.seek(0)
            #for record in b:
            #   print fmt % record
            # The previous method appears to be about as fast as
            # the following; the limiting factor may be the
            # print statement, or it may be that slicing is
            # slow.
            records = b.read()
            nrec = len(records) // b.ncolumns
            for irec in range(0, nrec):
                print(fmt % records[irec*b.ncolumns:(irec+1)*b.ncolumns])

