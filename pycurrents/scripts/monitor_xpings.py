#!/usr/bin/env python
'''
This program will "animate" ocean u,v from single-ping data.
See monitor_pings.py, its cousin, for amp, cor, beamvel


## must have config/CRUISE_proc.py with valid entries
## alter CRUISE_proc.py or may have to link CRUISE to /home/data/CRUISE

monitor_xpings.py -s wh300 --bin 4  --cruisename CRUISE


# or pointing to /home/data link made to real data:

## to go forward

monitor_xpings.py --cfgpath oc1401a_moum/proc/wh300/config -s wh300 --bin 4   --nsecs 300 --cruisename oc1401a_moum --startdd 12.7 --step 1 --avgwin=31


## to show the end of live data:
 monitor_xpings.py --cfgpath /net/currents/home/data/pierside_after_km1418/proc/wh300/config -s wh300 --bin 4 --nsecs -60 --cruisename pierside_after_km1418 --step 1 --avgwin 31


'''

# TODO:
# - cruiseid or path at the top
# - label variable
# - add Simrad ec support?

import os
import time
import sys
import glob

import numpy as np

#import matplotlib
#matplotlib.use("qt4agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
#from matplotlib.cbook import report_memory
from matplotlib.lines import Line2D

from pycurrents.adcp import pingsuite
from pycurrents.adcp.raw_multi import Multiread
import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents import codas
from pycurrents.system.misc import Bunch
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.plot.mpltools import get_extcmap
from pycurrents.num import Runstats


from optparse import OptionParser

def get_etimestr(start_epoch):
    elapsed = round(time.mktime(time.gmtime()) - start_epoch)
    if elapsed < 300:
        etimestr = '%d s' % (elapsed)
    elif elapsed < 30*60:
        hours = np.floor(elapsed/3660.)
        minutes = (elapsed - hours*3600)/60.
        etimestr = '%dhr,%dmin' % (hours, minutes)
    else:
        days = np.floor(elapsed/86400.)
        hours = (elapsed - 86400*days)/3600.
        etimestr = '%d days %2.1f hr' % (days, hours)
    return 'running ' + etimestr


class QFFig(object):
    def __init__(self, fig):
        self.fig = fig
        self.drew_cax = False

    def get_fig_ax(self,ax):
        cax, kw = mpl.colorbar.make_axes(ax, pad=0.1, aspect=12)
        self.ax = ax
        self.cax = cax

    def _process_cbar_kw(self, cbar_kw, ax, cax, discrete=False):
        cbkw = dict({'extend':'both'})
        if not discrete:
            cbkw['ticks'] = mpl.ticker.MaxNLocator(nbins=5)

        if cbar_kw is not None:
            if 'cax' in list(cbar_kw.keys()):
                cbkw['cax'] = cbar_kw['cax']
            else:
                cbkw['cax'] = cax
        cbkw.update(cbar_kw)
        return cbkw


def make_axes(fig):
    numplots = 5
    qfigs = []
    x0 = .08
    totalheight = .8
    ax_height = totalheight/float(numplots)     # 4 beams plus one stripchart
    starty= 0.1
    #
    pax_width = 0.95
    pad = totalheight*.01
    #pcolor axes; appending from the bottom upwards

    # define one, then sharex with that
    left = x0
    width = pax_width
    height = ax_height
    for num in [4,3,2,1,0]: #start with the highest (vertical) axes
        bottom = starty + num*(ax_height+pad)
        ax=fig.add_axes([left, bottom, width, height])
        ax.set_aspect('auto')
        QFF=QFFig(fig)
        QFF.get_fig_ax(ax) # add cax
        if num == 0:
            QFF.ax.xaxis.set_visible(True)
            QFF.ax2 = None
            fig.delaxes(QFF.cax)
        else:
            QFF.ax.xaxis.set_visible(False)
            QFF.ax2=QFF.ax.twinx()
        qfigs.append(QFF)

    return qfigs


