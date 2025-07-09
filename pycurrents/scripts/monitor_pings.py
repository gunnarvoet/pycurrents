#!/usr/bin/env python
'''
 simple adcp animator -- plot [amp,vel,cor] from raw data

## later add specs for
 - vertical = [bins, depth]
 - horizontal = [index, seconds, decimal day]
 - color range or auto



python monitor_rawadcp.py [options] raw_dir
python monitor_rawadcp.py [options]

eg.

 monitor_pings.py wh --var_ylim -.4:.4 --bin 4 -n 3 --start -300  --clim -.2:.2 --varname vel  -r /net/rigel/home/data/aaatest01/raw/wh300


CAVEAT: does not cross configuration boundaries, but file
        specification to avoid this is delicate

'''

# TODO:
# - cruiseid or path at the top
# - label variable
# - add Simrad ec support?

import os
import time
import sys
import glob
from optparse import OptionParser

import numpy as np

#import matplotlib
#matplotlib.use("qt4agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
#from matplotlib.cbook import report_memory #deprecated starting 3.5
from matplotlib.lines import Line2D

from pycurrents.adcp.raw_multi import Multiread      # singleping ADCP
import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents import codas


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

def get_clim(varname, override_clim=None):
    if varname == 'amp':
        clim=[20,180]
    elif varname == 'vel':
        clim=[-3,3]
    elif varname == 'cor':
        clim=[20,200]

    if override_clim is not None:
        parts=override_clim.split(':')
        if len(parts) == 2:
            clim = [float(parts[0]), float(parts[1])]
        else:
            clim = [-float(parts[0]), float(parts[0])]
    return clim



class CData(object):
    def __init__(self, filelist=None, varname=None,
                 start=-300,
                 stop=-1,
                 steptest=0,
                 pingtype=None,
                 ):
        if filelist is None:
            print('must send filelist')
            raise IOError

        if varname is None:
            print('varname is', varname)
            print('must select variable name to plot ("amp", "vel", "cor")')
            raise IOError

        if model is None:
            print('model is', model)
            print("must select model to read ('os', 'pn', 'bb','nb','wh')")
            raise IOError


        self.model = model
        self.pingtype = None
        self.start = start
        self.stop = stop
        self.steptest = steptest
        self.varname = varname

    def get_data(self):
        '''
        raw_dir is (eg.) uhdas_dir/raw/os75
        varname in ['amp','vel','cor']
        start, stop: indices to read data
        '''

        m=Multiread(filelist, self.model)
        if self.pingtype is not None:
            m.pingtype = self.pingtype
        if self.steptest > 0:
            self.start = np.max(self.start+self.steptest, -1)
            self.stop = np.max(self.stop+self.steptest, -1)
        data=m.read(start=self.start, stop=self.stop)
        if data is None:
            return None
        self.data = data
        var = getattr(self.data, self.varname)
        self.bins = np.arange(len(var[0,:,0]))
        self.t=np.arange(len(var[:,0,0]))
        return var




