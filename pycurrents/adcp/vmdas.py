"""
VMDAS-specific processing routines.

class FakeUHDAS: recast VmDAS ENR data as UHDAS data
                suitable for complete "quick_adcp.py --datatype uhdas..."
class LTA_Translate: translate LTA files into ldcodas *bin,*cmd files,
                suitable for ldcodas to load into codas
class VmdasInfo: used for 'scan' (quick_adcp.py) and gets info about files
                built for LTA at the moment
"""

import glob
import os
import sys
import numpy as np
import logging


from pycurrents.adcp.uhdas_defaults import serial_strmsg
from pycurrents.codas import to_datestring
from pycurrents.system import pathops
from pycurrents.system.misc import Bunch
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.file.binfile_n import binfile_n, BinfileSet
from pycurrents.data.nmea.serasc2bin import asc2bin
from pycurrents.adcp.uhdasfile import UHDAS_Tree
from pycurrents.adcp.raw_rdi import FileBBWHOS
from pycurrents.adcp.raw_rdi import instname_from_file
from pycurrents.adcp.raw_multi import Multiread
from pycurrents.adcp.pingavg import LDWriter
from pycurrents.adcp import EA_estimator

#import warnings
#warnings.simplefilter('error')  # to try and catch "Warning: converting a masked element to nan.

# Standard logging
_log = logging.getLogger(__name__)


def _makedirs(dir):
    try:
        os.makedirs(dir)
    except OSError:
        pass

