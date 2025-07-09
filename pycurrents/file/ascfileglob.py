
'''
This is almost a copy of binfileglob; the two need to be reorganized
with subclassing and consolidated in a single file.

Caution: I put in a third argument for line buffering in the open
call; this may require changes elsewhere if anything but the
default open function is to be used.
'''
from pycurrents.system.pathops import corresponding_pathname, filename_base
import glob

class out_ascfileglob:
    def __init__(self, fileglob, dir = './', ext = '', open_function = None):
        self.fileglob = fileglob
        self.dir = dir
        self.ext = ext
        if open_function:
            self.open = open_function
        else:
            self.open = open
        self.outfilename = ''
        self.lastinfilename = ''
        self.outfile = None
        glob_base = filename_base(self.fileglob.glob_pattern)
        self.glob_pattern = corresponding_pathname(glob_base, self.dir, self.ext)

    def close(self):
        if self.outfile:
            self.outfile.close()

    def get_filelist(self):
        fl = glob.glob(self.glob_pattern)
        fl.sort()
        return fl

    def new_filename(self):
        infile = self.fileglob.filename()
        if self.lastinfilename == infile:
            return 0
        self.lastinfilename = infile
        self.outfilename = corresponding_pathname(infile, self.dir, self.ext)
        return 1

    def write(self, record):
        if self.new_filename():
            if self.outfile:
                self.outfile.close()
            self.outfile = self.open(self.outfilename, 'w', 1) #1 for line buffering
        if self.outfile:
            self.outfile.write(record)
