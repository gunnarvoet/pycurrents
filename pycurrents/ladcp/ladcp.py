"""
ladcp data reading, calculations, and display.
"""
import os
from subprocess import Popen, PIPE
import logging

import numpy as np

# To avoid locking in the default backend, matplotlib
# imports will be done inside the plotting functions.

from pycurrents.adcp import raw_rdi
from pycurrents.adcp.transform import Transform, rdi_xyz_enu

from pycurrents.codas import to_date, to_datestring

from pycurrents.num.cleaner import fillmasked
from pycurrents.num import median
from pycurrents.num import interp1
from pycurrents.num import bl_filt
from pycurrents.num import runstats
from pycurrents.num.nptools import Flags

from pycurrents.plot.mpltools import get_extcmap
from pycurrents.plot.maptools import LonFormatter, LatFormatter

from pycurrents.data.seawater import depth as depth_from_p
from pycurrents.data.navcalc import uv_from_txy

from pycurrents.system import Bunch
from pycurrents.file import npzfile

from pycurrents.adcp._bottombounce import bump_coeff

import pycurrents.ladcp.unistat as unistat

_log = logging.getLogger(__name__)


#TODO: check for possible yearbase problems between the CTD and
#      the LADCP.

#TODO: check to see what soundspeed corrections are needed.

#TODO: add a scattering strength calculation.

#TODO: convert editing to use flag bits

#TODO: write netcdf output file

# Note that the rdi_xyz_enu function may be temporary...

## Editing flags from original UH shear method:
#define GLITCH_BIT                  BIT_0    /* Set by hand editing only */
#define ERROR_VEL_BIT               BIT_1
#define W_BIT                       BIT_2
#define WAKE_BIT                    BIT_3
#define SHEAR_BIT                   BIT_4
#define PG_BIT                      BIT_5
#define COR_BIT                     BIT_6
#define TEMPORARY_BIT               BIT_7

# This is for a Flags instance in Profile that is passed on to, and
# further amended in, Velocity.
# It operates at the level of depth cells for all beams together,
# so it does not include the correlation threshold criterion.
# (If any beam fails the correlation threshold, enue_base will
# be set.)
# (We could make a second Flags array to track editing at the
# single beam level.)
flagnames = ['enue_base',   # mask for u from initial enue calculation
             'e',
             'wake',   # not yet used
             'bottom', # based on WT ping bottom detection -> lgb
             'ppi',    # not yet used

             # below here, flags are set in Velocity
             'top_chop',  # :i0 in editparams
             'enue_composite', # after composite calculation of enue
             'top_outlier',
             'cell_outlier',
             ]

             # Although composite() is a Profile method, it is called only
             # in Velocity.


