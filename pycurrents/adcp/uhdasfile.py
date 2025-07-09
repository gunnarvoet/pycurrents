
'''
dictionaries
-------------
    binfile_ddayalias    # so binfiles will have consistent names
    pingtype_dict        # dict: instrument --> possible ping types

    heading_msgdict      # dict: directory --> acceptable messages
    heading_synonyms     # dict: attitude directory sysnonyms

filename utilities
-----------------------

    attmsg_from_dir     # get the first good attitude msg type in dir
    parse_filename      # extract shipabbrev, year, day, seconds
    msg_in_rbindir      # return list of messages found

'''

import os
import logging

import pycurrents.system.pathops as pathops
from pycurrents.adcp.adcp_specs import Sonar

# Standard logging
_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)

#----------------------------


binfile_ddayalias = {'monotonic_dday': 'm_dday',
                     'unix_dday'     : 'u_dday'}


#---------------

# This list provides the connection between generic directory
# names, attitude messages that might occur in that directory,
# and other (historical) directory names
#
#    directory  ,   messages     ,    other directory names
#     (string)       (list)             (list)
headingmsg = [
    ['posmv',   ['pmv'],                ['posmv', 'posmv1', 'posmv2']],
    ['seapath', ['sea'],                ['seapath', 'seapath2',
                                         'seapath200','seapath330']],
    ['ashtech', ['att', 'adu',
                 'at2', 'paq'],
                                        ['ashtech',
                                         'adu', 'adu2', 'adu5',
                                         'ashpaq', 'ashpaq2', 'ashpaq5',
                                         'adu_at2']],
    ['csi'    , ['psathpr', 'hdg'],     ['csi']],
    ['gyro'   , ['hdg', 'hdt',  'hnc'], ['gyro', 'gyro1', 'gyro2']],
    ['mahrs'  , ['tss1', 'hnc_tss1',
                 'hdg_tss1'],           ['mahrs']],
    ['phins'  , ['hdg'],                ['phins']],
    ['hydrins', ['hdg'],                ['hydrins']],
    ['unknown', ['rdi'],                ['mahrs']],  ## see note
    ]

## rdi is likely to cause trouble, but at least sometimes it will work.

qchcorr_devices = ['adu_at2', 'ashpaq2', 'ashpaq5', 'ashtech',
                   'seapath', 'posmv', 'coda_f185',
                   'mahrs']

def check_hdgmsg_syntax(hdict):
    '''
    make sure values in dictionary are all iterable
    '''
    for kk, mm in hdict.items():
        if isinstance(mm, str):
            hdict[kk]=[mm,]
            _log.warning('redefining string %s as [%s,]' % (mm, mm))
        elif not isinstance(mm, (list, tuple)):
            _log.critical('dictionary key %s has bad value' % (mm))
            # TODO : Don't we need to raise an Exception here?



heading_msgdict  = dict([(x[0], x[1]) for x in headingmsg])
heading_synonyms = dict([(x[0], x[2]) for x in headingmsg])
check_hdgmsg_syntax(heading_msgdict)
check_hdgmsg_syntax(heading_synonyms)

# key is synonym; value is standard instrument name
syn_to_inst = dict()
for std, msgs, syns in headingmsg:
    for s in syns:
        syn_to_inst[s] = std  #standard directory name

#======= filename utilities ===========

def attmsg_from_dir(rbindir, headdir):
    '''
    returns the first appropriate attitude msg in cruisedir/rbin/dir
    order of "appropriate" is specified in heading_msg[dir]
    '''
    rbin_hdir = os.path.join(rbindir, headdir)
    found_msglist = msg_in_rbindir(os.path.join(rbin_hdir, '*rbin'))

    if len(found_msglist) == 1:
        return found_msglist[0]

    inst = syn_to_inst[headdir]
    allowed_messages = heading_msgdict[inst]
    for msg in allowed_messages: #i.e. in order
        if msg in found_msglist:
            return msg

    return None

#---------------

def parse_filename(fname):
    """
    Given any UHDAS file name, return:
        + shipabbrev (two-character string)
        + year (int)
        + day  (int, zero-based)
        + seconds (int)

    Extensions and paths are ignored.
    """
    fname = os.path.split(fname)[1]
    fbase = fname.split('.')[0]
    sy, d, s = fbase.split('_')
    shipabbrev = sy[:-4]
    year = int(sy[-4:])
    day = int(d)
    seconds = int(s)
    return shipabbrev, year, day, seconds


def msg_in_rbindir(rlist):
    '''
    input: list or glob of rbin files
    output: the messages found (a list)
    '''
    rmessages = set()
    for rfile in pathops.make_filelist(rlist):
        try:
            e1, e2 = os.path.split(rfile)[-1].split('.')[-2:]
            if e2 == 'rbin':
                rmessages.add(e1)
        except IndexError:
            # Don't fail if some miscellaneous file is in the
            # directory.
            pass
    return list(rmessages)


def _guess_dbname(dirname):
    '''
    walks from specified directory; returns dbname if found, or None
    '''
    dbnames = []
    for dirpath, dirnames, filenames in os.walk(dirname,
                                                topdown=False,
                                                followlinks=True):
        for fn in filenames:
            if fn.lower()[-7:] == 'dir.blk':
                fullname = os.path.join(dirpath, fn)
                dbnames.append(fullname)
    if len(dbnames) == 1:
        return dbnames[0][:-7]
    elif len(dbnames) == 0:
        raise IOError(
            'Could not find database (*.blk) using "%s"' % dirname)
    else:
        raise Exception(
            "Folder structure corrupted. Several databases were found: "
            + ", ".join(dbnames))


