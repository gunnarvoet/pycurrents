#!/usr/bin/env python

'''
Plot Ashtech device reacquisition flag from $PASHR,ATT message

usage:

- specify a wildcard or list of files, or a UHDAS rbin directory
- this program plots the reaquisition value, so the files must contain it.

   plot_ashtech_reacq.py [options]  /home/data/HLY18TA/rbin/abxtwo/*adu*.rbin
   plot_ashtech_reacq.py [options]  /home/data/HLY18TA
   example :
       plot_ashtech_reacq.py --ash_name adu800  /home/data/HLY18TA

NOTE: by default the program plots the last 1200 points and
      a running average of 100 points to calculate  "Percent FAIL"

For a closer look, use
       plot_ashtech_reacq.py --start -3600 --halfwinmins 1   --ash_name adu800  /home/data/HLY18TA

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
from pycurrents.adcp.plot_ashtech_subs import get_filelist, plot_reacquisition


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
                      default = 30,
                      help="subsample by STEP (default is 30)")
    parser.add_option("--start", dest="start",
                      default = 0,
                      help="start at index START (default is the beginning")
    parser.add_option("--stop", dest="stop",
                      default = None,
                      help="start at index STOP (default is the end)")

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

    parser.add_option("--ash_name", dest="ashtech",
                      default = None,
                help="if using UHDAS directory name, specify ashtech instrument directory ")


    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")

    parser.add_option("--minutes_ago", dest="minutes_ago",
                      action="store_true",
                      default=False,
                   help='\n'.join(["label times with 'minutes ago', not decimal day",
                                      "(this option disables UTC timestamps)",
                                      ]))

    (options, args) = parser.parse_args()

    filelist=get_filelist(args, ash_inst=options.ashtech)
    data=BinfileSet(filelist, stop=2)
    if 'reacq' not in data.columns:
        _log.info('columns are: ' + '\n'.join(data.columns) + '\n')
        _log.error('no reaquisition field in data. exiting')

    stop=options.stop
    if options.stop is not None:
        stop=int(stop)
    start = int(options.start)
    step = int(options.step)
    data=BinfileSet(filelist, start=start, stop=stop, step=step)

    fig=plot_reacquisition(data, yearbase=options.yearbase,
                                 minutes_ago = options.minutes_ago,
                                 halfwinmins = options.halfwinmins,
                           )
    fig.text(.5,.93,'ashtech dir = %s' % os.path.split(filelist[0])[0],
              ha='center')
    if int(options.step) > 1:
        fig.text(.95,.91,'(data subsampled by %s)' % (options.step), ha='right')
    fig.text(.5,.97,'Ashtech QC assessment', weight='bold', ha='center')

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