class Profile:
    """
    The Profile class is intended for assembling information about
    the cast and deriving quantities that are not specific to any
    LADCP calculation.  That step is left for the Velocity class,
    which creates and uses a Profile instance.
    """
    editparams = Bunch(max_e=0.2,          # absolute max e
                       max_e_deviation=2,  # max in terms of sigma
                       min_cor=70,
                      )
    def __init__(self, fname, sonar="wh",
                              lonlat=None,
                              magdec=None,
                              use_index=False,
                              in_water=False,
                              defer=False,
                              badbeam=None,
                              editparams=None,
                              ):
                              # TODO: Add wake identification parameters.
        """
        *use_index* : if True, the ens_num attribute will be the index
                      into the file instead of the recorded ensemble
                      number.  This is used only in plotting.  It is
                      useful when the profile is the concatenation of
                      files generated when a firmware bug stopped and
                      restarted logging. (default is False)
        *defer* : if True, do not do the editing and velocity calculations.
                      (default is False)
        *badbeam* : if not None, this is the 1-based number of a beam to
                    be ignored.
        """
        self.fname = fname
        self.sonar = sonar
        self.lonlat = lonlat
        self.badbeam = badbeam
        self._ibadbeam = None if badbeam is None else badbeam-1

        if editparams is not None:
            self.editparams = Bunch(self.editparams)
            self.editparams.update_values(editparams, strict=True)

        _log.info("File name: %s", fname)
        _log.info("Profile editparams: \n%s", self.editparams)

        self.max_e = self.editparams.max_e
        self.max_e_deviation = self.editparams.max_e_deviation
        self.min_cor = self.editparams.min_cor

        self.file = raw_rdi.FileBBWHOS(fname, sonar, trim=True)

        if in_water: # Experimental
            ppd = None  # flag
            if self.file.sonar.model == 'wh':
                ppd = self.file.read(varlist=['VariableLeader'])
                pressure = ppd['VL']['Pressure'].astype(float)/1000.0
                                                        # to decibars
                cond = pressure > 5 + pressure.min()
                ind = np.nonzero(cond)[0]
                if len(ind) > 5:
                    ppd = self.file.read(start=ind[2], stop=ind[-2])
                    self.have_p = True
                else:
                    ppd = None
            if ppd is None:
                self.have_p = False
                _testprof = Profile(fname, sonar=sonar, lonlat=lonlat,
                                    magdec=magdec,
                                    use_index=use_index,
                                    in_water=False,
                                    defer=False,
                                    badbeam=badbeam,
                                    editparams=self.editparams)
                pressure = _testprof.fake_pressure
                cond = pressure > 5 + pressure.min()
                ind = np.nonzero(cond)[0]
                if len(ind) > 5:
                    ppd = self.file.read(start=ind[2], stop=ind[-2])
                    self.fake_pressure = pressure[ind[2]:ind[-2]]
                else:
                    raise ValueError("Too few in-water samples.")
        else:
            ppd = self.file.read()
        self.file.close()

        for key, val in ppd.items():
            setattr(self, key, val)

        self.has_bt = hasattr(self, "bt_vel") and not np.all(self.bt_vel.mask)
        self.yearbase = self.file.yearbase
        self.nprofs = self.VL.size

        fn = os.path.basename(fname)
        date = to_datestring(self.yearbase, ppd.dday[0])
        self.title = "%s  %s" % (fn, date) # maybe add lon, lat
        self.basename = fn
        self.datestring = date

        vl = self.VL
        self.temperature = np.ma.masked_equal(vl['Temperature'],
                                                    65535).astype(float)/100.0
        if self.file.sonar.model == 'wh':
            pressure = vl['Pressure'].astype(float)/1000.0 # to decibars
        else:
            pressure = np.ma.zeros(self.temperature.shape)
            # can't mask it--that would foul up the shared x-axis autoscaling
        self.pressure = pressure

        self.voltage = vl['ADC1']
        self.current = vl['ADC0']

        if use_index:
            ens = np.arange(len(self.temperature))
        else:
            ens = vl['EnsNum'].astype(np.uint) + vl['EnsNumMSB'].astype(np.uint)*65536
        self.ens_num = ens
        self.transform = self._get_transform()
        self._magdec = magdec
        self.flags = Flags(shape=(self.nprofs, self.NCells),
                           names=flagnames)
        if not defer:
            self.calculate()

    @property
    def magdec(self):
        if self._magdec is None:
            if self.lonlat is None:
                _log.info("No magnetic declination is available; using 0")
                self._magdec = 0
            else:
                lonlat = self.lonlat
                y, m, d = to_date(self.yearbase, self.dday[0])[:3]
                output = Popen(["magdec", str(lonlat[0]), str(lonlat[1]),
                                                str(y), str(m), str(d)],
                                                stdout=PIPE).communicate()[0]
                output = output.strip()
                _log.info("magdec output is: %s", output)
                self._magdec = float(output.split()[0])
        return self._magdec

    def calculate(self):
        """
        Transform, edit, integrate.
        """
        self.cor_edit()
        self.to_enue(ibad=self._ibadbeam)
        mask = np.ma.getmaskarray(self.enue[:, :, 0])
        self.flags.addmask(mask, "enue_base")
        if self.badbeam is None:
            max_e = min(self.max_e, self.e.std() * self.max_e_deviation)
            _log.info("max_e is %s", max_e)
            self.max_e_applied = max_e
            self.error_vel_edit(max_e)
        self.bt_edit()
        self.integrate_uvw()

    def cor_edit(self):
        c0 = self.vel.count()
        self.vel.mask |= self.cor < self.min_cor
        _log.info("min_cor = %d, deleted %d beam velocities", self.min_cor,
               c0 - self.vel.count())

    def _get_transform(self):
        if self.sysconfig.convex:
            geometry = 'convex'
        else:
            geometry = 'concave'
        tr = Transform(angle=self.sysconfig.angle, geometry=geometry)
        return tr


    def _get_relative_depths(self):
        """
        Correct depths for pitch and roll; soundspeed correction
        can be added later if needed.
        Adding the instrument depth will be done separately.
        """
        if self.sysconfig.up:
            orientation = 'up'
        else:
            orientation = 'down'
        xyz = np.zeros((self.nprofs, self.NCells, 3))
        xyz[:,:,2] = self.dep
        enu = rdi_xyz_enu(xyz, self.heading,   # (heading is irrelevant)
                                 self.pitch,
                                 self.roll,
                                 orientation=orientation)
        return enu[:,:,2]   # ignore east and north

    def _get_relative_beam_depths(self, tslice=None):
        """
        Correct beam depths for pitch and roll; soundspeed correction
        can be added later if needed.
        Adding the instrument depth will be done separately.
        """
        if tslice is None:
            tslice = slice(None)
            nprofs = self.nprofs
            heading = self.heading
        else:
            heading = self.heading[tslice]
            nprofs = len(heading)

        if self.sysconfig.up:
            orientation = 'up'
        else:
            orientation = 'down'
        xyz0 = np.zeros((nprofs, self.NCells, 3))
        xyz0[:,:,2] = - self.dep  # need positive up here
        theta = np.deg2rad(self.sysconfig.angle)
        xx = self.dep * np.tan(theta)
        beamd = np.zeros((nprofs, self.NCells, 4))
        for i in range(4):
            xyz = xyz0.copy()
            if i == 0:
                xyz[:,:,0] = -xx  # beam 1: port, or -X
            elif i == 1:
                xyz[:,:,0] = xx   # beam 2: starboard, or X
            elif i == 2:
                xyz[:,:,1] = xx   # beam 3: forward, or Y
            else:
                xyz[:,:,1] = -xx   # beam 4: aft, or -Y
            enu = rdi_xyz_enu(xyz, heading,     # heading doesn't matter
                                     self.pitch[tslice],
                                     self.roll[tslice],
                                     orientation=orientation)

            beamd[...,i] = - enu[:,:,2]   # ignore east and north
                                          # back to positive down
        return beamd

    def wake_beam_alignment(self, start, stop, step):
        """
        Arguments are passed to wake_vectors().

        Returns dots, vecamps.

        dots are the inner products of the beam unit vectors
        with the water displacement unit vectors.  Values near
        1 indicate that a beam is nearly aligned with the wake,
        so interference is likely.

        vecamps are the magnitudes of the water displacements.

        """
        if self.trans.coordsystem == 'earth':
            raise NotImplementedError(
                    "Wake angle checking works only in beam coordinates")
        vecs = self.wake_vectors(start, stop, step)
        vecamps = np.sqrt((vecs * vecs).sum(axis=-1))
        vecamps[vecamps == 0] = np.nan
        vecs /= vecamps[..., np.newaxis]  # unit vectors
        # vecs is (nsamps, ntimes, 3)

        if self.sysconfig.up:
            orientation = 'up'
        else:
            orientation = 'down'
        th = np.deg2rad(self.sysconfig.angle)
        c = np.cos(th)
        s = np.sin(th)
        beamvecs = np.array([[-s, 0, -c],   # X is from 1 towards 2
                             [s, 0, -c],
                             [0, s, -c],    # Y is from 4 towards 3
                             [0, -s, -c]])
        # beamvecs is 4x3: last dimension is x, y, z
        # We prepend a "time" axis because we want the beams
        # to be "depth-like", and the following function assumes
        # time-depth-component order.  We can't just add an axis because
        # rdi_xyz_enu is requiring a full array.
        strides = [0] + list(beamvecs.strides)
        beamvecs_tmp = np.lib.stride_tricks.as_strided(beamvecs,
                            shape=(len(self.heading), 4, 3),
                            strides=strides)

        beamenu = rdi_xyz_enu(beamvecs_tmp, self.heading,
                              self.pitch, self.roll,
                              orientation=orientation)
        # beamenu is (ntimes, nbeams, 3)

        dots = (vecs[:, :, np.newaxis] * beamenu[np.newaxis, ...]).sum(axis=-1)
        # dots is (nsamp, ntimes, nbeams)

        return dots, vecamps

    def wake_from_angle(self, dots, angle):
        """
        dots comes from wake_beam_alignment()
        angle is a threshold in degrees

        Returns badone, maxvals.  badone is a boolean
        array, (ntimes, nbeams), as in wake_identify.

        maxvals is (ntimes,) with the max cos(angle)
        values used to decide on wake interference.

        We are using the worst case among the samples provided in
        dots.
        """
        cos_angle = np.cos(np.radians(angle))
        maxdots1 = np.ma.masked_invalid(dots).max(axis=0)
        i_beam_max = np.ma.argmax(maxdots1, axis=-1, fill_value=-1)
        maxvals = maxdots1.max(axis=-1)
        in_wake = (maxvals > cos_angle).filled(False)
        badone = np.zeros(dots.shape[1:], dtype=bool)
        for i in range(4):
            cond = in_wake & (i_beam_max == i)
            badone[cond, i] = True

        return badone, maxvals

    def wake_identify0(self, i0, i1, excess_abs=4, excess_rel=3):
        """
        A different approach: look directly for the telltale bias
        towards zero at the top, in beam coordinates, in a single
        beam.

        The velocities at *i0* and i0 + 1 are compared to the
        average from i0 + 2 to *i1*.

        The primary return, *badone*, is a boolean array
        with True in no more than one of the four beams to
        mark that beam in that profile as bad.

        We may want to do the usual trick of padding to get
        neighbors, but if so, we need to be careful to ensure
        that no more than one beam is marked at a time.

        Returns *badone*, *bavg*, and *bias*.  Normally only
        the first is used; the other two are for development
        and debugging.
        """

        bavg = self.vel[:,i0+2:i1,:].mean(axis=1)
        bavg.shape = (bavg.shape[0], 1, bavg.shape[1])
        vel = self.vel.copy() - bavg
        bias = 2 * vel[:, i0] + vel[:, i0+1]

        # Downlooker is moving up, so beam velocity is negative,
        # hence bias towards zero is *positive* relative to mean.
        bad = bias > median(np.ma.abs(bias)) * excess_abs

        # Filter out the case where more than one beam is "bad".
        badone = bad & (bad.sum(axis=-1)[:,np.newaxis] == 1)

        # Make sure the bias is large enough compared to the
        # maximum bias in the "good" beams.
        others = ~(badone.filled(False))
        #otherlevel = (bias * others).max(axis=-1)
        otherlevel = np.ma.abs(bias * others).max(axis=-1)
        badone &= bias > excess_rel * otherlevel[:,np.newaxis]

        return badone.filled(False), bavg.squeeze(), bias

    def wake_identify(self, i0, i1,
                       excess_abs=4,
                       excess_rel=3,
                       min_n_beams=3,
                       rs_window=5):
        """
        A different approach: look directly for the telltale bias
        towards zero at the top, in beam coordinates, in a single
        beam.  This works for the MIXET data, but check_wake does
        not.

        The velocities at *i0* and i0 + 1 are compared to the
        average from i0 + 2 to *i1*.

        The primary return, *badone*, is a boolean array
        with True in no more than one of the four beams to
        mark that beam in that profile as bad.

        Experimental version...

        """

        bavg = self.vel[:,i0+2:i1,:].mean(axis=1)
        bavg.shape = (bavg.shape[0], 1, bavg.shape[1])
        vel = self.vel.copy() - bavg
        bias_orig = 2 * vel[:, i0] + vel[:, i0+1]
        rs = runstats.Runstats(bias_orig, rs_window, axis=0)
        bias = rs.median

        maxbias = bias.max(axis=-1)
        maxbias[bias.count(axis=-1) < min_n_beams] = np.ma.masked

        maxbiasmask = (bias == maxbias[:, np.newaxis])

        otherbias = np.ma.masked_where(maxbiasmask.filled(True), bias)

        background = np.ma.median(np.ma.abs(otherbias))

        bad1mask = maxbias > excess_abs * background
        bad2mask = maxbias > excess_rel * np.ma.abs(otherbias).max(axis=-1)

        badmask = (bad1mask & bad2mask).filled(False)

        badone = np.zeros(bias.shape, bool)
        badone[badmask] = maxbiasmask[badmask].filled(False)

        #  alternative approach
        #ibias = np.ma.argmax(maxbiasmask, fill_value=3, axis=-1)
        #badnum = np.ma.array(ibias, mask=~badmask)
        #goodmask = np.logical_and(bias.count() == min_n_beams, ~badmask)
        #return Bunch(locals())

        return badone, bavg.squeeze, bias

    def process_amp(self, amp, med_cutoff=20, medfilt_window=5):
        """
        Lightly filter amplitude, and correct for spreading loss
        but not absorption, in preparation for bottom detection.
        """
        # modified directly from pingavg

        # approx depth in bin units:
        d = self.Bin1Dist / self.CellSize + np.arange(self.NCells)

        # approx spreading loss (nominal 0.45 db/count):
        spread = (20/0.45) * np.log10(d)

        if med_cutoff is None:
            ampq = amp
        else:
            amprh = runstats.Runstats(amp, medfilt_window, axis=0)
            ampq = amprh.medfilt(med_cutoff)

        ampq = ampq.astype(float) + spread[:, np.newaxis]

        return ampq, d  # d is in bin units as floating point


    def bottom(self, tslice=None,
                     bump_thresh=55,
                     **ampedit_kw):

        if tslice is None:
            tslice = slice(None)

        ampq, d = self.process_amp(self.amp[tslice], **ampedit_kw)

        rawbump = bump_coeff(ampq, d, self.sysconfig.angle)
        maskedbump = np.ma.masked_less(rawbump, bump_thresh)
        maskedamp = np.ma.array(ampq, mask=maskedbump.mask)

        mab = np.ma.masked_equal(maskedamp.argmax(axis=1), 0, copy=False)

        nt, nd, nb = ampq.shape
        ii, kk = np.mgrid[:nt, :nb]
        vel = self.vel[tslice]
        mabvel0 = vel[ii, mab.filled(0), kk]

        mab1 = np.ma.minimum(mab + 1, nd-1)  # or mask the points
        mabvel1 = vel[ii, mab1.filled(0), kk]

        mabm1 = np.ma.maximum(mab - 1, 0)  # or mask the points
        mabvelm1 = vel[ii, mabm1.filled(0), kk]


        mabvel0 = np.ma.masked_where(mab.mask, mabvel0)
        mabvel1 = np.ma.masked_where(mab.mask, mabvel1)
        mabvelm1 = np.ma.masked_where(mab.mask, mabvelm1)

        # We might end up needing nothing other than mabvel.

        return Bunch(locals())

    def bottomvel(self, bvars, frac=0):
        """
        Stage 2: bvars is output from bottom()

        It's not clear we gain by interpolating to a point beyond the
        max amp bin, so default frac will start at zero.
        """

        if frac >=0:
            vel = bvars.mabvel0 * (1.0 - frac) + frac * bvars.mabvel1
        else:
            vel = bvars.mabvel0 * (1.0 + frac) - frac * bvars.mabvelm1

        if self.trans.coordsystem == 'earth':
            raise ValueError("This BT calculation requires beam velocities.")
        tr = self.transform
        xyze = tr.beam_to_xyz(vel, ibad=self._ibadbeam)
        heading = self.heading[bvars.tslice] + self.magdec
        if self.sysconfig.up:
            orientation = 'up'
        else:
            orientation = 'down'
        enue = rdi_xyz_enu(xyze, heading,
                                 self.pitch[bvars.tslice],
                                 self.roll[bvars.tslice],
                                 orientation=orientation)

        return Bunch(locals())  # another possibly temporary massive return
                                # looks like we need to at least remove
                                # "self" from this

    def find_btslice(self, package_depth=None, dmax=None):
        if dmax is None or package_depth is None:
            dmax = self.fake_pressure.max()
            package_depth = self.fake_pressure
        inst_range = self.NCells * self.CellSize + self.Bin1Dist
        clipfac = np.cos(np.deg2rad(self.sysconfig.angle))
        # Divide by clipfac so calculated lgb covers full range within
        # the time slice.
        top = dmax - inst_range / clipfac
        below = np.nonzero(package_depth > top)[0]
        i0 = below.min()
        i1 = below.max()
        return slice(i0, i1)

    def abs_bottom(self, dz, dstart=0,
                             d_inst=None,
                             tslice=None,
                             std_clip=2.5,
                             min_ngood=20,
                             bump_thresh=55, # for bottom()
                             ampedit_kw = None, # for process_amp
                             ):
        """
        Experimental calculation of bottom-referenced profile.

        It also sets and applies a bottom (lgb) mask to the velocities.

        """
        if tslice is None:
            tslice = self.find_btslice()

        if d_inst is None:
            d_inst = self.fake_pressure # positive down for now
        d_inst = d_inst[tslice]

        if ampedit_kw is None:
            ampedit_kw = dict()

        xb = self.bottom(tslice=tslice, bump_thresh=bump_thresh, **ampedit_kw)
        bv = self.bottomvel(xb)

        bt_enue = bv.enue.view()
        nt, nb = bt_enue.shape
        bt_enue.shape = nt, 1, nb


        d_relative = self._get_relative_depths()[tslice]
        depth = d_relative + d_inst[:, np.newaxis]
        d0 = int((depth.min() - dstart) / dz) * dz + dstart
        dgrid = np.arange(d0, np.floor(depth.max()), dz)

        dbeam = (self._get_relative_beam_depths(tslice) +
                  d_inst[:, np.newaxis, np.newaxis])

        ii, kk = np.mgrid[:nt, :nb]
        d_mab = dbeam[ii, xb.mab.filled(0), kk]
        d_mab = np.ma.masked_where(xb.mab.mask, d_mab)
        d_median = np.ma.median(d_mab)

        clipfac = np.cos(np.deg2rad(self.sysconfig.angle))
        lgb = np.ma.floor(xb.mab.min(axis=1) * clipfac) - 1
        lgb = lgb.filled(1000)
        indices = np.arange(self.NCells, dtype=int)
        lgb_mask = indices > lgb[:, np.newaxis]
        lgb_mask |= lgb[:, np.newaxis] < 0
        lgb_mask |= (d_median - d_inst[:, np.newaxis]) * clipfac < d_relative

        self.flags.addmask(lgb_mask, 'bottom', index_obj=tslice)

        enue = self.enue[tslice] - bt_enue
        enue.mask |= lgb_mask[..., np.newaxis]


        enue_grid = np.ma.masked_all((nt, len(dgrid), nb))
        for i in range(nt):
            enue_grid[i] = interp1(depth[i], enue[i], dgrid)

        # 2-pass standard deviation editing.
        counts = [enue_grid.count()]          # to track editing
        for i in range(2):
            #m = np.ma.median(enue_grid, axis=0) # slow...
            m = np.ma.mean(enue_grid, axis=0)
            dev = enue_grid - m
            sdev = dev.reshape(-1, dev.shape[2])
            s = enue_grid.std(axis=0)   # std over time and depth
            enue_grid.mask |= np.ma.abs(dev) > s * std_clip
            counts.append(enue_grid.count())

        if self.badbeam is None:
            # If any variable is bad, mask all 4.
            enue_grid.mask |= np.any(enue_grid.mask, axis=-1)[..., np.newaxis]
        else:
            # Ignore error velocity:
            enue_grid.mask |= np.any(enue_grid.mask[..., :-1],
                                     axis=-1)[..., np.newaxis]

        counts.append(enue_grid.count())

        uvwe = enue_grid.mean(axis=0)
        ngood = enue_grid.count(axis=0)
        uvwe.mask |= ngood < min_ngood
        u = uvwe[:,0]
        v = uvwe[:,1]
        w = uvwe[:,2]
        e = uvwe[:,3]

        ret = Bunch(dep=dgrid, u=u, v=v, w=w, e=e, ngood=ngood,
                     mab=xb.mab,
                     lgb = np.ma.masked_greater(lgb, 999),
                     counts=counts,
                     tslice=tslice,
                     d_mab = d_mab,
                     d_median = d_median,
                     )

        # extra output for debugging only; makes npzfile huge
        if False:
            ret.update(locals())
            ret.pop("self")
            ret.pop("xb")
            ret.pop("bv")

        return ret

    def to_enue(self, ibad=None, replace=True, indexmask=None):
        """
        If not None, indexmask is a boolean indexing array to
        select the times for which to do the calculation.

        Not yet supported for replace==True or for bt.
        """
        if self.has_bt:
            bt_enue = self.bt_vel
        if self.trans.coordsystem == 'earth':
            enue = self.vel
        else:
            tr = self.transform
            if indexmask is None:
                sl = slice(None)
            else:
                sl = indexmask
            xyze = tr.beam_to_xyz(self.vel[sl], ibad)
            heading = self.heading[sl] + self.magdec
            if self.sysconfig.up:
                orientation = 'up'
            else:
                orientation = 'down'
            enue = rdi_xyz_enu(xyze, heading,
                                     self.pitch[sl],
                                     self.roll[sl],
                                     orientation=orientation)
            # TODO: should we apply the indexmask slice to BT?
            if self.has_bt:
                bt_xyze = tr.beam_to_xyz(self.bt_vel, ibad)
                bt_enue = rdi_xyz_enu(bt_xyze, self.heading + self.magdec,
                                         self.pitch,
                                         self.roll,
                                         orientation=orientation)

        # TODO: should the indexmask slice be applied here also?
        if replace:
            self.u = enue[...,0]
            self.v = enue[...,1]
            self.w = enue[...,2]
            self.e = enue[...,3]
            self.enue = enue
            if self.has_bt:
                self.bt_u = bt_enue[...,0]
                self.bt_v = bt_enue[...,1]
                self.bt_w = bt_enue[...,2]
                self.bt_e = bt_enue[...,3]
                self.bt_enue = bt_enue

        else:
            return enue

    def composite(self, badone):
        """
        *badone* is a boolean array of shape (npings, nbeams)

        Returns a copy of self.enue in which 3-beam solutions
        replace the existing 4-beam solutions as specified by
        *badone*.
        """
        enue = self.enue.copy()
        for i in range(4):
            if badone[:,i].sum() == 0:
                continue # self.to_enue chokes on all-false indexmask
            threebeam = self.to_enue(ibad=i, replace=False,
                                     indexmask=badone[:,i])
            enue[badone[:,i]] = threebeam
        # Maybe the following should use index 3, to flag 3-beam solutions.
        self.flags.addmask(np.ma.getmaskarray(enue)[..., 0], "enue_composite")
        return enue

    def integrate_uvw(self, dslice=slice(1,10)):
        """
        Quick initial integration.

        A more careful version, with additional editing
        applied, is in a Velocity method.
        """
        self.ubar = self.u[:, dslice].mean(axis=1)
        self.vbar = self.v[:, dslice].mean(axis=1)
        self.wbar = self.w[:, dslice].mean(axis=1)

        # For this crude integration, we are assigning each
        # velocity to the time interval between it and the previous
        # sample.
        dt = np.zeros_like(self.dday)
        dt[1:] = np.diff(self.dday) * 86400
        self.x_u = - (fillmasked(self.ubar) * dt).cumsum()
        self.y_v = - (fillmasked(self.vbar) * dt).cumsum()
        self.z_w = - (fillmasked(self.wbar) * dt).cumsum()

        # In case there is no pressure sensor, make a fake
        # pressure that can be used for in_water detection,
        # starting and ending the cast a bit below the surface.
        z_backwards = self.z_w - self.z_w.compressed()[-1]
        igood = np.nonzero(~np.ma.getmaskarray(self.z_w))[0]
        i0 = igood[0]
        i1 = igood[-1]
        weights = np.zeros(z_backwards.shape, dtype=float)
        weights[i0:i1] = np.linspace(0, 1, i1 - i0)
        weights[i1:] = 1
        zz = weights * z_backwards + (1.0 - weights) * self.z_w
        self.fake_pressure = - zz
        self.ifirst = i0
        self.ilast = i1
        self.ibottom = np.argmax(zz)

    def wake_vectors(self, start, stop, step):
        """
        Calculate location of wake relative to instrument.
        """
        npings = len(self.x_u)
        xyz = np.empty((npings, 3), dtype=float)
        xyz[:, 0], xyz[:, 1], xyz[:, 2] = (self.x_u, self.y_v, self.z_w)
        steps = list(range(start, stop, step))
        nsamp = len(steps)
        vecs = np.zeros((nsamp, npings, 3), dtype=float)
        # xyz is instrument relative to water
        for j, i in enumerate(steps):
            # instrument at earlier ping minus instrument now;
            vecs[j, i:] = xyz[:-i] - xyz[i:]
        return vecs

    def scan_summary(self):
        """
        Return a string similar to the output of the old scanbb.

        """
        if not hasattr(self, 'z_w'):
            self.calculate()
        lines = ['Raw %s data file: %s' % (self.file.sonar.instname,
                                           self.basename)]
        lines.append('coords: %s' % self.trans.coordsystem)
        lines.append('')
        lines.append('Last ensemble was %d; %d were bad' %
                     (self.nprofs, 0))
        lines.append('')
        #zz = self.fake_pressure
        zz = -self.z_w # for scanbb compatibility
        i = np.ma.argmin(zz)
        lines.append('zmin:  %7.1f  at  %5d' % (zz[i], i))
        ibot = np.ma.argmax(zz)
        lines.append('zmax:  %7.1f  at  %5d' % (zz[ibot], ibot))
        i = self.ilast
        lines.append('zend:  %7.1f  at  %5d' % (zz[i], i))
        lines.append('')

        lines.append('number_with_velocity:   %5d' % (self.ilast - self.ifirst))
        lines.append('first_good_ensemble:    %5d' % self.ifirst)
        lines.append('last_good_ensemble:     %5d' % self.ilast)
        lines.append('')

        lines.append('downcast:  %s  to  %s' %
                     (to_datestring(self.yearbase, self.dday[self.ifirst]),
                      to_datestring(self.yearbase, self.dday[ibot])))
        lines.append('upcast:    %s  to  %s' %
                     (to_datestring(self.yearbase, self.dday[ibot+1]),
                      to_datestring(self.yearbase, self.dday[self.ilast])))
        lines.append('')

        return '\n'.join(lines)


    def error_vel_edit(self, emax):
        """
        Initial error velocity screening.
        """
        cond = (np.abs(self.e) > emax)
        self.flags.addmask(cond, 'e')
        self.enue[cond] = np.ma.masked
        if self.has_bt:
            cond = np.abs(self.bt_e) > emax
            self.bt_enue[cond] = np.ma.masked

    def bt_edit(self):
        """
        Edit built-in bottom track based on consistent depths.

        Mask out any bt data for which the second difference of the
        depth in time, in any beam, exceeds the cell size.
        """
        if not self.has_bt:
            return
        cond = np.abs(np.diff(self.bt_depth.data, n=2, axis=0)) < self.CellSize
        if self.badbeam is not None:
            cond[:, self._ibadbeam] = True
        cond = np.logical_not(cond.all(axis=1))
        self.bt_enue[1:-1][cond] = np.ma.masked
        self.bt_depth[1:-1][cond] = np.ma.masked
        self.bt_enue[0,:] = np.ma.masked
        self.bt_enue[-1,:] = np.ma.masked
        self.bt_depth[0,:] = np.ma.masked
        self.bt_depth[-1,:] = np.ma.masked

    def pressure_from_ctd(self, dday, pressure):
        """
        Given an approximately correct *dday* with the same yearbase
        as the Profile, and a matching *pressure*, find an
        appropriate small time shift and save the corresponding
        ctd_pressure as an attribute.

        This is a minimal version, looking only for a *small* and
        *constant* shift.  A fancier version could break the record
        into pieces and find a clock drift as well as a shift.
        """
        # pings may be staggered, so interpolate both the ctd and the
        # ladcp to a common grid
        t0 = min(self.dday[0], dday[0])
        t1 = max(self.dday[-1], dday[-1])
        dt0 = 86400 * (dday[-1] - dday[0]) / dday.size

        # If the ctd file has not already been averaged to something
        # like 1 Hz, subsample it to get a more reasonable size.
        if dt0 < 0.5:
            step = int(round(0.5/dt0))
            if step > 1:
                dday = dday[::step]
                pressure = pressure[::step]

        n = max(dday.size, self.dday.size)
        dt = 0.5 * (t1 - t0) / n
        tgrid = np.arange(t0, t1, dt)
        dpdt = np.ma.diff(pressure) / (np.diff(dday)*86400)

        # Grid and lightly smooth both w series.
        wgrid = interp1(self.dday, self.wbar, tgrid)
        pwgrid = interp1(0.5 * (dday[:-1] + dday[1:]), dpdt, tgrid, masked=True)
        pgrid = interp1(dday, pressure, tgrid, masked=True)
        # (Both vertical velocities are positive-down package
        # velocities.)
        nfilt = round(3.0/(dt*86400))  # 3-second half-width
        wgrid, ww = bl_filt(wgrid, nfilt)
        pwgrid, ww = bl_filt(pwgrid, nfilt)

        # Now find the lag, using wgrid.filled(0) and pwgrid.filled(0),
        # and using depths > 10 dbar to clip the ends.
        i_wet = np.nonzero(pgrid > 10)[0]
        sl = slice(i_wet[0], i_wet[-1])
        w = wgrid[sl].filled(0)
        pw = pwgrid[sl].filled(0)
        # z[k] = sum_n a[n] * conj(v[n+k])
        cor = np.correlate(w, pw, mode="same")
        cormax = cor.max()
        _log.info("Fitting CTD to LADCP, max cor is %s.", cormax)
        imax = np.nonzero(cor == cormax)[0][0]
        k = imax - cor.size / 2.0  # shift pw left this number of tgrid points
        newp = interp1(dday + k*dt, pressure, self.dday, masked=True)
        self.p_ctd = newp
        # Save for diagnostic plotting etc.
        self.p_ctd_vars = Bunch(cor=cor, imax=imax, tshift=k*dt,
                                w=w, pw=pw, tgrid=tgrid, pgrid=pgrid,
                                t0=t0, t1=t1, dt=dt,
                                )
        # (This might have gaps, or not cover the full range.)
        return newp