##
def get_clim(varname, override_clim=None):
    if varname[:3] == 'amp':
        clim=[20,200]
    elif varname[:3] == 'vel':
        clim=[-3,3]
    elif varname in ['uvel', 'vvel']:
        clim=[-1.5,1.5]
    elif varname == 'cor':
        clim=[20,160]
    #
    if override_clim is not None:
        parts=override_clim.split(':')
        if len(parts) == 2:
            clim = [float(parts[0]), float(parts[1])]
        else:
            clim = [-float(parts[0]), float(parts[0])]
    return clim



class CData(object):
    def __init__(self, procdir, cruisename, cfgpath='config',
                 startdd=None, nsecs=-600, step=1, verbose=False, avgwin=1):
        if procdir is None:
            print('procdir ', procdir)
            print("must select sonar from instruments like 'wh300', 'os75bb', 'os75nb'")
            raise IOError

        cfgfile = os.path.join(cfgpath, '%s_proc.py' % (cruisename))
        if not os.path.exists(cfgfile):
            print("processing config file %s does not exist" % (cfgfile))
            raise IOError

        self.S = Sonar(procdir)

        cfg_info = Bunch().from_pyfile(cfgfile)
        fileglob = os.path.join(cfg_info.uhdas_dir, 'raw', self.S.instname, '*.raw')
        if len(glob.glob(fileglob))==0:
            print("no files found with wildcard %s" % (fileglob))
            raise IOError

        self.cfg_info = cfg_info
        self.fileglob = fileglob
        self.PS=pingsuite.PingSuite(self.S.sonar, cfgpath=cfgpath, cruisename = cruisename)

        filelist=pathops.make_filelist(self.fileglob)
        m=Multiread(filelist, self.S.model)
        m.pingtype = self.S.pingtype
        data=m.read(ends=1)

        self.step=step
        self.nsecs = nsecs
        self.avgwin=avgwin
        if startdd is None:
            if self.nsecs > 0:
                self.startdd = data.dday[0]
            else:
                self.startdd = data.dday[-1]
        else:
            self.startdd = float(startdd)
        print('dataset %10.5f to %10.5f' % (data.dday[0], data.dday[-1]))
        print('startdd is ', self.startdd)
        print('reading %d seconds' % (self.nsecs))

    def get_data(self):
        '''
        read the last nsecs
        '''
        filelist=pathops.make_filelist(self.fileglob)
        m=Multiread(filelist, self.S.model)
        m.pingtype = self.S.pingtype

        self.PS.pinger.get_pings(start_dday=self.startdd, nsecs=self.nsecs)
        self.startdd += self.nsecs/86400.  # increment for next time


        if not hasattr(self.PS.pinger, 'ens'):
            self.PS.pinger.ens = None
        if self.PS.pinger.ens is None:
            return None

        self.data = self.PS.pinger.ens
        print('read data segment %7.5f to %7.5f' % (self.data.dday[0],self.data.dday[-1]))

        var = []
        var.append(self.PS.pinger.ens.uvel[::self.step,:])
        var.append(self.PS.pinger.ens.vvel[::self.step,:])
        var.append(self.PS.pinger.ens.amp1[::self.step,:])
        var.append(self.PS.pinger.ens.cor1[::self.step,:])
        var.append(Runstats(self.PS.pinger.ens.uvel, nwin=self.avgwin, axis=0).mean)
        var.append(Runstats(self.PS.pinger.ens.vvel, nwin=self.avgwin, axis=0).mean)

        return var #subset in time


