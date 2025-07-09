'''
   Modified file class; its next method uses readline() instead
   of the readahead buffer in file.next(), which doesn't work in
   a "tail -f " mode.

    All output is in bytes, not strings.

   Gzipped files are read transparently (unix only; this should
   be modified to use python gzip module if zcat is unavailable).

'''
import os
import tempfile
import subprocess

from pycurrents.file.pyfiletail import Filetail
from pycurrents.system.misc import sleep as safesleep

class linefile1:
    def __init__(self, filename,
                 timeout = 0.0, interval = 0.1, keep_running = None):
        fname_base, ext = os.path.splitext(filename)
        self.file = Filetail()
        if ext == '.gz':
            temp_fd, temp_fname = tempfile.mkstemp()
            fobj = os.fdopen(temp_fd)
            subprocess.call(['zcat', filename], stdout=fobj)
            fobj.close()
            self.file.open(temp_fname)   # Filetail will rewind it.
            self.temp_fname = temp_fname
        else:
            self.file.open(filename)
            self.temp_fname = None
        self.filename = filename
        self.interval = interval
        self.nloops = max(1, int(timeout / interval))
        if keep_running is not None:
            self.keep_running = keep_running
        else:
            self.keep_running = lambda : True

    def __iter__(self):
        return self

    def close(self):
        self.file.close()
        self.file = None
        if self.temp_fname is not None:
            os.remove(self.temp_fname)
            self.temp_fname = None

    def __next__(self):
        s = self.file.readline()
        if len(s) == 0:
            raise StopIteration
        return s

    def read_n(self, n):
        '''Read n bytes.
           Returns bytestring, number of bytes read.
        '''
        s = ''
        n_to_read = n
        for ii in range(self.nloops):
            if ii > 0: 
                safesleep(self.interval)
            ss = self.file.read(n_to_read)
            ns = len(ss)
            if ns > 0:
                s += ss
                n_to_read -= ns
            if n_to_read <= 0 or not self.keep_running():
                break
        return s, len(s)


    def readline(self):
        s = ''
        for ii in range(self.nloops):
            if ii > 0: 
                safesleep(self.interval)
            s = self.file.readline()
            if s or not self.keep_running():
                break
        return s

    def readlines(self):
        lines = []
        for ii in range(self.nloops):
            if ii > 0: 
                safesleep(self.interval)
            lines = self.file.readlines()
            if lines or not self.keep_running():
                break
        return lines


class linefile2s(linefile1):
    ''' Return lines a pair at a time, synchronizing by matching
        a string at the start of the first line.  The synchronization
        string, or sequence of strings, is given by the kwarg 'sync'.
        A KeyError will be
        raised if the kwarg is not supplied.
    '''
    def __init__(self, *args, **kwargs):
        sync = kwargs.pop('sync')
        if not isinstance(sync, (tuple, list)):
            sync = [sync]
        sync = [bytes(entry, 'ascii') for entry in sync]
        self.sync = sync
        linefile1.__init__(self, *args, **kwargs)
        self.lines = []

    def update(self):
        new = self.readlines()
        if len(new) == 0:
            return
        ii = len(self.lines)
        for line in new:
            if ii % 2 == 1 or any([line.startswith(entry)
                                    for entry in self.sync]):
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
