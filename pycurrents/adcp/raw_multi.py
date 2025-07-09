'''
Functions and a class (Multiread) for reading one or more files of raw
(single-ping) data from RDI or Simrad ADCPs.
'''

import os
from pathlib import Path
import pickle

import numpy as np
import logging

from pycurrents.system import pathops
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.file.binfile_n import BinfileSetCache
from pycurrents.adcp.transform import Transform
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp.raw_rdi import FileBBWHOS
from pycurrents.adcp.raw_rdi import FileNB
from pycurrents.adcp import raw_simrad
from pycurrents.adcp.raw_simrad import FileSimradEC


from pycurrents.adcp.raw_base import (
        Bunch,
        make_ilist,
        )


__all__ = [
    "rawfile",
    "rawread",
    "extract_raw",
    "Multiread",
]

# Standard logging
_log = logging.getLogger(__name__)


def rawfile(fname, sonar, trim=False, yearbase=None):
    '''
    Factory function to return an appropriate raw file reader
    '''
    sonar = Sonar(sonar)
    if sonar.isa('wh', 'bb', 'os', 'sv', 'pn'):
        return FileBBWHOS(fname, sonar, trim, yearbase)
    elif sonar.isa('nb'):
        if yearbase is None:
            raise ValueError("yearbase is required for nb instrument")
        return FileNB(fname, yearbase)
    elif sonar.isa('ec'):
        return FileSimradEC(fname, sonar, trim, yearbase)
    else:
        raise ValueError("unrecognized sonar, %s", sonar)

def rawread(fnames, inst, yearbase=None, ibad=None, beam_index=None, **kw):
    """
    Read one or more raw data files.

    *fnames* can be a single filename or a list.

    *inst* and *yearbase* are passed to rawfile

    keywords are passed to the read method.

    *ibad* is a zero-based index of a beam to be excluded from
    beam_to_xyz.

    *beam_index* is a list of integers [0,1,2,3] in the order
    Example using q_demos/uhdas/data/raw/nb150::

        ppd = rawread(['kk2005_336_57600.raw', 'kk2005_336_64800.raw'],
                    'nb', yearbase=2005)

    The Bunch object returned is like that from the read method of
    FileNB or FileBBWHOS, but without the 'raw' attribute.

    In most cases one will use the Multiread class below instead of
    this rawread function.

    """
    if len(fnames[0]) == 1:
        return rawfile(fnames, inst, yearbase=yearbase).read(**kw)

    ppdlist = []
    for f in fnames:
        ppdlist.append(rawfile(f, inst, yearbase=yearbase).read(**kw))

    ppd = _process_ppdlist(ppdlist, ibad=ibad, beam_index=beam_index)
    return ppd

def _process_ppdlist(ppdlist, ibad=None, beam_index=None):
    '''
    ppdlist is a list of chunks of raw PD0 or EC datagram data
    ibad is the zero-based index for a bad beam
    beam_index is a list with a permutation of beams [0,1,2,3]
       - if RDI got the beams in the wrong order in the transducer
         this is the correct mapping
    '''
    ppd = Bunch()
    p0 = ppdlist[0]
    # ignore the convenience variables such as vel1, vel2...
    vars = [k for k in p0 if k[-1] not in ['1', '2', '3', '4']]
    for k in vars:
        if k == 'dep' or k=='rVL' or not isinstance(p0[k], np.ndarray):
            continue
        chunks = [p[k] for p in ppdlist]
        if np.ma.isMaskedArray(chunks[0]):
            ppd[k] = np.ma.concatenate(chunks)
        else:
            ppd[k] = np.concatenate(chunks)
        if ppd[k].ndim == 3:
            ppd.split(k)
    ppd['rVL'] = ppd['VL'].view(np.recarray)
    ppd['dep'] = p0['dep']
    ppd['nprofs'] = len(ppd['rVL'])
    ppd['nbins'] = len(ppd['dep'])
    # For now we are assuming the scalar variables are the same for
    # all files; probably we should be checking this.
    for k in vars:
        # grabbing scalars from first chunk
        if k != 'raw' and not isinstance(p0[k], np.ndarray):
            ppd[k] = p0[k]
    try:
        if ppd.trans.coordsystem == 'beam':
            if ppd.sysconfig.convex:
                geom = 'convex'
            else:
                geom = 'concave'
            trans = Transform(angle=ppd.sysconfig.angle,
                              geometry=geom)
            if beam_index:
                if 'vel' in ppd:
                    ppd.vel[:] = ppd.vel[..., beam_index]
                    ppd.bt_vel[:] = ppd.bt_vel[..., beam_index]
                    ppd.bt_depth[:] = ppd.bt_depth[..., beam_index]
                if 'amp' in ppd:
                    ppd.amp[:] = ppd.amp[..., beam_index]
                if 'cor' in ppd:
                    ppd.cor[:] = ppd.cor[..., beam_index]
            if 'vel' in ppd:
                ppd.xyze = trans.beam_to_xyz(ppd.vel, ibad=ibad)
                ppd.bt_xyze = trans.beam_to_xyz(ppd.bt_vel, ibad=ibad)
    except AttributeError:
        pass

    if ppd.sonar.isa('ec'):
        if 'vel' in ppd:
            ppd.xyde = raw_simrad.beam_to_xyde(ppd.vel, ppd.sysconfig['angle'])
            ppd.xyze = raw_simrad.xyde_to_xyze(ppd.xyde)
            ppd.bt_xyze = ppd.bt_vel  # Dummy; it's all bad anyway
    return ppd