class CPlotter(object):
    def __init__(self, plotfig, qfigs, climbunch, climnames):
        '''
        qfig is a QFig instance
        '''

        self.qfigs = qfigs
        self.climbunch=climbunch
        self.climnames=climnames
        self.cmap = []
        self.cmap.append(get_extcmap('ob_vel'))
        self.cmap.append(get_extcmap('ob_vel'))
        self.cmap.append(get_extcmap('jet'))
        self.cmap.append(get_extcmap('jet'))


    def init_ax(self, var, ylim2=None, bin=10, cbar_kw=None,
                var_ylim=None, var_line=None):
        '''
        get data, update fig.  no titles here
        '''
        ## TODO : cbar_kw not treated well
        for vv in var:
            print('shape is', vv.shape)

        bins = np.arange(len(var[0][0,:]))
        t=np.arange(len(var[0][:,0]))
        self.ims = []
        for iplot in range(len(self.qfigs)-1):  #0,1,2,3
            #qfigs[0] is subplot(511), i.e. top plot
            qfig = self.qfigs[iplot]
            clim = climbunch[climnames[iplot]]
            qfig.drew_cax = False
            if cbar_kw:
                self.cbar_kw = cbar_kw #replace
            im=qfig.ax.imshow(var[iplot].T, vmin=clim[0], vmax=clim[1],
                              cmap=self.cmap[iplot])
            im.set_interpolation('nearest')
            qfig.ax.set_aspect('auto')
            if ylim2 is None:
                if qfig.ax2:
                    qfig.ax2.yaxis.set_visible(False)
            else:
                if qfig.ax2:
                    qfig.ax2.set_ylim(ylim2)
                    qfig.ax2.set_ylabel('meters')
            qfig.ax.set_ylabel(climnames[iplot] + '\nbins')
            cbkw = qfig._process_cbar_kw(dict(), qfig.ax, qfig.cax)
            plt.colorbar(im, **cbkw)
            self.ims.append(im)

            # add lines to image
            line = Line2D(t, 0*t + bins[bin], color='m', lw=2)
            qfig.ax.add_line(line)

        # var is [nprofs x nbins x nbeams]
        self.var_ylim = var_ylim
        self.var_line = var_line

        colors = 'rb'
        dummy = self.var_line + 0*t

        # add lines to stripchart
        qlinefig = qfigs[-1]
        line = Line2D(t, dummy, color='m', lw=2)
        qlinefig.ax.add_line(line)
        qlinefig.ax.set_xlim(qfigs[0].ax.get_xlim())
        qlinefig.ax.set_ylim(self.var_ylim)

        self.beamlines=[]
        # plot orig
        for iplot in [0,1]:
            line = Line2D(t,var[iplot][:,bin],color=colors[iplot], marker='.', markersize=2)
            qlinefig.ax.add_line(line)
            self.beamlines.append(line)
        # plot Runstats
        for iplot in [0,1]:
            line = Line2D(t,var[iplot+4][:,bin],marker='o', mec=colors[iplot], mfc='none')
            qlinefig.ax.add_line(line)
            self.beamlines.append(line)
        self.bin = bin
        self.t = t


class Boss(object):
    def __init__(self, cd, cp, start_time):
        self.CD = cd
        self.CP = cp
        self.start_time = start_time
        self.mem = []
        self.count = 0

    def update(self, *args):
        var = self.CD.get_data()
        if var is None:
            return
        dstr =  codas.to_datestring(self.CD.data.yearbase,
                                    self.CD.data.dday[-1])
        #
        CP.ims[0].set_array(var[0].T)
        CP.ims[1].set_array(var[1].T)
        CP.ims[2].set_array(var[2].T)
        CP.ims[3].set_array(var[3].T)
        CP.beamlines[0].set_data(CP.t, var[0][:,self.CP.bin])
        CP.beamlines[1].set_data(CP.t, var[1][:,self.CP.bin])
        CP.beamlines[2].set_data(CP.t, var[4][:,self.CP.bin])
        CP.beamlines[3].set_data(CP.t, var[5][:,self.CP.bin])

        duration = get_etimestr(self.start_time)
        last_time = 'last data time: %s UTC (%7.5f)  ' % (dstr, self.CD.data.dday[-1])
        self.CP.ttext.set_text(last_time + duration)
