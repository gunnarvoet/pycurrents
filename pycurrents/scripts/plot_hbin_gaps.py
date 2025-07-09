#!/usr/bin/env python

'''
Plot gaps in heading messages (useful for GPS-based headings)

usage:

- specify a wildcard or list of files, or a UHDAS rbin directory

   plot_hbin_gaps.py [options]  /home/data/HLY18TA/gbin/heading
   plot_hbin_gaps.py [options]  /home/data/HLY18TA
   example :
       plot_hbin_gaps.py --instmsg trimble:gps  /home/data/HLY18TA

NOTE: by default the program plots the last 1200 points and
      a running average of 100 points to calculate  "Percent FAIL"

For a closer look, use
       plot_hbin_gaps.py --start -3600 --halfwinmins 1   --instmsg trimble:gps  /home/data/HLY18TA

'''

import os
import sys
import logging
from optparse import OptionParser
#
#if ('-o' in sys.argv) or ('--outfile' in sys.argv):
#    matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib

from pycurrents.file.binfile_n import BinfileSet
from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.plot_hbin_subs import get_filelist, plot_gaps

_log = logging.getLogger(__name__)
_log.setLevel('INFO')

# make the fonts bigger
font = {'weight' : 'bold',
        'size'   : 14}
matplotlib.rc('font', **font)



# Standard logging
_log = logging.getLogger(__file__)

if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    if '--help' in sys.argv:
        print(__doc__)

    parser = OptionParser()


    parser.add_option("-s", "--step", dest="step",
                      default = 1,
                      help="subsample by STEP (default is 1)")

    parser.add_option("--startdday", dest="startdday", default = None,
               help="choose dday to start the plot")

    parser.add_option("--ndays", dest="ndays", default = None, # i.e. all
               help="choose how many days to plot")

    parser.add_option("--yearbase", dest="yearbase",
                      default = None,
               help="adds UTC timestamps to txy plot (requires yearbase)")

    parser.add_option("--halfwinmins", dest="halfwinmins",
                      default = 60,
                     help='\n'.join([
                         "number of points to smooth over (Blackman filter half-win)",
                         "default = 1 hour (60 min)"
                         ]))

    parser.add_option("-o", "--outfile", dest="outfile",
                      default = None,
                      help="save figure as OUTFILE.png (do not display)")

    parser.add_option("--instmsg", dest="instmsg",
                      default = None,
                help="specify instrument and message eg. trimble_gps ")


    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")

    parser.add_option("--print_instmsg", dest="print_instmsg",
                      action="store_true",
                      default=False,
                      help="print instrument+message strings")

    parser.add_option("--minutes_ago", dest="minutes_ago",
                      action="store_true",
                      default=False,
                   help='\n'.join(["label times with 'minutes ago', not decimal day",
                                      "(this option disables UTC timestamps)",
                                      ]))

    (options, args) = parser.parse_args()

    if len(args) == 0:
        _log.warning('must specify wildcard list of hbin files, or UHDAS directory')
        sys.exit(1)

    filelist=get_filelist(args)
    data=BinfileSet(filelist, stop=2)
    if not options.instmsg or options.print_instmsg:
        _log.warning('Options for instmsg are:\n' + '\n'.join(data.columns[1:]))
        sys.exit()
    if options.instmsg not in data.columns:
        _log.warning('%s is not in the list of options:\n' % (options.instmsg))
        _log.warning('\n'.join(data.columns[1:]))
        sys.exit(1)

    data=BinfileSet(filelist, step=int(options.step))

    if len(data.dday) == 0:
        _log.error('%d files but no data' % (len(filelist)))

    first_day = data.starts['dday'][0]  # dday
    last_day  = data.ends['dday'][-1]  # dday
    if options.startdday:
        startdday = options.startdday
    else:
        startdday = first_day

    if options.ndays:
        ndays = float(options.ndays)
        if ndays < 0:
            data.set_range(ddrange=[last_day + ndays, last_day], cname='dday')
        if ndays > 0:
            data.set_range(ddrange=[startdday, startdday + ndays], cname='dday')
    else:
        ndays = last_day-first_day

    if len(data.dday) == 0:
        _log.error('no data left after specifying start/stop')
        sys.exit(1)


    fig=plot_gaps(data, options.instmsg,
                  yearbase=options.yearbase,
                                 minutes_ago = options.minutes_ago,
                                 halfwinmins = options.halfwinmins,
                           )
    sep = os.path.sep
    uhdas_dir = os.path.realpath(filelist[0]).split(os.path.sep)[-4]
    fig.text(.5,.93,'UHDAS dir = %s' % (uhdas_dir), ha='center')
    if int(options.step) > 1:
        fig.text(.95,.91,'(data subsampled by %s)' % (options.step), ha='right')
    fig.text(.5,.97,'%s assessment' % (options.instmsg), weight='bold', ha='center')

    restore_ion = False
    if not options.show and plt.isinteractive():
        plt.ioff()
        restore_ion = True

    if options.outfile is not None:
        savepngs(options.outfile, dpi=110, fig=fig)

    if options.show:
        plt.show()

    if restore_ion:
        plt.ion()
