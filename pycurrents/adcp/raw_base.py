"""
Function and classes with minimal dependencies, used in RDI and Simrad raw file
reading.

"""

import logging
import os
from pathlib import Path
import stat

import numpy as np

__all__ = [
    "make_ilist",
    "Bunch",
    "PrettyTuple",
    "IncompleteFileError",
    "FileBase",
]


_log = logging.getLogger(__name__)


def make_ilist(nprofs, start=None, stop=None, step=None, ilist=None, ends=None):
    """
    Generate a new or modified list of indices, first by
    slicing, then by taking the ends if *ends* is not *None*.

    In any case, the highest index will be less than *nprofs*,
    and the lowest will be greater than or equal to zero.

    *ilist*, if given, is assumed to be sorted.

    Returns an ndarray, which may be empty.
    """
    if ilist is not None:
        ilist = np.asarray(ilist)[slice(start, stop, step)]
        i0 = np.searchsorted(ilist, 0)
        i1 = np.searchsorted(ilist, nprofs)
        out = ilist[i0:i1]
    else:
        sss = slice(start, stop, step).indices(nprofs)
        out = np.arange(sss[0], sss[1], sss[2], dtype=int)

    if ends is None:
        return out
    else:
        n = len(out)
        ie = np.array(list(range(ends)) + list(range(n - ends, n)), dtype=int)
        return out[ie]


class Bunch(dict):
    """
    A dictionary that also provides access via attributes.

    This version is specialized for this module; see also
    the version in pycurrents.system.misc, which has extra
    methods for handling parameter sets.
    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self)
        self.__dict__ = self
        for arg in args:
            self.__dict__.update(arg)
        self.__dict__.update(kwargs)

    def __str__(self):
        ## fix the formatting later
        slist = ["Dictionary with access to the following as attributes:"]
        keystrings = [str(key) for key in self.keys()]
        slist.append("\n".join(keystrings))
        return "\n".join(slist) + "\n"

    def split(self, var):
        """
        Method specialized for splitting velocity etc. into
        separate arrays for each beam.
        """
        n = self[var].shape[-1]
        for i in range(n):
            self["%s%d" % (var, i + 1)] = self[var][..., i]

    @classmethod
    def from_structured(klass, a):
        b = klass()
        for name in a.dtype.names:
            try:
                setattr(b, name, a[name][0])
            except:
                _log.warning("name is %s, a is %s", name, a)
                raise
        return b


class PrettyTuple(tuple):
    """
    Class to make tuples that print nicely, by applying the str()
    function to each element.  Otherwise, it prints like a normal
    tuple, complete with parentheses.
    """

    def __str__(self):
        return "(%s)" % (", ".join([str(x) for x in self]),)


class IncompleteFileError(Exception):
    pass


class FileBase:
    class Header:
        pass

    def __init__(self, fname, inst=None, trim=True, yearbase=None):
        """
        Make and open a raw data file reader.

        Arguments:

            *fname*
                file name

            *inst*
                instrument type, one of 'nb', 'wh', 'bb', 'os', 'pn', 'ec', or None
                If None, the file opening and potential trimming
                will not be done; it will be up the the subclass
                to open the file and determine the instrument type.

        Keyword arguments:

            *trim*
                default is True, so based on a sanity check,
                junk at the end of the file will be trimmed off.
                Set to False to disable this.  The trim() method
                can still be run later if desired.

            *yearbase*
                required for 'nb'

        """
        self.fname = str(Path(fname).resolve())  # Or switch to using Path?
        self.inst = inst
        self.yearbase = yearbase
        self.header = self.__class__.Header()
        self.nprofs = 0
        self.nbadend = 0  # updated by trim()
        self.fobj = None

        if inst is not None:
            self.open()
            if trim and self.opened:
                self.trim()

    def trim(self):
        pass

    def __str__(self):
        if not self.opened:
            return "Raw data file %s is closed" % (self.fname,)
        slist = ["Raw %s data file %s" % (self.inst, self.fname)]
        slist.append("    %d records" % self.nprofs)
        slist.append("    first time: %s" % self.dtstr)
        slist.append("    Variables:")
        vnames = list(self.available_varnames)  # copy, so we don't change it
        vnames[0] = "        " + vnames[0]
        slist.append("\n        ".join(vnames))
        if self.inst == "os":  # For "ec" also?
            slist.append("    pingtypes: " + " ".join(list(self.pingtypes.keys())))
        return "\n".join(slist) + "\n"

    @staticmethod
    def configtuple(dparamdict, ping="nb"):
        """
        Return a tuple identifying a configuration.

        A minimal set of parameters is used to decide whether
        files are similar enough to be concatenated.

        To accomodate the os, with its odd pulse lengths, a
        nominal pulse length is generated.
        """
        dd = dparamdict
        cell = dd["CellSize"]
        pulse = dd["Pulse"]
        # The outer round is needed with Py3 to get a nice result with str().
        pulse = round(round(pulse / cell, 1) * cell, 3)
        return PrettyTuple((ping, dd["NCells"], cell, dd["Blank"], pulse))

    def open(self):
        try:
            self.fobj = open(self.fname, "rb")
            self.header.read(self.fobj)
            self.refresh_nprofs()
            self.fobj.seek(0)
            self.opened = True
        except IncompleteFileError:
            self.fobj.close()
            self.fobj = None
            self.opened = False

    def close(self):
        """
        Close the file.
        """
        if self.fobj is not None:
            self.fobj.close()
            self.fobj = None
        self.opened = False  # could be used for nicer error reporting
        # but this is probably not necessary.

    def refresh_nprofs(self):
        """
        Calculate number of profiles in file based on file size.
        """
        s = os.stat(self.fname)
        self.nprofs = s[stat.ST_SIZE] // self.header.nbytes
        if self.nprofs < 1:
            raise IncompleteFileError

    def get_ens(self, ind):
        if hasattr(self, "starts"):
            i0 = self.starts[ind]
            n = self.lengths[ind]
        else:
            i0 = ind * self.header.nbytes
            n = self.header.nbytes
        self.fobj.seek(i0)
        return self.fobj.read(n)  # maybe raise if len != n
