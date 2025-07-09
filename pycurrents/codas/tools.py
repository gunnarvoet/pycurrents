"""
Convenient access to CODAS database, typically via :func:`get_profiles`.

Import :class:`ProcEns` and/or :func:`get_profiles` directly from
:mod:`pycurrents.codas`.

"""

import os
import glob

import numpy as np
import numpy.ma as ma

from pycurrents.codas._codas import ProfileDict, DB
from pycurrents.adcp.transform import heading_rotate


class ProcEns(ProfileDict):
    """
    Class for manipulating a chunk of data after extraction from CODAS db.

    Variables are accessible as attributes of the class instance
    or via dictionary lookup::

        uu = pe.umeas
        uu = pe['umeas']

    The two lines above are equivalent.

    The names of the variables are listed in :attr:`names`.
    Other attributes of interest are

    - :attr:`nbins`: the number of depth cells
    - :attr:`nprofs`: the number of profiles
    - :attr:`velmask`: the mask for velocity values missing from the db
    - :attr:`navmask`: :attr:`velmask` combined with mask for missing
      ship velocity; it is the base mask for velocities relative to earth.

    """

    dbvelvars = ['umeas', 'vmeas', 'w', 'e']  # straight from db
    velvars = dbvelvars + ['fmeas', 'pmeas']  # derived from db; no nav
    navvars = ['u', 'v', 'fvel', 'pvel']      # using nav
    allvels = velvars + navvars

    def __init__(self, pd, flagged=True, diagnostics=False, use_bt=False):
        """
        Argument:

            *pd*
                Instance of :class:`~pycurrents.codas._codas.ProfileDict`.

        Keyword Arguments:

            *flagged*
                *True* (default) to apply default flagging to velocities.
            *diagnostics*
                *True* to calculate velocities additionally as forward
                and port components, and to calculate ship's speed
                in meters per second (:attr:`spd`) and
                course over the ground (:attr:`cog`).  Default is *False*.

        """
        dict.__init__(self)
        self.__dict__ = self
        self.nprofs = pd.nprofs
        self.nbins = pd.nbins
        self.names = pd.names[:]
        for n in self.names:
            self.__setitem__(n, pd[n])

        self.dep = self.depth[0] # warn if it is not uniform?
        self.bins = np.arange(self.nbins, dtype=int) + 1
        nbeams = self.ra.shape[-1]
        for i in range(nbeams):
            self.__setitem__('amp%d' % (i+1,), self.ra[...,i])

        self.use_bt_for_shipspeed = use_bt
        self.velmask = ma.getmaskarray(self.umeas)
        nd = self.velmask.shape[1]
        if use_bt:
            navmask = ma.getmaskarray(self.u_bt)[:, np.newaxis]
        else:
            navmask = ma.getmaskarray(self.uship)[:, np.newaxis]
        self.navmask = np.ma.mask_or(np.repeat(navmask, nd, 1), self.velmask)
        self.newmask = np.ma.nomask
        self.calculate_uv()
        if diagnostics:
            self.calculate_fp()
            self.calculate_fpmeas()
            self.calculate_spd()
        if flagged:
            self.apply_flags()

    def calculate_uv(self):
        if self.use_bt_for_shipspeed is True:
            u_ = -1* self.u_bt
            v_ = -1* self.v_bt
        else:
            u_ = self.uship
            v_ = self.vship

        self['u'] = u_[:, np.newaxis] + self.umeas
        self['v'] = v_[:, np.newaxis] + self.vmeas

    def calculate_fp(self):
        if self.u is None:
            self.calculate_uv()
        vv = np.ma.empty((self.nprofs, self.nbins, 2), dtype=float)
        vv[:,:,0] = self.u
        vv[:,:,1] = self.v
        uvr = heading_rotate(vv, 90 - self.heading)
        self['fvel'] = uvr[:,:,0].squeeze()
        self['pvel'] = uvr[:,:,1].squeeze()

    def calculate_fpmeas(self):
        vv = np.ma.empty((self.nprofs, self.nbins, 2), dtype=float)
        vv[:,:,0] = self.umeas
        vv[:,:,1] = self.vmeas
        uvr = heading_rotate(vv, 90 - self.heading)
        self['fmeas'] = uvr[:,:,0].squeeze()
        self['pmeas'] = uvr[:,:,1].squeeze()

    def calculate_spd(self):
        self['spd'] = np.ma.hypot(self.uship, self.vship)
        # FIXME: ma bug: this should not be needed.
        with np.errstate(over='ignore'):
            cog = 90 - np.ma.arctan2(self.vship, self.uship) * (180.0/np.pi)
        cog = np.ma.remainder(cog, 360)
        self['cog'] = cog

    def apply_flags(self, vars=None,
                            pg_cutoff=None, pflag=True, lgb=True,
                            mask=None, base=True,
                            keep_mask=False):
        """
        Mask *vars* with specified flags:

            *vars*
                List of variable names, variables to be masked in place;
                default is all water velocity variables.
            *pg_cutoff*
                Minimum percent good
            *pflag*
                *True* (default) to use existing pflags
            *lgb*
                *True* (default) to use existing lgb<0 to flag profiles
            *mask*
                If not *None*, it is a user-supplied mask.
            *base*
                If *True* (default), always use the missing-value mask
                appropriate to the given variable.
            *keep_mask*
                If *True*, apply new mask on top of any existing mask;
                default is *False*, to replace any existing mask.


        This can be used repeatedly on any set of array variables,
        testing the effect of different parameters.

        See also :meth:`unflag`.

        """
        if vars is None:
            vars = [var for var in self.allvels if var in self.names]
        pmask = self.make_mask(pg_cutoff=pg_cutoff, pflag=pflag, lgb=lgb, mask=mask)
        if base:
            vmask = np.ma.mask_or(self.velmask, pmask)
            nmask = np.ma.mask_or(self.navmask, pmask)
        else:
            vmask = nmask = pmask
        for var in vars:
            if var in self.velvars:
                if var == 'e':
                    # With 3-beam solutions, error vel can be masked in
                    # additional locations.
                    mask = np.ma.mask_or(vmask, np.ma.getmaskarray(self['e']))
                else:
                    mask = vmask
            elif var in self.navvars:
                mask = nmask
            else:
                mask = pmask
            self[var] = np.ma.array(self[var], mask=mask, keep_mask=keep_mask)

    def unflag(self, vars=None, base=True):
        """
        Remove flags from each variable listed in *vars*.

        If *base* is True (default), leave the appropriate
        base flags: :attr:`navmask` for velocities involving
        ship speed, :attr:`velmask` for other velocities, and
        no mask for variables such as amp.
        """
        self.apply_flags(vars=vars, pflag=False, lgb=False,
                            base=base, keep_mask=False)

    def make_mask(self, pg_cutoff=None, pflag=True, lgb=True, mask=None):
        """
        Make a mask to fit the time-depth arrays.
        See :meth:`apply_flags`.
        """
        if mask is None:
            mask = np.zeros(self.umeas.shape, dtype=bool)
        elif np.ma.isMaskedArray(mask):
            mask = mask.filled(True)
        if pflag:
            mask |=  self.pflag.astype(bool)
        if pg_cutoff is not None:
            mask |= (self.pg < pg_cutoff)
        if lgb:
            mask |=  (self.lgb < 0)[:, np.newaxis]
        self.newmask = mask
        return mask


