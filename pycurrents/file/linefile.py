'''
   Modified file class; its next method uses readline() instead
   of the readahead buffer in file.next(), which doesn't work in
   a "tail -f " mode.

   Gzipped files are read transparently.

'''
import os
import stat
from pycurrents.system.misc import sleep as safesleep

class linefile1:
    def __init__(self, filename, mode = 'r',
                 timeout = 0.0, interval = 0.1, keep_running = None):
        fname_base, ext = os.path.splitext(filename)
        if ext == '.gz':
            self.file = os.tmpfile()
            self.file.write(os.popen('zcat %s' % filename).read())
            self.file.seek(0)
        else:
            self.file = open(filename, mode, 1)
        self.filename = filename
        self.mode = mode
        self.fileno = self.file.fileno
        self.tell = self.file.tell
        self.interval = interval
        self.nloops = int(timeout / interval)
        if keep_running is not None:
            self.keep_running = keep_running
        else:
            self.keep_running = lambda : True

    def __iter__(self):
        return self

    def close(self):
        self.file.close()
        self.file = None

    def __next__(self):
        s = self.readline()
        if len(s) == 0:
            raise StopIteration
        return s

    def read_n(self, n = None):
        '''Read n bytes, or to end of file.
           Returns string, number of bytes read.
        '''
        offset = self.tell()
        iloop = self.nloops
        n_available = self.length() - offset
        while n_available == 0 and iloop != 0 and self.keep_running():
            safesleep(self.interval)
            n_available = self.length() - offset
            iloop -= 1
        if n is None:   # Or we could just set it to a large number.
            n = n_available
        else:
            n = min(n, n_available)
        s = self.file.read(n)
        return s, n

    def read(self):
        s, n = self.read_n()
        return s

    def readline(self):
        offset = self.tell()
        iloop = self.nloops
        n_available = self.length() - offset
        while n_available == 0 and iloop != 0 and self.keep_running():
            safesleep(self.interval)
            n_available = self.length() - offset
            iloop -= 1
        if n_available == 0:
            return ''
        s = self.file.readline()
        return s

    def readlines(self):
        offset = self.tell()
        iloop = self.nloops
        n_available = self.length() - offset
        while n_available == 0 and iloop != 0 and self.keep_running():
            safesleep(self.interval)
            n_available = self.length() - offset
            iloop -= 1
        if n_available == 0:
            return ''
        lines = self.file.readlines()
        return lines

    def length(self):
        nbytes = os.fstat(self.fileno())[stat.ST_SIZE]
        return nbytes

class linefile2s(linefile1):
    ''' Return lines a pair at a time, synchronizing by matching
        a string at the start of the first line.  The synchronization
        string is given by the kwarg 'sync'.  A KeyError will be
        raised if the kwarg is not supplied.
    '''
    def __init__(self, *args, **kwargs):
        self.sync = kwargs.pop('sync')
        linefile1.__init__(self, *args, **kwargs)
        self.lines = []

    def update(self):
        new = self.readlines()
        if len(new) == 0:
            return
        ii = len(self.lines)
        for line in new:
            if ii % 2 == 1 or line.startswith(self.sync):
                self.lines.append(line)
                ii += 1


    def read_record(self):
        if len(self.lines) < 2:
            self.update()
        if len(self.lines) < 2:
            return []
        rec = self.lines[:2]
        del(self.lines[:2])
        return rec

    def read_records(self, n = None):
        '''This may be of little use; or perhaps it should
           return a list of pairs, or a pair of lists...
        '''
        if len(self.lines) < 2:
            self.update()
        if len(self.lines) < 2:
            return []
        nrec = len(self.lines) // 2
        if n is not None:
            nrec = min(n, nrec)
        rec = self.lines[:(2*nrec)]
        del(self.lines[:(2*nrec)])
        return rec

    def __next__(self):
        rec = self.read_record()
        if len(rec) == 0:
            raise StopIteration
        return rec



class linefile2(linefile1):
    ''' Return lines a pair at a time.
    '''
    def __init__(self, *args, **kwargs):
        linefile1.__init__(self, *args, **kwargs)
        self.lines = []

    def update(self):
        self.lines += self.readlines()
        if len(self.lines) % 2 == 1:
            self.lines += self.readlines()

    def read_record(self):
        if len(self.lines) < 2:
            self.update()
        if len(self.lines) < 2:
            return []
        rec = self.lines[:2]
        del(self.lines[:2])
        return rec

    def read_records(self, n = None):
        '''This may be of little use; or perhaps it should
           return a list of pairs, or a pair of lists...
        '''
        if len(self.lines) < 2:
            self.update()
        if len(self.lines) < 2:
            return []
        nrec = len(self.lines) // 2
        if n is not None:
            nrec = min(n, nrec)
        rec = self.lines[:(2*nrec)]
        del(self.lines[:(2*nrec)])
        return rec

    def __next__(self):
        rec = self.read_record()
        if len(rec) == 0:
            raise StopIteration
        return rec