def guess_dbname(name_or_path):
    '''
    return dbname (or path) by parsing the input as one of
      - a directory (assumed to contain one database)
      - the path and dbname (strip "dir.blk" if present)
    '''
    if os.path.isfile(name_or_path + 'dir.blk'):
        return name_or_path
    elif name_or_path[-7:] == 'dir.blk':
        return name_or_path[:-7]
    # backing up by one, in case we're in edit/ dir
    elif os.path.isdir(name_or_path):
        parts = os.path.split(os.path.abspath(name_or_path))
        if parts[1] == "edit" and os.path.isdir(parts[0]):
            name_or_path = parts[0]

    return _guess_dbname(name_or_path)


class UHDAS_Tree:
    """
    Generate standard UHDAS directory tree, with overrides.

    It provides attributes (properties) with directories,
    and methods for making full paths, globs, etc.

    Example:

        from pycurrents.adcp.uhdasfile import UHDAS_Tree

        t = UHDAS_Tree("/home/data/cruise", "os38nb")
        print t
        t.gbin = "some/other"  # override an attribute
        print t
        # override at initialization with kwargs
        t = UHDAS_Tree("/home/data/cruise", "os38nb", gbin="yet/another")
        print t
        t.procsonarpath("load")
        #'/home/data/cruise/proc/os38nb/load'
        t.procsonarpath("cal", "rotate")
        # etc.

    """
    def __init__(self, cruisedir, sonar, **kw):
        sonar = Sonar(sonar)
        self.sonar = sonar
        self.cruisedir = cruisedir
        self._gbinsonar = None
        self._gbinheading = None
        self._gbin = None
        self._rawsonar = None
        self._raw = None
        self._proc = None
        self._procsonar = None
        self._rbin = None
        for key, val in kw.items():
            setattr(self, "_%s" % key, val)

    def __str__(self):
        lines = ["UHDAS directory tree access based on cruisedir:",
                 "   %s" % self.cruisedir,
                 "and sonar:",
                  "  %s\n" % self.sonar,
                  "gbin          = %s" % self.gbin,
                  "gbinsonar     = %s" % self.gbinsonar,
                  "gbinheading   = %s" % self.gbinheading,
                  "raw           = %s" % self.raw,
                  "rawsonar      = %s" % self.rawsonar,
                  "rbin          = %s" % self.rbin,
                  "proc          = %s" % self.proc,
                  "procsonar     = %s" % self.procsonar,
                  "",
                  ]

        return "\n".join(lines)

    def get_gbin(self):
        if self._gbin is None:
            return os.path.join(self.cruisedir, "gbin")
        else:
            return self._gbin

    def set_gbin(self, d):
        self._gbin = d

    gbin = property(get_gbin, set_gbin)

    def get_gbinsonar(self):
        if self._gbinsonar is None:
            return os.path.join(self.gbin, self.sonar.instname)
        else:
            return self._gbinsonar

    def set_gbinsonar(self, d):
        self._gbinsonar = d

    gbinsonar = property(get_gbinsonar, set_gbinsonar)

    def get_gbinheading(self):
        if self._gbinheading is None:
            return os.path.join(self.gbin, "heading")
        else:
            return self._gbinheading

    def set_gbinheading(self, d):
        self._gbinheading = d

    gbinheading = property(get_gbinheading, set_gbinheading)


    def get_raw(self):
        if self._raw is None:
            return os.path.join(self.cruisedir, "raw")
        else:
            return self._raw

    def set_raw(self, d):
        self._raw = d

    raw = property(get_raw, set_raw)

    def get_rawsonar(self):
        if self._rawsonar is None:
            return os.path.join(self.raw, self.sonar.instname)
        else:
            return self._rawsonar

    def set_rawsonar(self, d):
        self._rawsonar = d

    rawsonar = property(get_rawsonar, set_rawsonar)

    def get_proc(self):
        if self._proc is None:
            return os.path.join(self.cruisedir, "proc")
        else:
            return self._proc

    def set_proc(self, d):
        self._proc = d

    proc = property(get_proc, set_proc)


    def get_procsonar(self):
        '''
        allow os75 (in addition to os75bb and os75nb) for "mixed_pings"
        '''
        if self._procsonar is None:
            if self.sonar.model in ('os', 'pn'):
                try:
                    return os.path.join(self.proc, self.sonar.sonar)
                except AttributeError:
                    return os.path.join(self.proc, self.sonar.instname)
            else:
                return os.path.join(self.proc, self.sonar.sonar)
        else:
            return self._procsonar

    def set_procsonar(self, d):
        self._procsonar = d

    procsonar = property(get_procsonar, set_procsonar)

    def get_rbin(self):
        if self._rbin is None:
            return os.path.join(self.cruisedir, "rbin")
        else:
            return self._rbin

    def set_rbin(self, d):
        self._rbin = d

    rbin = property(get_rbin, set_rbin)

    def gbinpath(self, *args):
        return os.path.join(self.gbin, *args)

    def gbinsonarpath(self, *args):
        return os.path.join(self.gbinsonar, *args)

    def gbinheadingpath(self, *args):
        return os.path.join(self.gbinheading, *args)

    def rawsonarpath(self, *args):
        return os.path.join(self.rawsonar, *args)


    def procpath(self, *args):
        return os.path.join(self.proc, *args)


    def procsonarpath(self, *args):
        return os.path.join(self.procsonar, *args)

    def rbinpath(self, *args):
        return os.path.join(self.rbin, *args)