"""
See the "tester" function at the bottom of the file for
an example of usage of FakeUHDAS

Because VMDAS substitutes the PC clock time for the ADCP clock time
even in the *.ENR files, the simple use of that time for m_dday
will work only if it is well-behaved--that is, free-running rather
than being occasionally reset by a system process.

TODO: Add methods for checking the clock behavior, and for
synthesizing a usable m_dday when necessary.

"""
class FakeUHDAS:
    def __init__(self, yearbase=None,
                        sourcedir=None,
                        destdir=None,
                        sonar=None,
                        navinfo=None,
                        ship=None,
                        max_block_hours=2,
                        dt_factor=0.5,
                        verbose=True):
        """
        All kwargs are mandatory; they are given as kwargs
        to enhance readability.

        *yearbase* is the usual.

        *sourcedir* holds the ENR, N1R, N2R files.  It must be
            writeable because the initial rbins will be put in
            subdirectories.

        *destdir* will be created to hold "raw" and "rbin"
            subdirectories.

        *sonar* can be a string (e.g. "os75") or a Sonar instance.

        *navinfo* is a list of tuples with (instrument, msg, num)
           where *num* is 1 or 2 depending on whether the data are
           in N1R or N2R files.  In addition, if *num* is zero,
           the heading may be extracted from the ENR files.

        *ship* is a 2-letter ship abbreviation

        *max_block_hours* is the upper end of the fake raw file
           size in hours.  The chopping will result in files no
           smaller than half this value.

        *dt_factor times the median dt is the threshold for splitting
           a file based on deviations of dt from its median.

        """
        self.yearbase = yearbase
        self.sourcedir = sourcedir
        self.destdir = destdir
        self.sonar = Sonar(sonar)
        self.navinfo = navinfo
        self.ship = ship
        self.tree = UHDAS_Tree(destdir, sonar)
        self.verbose=verbose
        self.max_block_hours = max_block_hours
        self.dt_factor = dt_factor

    def __call__(self):
        """
        Do everything.  Later, we may make this automatic
        with instantiation, if it looks like we don't need
        the ability to do the steps one-by-one.
        """
        if self.verbose:
            _log.info('making rbins from N1R (etc) in %s' % (self.sourcedir))
        self.nav_to_rbin()

        # do not attempt to redo if directory already exists
        if os.path.exists(self.destdir):
            msg = 'cannot make directory %s:  already exists' % (self.destdir)
            _log.warning(msg)
            return
        else:
            if self.verbose:
                msg ='reforming vmdas data. writing to %s' % (self.destdir)
                _log.info(msg)
            _makedirs(self.destdir)
            _makedirs(self.tree.raw)
            _makedirs(self.tree.rbin)

            self.fix_hundredths = self._check_hundredths()
            self.make_raw_logbins()
            self.extract_heading()
            self.convert_rbins()


    def nav_to_rbin(self):
        """
        Make rbin files corresponding to *.N?R files.

        They are in the form that serasc2bin produces for
        vmdas, not in the asc2bin form for uhdas, so their
        last two fields are count (always 0), and pingnum.

        They are put in instrument subdirectories of the
        source directory.
        """
        for inst, msg, num in self.navinfo:
            if num == 0:
                continue
            nglob = os.path.join(self.sourcedir, "*.N%sR" % num)
            files = pathops.make_filelist(nglob)
            outfiledir = os.path.join(self.sourcedir, inst)
            a2b = asc2bin(yearbase=self.yearbase,
                          outfiledir=outfiledir,
                          message=msg, verbose=self.verbose)
            a2b.translate_files(files)

    def _check_hundredths(self):
        # Look for the VMDAS bug: tenths of a second in the hundredths position.
        sglob = os.path.join(self.sourcedir, '*.ENR')
        sources = pathops.make_filelist(sglob)
        sizes = np.array([os.path.getsize(source) for source in sources])
        sorted_indices = np.argsort(sizes)[::-1]
        for i in sorted_indices:
            dat = None
            f = FileBBWHOS(sources[i], self.sonar, yearbase=self.yearbase)
            try:
                dat = f.read(varlist=["VariableLeader"])
            except Exception:
                _log.warning("Could not get Variable Leader from %s", sources[i])
            else:
                break
            finally:
                f.close()
        if dat is not None:
            return dat.rVL['Hundredths'].max() <= 9
        raise RuntimeError("Could not find a readable file.")

    @staticmethod
    def _fix_hundredths_enr(dday):
        '''
        VmDAS bug where rVL['Hundredths'] is actually 1/10
        '''
        seconds_int, rem = np.divmod(np.round(dday * 86400, 2), 1)
        return (seconds_int + rem * 10) / 86400

    @staticmethod
    def _fix_hundredths_nav(dday):
        '''
        VmDAS bug where rVL['Hundredths'] is actually 1/10
        nav timestamps are in hundredths; if buggy, change to tenths
        '''
        tenths = dday * 864000
        return np.floor(tenths) / 864000


    def make_raw_logbins(self):
        """
        Read the original ENR files, and write out corresponding
        *.raw and *.raw.log.bin files.  If a ping number reset
        occurs in a file, it is split.

        A file, name_map.txt, is written in the rawsonardir
        to record the original name of each file, so that the
        matching clump of N*R files can be used.

        vmdas bug: prior to v1.50 "hundredths" VL is actually tenths
                   - check boolean attribute fix_hundredths, fix if True
        """
        columns = ['unix_dday', 'offset', 'n_bytes',
                   'pingnum', 'instrument_dday', 'monotonic_dday']
        sglob = os.path.join(self.sourcedir, '*.ENR')
        sources = pathops.make_filelist(sglob)
        destdir = self.tree.rawsonar
        _makedirs(destdir)
        name_map = []
        for source in sources:
            f = FileBBWHOS(source, self.sonar, yearbase=self.yearbase)
            try:
                dat = f.read(varlist=['VariableLeader'])
                f.close()
            except Exception:
                _log.warning("Could not get Variable Leader from %s",source)
                continue

            if self.fix_hundredths:
                dat.dday = self._fix_hundredths_enr(dat.dday)

            dt = np.diff(dat.dday)*86400
            med_dt = np.median(dt)
            # We expect only small variations in dt.
            bad_dt = np.abs(dt - med_dt) > (self.dt_factor * med_dt)
            if (dt <= 0).any():
                _log.warning("Negative dt in %s", source)
                bad_dt = bad_dt | (dt <= 0)
            if (dt > 10).any():
                _log.warning("dt exceeding 10 seconds in %s", source)

            dn = np.diff(dat.ens_num)
            if (dn <= 0).any() or bad_dt.any():
                _log.warning("ens_num reset or stalled, or time jump in"
                         " %s; splitting file", source)
                ii = list(np.nonzero((dn <= 0) | bad_dt)[0] + 1)
                i0 = [0] + ii
                i1 = ii + [f.nprofs]
                slices = [slice(s, e) for s, e in zip(i0, i1)]
            else:
                slices = [slice(0, f.nprofs)]

            hours = dat.dday * 24
            smallslices = []
            maxhr = self.max_block_hours
            for s in slices:
                dhr = hours[s][-1] - hours[s][0]  ## check if >0
                if dhr > 0:
                    n = int(np.ceil(dhr / maxhr))
                    step = int(np.ceil((s.stop - s.start) / float(n)))
                    ii = list(range(s.start, s.stop, step))
                    if ii[-1] < s.stop:
                        ii.append(s.stop)
                    if len(ii) > 2 and ii[-1] - ii[-2] < step // 2:
                        del(ii[-2])
                    smallslices.extend([slice(a, b)
                                    for a, b in zip(ii[:-1], ii[1:])])

            slices = smallslices

            nbytes = f.header.nbytes
            logbin = np.zeros((f.nprofs, len(columns)), dtype=float)
            logbin[:,0] = dat.dday
            logbin[:,-2] = dat.dday
            logbin[:,-1] = dat.dday
            logbin[:,1] = nbytes * np.arange(f.nprofs, dtype=int)
            logbin[:,2] = nbytes
            logbin[:,3] = dat.ens_num

            for sl in slices:
                slen =  sl.stop - sl.start
                if slen < 5:
                    _log.warning("discarding short slice, len=%d, dday %10.7f" %
                             (slen, dat.dday[sl.start]))
                    continue
                lb = logbin[sl]
                iday = int(lb[0,0])
                seconds = int((lb[0,0] - iday) * 86400)
                name = "%s%4d_%03d_%05d.raw" % (self.ship, f.yearbase,
                                                    iday, seconds)
                dest = os.path.join(destdir, name)
                abssource = os.path.abspath(source)
                f_in = open(abssource, "rb")
                f_in.seek(sl.start * nbytes)
                nchunk = nbytes * (sl.stop - sl.start)
                with open(dest, "wb") as file:
                    file.write(f_in.read(nchunk))
                f_in.close()

                try:
                    ftest = FileBBWHOS(dest, self.sonar, yearbase=self.yearbase)
                    ftest.read(varlist=['VariableLeader'])
                    ftest.close()
                except Exception:
                    _log.warning("Deleting bad file %s split from %s",
                                dest, source)
                    os.remove(dest)
                    continue

                name_map.append((name, pathops.basename(source)))

                fn_logbin = dest + ".log.bin"
                outfile = binfile_n(fn_logbin, mode="w", columns=columns,
                                            name="ser_bin_log")
                outfile.write(lb)
                outfile.close()

        name_map.sort() # ordered by UHDAS name
        fmap = open(os.path.join(destdir, "name_map.txt"), "w")
        for pair in name_map:
            fmap.write("%s %s\n" % pair)
        fmap.close()

    def get_basedict(self):
        """
        Return a dictionary in which the key is the original vmdas
        filename base, and the value is the corresponding sequence
        of records from the name_map.txt file.

        Hence, each dictionary entry identifies a chunk of data with
        consecutive ping numbers, unless power failures caused
        resets.  In this case, two or more consecutive records
        in the value for a given key will have the same vmdas
        file name, which is the second field in the name_map record.

        """
        # For backward compatibility's sake
        py_version = sys.version_info[0]
        if py_version >= 3:
            with open(self.tree.rawsonarpath("name_map.txt"),
                          encoding='utf-8', errors='ignore') as newreadf:
                maptxt = newreadf.readlines()
        else:
            with open(self.tree.rawsonarpath("name_map.txt")) as newreadf:
                maptxt = newreadf.readlines()
        name_map = [line.split() for line in maptxt]
        bases = [record[1][:-6] for record in name_map]
        basedict = dict()
        for b, record in zip(bases, name_map):
            rlist = basedict.setdefault(b, [])
            rlist.append(record)
        return basedict

    @staticmethod
    def _find_time_pingnum(bfsa, dday, pingnum):
        """
        Helper for `convert_rbins`.

        *bfsa* is the array from a BinfileSet of N1R or N2R files.
        *dday* and *pingnum* are the values to be matched, taken from
        the .log.bin files.

        NOTE: Prior to v.1.5, ENR hundredts are actually tenths.
        That is corrected in the dday provided, but the bfsa[:,0]
        have actual hundredths.  Maybe that is OK.  Or maybe we have to
        round down so the bfsa[:,0] are in tenths.
        """

        i = np.argmin(np.abs(bfsa[:, 0] - dday))
        if bfsa[i, -1] == pingnum:
            return i
        else:
            return None

    def convert_rbins(self):
        """
        Convert rbins made by serasc2bin to the UHDAS form.

        The .log.bin file is used to look up the ADCP instrument time
        based on the ping number, and that time is used to replace the
        u_dday field, and to make an m_dday field that replaces the last
        two fields in the original file.
        """

        for base, names in self.get_basedict().items():
            # base is the part of the vmdas file name that
            # identifies a deployment.
            # names is the corresponding list of name_map.txt records,
            # each consisting of (uhdas_filename, vmdas_filename)
            sources = [name[0] for name in names]
            for inst, msg, num in self.navinfo:
                _log.info('-------------   processing rbins for %s',
                         ','.join([inst, msg, str(num)]))
                if num == 0:
                    continue
                _makedirs(self.tree.rbinpath(inst))
                rbin_glob = os.path.join(self.sourcedir, inst, f"{base}*.{msg}.rbin")
                _log.debug("In convert_rbins, rbin_glob is: %s", rbin_glob)
                # Bug fix - Ticket 730
                try:
                    bfs = BinfileSet(rbin_glob)
                except ValueError as err:
                    _log.warning('glob used: %s, yields: %s', rbin_glob, err)
                    continue
                bfsdat = bfs.array
                pn = bfsdat[:,-1]

                if self.fix_hundredths:
                    bfsdat[:,0] = self._fix_hundredths_nav(bfsdat[:,0])

                # If there was a power failure, upon resumption there
                # may be a sequence of PADCP records labeled as the
                # first ensemble; discard all but the last.
                if pn.size > 1:
                    igood = np.ones(pn.shape, dtype=bool)
                    igood[:-1] = np.diff(pn) != 0
                    bfsdat = bfsdat[igood]
                if pn.size == 0:
                    _log.warning("BinfileSet from glob '%s' is empty.", rbin_glob)
                columns = bfs.columns[:-2]
                columns.append("m_dday")
                for source in sources: # source is uhdas filename
                    sourcepath = self.tree.rawsonarpath(source + ".log.bin")
                    sourcebase = pathops.basename(source)
                    outpath = self.tree.rbinpath(inst, "%s.%s.rbin" %
                                                            (sourcebase, msg))
                    outfile = binfile_n(outpath, mode="w", columns=columns,
                                                name=bfs.name)
                    if bfsdat.size == 0:
                        _log.warning("rbin %s is empty", outpath)
                    else:
                        logbin = binfile_n(sourcepath).records
                        i0 = i1 = None
                        # Look for the first pingnum match, usually the first
                        # or second ping in logbin.
                        for ilog in range(len(logbin)):
                            p0 = logbin['pingnum'][ilog]
                            dday0 = logbin['unix_dday'][ilog]
                            i0 = self._find_time_pingnum(bfsdat, dday0, p0)
                            if i0 is not None:
                                break
                        if i0 is not None:
                            # Search for last match, backwards from the end.
                            for ilog in range(len(logbin) - 1, ilog, -1):
                                p1 = logbin['pingnum'][ilog]
                                dday1 = logbin['unix_dday'][ilog]
                                i1 = self._find_time_pingnum(bfsdat, dday1, p1)
                                if i1 is not None:
                                    break
                        if i1 is None:
                            _log.warning("%s is empty; there was no ping number match", outpath)
                        else:
                            i1 += 1
                            r_out = bfsdat[i0:i1, :-1].copy()
                            if self.verbose:
                                _log.info(' '.join([sourcepath, sourcebase]))
                            r_out[:, -1] = r_out[:, 0]
                            outfile.write(r_out)
                    outfile.close()
                    # An outfile is written for each "source", even if
                    # there are no records to put in it.

    def extract_heading(self):
        """
        Write rbins for heading from the ENR files.
        """
        for inst, msg, num in self.navinfo:
            if num != 0:
                continue
            outdir = self.tree.rbinpath(inst)
            _makedirs(outdir)
            sources = pathops.make_filelist(self.tree.rawsonarpath("*.raw"))
            for source in sources:
                internal_heading(source, self.sonar, outdir, self.yearbase)
            return


