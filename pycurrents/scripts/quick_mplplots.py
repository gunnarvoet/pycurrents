#!/usr/bin/env python
'''
This file contains the mechanisms use plotting classes on the command line.

Do this in the processing directory, after processing has been run

quick_mplplots.py --yearbase 2009 [options]


         [options] are

         --cruiseid CRUISEID              # CRUISEID is a title
         --printformats [pdf:png:ps]      # formats supported by matplotlib.
                                          # (colon-delimited list)
                                          # Default is pdf
         --plots2run x:y:z                # colon-delimited list of plots
                                          #   default is to plot all
                                          #   'all' is the same as
                                 # temp:npings:nav:refl:hcorr:btcal:wtcal

To make a specific plot, use a subset of the above colon-delimited list

  use this string   to plot this
       temp           temperature (edit/ directory)
       npings          number of pings per ensemble (edit/ directory)
       uvship         diff uship,vship calculated using nav, or pings
       nav            cruise track (nav directory)
       refl           reference layer (nav directory)
       hcorr          heading correction (cal/rotate directory)
       btcal          bottom track calibration  (cal/botmtrk directory)
       wtcal          water track calibration (cal/watertrk directory)

  NOTE: btcal and wtcal plot *and* print statistics (default) ; can be overrridden

'''

import sys
import os
import numpy as np
from optparse import OptionParser
import logging

from pycurrents.adcp.quick_mpl import dirdict, classdict
from pycurrents.system.misc import Cachefile
from pycurrents.adcp.reader import get_dbname

# Standard logging
_log = logging.getLogger(__file__)


def main():

    import matplotlib.pyplot as plt
    # Shutting down "More than 20 figures have been opened" RuntimeWarning (see Ticket 2508)
    # plt.rcParams.update({'figure.max_open_warning': 0})

    parser = OptionParser(__doc__)
    parser.add_option("--cruiseid", dest="cruiseid",
                 default='ADCP',
                 help="cruise ID or title for web page and some plots ")
    parser.add_option("--yearbase", dest="proc_yearbase",
                          type='int',
                          help="processing yearbase ")
    parser.add_option("--printformats", dest="printformats",
                          default='png:pdf',
                          help="print format (png, pdf,...) ")
    parser.add_option("--plots2run", dest="plots2run",
                          default='all',
        help="'all', or colon-delimited list 'temp:npings:uvship:nav:refl:hcorr:btcal:wtcal'")

    parser.add_option("--noshow", dest="show", action="store_false",
                          default=True)


    options, args = parser.parse_args()

    if len(sys.argv[1:]) == 0:
        print(__doc__)
        sys.exit()

    if options.plots2run == 'all':
        plots2run = 'temp:npings:nav:uvship:refl:hcorr:btcal:wtcal'
    else:
        plots2run = options.plots2run

    try:
        plotlist = plots2run.split(':')
    except Exception as e:
        print(f'could not split {plots2run} with ":"')
        print(__doc__)
        print(f"threw : {e}")
        sys.exit()

    if not np.iterable(plotlist):
        plotlist = [plotlist,]

    cruiseid = options.cruiseid

    yearbase = options.proc_yearbase
    if not options.proc_yearbase and os.path.exists('dbinfo.txt'):
        cc = Cachefile(cachefile='dbinfo.txt')
        cc.read()
        if cc.cachedict.yearbase is not None:
            yearbase = cc.cachedict.yearbase

    if yearbase is None:
        print('must set yearbase')
        sys.exit()
    printformats = options.printformats

    ## always make an overview vector plot
    fulldbname = get_dbname()
    dbname = os.path.split(fulldbname)[-1]
    print('found database %s' % (os.path.join('adcpdb',dbname),))

    if not os.path.exists(fulldbname+'dir.blk'):
        print('cannot find database block file %s' % (fulldbname+'dir.blk'))
        sys.exit()

    restore_ion = False
    if not options.show and plt.isinteractive():
        plt.ioff()
        restore_ion = True

    ## (3) ========== loop to make plots ===================

    startdir = os.getcwd()
    for plotname in plotlist:
        if plotname not in list(dirdict.keys()) or plotname not in list(classdict.keys()):
            print('unknown or unsupported plot name %s' % (plotname,))
            sys.exit()


    for plotname in plotlist:
        plotdir = dirdict[plotname]
        os.chdir(plotdir)
#        log.info('before plot, starting  at %s' % (os.getcwd()))
        try:
            _log.info('\n---> trying to make %s plot in %s directory' % (plotname, plotdir))
            Plotter = classdict[plotname](proc_yearbase=yearbase,
                                         dbname=dbname,
                                         printformats=printformats,
                                         cruiseid=cruiseid)
            Plotter.write()
            Plotter()

        finally:
            os.chdir(startdir)

    if options.show:
        plt.show()

    if restore_ion:
        plt.ion()

if __name__ == '__main__':
    main()