def extract_raw(infile, inst, i0, i1, outfile=None):
    '''
    extract pings from python-indexed slice(i0,i1,1) of infile
    'inst' is 'ec', 'sv', 'wh', 'bb, 'os', 'pn', or 'nb'
    optionally write to 'outfile'
    returns data

    This is used in the cut_raw_adcp.py script.
    '''
    yearbase = None
    if inst == 'nb':
        yearbase = 2000  # dummy value; it will not affect the output

    rf = rawfile(infile, inst, trim=True, yearbase=yearbase)
    _log.info("%s has %d profiles", infile, rf.nprofs)

    ii = np.arange(rf.nprofs)[i0:i1]

    if hasattr(rf, "starts"):
        # This is not exactly right for 'sv' if i0 != 0.  It should be ensuring that
        # the "Feature Data" structure is at the start of each file, but we
        # are not yet supporting that structure, or any of the 0x7000 series.
        istart = rf.starts[ii[0]]
        iend = rf.starts[ii[-1]] + rf.lengths[ii[-1]]
        nbytes = iend - istart
    else:
        nprofs = len(ii)
        if nprofs > 0:
            istart = ii[0] * rf.header.nbytes
        else:
            istart = 0
        nbytes = nprofs * rf.header.nbytes

    rf.close()
    _log.info("Extracting %d bytes starting at %d for profile range %d:%d",
                nbytes, istart, i0, i1)

    with open(infile, "rb") as src:
        src.seek(istart)
        chunk = src.read(nbytes)

    if outfile is not None:
        with open(outfile, "wb") as outf:
            outf.write(chunk)
            _log.info("Wrote extracted chunk to %s", outfile)

    return chunk


def cached_rawfiles(fnames, sonar, yearbase, cachefile="./rawfiles.cache"):
    """
    Returns list of closed rawfile instances and list of matching fnames.
    Files lacking a complete record are skipped.

    Note: the yearbase for each file in the cache is not used in the
    returned list of closed rawfile instances.  Instead, they all have the
    *yearbase* arg if it is not None, otherwise the yearbase of the
    first file. For NB files, the *yearbase* arg must not be None; Multiread
    takes care of this.

    This is exclusively a helper for Multiread.
    """
    cachepath = Path(cachefile)
    if cachepath.exists():
        try:
            cache = pickle.loads(cachepath.read_bytes())
        except (ModuleNotFoundError, AttributeError):
            # Pickle load failed because of library changes since it was made.
            cache = {}
    else:
        cache = {}
    rawfiles = []
    ok_fnames = []
    for name in fnames:
        p = Path(name)
        new_mtime = p.stat().st_mtime_ns
        if p.name in cache:
            mtime, rf = cache[p.name]
            cachedpath = Path(rf.fname)
            if new_mtime == mtime and cachedpath.exists() and p.samefile(cachedpath):
                rawfiles.append(rf)
                ok_fnames.append(name)
                continue
        new_rf = rawfile(name, sonar, yearbase=yearbase)
        if new_rf.opened:
            new_rf.close()
            cache[p.name] = (new_mtime, new_rf)
            rawfiles.append(new_rf)
            ok_fnames.append(name)
    try:
        cachepath.write_bytes(pickle.dumps(cache))
    except OSError:
        pass
    if yearbase is None:
        yearbase = rawfiles[0].yearbase
    for rf in rawfiles:
        rf.yearbase = yearbase
    return rawfiles, ok_fnames


