"""
Classes for evaluating attitude sensors.

This uses rbins directly.  At present the only thing using
this library is plot_hcorrstats_fromrbins.py (at-sea plots
and daily.py stats are coming from HbinDiagnostics).
"""

import os
import logging
import numpy as np
import matplotlib.pyplot as plt


from pycurrents.num.int1 import interp1           # interpolation
from pycurrents.data import navcalc # uv_from_txy, unwrap_lon, unwrap ...
from pycurrents.codas import to_date
from matplotlib.ticker import ScalarFormatter
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.data.nmea.qc_rbin import RbinSet
from pycurrents.num import Runstats, Stats
import pycurrents.system.pathops as pathops

#np.seterr(all='ignore')  #FIXME - that can't be good

# Standard logging
_log = logging.getLogger(__name__)
_log.setLevel(logging.INFO)


class Attitude:
    '''
    get attitude info
    '''

    def __init__(self, uhdas_cfg=None, binfileset=False, **kw):
        r'''
        base class to access attitude data

        *kwargs*

          * *uhdas_cfg*: UhdasConfig instance

          * *binfileset* : [False] -- if True, read BinfileSets of specified
                  data. (used for finding 'ends'; easy to read too much data)

          * \*\*kw (other kwargs are passed to UhdasConfig)

        '''

        self.uhdas_cfg = uhdas_cfg

        # position
        self.phead_inst = uhdas_cfg.gbin_params['pos_inst']
        self.phead_msg = uhdas_cfg.gbin_params['pos_msg']
        pglobstr = os.path.join(uhdas_cfg.rbin, self.phead_inst,
                                     '*.%s.rbin' % (self.phead_msg))
        self.phead_filelist=pathops.make_filelist(pglobstr)

        # reliable heading
        self.rhead_inst = uhdas_cfg.gbin_params['hdg_inst']
        self.rhead_msg = uhdas_cfg.gbin_params['hdg_msg']
        rglobstr = os.path.join(uhdas_cfg.rbin, self.rhead_inst,
                                     '*.%s.rbin' % (self.rhead_msg))
        self.rhead_filelist=pathops.make_filelist(rglobstr)


        # accurate heading
        self.ahead_inst = uhdas_cfg.hcorr[0]
        self.ahead_msg = uhdas_cfg.hcorr[1]
        aglobstr = os.path.join(uhdas_cfg.rbin, self.ahead_inst,
                                     '*.%s.rbin' % (self.ahead_msg))
        self.ahead_filelist=pathops.make_filelist(aglobstr)


        if binfileset:
            self.pdata_bfs = BinfileSet(self.phead_filelist)
            self.adata_bfs = BinfileSet(self.ahead_filelist)
            self.rdata_bfs = BinfileSet(self.rhead_filelist)


    #------------

    def get_range2(self, binset, range_):
        '''
        return range_ with 2 values (seems to be required)
        '''
        if range_ == 'all':
            range_ = None

        if np.iterable(range_):
            if len(range_) < 2:
                raise ValueError('iterable range_ must have two values')
            startdd, enddd = range_
        else:
            if range_ is None: # get all
                startdd = binset.starts[self.cname][0]
                enddd = binset.ends[self.cname][-1]
            elif range_ > 0:
                startdd = binset.starts[self.cname][0]
                enddd = startdd + range_
            else: #negative
                enddd =  binset.ends[self.cname][-1]
                startdd = enddd + range_

        self.startdd = startdd
        self.enddd = enddd
        # this alters the rbins in place
        return (startdd, enddd)

    #-------------
    def get_rbins(self, range_=None,
                      step=1, cname='u_dday',
                      qc_kw={}):
        '''
        In progress: replacement for get_rbins, using newer
        facilities of RbinSet; to be used in uhdas/scripts/run_hcorrstats

        Note: range_ is interpreted by RbinSet.set_range
        get a subset of rbins based on time range

        *required attributes*

          *  (for reliable heading)
          * aglobstr (for accurate heading)

        *kwargs*

          * *range_*, *step*, *cname*, as per BinfileSet/RbinSet
          * *qc_kw* dictionary of kwargs passed (via get_rbinrec) to RbinSet

          **NOTE** -- "step" refers to subsample rate for all, not new Hz
        '''

        self.step = step
        self.cname = cname
        #---------------
        # position
        self.pdata = RbinSet(self.phead_filelist, **qc_kw)
        if self.pdata is None:
            return 'failed to get positions. nonmonotonic %s?' % (cname,)
        _log.info('starting with range_ = ', range_)
        range_ = self.get_range2(self.pdata, range_) # replace it with a tuple
        _log.info('end with range_ = ', range_)
        self.pdata.set_range(range_, step=self.step, cname=self.cname)

        _log.debug('pdata: %d position (%s, %s): \n%s\n' % (
                    len(self.pdata.u_dday),
                    self.uhdas_cfg.gbin_params['pos_inst'],
                    self.uhdas_cfg.gbin_params['pos_msg'],
                    self.pdata.dtype.names.__str__()))

        #---------------
        #reliable heading
        self.rdata = RbinSet(self.rhead_filelist, **qc_kw)
        if self.rdata is None:
            return 'failed to get reliable heading. nonmonotonic %s?' % (cname,)
        self.rdata.set_range(range_, step=self.step, cname=self.cname)

        _log.debug('rdata: %d reliable heading (%s, %s): \n%s\n' % (
                    len(self.rdata.u_dday),
                    self.uhdas_cfg.gbin_params['hdg_inst'],
                    self.uhdas_cfg.gbin_params['hdg_msg'],
                    self.rdata.dtype.names.__str__()))

        #----------------
        # accurate heading
        self.adata = RbinSet(self.ahead_filelist, **qc_kw)
        if self.adata is None:
            return 'failed to get accurate heading. nonmonotonic %s?' % (cname,)
        self.adata.set_range(range_, step=self.step, cname=self.cname)

        _log.debug('adata: %d accurate heading (%s, %s): \n%s\n' % (
                    len(self.adata.u_dday),
                    self.ahead_inst,
                    self.ahead_msg,
                    self.adata.dtype.names.__str__()))

        # return empty error message
        return ''

    # ---------------
    def grid_att(self, dh_tol = 1, max_dx=None):
        '''
        grid acurate and reliable headings onto the same time base
        gridding is done using cname in ['m_dday' , 'u_dday'] fron get_rbins
        max_dx is the maximum gap over which interp1 will interpolate
           NOTE: if not set, all heading gaps will be interpolated over
                 Gridding is done ONTO the times of the accurate device
        dh_tol: also mask anything that would fail a median filter with dh_tol

        sets instances of 'dh' and 'dhm' (reliable -accurate) difference
          - (the latter is masked) matching griddday; suitable for "rotate"

        '''
        self.griddday  = self.pdata.records[self.cname]
        if max_dx == 0 or max_dx is None:
            max_dx = self.griddday[-1]-self.griddday[0]

        # unmasked  ## JH: I'll bet using ".data" is BAD BAD BAD
        self.ahead_ = interp1(self.adata.records[self.cname],
                         navcalc.unwrap(self.adata.heading.data),
                         self.griddday, max_dx=max_dx)
        # masked
        self.aheadm_ = interp1(self.adata.records[self.cname],
                          navcalc.unwrap(self.adata.heading),
                          self.griddday, max_dx=max_dx)

        # unmasked
        self.rhead_ = interp1(self.rdata.records[self.cname],
                         navcalc.unwrap(self.rdata.heading.data),
                         self.griddday, max_dx=max_dx)
        # masked
        self.rheadm_ = interp1(self.rdata.records[self.cname],
                          navcalc.unwrap(self.rdata.heading),
                          self.griddday, max_dx=max_dx)


        dh  = np.remainder(self.rhead_-self.ahead_+180.+360.,360.)-180.
        dhm = np.ma.remainder(self.rheadm_-self.aheadm_+180.+360.,360.)-180.
        RS = Runstats(dhm,301)
        dhm.mask = np.ma.mask_or(dhm.mask, abs(dhm - RS.median) >= dh_tol)

        self.dh = dh
        self.dhm = dhm