def dbname_from_path(path):
    """
    Given either a directory containing a database, or a dbname,
    return the dbname.

    Raises ValueError if no db is found, or if more than one is found.
    """
    if os.path.exists(path + 'dir.blk'):
        return path
    pat = os.path.join(path, '*dir.blk')
    files = glob.glob(pat)
    if len(files) == 0:
        raise ValueError("path %s has no block directory" % path)
    if len(files) > 1:
        raise ValueError("path %s has %d block directories" % (path, len(files)))
    return files[0][:-7]


def get_profiles(dbname, yearbase=None, flagged=True, diagnostics=False, use_bt=False, **kw):
    r"""
    Factory function to return a :class:`ProcEns`.

    Argument:

        *dbname*
            Database name, or directory containing a single database.

    Keyword arguments:

        *yearbase*
            If *None*, use year of first profile.
        *flagged*
            *True* (default) to apply editing from db.
        *diagnostics*
            *False* (default) to omit forward, port, etc.
        *\**kw*
            Remaining kwargs are passed to
            :meth:`pycurrents.codas._codas.DB.get_profiles`

    Useful :class:`ProcEns` methods:

    - :meth:`ProcEns.apply_flags`

    - :meth:`ProcEns.unflag`

    """
    dbname = dbname_from_path(dbname)
    db = DB(dbname, yearbase=yearbase)
    profs = db.get_profiles(**kw)
    pe = ProcEns(profs, flagged=flagged, diagnostics=diagnostics, use_bt=use_bt)
    config = db.get_variable("CONFIGURATION_1", r=profs.blkprf[[0, -1]])
    # We have generally assumed that a call to get_profiles returns profiles
    # with the same configuration; hence the use of "dep", for example.  Here
    # we provide the ability to at least check whether this is true.  If it is
    # not, the calling code can use 'config_start_indices' to find the uniform
    # range and re-extract the data over that range.
    startmask = np.concatenate(([True], (config[1:] != config[:-1])))
    configs = config[startmask]
    pe['configs'] = configs
    pe['config_start_indices'] = np.arange(len(startmask))[startmask]
    # Add items with the same names as in the raw data, so that BottomEdit will
    # work with CODAS data and with single-ping data.
    pe["CellSize"] = configs[0]["bin_length"]
    pe["Pulse"] = configs[0]["pls_length"]
    if len(pe.dep) < 2:
        kw2 = kw.copy()
        kw2["nbins"] = 2
        profs2 = db.get_profiles(**kw2)
        dep = profs2.depth[0]
    else:
        dep = pe.dep
    pe["depth_interval"] = dep[1] - dep[0]
    pe["Bin1Dist"] = dep[0] - configs[0]["tr_depth"]
    return pe