dparams_dtype = np.dtype([('NCells', int),
                         ('CellSize', float),
                         ('Blank', float),
                         ('Pulse', float)])


class Multiread:
    """
    Class for reading data from a set of raw adcp data files.

    The dataset is divided into chunks, where each chunk is a set of
    files covering a time period during which no configuration changes
    were made and no reboots occurred.  By setting the optional gap
    kwarg, for UHDAS data only, chunk boundaries can also be placed
    at time gaps in the dataset.

    Note that for the os, two ping types may be present in a given
    chunk.  A consequence is that if data are collected with both
    ping types, then briefly paused to turn off one of the ping types,
    and resumed with no change in the parameters of the remaining
    ping type, the change still makes a chunk boundary.

    Typical usage::

        m = Multiread('*.raw', 'os', gbinsonar="../../gbin/os38/")
        m.list_configs() # to find the indices of available configurations
        m.select(1) # to select a configuration, in this case the second;
                    # if there is only one, then select() is not needed.
        d = m.read(step=10) # to read all data, every 10th profile.

        d.keys()  # will show the attributes and dictionary keys to the data

        # Step through the data, using only a given ping type, and
        # read chunks delimited by configuration changes.
        m.pingtype = 'bb'           # for os only
        nchunks = len(m.bbchunks)   # for non-os it would be len(m.chunks)
        for ichunk in range(nchunks):
            select_chunk(ichunk)
            d = m.read()            # with whatever options you want
            # do something with it, of course

        # Or use the multiread object as an iterator through chunks of a
        # given pingtype (for the os):

        m.pingtype = 'nb'
        for chunk in m:
            d = chunk.read()         # again with options as needed,
                                     # or multiple reads within the chunk

        # To select a time range within a selected chunk:
        m.set_range((32, 32.1))
        d = m.read()

    The pingtype attribute can be set to None for iteration through
    all chunks in sequence, regardless of pingtype.

    After initialization the *fnames* attribute is the list of files
    that are being used, after filtering out those with fewer than
    *min_nprofs* profiles.

    In the output of read(), the *times* attribute holds the gbin time
    file data if gbinsonar has been specified; otherwise the *.log.bin
    files are used.  With gbin files, the *best* attribute holds the
    .best.gbin data.  Both gbin data objects are recarrays:

        d = m.read()
        utc = d.times.dday
        heading = d.best.heading
        # etc.

    """

    def __init__(self, fnames, sonar,
                                yearbase=None,
                                alias=None,
                                gap=None,
                                min_nprofs=1,
                                gbinsonar=None,
                                ibad=None,
                                beam_index=None,
                                require_watertrack=True):
        """
        fnames: glob or list of filenames
        sonar: 'nb', 'bb', 'wh', 'sv', 'pn', 'os', or 'ec' optionally
                followed by freq and pingtype, or a Sonar instance.
                For an 'os' or 'pn' with a pingtype included, that pingtype
                will be selected for initial data access.  It can
                be changed using set_pingtype().  Pingtype has no
                effect for other sonars.
        yearbase: if not given, it will be inferred from the
                  first filename if sonar is 'nb', otherwise
                  taken from the date in the first file.
        alias: a translation dictionary to be passed to binfile_n
               for reading *.log.bin, if present.  By default it
               changes unix_dday to u_dday, etc.
        gap: None (default) or a tuple consisting of a time column
               name in the translated binfiles, and a number of seconds;
               if the time gap between files exceeds this threshold,
               a new chunk will be started.

        min_nprofs: files with fewer profiles will be ignored.  Default
               is 1.

        gbinsonar: (optional) is the directory in which gbin subdirectories
               such as "time", "gpsnav", "gyro", etc. are found.
               If present, the time/*.tim.gbin files will be used,
               and data from other gbin subdirectories can be
               extracted on demand.  If None, the *.log.bin files
               will be used instead.

        ibad: (optional) the index of a beam to be excluded from
               the beam_to_xyz calculation.  This is the zero-based
               index.

        beam_index: (optional) list of remapped indices of beams in case an
               instrument has been miswired, eg [0,1,3,2]

        require_watertrack: (optional) if True, ignore files with BT only.

        ValueError will be raised (by make_filelist) if a glob
        is supplied and no files are found.
        """
        fnames = pathops.make_filelist(fnames)
        cachefile = Path(fnames[0]).with_name("rawfiles.cache")
        self.sonar = Sonar(sonar)
        # The nb initialization requires a yearbase; there is no year
        # info in the instrument clock.
        if yearbase is None and self.sonar.isa('nb'):
            fn = os.path.split(fnames[0])[1]
            yearbase = int(fn[2:6])
        if alias is None:
            alias = dict(unix_dday='u_dday', monotonic_dday='m_dday',
                         logger_dday='u_dday', bestdday='dday')
        self.alias = alias
        self.gap = gap
        self.min_nprofs = min_nprofs
        self.gbinsonar = gbinsonar
        self.ibad = ibad
        self.beam_index = beam_index

        all_rawfiles, fnames = cached_rawfiles(fnames, self.sonar,
                                                yearbase=yearbase,
                                                cachefile=cachefile)
        nproflist = []
        rawfiles = []
        _fnames = []

        for fn, r in zip(fnames, all_rawfiles):
            if require_watertrack and not r.includes_watertrack:
                continue
            if r.nprofs < min_nprofs:
                continue
            nproflist.append(r.nprofs)
            rawfiles.append(r)
            _fnames.append(fn)

        self.yearbase = rawfiles[0].yearbase
        self.rawfiles = np.array(rawfiles)
        self.fnames = np.array(_fnames)
        self.base_fnames = np.array(pathops.basename(_fnames))

        if gbinsonar is None:
            _log_fnames = [f + '.log.bin' for f in _fnames]
        else:
            _log_fnames = [os.path.join(gbinsonar, "time", f + '.tim.gbin')
                            for f in self.base_fnames]
        if os.path.exists(_log_fnames[0]):
            self.bs = BinfileSet(_log_fnames, alias=alias)
        else:
            self.bs = None

        # Helper for get_matching_bin():
        self.get_matching_bs_dict = {}

        # In the following, we are not checking that these variables
        # are available in all files; this might be a problem if there
        # is a dataset with only bt in some files.
        self.available_varnames = self.rawfiles[0].available_varnames

        nproflist = np.array(nproflist, int)
        self.nproflist = nproflist
        cs = np.cumsum(nproflist)
        self.nprofs = int(cs[-1])
        # starts is the starting profile index for each file in the sequence,
        # treating the sequence as a single array of profiles.
        self.starts = np.zeros_like(nproflist)
        self.starts[1:] = cs[:-1]

        # may not need the following 4 arrays--so they may go away
        # Also, they are specific to only one pingtype on the OS
        self.NCells = np.array([r.NCells for r in rawfiles], int)
        self.CellSize = np.array([r.CellSize for r in rawfiles], float)
        self.Blank = np.array([r.Blank for r in rawfiles], float)
        self.Pulse = np.array([r.Pulse for r in rawfiles], float)

        if self.sonar.model in ('os', 'pn'):
            self.pingtypes = [r.pingtypes for r in rawfiles]
            self.bbmask = np.array(['bb' in p for p in self.pingtypes], bool)
            self.nbmask = np.array(['nb' in p for p in self.pingtypes], bool)
        elif self.sonar.isa('ec'):
            self.bbmask = np.array(['fm' == r.sonar.pingtype for r in rawfiles], bool)
            self.nbmask = np.array(['cw' == r.sonar.pingtype for r in rawfiles], bool)

        # We do need this:
        if self.sonar.isa('nb'):     # Don't know without reading,
                                     # so initialize to True.
            self.bt = np.ones((len(_fnames),), dtype=bool)
        else:
            self.bt = np.array(['BottomTrack' in r.available_varnames
                                                    for r in rawfiles], bool)

        self.confdict = {}    # key: config tuple; value: list of rawfiles
        self.conflist = []    # list of config tuples, in order of encounter
        for r in rawfiles:
            for conf in r.configs:
                if conf in self.confdict:
                    self.confdict[conf].append(r)
                else:
                    self.confdict[conf] = [r]
                    self.conflist.append(conf)

        #The following ponderous object array creation and filling
        # seems to be needed to ensure a 1-D array under all conditions.
        confs = np.empty((len(rawfiles),), dtype=object)
        for i in range(len(rawfiles)):
            confs[i] = rawfiles[i].configs

        self.confs = confs

        self.sysconfig = rawfiles[0].sysconfig

        chunks = []

        if len(confs) > 1:  # more than one file
            # Mask: True if the *next* file has a different config.
            mask = confs[:-1] != confs[1:]
            # Mask: True if *next* file monotonic_dday has jumped backwards
            k = 'monotonic_dday'
            if self.alias is not None:
                k = self.alias.get(k, k)
            if self.bs is not None and k in self.bs.starts.dtype.names:
                rebootmask = self.bs.starts[1:][k] - self.bs.ends[:-1][k] < 0
                mask |= rebootmask
            if self.gap is not None:
                k, threshold = self.gap
                threshold /= 86400.0
                if self.alias is not None:
                    k = self.alias.get(k, k)
                if self.bs is not None and k in self.bs.starts.dtype.names:
                    gapmask = (self.bs.starts[1:][k] -
                                        self.bs.ends[:-1][k]) > threshold
                    mask |= gapmask
            ibreaks = np.nonzero(mask)[0] + 1
            i0 = [0] + list(ibreaks)
            i1 = list(ibreaks) + [len(confs)]
            for ii0, ii1 in zip(i0, i1):
                chunks.append(np.arange(ii0, ii1, dtype=int))
        else:
            chunks = [np.array([0], dtype=int)] # one chunk, one file

        self.chunks = chunks
        if self.sonar.model in ('os', 'pn', 'ec'):
            self.allchunks = chunks
            self.bbchunks = [c for c in chunks if self.bbmask[c[0]]]
            self.nbchunks = [c for c in chunks if self.nbmask[c[0]]]

        self._pingtype = None
        try:
            self.set_pingtype(self.sonar.pingtype)
        except AttributeError:
            self.set_pingtype(None)

    def __iter__(self):
        """
        Initialize iteration over chunks.
        """
        self._ichunk = 0
        return self

    def __next__(self):
        """
        Return the next chunk (which is the Multiread object itself,
        but with that chunk selected).
        """
        try:
            self.select_chunk(self._ichunk)
        except IndexError:
            raise StopIteration
        self._ichunk += 1
        return self

    ####

    def _set_chunks(self, pingtype):
        if pingtype not in ["bb", "nb", "fm", "cw", None]:
            raise ValueError("pingtype must be 'bb', 'nb', 'fm', 'cw', or None")
        if self.sonar.model in ("os", "pn"):
            if pingtype is None:
                self.chunks = self.allchunks
            elif pingtype == "bb":
                self.chunks = self.bbchunks
            elif pingtype == "nb":
                self.chunks = self.nbchunks
        elif self.sonar.isa("ec"):
            if pingtype is None:
                self.chunks = self.allchunks
            elif pingtype == "fm":
                self.chunks = self.bbchunks
            elif pingtype == "cw":
                self.chunks = self.nbchunks


    def set_pingtype(self, pingtype):
        self._set_chunks(pingtype)
        self._pingtype = pingtype
        self.select_chunk()

    def get_pingtype(self):
        return self._pingtype

    pingtype = property(get_pingtype, set_pingtype)

    def list_configs(self):
        """
        List all basic configurations (ping types and depth params)

        TODO: Better formatting.
        """
        print("# index (ping, NCells, CellSize, Blank, Pulse, NPings) nfiles")
        for i, conf in enumerate(self.conflist):
            print(i, '  ', conf, '   ', len(self.confdict[conf]))

    def _chunk_range(self, ichunk, chunk):
        """
        Return start dday, end dday for self.chunks[ichunk].
        """
        if self.bs is not None:
            j_time = 'u_dday' if self.gbinsonar is None else 'dday'
            start = self.bs.starts[chunk[0]][j_time]
            end = self.bs.ends[chunk[-1]][j_time]
        else:
            self.select_chunk(ichunk)
            start, end = self.read(varlist=[], ends=True).dday
        return start, end

    def chunk_ranges(self):
        """
        Find start and end times for currently selected chunks.

        Returns
        -------
        starts : array of float
            Start time (decimal day) of each chunk.
        ends : array of float
            End time (decimal day) of each chunk.
        """
        # Yes this is inefficient, but it isn't run often;
        # it is good enough for now.
        starts = []
        ends = []
        for ichunk, chunk in enumerate(self.chunks):
            s, e = self._chunk_range(ichunk, chunk)
            starts.append(s)
            ends.append(e)
        return np.array(starts), np.array(ends)

    def list_chunks(self):
        """
        List all chunks with the selected pingtype, or all chunks if
        no pingtype is selected.

        index nfiles start_u_dday end_u_dday BT conf1 [conf2]
        """
        outlist = []
        for ichunk, chunk in enumerate(self.chunks):
            line = ["%2d %2d" % (ichunk, len(chunk))]
            start, end = self._chunk_range(ichunk, chunk)
            line.append("%11.6f %11.6f" % (start, end))
            if self.bt[chunk[0]]:
                line.append(" on")  # may be bogus for NB
            else:
                line.append("off")
            for conf in self.confs[chunk[0]]:
                line.append("%s" % (conf,))
            outlist.append("   ".join(line))
        return "\n".join(outlist)

    def select(self, iconf=0, bt=None):
        """
        iconf: index of config as listed by list_configs()
        bt: True to select only files with BT available;
            False or None to ignore presence or absence of BT;
            this has no effect for the nb instrument, which
            always pretends to have BT.

        """

        conf = self.conflist[iconf]
        self.pingtype = conf[0]
        isel = [r in self.confdict[conf] for r in self.rawfiles]
        isel = np.array(isel)
        if bt and self.sonar.isnot('nb'):
            isel &= self.bt
        self.iselect = np.nonzero(isel)[0]  # indices of selected files
        self.iconf = iconf
        self._select_binset()

    def select_chunk(self, ichunk=0):
        """
        Select a contiguous set of files with the same configuration.

        The selection is made by specifying the index into an
        array of such sets.  Each set in the array is a list of
        indices into the original file list.  For the os, pn, and ec there
        are two possible arrays available as attributes: bbchunks
        and nbchunks.  The one used depends on the pingtype attribute.
        For other instruments, there is simply the chunks array, and
        the pingtype attribute is irrelevant.

        Like the select method, select_chunk merely sets two
        attributes: iselect, a list of indices into the file list;
        and iconf, an index into the conflist attribute.

        """
        self.iselect = self.chunks[ichunk]

        confs = self.confs[self.iselect[0]]
        if self.sonar.model in ('os', 'pn', 'ec') and self.pingtype is not None:
            for c in confs:
                if c[0] == self.pingtype:
                    break
            conf = c
        else:
            conf = confs[0]
        self.iconf = dict(zip(self.conflist, range(len(self.conflist))))[conf]
        self._select_binset()

    def _select_binset(self):
        if self.bs is not None:
            files = np.array(self.bs.filenames)[self.iselect]
            self.sel_bs = BinfileSet(files, alias=self.alias)
        else:
            self.sel_bs = None
        self.slicevars = (None, None, None)
        self._best_bs = None

    def set_range(self, ddrange='all', step=1, cname=None):
        if self.sel_bs is None:
            raise NotImplementedError("set_range requires *.bin or *.gbin")
        if cname is None:
            cname = "dday"
        self.sel_bs.set_range(cname=cname, ddrange=ddrange, step=step)
        start, stop, step = self.sel_bs.slicevars
        nprofs = int(self.nproflist[self.iselect].sum())
        stop = min(stop, nprofs)
        self.sel_bs.set_slice(start, stop, step)
        self.slicevars = (start, stop, step)


    def selected_files(self):
        """
        Return list of presently selected files.
        """
        if self.iconf is None:
            self.select()
        rf = self.rawfiles[self.iselect]
        files = [r.fname for r in rf]
        return files

    def make_ilists(self, start=None,
                          stop=None,
                          step=None,
                          ends=None,
                          ilist=None):
        """
        Find the index arrays for selected files.

        kwargs start, stop, step, ends, ilist pertain to indexing
            within that list, treated as a single sequence of profiles.

        This leaves two attributes set:

            ilist is the selected list of indices from the whole
                set of files treated as a single file;
            ilists is a list of ilists for the selected files,
                corresponding to rawfiles[self.iselect]
        """
        nproflist = self.nproflist[self.iselect]
        cs = np.cumsum(nproflist)
        nprofs = int(cs[-1])
        starts = np.zeros_like(nproflist)
        starts[1:] = cs[:-1]

        self.ilist = make_ilist(nprofs, start=start, stop=stop,
                                step=step, ilist=ilist, ends=ends)

        ilists = []
        for i in range(len(nproflist)):
            ilist0 = self.ilist - starts[i]
            ilist = make_ilist(nproflist[i], ilist=ilist0)
            ilists.append(ilist)
        self.ilists = ilists

    def read(self, start=None,
                       stop=None,
                       step=None,
                       ends=None,
                       ilist=None,
                       **kw):
        """
        Read data from presently selected files.

        kwargs start, stop, step, ends, ilist pertain to indexing
            within that list, treated as a single sequence of profiles.

        They may be omitted if set_range has been used to specify a
        range based on time.

        Additional kwargs are passed to the read() method of the
        individual File* instance.  The only one likely to be needed
        is the varlist.

        Data is returned in a Bunch instance, with most, but not all,
        of the fields provided by the File*.read() method.

        """
        if start is None and stop is None and step is None:
            start, stop, step = self.slicevars
        self.make_ilists(start=start, stop=stop, step=step,
                                        ends=ends, ilist=ilist)
        conf = self.conflist[self.iconf]
        pingtype = conf[0]
        if self.sonar.model in ('os', 'pn'):  # Not needed for ec.
            kw['ping'] = pingtype

        ppdlist = []
        for ilist, r in zip(self.ilists, self.rawfiles[self.iselect]):
            if len(ilist):
                r.open()
                d = r.read(ilist=ilist, **kw)
                ppdlist.append(d)
                r.close()
                self.last_file_read = r.fname
        nprofs = len(ppdlist)
        if nprofs == 0:
            return None

        ppd = _process_ppdlist(ppdlist, ibad=self.ibad, beam_index=self.beam_index)
        ppd.pingtype = pingtype
        ppd.yearbase = self.yearbase
        if ends:
            _ends = np.array([0, -1])
        if self.sel_bs is not None:
            ppd['times'] = self.sel_bs.records.copy().view(np.recarray)
            if ends:
                ppd['times'] = ppd['times'][_ends]
            # (.records is only a structured array, not a recarray)

            if self.sel_bs.name in ("pingtime", "besttime"):
                if self._best_bs is None:
                    files = [f[:-8] + "best.gbin"
                                        for f in self.sel_bs.filenames]
                    bs = BinfileSet(files) # no alias needed for best.gbin
                    self._best_bs = bs
                else:
                    bs = self._best_bs
                bs.set_slice(*self.slicevars)
                ppd['best'] = bs.records.copy().view(np.recarray)
                if ends:
                    ppd['best'] = ppd['best'][_ends]
        return ppd

    def read_matching_bin(self, dir, ext, cname=None):
        """
        After a range has been set, return the corresponding
        binfile records from the files in *dir* with
        extension *ext*.

        If *cname* is not None, match based on times rather
        than indices, using the same *cname* in the Multiread
        selection BinfileSet and in those in *dir*.
        """
        bases = self.base_fnames[self.iselect]
        files = [os.path.join(dir, bn + ext) for bn in bases]
        cachedict = self.get_matching_bs_dict
        bs_getter = cachedict.setdefault(ext, BinfileSetCache())
        bs = bs_getter(files)
        if cname is not None:
            t0, t1 = self.sel_bs.records[cname][[0, -1]]
            bs.set_range(ddrange=[t0, t1], cname=cname)
        else:
            bs.set_slice(*self.slicevars)
        return bs.records.copy().view(np.recarray)
