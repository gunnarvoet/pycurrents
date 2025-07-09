"""
Make UHDAS gbin files from the corresponding rbin and *.log.bin files.

The primary user interface is the Gbinner class::

    import time
    from pycurrents.adcp.gbin import Gbinner
    #
    class config:
        pos_inst = "posmv"
        pos_msg = "gps"
        hdg_inst = "gyro"
        hdg_msg = "hdg"
        pitch_inst = "posmv"
        pitch_msg = "pmv"
        roll_inst = "posmv"
        roll_msg = "pmv"
        hdg_inst_msgs = [("gyro", "hdg"), ("posmv", "pmv")]
    #
    t0 = time.time()
    gb = Gbinner(cruisedir="/home/data/km1009", sonar="wh300",
                    gbin="test_km1009/gbin",
                    config=config, timeinst="posmv", msg="gps",
                    rbin_edit_params=dict(acc_heading_cutoff=0.7))
    #
    gb(update=False)
    #
    print time.time() - t0

The example above will remake all gbin files, putting them in
test_km1009/gbin.

Using::

    gb(update=True)

(or omitting the argument--True is the default) runs the Gbinner
in incremental mode, updating the last two files of each type, with
the exception of *.best.gbin, for which only the last file may need
to be updated.

.. todo::

    Use a class to consolidate writing and using the time coefficient
    file.

"""

import os
import glob
import tempfile
import numpy as np
import logging
import logging.handlers


from pycurrents.data.nmea.qc_rbin import RbinSet
from pycurrents.file.binfile_n import binfile_n, BinfileSet
from pycurrents.num import Runstats, interp1
from pycurrents.data.navcalc import wrap
import pycurrents.system.pathops as pathops
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp.uhdasfile import UHDAS_Tree