#---------------

class Hcorr(Attitude):
    '''
    start with class Attitude, add heading correction

    Typical use:

    cruisedir = '/home/data/km1001a'
    cname='m_dday'

    uhdas_cfg=Uhdasconfig(...)
    HH = Hcorr(uhdas_cfg=uhdas_cfg)
    HH.get_rbins(ddrange=[130,131], cname=cname)
    HH.grid_att()
    HH.hcorr_stats(winsecs=300)
    HH.print_stats_summary()
    HH.print_hcorr('ens_hcorr', overwrite = True)
    HH.plot_hcorstats(detailed=False)


    '''
    def __init__(self, **kwargs):
        '''
        kwargs passed directly to Attitude
        '''
        Attitude.__init__(self, **kwargs)


    def plot_hcorr(self, titlestring=None):
        '''
        plot heading correction if possible: native rbin data, possibly subsampled
        '''

        #yearbase = FileParts(self.rhead_filelist[-1]).year
        ff,ax=plt.subplots(nrows=2, sharex=True)
        ax1,ax2 = ax

        gg = np.ma.remainder(self.rdata.records['heading'],360)
        gg_minmax = np.array([np.ma.min(gg), np.ma.max(gg)])
        atmp = self.adata.records['heading'].copy()
        atmp = atmp.compress(np.isnan(atmp)==False)
        aa = np.ma.remainder(atmp,360)
        aa_minmax = np.array([np.ma.min(aa), np.ma.max(aa)])
        if np.isnan(aa_minmax[0]) or np.isnan(aa_minmax[1]):
            aa_minmax = gg_minmax
        minmax = np.array([
                min(gg_minmax[0], aa_minmax[0]),
                max(gg_minmax[1], aa_minmax[1])])
        spread = 0.6 * np.diff(minmax)[0]
        ylims = np.ma.mean(minmax) + np.array([-spread, spread])

        mm=np.ma.getmaskarray(self.adata.records['heading'])
        ax1.plot(self.adata.records[self.cname][mm],
                 np.ma.remainder(self.adata.records['heading'][mm], 360),'r.', ms=4)
        ax1.plot(self.rdata.records[self.cname],
                 np.ma.remainder(self.rdata.records['heading'],360),'g.',ms=4,
                 mec='none')
        ax1.plot(self.adata.records[self.cname][mm],
                 np.ma.remainder(self.adata.records['heading'][mm],360),'b+', ms=2)
        ax1.set_ylim(ylims)

        ax1.text(.5, .9 , 'HEADING', fontsize=12, transform = ax1.transAxes,
                  ha='center')

        ax1.text(.1, .9 , '(%s)' % (self.rhead_inst), color='g',
                  fontsize=12, transform = ax1.transAxes, ha='left')

        ax1.text(.9, .9 , '(%s)' % (self.ahead_inst,), color='b',
                  fontsize=12, transform = ax1.transAxes, ha='right')

        ax1.set_ylabel('degrees')
        ax1.grid(True)

        cruisename = self.uhdas_cfg.cruisename
        if titlestring is None:
            ax1.set_title(cruisename)
        else:
            ax1.set_title(titlestring)

        # heading correction
        mm=np.ma.getmaskarray(self.dhm)
        ax2.plot( self.griddday[mm], self.dh[mm] ,'r.', ms=4)
        ax2.plot(self.griddday, self.dhm,'c+', ms=3)

        ax2.set_xlabel('decimal day')
        ax2.set_ylabel('degrees')
        ax2.set_xlim(self.griddday[0], self.griddday[-1])

        ax2.text(.6, .9 , 'heading correction: %s-%s' % (
                self.ahead_inst, self.rhead_inst),
                  fontsize=12, transform = ax2.transAxes,  ha='right')
        ax2.text(.6, .9 , '  (bad = red)', color='r',
                  fontsize=12, transform = ax2.transAxes,  ha='left')

        ax2.grid(True)
        ax2.set_xlim(self.griddday[0], self.griddday[-1])

        gg_minmax = np.array([np.ma.min(self.dhm), np.ma.max(self.dhm)])
        gg_spread = 0.6 * np.diff(gg_minmax)[0]
        gg_ylims = np.ma.mean(gg_minmax) + np.array([-gg_spread, gg_spread])
        ax2.set_ylim(gg_ylims)

        self.hcorr_fig = ff

    #-------------
    def get_rbin_stats(self):
        '''
        set attribute 'ptsPG' as the fraction of good heading values from
        the accurate heading device: this comes from rbins.
        '''
        self.ptsPG = 100*self.adata.heading.count()/len(self.adata.heading)

    #-------------

    def hcorr_stats(self, nwin=None, ens_timefile = None, comments='%',
                    mingoodfrac=0.5, mingoodnum = 15):

        '''
        generate statistics of heading correction using runstats.

        must run grid_att first, to initialize heading corrections


        *kwargs*

          * *nwin* : choose time step (seconds) for output (integer)
          * *ens_timefile* : file with first column containing ascii
                             dday ensemble times

                  +  eg. as from nav/*.gps or cal/rotate/ens_hcorr.asc

                  + **CHOOSE ONE** i.e  nwin -or- ens_timefile (not both)

          * *mingoodfrac* : fraction of ensemble required to be accepted
          * *mingoodnum*  : lowest threshold number of points for acceptance

        '''
        # test these statistics:
        if nwin is None and ens_timefile is None:
            print(__doc__)
            raise ValueError('Must specify "nwin" or "ens_timefile"')


        # dt
        if ens_timefile is None:
            self.out_stepsec = int(nwin)
            self.segends=np.arange(self.griddday[0],
                              self.griddday[-1]+self.out_stepsec/86400.,
                                   self.out_stepsec/86400.)

            self.ensdday = self.segends[1:]
        else:
            ensdday = np.loadtxt(ens_timefile, comments=comments,
                                      usecols=[0,])

            ensdday = ensdday[np.where(ensdday>=self.pdata['dday'][0])[0]]
            self.ensdday = ensdday[np.where(
                    ensdday<=self.pdata['dday'][-1])[0]]

            self.out_stepsec = int(np.median(np.diff(self.ensdday))*86400)
            self.segends = np.zeros((len(self.ensdday)+1),float)
            self.segends[0] = self.ensdday[0] - self.out_stepsec
            self.segends[1:] = self.ensdday

        data_stepsec = np.median(np.diff(self.griddday))*86400
        nwin_width = int(self.out_stepsec / data_stepsec)
        nwin_width_odd = int(np.ceil(nwin_width/2.) * 2 + 1)

        self.mingood = np.max([.4*nwin_width_odd, 15]) # 40% of data or 15 pts
        self.RS_dh  = Runstats(self.dh, nwin_width_odd, min_ng= self.mingood)
        self.RS_dhm = Runstats(self.dhm,nwin_width_odd, min_ng= self.mingood)
        self.RS_rhead= Runstats(self.rhead_, nwin_width_odd,
                               min_ng= self.mingood)


        self.mid_times = (self.segends[1:] + self.segends[:-1])/2
        self.mid_dhm = interp1(self.griddday, self.RS_dhm.median, self.mid_times)

        self.mid_dhstd = interp1(self.griddday, self.RS_dhm.std,
                                 self.mid_times)
        self.mid_n   = interp1(self.griddday, self.RS_dhm.ngood,
                               self.mid_times)

        # summary values
        self.ensnumgood =  len(np.ma.where(self.mid_dhm)[0])
        self.ensnumtotal = len(np.ma.where(self.mid_n)[0])
        self.enspercent = np.round(100.0 * self.ensnumgood/self.ensnumtotal)

    #------------

    def plot_enshcorr(self, titlestring=''):
        '''
        plot existing estimates of heading correction

        *kwargs*

        '''
        detailed=True

        ff=plt.figure(figsize=(7,10))
        ax1=ff.add_subplot(211)
        ff.text(.5,.95,titlestring,ha='center')
        kwp = {'transform' : ax1.transAxes}
        kwt = {'transform' : ax1.transAxes, 'ha' : 'left',
               'va' : 'center'}
        x=.03; y=.96; dx=.01; dy=.05

        if detailed:
            ax1.plot(self.griddday, self.dh,'r', ms=3)
            ax1.plot(self.griddday, self.dhm,'c.', ms=3)
            ax1.plot(self.griddday, self.RS_dhm.median,'k.', ms=3)
            ax1.plot(self.mid_times, self.mid_dhm,'yo')

            S=Stats(self.RS_dhm.median)
            yy=min(10*S.std, 8)
            ax1.set_ylim([S.median-yy, S.median+yy])
            ax1.plot(x-dx, y, 'r.', **kwp)
            ax1.text(x+dx, y,'diff (all)', color='r', **kwt)
            ax1.plot(x-dx, y-dy, 'c.',  **kwp)
            ax1.text(x+dx, y-dy,'diff (good)', color='c', **kwt)
            ax1.plot(x-dx, y-2*dy, 'k.',  **kwp)
            ax1.text(x+dx, y-2*dy,'runstats median', color='k', **kwt)
            ax1.plot(x-dx, y-3*dy, 'yo',  **kwp)
            ax1.text(x+dx, y-3*dy,'runstats pts', color='y', **kwt)
            ax1.set_xlim(self.griddday[0], self.griddday[-1])
            ax1.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))

        else:
            ax1.plot(self.mid_times, self.mid_dhm,'k.',ms=4)
            ax1.text(x+dx, y-dy,'diff (good)', color='c', **kwt)
            ax1.text(x+dx, y-3*dy,'runstats pts', color='k', **kwt)
            ax1.set_xlim(self.griddday[0], self.griddday[-1])
            ax1.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))

        ax1.set_title('heading correction (reliable-accurate)')
        ax1.set_xlim(self.griddday[0], self.griddday[-1])

        ax2=ff.add_subplot(212, sharex=ax1)
        if detailed:
            ax2.plot(self.griddday, 0.0*self.dh + self.mingood,'r.', ms=4)
            ax2.plot(self.griddday, 0.0*self.dhm + self.mingood,'k.', ms=4)
            ax2.plot(self.griddday, self.RS_dhm.ngood,'c')
            ax2.plot(self.mid_times, self.mid_n,'yo')
            ax2.set_title('number of good points')
        else:
            ax2.plot(self.mid_times, 0*self.mid_n+self.mingood,'r')
            ax2.plot(self.mid_times, self.mid_n,'k.',ms=4)

        ax2.set_title('number of good points')
        ax2.text(.98, .4, 'numgood cutoff', color='r', ha='right',
                  transform=ax2.transAxes)
        ax2.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        ax2.set_xlim(self.griddday[0], self.griddday[-1])

        self.enshcorr_fig = ff

    #------------

    def print_stats_summary(self):
        '''
        return a list of strings
        '''

        ## get some time info here (for printing and plotting)
        self.yearbase = self.uhdas_cfg.yearbase
        self.start_utc =  self.pdata.u_dday[0]
        self.end_utc =  self.pdata.u_dday[-1]

        dd = to_date(self.yearbase, self.start_utc)
        self.start_ymdhms_str = '%4d/%02d/%02d %02d:%02d:%02d' % (
            dd[0],dd[1],dd[2],dd[3],dd[4],dd[5])
        self.start_ymdhms = dd

        dd = to_date(self.yearbase, self.end_utc)
        self.end_ymdhms_str = '%4d/%02d/%02d %02d:%02d:%02d' % (
            dd[0],dd[1],dd[2],dd[3],dd[4],dd[5])
        self.end_ymdhms = dd

        slist = []
        slist.append('%s-%s statistics (comment=rangeslice, %s)' % (
                     self.ahead_inst,  self.rhead_inst, self.cname))
        slist.append('')

        slist.append('ddrange: %10.7f to %10.7f' % (
                self.start_utc, self.end_utc))
        slist.append('(%s to %s)' % (self.start_ymdhms_str, self.end_ymdhms_str))
        self.get_rbin_stats() ## use rbins (not gridded) to find 'good'
        slist.append('all %s messages:  (%d%%)  were good' % (
                self.ahead_inst, self.ptsPG))

        slist.append('')
        slist.append('(%ssec) ensemble heading corrections:' % (
                self.out_stepsec))
        slist.append('   %d out of %d   (%d%%) were good' % (
                self.ensnumgood, self.ensnumtotal, self.enspercent))
        slist.append('statistics of good data:')
        S = Stats(self.mid_n, masked=False)
        slist.append('   mean N = %.0f, stddev N =  %.1f' % (S.mean, S.std))
        slist.append('   min  = %4.2f, max = %4.2f'
                     % (np.ma.min(self.mid_dhm), np.ma.max(self.mid_dhm)))
        S = Stats(self.mid_dhm, masked=False)
        slist.append('   mean = %3.2f, stddev = %4.2f' % (S.mean,S.std))

        slist.append('')

        return slist
   #------------

    def print_enshcorr(self, outfilebase, overwrite=False):
        '''
        print files for codas processing, equivalent to post_headcorr
        eg. hcorr.ang, hcorr.asc
        '''

        suffixes = ['.asc', '.ang']
        if overwrite:
            for suffix in suffixes:
                fname = outfilebase+suffix
                if os.path.exists(fname):
                    try:
                        os.remove(fname)
                    except:
                        raise IOError('could not remove %s' % (fname,))

        for suffix in suffixes:
            fname = outfilebase+suffix
            if os.path.exists(fname):
                raise IOError('file exists.  not writing %s' % (fname,))



        header = '\n'.join([
                '% headings listed are from reliable heading device',
                '% sign is correct for use with "rotate"',
                '',
                ''.join(['%enddday, mean head, last head, ',
                        'dhfix, stddh, ndh, badmask(bad==1) persist_win']),
                ''])

        mask = self.mid_dhm.mask
        goodi =  np.ma.where(mask == False)[0]
