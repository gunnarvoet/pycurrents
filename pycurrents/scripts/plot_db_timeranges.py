#!/usr/bin/env python
'''
plot_db_timeranges.py [-o outfile] [-t title] [--noshow]  uhdas_dir [or procdir]

- looks in uhdas_dir/proc (or procdir) for valid sonar names
- plots sonar usage over time for a quick look

--help             : print help and exit

'''
import os
import glob
import sys
import logging
from optparse import OptionParser

import matplotlib
if '--noshow' in sys.argv:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.uhdas_report import DB_TimerangePlotter
from pycurrents.system import logutils


logging.captureWarnings(True)
_log = logging.getLogger()
_log.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logutils.formatterMinimal)
_log.addHandler(handler)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    parser = OptionParser(usage=__doc__)

    parser.add_option("-t", "--title", dest="title",
                      default = None,
                      help="text string for title, usually cruise name")

    parser.add_option('-o', '--outfile',
                        help='save figure as OUTFILE.png (otherwise show to screen)')

    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")


    (options, args) = parser.parse_args()

    if len(args) != 1:
        print(__doc__)
        sys.exit()

    targetdir = args[0]

    if targetdir[-1] == '/':
            targetdir = targetdir[:-1]

    dblist_uhdas = glob.glob(os.path.join(targetdir,'proc/*/adcpdb/*dir.blk'))
    dblist_proc = glob.glob(os.path.join(targetdir,'*/adcpdb/*dir.blk'))
    dblist_proc2 = glob.glob(os.path.join(targetdir,'adcpdb/*dir.blk'))

    dblist = dblist_uhdas + dblist_proc + dblist_proc2
    dblist.sort()

    if len(dblist) > 0:
        DBTP = DB_TimerangePlotter(dblist)
        if options.title is None:
            options.title = 'SONAR USAGE'
        fig = DBTP.plot_sonars(options.title)
    else:
        _log.warning('no CODAS databases exist for this cruise')
        fig = None

    restore_ion = False
    if plt.isinteractive():
        plt.ioff()
        restore_ion = True

    if options.show:
        plt.show()

    if fig:
        if options.outfile is not None:
            savepngs(options.outfile, dpi=72, fig=fig)

    if restore_ion:
        plt.ion()