# Standard logging
_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class Gbinner:
    """
    Make all gbin files.
    """
    coef_fname = "ztimefit.txt" # "z" makes it appear at end of "ls"

    def __init__(self, cruisedir=None,
                       sonar=None,
                       gbin=None,
                       config=None,  # here, or in make_best_gbin
                       timeinst=None,# here, or in make_time_gbins
                       msg=None,     # same as above
                       gbin_gap_sec=0,     # interp1: 0=interpolate across gaps
                       max_files_per_seg=6, # try 1 if there are gaps
                       method="linear",  # here or in make_sensor_gbins
                       rbin_edit_params=None, # editing kw for RbinSet
                       ):
        """

        The config kwarg can be specified here or in make_best_gbin.
        It is an object with 8 required attributes, such as in
        this example that can be used for testing:

        class config:
            pos_inst = "gpsnav" # "posmv"
            pos_msg = "gps"
            hdg_inst = "gyro"
            hdg_msg = "hdg"
            pitch_inst = "posmv"
            pitch_msg = "pmv"
            roll_inst = "posmv"
            roll_msg = "pmv"

        Alternatively, one can use a pycurrents.system.Bunch instance.

        Normally config will be the object returned by procsetup().

        """
        self.cruisedir = cruisedir
        self.sonar = Sonar(sonar)
        self.dirs = UHDAS_Tree(cruisedir, self.sonar)
        if gbin is not None:
            self.dirs.gbin = gbin

        self.timedir = self.dirs.gbinsonarpath("time")
        self.max_dt = float(gbin_gap_sec)/86400. # max_dt is in dday fraction
        self.max_files_per_seg = max_files_per_seg # used in TimeCal.split()

        _makedirs(self.timedir)

        self.timeinst = timeinst
        self.coefpath = self.dirs.gbinpath(self.coef_fname)


        self.msg = msg
        self.method = method
        self.config = config
        if rbin_edit_params is None:
            rbin_edit_params = {}
        self.rbin_kw = rbin_edit_params




    def __call__(self, update=True):
        self.make_time_calib(update=update)
        self.make_time_gbins(update=update)
        self.make_sensor_gbins(update=update)
        self.make_best_gbin(update=update)
        self.make_gridded_headings()

    def make_time_calib(self, timeinst=None, msg=None, update=True):
        """
        Calculate and write time calibrations and GMT ping times.

        It uses the rbin files for the given 'msg' from the 'timeinst'.
        It updates or replaces the 'ztimefit.txt' file, in which
        each line has 4 fields: the base filename, 2 correction
        coefficients, and a flag that is 1 if a new correction
        interval is started, and 0 otherwise.


        If there are gaps in gbins, but rbins and dday seem fine, try
        reducing max_files_per_seg to max_files_per_seg=1

        """
        if timeinst is None:
            timeinst = self.timeinst
        if msg is None:
            msg = self.msg
        timeinst_dir = self.dirs.rbinpath(timeinst)
        if not os.path.isdir(timeinst_dir):
            raise ValueError("Wrong timeinst kwarg? Directory %s is not found."
                                % timeinst_dir)
        globpattern = os.path.join(timeinst_dir, "*.%s.rbin" % msg)
        files = glob.glob(globpattern)
        if len(files) == 0:
            raise ValueError("Check the 'msg' settings in processing configuration -- no files found with wildcard:\n%s."
                                % globpattern)
        files.sort()
        if update:
            # Use a file list overlapping only with the last
            # two files that have already been seen; the last
            # one may be very short, so the one before that is
            # retained for context.
            # Possibly we need to do more to handle the overlap
            # region.
            try:
                tcor = read_coefs(self.coefpath)
                fnbase = tcor[-3][0]
                _files = list(files[::-1])
                files = []
                for f in _files:
                    if fnbase in f:
                        break
                    files.append(f)
                files.reverse()
            except (IOError, IndexError):
                pass

        tc = TimeCal(files)
        tc.split(max_files_per_seg=self.max_files_per_seg)
        tc.fit()
        if update:
            tc.update(self.coefpath)
        else:
            tc.write(self.coefpath)

    def make_time_gbins(self, update=True):
        tcor = read_coefs(self.coefpath)

        sourceglob = glob.glob(self.dirs.rawsonarpath("*.raw.log.bin"))
        sourceglob.sort()
        i0 = 0
        if update:
            destglob = glob.glob(os.path.join(self.timedir, "*.tim.gbin"))
            if len(destglob) > 1:
                destglob.sort()
                sbase = pathops.basename(sourceglob)
                dbase = pathops.basename(destglob)
                i0 = sbase.index(dbase[-2])
        sourcefiles = sourceglob[i0:]

        cdict = dict([r[:2] for r in tcor])

        for fn in sourcefiles:
            fbase = pathops.basename(fn)
            try:
                p = cdict[fbase]
            except KeyError:
                _log.warning("Raw file %s has no matching time correction", fn)
                continue
            bf = binfile_n(fn)
            # Hack to handle bad first datagram from EC150.
            _records = bf.records.copy()
            bf.close()
            if len(_records) > 1 and _records[0].n_bytes != _records[1].n_bytes:
                _records = _records[1:]
            m_dday = _records.monotonic_dday
            dday = p[0] + (1 + p[1]) * m_dday
            bfarray = np.empty((len(dday), 4), dtype=np.float64)
            bfarray[:,0] = _records.unix_dday
            bfarray[:,1] = dday
            bfarray[:,2] = _records.unix_dday - dday
            bfarray[:,3] = _records.monotonic_dday
            fn_out = os.path.join(self.timedir, fbase + ".tim.gbin")
            bfout = binfile_n(fn_out, mode="w",
                               name="pingtime",
                               columns=["unix_dday",
                                        "dday",
                                        "sec_pc_minus_utc",
                                        "monotonic_dday"])
            bfout.write(bfarray)
            bfout.close()



    def make_sensor_gbins(self, method=None, update=True):
        """
        Write the gbins for each sensor.
        This must be called after make_time_gbins().
        """
        if method is None:
            method = self.method
        coefs = read_coefs(self.coefpath)
        coefbases = set([c[0] for c in coefs])
        sensors = [s for s in os.listdir(self.dirs.rbin)
                        if os.path.isdir(self.dirs.rbinpath(s))]
        for sensor in sensors:
            destdir = self.dirs.gbinsonarpath(sensor)
            _makedirs(destdir)
            _dir = self.dirs.rbinpath(sensor)
            rbins = glob.glob(os.path.join(_dir, "*.rbin"))
            rbinbases = set([pathops.filename_base(fn) for fn in rbins])
            # set of base names in coefs and rbins:
            bases = coefbases.intersection(rbinbases)
            rbins = [f for f in rbins
                     if pathops.filename_base(f) in bases]
            _coefs = [rec for rec in coefs if rec[0] in bases]
            startflags = [r[2] for r in _coefs]
            rbins.sort()
            msgs = set([os.path.basename(fn).split('.')[1] for fn in rbins])
            for msg in msgs:
                msg_rbins = [f for f in rbins
                             if os.path.basename(f).split('.')[1] == msg]
                i0 = 0
                overlap = False
                if update:
                    # Overlap with the two most recent gbins:
                    gbins = glob.glob(os.path.join(destdir, "*.%s.gbin" % msg))
                    gbins = pathops.basename(gbins)
                    gbins.sort()
                    if len(gbins) > 2:
                        fb0 = gbins[-2]
                        mrb = pathops.basename(msg_rbins)
                        i0 = mrb.index(fb0)
                        overlap = True

                # Instead of processing everything at once, slice it up to
                # reduce the memory usage and avoid time jumps.
                m = 12
                n = min(len(msg_rbins), len(startflags))
                i1 = i0
                while i0 < n:
                    while (i1 < n and
                            (i1 == i0 or startflags[i1] == 0) and
                            i1 - i0 < m):
                        i1 += 1
                    # Back up the start of the RbinSet by one or two files,
                    # but don't write anything for the lowest overlap.
                    #log.debug("%s %s", i0, startflags)
                    if i0 > 0 and startflags[i0] == 0:
                        i0 -= 1
                        if i0 > 0 and startflags[i0] == 0:
                            i0 -= 1
                        overlap = True
                    force_m_dday = ( (msg=='adu') or (msg=='at2'))
                    write_gbins(_coefs, msg_rbins[i0:i1], self.timedir, destdir,
                                                    method=method,
                                                    force_m_dday=force_m_dday,
                                                    rbin_kw=self.rbin_kw,
                                                    max_dt=self.max_dt,
                                                    overlap=overlap)
                    #log.debug("%s %s %s", i0, i1, overlap)
                    overlap = False
                    i0 = i1


    def make_best_gbin(self, config=None, update=True):
        if config is None:
            config = self.config
        make_best_gbin(self.dirs.gbin, self.sonar.instname, config,
                       update=update)

    def make_gridded_headings(self):
        '''
        write out hbins, i.e. all headings gridded onto the times of the primary position device
        '''
        dirs = self.dirs
        hdg_inst_msgs = self.config.hdg_inst_msgs
        _makedirs(dirs.gbinheading)
        hfiles = glob.glob(dirs.gbinheadingpath("*.hbin"))
        hfiles.sort()
        hfilebases = pathops.basename(hfiles)

        timeinstglob = dirs.rbinpath(self.timeinst, "*.%s.rbin" % self.msg)
        timeinstfiles = glob.glob(timeinstglob)
        timeinstfiles.sort()

        timeinstbases = pathops.basename(timeinstfiles)

        if len(hfilebases) > 1:
            i = timeinstbases.index(hfilebases[-1])
            todo_bases = timeinstbases[i:]
        else:
            todo_bases = timeinstbases

        coefs = read_coefs(self.coefpath)
        cdict = dict([r[:2] for r in coefs])

        for fbase in todo_bases:
            tbf = RbinSet(dirs.rbinpath(self.timeinst,
                                    "%s.%s.rbin" % (fbase, self.msg)))
            dday = tbf.records['dday'].compressed()

            dat = np.ma.zeros((len(dday), len(hdg_inst_msgs)+1), float)
            dat[:] = np.ma.masked
            dat[:,0] = dday

            p = cdict.get(fbase, None) # Missing entry is flagged with None.
                                       # If we need a time correction,
                                       # but none is available, the
                                       # corresponding column will be
                                       # masked out below.

            cols = ['dday']
            i = 1
            for inst, msg in hdg_inst_msgs:
                instfile = dirs.rbinpath(inst, "%s.%s.rbin" % (fbase, msg))
                try:
                    ibf = RbinSet(instfile, unwrap=True, **self.rbin_kw)
                    # ... calculate corrected time if dday is not present
                    #  or if it as an Ashtech PASHR,ATT message,
                    #  for which dday is not reliable
                    if 'dday' in ibf.columns and msg not in ('adu', 'at2', 'att'):
                        idday = ibf.dday
                    else:
                        if p is None:
                            idday = ibf.m_dday.copy()
                            idday[:] = np.ma.masked
                            _log.warning("make_gridded_headings:"
                                        + " missing time correction for %s",
                                                                    fbase)
                        else:
                            idday = p[0] + (1 + p[1]) * ibf.m_dday
                    # ... interpolate heading, put in dat (do not fill gaps)
                    dat[:,i] = interp1(idday, ibf.heading, dday,
                                                    method=self.method,
                                                    max_dx=self.max_dt,
                                      )
                except ZeroDivisionError:
                    # interp1 found empty idday, ibf.heading
                    _log.info("No data in file: %s", instfile)
                except OSError:
                    pass
                except:
                    _log.exception("Error with file: %s", instfile)
                cols.append("%s_%s" % (inst, msg))
                i += 1

            # write dat out as a binfile
            fid, tmp_fname = tempfile.mkstemp(dir=dirs.gbin)
            os.close(fid)
            hbf = binfile_n(tmp_fname, mode="w",
                                       name="heading",
                                       columns=cols,
                                       type="f8")
            dat[:,1:] %= 360
            hbf.write(dat.filled(np.nan))
            hbf.close()
            os.chmod(tmp_fname, 0o664)
            os.rename(tmp_fname, dirs.gbinheadingpath("%s.hbin" % fbase))