class LTA_Translate(LDWriter):
    '''
    LTA_Translate(filelist_or_globstring, inst)

    ... writes *bin,*cmd,*gps2 to disk.   Run from load directory.

    '''
    def __init__(self, filelist, sonar):
        # TODO: use sonar as input instead of inst
        self.sonar = sonar
        self.inst = Sonar(self.sonar)
        self.blk_max_nprofs = 512
        self._block = 0
        self._profile = 0

        filelist=pathops.make_filelist(filelist)

        for fname in filelist:
            self.ldcodas(fname)

        ##==> need to start a new block if block size would exceed 512

    def ldcodas(self, fname):
        self.mr = Multiread(fname, self.inst)
        # TODO - TR: improve this uggly quick fix. For instance:
        #            - Refactor Multiread to deal with mixed nb-bb LTA files
        #            - Pass on quick_adcp.py options differently
        #            - Centralize the info discovery in one class/config. file
        if self.inst.model in ('os', 'pn'):
            if 'nb' in self.sonar:
                self.mr.pingtype = 'nb'
            elif 'bb' in self.sonar:
                self.mr.pingtype = 'bb'
        self.data = self.mr.read()
        self.data.ampmean = self.data.amp.mean(axis=2)
        self.open_files(fname)
        self.get_block_vars()  #initializes self.ens
        config = self.make_config()
        self.write_block_start()
        self.write_block_vars(config)

        self._profile = 0
        for ii in range(len(self.data.dday)):
            # staging: add to self.ens, alter self.avg
            ok_to_write = self.get_profile_vars(ii)
            # possibly don't write it (eg. if bad nav)
            if ok_to_write:
                self.write_profile_start()
                self.write_profile_vars()
                self.write_gps2()
                self._profile += 1
                if self._profile == self.blk_max_nprofs:
                    self.write_block_start()
                    self.write_block_vars(config)
                    self._profile = 0
                    self._block += 1

        self.close_files() # resets profile to 0; increments block

    def write_block_start(self):
        self._cmd.write("%s_endian\n" % sys.byteorder)
        self._cmd.write("binary_file: %s.bin\n" % self.block_basename)
        self._cmd.write("new_block\ndp_mask: 1\n")

    def write_block_vars(self, config):
        self.bin_float("DEPTH", self.ens.dep)
        self.bin_double("CONFIGURATION_1", config)


    def open_files(self, fname):
        # File names are 1-based for historical reasons.
        self.block_basename = os.path.split(fname)[-1]
        self._cmdname =  self.block_basename + ".cmd"
        self._cmd = open(self._cmdname, 'wt')
        self._bin = open(self.block_basename + ".bin", 'wb')
        self._gps2 = open(self.block_basename + ".gps2", 'wt')

    def close_files(self):
        if self._cmd is not None:
            self._cmd.close()
            self._bin.close()
            self._gps2.close()
            self._cmd = None

            self._profile = 0
            self._block += 1

            try:
                _log.info("%s  %s %s  %10.5f %10.5f",
                     self._cmdname,
                     self._block_start_date, self._profile_date,
                     self._block_start_dday, self._profile_dday)
            except AttributeError:
                _log.debug("Closing %s, no profiles written", self._cmdname)


    def get_block_vars(self):
        # for write_block_vars, config1
        self.beam_angle = self.mr.sysconfig.angle
        self.ping_interval = self.data.FL['TPP_sec'] + self.data.FL['TPP_hun']/100.
        self.have_bt = True #<---

        dt = self.data.nav_end_txy[:,0] - self.data.nav_start_txy[:,0]
        dt = dt.filled(np.nan)   ## numpy 1.9.2 round fails with masked scalar
        self.ens_secs = np.round(np.median(86400*dt))

        self.ens = Bunch()
        self.ens.sysconfig = self.data.sysconfig
        self.ens.CellSize = self.data.CellSize
        self.ens.Pulse = self.data.Pulse
        self.ens.Blank = self.data.Blank
        self.ens.NCells= self.data.NCells

        self.params=Bunch()
        self.params.tr_depth = self.data.VL['XducerDepth'][0]/10.
        self.params.head_align = self.data.FL['EA']/100.
        self.ens.dep = self.data.dep + self.params.tr_depth
        self.edit_params = Bunch()
        self.edit_params.rl_startbin = 0
        self.edit_params.rl_endbin = self.data.NCells
        self.edit_params.ecutoff = 3


    def get_profile_vars(self, ii):
        # for write_profile_start
        # self._profile = ii  # take this outside so we can roll over to new blocks
        self.ens = Bunch() ## re-initialize?
        best=Bunch()

        # for write_gps2
        dday = self.data.nav_end_txy[ii,0]
        lon =  self.data.nav_end_txy[ii,1]
        lat =  self.data.nav_end_txy[ii,2]

        ## if bad navigation return False (write==false)
        if np.any(np.isnan([dday, lon, lat])):
            msg = 'bad nav data. %s: skipping ensemble %d' % (self.block_basename, self.data.ens_num[ii])
            _log.warning(msg)
            return False

        best.dday=[dday, dday, dday]
        best.lon=[lon, lon, lon]
        best.lat=[lat, lat, lat]
        self.ens.best = best

        self.ens.times = Bunch()
        self.ens.times.dday = best.dday

        self.ens.ens_num=[0, self.data.ens_num[ii]]
        self.ens.dep = self.data.dep + self.params.tr_depth ## adding tr_depth
        self.ens.nprofs = self.data.num_pings[ii]

        # for access
        self.avg = Bunch
        self.avg.lgb = len(self.ens.dep)

        # for ancil1
        # stats is  [mn, std, last, n]
        self.avg.t_stats = [self.data.temperature[ii], 0.0,
                            self.data.temperature[ii], self.ens.nprofs]
        self.ss_fixer = None #maybe use fixer from pingavg? but when?


        # for ancil2
        self.avg.h_stats = [self.data.heading[ii],
                            self.data.VL['HeadingStd'][ii]/100.,
                            self.data.heading[ii],
                            self.ens.nprofs]
        self.avg.p_stats = [self.data.pitch[ii],
                            self.data.VL['PitchStd'][ii]/100.,
                            self.data.pitch[ii],
                            self.ens.nprofs]
        self.avg.r_stats = [self.data.roll[ii],
                            self.data.VL['RollStd'][ii]/100.,
                            self.data.roll[ii],
                            self.ens.nprofs]
        self.avg.soundspeed = self.data.VL['SoundSpeed'][ii]
        self.avg.meandh = 0
        self.avg.mab =0

        nd=len(self.data.dep)

        #for write_profile_vars
        self.avg.bt = [self.data.bt_vel[ii,0],
                       self.data.bt_vel[ii,1],
                       np.ma.mean(self.data.bt_depth[ii,:])]
        self.avg.nav = 1e38 * np.ones((4,), np.float64)  #putnav fixes this?
        self.avg.u = self.data.vel1[ii,:]
        self.avg.v = self.data.vel2[ii,:]
        self.avg.w = self.data.vel3[ii,:]
        self.avg.e = self.data.vel4[ii,:]
        self.avg.amp = self.data.ampmean[ii,:]
        self.avg.rawamp = self.data.amp[ii,:,:]
        self.avg.pg = self.data.pg4[ii,:]
        self.avg.pg3 = self.data.pg1[ii,:]  # first field is the
                                            # percentage of good 3-beam
                                            # solutions.
        self.avg.sw = None
        self.avg.rawsw = None
        self.avg.profile_flags =  np.zeros_like(self.avg.pg)

        # make masked arrays for variables that do not exist, but
        #   which we require 'play nice' with gautoedit.py, for instance
        self.avg.resid_stats = np.ma.masked_all((6, nd), dtype=np.float32)
        self.avg.tseries_stats = np.ma.masked_all((7,), dtype=np.float32)
        self.avg.tseries_diffstats = np.ma.masked_all((4,), dtype=np.float32)
        self.avg.estd = np.ma.masked_all(self.avg.e.shape,  dtype=np.float32)


        return True

#-----------

def internal_heading(fname, sonar, outdir, yearbase):
    """
    Write heading from .raw file into rbin file.

    """
    f = FileBBWHOS(fname, Sonar(sonar), yearbase=yearbase)
    dat = f.read(varlist=['VariableLeader'])

    columns = ['u_dday', 'heading', 'm_dday']
    hdgbin = np.zeros((f.nprofs, len(columns)), dtype=float)
    hdgbin[:,0] = dat.dday
    hdgbin[:,-1] = dat.dday
    hdgbin[:,1] = dat.heading

    fname_out = pathops.basename(fname) + ".hdg.rbin"
    fname_out = os.path.join(outdir, fname_out)
    outfile = binfile_n(fname_out, mode="w", columns=columns,
                                name="internal_heading")
    outfile.write(hdgbin)
    outfile.close()


#------------