def shear(p):
    """
    Temporary quick access to Shearcalc.
    """
    # really quick: just add pressure to relative depth
    pdepth = p._get_relative_depths() + p.pressure[:, np.newaxis]


    ndgrid = 2000
    dz = 0.25
    ncells = p.NCells
    sc = unistat.Shearcalc(0, dz, ndgrid, ncells)
    mask = np.zeros((p.nprofs, ncells), dtype=np.uint8)
    mask[:,0] = 1 # kill the top bin
    badone = p.wake_identify(1,12)[0]
    enue = p.composite(badone)

    sc(enue, mask, pdepth)
    return sc

def from_cnv0(fname):
    """
    Read a Seabird cnv file with a time series ctd record (either the
    original sample rate or processed down to 1 Hz), and return a
    Bunch with dday, pressure, longitude, and latitude.
    """
    from pycurrents.data.seabird import CnvFile

    cf = CnvFile(fname)
    b = Bunch(dday=cf.dday, pressure=cf.pressure,
                longitude=cf.records['longitude'],
                latitude=cf.records['latitude'])
    return b

def from_cnv(fname):
    """
    Read a Seabird cnv file with a time series ctd record (either the
    original sample rate or processed down to 1 Hz), and return a
    Bunch with dday, pressure, longitude, and latitude.
    """
    from pycurrents.data.seabird import CnvFile

    cf = CnvFile(fname)
    gmask = ~(np.ma.getmaskarray(cf.records['longitude']) |
            np.ma.getmaskarray(cf.records['latitude']))
    lon = np.ma.filled(cf.records['longitude'])[gmask]
    lat = np.ma.filled(cf.records['latitude'])[gmask]
    b = Bunch(dday=cf.dday[gmask], pressure=cf.pressure[gmask],
                longitude=lon,
                latitude=lat)
    return b


