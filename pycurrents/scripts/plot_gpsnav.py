#!/usr/bin/env python

'''
plot lon/lat versus time and a cruise track from processing nav file
with 'dday', 'lon', 'lat' (usually  ".gps" files)

Designed to plot nav+topo from one processing directory at a time.

usage:

   plot_gpsnav.py procdir

'''

import logging
import sys
from optparse import OptionParser
from pycurrents.plot.mpltools import savepngs


# Standard logging
_log = logging.getLogger(__file__)

if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    parser = OptionParser(__doc__)

    parser.add_option("--title", dest="titlestr",
                      default = '',
                      help="plot title")

    parser.add_option("-o", "--outfilebase", dest="outfilebase",
                      default = None,
                      help="save figures as OUTFILE_topo.png and OUTFILE_txy.png")
    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")

    parser.add_option("-y", "--yearbase", dest="yearbase",
                      default = None,
                      help="add UTC timestamps to txy plot (requires this yearbase)")


    (options, args) = parser.parse_args()

    import matplotlib
    if not options.show:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from pycurrents.adcp import plotnav

    procdir = args[0]
    txy, navfile = plotnav.guess_txy(procdir)
    if not navfile:
        print('could not determine nav file in procdir %s' % (procdir))
        sys.exit()

    titlestr = options.titlestr
    fig_topo = plotnav.plot_topo(txy, titlestr)
    fig_txy = plotnav.plot_txy(txy, titlestr, options.yearbase)

    if options.outfilebase is not None:
        dpi = [70,]
        outfiles = [options.outfilebase + "_topo",]
        savepngs(outfiles, dpi=dpi, fig=fig_topo)

        outfiles = [options.outfilebase + "_txy",]
        savepngs(outfiles, dpi=dpi, fig=fig_txy)

    if options.show:
        plt.show()