def _get_key(line):
    '''
    Return NMEA key such as '$GPGGA', "$PASHR', '$PASHR,ATT', $PSXN,20',
    and boolean, True if a checksum is likely present.

    This is far too specialized and restrictive, but VmDAS is rude about
    adding $PADCP to serial lines (clobbering some).
    Do we need to broaden this to include additional message types?
    '''
    if "$PADCP" in line:
        return None, False
    try:
        parts = line.rstrip().split(',')
        if parts[0] == '$PASHR':
            if parts[1] in ('ATT', 'AT2', 'PAT', 'POS'):
                key = ','.join([parts[0], parts[1]])
            else:
                key = parts[0]
        elif parts[0] in ('$PSXN', '$PSAT'):
            key = ','.join([parts[0], parts[1]])
        elif parts[0][-3:] in ('DID', 'GGA', 'GLL', 'HDT', 'HDG'):
                key = parts[0]
        else:
            key = None
    except IndexError:
        _log.debug('could not parse "%s"', line)
        return None, False

    has_checksum = '*' in parts[-1]

    return key, has_checksum



class VmdasInfo:
    '''
    info about LTA files; methods to get info, print info, link in time order
    '''
    def __init__(self, file_or_glob, model=None, verbose=False, quick=False):

        allowed_ext = ('ENR', 'ENS', 'ENX', 'STA', 'LTA')
        allfiles = pathops.make_filelist(file_or_glob)
        filelist = []
        for f in allfiles:
            suffix = os.path.splitext(f)[-1].upper()[1:]
            if suffix not in allowed_ext:
                _log.debug('file %s not allowed' % (f) + 'choose from '
                          + ','.join(allowed_ext))
            else:
                ## maybe only look at nonzero files?
                ##                 if os.path.getsize(f) > 0:

                filelist.append(f)
        if model is None:
            raise ValueError("must set instrument model: 'os', 'pn', 'bb', 'wh'")
        self.suffix = suffix

        self.verbose = verbose
        self.model=model
        self.filelist = filelist
        self.filelist.sort()        # how it came in

        self.get_infodicts(quick=quick)
        self.get_meta()

    def get_infodicts(self, quick=False):

        self.infodicts={}
        self.ddranges={}

        if self.verbose:
            print('\ngetting detailed information from ADCP data files\n\n')
        for fname in self.filelist:
            idict = self._getinfo(fname, quick=quick)
            self.ddranges[fname] = idict['timeinfo'].pctime_ends
            self.infodicts[fname] = idict
        if quick:
            print('quick results only')
            return

        # else read N*R files as well
        for fname in self.filelist:
            basename = fname[:-4]
            Nglob = os.path.join(basename +'*.N?R')
            try:
                Nfilelist = pathops.make_filelist(Nglob)
                Ndict = self._messages(Nfilelist)
                for Ntype in Ndict.keys():  #N1R, N2R, N3R
                    nkk = list(Ndict[Ntype].keys()) # serial messages
                    nkk.sort()
                    self.infodicts[fname][Ntype] = nkk
            except Exception:
                # should be log.exception?
                _log.debug('%s: problem with serial messages' % (fname))

        _log.info('\n(done guessing serial inputs from files)\n')

    #-----------------
    def _init_dict(self,):
        dummydict = Bunch()
        for name in ['filename', 'short_vmoname', 'pingtypes', 'bottomtrack',
                     'datadir',
                     'sysconfig', 'yearbase', 'EA', 'number_ensemble_resets']:
            dummydict[name] = None
        dummydict['numprofs'] = 0

        for name in ['CellSize', 'Blank', 'Pulse', 'NCells', 'NPings']:
            dummydict[name] = Bunch()

        dummydict['timeinfo'] = Bunch()
        for name in ['pctime_ends', 'min_dt', 'max_dt', 'median_dt',
                     'num_time_reversals', 'num_time_stopped', 'max_dt',
                     'min_dt', 'num_time_reversals', 'num_time_stopped',
                     'median_dt']:
            dummydict['timeinfo'][name] = None
        dummydict['timeinfo'].pctime_ends = ['NA', 'NA']

        dummydict['navinfo'] = Bunch()
        for name in ['min_dt', 'max_dt', 'median_dt',
                     'num_time_reversals', 'num_time_stopped']:
            dummydict['navinfo'][name]=None

        return dummydict

    #-----------------
    def _getinfo(self, fname, quick=False):
        '''
        fname should be ENR, ENX, ENS, STA, LTA
        '''
        ## ONE file only
        infodict = self._init_dict()
        if os.path.getsize(fname) == 0:
            return infodict
        else:
            try:
                m=Multiread(fname, self.model)
            except Exception:
                # should be log.exception?
                _log.warning('cannot read file %s' % (fname))
                return infodict
        ## vmdas data does not change configs inside a file
        infodict['filename'] = os.path.split(fname)[-1]
        # pingtypes is a list of dictionaries; just use the dictionary
        infodict['pingtypes'] = guess_pingtypes(m)