class CTD_flatfile:
    """
    Example CTD file reader.
    """
    def __init__(self, idday=None,
                       iseconds=None,
                        ipressure=None,
                        ilongitude=None, ilatitude=None,
                        ncolumns=None,
                        header_delims=None):
        self.idday = idday
        self.iseconds=iseconds
        self.ipressure = ipressure
        self.ilongitude = ilongitude
        self.ilatitude = ilatitude
        self.ncolumns = ncolumns
        self.header_delims = header_delims

    def __call__(self, fname, dday_down=None):
        f = open(fname, 'rb')
        if self.header_delims:
            while True:
                pos = f.tell()
                line = f.readline()
                line.strip()
                if line[0] not in self.header_delims:
                    break
            f.seek(pos)
        a = np.fromfile(f, dtype=float, sep=" ")
        a = np.reshape(a, (-1, self.ncolumns))

        self.a = a
        if self.idday is not None:
            itime = self.idday
        else:
            itime = self.iseconds
        self._delete_repeats(itime)

        pressure = self.a[:, self.ipressure]
        idown = np.nonzero(pressure == pressure.max())[0][0]
        if self.idday is not None:
            dday = self.a[:, self.idday]
        else:
            dday = self.a[:, self.iseconds] / 86400.0
            offset = dday_down - dday[idown]
            dday += offset

        b = Bunch(dday=dday,
                  pressure=pressure,
                  longitude=self.a[:, self.ilongitude],
                  latitude=self.a[:, self.ilatitude])
        return b

    def _delete_repeats(self, i):
        a = self.a
        bad = np.diff(a[:,i]) <= 0
        if bad.any():
            _log.info("Deleting %d repeated or backwards CTD times", bad.sum())
            cond = np.ones((a.shape[0],), dtype=bool)
            cond[1:] = ~bad
            self.a = np.compress(cond, a, axis=0)
            self._delete_repeats(i)


