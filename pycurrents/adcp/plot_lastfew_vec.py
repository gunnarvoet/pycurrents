"""
Special-purpose module for UHDAS realtime at-sea plotting.
"""

import logging
import matplotlib.pyplot as plt
import numpy as np

from pycurrents.codas import get_profiles         # general codasdb reader
from pycurrents import codas # DB, ProcEns (for more detailed work)
from pycurrents.num import Runstats               # running statistics
from pycurrents.num import Stats
from pycurrents.data import navcalc # uv_from_txy, unwrap_lon, unwrap ...
from pycurrents.plot.mpltools import get_extcmap

# Standard logging
_log = logging.getLogger(__name__)


def colorN(y, cmapname='rainbow'):
    '''
    inputs: array y,

    return a list of colors, len(y) suitable for this:

    colors = colorN(y)
    for ii in range(len(y)):
        plot(x[ii], y[ii], 'o', color=colors[i])
    '''
    if np.iterable(y):
        ncolors = len(y)
    else:
        ncolors = y
    cm = get_extcmap(cmapname)
    return cm(np.linspace(0, 1, ncolors))


class LastFewVec:
    '''
    pass in a Bunch with these values
         dbpath              :  path to database
         startdd             :  start extraction here
         history             :  hours to extract: (neg="backwards from here")
         rdi_startbins       :  list of starting bins for ref layer [1,2,3...]
         numbins             :  number of bins to include in reference layer
         avgwin              :  window for averaging (odd integer)
         plot_all_shallow    :  also plot all vectors in top layer (quiver only)
         cruisename          :  used in title
         sonar               :  used in title
         vecscale            :  manually set vecscale
                                   use_quiver: larger vecscale --> smaller vectors
                                not use_quiver: larger vecscale --> larger vectors
         autoscale           :  automatically set vecscale based on u,v
         use_quiver  :True= plot using the function that uses quiver (arrows)
                     :F(default) just make lines emanating from cruise track
         verbose             :  print additional information (debugging)
         annotate_time_color :  annotate timestamp in this color

    '''
    def __init__(self, options):

        self.dbpath = options.dbpath
        self.rdi_startbins = options.rdi_startbins
        self.numbins = options.numbins
        self.history = options.history
        self.avgwin  = options.avgwin
        self.cruisename = options.cruisename
        self.sonar = options.sonar
        self.plot_all_shallow = options.plot_all_shallow
        self.vecscale = options.vecscale
        self.verbose = options.verbose
        self.startdd = options.startdd
        self.autoscale = options.autoscale
        self.annotate_time_color = options.annotate_time_color

    def get_data(self):
        """
        get data from appropriate database
        get titlestring

        Returns data, or None if get_profiles fails.
        """

        try:
            self.data=get_profiles(self.dbpath, startdd = self.startdd,
                               ndays = self.history/24.)
        except:
            _log.debug('get_profiles failed with startdd = %s, ndays = %s',
                      self.startdd, self.history/24.)
            return None

        # Not sure if we need this check:
        if self.data.nprofs == 0:
            _log.warning('get_profiles returned no profiles')
            return None
        if len(self.data.dday) == 1:
            _log.warning('get_profiles returned only 1 profile')
            return None

        if self.verbose:
            _log.info('got %d pings, %7.5f to %7.5f' % (len(self.data.dday),
                                                self.data.dday[0],
                                                self.data.dday[-1]))

        self.titlestr1 = '%s %s (duration = %3.1f hours); ' % (
            self.cruisename, self.sonar,
            24 * (self.data.dday[-1] - self.data.dday[0]))
        self.titlestr2 = 'dday range=(%7.5f, %7.5f), last UTC time=%s' % (
            self.data.dday[0],  self.data.dday[-1],
            codas.to_datestring(self.data.yearbase, self.data.dday[-1]))
        if np.ma.is_masked(self.data.lat[-1]):
            platstr = plonstr = "NaN"
        else:
            platstr = navcalc.pretty_llstr(self.data.lat[-1],'lat')
            plonstr = navcalc.pretty_llstr(self.data.lon[-1],'lon')
        # augment it
        self.latstr = '(%s)' % platstr.lstrip()
        self.lonstr = '(%s)' % plonstr.lstrip()

        return self.data

    def magnitude(self, u, v):
        return np.sqrt(u*u + v*v)

    def stage_refls(self):

        self.refsl = []
        for bin in self.rdi_startbins:
            self.refsl.append(slice(bin-1, bin+self.numbins))

        if len(self.rdi_startbins) > 3:
            self.colors = colorN(len(self.refsl), 'jet')[::-1]
        else:
            allcolors = ['r','g','b']
            self.colors = allcolors[:len(self.rdi_startbins)]

        if self.avgwin > 1:
            # averaging window slice for plotting
            self.asl = slice(0,-1,self.avgwin)
        else:
            self.asl = slice(None)

        # turn positions into kilometers
        dx, dy = navcalc.diffxy_from_lonlat(self.data.lon,
                                            self.data.lat, pad=False)
        xx = np.cumsum(dx)/1000 #km
        yy = np.cumsum(dy)/1000 #km

        x = 0*self.data.lon; x[1:] = xx
        y = 0*self.data.lat; y[1:] = yy

        self.x = x - x[-1] # make it end up at the origin
        self.y = y - y[-1] # make it end up at the origin

        # get reference layers (and uvmax for scaling)
        self.uvsm = []
        self.endxy = []
        self.uvmax = 0
        for sl in self.refsl:
            uref = Stats(self.data.u[:,sl], axis=1).mean
            vref = Stats(self.data.v[:,sl], axis=1).mean

            if uref is np.ma.masked:
                uvmasked = np.ma.masked_array(self.data.u[:,0],
                                              mask=True)
                self.uvsm.append((uvmasked, uvmasked))
                self.uvmax == 0
                _log.debug('reference layer (bins %s) has no good data', sl)
            else:
                urefsm = Runstats(uref, self.avgwin).mean
                vrefsm = Runstats(vref, self.avgwin).mean
                self.uvsm.append((urefsm, vrefsm))
                #
                uvspd = self.magnitude(urefsm, vrefsm)
                reflmax = np.ma.max(uvspd)

                if np.ma.getmask(reflmax) == False:
                    self.uvmax = max(reflmax, self.uvmax)
        if self.uvmax == 0:
            self.uvmax = 1 # no data; give it some size

        #------------------
        if self.verbose:
            _log.info('uvmax = %f' % (self.uvmax))
        # get vector legend length
        if self.uvmax < .1:
            ulegend = .1
        elif self.uvmax < .2:
            ulegend = .2
        elif self.uvmax < .5:
            ulegend = .5
        elif self.uvmax < 1:
            ulegend = 1
        elif self.uvmax < 1.5:
            ulegend = 1.5
        elif self.uvmax < 2:
            ulegend = 2
        else:
            ulegend = 2.5
        self.ulegend = ulegend
        if self.verbose:
            _log.info('ulegend=%4.3f' %(self.ulegend))


        ## get the legend labels
        self.legendlist=[]
        index=np.arange(len(self.data.bins))
        for iref in range(len(self.refsl))[::-1]:
            ibins = index[self.refsl[iref]]
            if len(ibins)>0:
                bins = self.data.bins[ibins] # rdi bins
                if len(bins) == 1:
                    tt = 'bin %d\n(%dm)' % (bins[0], self.data.dep[ibins[0]])
                else:
                    tt = 'bin %d-%d\n(%dm-%dm)' % (bins[0], bins[-1],
                                          self.data.dep[ibins[0]],
                                          self.data.dep[ibins[-1]])
                self.legendlist.append( (tt, self.colors[iref]) )


    # -----

    def setup_axes(self,**kwargs):

        # make the plot
        f,ax=plt.subplots(**kwargs)
        return f, ax

    def plot_lastvec_quiver(self, f, ax, vmultiplier=4, make_legend=False):
        '''
        try to make vectors using quiver
        '''
        ax.plot(self.x,self.y,color=[.9,.9,.9])
        ax.plot(self.x,self.y,'k.', ms=4)
        ax.set_aspect('equal')
        ax.plot(0, 0, 'ko')

        # make the arrows
        if self.autoscale:
            self.vecscale = vmultiplier*self.ulegend
            if self.verbose:
                _log.info('vecscale=ulegend*%4.2f' % (vmultiplier))

        kwargs=dict(scale=self.vecscale)
        for iref in range(len(self.refsl))[::-1]:
            urefsm, vrefsm = self.uvsm[iref]

            if self.plot_all_shallow and iref==0:
                ax.quiver(self.x, self.y,
                          urefsm, vrefsm, color=[.8,.8,.8],
                          width=.005, **kwargs)

            ax.quiver(self.x[self.asl],self.y[self.asl],
                          urefsm[self.asl], vrefsm[self.asl],
                          color=self.colors[iref],
                          width=.004, **kwargs)

        # set xlim, ylim
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        xymin = min(xlim[0], ylim[0])
        xymax = max(xlim[1], ylim[1])
        pad=.5*self.uvmax
        xypad = pad*(xymax-xymin)
        xylim = (xymin - xypad, xymax+xypad)
        ax.set_xlim(xylim[0], xylim[1])
        ax.set_ylim(xylim[0], xylim[1])
        ax.hlines(0, xylim[0], xylim[1], 'k')
        ax.vlines(0, xylim[0], xylim[1], 'k')


        #legend for quiver  -------------------

        xlegend=xylim[0]+3*xypad
        ylegend=xylim[0]+.5*xypad
        ax.quiver(xlegend, ylegend, self.ulegend, 0, color='k',**kwargs)
        xlegend=xylim[0]+2*xypad
        ax.text(xlegend, ylegend, '%2.1fm/s' % (self.ulegend), color='k',
                                                 ha='right', va='center')
        ylegend+=.5*xypad

        xlegend=xylim[0]+.5*xypad
        ## put it on the axes
        if make_legend:
            for tt,cc in self.legendlist:
                ax.text(xlegend, ylegend, tt, ha='left', va='center', color=cc)
                ylegend+=.5*xypad


        # other decorations
        ax.grid(True)
        ax.set_xlabel('kilometers (E/W)')
        ax.set_ylabel('kilometers (N/S)')

        #------------------

    def plot_lastvec(self, f, ax, vmultiplier=8, make_legend=False):
        '''
        plot without using quiver; just make flags (tails) from dots
        '''

        if self.autoscale:
            self.vecscale = vmultiplier/self.ulegend
            if self.verbose:
                _log.info('vecscale=%4.2f/ulegend' % (vmultiplier))

        for sl in self.refsl:
            uref = Stats(self.data.u[:,sl], axis=1).mean
            vref = Stats(self.data.v[:,sl], axis=1).mean
            self.endxy.append((self.x + uref*self.vecscale,
                               self.y + vref*self.vecscale))

        ax.plot(self.x,self.y,color=[.9,.9,.9])
        ax.plot(self.x,self.y,'k.', ms=4)
        ax.set_aspect('equal')
        ax.plot(0, 0, 'ko')

        # plot the headless arrows
        for iref in range(len(self.endxy)):
            for ipt in np.arange(len(self.x)):
                startx = self.x[ipt]
                starty = self.y[ipt]
                tmpx, tmpy = self.endxy[iref]
                endx = tmpx[ipt]
                endy = tmpy[ipt]
                ax.plot([startx, endx], [starty, endy], '-',
                        color=self.colors[iref])


        # set xlim, ylim
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        pad=0.1 * min(np.diff(xlim)[0], np.diff(ylim)[0])
        newxlim = (xlim[0]-pad, xlim[1]+pad)
        newylim = (ylim[0]-pad, ylim[1]+pad)
        ax.set_xlim(newxlim)
        ax.set_ylim(newylim)
        ax.hlines(0, newxlim[0], newxlim[1], 'k')
        ax.vlines(0, newylim[0], newylim[1], 'k')

        # make it square
        extent = max(np.diff(newxlim),np.diff(newylim))[0]
        ax.set_xlim(newxlim[1]-extent, newxlim[1])
        ax.set_ylim(newylim[1]-extent, newylim[1])


        #legend on the lower left = depth range
        # (1) vector scale
        dy=.03
        dx=.05*extent
        xlim=ax.get_xlim()
        ylim=ax.get_ylim()
        xlegend=xlim[0]+.2*extent
        ylegend=ylim[0]+dy*extent

        # see if the autoscaling has the right side of ulegend too far right
        # use half size if so
        ulegend_end  = xlegend + dx + self.vecscale*self.ulegend
        if ulegend_end > xlim[-1]:
            self.ulegend = self.ulegend/2.
            ulegend_end  = xlegend + dx + self.vecscale*self.ulegend

        ax.plot([xlegend+dx, ulegend_end],
                [ylegend, ylegend], '-', color=self.colors[iref])
        ax.plot(xlegend+dx, ylegend, 'k.')
        ax.text(xlegend, ylegend, '%2.1fm/s' % (self.ulegend), #spacing
                            color='k', ha='right', va='center')


        ## ---
        if make_legend:
            for tt,cc in self.legendlist:
                ax.text(xlegend, ylegend, tt, ha='left', va='center', color=cc)
                ylegend+=dy*extent

        ax.grid(True)

        ax.set_xlabel('kilometers (E/W)')
        ax.set_ylabel('kilometers (N/S)')



    def place_labels(self, fig, dy=.1):
        titlestr =  '\n'.join([self.titlestr1, self.titlestr2])
        fig.text(.5, .92, titlestr, ha='center', color=self.annotate_time_color,
                 size=11)

        ## ---
        xstart = .98
        ystart = dy*2
        for tt,cc in self.legendlist: #already deepest first
            fig.text(xstart, ystart, tt, ha='right', color=cc, weight='bold')
            ystart+=dy


        tlist = ['END at origin (0,0):',]
        tlist.append(self.latstr)
        tlist.append(self.lonstr)

        # put lon, lat on top
        ystart += dy
        for tt in tlist[::-1]:
            fig.text(xstart, ystart, tt, ha='right', color='k',
                     size='small', weight='bold')
            ystart+=dy/2
