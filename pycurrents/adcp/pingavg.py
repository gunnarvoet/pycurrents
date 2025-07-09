"""
Read RDI raw files and ancillary files from UHDAS, and write cmd and bin
files for loading by ldcodas.  Then (optionally) run ldcodas.

Example:

from pycurrents.adcp.pingavg import Pingavg

params = dict(tr_depth=7,
                head_align=45.6,
                hbest=["gyro", "hdg"]      # Required if hcorr is present
                hcorr=["posmv", "pmv", 0], # optional: inst, msg, constant
                                           #             for filling gaps
                pbest=["posmv","pmv"]      # optional - for better positions
                apply_hcorr = True         # default; (False: just record it)
                # For discrete-beam systems (NB, WH) only; mainly for NB150
                # Also usable for rough correction for ducer in antifreeze.
                velscale=dict(scale=1,         # optional; normally omitted
                              calculate=True,  # if False, specify soundspeed.
                              salinity=35,     # for calculate=True; optional
                              soundspeed=1500) # only for calculate=False
                # See SoundspeedFixer for details.
                )

edit_params = dict(ecutoff=1,  # m/s
                   cor_cutoff=120,
                   weakprof_percent=30,
                   rl_startbin=2, # 1-based; e.g., 2 means ignore first bin
                   rl_endbin=50, # None to use all bins
                   refavg_valcutoff=1,
                   ampfilt=40,
                   estd_cutoff=10,  # disabled; experimental
                   max_search_depth=0, #  0: always look for maxampbin
                   )                   # -1: never look for maxampbin
                                       # positive int: (eg 2000)  use Etopo
                                       #   if topo < 2000, look for maxampbin

l = Pingavg(datadir="/home/data/km1002/raw/wh300",
        gbinsonar="/home/data/km1002/gbin/wh300",
        loaddir="./load",
        calrotdir="./cal/rotate",
        sonar="wh300",
        edit_params=edit_params,
        xducerxy=None,  # otherwise, list of 2 offsets [starboard, fwd]
        params=params,
        yearbase=2010,     ### required!

        # The following experimental arguments output ascii files with the same
        # time range and naming convention as *.bin,*.cmd, but contain SINGLE-PING
        # (not averaged) information for later calculations:
        #
        uvwref=None,   # otherwise slice inputs for reflayer (outputs *.uvwref)
                       #    ascii files alongside load/[*.bin, *.cmd])
        tuvship=False, # outputs time, shifted lon and lat (by xducer_dx, xducer_dy)
                       #    ship speeds (from shifted positions), and heading used
        use_rbins=False # try to get uvship speeds from rbins, not gbins
        )

l.run()

l.load_codas("./adcpdb")  # Directory is a required argument.

"""

import sys
import os
import time
import glob
import gc
import logging
import logging.handlers

import numpy as np

from pycurrents.system import Bunch
import pycurrents.system.pathops as pathops
from pycurrents.num.ringbuf import Ringbuf
from pycurrents.num.nptools import Flags
from pycurrents.num.runstats import Runstats
from pycurrents import num
from pycurrents.data import navcalc # uv_from_txy, unwrap_lon, unwrap ...
from pycurrents.codas import to_date, to_day, to_datestring
from pycurrents.adcp.raw_multi import Multiread
from pycurrents.adcp import raw_simrad
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.adcp.transform import heading_rotate
from pycurrents.adcp.refavg import refavg
import pycurrents.adcp.adcp_specs as adcp_specs
from pycurrents.data.navcalc import lonlat_shifted
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp.pingedit import BottomEdit
from pycurrents.num import interp1           # interpolation
from pycurrents.num import Stats            # mean,std,med (masked)

# Use Etopo because of its global coverage.
from pycurrents.data.topo import Etopo_file

# (1) set up logger
_log = logging.getLogger(__name__)


#----------

## try new single-ping editing based on correlation (FKt wh300)

def medfilt_2D(arr, med_cutoff=None, medfilt_window=3):
    """
    Apply a short median filter to first 2 dimensions of *arr*.
    *medfilt_window* must be an odd integer.
    Returns filtered *arr*.
    """
    arr = np.atleast_2d(arr)
    nprofs, nbins = arr.shape[:2]

    if med_cutoff is None or min(nprofs, nbins) < medfilt_window:
        return arr
    arr1 = Runstats(arr, 3, axis=0).medfilt(med_cutoff)
    return Runstats(arr1, 3, axis=1).medfilt(med_cutoff)


def ping_dday_transition(m, pingpref='nb'):
    '''
    m=Multiread(filelist, 'os')      #specify model only, to get all transitions
    pd = ping_day_transition(m)                 # all transitions
    pd = ping_day_transition(m, pingpref='nb')  ## nb chunks only

    returns a list of (ping,startdday, endday) tuples describing a chunk
    '''
    pd = []
    chunks = m.chunks
    for ichunk in range(len(chunks)):
        # first pingtypes in chunk, first pingtype
        chunk = chunks[ichunk]
        pingtypes = m.pingtypes[chunk[0]] # pingtypes don't change in a chunk
        pingnames = list(pingtypes.keys())
        if len(pingnames) == 1:
            pingtype = pingnames[0]
        else:
            pingtype = pingpref
        #
        m.select_chunk(ichunk=ichunk)
        dd=m.read(ends=2)
        pd.append((pingtype, dd.dday[0], dd.dday[-1]))
    return pd


def get_uvship(dday, lon, lat, method='centered'):
    '''
    This is a general-purpose function to calculate ship speeds.
    It returns ship u, v from centered or first differences.

    u, v are masked arrays, but the end points are filled,
    so values will be masked only if there are masked values
    in dday, lon, or lat.
    '''
    # navigation comes in split at +/- 180
    ulon = navcalc.unwrap(lon)

    if method=='centered':
        u, v = navcalc.uv_from_txy_centered(dday, ulon, lat, fill_ends=True)
    else:
        u, v = navcalc.uv_from_txy(dday, ulon, lat, pad=True)
        u[0] = u[1]
        v[0] = v[1]
    return u, v

