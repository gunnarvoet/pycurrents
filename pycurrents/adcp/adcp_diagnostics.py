"""
Diagnostic statistical summary and plotting of ADCP single-ping beam data.

"""
import os
import time

import logging

import numpy as np

import matplotlib as mpl

from pycurrents.codas import to_date
import pycurrents.system.pathops as pathops
from pycurrents.adcp.raw_multi import Multiread
from pycurrents.adcp.adcp_specs import cor_clim, amp_clim, vel_clim, sca_clim
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.data.sound import Attenuator

## statistics

from pycurrents.plot.mpltools import savepngs

from pycurrents.adcp.qplot import textfig
from pycurrents.adcp.qplot import qpc

#----------------------------

# Standard logging
_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class BeamDiagnostics(object):

    def __init__(self, uhdas_dir, new_enough = 10.5,
                 sonar=None,
                 savefigs=False,
                 ducerdepth=0,
                 beamangle=None,
                 annotate_color = 'k'):
        '''
        get and plot the last N pings of ADCP data from all inst+ping

        uhdas_dir is the root of the uhdas cruise directory

           * *new_enough* : print an error message if data are older
           * *get_plot_recent* : 'all', or choose one
           * *savefigs* : passed to get_plot_recent

           * *frequency* : khz, for scattering
           * *ducerdepth*: depth of transducer (meters)
           * *beamangle* : beam angle
           * *annotate_color* : color for timestamp annotations
        '''

        ## NOTE: minutes of data to plot - limited by number of files read
        ##  -- needs work.

        if sonar is None:
            raise ValueError('must specify sonar')

        self.new_enough = float(new_enough) #bad idea?
        self.cruisedir  = uhdas_dir

        self.prof_bins = [5,-5]  # shallow an ddeep bins for timeseries
        self.bincolor = ((5, 'magenta'),
                            (-5, 'darkblue')) #colors for self.prof_bins
        self.annotate_color = annotate_color
        self.sonar = Sonar(sonar)

        # for attenuation
        self.frequency = self.sonar.frequency
        self.ducerdepth=ducerdepth
        self.beamangle=beamangle

        # call as
        # self.get_plot_recent(plottype,minutes=minutes, savefigs=savefigs)

    #--------------

    def read_data(self,nfiles = 5,
                  start=-5, stop=None, step=None, minutes=None):
        '''
        read data with using Multiread. arguments mostly passed to Multiread

        *kwargs*

          * *start*, *stop*, *step*, passed to Multiread
              - default is "most recent 5 pings of last file"
          * *minutes* : minutes from the end; calculates stop, start, step

        *returns*

          * *data* from Multiread
        '''

        rawglobstr = os.path.join(self.cruisedir, 'raw',
                                  self.sonar.instname,'*.raw')
        filelist = pathops.make_filelist(rawglobstr)
        filestart = min(len(filelist), abs(nfiles))
        self.lastfiles = filelist[-filestart:]

        if hasattr(self,'m'):
            del self.m

        _log.debug('-------- reading ---------------')
        self.m=Multiread(self.lastfiles, self.sonar.model)

        if self.sonar.model == 'os':
            self.m.pingtype = self.sonar.pingtype    # for os only
            if self.sonar.pingtype == 'bb':
                nchunks = len(self.m.bbchunks)
            else:
                nchunks = len(self.m.nbchunks)
        else:
            nchunks = len(self.m.chunks)
        self.m.select_chunk(nchunks-1)

        if minutes is not None:
            minutes = np.abs(minutes)
            tmpdat = self.m.read(start=-10)
            dtsec = 86400*np.mean(np.diff(tmpdat.dday))
            pings2read = round(minutes*60/dtsec)
            start = int(-pings2read)
            nsamp = 250 # max out at 250 pings to view
            step = max(1, start//nsamp)

        data=self.m.read(start=start, stop=stop, step=step)
        _log.debug('got amp: %s' % (data.amp.shape.__str__(),))

        return data

    def plot_recent_pcolor(self, data, name, yearbase, new_enough=2,
                           titlestr=None,clim=None):
        '''
        make a 4-panel pcolor plot of correlation, amplitude, beam velocity

          * recommend not more than 200 profiles, (all depths used)
          * used by uhdas.scripts.plot_beamdiagnostics


        *args*

           * *data* : from Multiread
           * *name* : 'amp', 'cor', 'vel' -- field to plot
           * *yearbase* : yearbase (for correct time on title)

        *kwargs*

           * *new_enough*:  do not plot if end of data is older than this (hrs)
           * *titlestr* : title for plot
           * *clim* : color limits for the variable being plotted

        *returns*

           * age of most recent data, in hours

        '''

        proceed = True
        retval = None

        if data is None or len(data) == 0 :
            proceed = False
            message = 'no data found'


        if proceed:
           #sstr = 'plot generated at %s' %(time.asctime(time.gmtime()),)
            dd=to_date(yearbase, data.dday[-1])
            ymdhms_str = '%4d/%02d/%02d %02d:%02d:%02d' % (
                dd[0],dd[1],dd[2],dd[3],dd[4],dd[5])
            data_sec = (np.datetime64(str(yearbase), "Y") +
                         np.timedelta64(int(data.dday[-1] * 86400), "s"))
            now_sec = np.datetime64(int(time.time()), "s")
            age_hours = (now_sec - data_sec).astype(float)/3600.
            retval = age_hours

            _log.debug('age_hours = %2.1f' % (age_hours))
            if age_hours < new_enough:
                proceed = True

                tstr = 'ADCP end date (dday): %s, (%2.2f, %2.1f hrs ago)' % (
                    ymdhms_str, data.dday[-1], age_hours)
            else:
                proceed = False
                message = 'no recent data found\nage = %2.1f hours'%(age_hours,)
        if not proceed:
            self.recent_pcolor_fig = textfig(message, title=titlestr)
            return retval

        #proceeding

#        ylim = [len(data.dep), 0]
        ylim = [max(data.dep), 0]
        import matplotlib.pyplot as plt
        recent_pcolor_fig=plt.figure(figsize=(6,9))
        recent_pcolor_fig.text(.5,.05, tstr, ha='center', va='top', size=11,
                               color=self.annotate_color)

        mins  = (data.dday[-1] - data.dday) * 60 * 24
        xlim = (mins[0], mins[-1])

        if name in ('amp','cor','vel'):
            var = data.get(name[:3])  #amp, cor, vel
            if var is None:
                _log.warning('field %s not in data' % (name,))
        elif name == 'sca':  #scattering
            A = Attenuator(f=self.frequency, z=0, T=data.temperature[-1])
            aa = A.TL(data.dep, self.ducerdepth, beam_angle=self.beamangle)
            var = data.amp
            for beamnum in np.arange(4):
                var[:,:,beamnum] = var[:,:,beamnum]*0.45 + aa
        else:
            _log.warning('field %s not in data' % (name,))

        axes_list=[]
        for count in range(4):
            axes_list.append(recent_pcolor_fig.add_subplot(4,1,count+1))


        for count in range(4):
            beamnum = count+1
            ax = axes_list[count]
            qpc(var[:,:,count], profs=mins, bins=data.dep, clim=clim, ax=ax)
            ax.set_ylim(ylim)
            ax.set_xlim(xlim)
            ax.set_ylabel('depth, m')
            ax.set_title('beam %d' % (beamnum,))
            if beamnum <= 3:
                ax.set_xticklabels([])
            ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=5))
            ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=7))
        ax.set_xlabel('minutes ago')


        if titlestr is not None:
            recent_pcolor_fig.text(.5,.95, titlestr, ha='center',
                                    va='top', size=14)

        self.recent_pcolor_fig = recent_pcolor_fig

        plt.draw_if_interactive()



    #--------------

    def get_plot_recent(self, plottype, titlestr=None,
                        minutes=30,
                        savefigs=False):
        '''
        convenience function to get recent data and plot

        *args*:

          * *plottype* one of these:

              - profile     (profiles of the last N seconds)
              - timeseries  (timeseries of shallow and deep bin)
              - amplitude   (pcolor plot for 4 beams)
              - scattering  (pcolor plot of uncalibrated scattering for 4 beams)
              - correlation (pcolor plot for 4 beams)
              - velocity    (pcolor plot for 4 beams)

        *kwargs*

          * *titlestr* : title for plot
          * *savefigs* : [False] save png plot (to present name)

        '''

        if titlestr is None:
            cruisename = os.path.split(self.cruisedir)[-1]
            titlestr = '%s %s %s' % (cruisename, self.sonar, plottype)
        if savefigs:
            outfilebase = '%s_beam_%s' % (self.sonar, plottype)

        climdict = {'amp': amp_clim[self.sonar.model],
                    'cor': cor_clim[self.sonar.sonar],
                    'sca': sca_clim[self.sonar.model],
                    'vel': vel_clim[self.sonar.model]}

        outfiles = []

        if plottype not in ('amplitude','correlation','velocity','scattering'):
            raise IOError("no such plot type %s" % (plottype))

        data = self.read_data(minutes=minutes)
        self.plot_recent_pcolor(data, plottype[:3], self.m.yearbase,
                                titlestr=titlestr,
                                new_enough=self.new_enough,
                                clim=climdict[plottype[:3]])
        if savefigs:
            savepngs([outfilebase+'.png', outfilebase+'_thumb.png'],
                     [90,40], fig=self.recent_pcolor_fig)
            outfiles.append(outfilebase+'.png')
            outfiles.append(outfilebase+'_thumb.png')
            _log.debug('saving %s.png file' % (outfilebase,))


        return outfiles
