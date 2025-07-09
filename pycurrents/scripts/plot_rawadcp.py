#! /usr/bin/env python
'''
 simple adcp plotter -- plot [amp,vel,cor] from raw data

## later add specs for
 - vertical = [bins, depth]
 - horizontal = [index, seconds, decimal day]
 - color range or auto

python plot_rawadcp.py [options] instrument file1 [file2 file3...]

eg.

python plot_rawadcp.py --pingtype nb --var amp os hly2012_157_15409.raw
 '''

import sys
import numpy as np

import matplotlib
if '--noshow' in sys.argv:
    matplotlib.use('Agg')
#import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from pycurrents.adcp.raw_multi import Multiread      # singleping ADCP
import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.adcp.qplot import qpc
from pycurrents.plot.mpltools import savepngs
from pycurrents.num import Stats            # mean,std,med (masked)
from pycurrents.adcp.raw_simrad import subsample_ppd

from optparse import OptionParser


def usage():
    print(__doc__)
    sys.exit()

# make the fonts bigger
font = {'weight' : 'bold',
        'size'   : 14}
matplotlib.rc('font', **font)



def matchbox_width(change_this_one, source_of_width):
    '''
    make source axes have same width as dest
    '''
    source = source_of_width
    dest = change_this_one
    bbox0 = dest.get_position()
    bbox1 = source.get_position()
    dest.set_position([bbox0.x0, bbox0.y0, bbox1.width, bbox0.height])
    plt.draw()


def print_chunks(m, pingtype):
    '''
    print header and chunks
    '''
    print('======= %s chunks by configuration  =========\n' % (pingtype))
    print('index Nfiles startdday  enddday   BT  (ping, nbins,binsize, blank, pulse) (...)')
    print('---- ---   --------- --------     --- ')
    print(m.list_chunks())
    print('\n')


def make_axes(fig):
    numplots = 5
    axlist = []
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

    ## make the top axes
    num = 4
    bottom = starty + num*(ax_height+pad)
    ax=fig.add_axes([left, bottom, width, height])
    ax.set_aspect('auto')
    ax.yaxis.set_major_locator(MaxNLocator(5, prune='lower'))
    axlist.append(ax)


    # make the next 3 (for qpc): sharex, sharey with top plot
    for num in [3,2,1]: #start with the highest (vertical) axes
        bottom = starty + num*(ax_height+pad)
        ax=fig.add_axes([left, bottom, width, height],
                        sharex=axlist[0], sharey=axlist[0])
        ax.set_aspect('auto')
        ax.yaxis.set_major_locator(MaxNLocator(5, prune='both'))
        axlist.append(ax)


    ## last plot; timeseries; sharex only
    num=0
    bottom = starty + num*(ax_height+pad)
    ax=fig.add_axes([left, bottom, width, height], sharex=axlist[0])
    ax.set_aspect('auto')
    ax.yaxis.set_major_locator(MaxNLocator(5, prune='both'))
    axlist.append(ax)




    return axlist

def plot4(var3d, refbin=None, **kwargs):
    '''
    plot 4x1 subplots of variable
    **kwargs passed to qpc
    eg. plot4(data.vel[::5,:,:], profs=data.dday, clim=[-4,4])
    # or to add a timeseries plot of one refbin (first bin = 1)
    plot4(data.vel[::5,:,:], refbin=5, profs=data.dday, clim=[-4,4])

    '''
    if refbin is None:
        fig, axlist=plt.subplots(nrows=4, sharex=True, sharey=True)
    else:
        fig = plt.figure()
        axlist=make_axes(fig)

    for ii in [0,1,2,3]:
        qpc(var3d[:,:,ii], ax=axlist[ii], **kwargs)


    if refbin is not None:
        irefbin = int(refbin)
        _ax = axlist[-1]
        _ax.plot(profs, var3d[:,irefbin-1, 0], 'r-')
        _ax.plot(profs, var3d[:,irefbin-1, 1], 'g-')
        _ax.plot(profs, var3d[:,irefbin-1, 2], 'b-')
        _ax.plot(profs, var3d[:,irefbin-1, 3], 'k-')
        matchbox_width(axlist[-1], axlist[0])
        _kw = dict(size=9, transform=_ax.transAxes)
        _ax.text(0.05, 0.8, 'beam 1', color='r', **_kw)
        _ax.text(0.05, 0.6, 'beam 2', color='g', **_kw)
        _ax.text(0.05, 0.4, 'beam 3', color='b', **_kw)
        _ax.text(0.05, 0.2, 'beam 4', color='k', **_kw)

    return fig