def get_txy(dbname, yearbase=None, **kw):
    r"""
    Factory function to return a :class:`ProfileDict` with
    times and positions, but no profile data.

    Argument:

        *dbname*
            Database name, or directory containing a single database.

    Keyword arguments:

        *yearbase*
            If *None*, use year of first profile.
        *\**kw*
            Remaining kwargs are passed to
            :meth:`pycurrents.codas._codas.DB.get_profiles`

    Attributes (or keys) of the returned instance will include
    *blkprf*, *ymdhms*, *dday*, *yearbase*, *lon*, and *lat*.

    """
    dbname = dbname_from_path(dbname)
    db = DB(dbname, yearbase=yearbase)
    profs = db.get_profiles(txy_only=True, **kw)
    return profs

class Stepper:
    """
    Step through a CODAS database, forwards or backwards.

    The *profs* attribute (implemented as a property) holds
    a ProcEns instance with the presently selected time range.

    Use the *dday0* and *ndays* properties to read or change
    the start time and increment.

    The *forward* and *back* methods shift the start time.


    Example::

      from pycurrents.codas.tools import Stepper
      cstep = Stepper("/home/currents/programs/q_demos/uhdas/underway/adcpdb/a_kk")
      print cstep.profs.u.shape
      print cstep.profs.dday[0]
      cstep.ndays = 1.5
      cstep.forward()
      print cstep.profs.dday[0]
      cstep.ndays = 1.0
      cstep.back()
      print cstep.profs.dday[0]

    """

    def __init__(self, dbpathname):
        self.db = DB(dbpathname)
        self._dday0 = self.db.dday_start
        self._ndays = None
        self._profs = None

    def get_profs(self):
        if self._profs is None:
            p = self.db.get_profiles(startdd=self.dday0,
                                     ndays=self.ndays,
                                     )  # put in nbins later?
            self._profs = ProcEns(p)
        return self._profs

    profs = property(get_profs)

    def set_dday0(self, val):
        self._dday0 = max(self.db.dday_start, val)
        self._profs = None

    def get_dday0(self):
        return self._dday0

    dday0 = property(get_dday0, set_dday0)

    def set_ndays(self, val):
        self._ndays = val
        self._profs = None

    def get_ndays(self):
        return self._ndays

    ndays = property(get_ndays, set_ndays)

    def forward(self):
        self.dday0 += self.ndays
        self.dday0 = min(self.dday0, self.db.dday_end - self.ndays)
                        # This may need options for how to handle
                        # running off the end.

    def back(self):
        self.dday0 -= self.ndays




