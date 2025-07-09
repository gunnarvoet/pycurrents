import glob
import copy

class MissingFileError(Exception):
    pass

class fileglob:

    def __init__(self, glob_pattern, open_function = open, verbose=0):
        self.glob_pattern = glob_pattern
        self.open = open_function
        self.verbose = verbose
        self.filelist = []
        self.nfiles = 0
        self.ifile = -1     # Points to the open file
        self.file = None   # This will be whatever is returned by open_function.
        self.refresh_filelist()

    def __iter__(self):
        return(self)

    def refresh_filelist(self):
        fl = glob.glob(self.glob_pattern)
        fl.sort()
        if fl[:self.nfiles] != self.filelist:
            raise MissingFileError
        n_new = len(fl) - self.nfiles
        if n_new and self.verbose >= 2:
            print(fl)
        self.filelist = fl
        self.nfiles = len(fl)
        return n_new

    def next_file(self):
        self.refresh_filelist()
        if self.nfiles == 0:
            return 0
        if self.ifile + 1 < self.nfiles:
            if self.file:
                self.file.close()
            self.ifile += 1
            if self.verbose:
                print(self.filelist[self.ifile])
            self.file = self.open(self.filelist[self.ifile])
            return 1
        return 0

    def __next__(self):
        # Start by trying what should usually work:
        try:
            return next(self.file)
        except:
            pass
        if self.next_file():
            try:
                return next(self.file)
            except:
                pass
        raise StopIteration
        # It is possible that we need to deal with IOError separately,
        # so as to give notice if there are permission problems, for
        # example.

    def last_file(self):
        self.refresh_filelist()
        if self.nfiles == 0:
            return 0
        if self.ifile + 1 < self.nfiles:
            if self.file:
                self.file.close()
            self.ifile = self.nfiles - 1
            if self.verbose:
                print(self.filelist[self.ifile])
            self.file = self.open(self.filelist[self.ifile])
            return 1
        return 0

    def end_of_stream(self):
        if self.last_file():
            for r in self:
                pass

    def find_file(self, substring):
        self.refresh_filelist()
        if self.nfiles == 0:
            return 0
        for i, fn in enumerate(self.filelist):
            if fn.find(substring) >= 0:
                if self.file:
                    self.file.close()
                self.ifile = i
                if self.verbose:
                    print(self.filelist[self.ifile])
                self.file = self.open(self.filelist[self.ifile])
                return 1
        return 0

    def filename(self):
        if self.file:
            return self.filelist[self.ifile]
        else:
            return ''

class fileglob2(fileglob):
    '''Allow files to fall off the bottom of the list; for
    example, the older files might be gzipped so they no longer
    match the glob.
    '''
    def refresh_filelist(self):
        fl = glob.glob(self.glob_pattern)
        fl.sort()
        n_dropped = 0
        if self.nfiles > 0:
            f_last = self.filelist[-1]
            imatch = None
            for i in range(min(self.nfiles, len(fl)) - 1, -1, -1):
                if fl[i] == f_last:
                    imatch = i
                    break
            if imatch is None:
                raise MissingFileError
            n_dropped = self.nfiles - 1 - imatch
        n_new = len(fl) + n_dropped - self.nfiles
        if n_new and self.verbose >= 2:
            print(fl)
        self.ifile -= n_dropped
        self.filelist = fl
        self.nfiles = len(fl)
        return n_new

def strip_gz(fl):
    fl_new = copy.deepcopy(fl)
    for i, f in enumerate(fl_new):
        if f.endswith('.gz'):
            fl_new[i] = f[:-3]
    return fl_new


class fileglob3(fileglob):
    '''As above, but ignore any .gz suffix.
    '''
    def refresh_filelist(self):
        fl = glob.glob(self.glob_pattern)
        fl.sort()
        fl_new = strip_gz(fl)
        n_dropped = 0
        if self.nfiles > 0:
            f_last = self.filelist[-1]
            if f_last.endswith('.gz'):
                f_last = f_last[:-3]
            imatch = None
            for i in range(min(self.nfiles, len(fl)) - 1, -1, -1):
                if fl_new[i] == f_last:
                    imatch = i
                    break
            if imatch is None:
                raise MissingFileError
            n_dropped = self.nfiles - 1 - imatch
        n_new = len(fl) + n_dropped - self.nfiles
        if n_new and self.verbose >= 2:
            print(fl)
        self.ifile -= n_dropped
        self.filelist = fl
        self.nfiles = len(fl)
        return n_new