#        badi  =  np.ma.where(mask == True)[0]

        # not masked
        enddday = self.ensdday
        mean_head = interp1(self.griddday, self.RS_rhead.mean,
                            self.mid_times)
        last_head = interp1(self.griddday, self.rhead_, enddday)

        # take out masks so we don't get any NaNs when we print
        dhfix0         = np.zeros((len(mask)),float)
        dhfix0[goodi]  = self.mid_dhm[goodi]
        # this leaves us with zeros where the data ar bad
        stddh         = np.zeros((len(mask)),float)
        stddh[goodi]  = self.mid_dhstd[goodi]

        ndh  = np.zeros((len(mask)),int)
        for ii in goodi:
            ndh[ii] = int(self.mid_n[ii])

            badmask   = np.ones((len(mask)),int)  #ones are bad
            badmask[goodi] = 0 #zeros are good
            persist_win = badmask


        # write out original estimates, with zeros where bad
        F=open(outfilebase+'.asc','w')
        F.write(header)
        for ll in zip(enddday,
                      mean_head,
                      last_head,
                      dhfix0,
                      stddh,
                      ndh,
                      badmask,
                      persist_win):
            F.write('%10.7f %9.3f %9.3f %7.3f %7.3f %4d  %4d %4d\n' %(ll))
        F.close()


        F=open(outfilebase+'.ang','w')
        for ll in zip(enddday, dhfix0):
            F.write('%10.7f   %5.3f \n' %(ll))
        F.close()