class Velocity:
    """
    Quick version of velocity calculation, initially without
    absolute estimate. Grid, editing, etc. are hardwired for now.

    This might be generalized to take a Profile instance as an
    alternative to the ladcp and ctd file names.

    Initialization executes a default version of the whole calculation.
    The summary result, for saving by save_mat and save_npz, is
    in the *profile* attribute.

    The instance is a callable; if called with keyword arguments,
    the calculation will be redone with those arguments updating
    the editparams.

    """
    editparams = Bunch(max_step=2,       # 1: require adjacent
                       i0=1,             # 1: skip depth cell 0
                       reflayer=[1,10],  # input to slice()
                       topnav=30,      #  depth of profile start, end for nav
                       top=5,          # depth of profile start, end for shear
                       outlier=0.2,    # max distance of velocity
                       top_bias=0.07,  # smoothed cell i0 deviation
                       top_bias_halfwidth=5, # bl_filt parameter
                       )
    wake_params = Bunch(method='angle',
                        angle=12,
                        start=5,
                        stop=60,
                        step=10)

    # Bottom track based on water track pings.
    btparams = Bunch(
                     std_clip=2.5,
                     min_ngood=20,
                     bump_thresh=55, # for bottom()
                     )


    def __init__(self, fname, sonar='wh',
                              lon=None,
                              lat=None,
                              dstart=0,
                              dz=0.25,
                              ndgrid=2000,
                              ctd_fname=None,
                              ctd_func=None,
                              badbeam=None,  # 1-based
                              editparams=None,
                              wake_params=None,
                              prof_editparams=None, # passed to Profile
                              btparams=None):  # empty or populated
                                               # dictionary to trigger
                                               # bt calculation
        """
        *editparams* must be a Bunch or other dictionary-like object.
        It may contain only keys that are already in the class default.

        *ctd_func* must be None or a callable following the pattern
        of *CTD_flatfile.__call__*.

        """
        self.fname = fname
        self.ctd_fname = ctd_fname

        if editparams is not None:
            self.editparams = Bunch(self.editparams)
            self.editparams.update_values(editparams, strict=True)
        _log.info("Velocity editparams: \n%s", self.editparams)

        if wake_params is not None:
            self.wake_params = Bunch(self.wake_params)
            self.wake_params.update_values(wake_params, strict=True)
        _log.info("Velocity wake_params: \n%s", self.wake_params)

        if prof_editparams is None:
            prof_editparams = {}
        self.prof_editparams = prof_editparams

        if btparams is not None:
            self.btparams =  Bunch(self.btparams)
            self.btparams.update_values(btparams, strict=True)
        else:
            self.btparams = None
        _log.info("Velocity btparams: \n%s", self.btparams)

        self.lon = lon
        self.lat = lat
        self.dstart = dstart # normally left at 0
        self.dz = dz
        self.ndgrid = ndgrid
        self.badbeam = badbeam
        self.dgrid = dstart + dz * np.arange(ndgrid)
                # Shearcalc is calculating this independently, so there
                # is some redundancy.

        self.prof = p = Profile(fname, in_water=True,
                                       sonar=sonar,
                                       defer=True,
                                       badbeam=badbeam,
                                       editparams=prof_editparams)
        self.dday = p.dday # for convenience
        self.flags = p.flags  # continue working with (nt, nd) Flags instance

        if p.have_p:
            _pressure = p.pressure
        else:
            _pressure = p.fake_pressure

        if ctd_fname is None:
            self.ctd = None
        else:
            if ctd_func is None:
                self.ctd = from_cnv(ctd_fname)
            else:
                idown = np.nonzero(_pressure == _pressure.max())[0][0]
                dday_down = self.dday[idown]
                self.ctd = ctd_func(ctd_fname, dday_down=dday_down)

            self.lat = self.ctd.latitude[0]
            self.lon = self.ctd.longitude[0]

        _log.info("lon, lat are %s, %s", self.lon, self.lat)

        # final profile calculations deferred so we can get lon, lat from ctd
        if self.lon is not None and self.lat is not None:
            p.lonlat = [self.lon, self.lat]
        p.calculate()
        # pressure_from_ctd requires wbar, so it must follow calculate()
        if ctd_fname is not None:
            _pressure = p.pressure_from_ctd(self.ctd.dday, self.ctd.pressure)
        press_lat = 0 if self.lat is None else self.lat
        package_depth = depth_from_p(_pressure, press_lat)
        self.package_depth = package_depth
        pdepth = p._get_relative_depths()
        pdepth += package_depth[:, np.newaxis]
        self.pdepth = pdepth

        self.__call__()

    def __call__(self, **kw):
        """
        Recalculate with editparams updated from the kwargs.

        FIXME: self.flags should be cleared first wherever the
        editing here is setting new values. The flags set by
        Profile, however, must remain.  We are not using __call__
        repeatedly in shearcalc, though, so this is not an
        immediate problem.
        """
        self.editparams.update_values(kw, strict=True)
        package_depth = self.package_depth
        p = self.prof
        dmax = package_depth.max()
        _log.info("Maximum package depth is %.0f m.", dmax)

        top = self.editparams.top
        topnav = self.editparams.topnav
        idown = np.nonzero(package_depth == dmax)[0][0]
        try:
            istart = np.nonzero(package_depth[:idown] < top)[0][-1]
        except IndexError:
            istart = 0
            _log.warning("Warning: starting package_depth is %s", package_depth[0])
        try:
            istop =  idown + np.nonzero(package_depth[idown:] < top)[0][0]
        except IndexError:
            istop = idown + np.nonzero(~np.ma.getmaskarray(
                                        package_depth[idown:]))[0].max() + 1
            _log.warning("Warning: ending package_depth is %s", package_depth[
                                                                istop-1])
        self.sldn = slice(istart,idown)
        self.slup = slice(idown, istop)
        # TODO: put in improved handling of all these start/stop indices
        try:
            inav0 = np.nonzero(package_depth[:idown] < topnav)[0][-1]
        except IndexError:
            inav0 = istart
            _log.warning("Warning: inav0 package_depth is %s", package_depth[inav0])

        try:
            inav1 = idown + np.nonzero(package_depth[idown:] < topnav)[0][0]
        except IndexError:
            inav1 = istop
            _log.warning("Warning: inav1 package_depth is %s",
                   package_depth[inav1 - 1])
        self.slnav = slice(inav0, inav1)

        grid_args = (self.dstart, self.dz, self.ndgrid, self.prof.NCells)
        self.scdown = unistat.Shearcalc(*grid_args)
        self.scup = unistat.Shearcalc(*grid_args)

        if self.btparams is not None:
            btslice = self.prof.find_btslice(package_depth, dmax)

            self.bt = self.prof.abs_bottom(self.dz, dstart = self.dstart,
                                           d_inst=package_depth,
                                           tslice=btslice,
                                           **self.btparams)

        mask = np.zeros((p.nprofs, p.NCells), dtype=bool)
        mask[:, :self.editparams.i0] = True
        self.flags.addmask(mask, "top_chop")

        if self.wake_params.method == 'angle':
            dots, vecamps = p.wake_beam_alignment(
                                self.wake_params.start,
                                self.wake_params.stop,
                                self.wake_params.step)
            badone, maxvals = p.wake_from_angle(dots,
                                self.wake_params.angle)
        else:  # temporary until supported in wake_params
            badone = p.wake_identify(1,12)[0]    # range is still hardwired
        enue = p.composite(badone)
        _log.info('wake profile counts by beam: %s', badone.sum(axis=0))
        enue.mask |= self.flags.tomask()[:, :, np.newaxis]

        # save the following for diagnostic purposes
        self.badone = badone
        self.enue_composite = enue
        self.devs = np.ma.zeros((p.nprofs, p.NCells, 3))

        self.down, self.up = self._downup(enue)
        self.devs[self.sldn] = self.mask_outliers(self.down, self.sldn)
        self.devs[self.slup] = self.mask_outliers(self.up, self.slup)

        self.down, self.up = self._downup(enue)

        umean, vmean = self.navigate(self.down, self.up)
        #if not self.nav.valid:
        #    L.warning("No navigation; setting umean, vmean to zero in profile.")
        #    umean, vmean = 0, 0
        self.umean = umean
        self.vmean = vmean

        self.profile = self.consolidate()


    def consolidate(self):
        """
        Make a Bunch with variables to be saved.
        """
        umean = self.umean
        vmean = self.vmean
        b = Bunch(depth=self.dgrid,
                  u_dn=self.down.u + umean,
                  v_dn=self.down.v + vmean,
                  w_dn=self.down.w,
                  n_dn=self.down.n,
                  u_up=self.up.u + umean,
                  v_up=self.up.v + vmean,
                  w_up=self.up.w,
                  n_up=self.up.n,
                  u = 0.5 * (self.down.u + self.up.u) + umean,
                  v = 0.5 * (self.down.v + self.up.v) + vmean,
                  n = self.down.n + self.up.n,
                  yearbase=self.prof.yearbase,
                  dday_start=self.dday[self.sldn.start],
                  dday_down=self.dday[self.sldn.stop - 1],
                  dday_up=self.dday[self.slup.stop - 1],
                  ladcp_fname = self.fname,
                  ctd_fname = "" if self.ctd_fname is None else self.ctd_fname,
                  profile_editparams=self.prof.editparams,
                  velocity_editparams=self.editparams,
                  wake_params=self.wake_params,
                  btparams=self.btparams,
                  )
        if self.nav.valid:
            b.update(dict(lon_start=self.nav.lons[0],
                          lon_end=self.nav.lons[1],
                          lat_start=self.nav.lats[0],
                          lat_end=self.nav.lats[1]))

        if self.btparams is not None:
            b.bt = self.bt

        return b

    def save_npz_old(self, filename):
        d = dict()
        for k, v in self.profile.items():
            if np.ma.isMA(v):
                d[k] = v.data
                d[k + "__mask"] = v.mask
            else:
                d[k] = v
        np.savez(filename, **d)

    def save_npz(self, filename):
        npzfile.savez(filename, **self.profile)

    def save_mat(self, filename):
        # avoid pulling in scipy unless we need it--hence the local import
        from pycurrents.file.matfile import savematbunch
        savematbunch(filename, self.profile)


    def mask_outliers(self, relvel, sl):
        """
        Remove overall profile outliers, and top points with
        evidence of bias.
        """

        devs, ngood = self.vel_dev(relvel, sl)
        devsq = (devs[:,:,:2]**2).sum(axis=-1)
        cond =  devsq > self.editparams.outlier**2
        self.flags.addmask(cond, "cell_outlier", index_obj=sl)
        _log.info("mask_outliers: removed %s outliers", cond.sum())

        # The modified mask is not being used in the following.
        # Maybe this is correct; the cell outliers could be at the top.
        itop = self.editparams.i0
        topdev, ww = bl_filt(devsq[:,itop], self.editparams.top_bias_halfwidth)
        cond = (topdev > self.editparams.top_bias**2)
        self.flags.addmask(cond, "top_outlier", index_obj=(sl, itop))
        _log.info("mask_outliers: top_bias removed top from %s profiles",
                cond.sum())

        return devs

    def _downup(self, enue):
        sldn, slup = self.sldn, self.slup
        mask = self.flags.tomask()

        self.scdown.clear()
        self.scdown(enue[sldn], mask[sldn], self.pdepth[sldn],
                    self.editparams.max_step)
        down = self._relvel(self.scdown)

        self.scup.clear()
        self.scup(enue[slup], mask[slup], self.pdepth[slup],
                    self.editparams.max_step)
        up = self._relvel(self.scup)

        self.enue = enue # save the most recent version; not sure
                         # if this is good, so may be temporary
                         # It's useful for integrate_flow_past.
                         # Also used in vel_dev.
        return down, up

    def fourbeam(self):
        return self._downup(self.prof.enue)

    def threebeam(self, ibad):
        enue = self.prof.to_enue(ibad=ibad, replace=False)
        return self._downup(enue)

    def _relvel(self, sc):
        """
        Vertically integrate the shear and remove its vertical mean.
        """
        n = np.ma.masked_equal(sc.ustat.npts, 0)
        ush = np.ma.divide(sc.ustat.sum, n)
        vsh = np.ma.divide(sc.vstat.sum, n)
        wsh = np.ma.divide(sc.wstat.sum, n)
        uvw = np.ma.zeros((sc.ndgrid, 3), np.float64)
        uvw[:,0] = ush.cumsum() * self.dz
        uvw[:,1] = vsh.cumsum() * self.dz
        uvw[:,2] = wsh.cumsum() * self.dz
        uvw -= uvw.mean(axis=0)           # needs a depth range slice
        return Bunch(uvw=uvw, u=uvw[:,0], v=uvw[:,1], w=uvw[:,2], n=n)

    def integrate_flow_past(self, enue=None):
        if enue is None:
            enue = self.enue
        dslice = slice(*self.editparams.reflayer)

        uvw_bar = enue[:, dslice, :3].mean(axis=1)

        # For this crude integration, we are still assigning each
        # velocity to the time interval between it and the previous
        # sample.
        dt = np.zeros_like(self.dday)
        dt[1:] = np.diff(self.dday) * 86400
        xyz = np.ma.zeros((dt.size, 3), dtype=float)
        # fillmasked is restricted to simple linear interpolation
        # and to 1-D arrays.  The result is still masked; there is
        # no extrapolation.
        xyz[:,0] = (fillmasked(uvw_bar[:,0]) * dt).cumsum()
        xyz[:,1] = (fillmasked(uvw_bar[:,1]) * dt).cumsum()
        xyz[:,2] = (fillmasked(uvw_bar[:,2]) * dt).cumsum()
        return xyz

    def integrate_uprime(self, u, v):
        """
        u, and v constitute a vertically de-meaned ladcp profile as
        a function of self.dgrid.
        They are input here as variables so that they can be from
        upcast, downcast, or an average.
        """
        dslice = slice(*self.editparams.reflayer)
        d_mid = self.prof.dep[dslice].mean()
        uprime = interp1(self.dgrid, u, self.package_depth + d_mid)
        vprime = interp1(self.dgrid, v, self.package_depth + d_mid)
        dt = np.zeros_like(self.dday)
        dt[1:] = np.diff(self.dday) * 86400
        xy = np.ma.zeros((dt.size, 2), dtype=float)
        xy[:,0] = (fillmasked(uprime) * dt).cumsum()
        xy[:,1] = (fillmasked(vprime) * dt).cumsum()
        return xy

    def navigate(self, down, up):
        """
        First quick shot at calculation of absolute.
        Hardwired for lat, lon in CTD file.
        """
        istartstop = [self.slnav.start, self.slnav.stop - 1]
        t0, t1 = self.dday[istartstop]
        dt = (t1 - t0) * 86400

        xyz_past = self.integrate_flow_past()
        u_past = np.diff(xyz_past[istartstop, 0])[0] / dt
        v_past = np.diff(xyz_past[istartstop, 1])[0] / dt


        u = 0.5 * (down.u + up.u)
        v = 0.5 * (down.v + up.v)
        xy_rel = self.integrate_uprime(u, v)
        u_rel, v_rel = np.diff(xy_rel[istartstop], axis=0)[0] / dt

        # We may later stop assuming positions come
        # from the CTD file, but it is convenient for now.
        if self.ctd is None:
            _log.warning("No navigation; setting ship_u, ship_v to zero.")
            ship_u = ship_v = 0
            valid = False
        else:
            overhang = (t1 - self.ctd.dday[-1]) * 86400
            delay = (self.ctd.dday[0] - t0) * 86400
            if  delay > 20.0:
                _log.warning("CTD starts %s seconds after LADCP", delay)
            if  overhang > 20.0:
                _log.warning("CTD ends %s seconds before LADCP", overhang)
            i0 = np.searchsorted(self.ctd.dday, t0)
            i1 = np.searchsorted(self.ctd.dday, t1)
            i1 = min(len(self.ctd.dday) - 1, i1)
            ddays = self.ctd.dday[[i0, i1]]
            lons = self.ctd.longitude[[i0, i1]]
            lats = self.ctd.latitude[[i0, i1]]

            ship_u, ship_v = uv_from_txy(ddays, lons, lats  , pad=False)
            ship_u = ship_u[0]
            ship_v = ship_v[0]
            valid = True

        umean = ship_u + u_past - u_rel
        vmean = ship_v + v_past - v_rel

        _log.info("ship_u = %5.2f,  u_past = %5.2f,  u_rel = %5.2f,  umean = %5.2f\n"
               "ship_v = %5.2f,  v_past = %5.2f,  v_rel = %5.2f,  vmean = %5.2f",
                ship_u, u_past, u_rel, umean,
                ship_v, v_past, v_rel, vmean)

        self.nav = Bunch(umean=umean,
                         vmean=vmean,
                         ship_u=ship_u,
                         ship_v=ship_v,
                         u_past=u_past,
                         v_past=v_past,
                         u_rel=u_rel,
                         v_rel=v_rel,
                         t0=t0,
                         t1=t1,
                         valid=valid,)
        if valid:
            self.nav.update(dict(ddays=ddays,
                                 lons=lons,
                                 lats=lats))
        return umean, vmean

    def vel_dev(self, relvel, sl):
        """
        Deviations of pings from the composite profile, after
        matching their vertical mean over their overlapping
        depth range.

        Wrapper for unistat.velocity_deviation.
        """
        enue = self.enue[sl]
        mask = self.flags.tomask().astype(np.uint8)  # cython: no bool
        devs, ngood = unistat.velocity_deviation(enue, mask[sl],
                       self.pdepth[sl],
                       relvel.uvw.filled(np.nan),
                       relvel.n,
                       self.dstart, self.dz, self.ndgrid)

        devsm = np.ma.masked_invalid(devs)
        devsm = np.ma.masked_equal(devsm, 0)
        return devsm, ngood

