#!/usr/bin/env python

'''
plot lon/lat versus time and a cruist track from rbins files
with 'dday', 'lon', 'lat' (usually  ".gps.rbin" files)

usage:

   plot_rnav.py  /home/data/km1103/rbin/gpsnav/*.gps.rbin

NOTE: program subsamples by 30 for speed; use all points by saying


   plot_rnav.py -s1  /home/data/km1103/rbin/gpsnav/*.gps.rbin

'''

import logging
import sys
from optparse import OptionParser

import matplotlib.pyplot as plt

from pycurrents.adcp.qplot import qnav1, qtxy
import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.plot.mpltools import savepngs

# Standard logging
_log = logging.getLogger(__file__)

if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    parser = OptionParser(__doc__)


    parser.add_option("-s", "--step", dest="step",
                      default = 30,
                      help="subsample by STEP")
    parser.add_option("--start", dest="start",
                      default = 1,
                      help="start at index START")
    parser.add_option("--stop", dest="stop",
                      default = None,
                      help="start at index STOP")

    parser.add_option("--title", dest="titlestr",
                      default = '',
                      help="plot title")

    parser.add_option("-o", "--outfile", dest="outfile",
                      default = None,
                      help="save figures as OUTFILE_topo.png and OUTFILE_txy.png")
    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")
    parser.add_option("-y", "--yearbase", dest="yearbase",
                      default = None,
                      help="add UTC timestamps to txy plot (requires this yearbase)")


    (options, args) = parser.parse_args()

    filelist=pathops.make_filelist(args)
    data=BinfileSet(filelist, stop=2)
    for name in ['dday','lon','lat']:
        if name not in data.columns:
            _log.info('columns are: ' + '\n'.join(data.columns) + '\n')
            _log.error('Field "%s" not found in data. Exiting.', name)
            sys.exit()


    stop=options.stop
    if options.stop is not None:
        stop=int(stop)
    start = int(options.start)
    step = int(options.step)
    data=BinfileSet(filelist, start=start, stop=stop, step=step)

    fig_topo = plt.figure(figsize=(10,8), dpi=110)
    qnav1(data, fig=fig_topo)
    fig_topo.text(.5,.95,'%s' % options.titlestr, ha='center')

    if options.yearbase is None:
        # assume UHDAS file names
        from pycurrents.adcp.uhdasfileparts import FileParts
        yearbase = FileParts(filelist[0]).year
    fig_txy = plt.figure(figsize=(10,8), dpi=110)
    qtxy(data, fig=fig_txy, yearbase=yearbase)
    fig_txy.text(.5,.95,'%s' % options.titlestr, ha='center')

    restore_ion = False
    if not options.show and plt.isinteractive():
        plt.ioff()
        restore_ion = True

    if options.outfile is not None:
        dpi = [110,]
        outfiles = [options.outfile + "_topo",]
        savepngs(outfiles, dpi=dpi, fig=fig_topo)

        outfiles = [options.outfile + "_txy",]
        savepngs(outfiles, dpi=dpi, fig=fig_txy)

    if options.show:
        plt.show()

    if restore_ion:
        plt.ion()
