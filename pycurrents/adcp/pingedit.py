'''
Functions and classes involved in editing.

Most of the code here is used in editing after ensemble averaging,
but some is used at the single-ping stage as well.

independent functions:
    pg_from_mask, slidemask, mask_below
classes
   BottomEdit
   ThresholdEdit
   ProfileEdit
   CODAS_AutoEditor

'''

import os
import logging
import numpy as np
import string

from pycurrents.codas import to_date, to_datestring
from pycurrents.num import Runstats, Stats
from pycurrents.codas import get_profiles         # general codasdb reader
from pycurrents.num.nptools import Flags
from pycurrents.adcp._bottombounce import bump_coeff
from pycurrents.system.misc import Bunch, Cachefile

# Standard logging
_log = logging.getLogger(__name__)

np.seterr(all='ignore')   #FIXME: this is probably masking bad code

openstyle_dict = dict(a='appended', w='wrote')

# class          called by
#BottomEdit     pycurrents/adcpgui_qt/model/codas_data_models.py
#ThresholdEdit  pycurrents/adcpgui_qt/model/codas_data_models.py
#ProfileEdit    pycurrents/adcpgui_qt/model/codas_data_models.py

# BottomEdit    pycurrents/adcp/pingavg.py
# Single-ping thresholds and weak profile editing are done in pingavg.py
#---------------------------------


edit_names = [
    'bottom',            # bottom or maxampbin
# bad scattered bins
    'ecutoff',                # errvel cutoff
    'e_std_cutoff',             # errvel std cutoff
    'wcutoff',                # bad 'w'
    'pgcutoff',               # pg cutoff
    'wire',                   # bad errvel in refl on station
    'trimtopbins',            # trim top bins
    'topbins_pgcutoff',       # bad pg near top
    'topbins_corcutoff',      # bad cor near top
    'resid_std'               # using residual stddev (singleping)
# bad profiles
    'badpg_refl',             # bad refl means bad profile
    'friendless',             # neighbors
    'jittery',                # high jitter
    'fastship',               # underway
    'toofewpings',            # too few pings, eg. triggered
    # manual editing
    'zapbins',                # manually-selected region
    'badtimes',               # manual:bad profiles
]

#---------

def slidemask(mask, numslide=1, axis=1):
    '''
    push out the effect of a mask along axis, numslide on each side
    return new mask
    by default, axis=1 means "slide along bins" if array is nprofs x nbins


    ** test and clean if necessary **
    '''

    if numslide == 0:
        return mask

    if len(mask.shape) == 1:
        mask = mask[np.newaxis,:]
        axis = -1

    if axis == 0:
        mask=mask.T

    nprofs, nbins = mask.shape
    numslide = min(int(numslide), nbins)

    dm = mask.copy()

    for ss in range(numslide):
        slide=ss+1
        dm[:,0:nbins-slide] = dm[:,0:nbins-slide] | mask[:,slide:]

        # slide deeper
        dm[:,slide:] = dm[:,slide:] | dm[:,0:nbins-slide]

    if axis == -1:
        return dm[0,:]
    elif axis == 0:
        return dm.T
    else:
        return dm

#------
def get_jitter(data, pmask=None, mask=None, refsl=None, nwin = 5):
    '''
    Old algorithm to estimate jumpiness in reference layer ocean velocity.

    After initial editing, calculate the deviation of the velocity
    in each bin from the running median, and then return the 100 times
    the square root of the sum of the mean squared deviations of
    U and V, where the mean is over the cells in the reference layer.

    Parameters
    ----------
    data : Bunch
        Contains `u` and `v` 2-D masked arrays, (nprofs, nbins)
    pmask : Boolean array, optional
        1-D array, (nprofs,) True where a profile is rejected
    mask : Boolean array, optional
        2-D array, (nprofs, nbins) True where a bin is rejected
    refsl : slice, optional
        reference layer slice; default is None to use all bins
    nwin : odd int, optional
        width of median filter; default is 5

    Returns
    -------
    masked array
        1-D (nprofs,) float array of the 'jitter' values.

    Notes
    -----
    We view this as of questionable value in editing a database
    created with Python processing.
    It is more useful for databases generated with the Matlab
    version of CODAS processing.

    '''

    if refsl is None:
        refsl = slice(0, data.nbins)
    # Quick Fix: adding .copy() prevent from mutating data.vars' masks
    newmask = np.ma.getmaskarray(data.u).copy()
    if mask is not None:
        newmask |= mask
    if pmask is not None:
        newmask |= pmask[:, np.newaxis]


    u = np.ma.array(data.u, mask=newmask)
    v = np.ma.array(data.v, mask=newmask)


    udev = u[:, refsl] - Runstats(u[:, refsl], nwin, axis=0).median
    vdev = v[:, refsl] - Runstats(v[:, refsl], nwin, axis=0).median

    Su = Stats(udev, axis=1)
    Sv = Stats(vdev, axis=1)

    jitter = 100 * np.ma.sqrt(Su.mean*Su.mean + Sv.mean*Sv.mean)

    # If there is a single profile, Stats returns a scalar; we
    # need an array for later use.

    return np.atleast_1d(jitter)

