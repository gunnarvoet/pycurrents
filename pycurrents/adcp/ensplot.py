"""
Plot data from a single ensemble in UHDAS.

| TODO:
|    handle missing data:
|        check for data availability
        fall back on "no data available" text plot


"""

## The line block in the docstring doesn't seem to be handled
## correctly by Sphinx; it is generating a warning, and
## the leading space is not being preserved.

import os
import time
import numpy as np
import logging
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.patches import FancyArrow

# for file handling and data manipulation
from pycurrents.adcp.reader import Binsuite
from pycurrents.adcp.uhdas_defaults import annotate_time_color
from pycurrents.plot.mpltools import nowstr, shorten_ax
from pycurrents.num.stats import Stats
from pycurrents.codas import to_date, to_day
from pycurrents.plot.mpltools import savepngs
from pycurrents.plot.mpltools import get_extcmap
from pycurrents.system.misc import Bunch
#############################################################################

# Standard logging
_log = logging.getLogger(__name__)


def npz_lastens(prefix=None, path='./'):
    from pycurrents.system import Bunch
    fn = os.path.join(path, prefix + ".npz")
    age = time.time() - os.path.getmtime(fn)
    npz = np.load(fn)
    lastens = Bunch(npz, age_secs=age)
    uship = np.ma.masked_invalid(lastens.uship)
    vship = np.ma.masked_invalid(lastens.vship)
    #avg_amp = lastens.avg_amp # new 2016/02
    # Ensplot wants u, v with their original masks:
    mask = lastens.instpflag & 1
    lastens.u = np.ma.array(lastens.u + uship[:,np.newaxis], mask=mask)
    lastens.v = np.ma.array(lastens.v + vship[:,np.newaxis], mask=mask)
    # Add masking from uship:
    lastens.instpflag |= np.ma.getmaskarray(uship)[:,np.newaxis]
    # The uship calculation always masks the first point;
    # maybe we should adjust for this, so that PG can max out at 100.
    return lastens


def add_quiverkey(ax, MQ, ms_keyspeed, kts_keyspeed):
    # specialized for vector profile plot

    xlegend = .25
    ylegend_ms = .17
    ylegend_kts = .13
    coordinates = 'figure'
    labelpos = 'W'
    linewidth = 0.5

    qstr = '%2.1f m/s' % (ms_keyspeed)
    ax.quiverkey(MQ, xlegend , ylegend_ms , ms_keyspeed,
                      qstr , color='k',
                      labelpos=labelpos,
                      linewidth=linewidth,
                      coordinates=coordinates)

    qstr = '%2.1f kts' % (kts_keyspeed)
    ax.quiverkey(MQ, xlegend , ylegend_kts ,kts_keyspeed*.52,
                      qstr , color='k',
                      labelpos=labelpos,
                      linewidth=linewidth,
                      coordinates=coordinates)



