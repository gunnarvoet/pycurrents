#!/usr/bin/env python

'''
This is the same as plot_posmv.py except that you
must specify the *.pmv.rbin files

   plot_pashr.py *.pmv.rbin

NOTE: program subsamples by 30 for speed; use all points by saying

   plot_pashr.py -s1 *.pmv.rbin

'''

import os
import sys
from optparse import OptionParser
import logging

if ('--noshow' in sys.argv):
    import matplotlib
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.plot_posmv_subs import plot_posmv


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

    parser = OptionParser(usage=__doc__)


    parser.add_option("-s", "--step", dest="step",
                      default = 30,
                      help="subsample by STEP")
    parser.add_option("--start", dest="start",
                      default = 1,
                      help="start at index START")
    parser.add_option("--stop", dest="stop",
                      default = None,
                      help="start at index STOP")


    parser.add_option("--cutoff", dest="cutoff",
                      default = 0.02,
     help="cutoff to accept heading accuracy (exceeds is bad).default =0.02)")

    parser.add_option("--yearbase", dest="yearbase",
                      default = None,
                      type = int,
                      help="add UTC timestamps to txy plot (requires yearbase)")

    parser.add_option("-o", "--outfile", dest="outfile",
                      default = None,
                      help="save figure as OUTFILE.png (do not display)")
    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")

    (options, args) = parser.parse_args()


    if not options.show and options.outfile is None:
        _log.error('not showing figure; must select an output file')
    
    # filelist is explicit
    filelist=args

    data=BinfileSet(filelist, stop=2)
    if 'acc_heading' not in data.columns:
        _log.info('columns are: ' + '\n'.join(data.columns) + '\n')
        _log.error('no heading accuracy field in data. exiting')

    stop=options.stop
    if options.stop is not None:
        stop=int(stop)
    start = int(options.start)
    step = int(options.step)
    data=BinfileSet(filelist, start=start, stop=stop, step=step)

    fig=plot_posmv(data, head_acc_cutoff=float(options.cutoff), yearbase=options.yearbase)
    fig.text(.5,.96,'posmv dir = %s' % os.path.split(filelist[0])[0],
              ha='center')
    fig.text(.95,.93,'(data subsampled by %s)' % (options.step), ha='right')

    fig.text(.07,.93,'(heading accuracy cutoff %3.2f)' % (float(options.cutoff)), ha='left')
    restore_ion = False
    if not options.show and plt.isinteractive():
        plt.ioff()
        restore_ion = True

    if options.outfile is not None:
        savepngs(options.outfile, dpi=72, fig=fig)

    if options.show:
        plt.show()

    if restore_ion:
        plt.ion()
