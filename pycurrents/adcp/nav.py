"""
ADCP-specific navigation calculations: reference-layer smoothing.
"""

import os
import logging

import numpy as np
import numpy.ma as ma

from pycurrents.codas import get_profiles
from pycurrents.num.bl_filt import bl_filt
from pycurrents.num.nptools import loadtxt_no_warn
from pycurrents.data.navcalc import uv_from_txy
from pycurrents.data.navcalc import unwrap_lon
from pycurrents.system.misc import guess_comment

# Standard logging
_log = logging.getLogger(__name__)


def _mask_after_gap(t, u, v):
    """
    Mask u, v at the start of each new segment after a gap.

    t may be a masked array but it is assumed to have no masked values.

    u and v are assumed to be masked arrays.  Their masks are modified in
    place.  It is assumed that the t intervals are nearly uniform, with
    the exceptions being gaps when data acquisition is paused to change
    configuration (short gap) or for change in the ship's operations (e.g.,
    switching to a fish-finder sonar with the ADCP off).

    Returns u, v after modification
    """
    dt = np.diff(np.ma.filled(t, np.nan))
    dt_med = np.median(dt)
    mask = np.zeros((len(t),), dtype=bool)
    mask[1:] = dt > 2 * dt_med
    u[mask] = np.ma.masked
    v[mask] = np.ma.masked
    return u, v


class RefSmooth:
    """
    Perform velocity reference calculations at the ensemble-averaged stage.

    The initializer sets the parameters, including any changes
    from the defaults.

    Primary methods are read_data followed by adcp_nav.
    """
    min_pg          =  30   # only use velocity if PG greater than this
    min_maxpg       =  70   # skip profile if no PG exceeds this
    bl_half_width   =  3    # For filtering velocity.
    ref_top         =  1    # top bin reference layer
    ref_bot         =  20   # bottom of reference layer
                             ## should be deduced from the data instead?
    ensemble_secs   =  300  # length of ensemble (seconds)
    fix_t_mismatch  =  10   # seconds between ensemble time and fix time
    min_xy_frac     =  0.05 # data fraction of filter weight integral,
    min_uv_frac     =  0.5  #   ...  _xy_ for position, _uv_ for velocity

    def __init__(self, **kw):
        """
        Default parameters can be overridden here with kwargs.
        """
        self.__dict__.update(kw) # check that keys already exist?
        self.max_dt = self.ensemble_secs + self.fix_t_mismatch

    def read_data(self, dbname, input_file, yearbase, uvsource='nav'):
        """
        Read database and read or calculate uvship
        if uvsource is 'nav', use first differences from positions
        else (if 'uvship') read from uvship file.

        Returns True if data were found in *input_file*, else False.
        """
        if uvsource not in ('nav', 'uvship'):
            raise ValueError('uvsource "%s" should be "nav" or "uvship"' % uvsource)

        self.dbname = dbname
        self.yearbase = yearbase

        comment = guess_comment(input_file)
        data = loadtxt_no_warn(input_file, comments=comment, ndmin=2)
        if not data.size:
            return False

        data = np.ma.masked_invalid(data)
        if uvsource == 'nav':
            data[:,1] = unwrap_lon(data[:,1])
            self.unav, self.vnav = uv_from_txy(
                data[:,0], data[:,1], data[:,2])
            # FIXME: use ensemble start times and positions instead of masking.
            self.unav, self.vnav = _mask_after_gap(data[:, 0], self.unav, self.vnav)
        else: #'tuv' uvship outout has what we need in columns 0,1,2
            self.unav = data[:,1]
            self.vnav = data[:,2]

        self.profs = get_profiles(dbname, yearbase=yearbase)

        # UHDAS provides fix files that match the database;
        # we will just do a quick sanity check.
        # Later we may need to put in algorithms for handling
        # missing fixes and other glitches.
        dt = self.profs.dday - data[:,0]
        dtmin, dtmax = dt.min()*86400, dt.max()*86400