class Ensplot:
    ''' method to plot amp, vel, pg from a short segment of
            navigated, rotated, edited single-ping data.
            designed for "lastens" from uhdas underway data.

    E=Ensplot(
            # to read lastens:
            basename = 'lastens',
            path = '.',
            read_fcn = 'npz_lastens',  #'binsuite', (see note below)
            # or to specify data:
            data = None,
            #
            cruiseid = 'uhdas',
            proc_yearbase = None,
            top_plotbin = 1,  #python bin number (0,1,2,3...)
            num_refbins = 2,
            pingwarnN = None,  # if present, splash a warning if fewer
            colorscheme = 'day',    # used in ktvec, ktprof
            procdirname = 'ADCP',
            climdict = {'amp':None, 'vel':None, 'pg':[0,100]},
            verbose = False)

    # make the plots:
    E()                                               # Part1: instantiate
    E(plotname='ampuvpg')
    E(plotname='ktvec')
    E(plotname='kt_vecprof')           ## see run_lastensq for examples


    To change from day to night colorscheme, do this:


     E.colorscheme='night'
     E.set_colors(E.colorscheme)
     E(plotname = 'ktvec')


    if passing in data, it must have
        - timeseries x,y,T
        - vertical profile z
        - velocities u,v amp

    '''
    def __init__(self,
                 # to read lastens:
                 basename = 'lastens', path = '.', read_fcn = 'npz_lastens',
                 # if pre-forming data and passing it in:
                 data = None,
                 cruiseid = 'uhdas',
                 proc_yearbase = None,
                 timeout = None,
                 pingwarnN = None,
                 scalefactor = 'm/s',
                 top_plotbin = 1, #start the vertical binning here; python index
                 num_refbins = 2,
                 colorscheme = 'day',
                 procdirname = 'ADCP',
                 climdict = {'amp':None, 'vel':None, 'pg':[0,100]},
                 altdirs = None, ## directory to save figures
                 verbose = False):

        if data is None:
            # read the data
            self.path = path
            self.read_fcn = read_fcn
            self.data, self.age_secs = self.read_data(read_fcn, basename)  #uses path, above
            self.pg, self.origpg  = self.get_pg()
            self.u_edited, self.v_edited = self.edit_uv()
            self.proc_yearbase = proc_yearbase
            self.dhstr = self.get_hcorr()
        else:
            self.data = data
            self.proc_yearbase = self.data.yearbase
            self.pg = self.data.pg
            self.orig_pg = self.data.pg
            self.u_edited = Stats(self.data.u, axis=0).mean
            self.v_edited = Stats(self.data.v, axis=0).mean
            self.age_secs = 0
            self.dhstr = ''

        self.ylim=[self.data['dep'].max(), 0]   #should change to d0
        self.procdirname = procdirname
        self.verbose = verbose
        self.timeout = timeout
        self.pingwarnN = pingwarnN
        self.scalefactor = 'm/s'
        self.colorscheme = colorscheme
        self.set_colors(colorscheme)   ## used in kt_vecprof ktprof
        self.top_plotbin = top_plotbin
        self.num_refbins = num_refbins
        self.climdict=climdict
        self.altdirs = altdirs
        self.set_timestring()

        loc = MaxNLocator(nbins=6)
        self.yticks = loc.tick_values(0, self.data['dep'].max())

        self.scale_factors = {'m/s'  : 1, # leave as m/s
                              'cm/s' : 100,      # m/s to cm/s
                              'kts'  :  1/0.51}  # m/s to kts


        if self.scalefactor not in list(self.scale_factors.keys()):
            raise ValueError(__doc__ + '\n\nbad scalefactor.  chose from "m/s", "cm/s", "kts"')

    #-----------
    def __call__(self, plotname=None, kts_text = '', zbin=5, vcolor=None):
        '''
        plotname: choose from :
            ampuvpg
            ktvec
            kt_vecprof
        '''
        ## these figure names are assumed (used) in 'save' method
        if plotname == 'ampuvpg':
            # 5-minute profile
            self.set_timestring()
            self.fig1= self.plot_ampuvpg()
            plt.draw_if_interactive()

        elif plotname == 'ktvec':
            #NOTE: This will store vector data in self.ktvec_data
            # bridge plots
            self.set_timestring()
            self.kts_text = kts_text
            self.fig2 = self.plot_ktprof()
            plt.draw_if_interactive()

            self.fig3 = self.plot_ktvec2()
            plt.draw_if_interactive()

        elif plotname == 'kt_vecprof':
            # profile of vectors
            #NOTE: This will use vector data in self.ktvec_data
            self.set_timestring()
            self.fig5 = self.plot_vecprof_ktvec(zbin=zbin, vcolor=vcolor)
            plt.draw_if_interactive()

        else:
            raise ValueError('must use a plotname from ("ampuvpg", "ktvec", "kt_vecprof")')


    #-----------
    def set_colors(self, colorscheme):
        ''' only used in ktvec, ktprof, kt_vecprof '''
        self.c_annot   = 'k'
        self.c_plot    = 'b'
        self.c_axface  = 'w'
        self.c_figface = 'w'
        # override with reds if required
        if colorscheme == 'night':
            self.c_annot   = 'y'
            self.c_plot    = 'c'
            self.c_axface  = (.5,.1,.1)
            self.c_figface = (.8,.1,.1)

    #-----------
    def set_timestring(self):

        if self.proc_yearbase is None:
            nowtime = time.localtime()
            data_dday = self.data['corr_dday'][-1]
            y,m,d,hh,mm,ss=to_date(nowtime[0], data_dday)
            self.timestring = 'jday %03d %02d:%02d:%02d UTC' % (data_dday+1, hh,mm,ss)
        else:
            y,m,d,hh,mm,ss=to_date(self.proc_yearbase,
                                   self.data['corr_dday'][-1])
            self.timestring = '%04d/%02d/%02d %02d:%02d:%02d UTC' % (y,m,d,hh,mm,ss)


        tt=time.localtime()
        dday_data = to_day(y,y,m,d,hh,mm,ss)
        dday_now  = to_day(y, tt[0],tt[1],tt[2],tt[3],tt[4],tt[5])
        self.minutes_ago = (dday_now - dday_data)*1440.
        self.agostr = ' (%3.1f min ago)' % (self.minutes_ago,)

        if self.verbose:
            _log.debug('proc_yearbase is %s' , self.proc_yearbase)
            _log.debug('last data time   %s', self.timestring)
            _log.debug('computer says    %s', nowstr())


    #-----------
    def _set_y_ticks(self, ax):
        ax.set_ylim(self.ylim)
        ax.set_yticks(self.yticks)

    #-----------
    def save_fig(self, outfilebase, fig=None, dpi = [70, 40], altdirs=None):
        # generic
        if altdirs is None:
            altdirs = self.altdirs
        pngfile = '%s.png' % (outfilebase,)
        thumbfile = '%s_thumb.png' % (outfilebase)
        savepngs([pngfile, thumbfile], dpi, fig=fig, altdirs=altdirs)
    #-----------
    def read_data(self, read_fcn, basename):
        if read_fcn == 'binsuite':
            bs = Binsuite(prefix=basename, path = self.path)
            lastens = bs.data
            age_secs = bs.age_secs
            if 'proc_yearbase' in lastens:
                self.proc_yearbase = int(lastens['proc_yearbase'][0])

        elif read_fcn == 'npz_lastens':
            lastens = npz_lastens(prefix=basename, path=self.path)
            age_secs = lastens.age_secs
        else:
            _log.error(' data scheme not chosen')
            raise NotImplementedError('must choose read_fcn:\n%s' % (__doc__,))
        return lastens, age_secs


    #-----------
    def get_pg(self):
        goodmask = ~self.data['instpflag'].astype(bool) # True if good

        # figure out where PG is good'
        ngood = goodmask.astype(int).sum(axis=0)
        pg = 100.0 * ngood / goodmask.shape[0]

        goodorigmask = ~np.ma.getmaskarray(self.data['u'])
        ngoodorig = goodorigmask.astype(int).sum(axis=0)
        origpg = 100.0 * ngoodorig / goodorigmask.shape[0]

        return pg, origpg


    #-----------
    def get_hcorr(self):
        try:
            dhmean = self.data.dh  # from npz file
        except AttributeError:
            dhmean = (self.data['heading_used']-self.data['heading']).mean()
        dhstr = '%5.2f' % (dhmean)
        return dhstr


    #-----------
    def plotamp(self, ax):
        ''' pcolor plot on the left
        '''
        if self.climdict['amp'] is None:
            var_range = [50, 170]
        else:
            var_range = self.climdict['amp']
        dday = self.data['corr_dday']
        tr = [0, 86400 * (2*dday[-1] - dday[-2] - dday[0])]
        d = self.data['dep']
        delta_d = d[1] - d[0]
        dr = [d[0]-0.5*delta_d, d[-1]+0.5*delta_d]

        self.cplot = ax.pcolorfast(tr, dr,
                                    self.data['amp1'].T,
                                    cmap = get_extcmap(name='jet'), #FIXME
                                    vmin=var_range[0] , vmax=var_range[1])

        ax.set_xlabel('seconds\n(%d pings)' % (len(dday)))
        ax.set_ylabel('depth (m)')

        loc = MaxNLocator(nbins=3, integer=True)
        ax.xaxis.set_major_locator(loc)
        self._set_y_ticks(ax)

        self.cbar=plt.colorbar(self.cplot,extend='both', aspect=30,
                               use_gridspec=False) #2014/07/10
        self.cbar.set_label('')


        ## TODO: use one of the APIs for adjusting subplot parameters:
        ## rcParams, plt.subplots_adjust, fig.subplots_adjust,
        ## or fig.subplotpars.
        shorten_ax(ax, .15)
        shorten_ax(self.cbar.ax,.15)

        ax.set_title('Signal Strength')


    #----------- velocity ------
    def edit_uv(self):
        editmask = self.data['instpflag'].astype(bool)
        # don't really need Stats for a simple mean; but it's OK
        ustats= Stats(np.ma.array(self.data['u'], mask=editmask), axis=0)
        vstats= Stats(np.ma.array(self.data['v'], mask=editmask), axis=0)

        ## TODO : need to do something useful if there is no good data

        u = np.ma.masked_where(self.pg<50, ustats.mean, copy=1)
        v = np.ma.masked_where(self.pg<50, vstats.mean, copy=1)
        return u, v


    def plot_uvprof(self, ax):
        ''' plot u,v profiles (center)
        '''
        shorten_ax(ax, .15)

        vel_scalefactor = self.scale_factors[self.scalefactor]

        u = self.u_edited * vel_scalefactor
        v = self.v_edited * vel_scalefactor

        ax.plot(u, self.data['dep'],'r')
        ax.plot(v, self.data['dep'],'b')

        self._set_y_ticks(ax)
        ax.set_yticklabels([])