#------

def mask_below(bindepth, bottom, beamangle):
    '''
    return mask for "below bottom" including side-lobe effect
    bindepth: 1-d array (nbins,) or 2-d array (nprofs, nbins) of depths
    bottom: 1-d masked array, (nprofs,)

    (No fudge-factor offset is present.)
    '''

    _log.debug('bindepth, bottom, beamangle: %s, %s, %s', bindepth, bottom, beamangle)

    sidelobe = np.cos(np.pi*beamangle/180.0)*bottom
    output = (bindepth > sidelobe[:, np.newaxis])
    return output


#=======================

# make these plain-old-functions so gautoedit can call them too

def write_mab(dday, yearbase, mab, outfile=None, openstyle='a'):
    '''
    write (append) to a file or stdout, the lines for abottom.asc
    kwarg 'openstyle' is 'w' or 'a'
    dday is assumed to match mab (maxampbins)
    mab is a possibly-masked sequence of zero-based bin numbers

    '''
    s = string.Template(
        '0    0   0    $datestr A    32767    $mabprint  $mabprint')
    slist = []


    mab = np.ma.atleast_1d(mab)
    if mab.count() == 0:
        return

    mask = np.ma.getmaskarray(mab)
    dday = np.atleast_1d(dday)[~mask]
    mab = mab.compressed()

    for day, mm in zip(dday, mab):
        datestr = to_datestring(yearbase, day)
        slist.append(s.substitute(datestr=datestr, mabprint=mm+1))
    slist.append('')

    if outfile is None:
        _log.debug('%s', '\n'.join(slist))
    else:
        with open(outfile, openstyle) as file:
            file.write('\n'.join(slist))
        _log.debug('%s %d max_amp_bin to %s' % (openstyle_dict[openstyle],
                                                len(slist)-1, outfile))


def write_badbins(dday, yearbase, edit_names, cflags,
                  outfile=None, openstyle='a'):
    '''
    write (append) to a file or stdout, the lines for abadbin.asc
    kwarg 'open' is 'w' or 'a'
    len(dday) = nprofs ; mask is boolean, nprofs x nbins;
    yearbase is required
    '''
    s = string.Template(
        '$datestr   0  0  $numbins  $badbinstr')
    slist = []

    # write badbins for all flags except percent good
    bbflag=Flags(flags=cflags.tomask(edit_names), names=['badbin'])

    for iprof in np.arange(len(dday)):
        badbins = np.where(bbflag.tomask('all')[iprof,:])[0]
        numbins = len(badbins)
        if numbins > 0:
            dlist = to_date(yearbase, dday[iprof])
            datestr = '%4d/%02d/%02d  %02d:%02d:%02d' % (
                dlist[0], dlist[1], dlist[2], dlist[3], dlist[4], dlist[5])
            badbinstrlist=[]
            for bb in badbins:
                badbinstrlist.append('%d' % (bb+1))  #one-based bins
            badbinstr = ' '.join(badbinstrlist)
            slist.append(s.substitute(datestr=datestr,
                                      numbins=str(numbins),
                                      badbinstr=badbinstr))
    slist.append('')
    if outfile is None:
        _log.debug('%s', '\n'.join(slist))
    else:
        with open(outfile, openstyle) as file:
            file.write('\n'.join(slist))
        _log.debug('%s %d bad bins to %s' % (openstyle_dict[openstyle],
                                            len(slist), outfile))


