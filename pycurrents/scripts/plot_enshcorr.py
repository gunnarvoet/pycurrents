#!/usr/bin/env python
'''
plot ens_hcorr.asc for perusal, reports, or web site
'''
## TODO
# make it also interactive


import sys
import os
import argparse
import logging

import matplotlib as mpl

if "--outfile" in sys.argv:
    mpl.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

from pycurrents.plot.mpltools import savepngs
from pycurrents.plot.mpltools import add_UTCtimes

from pycurrents.adcp.plot_enshcorr import HcorrPlotter
from pycurrents.system import logutils

_log = logging.getLogger()
_log.setLevel(logging.WARN)
handler = logging.StreamHandler()
handler.setFormatter(logutils.formatterMinimal)
_log.addHandler(handler)


# make the fonts bigger
font = {'weight' : 'bold',
        'size'   : 14}
mpl.rc('font', **font)



if __name__ == '__main__':


    parser = argparse.ArgumentParser(
        description="plot recent heading corrections from ens_hcorr.asc")

    parser.add_argument('--infile',
                        default='ens_hcorr.asc',
                        help='input filename (default is "ens_hcorr.asc"')

    parser.add_argument('--outfile',
                        default=None,
                        help='prefix for png files:' +
                       'if specified, print to file (and thumbnail); else show on screen')

    parser.add_argument('--skiplines',
                        default=0,
                        help='skip this many lines before reading')

    parser.add_argument('--yearbase',
                        default=None,
                        type=int, help='yearbase for conversion of dday to date')

    parser.add_argument('--titlestring',
                        default='',
                        help='title for png files')


    options = parser.parse_args()

    if not os.path.exists(options.infile):
        _log.error('no such file %s' % (options.infile))
        sys.exit(1)


    HP = HcorrPlotter()
    HP.get_data(options.infile, skiplines=int(options.skiplines))
    HP.make_plots(options.titlestring)
    if options.yearbase is None:
        HP.ax[2].set_xlabel('decimal day')
    else:
        plt.subplots_adjust(bottom=0.2)
        add_UTCtimes(HP.ax[2], options.yearbase, position='bottom')

    HP.ax[2].xaxis.set_major_formatter(ScalarFormatter(useOffset = False))


    if options.outfile:
        outfilebase = options.outfile.replace('.png','')
        destlist = [outfilebase, outfilebase+'T']
        savepngs(destlist, dpi=[90, 40], fig=HP.fig)
    else:
        plt.show()