#        loc = MaxNLocator(nbins=4, integer=True, symmetric=True)
        maxuv = max(np.abs(u).max(), np.abs(v).max())
        integer_only = (maxuv > 0.5)
        loc = MaxNLocator(nbins=4, integer=integer_only, symmetric=True,
                  steps=[1, 2, 3, 5, 10])

        ax.xaxis.set_major_locator(loc)
        ax.autoscale_view(scaley=False)

        ax.set_title('Ocean Velocity')
        ax.set_xlabel(self.scalefactor)
        ax.grid()

        ax.text(.05, .05, 'U (east)', transform = ax.transAxes,
                   color='r', fontsize=12,weight='bold')
        ax.text(.95, .10, 'V (north)', transform = ax.transAxes,
                   color='b', fontsize=12, ha='right',weight='bold')


    #----------- percent good ------

    def plot_pg(self, ax):
        ''' PG plot on the right
        '''
        shorten_ax(ax, .15)

        ax.plot(self.pg, self.data['dep'],'g.')
        ax.plot(self.origpg, self.data['dep'],'k')

        ax.set_title('Percent Good')
        ax.set_xlim(0,105)
        ax.text(.98,.03,'PG(percent)', ha='right', color='g',
                transform=ax.transAxes)
        ax.tick_params('x', colors='g')
        self._set_y_ticks(ax)
        ax.grid()
        ax.yaxis.tick_right()

    #-----------

    def plot_avgamp(self, ax):
        '''
        overlay average amplitude on PG
        '''
        blue = [.4,.4,1]
        darker_blue = [.2,.2,1]
        ax2=ax.twiny()
        shorten_ax(ax2, .15)

        ax2.plot(self.data.avg_amp, self.data.dep, '-', color=blue,
                 lw=4, alpha=.5)
        ax2.set_ylim(ax.get_ylim())
        #
        if self.climdict['amp'] is None:
            var_range = [50, 170]
        else:
            var_range = self.climdict['amp']
        ax2.set_xlim(var_range)
        ax2.text(.05,.95,'Signal\nStrength\n(RSSI)', ha='left', va='top',
                 color=blue, weight='bold', transform=ax2.transAxes, size=12)
        #
        self._set_y_ticks(ax2)
        ax2.yaxis.tick_right()
        ax2.set_xticks([])
        #
        # now make a parasite axis for amp labels
        newax = ax2.twiny()  # create new axis
        newax.patch.set_visible(False)
        newax.set_frame_on(False)
        newax.xaxis.set_ticks_position('bottom')
        newax.xaxis.set_label_position('bottom')
        newax.spines['bottom'].set_position(('axes', 0.1))
        newax.set_xlim(ax2.get_xlim())
        newax.set_ylim(ax2.get_ylim())
        newax.tick_params('x', colors=darker_blue)
        newax.set_xlabel('RSSI (counts)', color=darker_blue)



    #-----------

    def plot_ampuvpg(self):
        '''
        assemble amp, uv, pg plot from lastens
        '''
        fig = plt.figure(figsize=(7,5))
        if self.timeout is not None:
            if self.age_secs > 2*self.timeout:
                fig.set_facecolor([1,0,.3])
            elif self.age_secs > self.timeout:
                fig.set_facecolor('orange')

        ## plot amplitude
        ax1 = fig.add_subplot(131)
        self.plotamp(ax1)
        if self.pingwarnN is not None:
            dday = self.data['corr_dday']
            numpings = len(dday)
            if numpings< int(self.pingwarnN):
                kwargs=dict(color='r', ha='center')
                fig.text(.5,.5,'WARNING', fontsize=114, alpha=0.7,**kwargs)
                fig.text(.52,.38, '%d' % numpings,fontsize=64, alpha=0.9, **kwargs)
                fig.text(.52,.31, 'pings',  fontsize=44, alpha=0.9, **kwargs)
                _log.info('warning: has %d pings in ensemble' % (numpings))

        ## plot uv profile
        ax2 = fig.add_subplot(132)
        self.plot_uvprof(ax2)

        ## plot PG; run before vel
        ax3 = fig.add_subplot(133)
        self.plot_pg(ax3)
        self.plot_avgamp(ax3)


        figtext = '%s (dday = %5.3f)\nheading correction: %s deg, %s' % (
            (self.procdirname, dday[-1], self.dhstr, self.timestring))
        _log.info(figtext)
        fig.text(.5,.03, figtext, fontsize=12, weight='bold',
                 ha='center', color=annotate_time_color)


        return fig

    #------ vector profile with key ----------

    def plot_vecprof_ktvec(self, zbin=5, vcolor=None, vecscale=None):
        ''' 2 axes, vecprof and ktvec'''
        if vcolor:
            self.c_plot = vcolor
            self.c_axface  = 'w'
            self.c_figface = 'w'
        fig, ax = plt.subplots(figsize=(8,8), ncols=2,
                               facecolor=self.c_figface, edgecolor=self.c_figface)
        ax[0].set_facecolor(self.c_axface)
        ax[1].set_facecolor(self.c_axface)

        plt.subplots_adjust(top=.85)
        ## makes self.ktvec_data
        self.plot_ktvec2(fig=fig, ax1=ax[1], xtext=.75, textsize=18, ytextshift=.15)

        ## uses self.ktvec_data
        self.plot_vecprof(fig=fig, ax=ax[0], zbin=zbin, vecscale=vecscale)
        fig.text(.5,.05, 'decimal day %5.3f' % (self.data.corr_dday[-1]),
                       fontsize=14, weight='bold', ha='center',
                       color=annotate_time_color)

        return fig

    #---------

    def plot_vecprof(self, fig=None, ax=None, zbin=5, vecscale=None):
        ''' smooth over this many bins: zbin
        '''

        vel_scalefactor = self.scale_factors[self.scalefactor] # m/s

        u = self.u_edited * vel_scalefactor
        v = self.v_edited * vel_scalefactor

        isgood = ~np.ma.getmaskarray(u)
        ngood = isgood.sum()
        nused = ngood - ngood % zbin
        nsegs = nused // zbin

        if nsegs:
            ugood = u.compressed()[:nused]
            vgood = v.compressed()[:nused]
            zgood = np.ma.getdata(self.data.dep[isgood])[:nused] #ndarray

            shape = (nsegs, zbin)
            usm = ugood.reshape(shape).mean(axis=1)
            vsm = vgood.reshape(shape).mean(axis=1)
            zsm = zgood.reshape(shape).mean(axis=1)
            maxuv = np.abs(np.hstack((usm, vsm))).max()

            if vecscale is None: #autoscale
                # vectors are in m/s, ms_vecscale is in m/s
                # kts_vecscale should be about the same length in m/s
                #     so pick nice numbers in kts, for the label,
                #     and scale the vector by .52
                if maxuv > 2:
                    vecscale = 3
                    ms_keyspeed = 2.
                    kts_keyspeed = 4.

                if maxuv > 1:
                    vecscale = 2
                    ms_keyspeed = 1.
                    kts_keyspeed = 2.
                else:
                    vecscale = 0.5
                    ms_keyspeed = 0.2
                    kts_keyspeed = 0.5
            else:
                vecscale = float(vecscale)
                ms_keyspeed = vecscale
                kts_keyspeed = vecscale*2

        else:
            vecscale = 1

        if fig is None:
            fig = plt.figure(figsize=(4,6),
                             facecolor=self.c_figface,
                             edgecolor=self.c_figface)
        if ax is None:
            ax = fig.add_axes([0.15,0.18,.75, .7])

        if nsegs:
            ax.grid(True)
            par2 = ax.twiny()
            par2.vlines(0, self.data.dep[0], self.data.dep[-1], 'k', lw=.5)
            par2.plot(0*zsm, zsm, 'k.', ms=3)
            # get rid of xticks
            ax.get_xaxis().set_ticks([])
            par2.get_xaxis().set_ticks([])
            # quiver in color  (m/s)

        _log.info('vecprof: vecscale is %2.1f' % (vecscale))
