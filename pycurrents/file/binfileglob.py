from pycurrents.system.pathops import corresponding_pathname, filename_base
import glob
from pycurrents.file.binfile import binfile

class out_binfileglob:
    def __init__(self, fileglob, dir = './', ext = '',
                   name = '', columns = []):
        self.fileglob = fileglob
        self.dir = dir
        self.ext = ext
        self.name = name
        self.columns = columns
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

    def write(self, row):
        if self.new_filename():
            if self.outfile:
                self.outfile.close()
            self.outfile = binfile(self.outfilename, 'w',
                                    self.name, self.columns)
        if self.outfile:
            self.outfile.write(row)