#        infodict['bottomtrack'] = m.bt[0]
        infodict['sysconfig'] = m.sysconfig
        infodict['numprofs'] = m.nprofs

        for p in infodict['pingtypes'].keys():
            m.pingtype=p
            dd=m.read(ends=1)
            infodict['CellSize'][p] = dd.CellSize
            infodict['Blank'][p] = dd.Blank
            infodict['Pulse'][p] = dd.Pulse
            infodict['NCells'][p] = dd.NCells
            infodict['NPings'][p] = dd.NPings

            # these are all the same for either pingtype
            infodict['yearbase'] = dd.yearbase
            infodict['timeinfo'].pctime_ends = dd.dday
            if hasattr(dd, 'nav_end_txy'):
                infodict['navinfo']['lon_ends'] =  dd.nav_end_txy[:,1]
                infodict['navinfo']['lat_ends'] =  dd.nav_end_txy[:,2]
                infodict['navinfo']['UTC_ends'] =  dd.nav_end_txy[:,0]
            infodict['EA'] = dd.FL['EA']/100.
            #
            ## look for backward timestamps
            dd=m.read()
            resets = (np.diff(dd.ens_num) < 0).sum()
            infodict['number_ensemble_resets'] = resets
            # see whether there are any unmasked BT depths
            infodict['bottomtrack'] = not dd.bt_depth.mask.all()
            #
            ## raw time
            ## EF ## check: is masked array use correct?
            dt = 86400*np.ma.diff(dd.dday)
            if len(dt) > 0:
                infodict['timeinfo'].max_dt = dt.max()
                infodict['timeinfo'].min_dt = dt.min()
                infodict['timeinfo'].num_time_reversals = (dt < 0).sum()
                infodict['timeinfo'].num_time_stopped = (dt == 0).sum()
                infodict['timeinfo'].median_dt = np.ma.median(dt)

            if hasattr(dd, 'nav_end_txy'):
                dt = 86400*np.ma.diff(dd.nav_end_txy[:,0])
                if len(dt) > 0:
                    infodict['navinfo'].max_dt = dt.max()
                    infodict['navinfo'].min_dt = dt.min()
                    infodict['navinfo'].num_time_reversals = (dt < 0).sum()
                    infodict['navinfo'].num_time_stopped = (dt == 0).sum()
                    infodict['navinfo'].median_dt = np.ma.median(dt)

        ## get VMO information
        vmofile=fname[:-4] + '.VMO'
        infodict['vmo_warning'] = []
        infodict['vmo_heading'] = []
        infodict['vmo_position'] = []

        short_vmoname = os.path.basename(vmofile)
        infodict['short_vmoname'] = short_vmoname
        vmoroot, vmoext = os.path.splitext(short_vmoname)
        vmoparts = vmoroot.split('_')

        inststring_dict = dict(
            bb='Broadband',
            wh='Workhorse',
            os='Ocean Surveyor',
            pn='Pinnacle',
            )

        vellist =  ('lta', 'sta','enr', 'ens', 'enx')
        infodict.instmodel = guess_instmodel_from_datafile(fname)
        infodict.inststring = inststring_dict[infodict.instmodel]

        if vmoparts[-1] == '000000' and fname[-3:].lower() in vellist:
            if os.path.exists(vmofile):
                # For backward compatibility's sake
                py_version = sys.version_info[0]
                if py_version >= 3:
                    with open(vmofile, 'r', encoding='utf-8',
                                 errors='ignore') as newreadf:
                        lines = newreadf.readlines()
                else:
                    with open(vmofile, 'r') as newreadf:
                        lines = newreadf.readlines()
                clues = ['ADCPSetupMethod','AlignmentOffsetEA']
                for line in lines:
                    if 'HeadingSource' in line:
                        infodict['vmo_heading'].append(line.rstrip())
                    if 'GGASource' in line:
                        infodict['vmo_position'].append(line.rstrip())
                    if 'FirstAvgTime' in line:
                        infodict['FirstAvgTime'] = line.rstrip()
                    if 'SecondAvgTime' in line:
                        infodict['SecondAvgTime'] = line.rstrip()
                    for cc in clues:
                        if cc in line:
                            infodict['vmo_warning'].append(line.rstrip())
            else:
                wlist=['','',
                       '===> WARNING!!',
                       'no matching .VMO file for %s\n' % (infodict['short_vmoname'])]
                _log.info('\n'.join(wlist))


        if quick:
            return infodict
        # get EA_estimator results for that chunk of EA data
        part1, part2 = os.path.split(fname)
        infodict['datadir'] = os.path.realpath(part1)
        prefix = part2[:-10]
        ENRlist = pathops.make_filelist(os.path.join(part1, prefix+'*.ENR'),
                                        allow_empty=True)
        ENR_0size = []
        for efile in ENRlist:
            if os.path.getsize(efile) == 0:
                ENR_0size.append(efile)
        for efile in ENR_0size:
            ENRlist.remove(efile)
        #remaining files
        numenr = len(ENRlist)
        if numenr == 0:
            prettystr = '\ncould not get EA estimate from ENR files: %s\n ' % (str(ENRlist))
            read_enr = False
        elif numenr > 3:
            step = numenr*10
            read_enr=True
        else:
            step = 1
            read_enr=True
        if read_enr:
            try:
                m=Multiread(ENRlist, infodict.instmodel)
                if self.verbose:
                    print('estimating EA from raw files (step = %d): %s\n' % (step, str(ENRlist)))
                data=m.read(step=step, stop=10000)
                npts = len(data.dday)
                if npts <=3:
                    prettystr = '\n# got N=%d points from %s\n' % (npts*step, str(ENRlist))
                else:
                    prettystr = EA_estimator.make_pretty(data, underway=2, bin=2, prefix='ENR_estimate: ')
            except Exception:
                prettystr = '\ncould not get EA estimate from ENR files: %s\n ' % (str(ENRlist))

        infodict['EA_estimate'] = prettystr
        return infodict

    def sort_bytime(self, outfile=None):
        '''
        set up attribute with time-sorted filelist
        '''
        startdays = []
        for f in self.filelist:
            startdays.append(self.ddranges[f][0])
        #
        self.startdays_timesorted=[]
        self.infodicts_timesorted=[]
        self.filelist_timesorted=[]
        for ii in np.argsort(startdays):
            # do this with the short filename
            sorted_fname = self.filelist[ii]
            self.startdays_timesorted.append(startdays[ii])
            self.infodicts_timesorted.append(self.infodicts[sorted_fname])
            self.filelist_timesorted.append(sorted_fname)
        olines=[]
        if startdays == self.startdays_timesorted:
            olines.append('\nFiles are in ascii order: also already in time order\n')
        else:
            olines.append('\nreordering files: ascii order is NOT TIME ORDER\n')

        ostr = '\n'.join(olines)
        if outfile:
            with open(outfile,'a') as file:
                file.write(ostr)
        else:
            _log.info(ostr)

    def _messages(self, filelist, numlines=100):
        '''
        return a dictionary with
           keys ['N1R', 'N2R', 'N3R' (whatever exists)
           values are a list of unique NMEA messages in the N*R file
        '''
        Ndict = dict()
        if isinstance(filelist, str):
            filelist=[filelist,]
        for fname in filelist:
            Ntype = fname.split('.')[-1]
            if Ntype not in list(Ndict.keys()):
                Ndict[Ntype] = {}
            # For backward compatibility's sake
            py_version = sys.version_info[0]
            if py_version >= 3:
                with open(fname, 'r', encoding='utf-8', errors='ignore') as newreadf:
                    lines = newreadf.readlines()
            else:
                with open(fname, 'r') as newreadf:
                    lines = newreadf.readlines()
            _log.info('read %d out of %8d lines from %s' % (numlines, len(lines), fname))
            for line in lines[:numlines]:
                key, has_checksum = _get_key(line)
                if key not in list(Ndict[Ntype].keys()) and key is not None:
                    if has_checksum:
                        Ndict[Ntype][key] = line.rstrip()
                    else:
                        Ndict[Ntype][key+ ',NO CHECKSUM'] = line.rstrip()
        return Ndict

    # useful methods

    def get_meta(self):
        lines=[]
        for fname in self.filelist:
            if os.path.getsize(fname) == 0:
                lines.append(f'file {fname} has size 0 -- skipping')
            else:
                lines.append(f'\n------- {fname} --------\n')
                idict = self.infodicts[fname]
                for kk, vv in sorted(idict.items()):
                    lines.append(f'{kk:>15s}: {vv}')
            lines.append('\n\n')
        self.metalines=lines

    def print_meta(self, outfile=None):

        ostr = '\n'.join(self.metalines)
        if outfile:
            with open(outfile,'a') as file:
                file.write(ostr)
        else:
            _log.info(ostr)

    def print_scan(self, outfile=None, include_glossary=True):
        '''
        for quick_adcp.py
        '''
        fstr = '%2s %20s %15s %10.4f %10.4f %7ds %5dm %5dm %7d   %s    %ss  %7d  %6d'
        lines = []
        lines.append(' ("*" is out of time order)')
        lines.append('  #filename                  ' +
                 'datestr         startdd     enddd     gapsecs   ' +
                 'bin   blank   Nbins   ping    medens PingsPerProf numprofs')

        fullddrange = [10000, -10000]
        fullddstr = ['a','b']
        prev_file_end_time = None

        for fname in self.filelist:
            reverse_comment = '  '   # replace with '*' if backwards time order
            idict=self.infodicts[fname]

            if idict['numprofs'] == 0:
                lines.append('%s is empty' % (fname))
                continue

            yearbase = idict['yearbase']
            startdd = self.ddranges[fname][0]
            enddd = self.ddranges[fname][1]

            if prev_file_end_time is None:
                gap = 0
            else:
                gap = round(86400*(startdd - prev_file_end_time))
                if gap < 0:
                    reverse_comment = '*'
            # reset
            prev_file_end_time = enddd

            startstr = to_datestring(yearbase, startdd)
            endstr = to_datestring(yearbase, enddd)

            median_dt = idict['timeinfo'].median_dt
            if median_dt is None:
                median_dtstr = ' NA '
            else:
                median_dtstr = '%5.2f' % (median_dt)

            if startdd < fullddrange[0]:
                fullddrange[0]=startdd
                fullddstr[0]=startstr
            if enddd > fullddrange[1]:
                fullddrange[1]=enddd
                fullddstr[1]=endstr


            for p in idict['pingtypes'].keys():

                if p == 'bb':
                    pstr = 'bb  '
                else:
                    pstr = '  nb'
                if idict['bottomtrack']:
                    pstr += '/bt'
                else:
                    pstr += '/--'

                lines.append( fstr % (reverse_comment,
#                                     os.path.split(idict['filename'])[-1],
                                      idict['filename'],
                                      startstr,
                                      startdd,
                                      enddd,
                                      gap,
                                      idict['CellSize'][p],
                                      idict['Blank'][p],
                                      idict['NCells'][p],
                                      pstr,
                                      median_dtstr,
                                      idict['NPings'][p],
                                      idict['numprofs']))

        lines.append('\n')

        if self.suffix in ('LTA', 'STA'):
            word = 'averaged'
        else:
            word = 'single-ping'

        glossary = ['=== GLOSSARY ===',
                    'datestr     : date of data start (convert to startdd)',
                    'startdd     : floating point decimal day of data start (Jan 1 noon UTC = 0.5)',
                    'enddd       : floating point decimal day of data end (Jan 1 noon UTC = 0.5)',
                    'gapsecs     : instrument setting: time gap in seconds between this and the previous file ',
                    'bin         : instrument setting: bin size in meters',
                    'blank       : instrument setting: size of blank (meters)',
                    'Nbins       : instrument setting: number of bins',
                    'ping        : broadband, narrowband, bottomtrack',
                    'medens      : estimated time duration of profiles in seconds'
                    'PingsPerProf: number of pings in the profile (numpings=1 for ENR,ENS,ENX)',
                    'numprofs    : number of %s profiles in the file' % (word),
                    '====\n'
        ]

        caveat = []
        if self.suffix in ('LTA', 'STA'):
            caveat = [
                'NOTE ABOUT NUMBER OF PINGS PER AVERAGE ("PingsPerProf")',
                'LTA and STA data are VmDAS "Long Term Average" and "Short Term Average", respectively.',
                'Only the first ensemble average contains a value for "number of pings per ensemble".',
                'If the instrument was set to ping only when receiving a synchronizing pulse,',
                '(commonly called "triggering"), then the number of pings for each ensemble is unknown.',
                'Because VmDAS can get "stalled", the first ensemble might not be a good representation.',
                'You are advised to look at the *.ENR data to determine time between pings',
                '... or, to have more control, and get a better dataset, reprocess from ENR.',
                '----------------------\n'
            ]

        if include_glossary:
            ostr = '\n'.join(lines + glossary + caveat)
        else:
            ostr = '\n'.join(lines)
        if outfile:
            with open(outfile,'a') as file:
                file.write(ostr)
        else:
            _log.info(ostr)
        return fullddstr  ### for ScanLTA



    ## the next functions were added from scripts/vmdas_info.py

    def get_beaminst_info(self, outfile=None):
        '''
        print a string describing frequency, beam angle, and EA used by VmDAS
        return list of EA used
        '''
        vm = self
        freq = None
        beamangle = None
        EA=[]
        outlist=[]
        # first file might be empty
        for f in vm.filelist:
            if vm.infodicts[f]['numprofs'] > 0:
                if freq is None:
                    freq = vm.infodicts[f]['sysconfig']['kHz']
                    beamangle = vm.infodicts[f]['sysconfig']['angle']
                    outlist.append('\n\ninstrument frequency is %d' % (freq))
                    outlist.append('beam angle is %d' % (beamangle))
                else:
                    newfreq = vm.infodicts[f]['sysconfig']['kHz']
                    # newbeamangle is not used
                    # newbeamangle = vm.infodicts[f]['sysconfig']['angle']
                    if newfreq != freq:
                        outlist.append('WARNING:')
                        outlist.append('   instrument changed (new freq=%s) in %s' % (newfreq, f))
        #
                if vm.infodicts[f]['EA'] not in EA:
                    EA.append(vm.infodicts[f]['EA'])
                # now get EA estimate from ENR data; add this to the collective
                vm.infodicts[f]['EA_estimate_from_ENR'] = self.get_EA_from_ENR(vm.infodicts[f],
                                                                               verbose=self.verbose)

        if len(EA) == 1:
            outlist.append('transducer angle (EA) was set as %5.3f' % (EA[0]))
        elif len(EA) > 1:
            outlist.append('WARNING: Multiple acquistion angles: EA = %s\n\ndetails:\n' % (str(EA)))
            for f in vm.filelist:
                if vm.infodicts[f]['EA'] is not None:
                    outlist.append('%s %f' % (f,vm.infodicts[f]['EA']))
        else:
            outlist.append('transducer angle not found... only exists in ENX, STA, LTA')
        outlist.append('\n----------\n')

        ostr = '\n'.join(outlist)
        if outfile:
            with open(outfile,'a') as file:
                file.write(ostr)
        else:
            _log.info(ostr)

        return EA #used by vmdas_quick_ltaproc.py

    def get_enslen(self, outfile=None):
        '''
        print warning if multiple enslen were used
        return list of nonzero enslen used
        '''
        vm = self
        enslen=[]
        outlist=[]
        # first file might be empty

        for f in vm.filelist:
            idict = vm.infodicts[f]
            median_dt = idict['timeinfo'].median_dt
            if median_dt is None:
                continue
            # now we have a real median_dt
            median_dt = float(np.ma.getdata(np.floor(median_dt)))
            if len(enslen) == 0:
                enslen.append(np.floor(median_dt))
            if len(enslen) > 0: # only add enslen if nonzero
                if (median_dt < np.min(enslen)-10) or (median_dt > np.min(enslen) + 10):
                    enslen.append(np.floor(median_dt))

        if len(enslen) == 1:
            outlist.append('ensemble length = %d sec (+/- 10sec)' % (enslen[0]))
        elif len(enslen) > 1:
            outlist.append('WARNING: Multiple ensemble lengths (seconds): %s\n\n' % (str(enslen)))
            outlist.append('details:\n')
            for f in vm.filelist:
                med_dt = vm.infodicts[f]['timeinfo'].median_dt
                if med_dt is None:
                    med_dt = 0
                outlist.append('%s %d' % (f, np.floor(med_dt)))
        else:
            outlist.append('error calculating ensemble length (seconds)')
        outlist.append('\n----------\n')

        ostr = '\n'.join(outlist)
        if outfile:
            with open(outfile,'a') as file:
                file.write(ostr)
        else:
            _log.info(ostr)

        return np.array(enslen) #used by vmdas_quick_ltaproc.py


    def get_npings(self, outfile=None):

        '''
        return list of NPings
        '''
        vm = self
        npinglist = []
        for f in vm.filelist:
            idict = vm.infodicts[f]
            npinglist.append(idict.NPings)
        return npinglist


    def get_instrument(self, outfile=None):
        '''
        print warning if log files missing
        return list instrument models if found
        '''
        vm = self
        models=[]
        mstrings = []
        outlist=[]

        nonemptyfiles = [f for f in vm.filelist if os.path.getsize(f) > 0]

        for f in nonemptyfiles:
            idict = vm.infodicts[f]
            if len(idict.instmodel) > 0 and idict.instmodel not in models:
                models.append(idict.instmodel)
                mstrings.append(idict.inststring)

        if len(models) == 1:
            outlist.append('all data from instrument "%s"' % (mstrings[0]))
        else:
            outlist.append('WARNING: multiple models found: %s' % mstrings)
            print(outlist)
            raise ValueError('multiple instrument models found')

        instlist = []

        for f in nonemptyfiles:
            idict = vm.infodicts[f]
            ss = '%s%s' % (models[0], idict['sysconfig']['kHz'])
            if ss not in instlist:
                instlist.append(ss)
        if len(instlist) == 1:
            outlist.append('all files come from %s' % (instlist[0]))
        elif len(instlist) > 1:
            outlist.append('WARNING: Multiple instruments found:\n')
            outlist.append('details:\n')
            for f in vm.filelist:
                idict = vm.infodicts[f]
                outlist.append('%s instrument = <%s>' % (f, idict.inststring))
        else:
            outlist.append('could not determine instrument: no LOG files??')
        outlist.append('\n----------\n')

        ostr = '\n'.join(outlist)
        if outfile:
            with open(outfile,'a') as file:
                file.write(ostr)
        else:
            _log.info(ostr)

        # FIXME: Why return a masked array?  It is contrary to the docstring.
        return np.ma.array(models) #used by vmdas_quick_ltaproc.py

    def get_EA_from_ENR(self, infodict, outfile=None, verbose=False):
        '''
        print EA estimate from ENR files associated with one infodict
        '''
        filebase = infodict['filename'][:-10]
        datadir =  infodict['datadir']
        enrglobstr = os.path.join(datadir, filebase + '*ENR')
        # Bug fix - Ticket 730
        if not glob.glob(enrglobstr):
            _log.info('Could not estimate EA from %s' % enrglobstr)
            return
        ENRlist_orig=pathops.make_filelist(enrglobstr)
        ENRlist=pathops.make_filelist(enrglobstr)
        ENR_0size = []
        for efile in ENRlist:
            if os.path.getsize(efile) == 0:
                ENR_0size.append(efile)
        for efile in ENR_0size:
            ENRlist.remove(efile)
            _log.info('file %s had zero size' % (efile))
        #remaining files
        numenr = len(ENRlist)
        if numenr == 0:
            prettystr = 'could not get EA estimate from ENR files: %s\n ' % (str(ENRlist_orig))
            read_enr = False
        else:
            read_enr = True
        if read_enr:
            try:
                instrument = infodict.instmodel
                if verbose:
                    print('reading %d ENR files' % (len(ENRlist)))
                m=Multiread(ENRlist, instrument)
                if verbose:
                    print('ENR files contain %d profiles' % (m.nprofs))
                if m.nprofs > 10000:
                    enrstep=10
                data=m.read(step=enrstep, stop=10000)
                if verbose:
                    print('reading up to %d profiles with step = %d' % (10000, enrstep))
                npts = len(data.dday)
                if verbose:
                    print('estimating transducer angle from %d points' % (npts))
                if npts <=3:
                    prettystr = '# got N=%d points from %s\n' % (npts*enrstep, str(ENRlist))
                    prettystr += '# subsample by fewer or pick a longer file'
                else:
                    prettystr = EA_estimator.make_pretty(data)
            except Exception:
                prettystr = 'could not get EA estimate from ENR files: %s\n ' % (str(ENRlist))
        return prettystr

    def get_badfile_info(self, outfile=None):
        '''
        return a string with time stalled or time reversals
        '''
        badfiles = []
        outlist = []
        for ff in self.filelist:
            idict = self.infodicts[ff]
            kklist = list(idict.keys())
            if 'numprofs' in kklist:
                numprofs = idict['numprofs']
                if numprofs <= 1:
                    badfiles.append('%s (%d ensembles)' % (ff, numprofs))
            if 'number_ensemble_resets' in kklist:
                ens_reset = idict['number_ensemble_resets']
                if ens_reset is not None:
                    if ens_reset > 0:
                        badfiles.append('%s (ensemble reset %d times)' % (ff, ens_reset))
            if 'timeinfo' in kklist:
                min_dt = idict['timeinfo'].min_dt
                if min_dt is not None and min_dt <= 0:
                    badfiles.append('%s (min PC time step %f sec)' % (ff, min_dt))
                tt = idict['timeinfo'].num_time_reversals
                if tt is not None and tt > 0:
                    badfiles.append('%s (%d PC time reversals)' % (ff, tt))
                tt = idict['timeinfo'].num_time_stopped
                if tt is not None and tt > 0:
                    badfiles.append('%s (%d PC time stalled)' % (ff, tt))
            if 'navinfo' in kklist:
                min_dt = idict['navinfo'].min_dt
                if min_dt is not None and min_dt <= 0:
                    badfiles.append('%s (min UTC end time step %f sec)' % (ff, min_dt))
                tt = idict['navinfo'].num_time_reversals
                if tt is not None and tt > 0:
                    badfiles.append('%s (%d UTC end time reversals)' % (ff, tt))
                tt = idict['navinfo'].num_time_stopped
                if tt is not None and tt > 0:
                    badfiles.append('%s (%d UTC end time stalled)' % (ff, tt))
        #
        if len(badfiles) > 0:
            outlist = ['\n WARNINGS::\n', '\n'.join(badfiles), '\n----------\n']

        ostr = '\n'.join(outlist)
        if outfile:
            with open(outfile,'a') as file:
                file.write(ostr)
        else:
            _log.info(ostr)

    ## should do this by pattern recognition not [0] or [1]
    # looking for this:
    # ['HeadingSource(0:adcp,1:navHDT,2:navHDG,3:navPRDID,4:manual)=1',

    def guess_heading_source_lta(self, outfile=None):
        '''
        return a string with a guess for heading source
        '''
        vm = self
        outlist=[]
        outlist.append('Heading Source information comes from *.VMO files;')
        outlist.append('Duplicate entries with different values require further investigation:')
        outlist.append('\n')
        #
        paths=[]
        for f in vm.filelist:
            pf = os.path.split(f)
            if pf[0] not in paths:
                paths.append(pf[0])
        #
        ext = pf[1][-3:]
        vellist =  ('lta','sta','enr', 'ens', 'enx')
        for pp in paths:
            vglobstr = os.path.join(pp,'*.VMO')
            vbase = []
            vglob = glob.glob(vglobstr)
            if len(vglob) > 0:
                vmos = pathops.make_filelist(vglobstr)
                vmos.sort()
                for v in vmos:
                    vbase.append(os.path.split(v)[1][:-4])
            # these might be ENX, ENR, ENS so only take the first of the series
            #
            pglobstr = os.path.join(pp,'*.%s' % (ext))
            pbase=[]
            pglob = glob.glob(pglobstr)
            if len(pglob) > 0:
                allpfiles = pathops.make_filelist(pglobstr)
                for pf in allpfiles:
                    short_name = os.path.basename(pf)
                    proot, pext = os.path.splitext(short_name)
                    parts = proot.split('_')
                    if parts[-1] == '000000' and pext[-3:].lower() in vellist:
                        pbase.append(proot)
            #
            v_only=[]
            p_only=[]
            both=[]
            for v in vbase:
                if v in pbase:
                    both.append(v)
                else:
                    v_only.append(v)
            for p in pbase:
                if p in vbase:
                    both.append(p)
                else:
                    p_only.append(p)
            if len(p_only) > 0:
                outlist.append('WARNING: mismatch between %s and VMO files' % (ext))
                outlist.append('No matching VMO file for: %s ' % str(p_only))
            if len(v_only) > 0:
                outlist.append('WARNING: mismatch between %s and VMO files' % (ext))
                outlist.append('No matching %s file for: %s' % (ext, str(v_only)))
        #
        try:
            vmo_heading = []
            for ff in vm.filelist:
                short_fname = os.path.basename(ff)
                idict = vm.infodicts[ff]
                if os.path.getsize(ff) > 0:
                    if 'vmo_heading' not in idict.keys():
                        wlist=['','', '===> WARNING!!',
                               'no heading device found for %s\n' % (short_fname)]
                        _log.info('\n'.join(wlist))
                        print('\n'.join(wlist))
                    else:
                        for heading in idict['vmo_heading']:
                            if heading not in vmo_heading:
                                vmo_heading.append(heading)

            if len(vmo_heading) > 1:
                outlist.append('\n'.join(vmo_heading))
            elif len(vmo_heading) == 1:
                outlist.append(vmo_heading[0])
            else:
                outlist.append('\ncould not find heading source for %s' % (
                    short_fname))
            outlist.append('\n----------\n')
        except Exception:
            #FIXME: discarding the actual exception and substituting IOError
            #doesn't make sense, here and elsewhere.
            raise IOError('Error finding Heading Source')
        #
        try:
            vmo_position = []
            for ff in vm.filelist:
                if os.path.getsize(f) > 0:
                    short_fname = os.path.basename(ff)
                    idict = vm.infodicts[ff]
                    if 'vmo_position' not in idict.keys():
                        wlist=['','', '===> WARNING!!',
                               'no position device found for %s\n' % (short_fname)]
                        _log.info('\n'.join(wlist))
                        print('\n'.join(wlist))
                    else:
                        for position in idict['vmo_position']:
                            if position not in vmo_position:
                                vmo_position.append(position)

            if len(vmo_position) > 1:
                outlist.append('\n'.join(vmo_position))
            elif len(vmo_position) == 1:
                outlist.append(vmo_position[0])
            else:
                outlist.append('\ncould not find position source for %s' % (
                    short_fname))

            outlist.append('\n----------\n')
        except Exception:
            # FIXME: see previous try/except block.
            raise IOError('ERROR finding Position Source')
        #

        ostr = '\n'.join(outlist)
        if outfile:
            with open(outfile,'a') as file:
                file.write(ostr)
        else:
            _log.info(ostr)


    def guess_serial_msg_types(self, outfile=None):
        '''
        return a string with serial message information
        '''
        #
        vm = self
        outlist=[]
        for Nkey in ['N1R', 'N2R', 'N3R']:
            path = os.path.split(vm.filelist[0])[0]
            Nlist = glob.glob(os.path.join(path, '*.%s' % (Nkey)))
            if len(Nlist) == 0:
                outlist.append('\nno %s files' % (Nkey))
            else:
                try:
                    Ndata=[]
                    for ff in vm.filelist:
                        path, short_name = os.path.split(ff)
                        root, ext = os.path.splitext(short_name)
                        parts = root.split('_')
                        if parts[-1] == '000000':
                            Nkeyfile = os.path.join(path, '%s.%s' % (root,Nkey))
                            if not os.path.exists(Nkeyfile):
                                keytup = (Nkey, '_'.join(parts[:-1]), Nkeyfile)
                                outlist.append('\n%s: missing series %s, \neg. %s' % keytup)
                            else:
                                idict =  vm.infodicts[ff]
                                if Nkey in idict:
                                    if idict[Nkey] not in Ndata:
                                        Ndata.append(idict[Nkey])
                    if len(Ndata) > 1:
                        outlist.append('\n%s files had multiple matches (possible problem):' % (Nkey))
                        for Nlist in Ndata:
                            outlist.append(', '.join(Nlist))
                        outlist.append('\n')
                        for ff in vm.filelist:
                            try:
                                outlist.append(os.path.split(ff)[-1] + ':  ' +  ', '.join(vm.infodicts[ff][Nkey]))
                            except Exception:
                                #FIXME: more specific exception? Or another way
                                #to catch "no data"?
                                outlist.append('WARNING: no %s data for %s' % (Nkey, ff))
                    elif len(Ndata) == 1:
                        msgstr = str(Ndata)
                        outlist.append('\n%s files include these messages:\n%s' % (Nkey, msgstr))
                    else:
                        outlist.append('found no %s data' % (Nkey))
                except Exception:
                    _log.exception('could not get serial messages for %s' % (Nkey))
                    raise# IOError('could not get serial messages for %s' % (Nkey))

        #
        outlist.append('\n----------\n')

        ostr = '\n'.join(outlist)
        if outfile:
            with open(outfile,'a') as file:
                file.write(ostr)
        else:
            _log.info(ostr)


