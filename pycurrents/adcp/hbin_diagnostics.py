
"""
class for heading correction plots, statistics, using hbins
This is primarily leverged by
- pycurrents/scripts/plot_hcorrstats_fromhbins.py
- uhdas/uhdas/scripts/run_hbinhcorrstats.py (at sea)
"""

import os
import logging
import numpy as np
import matplotlib.pyplot as plt

from pycurrents.num.int1 import interp1           # interpolation
from pycurrents.codas import to_date
from pycurrents.plot.mpltools import savepngs
from matplotlib.ticker import ScalarFormatter, MultipleLocator
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.num import Runstats, Stats
from pycurrents.num.nptools import rangeslice
from pycurrents.system.misc import guess_comment
import pycurrents.system.pathops as pathops

# Standard logging
_log = logging.getLogger(__name__)
_log.setLevel(logging.INFO)

#---------------


class HbinDiagnostics:
    '''

    cruiseid = 'nh1105'
    hcorr_inst_msg = 'ashtech_adu'
    hdg_inst_msg = 'gyro_hnc'
    gap_interp_secs = 10.0  #do not interpolate over longer gaps
    yearbase = 2010
    gbin = '/home/data/current_cruise/gbin'
    annotate_color = 'k'  # for date+timestamp

    H=HbinDiagnostics(gbin=gbin, yearbase=yearbase, gap_interp_secs=gap_interp_secs)

    H.get_segment(-4/24.)
    H.get_hcorr(hdg_inst_msg, hcorr_inst_msg, acc_heading_cutoff)
    H.plot_hcorr()
    H.hcorr_stats(winsecs=301)
    H.print_stats_summary()

    H.plot_hcorstats()
    H.plot_hcorstats(detailed=True)

    '''
    def __init__(self, gbin=None, cname='dday', yearbase=None, gap_interp_secs=10):
        '''
        "atsea" will start with only the last 10 files
        these are BinfileSet, so nans, not masked;
        but we will mask as needed.
        '''

        if yearbase is None:
            raise ValueError('must set yearbase')
        else:
            self.yearbase=yearbase

        hglob=os.path.join(gbin, 'heading','*.hbin')
        self.filelist=pathops.make_filelist(hglob)

        self.binset=BinfileSet(self.filelist[-2:])
        self.max_dt = gap_interp_secs/86400.

        if cname not in self.binset.columns:
            raise ValueError('cname  not in data columns %s' %
                                       (str(self.binset.columns)))
        else:
            self.cname = cname

    def get_segment(self, range_, nfiles=None):
        '''
        see range_ in rangeslice
        range_ is in days
        '''

        if np.iterable(range_):
            if len(range_) < 2:
                raise ValueError('iterable range_ must have two values')

            self.binset = BinfileSet(self.filelist)
            startdd = self.binset.dday[0]
            enddd   = self.binset.dday[-1]

        else:
            if nfiles is None:
                if range_ is None:
                    nfiles = len(self.filelist)
                else:
                    nfiles=int(1 + np.ceil(4*np.abs(range_)*24.))
            if range_ is None: # get all
                self.binset = BinfileSet(self.filelist)
                startdd = self.binset.starts[self.cname][0]
                enddd = self.binset.ends[self.cname][-1]
            elif range_ > 0:
                self.binset = BinfileSet(self.filelist[:nfiles])
                startdd = self.binset.starts[self.cname][0]
                enddd = startdd + range_
            else: #negative
                self.binset = BinfileSet(self.filelist[-nfiles:])
                enddd =  self.binset.ends[self.cname][-1]
                startdd = enddd + range_

        self.startdd = startdd
        self.enddd = enddd
        self.binset.cname = self.cname
        self.binset.set_range(ddrange=[startdd, enddd])

    def get_hcorr(self, hdg_inst_msg, hcorr_inst_msg, acc_heading_cutoff):
        '''
        reliable heading instrument must be FIRST
        accurate heading instrument is SECOND
        no underscores in message name, eg ('abxtwo_b2_udp, 'adu') is OK
        '''

        # reliable heading
        self.rhead = self.binset.records[hdg_inst_msg]
        parts = hdg_inst_msg.split('_')
        self.rhead_inst = '_'.join(parts[:-1])
        # heading correction instrument
        self.hcorr = self.binset.records[hcorr_inst_msg]
        parts = hcorr_inst_msg.split('_')
        self.hcorr_inst = '_'.join(parts[:-1])
        self.hcorr_msg =  parts[-1]

        self.acc_heading_cutoff = acc_heading_cutoff

        ## bugfix: to be consistent with rotate, use reliable-accurate
        dh = ((self.rhead - self.hcorr + 180) % 360) - 180
        self.dh = np.ma.masked_invalid(dh)


    def plot_hcorr(self, titlestring=None,
                   hcorr_gap_fill = 0, outfilename=None,
                   dpi=90, annotate_color = 'k'):
        '''
        plot heading correction if possible
        '''

        # for debugging convenience
        binset = self.binset
        rhead = self.rhead
        hcorr = self.hcorr
        dh = self.dh

        # regardless of which instruments feed which data, we want
        # the most recent timestamp of any
        # column 'dday', this is UTC
        last_utc = self.binset.dday[-1]

        # for plotting dh
        minutesago = (binset.dday - last_utc)*1440.
        last_utc_str = str(np.datetime64(str(self.yearbase)) +
                           np.timedelta64(int(last_utc * 86400), "s")).replace('T', ' ')

        ff=plt.figure(figsize=(8,6))

        ax1=ff.add_subplot(211)

        ax1.plot(minutesago, np.remainder(hcorr,360),'b+', ms=2)
        ax1.plot(minutesago, np.remainder(rhead,360),'g+', ms=2)

        ax1.text(.5, .9 , 'HEADING', fontsize=14, transform = ax1.transAxes,
                  ha='center')

        ax1.text(.1, .9 , '(%s)' % (self.rhead_inst), color='g',
                  fontsize=14, transform = ax1.transAxes, ha='left')

        ax1.text(.9, .9 , '(%s)' % (self.hcorr_inst,), color='b',
                  fontsize=14, transform = ax1.transAxes, ha='right')

        ax1.set_ylabel('degrees')
        ax1.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        ax1.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        ax1.xaxis.set_major_locator(MultipleLocator(base=60.))
        ax1.xaxis.set_minor_locator(MultipleLocator(base=30.))
        ax1.grid(True)
        ax1.set_xticklabels(['',])

        if titlestring is not None:
            ax1.set_title(titlestring)

        # heading correction
        ax2=ff.add_subplot(212, sharex=ax1)
        bbox = ax2.get_position()
        ax2.set_position([bbox.x0, bbox.y0+0.05, bbox.width, bbox.height])

        # red dots at zero where dh is missing:
        dhm = hcorr_gap_fill + np.ma.zeros(dh.shape, float)
        dhm[~np.ma.getmaskarray(dh)] = np.ma.masked
        ax2.plot(minutesago, dhm ,'r.', ms=6)

        ax2.plot(minutesago, dh,'c+', ms=3)

        timelabel='minutes before %s UTC (dday=%5.3f)' % (last_utc_str, last_utc)
        ff.text(.5,.05, timelabel, ha='center', weight='bold', size=14,
                color=annotate_color)
        ax2.set_xlabel('minutes')
        ax2.set_ylabel('degrees')
        ax2.set_xlim(minutesago[0], minutesago[-1])
        ax2.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        ax2.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))

        ax2.text(.6, .9 , 'heading correction: %s-%s' % (
                self.hcorr_inst, self.rhead_inst),
                  fontsize=14, transform = ax2.transAxes,  ha='right')
        ax2.text(.6, .9 , '  (bad = red)', color='r',
                  fontsize=14, transform = ax2.transAxes,  ha='left')

        ax2.xaxis.set_major_locator(MultipleLocator(base=60.))
        ax2.xaxis.set_minor_locator(MultipleLocator(base=30.))
        ax2.grid(True)
        ax2.set_xlim(minutesago[0], 0)

        # heading diff can get thrown off by large values.  Cap if required
        ybounds=[-15,15]
        y0,y1= ax2.get_ylim()

        #color the bad points with red vertical lines so they are more obvious
        badindex = np.where(dhm.mask==False)[0]
        ax2.vlines(minutesago[badindex], y0,y1, color='r')
        ax2.set_ylim(max(y0,ybounds[0]), min(y1,ybounds[1]))


        self.fig = ff
        self.ax1=ax1
        self.ax2=ax2
        self.minutesago = minutesago
        self.timelabel = timelabel
        plt.draw()

        if not plt.isinteractive():
            if outfilename is not None:
                if not np.iterable(dpi):
                    dpi = [dpi]
                    outfilename = [outfilename]
                for d, outf in zip(dpi, outfilename):
                    savepngs(outf, dpi=d, fig=self.fig)



    def get_rbin_stats(self):
        '''
        set attribute 'ptsPG' as the fraction of good heading values from
        the accurate heading device: this comes from rbins.
        '''
        from pycurrents.adcp import uhdasfileparts
        from pycurrents.data.nmea.qc_rbin import RbinSet
        F=uhdasfileparts.FileParts(self.filelist)
        rbinlist=F.rbinlist(self.hcorr_inst, self.hcorr_msg)
        # if 'dday' is not in the data we might need to use u_dday
        # this will only cause a problem with a glitchy timeserver
        #    or if there is none, and the clock has drifted.
        data=RbinSet(rbinlist, acc_heading_cutoff=self.acc_heading_cutoff)
        if self.cname not in data.columns:
            cname = 'u_dday'
        else:
            cname = self.cname
        data.set_range((self.startdd, self.enddd), cname=cname)
        self.ptsPG = 100*data.heading.count()/len(data.heading)


    def hcorr_stats(self,winsecs=None, ens_timefile = None,
                    mingoodfrac=0.4, mingoodnum = 15):

        '''
        generate statistics of heading correction using runstats.

        must run grid_att first, to initialize heading corrections


        *kwargs*

          * *winsecs* : choose time step (seconds) for output (integer)
          * *ens_timefile* : file with first column containing ascii
                             dday ensemble times

                  +  eg. as from nav/*.gps or cal/rotate/ens_hcorr.asc

                  + **CHOOSE ONE** i.e  winsecs -or- ens_timefile (not both)
        '''
        # Not implemented:
        #   * *mingoodfrac* : fraction of ensemble required to be accepted
        #   * *mingoodnum*  : lowest threshold number of points for acceptance

        # test these statistics:
        if winsecs is None and ens_timefile is None:
            raise ValueError('Must specify "winsecs" or "ens_timefile"')

        d0 = self.binset.dday[0]
        d1 = self.binset.dday[-1]

        if ens_timefile is None:
            self.out_stepsec = int(winsecs)
            dstep = self.out_stepsec / 86400.0
            self.segends=np.arange(d0, d1 + 1e-5, dstep)

            self.ensdday = self.segends[1:]
        else:
            comments = guess_comment(ens_timefile)
            ensdday = np.loadtxt(ens_timefile, comments=comments,
                                      usecols=[0,])

            self.ensdday = ensdday[rangeslice(ensdday, d0, d1 + 1e-5)]
            dstep = np.median(np.diff(self.ensdday))
            self.out_stepsec = int(dstep * 86400)
            self.segends = np.zeros((len(self.ensdday)+1), float)
            self.segends[0] = self.ensdday[0] - dstep
            self.segends[1:] = self.ensdday

        ping_dt = np.median(np.diff(self.binset.dday))
        nwin_width = int(dstep / ping_dt)
        nwin_width_odd = int(np.ceil(nwin_width/2.) * 2 + 1)

        self.mingood = np.max([mingoodfrac*nwin_width_odd, mingoodnum]) # 40% of data or 15 pts
        self.RS_dh  = Runstats(self.dh, nwin_width_odd,
                                                min_ng=self.mingood,
                                                masked=True)
        self.RS_rhead= Runstats(self.rhead, nwin_width_odd,
                                                min_ng=self.mingood,
                                                masked=True)

        self.mid_times = (self.segends[1:] + self.segends[:-1])/2
        self.mid_dh = interp1(self.binset.dday, self.RS_dh.median,
                                                  self.mid_times,
                                                  max_dx = self.max_dt,
                                                   )

        self.mid_dhstd = interp1(self.binset.dday, self.RS_dh.std,
                                                    self.mid_times,
                                                  max_dx = self.max_dt,
                                                       )
        self.mid_n   = interp1(self.binset.dday, self.RS_dh.ngood,
                                                    self.mid_times,
                                                  max_dx = self.max_dt,
                                                       )

        # summary values
        self.ensnumgood =  self.mid_dh.count()
        self.ensnumtotal = (self.mid_n > 0).sum()
        # percent accepted of those with at least 1 sample;
        #   is this what we want here?
        if self.ensnumtotal == 0:
            self.enspercent = 0
        else:
            self.enspercent = np.round(100.0 * self.ensnumgood/self.ensnumtotal)

    #------------

    def plot_hcorstats(self, detailed=False):
        '''
        plot existing estimates of heading correction

        *kwargs*

        * *detailed* : [False] if True, show original data too
        '''

        ff=plt.figure(figsize=(7,10))
        ax1=ff.add_subplot(211)
        kwp = {'transform' : ax1.transAxes}
        kwt = {'transform' : ax1.transAxes, 'ha' : 'left',
               'va' : 'center'}
        x=.03; y=.96; dx=.01; dy=.05

        if detailed:
            ax1.plot(self.binset.dday, self.dh,'c', ms=3)
            dhm = np.ma.zeros(self.dh.shape, float)
            dhm[~np.ma.getmaskarray(self.dh)] = np.ma.masked
            ax1.plot(self.binset.dday, dhm,'r.', ms=3)
            ax1.plot(self.binset.dday, self.RS_dh.median,'k.', ms=3)
            ax1.plot(self.mid_times, self.mid_dh,'yo')

            S=Stats(self.RS_dh.median)
            yy=min(10*S.std, 8)
            ax1.set_ylim([S.median-yy, S.median+yy])
            ax1.plot(x-dx, y-dy, 'c.',  **kwp)
            ax1.text(x+dx, y-dy,'diff (good)', color='c', **kwt)
            ax1.plot(x-dx, y-2*dy, 'r.',  **kwp)
            ax1.text(x+dx, y-2*dy,'runstats median', color='k', **kwt)
            ax1.plot(x-dx, y-3*dy, 'yo',  **kwp)
            ax1.text(x+dx, y-3*dy,'runstats pts', color='y', **kwt)
            ax1.set_xlim(self.binset.dday[0], self.binset.dday[-1])
            ax1.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))

        else:
            ax1.plot(self.mid_times, self.mid_dh,'k.',ms=4)
            ax1.text(x+dx, y-3*dy,'runstats pts', color='k', **kwt)
            ax1.set_xlim(self.binset.dday[0], self.binset.dday[-1])
            ax1.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))

        ax1.set_title('heading correction (reliable-accurate)')
        ax1.set_xlim(self.binset.dday[0], self.binset.dday[-1])

        ax2=ff.add_subplot(212, sharex=ax1)
        if detailed:
            ax2.plot(self.binset.dday, 0.0*self.dh + self.mingood,'r.', ms=4)
            ax2.plot(self.binset.dday, self.RS_dh.ngood,'c')
            ax2.plot(self.mid_times, self.mid_n,'yo')
            ax2.set_title('number of good points')
        else:
            ax2.plot(self.mid_times, 0*self.mid_n+self.mingood,'r-.')
            ax2.plot(self.mid_times, self.mid_n,'k.',ms=4)

        ax2.set_title('number of good points')
        ax2.text(.98, .4, 'numgood cutoff', color='r', ha='right',
                  transform=ax2.transAxes)
        ax2.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        ax2.set_xlim(self.binset.dday[0], self.binset.dday[-1])

        self.fig = ff
        self.ax1=ax1
        self.ax2=ax2

        plt.draw()


    #------------

    def print_stats_summary(self):
        '''
        return a list of strings
        '''

        ## get some time info here (for printing and plotting)
        self.start_utc = self.binset.dday[0]
        self.end_utc =  self.binset.dday[-1]

        dd = to_date(self.yearbase, self.start_utc)
        self.start_ymdhms_str = '%4d/%02d/%02d %02d:%02d:%02d' % (
            dd[0],dd[1],dd[2],dd[3],dd[4],dd[5])
        self.start_ymdhms = dd

        dd = to_date(self.yearbase, self.end_utc)
        self.end_ymdhms_str = '%4d/%02d/%02d %02d:%02d:%02d' % (
            dd[0],dd[1],dd[2],dd[3],dd[4],dd[5])
        self.end_ymdhms = dd

        slist = [] #bugfix 2015 addressed the actual difference.  Now 2.5 years
        # later the comment in the daily email (stats summary file) is correct too.
        s = '%s-%s statistics (comment=same sign as cal/rotate/*ang)' % (
                     self.rhead_inst, self.hcorr_inst)
        if self.hcorr_msg == 'pmv':
            s+= ' (acc_heading_cutoff is %4.3f)' % (self.acc_heading_cutoff)
        slist.append(s)
        slist.append('')

        slist.append('ddrange: %10.7f to %10.7f' % (
                self.start_utc, self.end_utc))
        slist.append('(%s to %s)' % (self.start_ymdhms_str, self.end_ymdhms_str))

        ## QC notes for heading correction
        self.get_rbin_stats() # ptsPG
        s = 'all %s messages:  (%d%%)  were good' % (self.hcorr_inst, self.ptsPG)
        if self.hcorr_msg in ('hdg', 'rdi', 'psxn23'):
            s+= '  [QC does not exist for this instrument]'
        else:
            s+= '  [using available QC]'
        slist.append(s)


        slist.append('')
        slist.append('(%ssec) ensemble heading corrections:' % (
                self.out_stepsec))
        slist.append('   %d out of %d   (%d%%) were good' % (
                self.ensnumgood, self.ensnumtotal, self.enspercent))
        slist.append('statistics of good data:')
        S = Stats(self.mid_n, masked=False)
        slist.append('   mean N = %.0f, stddev N =  %.1f' % (S.mean, S.std))
        slist.append('   min  = %4.2f, max = %4.2f'
                     % (self.mid_dh.min(), self.mid_dh.max()))
        S = Stats(self.mid_dh, masked=False)
        slist.append('   mean = %3.2f, stddev = %4.2f' % (S.mean,S.std))

        slist.append('')


        return slist
    #------------
    def print_hcorr(self, outfilebase='hbin', save_interp=False,
                    overwrite=False):
        '''
        print files for codas processing, equivalent to post_headcorr
        eg. hcorr.ang, hcorr.asc

        if 'timefile' is present, use first column for times.

        save_interp=True : interpolates through bad data holes
        '''

        suffixes = ['.asc', '.ang']
        if save_interp:
            suffixes.append('_interp.ang')
            suffixes.append('_interp.asc')
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
                '% sign is correct for use with "rotate": reliable-accurate',
                '',
                ''.join(['%enddday, mean head, last head, ',
                        'dhfix, stddh, ndh, badmask(bad==1) persist_win']),
                ''])

        enddday = self.ensdday
        # not masked
        numens = len(self.ensdday)

        # This can be simplified by eliminating the "where" and using
        # the mask directly.
        mid_dh_mask = np.ma.getmaskarray(self.mid_dh)
        goodi =  np.where(~mid_dh_mask)[0]
        badi  =  np.where(mid_dh_mask)[0]

        mean_head = interp1(self.binset.dday, self.RS_rhead.mean,
                                              self.mid_times,
                                              max_dx = self.max_dt,
                                               )
        last_head = interp1(self.binset.dday, self.rhead, enddday,
                                              max_dx = self.max_dt,
                                                )

        # take out masks so we don't get any NaNs when we print
        dhfix0         = np.zeros((numens),float)
        dhfix0[goodi]  = self.mid_dh[goodi]

        # stage this for save_interp
        # interpolate bad stuff; then take out NaNs
        dhfix_interp = dhfix0.copy()
        dhfix_interp[badi]   = interp1(enddday[goodi], dhfix0[goodi],
                                       enddday[badi],
                                       max_dx = self.max_dt,
                                       )

        # should only be at the ends; could extrapolate
        dhfix_interp[np.where(np.isnan(dhfix_interp))[0]] = 0.0

        stddh         = np.zeros((numens),float)
        stddh[goodi]  = self.mid_dhstd[goodi]


        ndh  = np.zeros((numens),float)
        ndh[goodi] = np.round(self.mid_n[goodi])
        ndhi = np.zeros((numens),int)
        ndhi[:] = ndh[:]

        badmask   = np.ones((numens),int)  #ones are bad
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


        # write out original estimates, with zeros where bad
        if save_interp:
            F=open(outfilebase+'_interp.asc','w')
            F.write(header)
            for ll in zip(enddday,
                          mean_head,
                          last_head,
                          dhfix_interp,
                          stddh,
                          ndh,
                          badmask,
                          persist_win):
                F.write('%10.7f %9.3f %9.3f %7.3f %7.3f %4d  %4d %4d\n'%(ll))
            F.close()


            F=open(outfilebase+'_interp.ang','w')
            for ll in zip(enddday, dhfix_interp):
                F.write('%10.7f   %5.3f \n' %(ll))
            F.close()