#        scale=1/vecscale
        if nsegs:
            ax.quiver(0*zgood, zgood,
                  ugood,  # do not scale velocities here; use 'scale'
                  vgood,  # do not scale velocities here; use 'scale'
                  lw=0, #thickness of edgeline
                  scale_units='width',  # arrow width
                  width=.002,
                  color=(.7,.7,.7),
                  scale=vecscale,         #vector length
                  clip_on=False)

        if nsegs:
            MQ = ax.quiver(0*zsm, zsm,
                      usm, # do not scale velocities here; use 'scale'
                      vsm, # do not scale velocities here; use 'scale'
                      -zsm,
                      cmap = 'coolwarm',
                      lw=1,
                      width=.015,
                      scale_units='width',
                      edgecolor='k',
                      scale=vecscale,
                      clip_on=False)


        if hasattr(self, 'ktdir_data'):
            ax.quiver(0, self.ktdir_data.z ,
                      self.ktdir_data.u, #do not scale velocities here
                      self.ktdir_data.v, #do not scale velocities here
                      lw=0, #thickness of edgeline
                      scale_units='width',
                      width=.01,
                      color=self.c_plot,
                      scale=vecscale,         #vector length
                      clip_on=False)

        ax.set_xlim([-vecscale, vecscale])  # use vecscale for axes
        ax.invert_yaxis()
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4,symmetric=True))

        ax.set_ylabel('depth, meters')

        # use a quiverkey
        if nsegs:
            add_quiverkey(ax, MQ, ms_keyspeed, kts_keyspeed)

        if ngood:
            fig.text(.5, .96,
            'Vector profile: each depth has speed and direction.',
                      ha='center', size=15)
        else:
            ax.text(0.5, 0.5, 'No valid data', transform=ax.transAxes,
                     ha='center', va='center', fontsize='xx-large')

        if nsegs:
            fig.text(.5, .93, 'Colors have no quantitative meaning; North is "up"',
                      ha='center', size=15)
            fig.text(.6, .82, 'red: shallow bins', ha='left', size=15, color='r')
            fig.text(.6, .79, 'blue: deep bins', ha='left', size=15, color='b')

        return fig


    #----------------

    def plot_ktprof(self):

        plt.rc(('xtick', 'ytick'), color=self.c_annot)
        plt.rc('axes', edgecolor=self.c_annot, labelcolor=self.c_annot)
        fig = plt.figure(facecolor=self.c_figface, edgecolor=self.c_figface)
        pos1 = [0.125, 0.1, 0.35, 0.8]
        pos2 = [0.55,  0.1, 0.35, 0.8]

        try:
            ax1 = fig.add_axes(pos1, facecolor=self.c_axface)
            ax2 = fig.add_axes(pos2, facecolor=self.c_axface, sharey=ax1)
        except AttributeError:  # old mpl
            ax1 = fig.add_axes(pos1, axisbg=self.c_axface)
            ax2 = fig.add_axes(pos2, axisbg=self.c_axface, sharey=ax1)

        shorten_ax(ax1, .2)
        shorten_ax(ax2, .2)

        uv2 = self.u_edited**2 + self.v_edited**2
        uvmag = np.ma.sqrt(uv2)
        uvangle = np.ma.arctan2(self.v_edited, self.u_edited)
        # Compass direction in degrees, -180 to 180:
        uvdir = np.ma.remainder((360 + 90 - uvangle*180/np.pi), 360.0)
        # make it go [-180 to 180]
        uvdir = np.ma.remainder(uvdir+180,360)-180

        uvmag = uvmag/0.51  # m/s to kts

        ax1.plot(uvmag, self.data['dep'], color=self.c_plot)
        self._set_y_ticks(ax1)

        if np.max(uvmag) > 2:
            uvticks = np.linspace(0,4,9)
        else:
            uvticks = np.linspace(0, 2, 5)

        ax1.set_xticks(uvticks)
        ax1.set_xlim(uvticks[0], uvticks[-1])
        ax1.set_title('Ocean Velocity Magnitude', color=self.c_annot)

        ax1.set_xlabel('Kts', color=self.c_annot)
        ax1.grid()

        ax2.plot(uvdir, self.data['dep'], color=self.c_plot, marker='.')
        self._set_y_ticks(ax2)

        uvticks = [-180,-90,0,90,180]
        ax2.set_xticks(uvticks)
        ax2.set_xlim(-200,200)
        ax2.set_title('Direction (True)', color=self.c_annot)
        ax2.set_xticklabels(['S','W','N','E','S'])
        ax2.set_xlabel('direction\n(current goes towards)', color=self.c_annot)
        ax2.grid()

        fig.text(.5,.05,'%s\n heading correction: %s deg, %s' %
                    (self.procdirname,
                        self.dhstr, self.timestring),
                   fontsize=14, weight='bold', ha='center',
                   color=annotate_time_color)
        plt.rcdefaults()
        return fig

    #----------------
    ## plot_ktvec used a circle (like a radar circle) to show speed;
    ##   vetoed by the Bridge (still exists in the repo, removed 6/2014

    def plot_ktvec2(self, fig=None, ax1=None, xtext=0.5, textsize=22, ytextshift=0):
        """ Create bridge/surface currents plot.

        Parameters
        ----------
        fig : Figure, optional
        ax1 : Axes, optional
        xtext : float, optional
        textsize : int, optional
        ytextshift : int, optional

        Returns
        -------
        fig
            Figure displaying bridge plot.
        """
        vecscale = None
        refbins = self.top_plotbin + np.arange(self.num_refbins)  # eg.1 + [0,1,2]

        plt.rc(('xtick', 'ytick'), color=self.c_annot)
        plt.rc('axes', edgecolor=self.c_annot, labelcolor=self.c_annot)

        if fig is None:
            fig = plt.figure(facecolor=self.c_figface, edgecolor=self.c_figface)
        if ax1 is None:
            pos1 = [0.2, 0.2, .6,  0.6]
            try:
                ax1 = fig.add_axes(pos1, facecolor=self.c_axface)
            except AttributeError:   # old mpl
                ax1 = fig.add_axes(pos1, axisbg=self.c_axface)

        ubinstats = Stats(self.data['u'][:,refbins], axis=0)
        vbinstats = Stats(self.data['v'][:,refbins], axis=0)

        # set vector scale; these are m/s
        urefstats = Stats(ubinstats.mean)
        vrefstats = Stats(vbinstats.mean)


        uv2 = urefstats.mean**2 + vrefstats.mean**2
        if uv2 is not np.ma.masked:
            u = urefstats.mean
            v = vrefstats.mean

            u_kts = u/0.51
            v_kts = v/0.51

            uvmag = np.ma.sqrt(uv2) #mps
            uvangle = np.ma.arctan2(v,u)
            uvmax = np.max((np.abs(u),np.abs(v)))
            # Compass direction in degrees, -180 to 180:
            uvdir = np.ma.remainder((360 + 90 - uvangle*180/np.pi), 360.0)


            uvmag_kts = uvmag/0.51  # m/s to kts
            uvmax_kts = uvmax/0.51

            # do the whole plot in kts
            vecscale=.2 + uvmag_kts

            ax1.plot([0 , u_kts], [0, v_kts], self.c_plot, lw=3)
            ax1.plot([0], [0],'o', color=self.c_plot )
            ax1.set_xlim([-1,1])
            ax1.set_ylim([-1,1])

            ax1.set_autoscale_on(False)

            arrowlen = .15*uvmax_kts
            arrow_angle = 30*np.pi/180.

            line1x = [u_kts, u_kts+arrowlen*np.cos(np.pi+uvangle - arrow_angle)]
            line1y = [v_kts, v_kts+arrowlen*np.sin(np.pi+uvangle - arrow_angle)]

            line2x = [u_kts, u_kts+arrowlen*np.cos(np.pi+uvangle + arrow_angle)]
            line2y = [v_kts, v_kts+arrowlen*np.sin(np.pi+uvangle + arrow_angle)]

            ax1.plot(line1x, line1y, self.c_plot, lw=2)
            ax1.plot(line2x, line2y, self.c_plot, lw=2)

            # crosshair
            ax1.plot([-vecscale, vecscale], [0,0],'k')
            ax1.plot([0,0], [-vecscale, vecscale], 'k')
            ax1.set_xlim(-vecscale, vecscale)
            ax1.set_ylim(-vecscale, vecscale)
            ax1.set_yticks([])
            ax1.set_xticks([])

            # add labels
            ax1.text(0.5, 1.02, 'N', ha='center', size=14, transform = ax1.transAxes)
            ax1.text(0.5, -.02, 'S', ha='center', va='top', size=14, transform = ax1.transAxes)
            ax1.text(1.02, .5, 'E', ha='left', size=14, transform = ax1.transAxes)
            ax1.text(-.02, .5, 'W', ha='right', size=14, transform = ax1.transAxes)

            #add boat
            #ship_heading_stats = Stats(self.data.heading)
            #ship_heading = Stats(ship_heading_stats.mean)
            ship_heading = np.ma.remainder((90 - self.data.heading[-1]), 360.0)
            sh_dir = ship_heading*np.pi/180
            sh_dx = (0.5*vecscale) * np.cos(sh_dir)
            sh_dy = (0.5*vecscale) * np.sin(sh_dir)
            fancy_arrow = FancyArrow(-sh_dx, -sh_dy, 2*sh_dx, 2*sh_dy, width = 0.15*vecscale,
                                     length_includes_head=True, head_width=0.15*vecscale,
                                     head_length=0.15*vecscale, alpha=0.2,
                                     facecolor='0.2', edgecolor='k')
            ax1.add_artist(fancy_arrow)

            #key, lower left corner
            vec_keyspeed = .5
            u_key = vec_keyspeed
            v_key = 0
            x_key = -.9*vecscale
            y_key = -.9*vecscale
            arrowlen = 0.15*vec_keyspeed

            line1x = [x_key + u_key,
                      x_key + u_key + arrowlen*np.cos(np.pi-arrow_angle)]
            line1y = [y_key + v_key,
                      y_key + v_key + arrowlen*np.sin(np.pi-arrow_angle)]

            line2x = [x_key + u_key,
                      x_key + u_key + arrowlen*np.cos(np.pi+arrow_angle)]
            line2y = [y_key + v_key,
                      y_key + v_key + arrowlen*np.sin(np.pi+arrow_angle)]



            ax1.plot([x_key , x_key+u_key] , [y_key, y_key+v_key],
                     color=self.c_annot)
            ax1.plot([x_key], [y_key], 'o', mfc=self.c_annot, mec=self.c_annot)
            ax1.plot(line1x, line1y, self.c_annot)
            ax1.plot(line2x, line2y, self.c_annot)

            ax1.text(x_key+.1*vecscale, y_key+.1*vecscale,
                     '%2.1f kts' % (vec_keyspeed,),
                       color=self.c_annot)

            # TODO: add in ship heading here
            tstr = '%2.1f kts, %.0f degT \n ship heading %.0f degT' % (uvmag_kts, uvdir, self.data.heading.mean())
            fig.text(xtext,.88 - ytextshift, tstr, fontsize=textsize,
                     weight='bold', ha='center',
                     color=annotate_time_color)

        else:
            fig.text(xtext,.05,'No valid data',
                       fontsize=14, weight='bold', ha='center',
                       color=self.c_annot)

        ax1.set_aspect('equal', adjustable='box')
        rangestr = '%d-%d m' % (np.round(self.data['dep'][refbins[0]]) ,
                                np.round(self.data['dep'][refbins[-1]]))

        if len(self.procdirname) < 10:
            tstr1 = '%s Ocean Velocity (%s)' % (self.procdirname, rangestr)
        else:
            tstr1 = '%s\nOcean Velocity (%s)' % (self.procdirname, rangestr)
            ytextshift -= 0.05

        tstr2 = self.timestring

        fig.text(xtext,.1 + ytextshift, tstr1, fontsize=14, weight='bold',
                  ha='center',color=annotate_time_color)
        fig.text(xtext,.05+ ytextshift, tstr2, fontsize=14, weight='bold',
                  ha='center',color=annotate_time_color)

        plt.rcdefaults()

        # add text string for SCS and NOAA ships (by request)
        try:
            self.kts_text = ','.join([self.procdirname,
                                      '%2.1f' % (uvmag_kts,), 'kts',
                                      '%d' % (uvdir,), 'degT',
                                      rangestr,
                                      self.timestring])
        except UnboundLocalError:
            self.kts_text = "No valid velocity estimate is available."
            _log.info(self.kts_text)  ### FIXME Q: where is this message going?
#            self.ktdir_data=Bunch()
#            self.ktdir_data.u = np.masked_array([
#            self.ktdir_data.v = v
#            self.ktdir_data.z = np.mean(self.data['dep'][refbins])
        else:
            self.ktdir_data=Bunch()
            self.ktdir_data.u = u
            self.ktdir_data.v = v
            self.ktdir_data.z = np.mean(self.data['dep'][refbins])

        return fig