#---------------------------

def tester():
    navinfo = [("gpsnav", "gps", 1),
               ("posmv", "gga", 2),
               ("posmv", "pmv", 2)]
               # There is also an INHDT--from what?

    F = FakeUHDAS(yearbase=2005,
                  sourcedir="kn182_05_VMDAS",
                  destdir="kn182",
                  sonar="os75",
                  navinfo=navinfo,
                  ship="kn")
    F()


def guess_instmodel_from_logfilelist(filelist):
    '''
    guess using *.LOG
    '''
    filelist = pathops.make_filelist(filelist)
    model_list = []
    inststring_list = []
    for logfile in filelist:
        instmodel = '' # unknown
        inststring = '' # unknown
        try:
            with open(logfile, 'r', encoding='utf-8', errors='ignore') as newreadf:
                lines = newreadf.readlines()[:100]
            for line in lines:
                if 'Ocean Surveyor' in line:
                    instmodel = 'os'
                    inststring = line.rstrip()
                    break
                elif 'WorkHorse' in line:
                    instmodel = 'wh'
                    inststring = line.rstrip()
                    break
                elif 'Broadband' in line:
                    instmodel = 'bb'
                    inststring = line.rstrip()
                    break
                elif 'Pinnacle' in line:
                    instmodel = 'pn'
                    inststring = line.rstrip()
                else:
                    pass
            if (instmodel not in model_list) and (instmodel != ''):
                model_list.append(instmodel)
                inststring_list.append(inststring)
        except Exception:
            #FIXME: what might we catch here? Should it always go unreported?
            pass

    return model_list, inststring_list