class LDWriter:
    '''
    mixin class
    - contains only the components used to write *bin, *cmd, *gps2 (*gpst2) files
    - used in Pingavg and vmdas
    '''

    def write_uvship(self):
        '''
        uship and vship are already determined, by gbins or rbins
        '''
        # find out where velocities are good (already edited,masked)
        u_tr, u_prof, uresid = refavg(self.ens.vs['u'])
        v_tr, v_prof, vresid = refavg(self.ens.vs['v'])
        # get uvship where velocities are good

        dday, lon, lat, uship, vship = self.txyuvship

        ii = np.where(~np.isnan(lon))[0]
        if len(ii) == 0:
            lastdday = self.ens.times.dday[-1]
            lastlon = 1e38
            lastlat = 1e38
            # no good positions
        else:
            ilast = ii[-1]
            lastdday = self.ens.times.dday[ilast]
            lastlon = lon[ilast]
            lastlat = lon[ilast]

        self.ushipma=np.ma.masked_where(u_tr.mask, uship)
        self.vshipma=np.ma.masked_where(v_tr.mask, vship)

        self.lonma = np.ma.masked_where(u_tr.mask, lon)
        self.latma = np.ma.masked_where(v_tr.mask, lat)

        if self.tuvship:
            self.write_tuvship()

        us_mean = uship.mean()
        if np.isnan(us_mean):
            us_mean = 1e38
            vs_mean = 1e38
        else:
            vs_mean = vship.mean()

        Su=Stats(self.ushipma)
        Sv=Stats(self.vshipma)
        usma_mean = Su.mean
        if np.isnan(usma_mean):
            usma_mean = 1e38
            vsma_mean = 1e38
        else:
            vsma_mean = Sv.mean


        ## This file is consistent with files for putnav, which requires
        ## 8 columns but only uses 5: [dday, ?,?, uship, vship, lon, lat, ?]
        ## but columns 1,2 will be means of masked uship, vship, and the
        ## last column will be number of good points in the masked version
        ##
        ## This file is only for testing with putnav; if positions are
        ## shifted, we write out a new .tuv using speeds from masked positions
        fmt = "%12.6f %12.6f %12.6f %12.12g %12.12g %12.12g %12.12g %4d\n"
        self._uvship.write(fmt % (lastdday,  # from uvship
                                  usma_mean, vsma_mean,
                                  us_mean, vs_mean,
                                  lastlon, lastlat, # from uvship
                                  Su.N))

        ## This file is a simple t,u,v
        fmt = "%12.6f %12.6f %12.12g\n"
        self._tuv.write(fmt % (lastdday, usma_mean, vsma_mean))


    def write_tuvship(self):
        '''
        write ping times and uship, vship for comparison, only where
           full profiles exist.
           - positions are shifted (if nonzero xducer_dx,dy)
           - ship speeds are calculated from shifted positions
        '''
        fmt = "%12.6f %12.6f %12.6f %12.6f %12.6f  %7.3f\n"
        for count in range(len(self.ens.times.dday)):
            # False = 'not masked'.  we want those
            if not self.ushipma.mask[count]:
                self._tuvship.write(fmt % (self.ens.times.dday[count],
                                           self.lonma[count],
                                           self.latma[count],
                                           self.ushipma[count],
                                           self.vshipma[count],
                                           self.heading_corrected[count],
                ))


    def write_uvwref(self):
        '''
        calculate reflayer values for lagged correlation and w experiments
        '''
        uref = Stats(self.ens.u[:,2:7], axis=1).mean
        vref = Stats(self.ens.v[:,2:7], axis=1).mean
        wref = Stats(self.ens.w[:,2:7], axis=1).mean

        fmt = "%12.6f %12.6f %12.6f %12.6f\n"
        for count in range(len(self.ens.times.dday)):
            self._uvwref.write(fmt % (self.ens.times.dday[count],
                                      uref[count],
                                      vref[count],
                                      wref[count]))

    def write_gps2(self):
        """
        Matlab version backs up as far as necessary to find
        values; for now, we will only check the fix before the last one.
        """
        lon = self.ens.best.lon[-1]
        if np.isnan(lon):
            lon = self.ens.best.lon[-2]
            lat = self.ens.best.lat[-2]
            dday = self.ens.times.dday[-2]
        else:
            lat = self.ens.best.lat[-1]
            dday = self.ens.times.dday[-1]
        self._gps2.write("%14.7f %14.7f %14.7f\n" % (dday, lon, lat))

    def write_gpst2(self):
        """
        same as write_gps but for positions translated using xducerxy
        """
        #'ens.bestx' is transformed lon, lat using xducerxy and hdg-dh
        lon = self.ens.bestx.lon[-1]
        if np.isnan(lon):
            lon = self.ens.bestx.lon[-2]
            lat = self.ens.bestx.lat[-2]
            dday = self.ens.times.dday[-2]
        else:
            lat = self.ens.bestx.lat[-1]
            dday = self.ens.times.dday[-1]

        self._gpst2.write("%14.7f %14.7f %14.7f\n" % (dday, lon, lat))

    def write_block_start(self):
        self._cmd.write("%s_endian\n" % sys.byteorder)
        self._cmd.write("binary_file: %s.bin\n" % self.block_basename)
        self._cmd.write("new_block\ndp_mask: 1\n")

    def write_block_vars(self):
        self.bin_float("DEPTH", self.ens.dep)
        self.bin_double("CONFIGURATION_1", self.make_config())

    def write_profile_start(self):
        t_end = to_date(self.mr.yearbase, self.ens.times.dday[-1])
        # The following might be moved more directly into run():
        self._profile_date = "%4d/%02d/%02d %02d:%02d:%02d" % tuple(t_end)
        self._profile_dday = self.ens.times.dday[-1]
        # Fudge for update mode: block start date is time of first
        # profile added in this run.
        if self._profile == 0:
            self._block_start_date = self._profile_date
            self._block_start_dday = self._profile_dday

        self._cmd.write("new_profile: " + self._profile_date)
        self._cmd.write("  /* %d %d */\n" %
                              (self.ens.ens_num[0], self.ens.ens_num[-1]))
        self._cmd.write("depth_range: %d %d\n" %
                      (round(self.ens.dep[0]), round(self.ens.dep[-1])))


    def write_profile_vars(self):
        self.bin_double("ACCESS_VARIABLES", self.make_access())
                        # make_access could be run only once per chunk
        self.bin_double("ANCILLARY_1", self.make_ancil1())
        self.bin_double("ANCILLARY_2", self.make_ancil2())
        self.bin_double("BOTTOM_TRACK", self.avg.bt)
        self.bin_double("NAVIGATION", self.avg.nav)
        self.bin_float("U", self.avg.u)
        self.bin_float("V", self.avg.v)
        self.bin_float("W", self.avg.w)
        self.bin_float("ERROR_VEL", self.avg.e)
        self.bin_float("EV_STD_DEV", self.avg.estd)
        self.bin_ubyte("AMP_SOUND_SCAT", self.avg.amp)
        self.bin_ubyte("RAW_AMP", self.avg.rawamp)

        self.bin_ubyte("PERCENT_GOOD", self.avg.pg)
        self.bin_ubyte("PERCENT_3_BEAM", self.avg.pg3)

        self.bin_float("RESID_STATS", self.avg.resid_stats)
        self.bin_float("TSERIES_STATS", self.avg.tseries_stats)
        self.bin_float("TSERIES_DIFFSTATS", self.avg.tseries_diffstats)

        if self.avg.sw is not None:
            self.bin_ubyte("SPECTRAL_WIDTH", self.avg.sw)
            self.bin_ubyte("RAW_SPECTRAL_WIDTH", self.avg.rawsw)

        self.bin_ubyte("PROFILE_FLAGS", self.avg.profile_flags)


    def make_config(self):
        c = 1e38 * np.ones((23,), dtype=np.float64)
        i = config_indices
        c[i.avg_interval] = self.ens_secs
        c[i.compensation] = 1 # as in matlab, but with note to decode from
                              # instrument config
        c[i.num_bins] = self.ens.NCells
        c[i.tr_depth] = self.params.tr_depth
        c[i.bin_length] = self.ens.CellSize
        c[i.pls_length] = self.ens.Pulse
        c[i.blank_length] = self.ens.Blank
        c[i.ping_interval] = self.ping_interval # missing from matlab
        # BT is handled differently here than in matlab:
        # for the NB, we are just calling it True, rather than
        # reading the whole chunk to see if there is any valid BT data.
        # Also, the matlab version has
        #c1(ii.bot_track)            = 255*a.config.bt_was_on;
        # which seems odd.
        c[i.bot_track] = self.have_bt
        c[i.pgs_ensemble] = 1
        # What is ens_threshold? not set by matlab, shows up as 0 after proc.
        c[i.ens_threshold] = 1e38
        c[i.top_ref_bin] = self.edit_params.rl_startbin
        if self.edit_params.rl_endbin is None:
            c[i.bot_ref_bin] = self.ens.NCells
        else:
            c[i.bot_ref_bin] = self.edit_params.rl_endbin
        # ecutoff should already be zero if 3beam
        c[i.ev_threshold] = round(self.edit_params.ecutoff * 1000)

        c[i.freq_transmit] =  self.ens.sysconfig['kHz'] * 1000
                            # We should have defined it as kHz...
        c[i.hd_offset] = self.params.head_align
        c[i.heading_bias] = 0 # No longer used.
        c[i.beam_angle] = self.beam_angle
        return c

    def make_access(self):
        a = 1e38 * np.ones((8,), dtype=np.float64)
        a[0] = 1                       # first good bin
        a[1] = self.avg.lgb            # last good bin
        # Remaining fields start as invalid; processing fills in
        # U_ship_absolute and V_ship_absolute
        return a

    def make_ancil1(self):
        a = 1e38 * np.ones((10,), dtype=np.float64)
        a[0] = self.avg.t_stats[0]
        a[1] = self.avg.soundspeed
        ssf = self.ss_fixer
        if ssf is not None and ssf.new_soundspeed is not None:
            a[1] = ssf.new_soundspeed
        # a[2] is best_snd_spd; it has never been used for anything.
        a[3] = self.avg.h_stats[0]
        a[4] = self.ens.nprofs
        return a

    def make_ancil2(self):
        a = 1e38 * np.ones((23,), dtype=np.float64)
        i = ancil2_indices
        avg = self.avg
        a[i.std_temp] = avg.t_stats[1]
        a[i.last_temp] = avg.t_stats[2]
        a[i.std_heading] = avg.h_stats[1]
        a[i.last_heading] = avg.h_stats[2]
        a[i.mn_pitch], a[i.std_pitch], a[i.last_pitch] = avg.p_stats[:3]
        a[i.mn_roll], a[i.std_roll], a[i.last_roll] = avg.r_stats[:3]
        a[i.watrk_hd_misalign] = a[i.botrk_hd_misalign] = avg.meandh
        a[i.pit_misalign] = a[i.rol_misalign] = 0
        velscale = 1
        if self.ss_fixer is not None:
            velscale = self.ss_fixer.scale
        a[i.watrk_scale_factor] = a[i.botrk_scale_factor] = velscale
        a[i.last_good_bin] = self.avg.lgb

        if avg.mab > 0:
            a[i.max_amp_bin] = avg.mab # matlab was not setting this
        return a

    def bin_float(self, name, array):
        offset = self._bin.tell()
        array = np.ma.filled(array, 1e38)
        if array.dtype != np.float32:
            array = array.astype(np.float32)
        array.tofile(self._bin)
        self._cmd.write('binary_data: %s FLOAT %d %d\n' %
                                    (name, array.size, offset))

    def bin_double(self, name, array):
        offset = self._bin.tell()
        array = np.ma.filled(array, 1e38)
        if array.dtype != np.float64:
            array = array.astype(np.float64)
        array.tofile(self._bin)
        self._cmd.write('binary_data: %s DOUBLE %d %d\n' %
                                    (name, array.size, offset))

    def bin_ubyte(self, name, array):
        offset = self._bin.tell()
        array = np.ma.filled(array, 255)
        if array.dtype.itemsize != 1:
            array = array.astype(np.uint8)
        array.tofile(self._bin)
        self._cmd.write('binary_data: %s UBYTE %d %d\n' %
                        (name, array.size, offset))

#-----------