def write_badprf(dday, yearbase, cflags,
                 outfile=None, openstyle='a'):
    '''
    write (append) to a file or stdout, the lines for abadprf.asc
    kwarg 'open' is 'w' or 'a'

    '''
    s = string.Template(
        '-1    0   0    $datestr ')
    slist = []
    mask = cflags.flags>0
    badprofs = np.ma.where(mask)[0]
    for ibadprof in badprofs:
        datestr = to_datestring(yearbase, dday[ibadprof])
        slist.append(s.substitute(datestr=datestr))
    slist.append('')

    if outfile is None:
        _log.debug('%s', '\n'.join(slist))
    else:
        with open(outfile, openstyle) as file:
            file.write('\n'.join(slist))
        _log.debug('%s %d bad profiles to %s' % (openstyle_dict[openstyle],
                                                len(slist), outfile))

    return len(badprofs)


#=======================
class BottomEdit:
    '''
    method 'get_mask' for bottom masking
    be sure to clean amp if using single-ping data
    '''
    def __init__(self, pfc, beam_angle=None, bin_offset=1.5):
        '''
        data is from get_profiles (codasdb) or pingsuite (single-ping)
        if single-ping; must clean amplitude first.

        bin_offset is the distance to the center of the first bin
        in bin units.

        BE=BottomEdit(beam_angle=30)
        BE.get_flags(data)


        '''
        if beam_angle is None:
            raise ValueError('must set beam angle')
        #
        self.mab = np.zeros((), dtype=bool)  # TR-FIX - 18Jan2018
        self.pfc = pfc
        self.beam_angle = beam_angle
        self.bin_offset = bin_offset

    #------------
    def get_flags(self, data, override_pfc=None):
        '''
        sets attributes:
                  sets useful attributes:
                  cflags: 2D Flags instance
                  mab: 1D (max amp bin, -1 if all good)
                  lgb 1D (last good bin)
        '''
        # These are for convenience only.
        self.yearbase = data.yearbase
        self.dday = data.dday

        self.cflags = Flags(shape=(data.nprofs, data.nbins),
                            names=['sidelobe'])

        kw = Bunch.fromkeys(['bigtarget_ampthresh',
                            'bigtarget_mab_window',
                            ])
        kw.update_values(self.pfc)
        if override_pfc is not None:
            kw.update_values(override_pfc)
        thresh = kw.bigtarget_ampthresh
        try:
            lgb_margin = (data.CellSize + data.Pulse) / (4 * data.depth_interval)
        except AttributeError:
            print(list(data.__dict__.keys()))
            raise
        self.process_amp(getattr(data, 'amp'))  # leaves self.ampq, self.d
        self.rawbump = bump_coeff(self.ampq, self.d, self.beam_angle)
        self.maskedbump = np.ma.masked_less(self.rawbump, thresh)
        self.maskedamp = np.ma.array(self.ampq, mask=self.maskedbump.mask)

        mab = np.ma.masked_equal(self.maskedamp.argmax(axis=1), 0, copy=False)

        if mab.ndim > 1:
            mab_window = kw.bigtarget_mab_window

            # This is now 1-D (if amp was 2-D) or 2-D (nprof,4)
            self.mab_raw = mab # save for debugging

            # There are a couple more hardwired editing parameters here...
            rs = Runstats(mab, mab_window, axis=0,
                            masked=True, min_ng=mab_window//2)
            med_diff = np.ma.absolute(mab - rs.median)
            mdthresh = np.ma.maximum(2, mab//25)
            mab_runfilt = np.ma.masked_where(med_diff > mdthresh, mab)

            # for debugging:
            self.med_diff = med_diff
            self.mab_runfilt = mab_runfilt

            mabmin1 = mab_runfilt.min(axis=1)
            mabmin = np.ma.masked_where(mab_runfilt.count(axis=1) < 2,
                                        mabmin1)
        else:
            mabmin = mab

        frac = np.cos(self.beam_angle*(np.pi/180.0))
        lgb = frac * (mabmin + self.bin_offset) - self.bin_offset - lgb_margin

        self.lgb = np.ma.masked_less(lgb.astype(int), 0, copy=False)

        # bottom mask
        nbins = self.ampq.shape[1]
        indices = np.arange(nbins, dtype=int)
        bmask = indices > self.lgb[:,np.newaxis]
        # No bottom mask where lgb is masked.
        bmask = bmask.filled(False)
        self.cflags.addmask(bmask, 'sidelobe')

        self.mab = np.ma.masked_equal(mabmin, 0, copy=False)
        self.mab.fill_value = -1 # for CODAS flag value

    def process_amp(self, rawamp, med_cutoff=None):
        amp = np.atleast_2d(rawamp)

        nprofs, nbins = amp.shape[:2]

        # approx depth in bin units:
        d = self.bin_offset + np.arange(nbins)

        # approx spreading loss (nominal 0.45 db/count):
        spread = (20/0.45) * np.log10(d)

        if med_cutoff is None:
            ampq = amp
        else:
            medfilt_window = 3
            if nprofs < medfilt_window:
                # can't run medfilt with too few profiles
                ampq = amp
            else:
                # horizontal: to get rid of noise
                amprh = Runstats(amp, 3, axis=0)
                ampq = amprh.medfilt(med_cutoff)

        if amp.ndim == 3:
            spread = spread[:, np.newaxis]
        ampq = ampq.astype(float) + spread
        self.ampq = ampq
        self.d = d

#===============
class ThresholdEdit:
    '''
    incorporate all simple threshold editing (yields bad bins)
    should work for singleping and averaged data, tailoring cutoff
    '''
    average = ['ecutoff', 'e_std_cutoff', 'wcutoff',
               'wire', 'resid_stats', 'pgcutoff', 'trimtopbins',
               'topbins_pgcutoff',  'topbins_corcutoff',
               ]
    # I think this is obsolete/was never used:
    raw = ['ecutoff', 'wcutoff'] #single-ping editing is in pingedit.py

    def __init__(self, pfc, edit='average', verbose=False, **kw):
        '''
        simple threshold editing

        input
            args
                pfc: dictionary with key, value pairs for editing
             kwargs
                edit: 'average', 'raw', or a list of specific function names
                the rest are used to override pfc (profile flag cutoffs)
        methods (cutoff threshold editing)
            editing functions:generate boolean mask (True is masked)
            'get_flags': apply and add all, creates attribute 'flags'
        **kw overrides pfc (profile flag cutoffs) dictionary elements
        '''
        self.verbose = verbose

        if isinstance(edit, str):
            self.edit_names = getattr(self, edit)  #eg. 'average'
        else:
            self.edit_names = edit  # should be a list of names

        # assign override cutoffs if specified
        self.pfc = pfc.copy()
        for kk in kw:
            if kk in pfc.keys():
                self.pfc[kk]=kw[kk]

 #---

    def get_flags(self, data, mask=None, override_pfc = {}):
        '''
        apply all edit cutoffs
        'mask' should be bottom mask, and is used on topbins_pgcutoff
        **kw overrides profile flag cutoff values ('pfc')

        sets useful attributes: 2-D "cflags" (Flags instance)
        '''
        #FIXME - return Flags instance, do not create an attribute
        # override_pfc  overrides profile flag cutoffs locally, if specified
        self.local_pfc = self.pfc.copy()
        self.yearbase = data.yearbase

        for kk in override_pfc.keys():
            if kk in self.local_pfc:
                self.local_pfc[kk] = override_pfc[kk]

        if mask is None:
            self.cflags = Flags(shape=(data.nprofs, data.nbins),
                               names=self.edit_names)
        else:
            self.cflags = Flags(flags=mask, names=self.edit_names)

        if self.verbose:
            _log.debug('edit_names: %s', self.edit_names)
        for name in self.edit_names:
            if name == 'topbins_corcutoff': #include mask
                newmask = self.refl_bad_threshold(data.swcor, name, self.local_pfc, mask=mask)
            elif name == 'topbins_pgcutoff': #include mask
                newmask = self.refl_bad_threshold(data.pg, name, self.local_pfc, mask=mask)
            else:
                flagfcn = getattr(self, name)
                newmask = flagfcn(data, self.local_pfc)

            self.cflags.addmask(newmask, name)

        self.dday = data.dday

    #----------
    def ecutoff(self,data, pfc):
        '''
        mask error velocity greater pfc['ecutoff']
        input mask not used
        '''

        name = 'ecutoff'
        if self.verbose:
            _log.debug('%20s: orig=%5s, used=%5s',
                      name, self.pfc[name], pfc[name])

        bad = (np.abs(data.e.data) >= pfc['ecutoff'])
        valid = ~data.e.mask

        return bad & valid


    #----------
    def e_std_cutoff(self,data, pfc):
        '''
        mask error velocity std greater pfc['e_std_cutoff'] and pg < 80
        input mask not used
        '''

        name = 'e_std_cutoff'
        if self.verbose:
            _log.debug('%20s: orig=%5s, used=%5s',
                      name, self.pfc[name], pfc[name])

        # although PG is a masked array, its values are never masked
        # FIXME - the PG cutoff should be propagated outside this test
        # FIXME - figure out why this is called twice in dataviewer.py,
        #         with masking maybe ignored the second time?
        #         (or the mask is being shared with something eles??)
        if hasattr(data, 'e_std'):
            valid = (data.e_std.data < 1e37)
            bad = (data.e_std.data >= pfc['e_std_cutoff']) & (data.pg.data < 80)

            return bad & valid
        else:
            return np.zeros_like(data.e.mask)

    #----------
    def pgcutoff(self,data, pfc):
        '''
        mask percent good less than  pfc['pgcutoff']
        input mask not used
        '''

        name = 'pgcutoff'
        if self.verbose:
            _log.debug('%20s: orig=%5s, used=%5s',
                      name, self.pfc[name], pfc[name])

        bad = (np.abs(data.pg) < pfc['pgcutoff'])

        return bad


    #----------
    def resid_stats(self, data, pfc):
        '''
        mask resid_stats['ff'] velocity greater pfc['resid_stats_fwd']
        Initial mask is data.u.mask; returned mask shows additional masked points.
        '''

        name = 'resid_stats_fwd'
        if hasattr(data, name):
            if self.verbose:
                _log.debug('%20s: orig=%5s, used=%5s',
                          name, self.pfc[name], pfc[name])

            bad = np.abs(data.resid_stats_fwd.data) >= pfc[name]
            valid = ~data.resid_stats['ff'].mask
        else:
            bad = data.u.mask
            valid = ~data.u.mask

        return bad & valid

    #------------------
    def wcutoff(self,data, pfc):
        '''
        mask w greater than pfc['wcutoff']
        input mask not used
        '''

        name = 'wcutoff'
        if self.verbose:
            _log.debug('%s: orig=%s, used=%s', name,
                      self.pfc[name], pfc[name])

        # only return bad bins if w is valid


        bad = (np.abs(data.w.data) >= pfc['wcutoff'])
        valid = ~data.w.mask

        return bad & valid

    #---
    def wire(self, data, pfc):
        '''
        mask bins with wire interference
        input mask not used
        '''
        # test these bins
        wire_lastbin = int(pfc['wire_lastbin'])
        if wire_lastbin == 0: # check no bins
            return np.zeros_like(data.u.mask)

        names = ['wire_lastbin', 'onstation', 'wire_ecutoff']
        if self.verbose:
            for name in names:
                _log.debug('%20s: orig=%5s, used=%5s',name,
                          self.pfc[name], pfc[name])

        names.append('validvel')

        # accumulate flag criteria to be combined with 'logical and'
        ff = Flags(shape=data.u.shape, names=names)

        # valid vel
        goodvel = ~data.w.mask
        ff.addmask(goodvel, 'validvel')
        # if in refl
        refsl = slice(0, wire_lastbin)
        inrefl = np.zeros(data.u.shape,dtype=bool)
        inrefl[:,refsl]=True
        ff.addmask(inrefl, 'wire_lastbin')
        # if on station
        onstation = np.zeros(data.u.shape,dtype=bool)
        onstation[data.spd<=pfc['onstation'],:]=True
        ff.addmask(onstation, 'onstation')
        # errvel too high
        bad_errvel = np.abs(data.e.filled(0)) >= pfc['wire_ecutoff']
        ff.addmask(bad_errvel, 'wire_ecutoff')
        #
        badbins = (ff.flags == ff.maxflag())
        h_mask=slidemask(badbins, numslide=1, axis=0)
        v_mask=slidemask(badbins, numslide=1, axis=1)
        badbins = badbins | h_mask | v_mask
        return badbins

   #---
    def trimtopbins(self,data, pfc):
        '''
        trim top N bins if underway (eg. ringing)

        '''

        names = ['trimtopbins', 'onstation']
        if self.verbose:
            for name in names:
                _log.debug('%s: orig=%s, used=%s',name,
                          self.pfc[name], pfc[name])

        ff = Flags(shape=data.u.shape,
                       names=['trimtopbins', 'underway'])
        # if underway
        underway = np.zeros(data.u.shape,dtype=bool)
        underway[data.spd>pfc['onstation'],:]=True
        ff.addmask(underway, 'underway')

        # bins to trim
        trimtopbins = int(pfc['trimtopbins'])

        trimbins =  np.zeros(data.u.shape,dtype=bool)
        trimbins[:,slice(0,trimtopbins)] = True
        ff.addmask(trimbins, 'trimtopbins')

        return ff.flags == ff.maxflag()

    #===

    def refl_bad_threshold(self, arr, name, pfc, mask = False):
        '''
        min arr threshold applied to reflayer, by bin

        Returns a mask with True in locations newly identified by
        this criterion.
        '''
        if self.verbose:
            _log.debug('%s: orig=%s, used=%s', name,
                      self.pfc[name], pfc[name])
        thresh = pfc[name]

        refl_startbin = int(pfc['refl_startbin'])
        refl_endbin = int(pfc['refl_endbin'])
        refbins = slice(refl_startbin, refl_endbin)
        badtop = np.empty(arr.shape, dtype=bool)
        badtop.fill(False)
        valid = badtop.copy()
        valid[:] = np.logical_not(mask)
        badtop[:, refbins] = (arr[:, refbins] < thresh) & valid[:, refbins]

        return badtop


#=============
class ProfileEdit:
    '''
    simple profile editing
    ==> need to make these be in order
    '''
    average = ['badpg_refl', 'jittery', 'fastship', 'friendless', 'toofewpings']

    def __init__(self, pfc, edit='average', verbose=False, **kw):
        '''
        simple bad profile editing

        input
            args
                pfc: dictionary with key, value pairs for editing
                pfc_flags: orthogonal integers to tag editing
             kwargs
                edit: 'average', 'raw', or a list of specific functions
                the rest are applied to override pfc

        methods
             edit profile functions : generate boolean mask
                     input mask is 2-d (nprofs x nbins) boolean
                     output masks are 1-D arrays, length 'nprofs'
             'get_flags': apply and add all, creates attribute 'flags'
                     flags is also nprofs x nbins
        '''
        self.verbose=verbose
        if isinstance(edit, str):
            self.edit_names = getattr(self, edit)  #self.average, eg. 'jitter'
        else:
            self.edit_names = edit

        if self.verbose:
            _log.debug('edit names: %s', self.edit_names)

        self.pfc = pfc.copy()
        # assign flags to errors
        for kk,vv in kw:
            if kk in self.pfc:
                self.pfc[kk]=kw[kk]

        # generate function dictionary
        fdict = {}
        for name in self.edit_names:
            fdict[name] = getattr(self, name)

        self.jitter = None

   #---
    def get_flags(self, data, mask=None, override_pfc = {}):
        '''
        apply bin-wise masks before calling
        **kw overrides profile flag cutoff values ('pfc')

        sets useful attributes: 1-D "cflags" (Flags instance), and flags2D
        '''
        # override profile flag cutoffs locally, if specified
        self.local_pfc = self.pfc.copy()
        self.yearbase = data.yearbase

        for kk in override_pfc.keys():
            if kk in self.local_pfc:
                self.local_pfc[kk] = override_pfc[kk]
        self.cflags = Flags(shape=(data.nprofs), names=self.edit_names)
        for name in self.edit_names:
            if name in ('badpg_refl', 'fastship', 'toofewpings'):
                try:
                    flagfcn = getattr(self, name)
                    newmask = flagfcn(data, self.local_pfc)
                    self.cflags.addmask(newmask, name)
                except Exception:
                    _log.exception('===> could not apply %s mask' % (name))
        ## these should be done at the end, in this order
        if 'jittery' in self.edit_names: #include profile mask thus far
            try:
                newmask = self.jittery(data, self.local_pfc,
                                       pmask=self.cflags.flags>0)
                self.cflags.addmask(newmask, 'jittery')
            except Exception:
                _log.exception('===> could not apply jittery mask')
                pass
        if 'friendless' in self.edit_names:
            try:
                newmask = self.friendless(self.cflags.flags > 0,
                                          self.local_pfc)
                self.cflags.addmask(newmask, 'friendless')
            except Exception:
                _log.exception('===> could not apply friendless')
                pass
        self.flag2D = Flags(shape=(data.nprofs, data.nbins),
                             names=self.edit_names)
        self.flag2D.flags = np.tile(self.cflags.flags, (data.nbins,1)).T
        if mask is not None:
            self.flag2D.flags[mask] = 0
        self.dday = data.dday

    #----------

    #---
    def badpg_refl(self, data, pfc):
        '''
        mask profiles with too few good PG in reflayer
        '''
        # take out ringing if necessary


        for name in ['refl_startbin', 'refl_endbin', 'badpgrefl_nbins']:
            if self.verbose:
                _log.debug('%20s: orig=%5s, used=%5s',
                      name, self.pfc[name], pfc[name])

        refl_startbin = int(pfc['refl_startbin'])
        refl_endbin = int(pfc['refl_endbin'])
        badpgrefl =  int(pfc['badpgrefl'])
        badpgrefl_nbins =  int(pfc['badpgrefl_nbins'])


        reflbins = slice(refl_startbin, refl_endbin)

        numgoodbins = np.sum(data.pg[:,reflbins] >= badpgrefl, axis=1)

        badrefl = (numgoodbins <= badpgrefl_nbins)
        return badrefl

    #---
    def fastship(self, data, pfc):
        '''
        mask profiles with ship velocity too great
        '''


        name = 'shipspeed_cutoff'
        if self.verbose:
            _log.debug('%20s: orig=%5s, used=%5s',
                      name, self.pfc[name], pfc[name])

        return  data.spd.data > pfc[name]


    #---
    def toofewpings(self, data, pfc):
        '''
        mask profiles with too few pings per ensemble
        '''
        name = 'numpings'
        if self.verbose:
            _log.debug('%20s: orig=%5s, used=%5s',
                      name, self.pfc[name], pfc[name])

        return  data.pgs_sample <= pfc[name]

   #---
    def jittery(self, data, pfc, pmask = None, mask=None):
        '''

        returns 1-D mask (True if jitter is too high)
        sets attribute jitter
        '''

        name = 'jitter_cutoff'
        if self.verbose:
            _log.debug('%20s: orig=%5s, used=%5s',
                      name, self.pfc[name], pfc[name])

        refsl = slice(int(pfc['refl_startbin']), int(pfc['refl_endbin']))
        self.jitter = get_jitter(data, pmask=pmask, mask=mask, refsl=refsl)
        return self.jitter.data  >= pfc['jitter_cutoff']

    #---
    def friendless(self, profmask, pfc):
        '''
        mask profiles with insufficient friends
        uses bad_pgrefl to decide which profiles are good enough
        '''

        name = 'numfriends'
        if self.verbose:
            _log.debug('%20s: orig=%5s, used=%5s',
                      name, self.pfc[name], pfc[name])

        numfriends=int(pfc['numfriends'])
        return slidemask(profmask, numslide=numfriends)



class CODAS_AutoEditor:
    '''
    run through codas database, determining flags, writing
    '''
    def __init__(self, pfc, dbname=None, editparams_file = None,
                 override_pfc={}, verbose=False):
        '''
        required inputs:
        - dbname

        optional:
        - defaults come from adcp_spec.codas_editparams
        - editparams_file : name,value pair for editing
        - override_pfc (dictionary of profile flag cutoffs)

        methods:

        - set_beamangle  (** must do once, or must specify in write_flags)
        - get data (get some)
        - write_flags (writes to stdout or a*.asc files in cwd)
        '''
        self.verbose=verbose
        self.beamangle = None

        try:
            get_profiles(dbname, startdd=[.1])
            self.dbname = dbname
        except Exception:
            _log.exception('===> failed to get data from database %s' % (dbname,))
            raise

        self.editparams = Bunch(pfc)
        if editparams_file is not None:
            try:
                cc=Cachefile(cachefile=editparams_file)
                cc.read()
                for k in cc.cachedict.keys():
                    cc.cachedict[k] = int(cc.cachedict[k])
                self.editparams.update_values(cc.cachedict)
            except Exception:
                _log.warning('===> could not read codas editparams file %s',
                            editparams_file)

        self.editparams.update_values(override_pfc)


    def set_beamangle(self, beamangle=None, cachefile='../dbinfo.txt'):
        '''
        set beam angle from a cache file or specify it
        '''
        if os.path.exists(cachefile):
            try:
                dbcache = Cachefile(cachefile=cachefile)
                dbcache.read()
                cache_beamangle = dbcache.cachedbdict['beamangle']
                if cache_beamangle is not None:
                    self.beamangle = cache_beamangle
            except Exception:
                pass

        if beamangle is not None:
            self.beamangle = beamangle

    def get_data(self, ddrange):
        '''
        get a chunk of data
        '''
        if self.beamangle is None:
            msg='\n'.join(['must set beam angle once with "set_beamangle"',
                           'or when calling write_flags'])
            raise ValueError(msg)

        try:
            self.data=get_profiles(self.dbname, ddrange=ddrange,
                                   diagnostics=True, flagged=False)
            self.data.w = self.data.w * 1000
            self.data.e = self.data.e * 1000
        except Exception:  # Several ways get_profiles could fail.
            _log.debug('no data found in ddrange %s', ddrange)
            self.data = None


    def write_flags(self, fformat=None, beamangle=None, override_pfc=None,
                    openstyle='a', use_bt=False, use_lgb=False,
                    write_bottom = False):
        '''
        write flags to stdout or to files
        if fformat is None, write to stdout
        otherwise specify as a format string, and the missing
             portion will be filled with one of
             ['bottom', 'badbin', 'badprf'],
             eg 'a%s_tmp.asc' for automatic editing
        '''
        if override_pfc is None:
            override_pfc = {}
        else:
            self.editparams.update_values(override_pfc)

        #TODO -- add functionality for "use_lgb=False"

        if self.beamangle is None:
            msg='\n'.join(['must set beam angle once with "set_beamangle"',
                           'or when calling write_flags'])
            raise ValueError(msg)

        if fformat is None:
            bottomfile = None
            badbinfile = None
            badprffile = None
        else:
            bottomfile = fformat % ('bottom',)
            badbinfile = fformat % ('badbin',)
            badprffile = fformat % ('badprf',)

        if self.data is None:
            _log.error('no data available')
        else:
            # identify the bottom so we only write the badbin and
            # badprf files for actual velocity data
            if hasattr(self.data, 'd_bt') and use_bt:
                d_bt = self.data.d_bt[:, np.newaxis]
                abovemask = (self.data.depth < d_bt)
                mab = abovemask.sum(axis=1)
                btflags = mask_below(self.data.depth, d_bt, self.beamangle)
            else:
                self.BE = BottomEdit(self.editparams,
                                     beam_angle=self.beamangle)
                self.BE.get_flags(self.data)
                mab = self.BE.mab
                btflags = self.BE.cflags.flags # based on lgb

            if write_bottom:
                write_mab(self.BE.dday, self.BE.yearbase, mab,
                          outfile=bottomfile, openstyle=openstyle)

            # threshold edit --> badbins
            self.TE = ThresholdEdit(self.editparams)
            self.TE.get_flags(self.data, mask=btflags>0,
                              override_pfc=override_pfc)
            write_badbins(self.TE.dday, self.TE.yearbase,
                          self.TE.edit_names, self.TE.cflags,
                          outfile=badbinfile, openstyle=openstyle)

            # profile edit --> badprf
            self.data.apply_flags(keep_mask=True,
                                  mask=(btflags + self.TE.cflags.flags)>0)
            self.PE = ProfileEdit(self.editparams)
            self.PE.get_flags(self.data, override_pfc=override_pfc)
            # make a 2-D array; write as badbins; append to earlier file
#            write_badbins(self.PE.dday, self.PE.yearbase,
#                          self.PE.edit_names, self.PE.flag2D,
#                          outfile=badbinfile, openstyle='a')

            write_badprf(self.PE.dday, self.PE.yearbase, self.PE.cflags,
                         outfile=badprffile, openstyle=openstyle)