def read_npz(filename):
    """
    Load an npz file written by Velocity.save_npz().
    This rebuilds masked arrays and converts array scalars
    to ordinary python scalars.

    It also reads everything and closes the file so that we
    don't end up with too many open files.

    This is obsolete, and useful only for reading npz files
    written before the npzfile.savez was being used.
    """
    xf = open(filename, 'rb')
    x = np.load(xf)
    b = Bunch()
    for k in x.keys():
        if k.endswith("__mask"):
            continue
        km = k + "__mask"
        if km in x:
            var = np.ma.array(x[k], mask=x[km])
            b[k] = var
        else:
            var = x[k]
            if var.ndim == 0:
                if var.dtype.kind == 'i':
                    var = int(var)
                elif var.dtype.kind == 'f':
                    var = float(var)
            else:
                var = np.array(var)
            b[k] = var
    xf.close()
    return b

def plot_ladcp(b, title=None,
               maxdepth=None,
               parts=["down", "up", "mean"],
               velrange=None,):
    """
    Basic plot of Velocity results.

    The first argument is the Bunch stored as the Velocity.profile, or
    as loaded by read_npz().
    """
    import matplotlib.pyplot as plt

    legendkw = dict(#frameon=False,
                    prop=dict(size=10),
                    loc='lower right',
                    )
    fig, axs = plt.subplots(2, 2, sharey=True, figsize=(6, 8))

    showdown = "down" in parts
    showup = "up" in parts
    showmean = "mean" in parts

    if title is None:
        title = os.path.split(b.ladcp_fname)[-1]
        if b.ctd_fname:
            title = "%s, %s" % (title, os.path.split(b.ctd_fname)[-1])

    if velrange is None:
        velrange = [-1, 1]

    ax = axs[0,0]
    if showdown:
        ax.plot(b.u_dn, b.depth, label='down')
    if showup:
        ax.plot(b.u_up, b.depth, label='up')
    if showmean:
        ax.plot(b.u, b.depth, label='mean')
    if "bt" in b:
        ax.plot(b.bt.u, b.bt.dep, label='bt')
        ax.axhline(b.bt.d_median, lw=2, color='brown')
    ax.set_title('U (m s$^{-1}$)')
    #ax.legend(**legendkw)

    ax = axs[0,1]
    if showdown:
        ax.plot(b.v_dn, b.depth, label='down')
    if showup:
        ax.plot(b.v_up, b.depth, label='up')
    if showmean:
        ax.plot(b.v, b.depth, label='mean')
    if "bt" in b:
        ax.plot(b.bt.v, b.bt.dep, label='bt')
        ax.axhline(b.bt.d_median, lw=2, color='brown')
    ax.set_title('V (m s$^{-1}$)')
    ax.legend(**legendkw)

    ax = axs[1,0]
    davg = 0.5 * (b.depth[:-1] + b.depth[1:])
    dz = - np.diff(b.depth)  # converted to z positive up
    if showdown:
        du = np.diff(b.u_dn)
        dv = np.diff(b.v_dn)
        sh = np.ma.sqrt((du/dz)**2 + (dv/dz)**2)
        ax.plot(sh, davg, label='down')
    if showup:
        du = np.diff(b.u_up)
        dv = np.diff(b.v_up)
        sh = np.ma.sqrt((du/dz)**2 + (dv/dz)**2)
        ax.plot(sh, davg, label='up')
    if showmean:
        du = np.diff(b.u)
        dv = np.diff(b.v)
        sh = np.ma.sqrt((du/dz)**2 + (dv/dz)**2)
        ax.plot(sh, davg, label='mean')
    ax.set_title('Shear (s$^{-1}$)')
    #ax.legend(**legendkw)

    ax = axs[1,1]
    if showdown:
        ax.plot(b.n_dn, b.depth, label='down')
    if showup:
        ax.plot(b.n_up, b.depth, label='up')
    if showmean:
        ax.plot(b.n, b.depth, label='mean')
    ax.set_title('Samples')
    ax.legend(**legendkw)

    if maxdepth is None:
        ax.invert_yaxis()
        ax.set_ylim(top=0)
    else:
        ax.set_ylim(maxdepth, 0)

    ax.locator_params(axis='y', nbins=5)

    axs[0,0].set_xlim(*velrange)
    axs[0,1].set_xlim(*velrange)
    axs[1,0].set_xlim(0, 0.06)
    axs[1,1].set_xlim(0, 600)

    for ax in axs.flat:
        ax.locator_params(axis='x', nbins=5)
        ax.grid(True)

    fig.suptitle(title, fontsize=14)

    try:
        pos = "%s, %s" % (LonFormatter(round=2)(b.lon_start),
                            LatFormatter(round=2)(b.lat_start))
    except AttributeError:
        pos = ""
    datestr = to_datestring(b.yearbase, b.dday_start)
    if pos:
        time_position = pos + ", " + datestr
    else:
        time_position = datestr

    fig.text(0.5, 0.02, time_position, ha='center', va='bottom')

    return fig


