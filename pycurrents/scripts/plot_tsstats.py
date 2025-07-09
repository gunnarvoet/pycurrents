#!/usr/bin/env python
'''
Plot codas error variables errvel and TSERIES_DIFFSTATS
to screen, and print summary statistics to stdout.
==>This is a new variable.  Most datasets do not have it.

usage:

plot_tsstats.py [--ndays N] [--title TEXT] databasepath

eg:

# whole cruise

plot_tsstats.py  -t  "TN267 os75nb stats" TN267_os75nb

# last day of data

plot_tsstats.py  -n -1 -t stats  path/to/cruisedir

'''


import logging
import sys
from optparse import OptionParser

import matplotlib.pyplot as plt

from pycurrents.adcp.tseries_diffstats import get_data, plot_data
from pycurrents.adcp.uhdasfile import guess_dbname

from pycurrents.system import logutils

_log = logging.getLogger()
_log.setLevel(logging.WARN)
handler = logging.StreamHandler()
handler.setFormatter(logutils.formatterMinimal)
_log.addHandler(handler)


def usage():
    print(__doc__)
    sys.exit()


if __name__ == '__main__':

    if len(sys.argv)==1:
        usage()

    parser = OptionParser(__doc__)

    parser.add_option("-n", "--ndays", dest="ndays",
                      default = None,
                      help="(float) number of days of data to get")
    parser.add_option("-t", "--title", dest="tstr",
                      default = '',
                      help="title string")

    (options, args) = parser.parse_args()
    dbname = guess_dbname(args[0])

    ndays = None
    if options.ndays is not None:
        ndays = float(options.ndays)

    data = get_data(dbname, ndays=ndays)

    fig, ax, sd = plot_data(data, titlestr=options.tstr)
#    print(stats_str(sd))

    plt.show()

#from pycurrents.plot.mpltools import savepngs

#    if options.figname is not None:
#        fullfilebase = os.path.join(path, '%s_stats' % (options.figname))
#        savepngs(fullfilebase,  90, fig=fig)
#        print 'wrote fig to ', fullfilebase+'.png'