#        if self.count % 60 == 0:
#            mem = report_memory()
#            print(mem)
#            self.mem.append(mem)    ## This will cause a small increase in
                                    ## memory consumption.
        self.count += 1
        return True

if __name__ == '__main__':

    start_time = time.mktime(time.gmtime())

    parser = OptionParser(__doc__)

    parser.add_option("-s", "--sonar", dest="procdir",
                      default=None,
                      help="specify instrument (+pingtype), eg: 'wh300', 'os75bb'")

    parser.add_option("--cfgpath", dest="cfgpath",
                      default='config',
                      help="directory with CRUISENAME_proc.py file")

    parser.add_option("--cruisename", dest="cruisename",
                      default=None,
                      help="specify cruise name for config/CRUISENAME_proc.py")

    parser.add_option("--startdd", dest="startdd",
                      default = None,
                      help="start at this decimal day")
    parser.add_option("--nsecs", dest="nsecs",
                      default = 600,
                      help="back up this far")
    parser.add_option("--step", dest="step",
                      default = 1,
                      help="step size for subsampling")
    parser.add_option("--bin", dest="bin",
                      default = 10,
                      help="stripchart of this bin")
    parser.add_option("--avgwin", dest="avgwin",
                      default = 1,
                      help="odd-number of points for running mean")
    parser.add_option("--var_line", dest="var_line",
                      default = 40,
                      help="one constant line on stripchart")
    parser.add_option("--var_ylim", dest="var_ylim",
                      default = None,
                      help="colon-delimited ylims for stripchart")
    parser.add_option("--pause", dest="pause",
                      default = 5,
                      help="pause between animation frames ")
    parser.add_option("--clim", dest="clim",
                      default = None,
                      help="colon-delimited min:max for u,v colors")
    parser.add_option("-t", "--title", dest="title",
                      default = None,
                      help="plot title")


    (options, args) = parser.parse_args(args=sys.argv)

    options.varname = 'vel'
    # want ['monitor_pings.py', 'os', '*/raw']

    var_line = float(options.var_line)
    var_ylim = get_clim('uvel', options.var_ylim)
    climbunch=Bunch()
    climbunch.uvel = get_clim('uvel', options.clim)
    climbunch.vvel = get_clim('vvel', options.clim)
    climbunch.amp1 = get_clim('amp')
    climbunch.cor1 = get_clim('cor')
    climnames = ['uvel', 'vvel', 'amp1', 'cor1']


    print('startdd is ', options.startdd)

    CD = CData(options.procdir, options.cruisename, cfgpath=options.cfgpath,
               startdd=options.startdd, nsecs=int(options.nsecs),
               step=int(options.step), avgwin=int(options.avgwin))

    fig = plt.figure(figsize=(10,7))
    if options.title:
        fig.text(.5,.95,options.title + ' ' + options.varname, ha='center')
    fig.text(.97,.20, 'ocean u', ha='right', color='r')
    fig.text(.97,.16, 'ocean v', ha='right', color='b')
    fig.text(.97,.12, 'amp1', ha='right')
    fig.text(.97,.08, 'cor1', ha='right')
    qfigs = make_axes(fig)
    plt.draw()
    var = CD.get_data()
    CP= CPlotter(fig, qfigs, climbunch, climnames)
    CP.init_ax(var, bin=int(options.bin), ylim2=[CD.data.dep[-1], 0],
               var_line=var_line, var_ylim=var_ylim)
    CP.ttext=fig.text(.45,.04,get_etimestr(start_time), ha='center')
    b=Boss(CD,CP, start_time)

    interval = max(int(options.pause), 1)

    while True:
        out = b.update()
        plt.draw()
        plt.pause(interval)


#    timer = fig.canvas.new_timer(interval=interval,
#                                 callbacks=[(b.update, tuple(), {}),
#                                            (fig.canvas.draw, tuple(), {})])
#    timer.start()
#    plt.show()