def beamhist(p):
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(2,2,sharex=True, sharey=True, figsize=(6, 8))
    for i, ax in enumerate(axs.flat):
        v = p.vel[:,:,i].compressed()
        ax.hist(v, 50, density=True, cumulative=False)
        txt = "Beam %d\n" % (i + 1)
        txt += "%.2f to %.2f" % (v.min(), v.max())
        ax.text(0.05, 0.95, txt,
                ha="left", va="top",
                transform=ax.transAxes,
                bbox=dict(boxstyle="round",
                          facecolor='lemonchiffon'),
                )

    ax.set_ylim(0,1)
    ax.set_xlim(v.min(), v.max())
    ax.locator_params(nbins=5)
    plt.draw_if_interactive()
    return fig

def plot_PTCV(p):
    """
    Plot pressure, temperature, current, voltage.

    Quick transfer of code from the original plot_PTCV.py.
    """
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(6,7.5), dpi=120)
    plt.subplots_adjust(hspace=0.05, top=0.95, left=0.15, bottom=0.07)

    ax1 = fig.add_subplot(4,1,1)
    ax1.plot(p.ens_num, p.pressure)
    ax1.set_ylabel('pressure')
    ax1.set_title(p.fname)

    ax2 = fig.add_subplot(4,1,2, sharex=ax1)
    ax2.plot(p.ens_num, p.temperature)
    ax2.set_ylabel('temperature')
    ax2.ticklabel_format(useOffset=False)

    ax3 = fig.add_subplot(4,1,3, sharex=ax1)
    ax3.plot(p.ens_num, p.voltage)
    ax3.set_ylabel('voltage')

    ax4 = fig.add_subplot(4,1,4, sharex=ax1)
    ax4.plot(p.ens_num, p.current)
    ax4.set_ylabel('current')
    ax4.set_xlabel('Ping number')

    for ax in [ax1, ax2, ax3]:
        plt.setp(ax.get_xticklabels(), visible=False)
    return fig

def _y_label_color(lineobj, label, linecolors):
    color = linecolors[label]
    ax = lineobj.axes
    lineobj.set_color(color)
    ax.set_ylabel(label, color=color)
    ax.tick_params(axis='y', colors=color)

def _xvar(p, xvar):
    if xvar == "dday":
        x = p.dday
        xlabel = "%d Decimal day" % p.yearbase
    elif xvar == "ens_num":
        x = p.ens_num
        xlabel = "Ping number"
    else:
        raise ValueError(
            "xvar is %s; valid values are 'dday' and 'ens_num'" % xvar)
    return x, xlabel

def plot_scalars(p, xvar="dday"):
    """
    Plot pressure, temperature, heading, pitch, roll, voltage, current.

    *xvar* can be "dday" (default) or "ens_num"
    """
    import matplotlib.pyplot as plt

    x, xlabel = _xvar(p, xvar)

    linecolors = dict(pressure='b',
                      temperature='r',
                      heading='b',
                      pitch='b',
                      roll='r',
                      voltage='b',
                      current='r',
                      )


    fig, axs = plt.subplots(4, sharex=True, figsize=(6, 7.5))
    fig.subplots_adjust(left=0.14, right=0.86)
    ax_rh = []
    ax = axs[0]
    line_pr, = ax.plot(x, p.pressure)
    ax.invert_yaxis()
    ax.set_ylim(top=-20)
    _y_label_color(line_pr, 'pressure', linecolors)
    axt = ax.twinx()
    ax_rh.append(axt)
    axt.yaxis.grid(True, color=linecolors['temperature'])
    line_t, = axt.plot(x, p.temperature)
    _y_label_color(line_t, 'temperature', linecolors)

    ax = axs[1]
    line_h, = ax.plot(x, p.heading, '.', ms=2)
    ax.set_ylim(0, 360)
    _y_label_color(line_h, 'heading', linecolors)
    ax.set_yticks([0, 90, 180, 270, 360])

    ax = axs[2]
    line_pi, = ax.plot(x, p.pitch, label="pitch")
    ax.set_ylabel('pitch', color='b')
    _y_label_color(line_pi, 'pitch', linecolors)
    axr = fig.add_axes(ax.get_position(True), sharex=ax, sharey=ax)
    axr.yaxis.set_label_position('right')
    axr.yaxis.set_offset_position('right')
    axr.yaxis.tick_right()
    axr.xaxis.set_visible(False)
    axr.patch.set_visible(False)
    axr.grid(False)
    line_r, = axr.plot(x, p.roll, 'r', label="roll")
    _y_label_color(line_r, 'roll', linecolors)

    ax = axs[3]
    line_v, = ax.plot(x[1:-1], p.voltage[1:-1])
    _y_label_color(line_v, 'voltage', linecolors)
    axc = ax.twinx()
    axc.grid(True, color='r')
    ax_rh.append(axc)
    line_c, = axc.plot(x[1:-1], p.current[1:-1])
    _y_label_color(line_c, 'current', linecolors)

    ax.set_xlabel(xlabel)

    for ax in axs[:-1]:
        plt.setp(ax.get_xticklabels(), visible=False)

    for i in [0,2,3]:
        axs[i].locator_params(nbins=4, axis='y')
    for ax in ax_rh:
        ax.locator_params(nbins=4, axis='y')

    for ax in axs:
        ax.grid(True)
        ax.yaxis.grid(True, color='b')
        ax.ticklabel_format(useOffset=False)

    ax.autoscale_view(tight=True, scaley=False)

    fig.suptitle(p.title)
    return fig

def _x_bdry(p, x):
    ensbdry = np.empty((p.nprofs + 1,), dtype=float)
    dx = x[1] - x[0]
    ensbdry[:-1] = x - 0.5 * dx
    ensbdry[-1] = x[-1] + 0.5 * dx
    return ensbdry

def plot_beamvel(p, vmin, vmax, xvar="dday"):
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    x, xlabel = _xvar(p, xvar)

    ensbdry = _x_bdry(p, x)
    binbdry = np.arange(p.NCells + 1)

    #velcmap = mpl.cm.get_cmap('RdYlBu_r')
    velcmap = get_extcmap('ob_vel')
    velcmap.set_bad(color='0.5', alpha=1.0)
    #velcmap.set_under('k')
    #velcmap.set_over('k')

    velnorm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

    fig, axes = plt.subplots(nrows=4, sharex=True, sharey=True,
                                 figsize=(6,7.5))
    plt.subplots_adjust(hspace=0.05, top=0.95, left=0.1,
                                        right=0.85, bottom=0.07)
    cax = fig.add_axes([0.87, 0.3, 0.02, 0.4])

    images = []
    labels = ["Beam 1", "Beam 2", "Beam 3", "Beam 4"]
    for i, (ax, label) in enumerate(zip(axes, labels)):
        ax.ticklabel_format(useOffset=False)
        im = ax.pcolorfast(ensbdry, binbdry, p.vel[:,:,i].T,
                                    cmap=velcmap, norm=velnorm)
        images.append(im)
        ax.text(0.02, 0.05, label, transform=ax.transAxes,
                fontsize='small',
                bbox=dict(color='w', alpha=0.6))

    axes[0].set_title(p.fname)

    if not p.sysconfig['up']:
        axes[0].invert_yaxis()

    for ax in axes:
        ax.set_ylabel('bin')
    ax.locator_params(axis='y', nbins=4, prune='upper')

    axes[3].set_xlabel(xlabel)

    cbloc = mpl.ticker.MaxNLocator(nbins=8)
    cb = fig.colorbar(images[0], cax, extend='both', ticks=cbloc)
    cb.set_label('m/s')
    return fig