class CPlotter(object):
    def __init__(self, plotfig, qfigs):
        '''
        qfig is a QFig instance
        '''

        self.qfigs = qfigs

    def init_ax(self, var, ylim2=None, bin=10, clim=None, cbar_kw=None,
                var_ylim=None, var_line=None):
        '''
        get data, update fig.  no titles here
        '''
        ## TODO : cbar_kw not treated well
        bins = np.arange(len(var[0,:,0]))
        t=np.arange(len(var[:,0,0]))
        self.ims = []
        for iplot in range(len(self.qfigs)-1):  #0,1,2,3
            #qfigs[0] is subplot(511), i.e. top plot
            qfig = self.qfigs[iplot]
            if clim or cbar_kw:
                qfig.drew_cax = False
                if clim:
                    self.clim = clim #replace
                if cbar_kw:
                    self.cbar_kw = cbar_kw #replace
            im=qfig.ax.imshow(var[:,:,iplot].T,
                              vmin=self.clim[0], vmax=self.clim[1])
            im.set_interpolation('nearest')
            qfig.ax.set_aspect('auto')
            if ylim2 is None:
                if qfig.ax2:
                    qfig.ax2.yaxis.set_visible(False)
            else:
                if qfig.ax2:
                    qfig.ax2.set_ylim(ylim2)
                    qfig.ax2.set_ylabel('meters')
            qfig.ax.set_ylabel('bins')
            cbkw = qfig._process_cbar_kw(dict(), qfig.ax, qfig.cax)
            plt.colorbar(im, **cbkw)
            self.ims.append(im)

            # add lines to image
            line = Line2D(t, 0*t + bins[bin], color='m', lw=2)
            qfig.ax.add_line(line)

        # var is [nprofs x nbins x nbeams]
        self.var_ylim = var_ylim
        self.var_line = var_line

        colors = 'rgbk'
        dummy = self.var_line + 0*t

        # add lines to stripchart
        qlinefig = qfigs[-1]
        line = Line2D(t, dummy, color='m', lw=2)
        qlinefig.ax.add_line(line)
        qlinefig.ax.set_xlim(qfigs[0].ax.get_xlim())
        qlinefig.ax.set_ylim(self.var_ylim)

        self.beamlines=[]
        for iplot in [0,1,2,3]:
            line = Line2D(t,var[:,bin,0],color=colors[iplot], marker='.')
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
        var=self.CD.get_data()
        if var is None:
            return
        dstr =  codas.to_datestring(self.CD.data.yearbase,
                                    self.CD.data.dday[-1])
        for iplot in [0,1,2,3]:
            CP.ims[iplot].set_array(var[:,:,iplot].T)
            CP.beamlines[iplot].set_data(CP.t, var[:,self.CP.bin,iplot])

        duration = get_etimestr(self.start_time)
        last_time = 'last data time: %s UTC; ' %  dstr
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

    parser.add_option("-r", "--rawdir", dest="rawdir",
                      default=None,
                      help="specify this directory for data files (else use arg)")
    parser.add_option("-v", "--varname", dest="varname",
                      default='amp',
                      help="plot this 3D variable, eg 'amp','vel'")
    parser.add_option("--start", dest="start",
                      default = -300,
                      help="start at index START")
    parser.add_option("--stop", dest="stop",
                      default = -1,
                      help="start at index STOP")
    parser.add_option("--steptest", dest="steptest",
                      default = 0,
                      help="simulate animation: increment start and stop by steptest")
    parser.add_option("--bin", dest="bin",
                      default = 10,
                      help="stripchart of this bin")
    parser.add_option("--var_line", dest="var_line",
                      default = 40,
                      help="one constant line on stripchart")
    parser.add_option("--var_ylim", dest="var_ylim",
                      default = None,
                      help="colon-delimited ylims for stripchart")

    parser.add_option("--pause", dest="pause",
                      default = 5,
                      help="pause between animation frames ")
    parser.add_option("-n", "--nfiles", dest="nfiles",
                      default = 3,
                      help="read last N files ")
    parser.add_option("--clim", dest="clim",
                      default = None,
                      help="colon-delimited min:max for colors")
    parser.add_option("-t", "--title", dest="title",
                      default = None,
                      help="plot title")
    parser.add_option("-p", "--pingtype", dest="pingtype",
                      default=None,
                      help='specify ping type (use with OS only)')

    (options, args) = parser.parse_args(args=sys.argv)

    # want ['monitor_pings.py', 'os', '*/raw']

    if len(args) <2:
        print(__doc__)
        sys.exit()

    if len(args) >=2:
        model = args[1][:2]
        if model not in ('os', 'pn', 'nb','bb','wh'):
            IOError("%s not in model list: ('os', 'pn', 'nb','bb','wh')" %(args[0]))

    print(args)

    filelist = None
    globstr = ''
    if options.rawdir: #assume path
        globstr = os.path.join(options.rawdir,'*.raw')
    if len(args) == 3 : # try path first, then try file
        globstr = os.path.join(args[2],'*.raw')
        if len(glob.glob(globstr)) == 0:
            globstr = args[2]
    elif len(args) > 3: #assume file list
        filelist = args[2:]

    if filelist:
        for f in filelist:
            if not os.path.exists(f):
                print('file %s does not exist' % (f))
    elif globstr:
        if len(glob.glob(globstr)) == 0:
            print('no files found with %s' % globstr)
            sys.exit()
        else:
            filelist=pathops.make_filelist(globstr)[-int(options.nfiles):]
    else:
        print('args', args)
        print('filelist', filelist)
        print('globstr', globstr)







    # data
    raw_dir = args[1]
    varname = options.varname
    params = dict()
    params['pingtype'] = options.pingtype
    params['start']   = int(options.start)
    params['stop']    = int(options.stop)
    params['steptest'] = int(options.steptest)


    var_line = float(options.var_line)
    var_ylim = get_clim(varname, options.var_ylim)
    clim = get_clim(varname, options.clim)

    CD = CData(filelist, varname, **params)
    fig = plt.figure()
    if options.title:
        fig.text(.5,.95,options.title + ' ' + options.varname, ha='center')
    qfigs = make_axes(fig)
    plt.draw()
    var = CD.get_data()
    CP= CPlotter(fig, qfigs)
    CP.init_ax(var, bin=int(options.bin), ylim2=[CD.data.dep[-1], 0],
               clim=clim, var_line=var_line, var_ylim=var_ylim)
    CP.ttext=fig.text(.45,.04,get_etimestr(start_time), ha='center')
    b=Boss(CD,CP, start_time)

    if options.steptest:
        interval = float(options.pause)
    else:
        interval = max(int(options.pause), 1)

    while True:
        out = b.update()
        if options.steptest and out is None:
            break
        else:
            plt.pause(interval)



#    timer = fig.canvas.new_timer(interval=interval,
#                                 callbacks=[(b.update, tuple(), {}),
#                                            (fig.canvas.draw, tuple(), {})])
#    timer.start()
#    plt.show()