def guess_instmodel_from_datafile(fname):
    '''
    return 2-letter instrument model ('os', 'pn', 'wh', 'bb') from data file
    '''
    sonar = Sonar(instname_from_file(fname))
    return sonar.model


def guess_pingtypes(m):
    if hasattr(m,'pingtypes'):
        pingtypes = m.pingtypes[0]
    else:
        pingtypes = {m.get_pingtype():0} #first ping
    return pingtypes


def guess_sonar_from_datafile(onefile):
    '''
    return a tuple with (instname, pingtypes)
    by attempting to read the file and guessing the model ('os', 'pn', 'wh', 'bb')
           then add the frequency by reading the file
    '''
    filelist=pathops.make_filelist(onefile)
    if len(filelist) != 1:
        raise IOError('requires exactly one RDI data file')
    if not os.path.exists(onefile):
        raise IOError('file %s does not exist' % (onefile))

    instname = ''
    pingtypes = ()
    onefile = filelist[0]
    #
    instname = instname_from_file(onefile)
    model=instname[:2]
    m=Multiread(onefile, model)

    pingtypes = guess_pingtypes(m)
    return instname, pingtypes


def guess_sonars(fileglob, verbose=False):
    '''
    guess instrument model+freq and pingtypes from multiple data files
    '''
    datafile_list = pathops.make_filelist(fileglob)
    nonemptyfiles = []
    for f in datafile_list:
        if os.path.getsize(f) > 0:
            nonemptyfiles.append(f)

    instping_tuplist = []
    for f in nonemptyfiles:
        instping = guess_sonar_from_datafile(f) #tuple: (inst+freq, m.pingtypes)
        if verbose:
            print(f, instping)
        instping_tuplist.append( instping )
    return instping_tuplist