# TODO: refactor; this is almost identical to plot_beamvel
def plot_vel(p, vmin, vmax, xvar='dday'):
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    x, xlabel = _xvar(p, xvar)

    ensbdry = _x_bdry(p, x)
    binbdry = np.arange(p.NCells + 1)

    velcmap = get_extcmap('ob_vel')
    velcmap.set_bad(color='0.5', alpha=1.0)
    #velcmap.set_under('k')
    #velcmap.set_over('k')

    velnorm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
    elim = 300 * np.ma.abs(p.e).std()   # to cm/s
    enorm = mpl.colors.Normalize(vmin=-elim, vmax=elim)
    wlim = 3 * np.ma.abs(p.w).std()
    wnorm = mpl.colors.Normalize(vmin=-wlim, vmax=wlim)

    norms = [velnorm, velnorm, wnorm, enorm]

    fig, axes = plt.subplots(nrows=4, sharex=True, sharey=True,
                            figsize=(6,7.5))
    plt.subplots_adjust(hspace=0.05, top=0.95, left=0.1,
                                        right=0.85, bottom=0.07)
    caxu = fig.add_axes([0.87, 0.6, 0.02, 0.3])
    caxw = fig.add_axes([0.87, 0.3, 0.02, 0.18])
    caxe = fig.add_axes([0.87, 0.1, 0.019, 0.18])

    images = []
    for i, (ax, varletter) in enumerate(zip(axes, 'UVWE')):
        ax.ticklabel_format(useOffset=False)
        c = p.enue[:,:,i].copy()
        if i == 3:
            c *= 100  # put e in cm/s
        im = ax.pcolorfast(ensbdry, binbdry, c.T,
                                    cmap=velcmap, norm=norms[i])
        images.append(im)
        ax.text(0.02, 0.05, varletter, transform=ax.transAxes,
                fontsize='small',
                bbox=dict(color='w', alpha=0.6))

    axes[0].set_title(p.fname)

    if not p.sysconfig['up']:
        axes[0].invert_yaxis()

    for ax in axes:
        ax.set_ylabel('bin')
    ax.locator_params(axis='y', nbins=4, prune='upper')

    axes[3].set_xlabel(xlabel)

    cax_info = ((caxu, images[0], 'm/s'),
                (caxw, images[2], 'm/s'),
                (caxe, images[3], 'cm/s'))
    for cax, im, label in cax_info:
        cbloc = mpl.ticker.MaxNLocator(nbins=6)
        cb = fig.colorbar(im, cax, extend='both', ticks=cbloc)
        cb.set_label(label)

    return fig

# TODO: propagate the xvar kwarg to the functions below.
def plot_onebeam(p, beam):
    """
    Exploration of one beam at a time.
    """
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    binbdry = np.arange(p.NCells + 1)
    ensbdry = np.empty((p.nprofs + 1,), dtype=np.uint)
    ensbdry[:-1] = p.ens_num - 0.5
    ensbdry[-1] = p.ens_num[-1] + 0.5

    velcmap = get_extcmap('ob_vel')
    velcmap.set_bad(color='0.5', alpha=1.0)
    #velcmap.set_under('k')
    #velcmap.set_over('k')

    hotcmap = get_extcmap('hot')

    velnorm = mpl.colors.Normalize(vmin=-2, vmax=2)
    vdevnorm = mpl.colors.Normalize(vmin=-0.1, vmax=0.1)
    ampnorm = mpl.colors.Normalize(vmin=20, vmax=160)
    cornorm = mpl.colors.Normalize(vmin=60, vmax=120)

    norms = [velnorm, vdevnorm, ampnorm, cornorm]
    cmaps = [velcmap, velcmap, hotcmap, hotcmap]
    i = beam
    fields = [p.vel[:,:,i],
              p.vel[:,:,i] - p.vel[:,:,i].mean(axis=-1)[:, np.newaxis],
              p.amp[:,:,i],
              p.cor[:,:,i]]

    fig = plt.figure(figsize=(6,7.5), dpi=120)
    plt.subplots_adjust(hspace=0.05, top=0.95, left=0.1,
                                        right=0.85, bottom=0.07)

    images = []
    axes = []
    shkw = {}
    cbars = []
    for i in range(4):
        ax = fig.add_subplot(4,1,i+1, **shkw)
        im = ax.pcolorfast(ensbdry, binbdry, fields[i].T,
                                    cmap=cmaps[i], norm=norms[i])
        images.append(im)
        axes.append(ax)
        if i==0:
            shkw = {'sharex':axes[0], 'sharey':axes[0]}
        cbars.append(fig.colorbar(im, ax=ax, shrink=0.9,
                                   extend='both',
                                   use_gridspec=True,
                                   ticks=mpl.ticker.MaxNLocator(nbins=5)))
        ax.locator_params(nbins=5)
        ax.ticklabel_format(useOffset=False)
    axes[0].set_title(p.fname)

    if not p.sysconfig['up']:
        axes[0].invert_yaxis()

    for ax in axes:
        ax.set_ylabel('bin')

    axes[3].set_xlabel('ping')
    for ax in axes[:-1]:
        plt.setp(ax.get_xticklabels(), visible=False)

    return fig

def beam_amp_cor_profile(p, n=101, goodcor=65):
    """
    Plot 4 panels with beam amplitude and correlation diagnostics.

    *p* is a Profile instance
    *n* must be an odd integer; it is the length of the Runstats window.
    *goodcor* is the correlation threshold for counting nominally "good"
    velocity estimates.

    """
    import matplotlib.pyplot as plt

    rp = runstats.Runstats(p.pressure, n)
    ncor = (p.cor > goodcor).sum(axis=1)
    rc = runstats.Runstats(ncor, n, axis=0)
    atop = p.amp[:, 1:6].mean(axis=1)
    abot = p.amp[:, -6:-1].min(axis=1)
    #atop = p.amp[:, 1, :]
    #abot = p.amp[:, -1, :]
    ratop = runstats.Runstats(atop, n, axis=0)
    rabot = runstats.Runstats(abot, n, axis=0)

    fig, axs = plt.subplots(2, 2, sharey='all', figsize=(7, 9))
    fig.suptitle(p.title)

    goodp = np.nonzero(rp.min > 20)[0]
    if len(goodp) < 100:
        _log.warning("Too few points (%s) with pressure > 20." % len(goodp))
        return fig

    psl = slice(goodp[0], goodp[-1], n)
    pvals = rp.mean[psl][:, np.newaxis]

    ax = axs[0,0]
    lines = ax.plot(ratop.mean[psl], pvals)
    #ax.set_xlim(left=ratop.mean[psl][:10].min())
    ax.set_xlabel("amp[1:6] mean")
    ax.legend(lines, ('1', '2', '3', '4'), loc='lower right', title='beam')


    ax = axs[0,1]
    ax.plot(rabot.mean[psl], pvals)
    ax.set_xlim(right=rabot.mean[psl][:10].max())
    ax.set_xlabel("amp[-6:-1] min")

    ax = axs[1,0]
    ax.plot(ratop.mean[psl] - rabot.mean[psl], pvals)
    ax.set_xlim(left=20)
    ax.set_xlabel("Amp, near minus far")

    ax = axs[1,1]
    ax.plot(rc.mean[psl], pvals)
    ax.set_xlabel("N bins, cor > %s" % goodcor)

    ax.set_ylim(6000, 0)

    for ax in axs.flat:
        ax.grid(True)

    return fig

def e_range_stats(prof_or_vel, step=10):
    """
    Diagnostics of range and accuracy as a function of instrument
    depth.

    *prof_or_vel* is a Profile or Velocity instance

    *step* is the depth bin size as a multiple of the cell size.
    For example if *step* is 10 and the cell size is 8 m, the
    depth grid will be at 80-m intervals.

    Statistics are collected for profiles binned in an instrument
    depth grid with boundaries *z_bounds*, centered on *z* (both
    positive down).

    *e_std* and *e_num* are (n_zbins, NCells) arrays with the
    standard deviation of the error velocity and the corresponding
    number of samples.

    *med_nbins* is a (n_zbins, 4) array with the median number of
    valid velocities in each beam.

    *med_ebins* is a (n_zbins) array with the median number of
    4-beam solutions (or error velocities).

    *nprofs* is the number of profiles
    """
    if hasattr(prof_or_vel, "prof"): #isinstance(prof_or_vel, Velocity):
        prof = prof_or_vel.prof
        z = prof_or_vel.package_depth
        e_vel = prof_or_vel.enue_composite[..., 3]
    else:
        prof = prof_or_vel
        z = prof.pressure  # or allow for fake_pressure if necessary later
        e_vel = prof.enue[..., 3]
    vel = prof.vel

    dz = np.round(step * prof.CellSize)
    z_bounds = np.arange(10, z.max(), dz)
    zgrid = np.arange(10 + dz / 2, z_bounds.max(), dz)
    n_zbins = len(z_bounds) - 1
    e_std = np.ma.zeros((n_zbins, prof.NCells), float)
    e_num = np.ma.zeros((n_zbins, prof.NCells), np.int16)

    med_nbins = np.zeros((n_zbins, 4), np.int8)
    med_ebins = np.zeros((n_zbins,), np.int8)
    nprofs = np.zeros((n_zbins,), np.int64)

    for i in range(n_zbins):
        iz = (z >= z_bounds[i]) & (z < z_bounds[i+1])
        nprofs[i] = iz.sum()
        e_std[i] = e_vel[iz].std(axis=0)
        e_num[i] = e_vel[iz].count(axis=0)
        med_nbins[i] = np.median(vel[iz].count(axis=1), axis=0)
        med_ebins[i] = np.median(e_vel[iz].count(axis=1))

    return Bunch(z=zgrid,
                 z_bounds=z_bounds,
                 e_std=e_std,
                 e_num=e_num,
                 med_nbins=med_nbins,
                 med_ebins=med_ebins,
                 nprofs=nprofs)
