
''' Read and (when implemented) write flat ascii numeric files.

    This might be extended to handle comment lines, etc,
    but at present it is a minimal version.
    (Right now: a *very* minimal read iterator,
    with no write support.)

    Note that the entire file contents are kept in memory
    as a list of lines, so this class is not appropriate for
    enormous files.  If the file is not changing in time,
    then the entire file is read upon the first access to
    a record.

    Note 2: ascfile is being used right now in DAS_speedlog.py,
    and while it is, it is necessary to use "open" with only
    one argument so that it works with Filetail as well as with
    regular open.  This is no problem, because the only possible
    mode is 'r' anyway, and that is the default with "open".
    Longer term, the speedlog should not be using this module
    at all. It is not clear whether the module will actually be
    used for anything at all in anything like its present form.
    2008/01/05

'''

# EF 2004/10/01

class ascfile:
    def __init__(self, filename, mode = 'r', ncolumns = 0, open=open):
        self.filename = filename
        self.mode = mode
        self.file = open(filename)  ## see note 2 in docstring
        self.ncolumns = ncolumns
        self.filename = filename
        if mode[0] != 'r':
            assert ncolumns > 0
        self.cursor = 0
        self.lines = []

    def __iter__(self):
        return self

    def __str__(self):
        if self.mode[0] != 'r':
            lines = ['filename: %s' % self.filename,
                     'mode:     %s' % self.mode,
                     'ncolumns: %d' % self.ncolumns]
            s = '\n'.join(lines)
            return s
        cursor = self.cursor
        self.seek(-1, 2)
        nrec = self.cursor + 1
        self.seek(cursor, 0)
        lines = ['filename: %s' % self.filename,
                 'mode:     %s' % self.mode,
                 'ncolumns: %d' % self.ncolumns,
                 'nrecords: %d' % nrec,
                 'cursor:   %d' % self.cursor]
        s = '\n'.join(lines)
        return s

    def close(self):
        '''Close the file; this may not be very useful.
        Any subsequent operations will generate an error,
        unless we modify the class so that it can keep
        getting lines from self.lines after the file is
        closed.
        '''
        self.file.close()
        self.file = None

    def __next__(self):
        self.lines += self.file.readlines()
        if self.cursor >= len(self.lines):
            raise StopIteration
        fields = self.lines[self.cursor].split()
        self.cursor += 1
        if self.ncolumns == 0:
            self.ncolumns = len(fields)
        return [float(f) for f in fields]

    def seek(self, index, whence=0):
        self.lines += self.file.readlines()
        nrec = len(self.lines)
        if whence == 0:
            irec = index
        elif whence == 1:
            irec = self.cursor + index
        elif whence == 2:
            if index > 0:
                raise IndexError
            irec = nrec + index
        else:
            raise ValueError
        irec = min(irec, nrec)
        irec = max(irec, 0)
        self.cursor = irec
