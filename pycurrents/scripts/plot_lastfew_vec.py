#!/usr/bin/env python



import os
import sys

## do not show plot if "savefigs" is true
if '--savefig' in sys.argv:
    import matplotlib
    matplotlib.use('Agg')
    savefig = True
else:
    savefig = False
    import matplotlib.pyplot as plt

# makes a logging.RootLogger instance with StreamHandler
import logging
_log = logging.getLogger(__file__)


from pycurrents.adcp.uhdasfile import guess_dbname
from pycurrents.adcp.plot_lastfew_vec import LastFewVec
from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.uhdas_defaults import annotate_time_color
from optparse import OptionParser

#----------------------------------------------------

def usage():

    tlist = [
        'plot_lastfew_vec.py: designed to plot the last few profiles of a',
        '                     live UHDAS processing directory in vector form',
        '                     to allow tracking of a frontal feature',
        '',
        'example usage at sea:  ',
        'plot_lastfew_vec.py --uhdas_dir /home/data/current_cruise --sonar os150nb --savefig',
        '',
        ' example at home:',
        'plot_lastfew_vec.py --procdir os150nb --startdd 122',
        ]
    return '\n'.join(tlist)

#----------------------------------------------------


if __name__ == '__main__':


    parser = OptionParser(usage())


    ## use this to specify a database for exploration

    parser.add_option("--procdir", dest="procdir",
                      default=None,
                      help="path to processing directory (or database)")

    ## use this to get at a live uhdas processing directory

    parser.add_option("--uhdas_dir", dest="uhdas_dir",
                      default=None,
                      help="part of path for data, eg. /home/data/KM1703")

    parser.add_option("-s", "--sonar", dest="sonar",
                      default=None,
                      help="if using uhdas_dir, specify instrument (+pingtype), eg: 'wh300', 'os75bb'")


    # "processing" options ---------------------------------
    parser.add_option("--startdd", dest="startdd",
                      default = None,
                      help="start at this decimal day; default is end of the data")

    parser.add_option("--hours", dest="hours",
                      default = -1,  # history in hours
                      help="how much data to get (default = -1: last 1 hour)")

    parser.add_option("--startbins", dest="startbins",
                      default = '2:30',
                      help="colon-delimited default bins to start reference layers, eg: '2:30'; bins start at 2 and 30")

    parser.add_option("--numbins", dest="numbins",
                      default = 5,
             help="number of bins to average in reflayer (default=5)")

    parser.add_option("--annotate_time_color", dest="annotate_time_color",
                      default = annotate_time_color,
             help="color of time labels")

    parser.add_option("--avgwin", dest="avgwin",
                      default = 1,
             help="averaging window (should be odd); default = 1 (no averaging)")

    parser.add_option("--vecscale", dest="vecscale",
                      default = 'auto',
                      help="vector length multiplier (larger = longer)")

    parser.add_option("--plot_all_shallow", dest="plot_all_shallow",
                      default = False, action="store_true",
            help="if avgwin>1, also plot the original values in top reflayer")

    parser.add_option("--outfile", dest="outfilebase",
                      default = None,
                      help="save figure as OUTFILE.png")

    parser.add_option("--verbose", dest="verbose",
                      default = False, action="store_true",
                      help="print debugging information")

    parser.add_option("--use_quiver", dest="use_quiver",
                      default = False, action="store_true",
     help="use quiver for vector plot.  note: DECREASE vecscale for longer vectors")

    (options, args) = parser.parse_args(args=sys.argv)


    if options.procdir is not None:
        options.dbpath = guess_dbname(options.procdir)
        options.cruisename = options.procdir
        options.sonar = ''
    else:
        procdir = os.path.join(options.uhdas_dir, 'proc', options.sonar)
        options.dbpath = guess_dbname(procdir)
        options.cruisename = os.path.split(options.uhdas_dir)[-1]

    if not os.path.exists('%sdir.blk' % (options.dbpath)):
        raise IOError('cannot find database %s' % (options.dbpath))

    if options.startdd is not None:
        options.startdd = float(options.startdd)

    options.rdi_startbins = []
    for rb in options.startbins.split(':'):
        options.rdi_startbins.append(int(rb))
    options.numbins = int(options.numbins)
    options.history = float(options.hours)
    options.avgwin = int(options.avgwin)
    try:
        if options.vecscale == 'auto':
            options.autoscale = True
            options.vecscale = None
    except:
        options.autoscale = False
        options.vecscale = float(options.vecscale)

    LFV = LastFewVec(options)
    f, ax = LFV.setup_axes()
    LFV.get_data()
    LFV.stage_refls()
    if options.use_quiver:
        LFV.plot_lastvec_quiver(f, ax)
    else:
        LFV.plot_lastvec(f, ax)

    LFV.place_labels(f, dy=.2)  # for single axes

    if options.outfilebase is not None:
        savepngs('%s.png' % (options.outfile), 90, f)
    else:
        plt.show()