#        log.debug("dtmin = %5.2f  dtmax = %5.2f", dtmin, dtmax)
        if max(abs(dtmin), abs(dtmax)) > self.fix_t_mismatch:
            _log.warning("profile and fix times min, max mismatches (s): %5.2f %5.2f",
                      dtmin, dtmax)
        return True

    def adcp_nav(self):
        """
        Core functionality of adcp_nav.m.

        Fix time matching and interpolation are not done here.
        """

        ## DO edit out bad profiles
        umeas, vmeas = self.edit_umeas()
        self.umeas_e, self.vmeas_e = umeas, vmeas # for debugging

        # only smooth if requested
        if self.bl_half_width > 0:
            # Adjusted ship velocity estimates from ensemble-end navigation:
            u, v, n =self.adjust_ship_vel(self.unav, self.vnav, umeas, vmeas)
            self.unav_adj, self.vnav_adj = u, v
            self.n_adj = n

        else: #just rewrite
            self.unav_adj = self.unav
            self.vnav_adj = self.vnav

        # Adjusted absolute water velocity estimates:
        self.u_abs_unav_adj = umeas + self.unav_adj[:, np.newaxis]
        self.v_abs_vnav_adj = vmeas + self.vnav_adj[:, np.newaxis]

    def edit_umeas(self):
        """
        Return edited umeas, vmeas.

        Criteria are:
            no profile flags;
            adequate PG;
            short enough interval between profiles;
            adequate maximum PG in each profile.
        """
        profs = self.profs
        umeas, vmeas = profs.umeas, profs.vmeas
        badmask = ~((profs.pg > self.min_pg) & (profs.pflag == 0))
        umeas_e = ma.masked_where(badmask, umeas)
        vmeas_e = ma.masked_where(badmask, vmeas)
        low_maxpg = profs.pg.max(axis=1) < self.min_maxpg

        # The following is misplaced; the problem with a
        # long interval is not that the measured velocity is
        # bad, but that the end of the previous ensemble is not
        # an adequate estimate of the start of the present ensemble.
        # Ideally we will eliminate this by recording the start time
        # and position of each ensemble, and using that to calculate
        # the ship's velocity.
        dt = np.zeros_like(profs.dday)
        dt[1:] = np.diff(profs.dday)*86400
        longtime = dt > self.max_dt

        imask = low_maxpg | longtime
        umeas_e[imask, :] = ma.masked
        vmeas_e[imask, :] = ma.masked

        return umeas_e, vmeas_e


    def adjust_ship_vel(self, uship, vship, umeas, vmeas):
        """
        Adjust the raw estimates of ship velocity to smooth the water
        velocity estimates.

        uship, vship are estimates of ship velocity from navigation
        umeas, vmeas are edited estimates of ship-relative water velocity

        Returns adjusted uship, vship, number of depths.
        """
        dslice = slice(self.ref_top-1, self.ref_bot) # Parameters are 1-based.
        u_abs_raw = umeas[:, dslice] + uship[:, np.newaxis]
        v_abs_raw = vmeas[:, dslice] + vship[:, np.newaxis]

        try:
            u_abs_filt, ff = bl_filt(u_abs_raw, self.bl_half_width,
                                    axis=0, min_fraction=self.min_uv_frac)
            v_abs_filt, ff = bl_filt(v_abs_raw, self.bl_half_width,
                                    axis=0, min_fraction=self.min_uv_frac)
        except:
            u_abs_filt = np.ma.masked_array(u_abs_raw, mask=True, shrink=False)
            v_abs_filt = np.ma.masked_array(v_abs_raw, mask=True, shrink=False)

        u_adj = (u_abs_filt - u_abs_raw).mean(axis=1) # uv_mean_adj
        v_adj = (v_abs_filt - v_abs_raw).mean(axis=1)

        # Adjusted ship velocity estimates:   (uv.adj_uvship)
        uship_adj = u_adj + uship
        vship_adj = v_adj + vship

        # Find out how many depths went into the average:
        n = (~ma.getmaskarray(u_abs_filt)).sum(axis=1)

        return uship_adj, vship_adj, n

    def write_asc(self, fname, header=''):
        """
        Write a file that can serve as input for put_tuv (i.e. t,u,v)
        """
        base, ext = os.path.splitext(fname)
        if not ext:
            fname = fname + ".asc"

        out = np.zeros((self.unav_adj.size, 3), dtype=float)
        out[:,0] = self.profs.dday
        out[:,1] = self.unav_adj.filled(1e38)
        out[:,2] = self.vnav_adj.filled(1e38)
        # fill bad speeds with reasonable speeds
        mask = self.unav_adj.mask
        if mask is not np.ma.nomask:
            out[mask, 1] = self.unav[mask].filled(1e38)
            out[mask, 2] = self.vnav[mask].filled(1e38)
        f = open(fname, 'w')
        fmt = "%12.6f %12.12g %12.12g\n"
        f.write(header)
        for rec in out:
            f.write( fmt % tuple(rec))
        f.close()


def _test():
    base='/home/currents/programs/adcp_py3demos/adcp_pyproc/km1001c_uhdas/os38nb_fullproc'
    dbpathname = os.path.join(base, 'os38nb','adcpdb','aship')
    fixfile = os.path.join(base, 'os38nb','nav', 'aship.gps')
    yearbase = 2010
    R = RefSmooth(min_maxpg=30,
                   ref_top=2,
                   ref_bot=20,
                   ensemble_secs=300,
                   refuv_smoothwin=3,
                   )
    R.read_data(dbpathname, fixfile, yearbase)
    R.adcp_nav()
    R.write_asc(os.path.join(base, 'os38nb','nav','refsm_tuv.asc'))
