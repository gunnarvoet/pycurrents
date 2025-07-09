#!/usr/bin/env python3

import os
import sys
import glob
import logging

import matplotlib
if '--noshow' in sys.argv:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

from pycurrents.adcp.raw_multi import Multiread
from pycurrents.num import Runstats
from pycurrents.codas import to_datestring
from pycurrents.plot.mpltools import add_UTCtimes
from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.adcp_specs import Sonar
from optparse import OptionParser

_log = logging.getLogger()

def get_data(cruisedir, inst, npts = -30000):
    instname = Sonar(inst).instname
    globstr = os.path.join(cruisedir, 'raw',inst,'*raw')
    filelist=glob.glob(globstr)
    _log.debug(globstr)
    if len(filelist) == 0:
        return None
    filelist.sort()
    m=Multiread(filelist, instname)
    if npts >= 0:
        data=m.read(stop=npts)
    else:
        data=m.read(start=npts)
    return data

def plot_data(data, ampbin=-4, min_yrange=3):

    f,ax=plt.subplots(figsize=(12,10), nrows=3, sharex=True)

    ax[0].plot(data.dday, data.amp[:,ampbin,0],'r')
    ax[0].plot(data.dday, data.amp[:,ampbin,1],'g')
    ax[0].plot(data.dday, data.amp[:,ampbin,2],'b')
    ax[0].plot(data.dday, data.amp[:,ampbin,3],'k')
    ax[1].plot(data.dday, data.temperature,color=[.2,.2,.2])
    ymin, ymax = ax[1].get_ylim()
    add_extra= (min_yrange - (ymax-ymin))/2.
    if add_extra > 0:
        ymin = ymin - add_extra
        ymax = ymax + add_extra
        ax[1].set_ylim(ymin, ymax)
    ax[1].grid(True)

    R=Runstats(data.temperature, nwin=15)
    ax[2].plot(data.dday, R.std, 'r')
    ax[2].grid(True)

    ax[0].set_ylim([20,230])
    ax[2].set_ylim([0,3.5])

    ax[2].set_xlabel('dday')
    ax[2].set_ylabel('deg C')
    ax[2].set_title('standard dev of temperature (15pts)')
    ax[1].set_ylabel('deg C')
    ax[1].set_title('temperature')
    ax[0].set_ylabel('counts')
    ax[0].set_title('Amplitude')

    plt.subplots_adjust(top=0.75)

    add_UTCtimes(ax[0], yearbase=data.yearbase, offset=35)

    return f

def save_fig(f, outfilebase, save_dir='./', thumbnail=True):
    outfile = os.path.join(save_dir, outfilebase)
    if thumbnail:
        savepngs((outfile, outfile+'T'), (90, 40), f)
        _log.debug('saving figure to %s.png and %sT.png', outfile, outfile)
    else:
        savepngs((outfile), (90), f)
        _log.debug('saving figure to %s.png', outfile)

#============================================


if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    parser = OptionParser(__doc__)


    parser.add_option("--title", dest="title",
                      default = None,
                      help="figure title (default is blank)")

    parser.add_option("--shipdir", dest="shipdir",
                      default = '/home/data',
                      help="location of cruise directories (default is /home/data)")

    parser.add_option("--cruisename", dest="cruisename",
                      default = 'current_cruise',
                      help="name of UHDAS cruise directory (defautl is current_cruise)")

    parser.add_option("--inst", dest="inst",
                      default = 'inst',
                      help="instrument directory, eg: os75, wh300, nb150")

    parser.add_option("--npts", dest="npts",
                      default = -30000,
                      help='\n'.join(["number of points to plot\n"
                    "(positive: from the beginning, negative: from the end)"]))

    parser.add_option("--ampbin", dest="ampbin",
                      default = -4,  help="plot amplitude of this bin (default=-4)")

    parser.add_option("--save_fig", dest="save_fig", action="store_true",
                       default=False, help="save as png")

    parser.add_option("--save_figT", dest="save_figT", action="store_true",
                       default=False, help="save as png also with a thumbnail")

    parser.add_option("--noshow", dest="noshow", action="store_true",
                       default=False, help="do not show the figure")

    parser.add_option("--outfilebase", dest="outfilebase",
                      default = None,
                      help="file base for pngs (default: do not save)")

    parser.add_option("-o", "--outdir", dest="outdir",
                 default = './',  help="save figures to this directory (default is ./)")

    parser.add_option("--outdir2", dest="outdir2",
       default = None,  help="also save figures to this directory (default is disabled) ")

    (options, args) = parser.parse_args()
    if len(args) > 1:
        print('cannot accept multiple arguments')
        sys.exit()
    if len(args) == 1:
        cruisedir = args[0]
    else:
        cruisedir = os.path.join(options.shipdir, options.cruisename)

    cruisename = os.path.basename(os.path.realpath(cruisedir))
    instname = Sonar(options.inst).instname
    data = get_data(cruisedir, options.inst, npts=int(options.npts))
    if not data:
        print('no data')
        sys.exit()

    if options.outdir or options.outdir2:
        if not options.outfilebase:
            outfilebase = '%s_%s' % (instname, 'noisy-temps')
        else:
            outfilebase=options.outfilebase

    fig = plot_data(data, ampbin=int(options.ampbin))

    ## annotate
    fig.text(.5,.97, '%s %s temperature and amplitude (bin %d)' % (cruisename,
                         instname, options.ampbin),
             color='b',    ha='center', size=15)
    start_date = to_datestring(data.yearbase, data.dday[0])
    end_date = to_datestring(data.yearbase, data.dday[-1])
    fig.text(.5,.93,'UTC date range: %s to %s' % (start_date, end_date),
             ha='center', size=15)

    if not options.noshow:
        plt.show()

    if (options.save_fig or options.save_figT):
        save_fig(fig, outfilebase, save_dir=options.outdir,
                 thumbnail=options.save_figT)
        if options.outdir2:
            save_fig(fig, outfilebase, save_dir=options.outdir2,
                 thumbnail=options.save_figT)