def plot_profile(var3d, xlim=None, **kwargs):
    '''
    plot 4x1 subplots of variable
    **kwargs passed to qpc
    eg. plot_profile(data.vel[::5,:,:], profs=data.dday)
    '''
    colors=['r','g','b','k']
    f,ax=plt.subplots(nrows=1)
    for ii in [0,1,2,3]:
        S=Stats(var3d[:,:,ii], axis=0)
        ax.plot(S.median, np.arange(len(S.N)), color=colors[ii],
                **kwargs)
    if xlim is not None:
        try:
            ax.set_xlim(xlim)
        except:
            raise
    ax.invert_yaxis()
    return f



if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    parser = OptionParser(__doc__)

    ## data extraction
    parser.add_option("-v", "--varname", dest="varname",
                      default='amp',
                      help="plot this 3D variable, eg 'amp','vel'")
    parser.add_option("-s", "--step", dest="step",
                      default = 1,
                      help="subsample by STEP")
    parser.add_option("--start", dest="start",
                      default = 1,
                      help="start at index START")
    parser.add_option("--stop", dest="stop",
                      default = None,
                      help="start at index STOP")
    parser.add_option("-p", "--pingtype", dest="pingtype",
                      default=None,
                      help='specify ping type (use with OS only)')
    parser.add_option("--ichunk", dest="ichunk",
                      default = 0,
                      help="0-based chunk to plot (if multiple)")

    parser.add_option("--list_chunks", dest="list_chunks", action="store_true",
                      default=False,
                      help="just list bb/nb chunks and exit")
    parser.add_option("--original_ec", dest="original_ec", action="store_true",
                      default=False,
                      help="ec150: do not run subsample_ppd; original amplitude counts")
    parser.add_option("--autoscale", dest="autoscale", action="store_true",
                      default=False,
                      help="autoscale color bar (overrides --clim)")


    ## plotting
    parser.add_option("--clim", dest="clim",
                      default=None,
                      help="colon-delimited min:max for colors")
    parser.add_option("-t", "--title", dest="title",
                      default=None,
                      help="plot title")
    parser.add_option("-V", "--Vcoord", dest="Vcoord",  default=None,
                      help="choose 'bins' (default) or 'meters'")
    parser.add_option("-H", "--Hcoord", dest="Hcoord", default=None,
                      help="choose 'index' (default), 'dday', or 'secs'")
    parser.add_option("--refbin", dest="refbin",
                      default = None,
                      help="also plot this bin (does not work for 'profile')")
    parser.add_option("--set_bad", dest="set_bad",
                      default=None,
                      help="valid color for masked values (default is masked)")

    parser.add_option("--beam_order", dest='beam_order', default=None,
       help="colon-delimited list of RDI beam numbers in order (eg. Revelle in 2020)")

    parser.add_option("-o", "--outfile", dest="outfile",
                      default = None,
                      help="save figure as OUTFILE.png")
    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")
    parser.add_option("--profile", dest="plot_profile",
                      action="store_true",
                      default=False,
                      help="plot as profile")

    (options, args) = parser.parse_args()
    if args[0] not in ['os','bb','wh','nb','ec','sv','pn']:
        print('must choose instrument type (before file list)')
        print('choose from: bb, nb, wh, os, ec, sv, pn')
        sys.exit()


    subsample_ec_vars = True # override - use original
    if args[0] == 'ec' and options.original_ec:
        subsample_ec_vars = False

    if options.beam_order:
        beam_index = []
        for num in options.beam_order.split(':'):
            beam_index.append(int(num)-1)
    else:
        beam_index=None

    if not options.show:
        matplotlib.use('agg')
    import matplotlib.pyplot as plt

    filelist=pathops.make_filelist(args[1:])

    stop=options.stop
    if options.stop is not None:
        stop=int(stop)
    start = int(options.start)
    step = int(options.step)
    ichunk = int(options.ichunk)

    instrument = args[0]
    m=Multiread(filelist, instrument, beam_index=beam_index)
    data = m.read(ends=1)
    default_pingtype = data.pingtype
    pingtypes = []

    print('\ndefault (first) pingtype is %s\n' % (default_pingtype))
    if hasattr(m, 'bs'):  #has .log.bin files, so we can do chunks
        # FIXME: What's going on here? How do we support Simrad 'ec'?
        for pingtype in ('nb', 'bb'):
            # all the rest will have 'bb'
            try:
                m.pingtype = pingtype
                print_chunks(m, pingtype)
                pingtypes.append(pingtype)
            except:
                if instrument in ('os', 'pn'):
                    print('no narrowband pings')

    if options.list_chunks:
        sys.exit()


    if options.pingtype is not None:
        if options.pingtype not in pingtypes:
            print('%s pings not available' % (options.pingtype))
            sys.exit()
        print('\nselecting pingtype %s\n' % (options.pingtype))
        m.pingtype = options.pingtype
    else:
        m.pingtype = default_pingtype

    m.select_chunk(ichunk)
    data=m.read(start=start, stop=stop, step=step)
    if instrument == 'ec' and subsample_ec_vars:
        subsample_ppd(data)
    if options.autoscale:
        clim = (np.min(data.amp), np.max(data.amp))

    if options.clim is not None:
        parts=options.clim.split(':')
        if len(parts) == 2:
            clim = [float(parts[0]), float(parts[1])]
        else:
            clim = [-abs(float(parts[0])), abs(float(parts[0]))]
    else:
        if options.varname == 'amp':
            if not options.autoscale:
                clim=[10,180]
        elif options.varname == 'vel':
            clim=[-3,3]
        elif options.varname == 'cor':
            clim=[20,200]

    if options.title is None:
        title = '%s, dday range %5.2f-%5.2f (%d %s pings)' % (
                        options.varname, data.dday[0], data.dday[-1],
                        len(data.dday), data.pingtype)
    else:
        title = options.title

    if options.plot_profile:
        fig=plot_profile(getattr(data, options.varname), xlim=clim)
        title = 'median ' + title
    else:
        #vertical coord
        if options.Vcoord is None:
            bins=np.arange(len(data.dep))
        elif options.Vcoord in ('meters', 'depth'):
            bins=data.dep
        else:
            print('ERROR: no vertical coordinate %s' % (options.Vcoord))
            sys.exit()
        #horiz coord
        if options.Hcoord is None:
            profs = np.arange(len(data.dday))
        elif options.Hcoord == 'dday':
            profs = data.dday
        elif options.Hcoord == 'secs':
            profs = (data.dday-data.dday[0])*86400
        else:
            print('ERROR: no horizontal coordinate %s' % (options.Hcoord))
            sys.exit()

        fig=plot4(getattr(data, options.varname), clim=clim,
                  refbin=options.refbin, profs=profs, bins=bins,
                  set_bad=options.set_bad)
    fig.text(.5,.95, title, ha='center')

    if options.outfile is not None:
        savepngs(options.outfile, dpi=72, fig=fig)

    if options.show:
        plt.show()