class TimeCal(BinfileSet):
    """
    Calculate linear fits of UTC to logger monotonic dday.
    """
    def split(self, max_dt_seconds=10, max_files_per_seg=6):
        """
        Find segments as ranges of files, identified by index into
        the rb filelist, with no monotonic time jumps.  (A jump that
        occurs in the middle of a file, such as when a sensor drops out,
        does not trigger starting a new segment.)

        If there are gaps in gbins, but rbins and dday seem fine, try
        reducing max_files_per_seg to max_files_per_seg=1
        """
        # dm[i] is time gap since end of previous file
        dm = np.zeros((self.starts.shape[0],), float)
        dm[0] = 10000 # so the first file is always a start
        dm[1:] = (self.starts['m_dday'][1:] - self.ends['m_dday'][:-1])*86400
        jump = np.absolute(dm) > max_dt_seconds
        self.startflag = jump
        segstarts = list(jump.nonzero()[0])
        if len(segstarts) > 1:
            segstops = segstarts[1:]
        else:
            segstops = []
        segstops.append(len(self.filenames))

        _segs = list(zip(segstarts, segstops))
        # Save the original time-gap-based segmentation for
        # use in generating gbins; we don't want to interpolate
        # across the gaps.
        self.timesegs = _segs

        # Now chop up segments that are too long.
        segs = []

        for seg in _segs:
            nfiles = seg[1] - seg[0]
            nsplit = (nfiles - 1) // max_files_per_seg
            if nsplit == 0:
                segs.append(seg)
            else:
                i0 = np.arange(seg[0], seg[1], nfiles // (nsplit + 1), dtype=int)
                i1 = np.zeros_like(i0)
                i1[:-1] = i0[1:]
                i1[-1] = seg[1]
                for ii0, ii1 in zip(i0, i1):
                    segs.append((ii0, ii1))
        self.segs = segs

    def fit(self, nwindow=61):
        tcor_fnames = []
        tcor_coefs = []
        for seg in self.segs:
            #data_sl = slice(self.istart[seg[0]], self.istop[seg[1]-1])
            self.set_slice(self.istart[seg[0]], self.istop[seg[1]-1])
            #p = linfit(self.m_dday[data_sl], self.dday[data_sl], nwindow)
            p = linfit(self.m_dday, self.dday, nwindow)
            fn_sl = slice(*seg)
            for fn in self.filenames[fn_sl]:
                fn = os.path.split(fn)[1].split('.')[0]
                tcor_fnames.append(fn)
                tcor_coefs.append(p)
        self.tcor_fnames = tcor_fnames
        self.tcor_coefs = tcor_coefs
        self.tcor = list(zip(tcor_fnames, tcor_coefs, self.startflag))

    def predict(self):
        tpred = np.zeros_like(self.m_dday)
        for seg in self.segs:
            data_sl = slice(self.istart[seg[0]], self.istop[seg[1]-1])
            p = self.tcor_coefs[seg[0]]
            tpred[data_sl] = p[0] + (1 + p[1]) * self.m_dday[data_sl]
        self.p_dday = tpred

    def calculate(self, fname, m_dday):
        p = dict([r[:2] for r in self.tcor])[fname]
        return p[0] + (1 + p[1]) * m_dday

    def write(self, fname):
        """
        Write the time correction coefficients file.
        """
        # Don't write an empty file:
        if not self.tcor:
            return

        lines = []
        for fn, c, sflag in self.tcor:
            lines.append("%s %.13e %.13e %d\n" % (fn, c[0], c[1], sflag))
        # Use a temporary file so that the re-written file is
        # changed atomically by the OS via the rename call.
        # This guarantees that any attempt to read the file yields
        # a complete and valid version.
        fid, tmp_fname = tempfile.mkstemp(dir=os.path.split(fname)[0])
        os.fdopen(fid, 'w').writelines(lines)
        os.chmod(tmp_fname, 0o664)
        os.rename(tmp_fname, fname)

    def update(self, fname):
        """
        Update an existing time correction coefficients file,
        or write a new one if none exists.
        (Updating is done be rewriting the whole file.)
        """
        try:
            tcor = read_coefs(fname)
            oldnames = [r[0] for r in tcor]
        except IOError:
            self.write(fname)
            return
        fn0 = self.tcor_fnames[0]
        try:
            ii = oldnames.index(fn0)
            if len(self.tcor_fnames) > 1:
                # Don't update the first overlapping file:
                tcormerged = tcor[:(ii+1)] + self.tcor[1:]
            else:
                tcormerged = tcor[:ii] + self.tcor
        except ValueError:
            # warn here?
            tcormerged = tcor + self.tcor

        lines = []
        for fn, c, sflag in tcormerged:
            lines.append("%s %.13e %.13e %d\n" % (fn, c[0], c[1], sflag))
        with open(fname, 'w') as file:
            file.writelines(lines)


def read_coefs(fname):
    """
    Read ascii time correction file, return list of corrections.

    The format is slightly different from what is calculated by
    TimeCal, in that the coefficients are given as a tuple of
    floats instead of an ndarray.
    """
    tcor = []
    with open(fname) as newreadf:
        lines = newreadf.readlines()
    for line in lines:
        fn, p0, p1, sflag = line.split()
        tcor.append((fn, (float(p0), float(p1)), int(sflag)))
    return tcor


def linfit(tmono, tgps, nwindow):
    n = len(tmono)
    dt = tgps - tmono

    # If there are fewer than 2*nwindow points, we are probably
    # better-off taking a simple maximum than trying to fit
    # a line to a running maximum.
    if n < 2 * nwindow:
        return np.array([dt.max(), 0.0], dtype= np.float64)

    rs = Runstats(dt, nwindow, masked=False)
    dtrmax = rs.max
    goodmask = (rs.ngood == nwindow)
    dtrmax = np.extract(goodmask, dtrmax)
    if len(dtrmax) < 2:
        raise ValueError("Too few valid points for linear fit.")
    lin = np.ones((len(dtrmax), 2), np.float64)
    lin[:,1] = np.extract(goodmask, tmono)
    p, resid = np.linalg.lstsq(lin, dtrmax, rcond=-1)[:2]  # temporary, until numpy>1.14 (then use None)
    return p


def _makedirs(dir):
    try:
        os.makedirs(dir)
    except OSError:
        pass


def write_gbins(coefs, sourcefiles, timdir, destdir,
                        force_m_dday=False,
                        method='linear',
                        rbin_kw=None,
                        max_dt=0,
                        overlap=False):
    """
    Generate a set of sensor gbin files.

    (set force_m_dday to True to use m_dday instead of dday with
    sensors that have both.)
    """
    cdict = dict([r[:2] for r in coefs])
    unwrap = (method == 'linear')
    if rbin_kw is None:
        rbin_kw = {}
    rb = RbinSet(sourcefiles, unwrap=unwrap, **rbin_kw)
    if force_m_dday or "dday" not in rb.columns:
        dday = np.ma.empty((rb.nrows,), dtype=np.float64)
        for i, fn in enumerate(rb.filenames):
            fnbase = os.path.split(fn)[1].split('.')[0]
            sl = slice(rb.istart[i], rb.istop[i])
            p = cdict.get(fnbase, None)
            if p is None:
                dday[sl] = np.ma.masked
                _log.warning("write_gbins: missing time coefs for %s", fnbase)
            else:
                dday[sl] = p[0] + (1 + p[1]) * rb.m_dday[sl]
    else:
        dday = rb.dday

    if dday.size < 2:
        _log.debug("write_gbins: dday.size is %s, files %s",
                                        dday.size, sourcefiles)
        return

    if dday.count() < 2:
        _log.warning("write_gbins: dday.count() is %s, files %s",
                                        dday.count(), sourcefiles)
        return

    pg = (100.0 * dday.count()) / dday.size
    if pg < 99:
        _log.warning("write_gbins: dday.count() is %s, dday.size is %s, files %s",
                            dday.count(), dday.size, sourcefiles)

    # mask for good points
    mask = ~np.ma.getmaskarray(dday)
    dday = dday.compressed()  # ndarray suitable for searchsorted
    dat = rb.array[:, 1:].compress(mask, axis=0)
        # Note: as of 1.6.1.dev-a265004, np.ma.compress function is
        # broken, but the corresponding method works.
    # Interp can handle dat as masked array.

    for i, fn in enumerate(rb.filenames):
        if i==0 and overlap:
            continue
        rbin_to_gbin(fn, rb, dday, dat, timdir, destdir, method, max_dt=max_dt)

def rbin_to_gbin(fname, rb, dday, dat, timdir, destdir, method, max_dt=0):
    """
    Generate a single gbin file from the corresponding *.tim.gbin,
    and a set of rbins.
    """
    fn1e = os.path.split(fname)[1]
    fn1 = os.path.splitext(fn1e)[0]
    fnbase = fn1.split('.')[0]
    timbin_name = os.path.join(timdir, fnbase + ".tim.gbin")
    try:
        timbin = binfile_n(timbin_name)
    except IOError:
        _log.warning("rbin_to_gbin: timbin %s not available", timbin_name)
        timbin = None
    fn_out = os.path.join(destdir, fn1 + ".gbin")
    bfout = binfile_n(fn_out, mode="w",
                       name=fn1.split('.')[1],
                       columns=rb.columns[1:])
    # If there is an empty or missing .tim.gbin,
    # write a corresponding empty sensor gbin:
    if timbin is None or timbin.count() == 0:
        bfout.close()
        return
    i0 = np.searchsorted(dday, timbin.records.dday[0])
    i0 = max(0, i0-1)
    try:
        newdat = interp1(dday[i0:], dat[i0:], timbin.records.dday,
                            masked=False, method=method, max_dx=max_dt) ## don't fill
    except:
        _log.exception("rbin_to_gbin: interp1 failed for %s", fn_out)
        bfout.close()
        return
    if method == "linear":
        try:
            i = bfout.columns.index("heading")
            newdat[:,i] %= 360.0
        except ValueError:
            pass
        try:
            i = bfout.columns.index("lon")
            newdat[:,i]  = wrap(newdat[:,i], 180)
        except ValueError:
            pass

#    basename = os.path.basename(fname)
#    if basename.split('.')[1] == 'gps':
#        from IPython import embed; embed()

    bfout.write(newdat)
    bfout.close()

def _binfile_or_None(fn):
    try:
        return binfile_n(fn)
    except IOError:
        return None

def make_best_gbin(gbin, sonarname, config, update=True):
    """
    config is an object such as is returned by procsetup, with
    attributes pos_inst, pos_msg, etc.

    This function is wrapped by Gbinner, but is retained for
    now as an independent function, in case that turns out to
    provide a simpler way of using it for remaking gbins.
    (It probably won't matter.)
    """
    best_columns = ["lon", "lat", "heading", "pitch", "roll"]
    c = config
    inst_msgs = [(c.pos_inst, c.pos_msg), (c.hdg_inst, c.hdg_msg),
                     (c.pitch_inst, c.pitch_msg), (c.roll_inst, c.roll_msg)]
    unique_inst_msgs = list(set(inst_msgs))
    imdict = dict(pos=unique_inst_msgs.index(inst_msgs[0]),
                  hdg=unique_inst_msgs.index(inst_msgs[1]),
                  pitch=unique_inst_msgs.index(inst_msgs[2]),
                  roll=unique_inst_msgs.index(inst_msgs[3]))

    sonarnamedir = os.path.join(gbin, sonarname)
    timdir = os.path.join(sonarnamedir, "time")
    fns = glob.glob(os.path.join(timdir, "*.tim.gbin"))
    fns.sort()
    if update:
        bests = glob.glob(os.path.join(timdir, "*.best.gbin"))
        if len(bests) > 1:
            del fns[:(len(bests) - 1)]
    for fn in fns:
        bf = binfile_n(fn)
        nrows = bf.count()
        bf.close()
        arr = np.empty((nrows, 5), dtype=np.float64)
        arr.fill(np.nan)
        fnbase = os.path.split(fn)[1].split(".")[0]

        sourcenames = [os.path.join(sonarnamedir, im[0],
                                fnbase + ".%s.gbin" % (im[1],))
                                for im in unique_inst_msgs]
        sources = [_binfile_or_None(sn) for sn in sourcenames]
        bf = sources[imdict['pos']]
        try:
            arr[:,0] = bf.records.lon
            arr[:,1] = bf.records.lat
        except AttributeError:
            _log.warning("%s is missing in make_best_gbin",
                                sourcenames[imdict['pos']])
        except:
            _log.exception("Bad %s in make_best_gbin",
                                sourcenames[imdict['pos']])
        bf = sources[imdict['hdg']]
        try:
            arr[:,2] = bf.records.heading
        except AttributeError:
            _log.warning("%s is missing in make_best_gbin",
                                sourcenames[imdict['hdg']])
        except:
            _log.exception("Bad %s in make_best_gbin",
                                sourcenames[imdict['hdg']])
        # Special case pitch and roll; for example, they
        # might come from a bad Ashtech, causing empty rbins
        # and no gbins.
        # Or pitch_inst, roll_inst might be set to "none",
        # so that again there will be no gbins found.
        #arr[:,3] = sources[imdict['pitch']].records.pitch
        #arr[:,4] = sources[imdict['roll']].records.roll
        try:
            bf = sources[imdict['pitch']]
            if bf is not None:
                arr[:,3] = bf.records.pitch
        except:
            _log.exception("Bad %s in make_best_gbin",
                                sourcenames[imdict['pitch']])
        try:
            bf = sources[imdict['roll']]
            if bf is not None:
                arr[:,4] = bf.records.roll
        except:
            _log.exception("Bad %s in make_best_gbin",
                                sourcenames[imdict['roll']])

        fn_out = os.path.join(timdir, fnbase + ".best.gbin")
        bfout = binfile_n(fn_out, mode="w",
                           name="best",
                           columns=best_columns)
        bfout.write(arr)
        bfout.close()
        for bf in sources:
            if bf is not None:
                bf.close()