class Pingavg(LDWriter):
    codas_blkmax_nprofs = 512 # hardcoded in CODAS
    pflagnames = ["orig",   # original, from the instrument
                  "e",      # error vel
                  "cor",    # correlation
                  "amp",    # amplitude spikes
                  "be",     # bottom-edit
                  "wp",     # weak profile
                  "ra",     # refavg residual
                  "estd",     # e_std outlier (do not use)
                  "slc"    # shallow low correlation
                  ]
    def __init__(self, datadir=None,  # sonar
                        gbinsonar=None,
                        loaddir=None,
                        calrotdir=None,
                        sonar=None,
                        new_block_on_start=False,  ## for processing multiple ping types
                        ens_len=300,       # seconds; becomes ens_secs below
                        ens_offset=None,  # for ensemble boundary location; None or seconds.
                        blk_max_nprofs=300,
                        edit_params=None,
                        params=None,       # required dictionary
                        use_rbins=False,    # for uvship
                        xducerxy=None,     # starboard, fwd
                        uvwref=None,       # output uvw reflayer or not
                        tuvship=False,   # output [t; uship,vship,lon, lat] shifted positions
                        yearbase=None,     # Required.
                        update=False,
                        dryrun=False,      # if True, don't write any files
                        ibadbeam=None, #0-based bad beam (for 3beam sol'n)
                        beam_index=None,
                        ):

        # Directories:
        self.datadir = datadir
        parts = self.datadir.split(os.path.sep)
        self.uhdas_dir = os.path.sep.join(parts[:-2])
        self.rbindir = os.path.join(self.uhdas_dir, 'rbin')
        self.gbinsonar = gbinsonar
        parts = self.gbinsonar.split(os.path.sep)
        gbinroot = os.path.sep.join(parts[:-1])
        self.hbindir = os.path.join(gbinroot, 'heading')

        self.ibadbeam = ibadbeam
        self.beam_index = beam_index
        self.use_rbins = use_rbins
        self.new_block_on_start = new_block_on_start

        ## quick fix to create gbinheading
        self.gbinheading = os.path.join(os.path.split(gbinsonar)[0],'heading')

        self.loaddir = loaddir
        self.calrotdir = calrotdir
        if not dryrun:
            try:
                os.makedirs(self.loaddir)
            except OSError:
                pass

        # Files:
        self.gbintimepat = os.path.join(self.gbinsonar, "time", "*.tim.gbin")
        if not dryrun:
            self._ens_blk_pat = os.path.join(self.loaddir, "ens_blk%03d")
            self.state_fn = os.path.join(self.loaddir, "ens_last_written.asc")
            self.log_fn = os.path.join(self.loaddir, "write_ensblk.log")
            self.lastens_fn = os.path.join(self.loaddir, "lastens.npz")
            # file used by repeater:
            self.time_fn = os.path.join(self.loaddir, "wrote_ens_time")

        self.update = update
        if self.update:
            self.filemode = "a"
        else:
            self.filemode = "w"

        self.dryrun = dryrun

        try:
            self.topo = Etopo_file()
        except Exception:
            _log.debug('cannot load topography')
            pass

        # Parameters:
        self.yearbase = yearbase
        if self.yearbase is None:
            raise ValueError("The yearbase kwarg is required.")
        self.sonar = Sonar(sonar)
        self.ens_secs = ens_len
        self.ens_dday = ens_len / 86400.0
        self.ens_offset = ens_offset
        if ens_offset is not None:
            if update:
                raise ValueError("In update mode, ens_offset must be None")
            if ens_offset < 0:
                raise ValueError("ens_offset must be non-negative")
            self.ens_offset = ens_offset / 86400.0

        if xducerxy is None:
            xducerxy = [0,0]
        self.xducerxy = xducerxy

        self.uvwref = uvwref # None, or slice bins
        self.tuvship = tuvship # True/False

        if blk_max_nprofs > self.codas_blkmax_nprofs:
            _log.debug('oversized blk_max_nprofs: resetting to %d' % (
                    self.codas_blkmax_nprofs))
        self.blk_max_nprofs = min(blk_max_nprofs, self.codas_blkmax_nprofs)

        self.edit_params = adcp_specs.ping_editparams(self.sonar,
                                 badbeam=ibadbeam) # 0-based
        self.edit_params.update(edit_params) # ensure this includes 3-beam

        self.refsl = slice(self.edit_params.rl_startbin - 1,
                            self.edit_params.rl_endbin)

        self.params = Bunch(params)
        self._apply_hcorr = self.params.get('apply_hcorr', True)

        if 'velscale' in self.params:
            self.ss_fixer = SoundspeedFixer(**self.params['velscale'])
        else:
            self.ss_fixer = None


        # Test for heading correction, and set up files etc. as needed.
        # This has to follow the directory and parameter initialization.
        self._init_hcorr()

        # This must follow _init_hcorr, which sets more paths.
        if not self.update and not self.dryrun: ## dryrun: (pingave subclassed by pingsuite)
            self.delete_oldfiles()

        # For timing various calculations:
        self._BE_time = 0
        self._topo_time = 0
        self._weak_time = 0
        self._amp_time = 0
        self._topcor_time = 0
        self._hcorr_time = 0



    def delete_oldfiles(self):
        """
        Wipe the slate clean; remove all files written by Pingavg.

        This uses 'ens_*' as a glob, so consider that pattern
        reserved for use by Pingavg within the load directory.
        """
        ensglob = glob.glob(os.path.join(self.loaddir, "ens_*"))
        for f in ensglob:
            try:
                os.remove(f)
            except OSError:
                pass

        if self._do_hcorr:
            for f in (self._hcorr_asc_fn, self._hcorr_ang_fn):
                try:
                    os.remove(f)
                except OSError:
                    pass

        try:
            os.remove(self.log_fn)
        except OSError:
            pass

    def read_inputs(self):
        """
        Use Multiread to read raw files with corresponding time
        files.  If there are no time files or if the raw file
        matching a time file is not found, ValueError is raised.
        """
        # Read only raw files that have matching time files.
        timefiles = glob.glob(self.gbintimepat)
        timefiles.sort()
        tfbase = pathops.basename(timefiles)

        self.update_start_t = None
        if self.update and os.path.exists(self.state_fn):
            with open(self.state_fn) as newreadf:
                line = newreadf.read()

            mode, t0, t1, prf, blk, last_fn = line.split()
            t0 = float(t0)
            t1 = float(t1)
            self.update_start_t = t1
            prf = int(prf)            # Last profile written
            blk = int(blk)            # Last block
            self._profile = prf + 1
            self._block = blk
            ## used in conjunction with "dday_bailout" and "incremental"
            if self.new_block_on_start:
                self._profile = 0
                self._block += 1
            else:
                if self._profile >= self.blk_max_nprofs:
                    self._profile = 0
                    self._block += 1
            istart = tfbase.index(last_fn)
        else:
            self._block = 0
            self._profile = 0
            istart = 0

        newbase = tfbase[istart:]
        rawfiles = pathops.corresponding_pathname(
                            newbase, self.datadir, ".raw")

        for f in rawfiles:
            if not os.path.exists(f):
                raise ValueError("Pingavg.read_inputs: file %s is missing", f)
                # This never should happen, since there has to be a raw.log.bin
                # file for a .tim file to be generated.

        # Multiread raises ValueError if rawfiles is empty.
        self.mr = Multiread(rawfiles,
                            self.sonar,
                            gbinsonar=self.gbinsonar,
                            gap=("dday", 60),
                            ibad=self.ibadbeam,
                            beam_index=self.beam_index,
                            yearbase=self.yearbase)

        self.beam_angle = self.mr.sysconfig['angle']

    def read_rbins(self):
        ''' instantiates two BinfileSets : self.rbinpos (rbin positions
            and self.hbinhead (heading/hbins) or assigns them None if failure
        '''
        ## --- add rbins ---
        ## position
        if not self.use_rbins:
            return #

        if  hasattr(self.params, 'pbest'):
            try:
                pos_inst, pos_msg = self.params.pbest
                # read the rbins from position inst,msg
                rbinglob = os.path.join(pos_inst, '*.%s.rbin' % (pos_msg))
                self.rbinpos = BinfileSet(os.path.join(self.rbindir, rbinglob),
                                          cname='dday')
            except Exception:
                _log.warning('could not read rbin positions using %s' % (rbinglob))
                self.rbinpos = None
            else:
                _log.info('reading rbin positions from %s' % (rbinglob))
        else:
            self.rbinpos = None
            _log.info('not using rbin positions: "pbest" missing from pingavg params')

        try:
            # read the hbins from from heading/*.hbin and extract what we want
            hbinglob = '*.hbin'
            self.hbinhead = BinfileSet(os.path.join(self.hbindir, hbinglob),
                                          cname='dday')
        except Exception:
            _log.warning('could not read headings using %s' % (hbinglob))
            self.hbinhead = None
        else:
            _log.info('reading hbin headings from %s' % (hbinglob))


    def run(self, stop_n=None, stop_dday=None,
                    start_dday=None):
        """
        Process all input files. In update mode, the set of
        input files is re-read with each call to this method.

        All kwargs are primarily for testing purposes,
        but *start_dday* and *stop_dday* might be useful
        in batch mode for discarding in-port data.

        Returns the number of ensembles written.

        """
        handler = logging.FileHandler(self.log_fn, self.filemode)
        handler.setLevel(logging.DEBUG)
        _log.addHandler(handler)

        self._files = []
        self._ens_count = 0
        self._cmd = None
        self._bin = None
        cycle_t0 = time.time()

        if self.update:
            mode = "update"
        else:
            mode = "batch"

        try:
            self.read_inputs()
        except Exception:
            _log.exception("Pingavg.read_inputs: no data available?")
            return
        if self.use_rbins:
            self.read_rbins() # sets self.rbinhead or self.rbinpos to None if failure

        ## heading
        hcorr_headlist = [
            "# dh is 'reliable' (usually a gyro) minus 'accurate'",
            "# reliable instrument, message = %s,%s" % tuple(self.params.hbest),
            ]
        if 'hcorr' in self.params.keys():
            hcorr_headlist.append(
            "# accurate instrument, message = %s,%s" % tuple(self.params.hcorr[:2]))
        else:
            hcorr_headlist.append('')
        hcorr_headlist.append(
            "# dday      mean_hdg last_hdg mean_dh std_dh num badflag\n"
            )
        hcorr_asc_header = '\n'.join(hcorr_headlist)

        if self._do_hcorr and not self.dryrun:
            self._hc_ang = open(self._hcorr_ang_fn, self.filemode)
            self._hc_asc = open(self._hcorr_asc_fn, self.filemode)
            if self._hc_asc.tell() == 0:
                self._hc_asc.write(hcorr_asc_header)

        stop_now = False

        nchunks = len(self.mr.chunks)
        _starts, _ends = self.mr.chunk_ranges()
        _log.info("----------------")
        _log.info("sonar is %s" % (str(self.sonar)))
        _log.info("Pingavg.run for time range %f to %f", _starts[0], _ends[-1])
        _log.info("transducer offset: xducer_dx = %5.3f, xducer_dy = %5.3f" % (
                self.xducerxy[0], self.xducerxy[1]))
        _log.info("shifted positions applied to *.gpst2 and *.uvship'")
        if self.uvwref:
            _log.info("writing single-ping reference layer u,v,w %d to %d" % (
                self.uvwref[0], self.uvwref[1]))

        _log.info("----------------")

        for ich, chunk in enumerate(self.mr):
            # chunk is just self.mr with a chunk selected
            t0, t1 = chunk.read(ends=True).times.dday

            _log.debug("Chunk %d of %d, %f to %f", ich + 1, nchunks, t0, t1)
            if stop_dday is not None:
                t1 = min(stop_dday, t1)
            if (self.update_start_t is not None
                    and self.update_start_t >= t1):
                # This chunk ends before the start time;
                # try the next one.
                continue
            if (self.update_start_t is not None
                        and self.update_start_t >= t0):
                t0 = self.update_start_t
            elif (start_dday is not None
                        and (start_dday < t1)
                        and (start_dday >= t0)):
                t0 = start_dday
            if self.ens_offset is not None:
                _t0 = np.floor((t0 + self.ens_offset) / self.ens_dday) * self.ens_dday
                t0 = _t0 - self.ens_dday if _t0 > t0 else _t0
            tseq = list(np.arange(t0, t1, self.ens_dday))
            if not tseq:
                continue
            # If there is a chunk transition, try for a last
            # ensemble in the old chunk.
            if ich < nchunks - 1:
                tseq.append(tseq[-1] + self.ens_dday)
            if len(tseq) < 2:
                continue
            ens_segs = list(zip(tseq[:-1], tseq[1:]))
            _log.debug("%d segments, %f to %f", len(ens_segs),
                               ens_segs[0][0], ens_segs[-1][-1])

            self.have_bt = np.any(self.mr.bt[self.mr.iselect]) #not [0]
            n = chunk.nproflist[chunk.iselect].sum()
            self.ping_interval = 86400 * (t1 - t0) / n

            for seg in ens_segs:
                if stop_n is not None and self._ens_count == stop_n:
                    stop_now = True
                    break
                try:
                    chunk.set_range(seg)
                    ppd = chunk.read()
                except Exception:
                    _log.exception("set_range failed for segment %f %f" % seg)
                    continue

                if ppd is None:
                    _log.debug("Empty segment: %f %f" % seg)
                    continue
                if ppd.nprofs < 10:
                    _log.debug("Segment %f %f has only %d profiles",
                                              seg[0], seg[1], ppd.nprofs)
                    continue
                if self.sonar.isa('ec'):
                    # In late 2024, the EK80 API gained the ability to specify
                    # subsampling when generating the datagram, so for newer
                    # data we should not need to do our own subsampling.  As a
                    # heuristic to decide whether we need subsampling, assume
                    # that a bin size of 1 m or greater means we specified the
                    # subsampling at the data acquisition stage and do not
                    # need additional subsampling.  The older datasets
                    # typically started with about 0.25 m sampling.
                    if ppd.dep[1] - ppd.dep[0] < 0.99:
                        raw_simrad.subsample_ppd(ppd)  # Modified in place!
                self.ens = ppd
                self.ens.dep += self.params.tr_depth
                avg = Bunch() # We need this near for hcorr and edit.
                              # Otherwise, it would be at the start of average().
                self.avg = avg
                try:
                    self.average_scalars() # HPR; heading is needed by hcorr
                                           # for ens_hcorr_asc
                    self.rotate() #sets self.dh #   hcorr
                    self.edit()
                    self.average()
                    self.get_txyuvship()
                except Exception:
                    _log.exception("Segment %s", seg)
                    continue # Try the next one.
                if not self.dryrun:
                    self.write()
                last_file_read = self.mr.last_file_read
                self._ens_count += 1
                last_seg = seg        # Don't save--needs to be local.

                # Write state here, so that it will be current in
                # the event of an error in the processing that is not
                # caught with the try/except above.
                msg = "%s %14.8f %14.8f  %d %d  %s\n" % (mode,
                             last_seg[0], last_seg[1],
                             self._profile - 1, self._block,
                             pathops.basename(last_file_read))
                if not self.dryrun:
                    with open(self.state_fn, "wt") as file:
                        file.write(msg)

            if not self.dryrun:
                self.check_close_files()
            if stop_now:
                break

        if self._do_hcorr and not self.dryrun:
            self._hc_ang.close()
            self._hc_asc.close()

        try:
            _log.info(msg.rstrip())  # remove newline
            _log.info("Wrote bin, cmd for %d ensembles in %d files.  %d seconds",
                            self._ens_count, len(self._files),
                            round(time.time() - cycle_t0))
            _log.debug("amp: %d  topo: %d  bottom: %d  weak: %d  hcorr: %d",
                        self._amp_time, self._topo_time, self._BE_time,
                        self._weak_time, self._hcorr_time)
        except (AttributeError, NameError):
            _log.debug("Nothing written")

        _log.removeHandler(handler)

        if self._ens_count > 0:
            try:
                if not self.dryrun:
                    self.write_last_ens()
            except Exception:
                _log.exception("in write_last_ens, seg = %s", last_seg)
            try:
                del_t = (self.ens.times.u_dday - self.ens.times.dday).mean()
                seg_u_dday = last_seg[1] + del_t
                seg_u_date = to_datestring(self.yearbase, seg_u_dday)
                if not self.dryrun:
                    with open(self.time_fn, "w") as file:
                        file.write(seg_u_date)
            except Exception:
                _log.exception("writing %s", self.time_fn)

        return self._ens_count

    def write_last_ens(self):
        """
        After writing one or more averaged ensembles to cmd and bin,
        write some ensemble data from the last ensemble so it can
        be used for plotting.
        """
        if hasattr(self.ens, 'bestx'):
            b = self.ens.bestx
        else:
            b = self.ens.best

        b = self.ens.best
        dday = self.ens.times.dday
        uship, vship = navcalc.uv_from_txy(dday, navcalc.unwrap(b['lon']), b['lat'])
        avg_amp = Stats(Stats(self.ens.amp, axis=2).mean, axis=0).mean

        np.savez(self.lastens_fn,
                                uship=np.ma.filled(uship, np.nan),
                                vship=np.ma.filled(vship, np.nan),
                                avg_amp=avg_amp,    ## new, profile
                                u=self.ens.u.data,
                                v=self.ens.v.data,
                                instpflag=self.flags.flags,
                                dep=self.ens.dep,
                                corr_dday=dday,
                                yearbase=self.yearbase,
                                dh=self.dh,    # scalar: average
                                amp1=self.ens.amp1_orig,
                                heading=self.ens.best.heading # reliable
                                )

    def load_codas(self, dbdir, newdir=False):
        """
        Load all processed files into a new codas database which
        will be given the name 'aship' and put in the specified
        directory.

        If *newdir* is True, any existing  directory will
        be renamed first.  Default is False.
        """

        if newdir:
            try:
                os.rename(dbdir, dbdir + ".%d" % round(time.time()))
            except OSError:
                pass
        try:
            os.makedirs(dbdir)
        except OSError:
            pass

        defpath = os.path.join(self.loaddir, "vmadcp.def")
        if not os.path.exists(defpath):
            with open(defpath, "w") as file:
                file.write(_producer_def)

        cntpath = os.path.join(self.loaddir, "ldcodas.tmp")

        try:
            filelist = "\n".join(self._files)
        except AttributeError:
            filelist = glob.glob(os.path.join(self.loaddir, "*.cmd"))
            filelist.sort()
            filelist = '\n'.join(filelist)

        with open(cntpath, "w") as file:
            file.write(_ldcnt_template.format(yearbase=self.mr.yearbase,
                                       dbpath=os.path.join(dbdir, "aship"),
                                       defpath=defpath,
                                       logpath=os.path.join(
                                                self.loaddir,"load.log"),
                                       filelist=filelist))
        os.system("ldcodas %s" % cntpath)


    def average_scalars(self):
        ens = self.ens
        avg = self.avg
        avg.t_stats = stats(ens.temperature)
        avg.p_stats = stats(ens.best.pitch)
        avg.r_stats = stats(ens.best.roll)
        h = ens.best.heading
        if np.isnan(h).any():
            h = np.ma.masked_invalid(h)
            # Matlab was printing a message if there were any nans in heading.
        h = navcalc.unwrap(h, centered=True, copy=True)
        h = np.ma.compressed(h)
        avg.h_stats = stats(h)
        if self.sonar.isa("nb"):
            avg.soundspeed = 1536
        elif self.sonar.isa("ec"):
            avg.soundspeed = ens.FL['sound_speed']
        else:
            avg.soundspeed = ens.VL['SoundSpeed'].mean() # Editing needed?
        if self.ss_fixer is not None:
            self.ss_fixer.setup(avg.t_stats[0], avg.soundspeed)

    def _init_hcorr(self, use_hbin=True):
        if "hcorr" not in self.params:
            self._do_hcorr = False
            return

        self._do_hcorr = True
        inst, msg, self._hcorr_offset = self.params.hcorr
        if use_hbin:
            self.ens_hcorr = self.ens_hcorr_hbin
            self._hcorr_dir = self.gbinheading
            self._hcorr_ext = ".hbin"

        else:
            self.ens_hcorr = self.ens_hcorr_gbin
            self._hcorr_dir = os.path.join(self.gbinsonar, inst)
            self._hcorr_ext = ".%s.gbin" % msg

        if not self.dryrun:
            try:
                os.makedirs(self.calrotdir)
            except OSError:
                pass

        if not self.dryrun:
            if  self._apply_hcorr:
                self._hcorr_asc_fn = os.path.join(self.calrotdir, "ens_hcorr.asc")
                self._hcorr_ang_fn = os.path.join(self.calrotdir, "ens_hcorr.ang")
            else:
                self._hcorr_asc_fn = os.path.join(self.calrotdir, "hcorr.asc")
                self._hcorr_ang_fn = os.path.join(self.calrotdir, "hcorr.ang")

        nrb = int(7200.0 / self.ens_secs)  # 2 hours
        self._hcorr_rb = Ringbuf(nrb)
        self._hcorr_rb.add(self._hcorr_offset) # seed the buffer
        self._hc_persist = self._hcorr_offset
        if self.update:
            try:
                # Read into a string instead of directly with fromfile
                # because the latter has poor error handling.
                with open(self._hcorr_ang_fn) as newreadf:
                    s = newreadf.read()
                if len(s) > 15:
                    dd_ang = np.fromstring(s, sep=" ")
                    dd_ang.shape = (len(dd_ang)//2, 2)
                    for dd, ang in dd_ang[-nrb:]:
                        self._hcorr_rb.add(ang)
            except IOError:
                pass # No existing file.

    def ens_hcorr_hbin(self):
        """
        Ensemble-average heading correction using hbins.
        """
        _t0 = time.time()

        # Start hbin-specific part
        hc = self.mr.read_matching_bin(self._hcorr_dir, self._hcorr_ext,
                                        cname="dday")
        # Historical artifact: dh is "best" (gyro) minus "accurate".
        h_acc = hc["%s_%s" % tuple(self.params.hcorr[:2])]
        h_best = hc["%s_%s" % tuple(self.params.hbest)]

        dh = ((h_best - h_acc + 180) % 360) - 180
        rb = self._hcorr_rb
        # End hbin-specific part

        self._dh_stats = stats(dh, medclip=5) # saved for debugging if needed
        dhm, dhs, dh_last, dhn = self._dh_stats

        if (        dhn > 0.20*len(dh)    # len(dh) > 0 and PG > 20
                and dhn > 20
                and dhs < 2
                and abs(dhm - self._hcorr_offset) < 15
                and abs(dhm - self._hc_persist) < 10):
            rb.add(dhm)
            badflag = 0
            self._hc_persist = self._hcorr_rb.mean()
        else:
            if self._hcorr_rb.N_good() == 0:
                self._hc_persist = self._hcorr_offset
            dhm = self._hc_persist
            rb.add(np.nan)
            badflag = 1

        # Append to the files;
        if not self.dryrun:
            dday = self.ens.times.dday[-1]
            self._hc_ang.write("%11.7f %7.2f\n" % (dday, dhm))
            fmt = '%10.7f  %7.2f  %7.2f  %5.2f  %3.2f  %5d %5d\n'
            vals = (dday, self.avg.h_stats[0], self.avg.h_stats[2],
                    dhm, dhs, dhn, badflag)
            self._hc_asc.write(fmt % vals)
        self._hcorr_time += (time.time() - _t0)

        return dhm

    def ens_hcorr_gbin(self):
        """
        Ensemble-average heading correction using gbins.
        """
        _t0 = time.time()
        hc = self.mr.read_matching_bin(self._hcorr_dir, self._hcorr_ext)
        # Historical artifact: dh is "best" (gyro) minus "accurate".
        dh = ((self.ens.best.heading - hc.heading + 180) % 360) - 180
        rb = self._hcorr_rb
        self._dh_stats = stats(dh) # saved for debugging if needed
        dhm, dhs, dh_last, dhn = self._dh_stats
        if dhn > 10:
            rb.add(dhm)
            badflag = 0
            self._hc_persist = self._hcorr_rb.mean()
        else:
            if self._hcorr_rb.N_good() == 0:
                self._hc_persist = self._hcorr_offset
            dhm = self._hc_persist
            rb.add(np.nan)
            badflag = 1

        # Append to the files;
        if not self.dryrun:
            dday = self.ens.times.dday[-1]
            self._hc_ang.write("%11.7f %7.2f\n" % (dday, dhm))
            fmt = '%10.7f     %5.2f    %5.2f      %5.2f    %3.2f  %5d %5d 0\n'
            vals = (dday, self.avg.h_stats[0], self.avg.h_stats[2],
                    dhm, dhs, dhn, badflag)
            self._hc_asc.write(fmt % vals)
        self._hcorr_time += (time.time() - _t0)

        return dhm

    def set_rbin_position_subset(self, ddrange, pad=5.0):
        ''' set rbin time range to ddrange with a padding of "pad" seconds on each side"
            return a copy of the view
        '''
        try:
            self.rbinpos.set_range(ddrange=[ddrange[0]-pad/86400, ddrange[1]+pad/86400])
            return(len(self.rbinpos.records))
        except Exception:
            return None

    def set_hbin_heading_subset(self, ddrange, pad=5.0):
        ''' set rbin time range to ddrange with a padding of "pad" seconds on each side"
            return a copy of the view
        '''
        try:
            self.hbinhead.set_range(ddrange=[ddrange[0]-pad/86400, ddrange[1]+pad/86400])
            return(len(self.hbinpos.records))
        except Exception:
            return None

    def get_txyuvship(self):
        '''
        This is a special-purpose wrapper to gather t,x,y in Pingavg
        (depending on options) and calculate t,x,y,uship,vship for later use.
        '''
        # if transformed positions 'bestx' exist, use those
        # if dx,dy not zero and rbin positions, exist, use this
        #    translate rbin positions to new locations, then do ship speed

        if self.use_rbins: #new
            # (FIXME: this does no good for VmDAS data because
            #    - processing requires "asc2bin" to use "-c last"
            #    - but then there's no difference between rbin and gbin times
            #    To get all the positions we need to use asc2bin -c all
            #    but the machinery is not there for that (2 sets of rbins) at the moment

            ## ensure longitudes are centered:
            ddrange = [self.ens.times.dday[0], self.ens.times.dday[-1]]
            self.set_rbin_position_subset(ddrange=ddrange)
            rt = self.rbinpos.dday
            rx = navcalc.unwrap_lon(self.rbinpos.lon)
            ry = self.rbinpos.lat

            self.set_hbin_heading_subset(ddrange=ddrange)
            hdg_inst, hdg_msg = self.params.hbest
            hbin_besthead = self.hbinhead.records['%s_%s' % (hdg_inst, hdg_msg)]
            rhead_ = interp1(self.hbinhead.dday, navcalc.unwrap(hbin_besthead), rt)
            rhead_corr_ = rhead_ - self.dh

            if self.xducerxy is not None:
                newlon, newlat = lonlat_shifted(rx, ry, rhead_corr_,
                                                starboard=self.xducerxy[0],
                                                forward=self.xducerxy[1])
            else:
                newlon = rx
                newlat = ry

            ruship, rvship = get_uvship(rt, newlon, newlat, method='centered')
            uship=interp1(rt, ruship, self.ens.times.dday)
            vship=interp1(rt, rvship, self.ens.times.dday)
            x=interp1(rt, newlon, self.ens.times.dday)
            y=interp1(rt, newlat, self.ens.times.dday)
            self.txyuvship = (self.ens.times.dday, x, y, uship, vship)

        else: # refactored out of write_uvship
            if hasattr(self.ens, 'bestx'):
                ensbest = self.ens.bestx
            else:
                ensbest = self.ens.best
            self.heading_corrected = self.ens.heading_corrected
            uship, vship = get_uvship(self.ens.times.dday,
                                         ensbest.lon, ensbest.lat,
                                         method='centered')
            self.txyuvship = (self.ens.times.dday,
                              ensbest.lon, ensbest.lat,
                              uship, vship)


    def rotate(self):
        if self._do_hcorr:
            dh = self.ens_hcorr() # calculate and write
        else:
            dh = 0
        if not self._apply_hcorr:
            dh = 0
        self.dh = dh

        ens = self.ens
        ens.heading_corrected = ens.best.heading - dh

        # transform positions if required
        if self.xducerxy is not None:
            ens.bestx = ens.best.copy()
            newlon, newlat = lonlat_shifted(
                ens.best.lon,
                ens.best.lat,
                ens.heading_corrected,      # here, use corrected heading
                starboard=self.xducerxy[0],
                forward=self.xducerxy[1])
            ens.bestx.lon = navcalc.unwrap_lon(newlon)
            ens.bestx.lat = newlat

        ## ensure longitudes are centered:
        ens.best.lon = navcalc.unwrap_lon(ens.best.lon)

        dt = np.dtype(dict(names=['u', 'v', 'w', 'e'],
                                formats=["f4"]*4))
        vs = np.ma.zeros(ens.xyze.shape[:2], dtype=dt)

        # amount to rotate by: corrected heading + head_align
        hd = ens.heading_corrected + self.params.head_align
        uv = heading_rotate(ens.xyze[:,:,:2], hd)
        ens.bt_uv = heading_rotate(self.ens.bt_xyze[:,:2], hd)
        vs['u'], vs['v'] = uv[:,:,0], uv[:,:,1]
        vs['w'], vs['e'] = ens.xyze[:,:,2], ens.xyze[:,:,3]
        ens.vs = vs
        ens.u = vs['u']
        ens.v = vs['v']
        ens.w = vs['w']
        ens.e = vs['e']

    # editing
    def badcor_topbins(self):
        """
        Generate a mask for correlations above slc_bincutoff  and above
        the max correlation for each profile, if they are less than the max
        by the threshold value, slc_deficit.   Return 2D mask.
        """
#        import IPython; IPython.embed() #xxx

        cor = medfilt_2D(self.ens.cor)
        max_per_profile = np.max(cor, axis=1)
        maskcor = cor < (max_per_profile[:,np.newaxis,:] - self.edit_params['slc_deficit'])

        ibin = np.arange(cor.shape[1])
        # Flag only above the location of the max.
        j_maxcor = cor.argmax(axis=1)
        maskbin = ibin[:, np.newaxis, ...] < j_maxcor[:,np.newaxis,:]

        # 3D
        newmask = (maskcor & maskbin &
                  (ibin < self.edit_params['slc_bincutoff'])[:, np.newaxis, ...])
        return np.any(newmask, axis=-1)

    def get_estd_mask(self):
        ''' Needs more testing and thought.  This was an attempt to deal
            with electrical interference.
            Sequences of error velocity at a given depth bin are eliminated
            based on time-windowed standard deviation.
        '''
        estd_cutoff = self.edit_params.estd_cutoff

        e = self.ens.xyze[:,:,3]
        Rh = Runstats(e, 5, axis=0)
        mask= Rh.std > estd_cutoff
        return mask

    def edit(self):
        avg = self.avg
        ens = self.ens
        par = self.edit_params

        self.umask = np.ma.getmaskarray(ens.u)
        nt, nd = self.umask.shape
        self.flags = Flags(shape=self.umask.shape, names=self.pflagnames)
        flags = self.flags
        flags.addmask(self.umask, "orig")
        if par.ecutoff < 5:
            emask = (np.abs(ens.e.data) >= par.ecutoff)
            self.umask |= emask
            flags.addmask(emask, "e")

        if hasattr(ens, 'cor'): #nb150 does not have 'cor'
            cormask = (ens.cor.min(axis=-1) < par.cor_cutoff)
            self.umask |= cormask
            flags.addmask(cormask, "cor")

            # bad_topbins correlation
            if  par['slc_bincutoff'] != 0:
                _t0 = time.time()
                slcmask = self.badcor_topbins() #shallow low cor
                self.umask |= slcmask
                flags.addmask(slcmask, "slc")
                self._topcor_time += (time.time() - _t0)

        # remove acoustic interference
        _t0 = time.time()
        a = ens.amp
        ens.amp1_orig = ens.amp1.copy()  # saved for lastens
        if self.sonar.isa("os"):
            a[:,-1] = a[:,-2]  # Old OS bug...
        athresh = par.ampfilt
        amask = np.zeros(a.shape, bool)
        if a.shape[0] > 2:
            aa = a.astype(np.int16)
            amed = np.empty(a.shape, dtype=np.int16)
            amed[1:-1] = (aa[:-2] + aa[2:])//2
            amed[0] = (aa[1] + aa[2])//2
            amed[-1] =  (aa[-2] + aa[-3])//2
            amask = (aa - amed) > athresh
            np.putmask(a, amask, amed.astype(np.uint8))
            # now ens.amp has been cleaned

            # vertical slide for velocity masking
            amask[:,1:-1] |= (amask[:,:-2] | amask[:,2:])
            amask[:,0] |= amask[:,1]

        amaskany = amask.any(axis=-1)
        self.umask |= amaskany
        flags.addmask(amaskany, "amp")
        self._amp_time += (time.time() - _t0)


        # flag data below the bottom
        _t0 = time.time()
        if par.max_search_depth > 0:
            x = ens.best.lon.mean()
            y = ens.best.lat.mean()
            depth = -self.topo.nearest(x, y)[0] # make depth positive down
            self._topo_time += (time.time() - _t0)
        else:
            depth = -1

        if depth < par.max_search_depth:
            _t0 = time.time()
            # TODO: if BT is available, use its range measurement;
            #       maybe don't even bother to do our own in that case.
            self.BE = BottomEdit(
                self.edit_params,
                beam_angle=self.beam_angle,
                bin_offset=ens.Bin1Dist / ens.depth_interval,
                )
            self.BE.get_flags(ens)
            self.umask |= self.BE.cflags.tomask('all')
            flags.addmask(self.BE.cflags.tomask('all'), "be")
            mab = self.BE.mab
            lgb = self.BE.lgb

            # faster median
            avg.mab = np.ma.filled(num.median(mab), -1)
            avg.lgb = np.ma.filled(num.median(lgb), nd)
            self._BE_time += time.time() - _t0
        else:
            avg.mab = -1
            avg.lgb = nd
            lgb = None

        # weak profile editing
        _t0 = time.time()
        tmpmask=flags.tomask(["orig","e","cor","amp"])
        wpmask = weak_profile_edit(lgb, tmpmask, par)[:,np.newaxis]
        self.umask |= wpmask
        flags.addmask(wpmask, "wp")
        self._weak_time += (time.time() - _t0)

        # electrical interference?
        estd_cutoff = par.get("estd_cutoff", 0)
        if self.ibadbeam is not None and estd_cutoff:  # 0 is the official "disabled" for this
            wstdmask = self.get_estd_mask()
            self.umask |= wstdmask
            flags.addmask(wstdmask, "estd")

        ens.vs[self.umask] = np.ma.masked

    def average(self):
        ens = self.ens
        avg = self.avg

        nt, nd = ens.u.shape

        u_ts, u_mn, u_resid = refavg(ens.u, self.refsl)
        v_ts, v_mn, v_resid = refavg(ens.v, self.refsl)

        # diagnostics for interactive exploration
        ens.u_ts = u_ts
        ens.v_ts = v_ts
        ens.u_resid = u_resid
        ens.v_resid = v_resid

        # Outliers tend to be biased toward zero in shallow bins, so in
        # bad weather we can do a little better by using
        # the median rather than the mean to detect outliers.
        ures = u_resid - num.median(u_resid, axis=0)
        vres = v_resid - num.median(v_resid, axis=0)
        c_resid = ures + 1j * vres
        bad = np.ma.abs(c_resid) > self.edit_params.refavg_valcutoff
        if bad.any():
            ens.vs[bad] = np.ma.masked
            self.flags.addmask(bad, "ra")
            u_ts, u_mn, u_resid = refavg(ens.u, self.refsl)
            v_ts, v_mn, v_resid = refavg(ens.v, self.refsl)

            #log.debug("%d refavg outliers", bad.sum())

        if self.ss_fixer is not None:
            self.ss_fixer.correct_vel(u_mn, v_mn)

        avg.u = u_mn
        avg.v = v_mn

        avg.pg = np.round((100 * u_resid.count(axis=0)) / nt).astype(np.uint8)
        # only supporting "bad beam" not "3-beam" solutions
        if self.ibadbeam is None:
            avg.pg3 = np.zeros_like(avg.pg)
        else:
            avg.pg3 = avg.pg.copy()

        # This will remain initialized to zero; it is modified in
        # post-processing.
        avg.profile_flags = np.zeros_like(avg.pg)

        # It looks like these resid_stats and ts_stats calculations
        # take a significant fraction of the overall run time.
        # Storage is in the old Matlab order.
        resid_stats = np.zeros((6, nd), dtype=np.float32)
        resid_stats[0] = (u_resid**2).mean(axis=0).filled(1e38)
        resid_stats[1] = (u_resid * v_resid).mean(axis=0).filled(1e38)
        resid_stats[2] = (v_resid**2).mean(axis=0).filled(1e38)

        uv_resid = np.ma.empty((nt, nd, 2), dtype=np.float32)
        uv_resid[:,:,0] = u_resid
        uv_resid[:,:,1] = v_resid
        # Check: OK if heading has NaNs?

        ## I don't think we should need to do all this forward/port
        ## calculating; it should be possible to directly rotate the
        ## uv covariance matrix into fp.
        fp_resid = heading_rotate(uv_resid, -self.ens.best.heading)
        ens.fwd_resid = fp_resid[:,:,0]
        ens.port_resid = fp_resid[:,:,1]
        mnfpsq = (fp_resid**2).mean(axis=0).filled(1e38)
        resid_stats[3] = mnfpsq[:,0]
        resid_stats[5] = mnfpsq[:,1]
        resid_stats[4] = (fp_resid[:,:,0] *
                            fp_resid[:,:,1]).mean(axis=0).filled(1e38)
        avg.resid_stats = resid_stats

        ts_stats = np.zeros((7,), dtype=np.float32)
        ts_stats[6] = u_ts.count()
        ts_diffstats = np.zeros((4,), dtype=np.float32)
        ts_diffstats[-1] = np.diff(u_ts).count()

        uv_ts = np.ma.empty((nt, 2), dtype=np.float32)
        uv_ts[:,0] = u_ts
        uv_ts[:,1] = v_ts
        fp_ts = heading_rotate(uv_ts, -self.ens.best.heading)
        ens.fwd_ts = fp_ts[:,0]
        ens.port_ts = fp_ts[:,0]
        # ma bugs prevent the following from working:
        #mnuvsq = np.ma.filled((uv_ts**2).mean(axis=0), 1e38)
        #mnfpsq = np.ma.filled((fp_ts**2).mean(axis=0), 1e38)
        # But after making the changes, things still didn't work
        # in ipython, but they did from the shell, so maybe it is
        # all a matter of bugs in my devel version of ipython.

        ts_stats[0] = np.ma.filled((u_ts**2).mean(), 1e38)
        ts_stats[2] = np.ma.filled((v_ts**2).mean(), 1e38)
        # Note: as of 2.0.0.dev8455, the mean of a 1-D masked
        # array with unmasked values is an array scalar, so
        # we have to use np.ma.filled instead of the .filled method.
        ts_stats[1] = np.ma.filled((u_ts * v_ts).mean(), 1e38)
        ts_stats[3] = np.ma.filled((fp_ts[:,0]**2).mean(), 1e38)
        ts_stats[5] = np.ma.filled((fp_ts[:,1]**2).mean(), 1e38)
        ts_stats[4] = np.ma.filled((fp_ts[:,0] * fp_ts[:,1]).mean(), 1e38)
        avg.tseries_stats = ts_stats

        ## diff(vel)
        ts_diffstats[0] = np.ma.filled(((np.diff(u_ts))**2).mean(), 1e38)
        ts_diffstats[1] = np.ma.filled((np.diff(u_ts) * np.diff(v_ts)).mean(), 1e38)
        ts_diffstats[2] = np.ma.filled(((np.diff(v_ts))**2).mean(), 1e38)
        avg.tseries_diffstats = ts_diffstats

        avg.w = ens.w.mean(axis=0)
        avg.e = ens.e.mean(axis=0)
        avg.estd = Stats(ens.e, axis=0).std

        # Raw amp and raw Correlation (called spectral width in
        # the CODAS variable naming) are stored in CODAS with
        # depth varying most rapidly, hence the transpose.

        # amp starts out as an ndarray, not masked; if we change
        # this in editing, the following will need to be changed also.
        rawamp = ens.amp.mean(axis=0)
        avg.amp = np.round(rawamp.mean(axis=1)).astype(np.uint8)
        avg.rawamp = np.round(rawamp).T.astype(np.uint8)

        try:
            rawsw = ens.cor.mean(axis=0)
            avg.sw = np.round(rawsw.mean(axis=1)).astype(np.uint8)
            avg.rawsw = np.round(rawsw).T.astype(np.uint8)
        except AttributeError:
            avg.sw = None
            avg.rawsw = None

        avg.bt = 1e38 * np.ones((3,), np.float64)
        if self.have_bt:
            uv = self.ens.bt_uv.mean(axis=0)
            if uv.count() == 2:
                avg.bt[:2] = uv.data
                avg.bt[2] = self.ens.bt_depth.mean()
                if self.ss_fixer is not None:
                    self.ss_fixer.correct_vel(avg.bt[:2])

        # The following might be moved to write_profile, if
        # average() is never actually going to put anything in nav.
        avg.nav = 1e38 * np.ones((4,), np.float64)

        avg.velscale = 1
        if self.ss_fixer is not None:
            avg.velscale = self.ss_fixer.new_scale
        avg.meandh = self.dh     # recorded by rotate(); zero if no ping hcorr

        self.avg = avg

    def write(self):
        self.check_open_files()

        if self._profile == 0:
            self.write_block_start()
            self.write_block_vars()
        self.write_profile_start()
        self.write_profile_vars()
        if self.xducerxy is not None:
            self.write_gpst2()
        self.write_gps2()
        self.write_uvship() # initializes some variables
        if self.uvwref:
            self.write_uvwref()
        if self.tuvship:
            self.write_tuvship()

        # After everything is written:
        self._profile += 1
        if self._profile == self.blk_max_nprofs:
            self.check_close_files()
        gc.collect()  # We need this to keep memory usage down for octopus.

    def check_open_files(self):
        if self.update:
            tmode = "at"
            bmode = "ab"
        else:
            tmode = "wt"
            bmode = "wb"
        if self._cmd is None:
            # File names are 1-based for historical reasons.
            fn = self._ens_blk_pat  % (self._block + 1)
            self.block_basename = pathops.basename(fn)
            self._cmdname = fn + ".cmd"
            self._cmd = open(self._cmdname, tmode)
            self._bin = open(fn + ".bin", bmode)
            if self.xducerxy is not None:
                self._gpst2 = open(fn + ".gpst2", tmode)
            self._gps2 = open(fn + ".gps2", tmode)
            self._uvship = open(fn + ".uvship", tmode)
            self._tuv = open(fn + ".tuv", tmode)
            if self.uvwref:
                self._uvwref = open(fn + ".uvwref", tmode)
            if self.tuvship:
                self._tuvship = open(fn + ".tuvship", tmode)

    def check_close_files(self):
        if self._cmd is not None:
            self._cmd.close()
            self._bin.close()
            if self.xducerxy is not None:
                self._gpst2.close()
            self._gps2.close()
            self._uvship.close()
            self._tuv.close()
            if self.uvwref:
                self._uvwref.close()
            if self.tuvship:
                self._tuvship.close()
            self._cmd = None

            self._profile = 0
            self._block += 1
            self._files.append(self._cmdname)

            try:
                _log.info("%s  %s %s  %10.5f %10.5f",
                            self._cmdname,
                            self._block_start_date, self._profile_date,
                            self._block_start_dday, self._profile_dday)
            except AttributeError:
                _log.debug("Closing %s, no profiles written", self._cmdname)


def weak_profile_edit(lgb, umask, params):
    """
    lgb: last good bin, or None if no bottom search was done.
         If not None, it will be a masked array.
    umask: velocity component mask
    params: dictionary-like object:
            weakprof_percent  : typically 30;

                if weakprof_percent is None, use the simple
                algorithm with the following:

            weakprof_testbins : [first, last] 1-based bins, inclusive
            weakprof_numbins  : min number of valid velocities in testbins

    """
    nt, nd = umask.shape
    weakprof_percent = params.get("weakprof_percent", None)
    if weakprof_percent is not None:
        # Adaptive algorithm; but it presently lacks an ability
        # to start below bin 1.  Is that needed?
        if lgb is not None:
            if lgb.count() > max(nt*0.8, 15):
                lgb = num.median(lgb)
            else:
                lgb = None
        if lgb is not None:
            maxvelbin = lgb
        else:
            # Find 90th percentile of valid velocity counts
            nv = nd - umask.sum(axis=1)
            nv.sort()
            maxvelbin = max(1, nv[int(np.floor(0.9 * nt))])

        frac = weakprof_percent / 100.0
        testsl = slice(maxvelbin+1)
        ngood = maxvelbin + 1 - umask[:, testsl].sum(axis=1)
        needed = max(1, int(frac * maxvelbin))

    else:
        # Simple algorithm: fixed number of testbins and valid velocities.
        tb0, tb1 = params.get("weakprof_testbins", [1,20])
        testsl = slice(tb0 - 1, tb1)
        ngood = tb1 - tb0 + 1 - umask[:,testsl].sum(axis=1)
        needed = params.get("weakprof_numbins", 1)

    wpmask = ngood < needed
    return wpmask

def stats(a, medclip=None):
    """
    Quick stats calculation for 1-D ndarrays (not masked arrays).
    It is most efficient for arrays without nans, but will work
    with nans.

    If *medclip* is not None, outliers will be defined as points
    deviating from the median by *medclip*, and the statistics will
    be calculated after removing the outliers.

    Returns the mean, standard deviation, last value used, and
    number of values used.  (Return of the last value is needed
    for the ADCP temperature and heading, for historical reasons.)
    """
    mn = a.mean()
    if np.isnan(mn):
        goodmask = ~np.isnan(a)
        a = np.extract(goodmask, a)
        mn = None
    if a.size == 0:
        return np.nan, np.nan, np.nan, 0
    if medclip is not None:
        med = np.median(a)
        goodmask = abs(a - med) < medclip
        a = np.extract(goodmask, a)
        mn = None
    if mn is None:
        mn = a.mean()
    std = a.std()
    n = len(a)
    try:
        last = a[-1]
    except IndexError:
        last = np.nan
    return mn, std, last, n

def _svel0(T, S):
    """
    Chen and Millero, 1977, algorithm with P set to zero.
    (Translated from Matlab, which was translated from Fortran.)

    This is a version strictly for use in this module.
    """
    SR = np.sqrt(S)
    D = 1.727E-3
    B = -1.922E-2 - 4.42E-5*T
    A = (((-3.21E-8*T + 2.006E-6)*T + 7.164E-5)*T - 1.262E-2)*T + 1.389
    C = (((((3.1464E-9*T - 1.47800E-6)*T + 3.3420E-4)*T
                            - 5.80852E-2)*T + 5.03711)*T + 1402.388)
    sv = C + (A + B*SR + D*S)*S
    return sv

class SoundspeedFixer:
    """
    This class provides attributes and methods for handling
    soundspeed and other scale factor corrections. It is
    initialized in Pingavg.__init__() if a velscale dictionary is
    included in the kwargs.

    setup(T, original_soundspeed) is called for each ensemble to
    set the new_scale attribute.

    correct_vel(u, v) is called to apply the new_scale attribute
    to u and v in place, requiring that they be mutable via the
    inplace multiplication operator.
    """
    def __init__(self, scale=1, calculate=False,
                        soundspeed=None, salinity=None,
                        ):
        """
        If *scale* is not 1, then it multiplies the velocities in
        combination with the factor based on *calculate* or
        *soundspeed*.

        If *calculate* is True, then in addition to *scale*, a
        correction is made based on soundspeed calculated from
        temperature and *salinity*.  This is appropriate if a constant
        soundspeed was used for the original velocity estimates from
        the instrument, as in the case of the NB instruments.  By
        default the BB and WH instruments already use a calculated
        soundspeed, so for them (and for the OS) *calculate* should be
        False.  If *calculate* is True then *salinity* is used but
        *soundspeed* is ignored.

        If *soundspeed* is not None then a scale correction is
        calculated as the ratio between this *soundspeed* and
        the original_soundspeed supplied as an argument to setup().

        If *calculate* is False and *soundspeed* is None then only
        a correction for *scale* is applied. This can correct a
        small systematic bias, or provide a rough correction for
        errors in a discrete-beam system immersed in antifreeze but
        using soundspeed based on saltwater.
        """

        self.scale = scale
        self.calculate = calculate
        if salinity is None:
            salinity = 35
        self.salinity = salinity

        self.new_soundspeed = None
        self.new_scale = 1 # for ease of setting ancillary_2

        if self.calculate:
            self.setup = self.set_calc
            self.correct_vel = self.correct_all
        elif soundspeed is not None:
            self.setup = self.set_constant
            self.correct_vel = self.correct_all
            self.new_soundspeed = soundspeed
        elif scale != 1:
            self.setup = self.set_scale
            self.correct_vel = self.correct_all
            self.new_scale = scale
        else:
            self.setup = self.set_nothing
            self.correct_vel = self.correct_nothing


    def set_calc(self, T, original_soundspeed):
        """
        Calculate soundspeed correction based on temperature
        argument and original soundspeed.  The corrected
        soundspeed is calculated from this temperature and
        the salinity attribute.  A scale attribute is also
        applied.
        """
        self.new_soundspeed = _svel0(T, self.salinity)
        new_scale = self.new_soundspeed / original_soundspeed
        self.new_scale = self.scale * new_scale

    def set_constant(self, *args):
        """
        Set up correction from the original_soundspeed to
        self.new_soundspeed.
        """
        original_soundspeed = args[1]
        new_scale = self.new_soundspeed / original_soundspeed
        self.new_scale = self.scale * new_scale

    def set_scale(self, *args):
        """
        Set up a correction for a fixed scale factor only.
        """
        self.new_scale = self.scale

    def set_nothing(self, *args):
        pass

    def correct_nothing(self, *args):
        pass

    def correct_all(self, *args):
        for arg in args:
            arg *= self.new_scale


def proftimes_from_cmd(loaddir, yearbase=None):
    #new_profile: 2010/02/02 05:35:54  /* 1 50 */
    cmdlist = glob.glob(os.path.join(loaddir, "*.cmd"))
    cmdlist.sort()
    with open(cmdlist[-1]) as newreadf:
        lines = newreadf.readlines()
    profs = [line for line in lines if line.startswith("new_profile")]
    n = len(profs)
    dday = np.empty((n,), dtype=float)
    ens0 = np.empty((n,), dtype=int)
    ens1 = np.empty((n,), dtype=int)
    for i, line in enumerate(profs):
        fields = line.split()
        Y, M, D = [int(f) for f in fields[1].split("/")]
        h, m, s = [int(f) for f in fields[2].split(":")]
        if yearbase is None:
            yearbase = Y
        dday[i] = to_day(yearbase, Y, M, D, h, m, s)
        ens0[i] = int(fields[4])
        ens1[i] = int(fields[5])

    return dday, ens0, ens1






# CONFIGURATION_1
_names = ["avg_interval",
          "compensation",
          "num_bins",
          "tr_depth",
          "bin_length",
          "pls_length",
          "blank_length",
          "ping_interval",
          "bot_track",
          "pgs_ensemble",
          "ens_threshold",
          "ev_threshold",
          "hd_offset",
          "pit_offset",
          "rol_offset",
          "unused1",
          "unused2",
          "unused3",
          "freq_transmit",
          "top_ref_bin",
          "bot_ref_bin",
          "beam_angle",
          "heading_bias"]

config_indices = Bunch(list(zip(_names, list(range(len(_names))))))

# ANCILLARY_2
_names ="""watrk_hd_misalign
           watrk_scale_factor
           botrk_hd_misalign
           botrk_scale_factor
           pit_misalign
           rol_misalign
           unused1
           last_temp
           last_heading
           last_pitch
           last_roll
           mn_pitch
           mn_roll
           std_temp
           std_heading
           std_pitch
           std_roll
           ocean_depth
           max_amp_bin
           last_good_bin
           unused2
           unused3
           unused4""".split()

ancil2_indices = Bunch(list(zip(_names, list(range(len(_names))))))





_producer_def = """
/******************************************************************************

-----------------------------------------------------------------------------*/

DATASET_ID         ADCP-VM    /* vessel-mounted ADCP */
PRODUCER_ID        31026N0001 /* 31 = USA, 02 = WHOI, 6N = Knorr */
BLOCK_DIR_TYPE     0
PROFILE_DIR_TYPE   3          /* time, position, and depth range keys */
/*
        DATA DEFINITION FOR ADCP DATA

frequency     id value_type  data_name         offset  scale  units
*/
BLOCK_VAR      0  FLOAT     DEPTH                0       1       m
UNUSED         1  USHORT    TEMPERATURE          -10     1.E-3   C
UNUSED         2  USHORT    SALINITY             0       1.E-3   ppt
UNUSED         3  USHORT    OXYGEN               0       1.E-3   ppt
UNUSED         6  STRUCT    OPTICS               0       1       none
PROFILE_VAR    7  UBYTE     AMP_SOUND_SCAT       0       1       none
PROFILE_VAR    8  SHORT     U                    0       1.E-3   m/s
PROFILE_VAR    9  SHORT     V                    0       1.E-3   m/s
UNUSED        10  SHORT     P                    0       1       dbar
UNUSED        11  STRUCT    TEMP_SAMPLE          0       1       none
UNUSED        12  USHORT    SALINITY_SAMPLE      0       1.E-3   ppt
UNUSED        13  USHORT    OXYGEN_SAMPLE        0       1.E-3   ppt
UNUSED        14  STRUCT    NUTRIENT_SAMPLE      0       1       none
UNUSED        15  STRUCT    TRACER_SAMPLE        0       1       none
UNUSED        20  SHORT     OCEAN_DEPTH          0       1       m
UNUSED        21  STRUCT    WEATHER              0       1       none
UNUSED        22  STRUCT    SEA_SURFACE          0       1       none
PROFILE_VAR   32  CHAR      PROFILE_COMMENTS     0       1       none
BLOCK_VAR     33  CHAR      BLOCK_COMMENTS       0       1       none
PROFILE_VAR   34  UBYTE     PROFILE_FLAGS        0       1       none
BLOCK_VAR     35  STRUCT    CONFIGURATION_1      0       1       none
BLOCK_VAR     36  STRUCT    CONFIGURATION_2      0       1       none
PROFILE_VAR   37  STRUCT    ANCILLARY_1          0       1       none
PROFILE_VAR   38  STRUCT    ANCILLARY_2          0       1       none
PROFILE_VAR   39  STRUCT    ACCESS_VARIABLES     0       1       none
UNUSED        40  SHORT     DEPTH_SAMPLE         0       1       m
UNUSED        41  USHORT    SIGMA_T              0       1.E-3   kg/m3
UNUSED        42  USHORT    SIGMA_THETA          0       1.E-3   kg/m3
UNUSED        43  USHORT    SIGMA_Z              0       1.E-3   kg/m3
UNUSED        44  USHORT    SIGMA_2              0       1.E-3   kg/m3
UNUSED        45  USHORT    SIGMA_4              0       1.E-3   kg/m3
UNUSED        46  USHORT    SPEC_VOL_ANOM        0       1.E-9   m3/kg
UNUSED        47  USHORT    THERMOSTERIC_ANOM    0       1.E-9   m3/kg
UNUSED        48  SHORT     DYNAMIC_HEIGHT       0       1.E-3   dyn_m
UNUSED        49  SHORT     BVF                  0       1.E-5   /s
UNUSED        50  SHORT     SOUNDSPEED           1500    1.E-2   m/s
UNUSED        51  SHORT     TIME_FROM_START      0       1       s
UNUSED        52  USHORT    POTENTIAL_TEMP       -10     1.E-3   C
UNUSED        53  FLOAT     CONDUCTIVITY         0       1       none
PROFILE_VAR   54  SHORT     W                    0       1.E-3   m/s
PROFILE_VAR   55  SHORT     ERROR_VEL            0       1.E-3   m/s
PROFILE_VAR   56  UBYTE     PERCENT_GOOD         0       1       none
PROFILE_VAR   57  UBYTE     PERCENT_3_BEAM       0       1       none
PROFILE_VAR   58  UBYTE     SPECTRAL_WIDTH       0       1       none
PROFILE_VAR   59  SHORT     U_STD_DEV            0       1.E-3   m/s
PROFILE_VAR   60  SHORT     V_STD_DEV            0       1.E-3   m/s
PROFILE_VAR   61  SHORT     W_STD_DEV            0       1.E-3   m/s
PROFILE_VAR   62  SHORT     EV_STD_DEV           0       1.E-3   m/s
PROFILE_VAR   63  BYTE      AMP_STD_DEV          0       1       none
PROFILE_VAR   64  SHORT     RAW_DOPPLER          0       1       none
PROFILE_VAR   65  UBYTE     RAW_AMP              0       1       none
PROFILE_VAR   66  UBYTE     RAW_SPECTRAL_WIDTH   0       1       none
PROFILE_VAR   67  UBYTE     BEAM_STATS           0       1       none
PROFILE_VAR   68  STRUCT    NAVIGATION           0       1       none
PROFILE_VAR   69  STRUCT    BOTTOM_TRACK         0       1       none
UNUSED        70  SHORT     U_LOG                0       1.E-3   m/s
UNUSED        71  SHORT     V_LOG                0       1.E-3   m/s
PROFILE_VAR   75  STRUCT    USER_BUFFER          0       1       none
PROFILE_VAR   76  STRUCT    ADCP_CTD             0       1       none
PROFILE_VAR   80  FLOAT     RESID_STATS          0       1       m/s
PROFILE_VAR   81  FLOAT     TSERIES_STATS        0       1       m/s
PROFILE_VAR   82  FLOAT     TSERIES_DIFFSTATS    0       1       m/s


/*
     STRUCTURE DEFINITIONS
*/
DEFINE_STRUCT  CONFIGURATION_1  23
  ELEM         1  FLOAT     avg_interval                         s
  ELEM         1  SHORT     compensation                         none
  ELEM         1  SHORT     num_bins                             none
  ELEM         1  FLOAT     tr_depth                             m
  ELEM         1  FLOAT     bin_length                           m
  ELEM         1  FLOAT     pls_length                           m
  ELEM         1  FLOAT     blank_length                         m
  ELEM         1  FLOAT     ping_interval                        s
  ELEM         1  SHORT     bot_track                            none
  ELEM         1  SHORT     pgs_ensemble                         none
  ELEM         1  SHORT     ens_threshold                        none
  ELEM         1  SHORT     ev_threshold                         mm/s
  ELEM         1  FLOAT     hd_offset                            deg
  ELEM         1  FLOAT     pit_offset                           deg
  ELEM         1  FLOAT     rol_offset                           deg
  ELEM         1  FLOAT     unused1                              none
  ELEM         1  FLOAT     unused2                              none
  ELEM         1  FLOAT     unused3                              none
  ELEM         1  FLOAT     freq_transmit                        Hz
  ELEM         1  SHORT     top_ref_bin                          none
  ELEM         1  SHORT     bot_ref_bin                          none
  ELEM         1  FLOAT     beam_angle                           deg
  ELEM         1  FLOAT     heading_bias                         deg

DEFINE_STRUCT ANCILLARY_1 10
  ELEM         1  FLOAT     tr_temp                              C
  ELEM         1  FLOAT     snd_spd_used                         m/s
  ELEM         1  FLOAT     best_snd_spd                         m/s
  ELEM         1  FLOAT     mn_heading                           deg
  ELEM         1  SHORT     pgs_sample                           none
  ELEM         1  SHORT     unassigned1                          none
  ELEM         1  SHORT     unassigned2                          none
  ELEM         1  SHORT     unassigned3                          none
  ELEM         1  SHORT     unassigned4                          none
  ELEM         1  SHORT     unassigned5                          none

DEFINE_STRUCT ANCILLARY_2 23
  ELEM         1  FLOAT     watrk_hd_misalign                    deg
  ELEM         1  FLOAT     watrk_scale_factor                   none
  ELEM         1  FLOAT     botrk_hd_misalign                    deg
  ELEM         1  FLOAT     botrk_scale_factor                   none
  ELEM         1  FLOAT     pit_misalign                         deg
  ELEM         1  FLOAT     rol_misalign                         deg
  ELEM         1  FLOAT     unused1                              none
  ELEM         1  FLOAT     last_temp                            C
  ELEM         1  FLOAT     last_heading                         deg
  ELEM         1  FLOAT     last_pitch                           deg
  ELEM         1  FLOAT     last_roll                            deg
  ELEM         1  FLOAT     mn_pitch                             deg
  ELEM         1  FLOAT     mn_roll                              deg
  ELEM         1  FLOAT     std_temp                             C
  ELEM         1  FLOAT     std_heading                          deg
  ELEM         1  FLOAT     std_pitch                            deg
  ELEM         1  FLOAT     std_roll                             deg
  ELEM         1  SHORT     ocean_depth                          m
  ELEM         1  SHORT     max_amp_bin                          none
  ELEM         1  SHORT     last_good_bin                        none
  ELEM         1  SHORT     unused2                              none
  ELEM         1  SHORT     unused3                              none
  ELEM         1  SHORT     unused4                              none

DEFINE_STRUCT  ACCESS_VARIABLES  8
  ELEM         1  SHORT     first_good_bin                       none
  ELEM         1  SHORT     last_good_bin                        none
  ELEM         1  FLOAT     U_ship_absolute                      m/s
  ELEM         1  FLOAT     V_ship_absolute                      m/s
  ELEM         1  SHORT     user_flag_1                          none
  ELEM         1  SHORT     user_flag_2                          none
  ELEM         1  SHORT     user_flag_3                          none
  ELEM         1  SHORT     user_flag_4                          none

DEFINE_STRUCT  BOTTOM_TRACK  3
  ELEM         1  FLOAT     u                                    m/s
  ELEM         1  FLOAT     v                                    m/s
  ELEM         1  FLOAT     depth                                m

DEFINE_STRUCT  NAVIGATION 4
  ELEM         1  DOUBLE   latitude                              deg
  ELEM         1  DOUBLE   longitude                             deg
  ELEM         1  DOUBLE   speed                                 knots
  ELEM         1  DOUBLE   direction                             deg

"""

# Python 2.6 and later only: using the string format method
_ldcnt_template = """
DATABASE_NAME:   {dbpath}
DEFINITION_FILE: {defpath}
LOG_FILE:        {logpath}
YEAR_BASE: {yearbase}
cmd_file_list
END

{filelist}
"""