def sort_sonars(instping_tuplist, datatype=''):
    '''
    return dictionary with
    - instruments and count
    - pingtypes and count
    - instping combination and count

    This list is a list of *potential* ping types, but if the
    data are 'lta' or 'sta' that choice has already been made

    '''
    info = Bunch()
    info.sonars = Bunch()     # sonars: 'os75bb', 'wh300'
    info.instruments = Bunch()   #model+freq eg. 'os75' or 'wh300'
    info.pingtypes = Bunch()     # 'bb', 'nb', 'bbnb'
    #
    for inst, ping in instping_tuplist:
        '''
        inst = model+frequency
        ping = m.pingtypes, a dictionary with keys in ('bb','nb') and index for reading
        '''
        for pingkey in ping.keys():
            if datatype.lower() in ('lta', 'sta'):
                # only take the one with the index == 0
                if ping[pingkey] == 0:
                    sonar = Sonar(inst+pingkey).sonar  #'wh300', 'os75bb', 'os150nb'
                    if sonar not in info.sonars.keys():
                        info.sonars[sonar] = 1
                    else:
                        info.sonars[sonar] += 1
            else:
                sonar = Sonar(inst+pingkey).sonar
                if sonar not in info.sonars.keys():
                    info.sonars[sonar] = 1
                else:
                    info.sonars[sonar] += 1
    #
    for sonar in info.sonars.keys():
        instname = Sonar(sonar).instname
        pingkey =   Sonar(sonar).pingtype
        # we already sorted and culled.
        if instname not in info.instruments.keys():
            info.instruments[instname] = 1
        #
        if pingkey not in info.pingtypes.keys():
            info.pingtypes[pingkey] = info.sonars[sonar]
        else:
            info.pingtypes[pingkey] += info.sonars[sonar]
    #
    return info


#=====================================

class VmdasNavInfo:
    '''
    read ascii N1R, N2R, N3R files, output likely navinfo list for fake_uhdas
    '''
    def __init__(self, vmdas_dir):
        '''
        vmdas_dir: must have write permission, contains all vmdas files
        '''
        self.vmdas_dir = vmdas_dir
        self.Nlist=pathops.make_filelist(os.path.join(vmdas_dir, '*.N?R'))
        self.ser_messages = self.messages(self.Nlist)
        self.navinfo = self.build_nav(self.ser_messages)


    #----------------
    def messages(self,filelist, numlines=50):
        '''
        return a dictionary with
           keys ['N1R', 'N2R', 'N3R' (whatever exists)
           values are a list of unique NMEA messages in the N*R file
        '''
        ser_messages = Bunch()
        flist = pathops.make_filelist(filelist)
        for fname in flist:
            Nkey = fname.split('.')[-1]
            if Nkey not in list(ser_messages.keys()):
                ser_messages[Nkey]=Bunch() #key = sermsg, value = example line
            # For backward compatibility's sake
            py_version = sys.version_info[0]
            if py_version >= 3:
                with open(fname, 'r', encoding='utf-8', errors='ignore') as newreadf:
                    lines = newreadf.readlines()
            else:
                with open(fname, 'r') as newreadf:
                    lines = newreadf.readlines()
            for line in lines[:numlines]:
                if line[0] in (':','$') and 'ADCP' not in line:
                    key, has_checksum = _get_key(line)
                    if key is not None and not has_checksum:
                        key += ',NO CHECKSUM'
                    if key is not None and key not in list(ser_messages[Nkey].keys()):
                        ser_messages[Nkey][key] = line.strip()
        return ser_messages


    def build_nav(self, ser_messages):
        navinfo = []
        for Nkey in ser_messages.keys():
            num = int(Nkey[1])
            # look for  '$PSXN,20' and '$PSXN,23'; combine
            nmea_list = list(ser_messages[Nkey].keys())
            if '$PSXN,20' in nmea_list and '$PSXN,23' in nmea_list:
                nmea_list.append('ADD_SEA')
                nmea_list.remove('$PSXN,23')
                nmea_list.remove('$PSXN,20')
            for dstr in nmea_list:
                msg = None
                if dstr in serial_strmsg.keys():
                    msg = serial_strmsg[dstr]
                elif dstr == 'ADD_SEA':
                    msg = 'sea'
                else:
                    line = ser_messages[Nkey][dstr]
                    has_checksum = ('*' in line.split(',')[-1])
                    if line[3:6] == 'GGA':
                        if has_checksum:
                            msg = 'gps'
                        else:
                            msg = 'ggn'
                    elif line[3] == 'H':
                        if has_checksum:
                            msg = 'hdg'
                        else:
                            msg = 'hnc'
                    else:
                        msg = None
                if msg is None:
                    _log.info('not using %s string' % (dstr))
                if msg is not None:
                    navinfo.append((Nkey, msg, num))

        navinfo.insert(0, ('synchro', 'hdg', 0))
        return navinfo


# 2025-01-01: Is the following used anywhere?
def get_instrument_frequency(filename, instrument):
    ''' filename is ONE file, instrument is used in Multiread
    '''
    frequency = None
    try:
        m = Multiread(filename, instrument)
        data=m.read(step=3)
        frequency = data.sysconfig['kHz']
    except Exception:
        pass
    return frequency
