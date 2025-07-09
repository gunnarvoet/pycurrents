#!/usr/bin/env python

'''
usage: any of the following will work (for a standard uhdas data directory)

   plot_hbins.py /home/data/km1103/gbin/heading/km_2011_123*.hbin
   plot_hbins.py /home/data/km1103/gbin/heading
   plot_hbins.py /home/data/km1103/gbin/
   plot_hbins.py /home/data/km1103/

NOTE: program subsamples by 30 for speed; use all points by saying

   plot_hbins.py -s1  /home/data/km1103

NOTE: if "gbin/heading" does not exist, you can make it with make_hbins.py
'''

import logging
import os
import sys
from optparse import OptionParser

import numpy as np

import matplotlib.pyplot as plt

import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.plot_hbin_subs import plot_hbins

_log = logging.getLogger(__file__)


def get_filelist(arglist):
    '''
    guess and return hbin filelist
    '''
    if len(arglist) > 1:
        return arglist
    #
    arg = arglist[0]
    if os.path.isfile(arg) or os.path.islink(arg):
        return(arglist)
    contents=os.listdir(arg)
    # assume directory
    for c in contents:
        # "heading" directory, with *.hbin; return *hbin
        if 'hbin' == c[-4:]:
            globstr = os.path.join(arg, '*hbin')
            return pathops.make_filelist(globstr)
    if 'heading' in contents:
        globstr = os.path.join(arg,'heading','*hbin')
        return pathops.make_filelist(globstr)
    if 'gbin' in contents:
        globstr = os.path.join(arg,'gbin','heading','*hbin')
        return pathops.make_filelist(globstr)
    print('contents: ', contents)
    _log.error('==> could not find hbins here')


if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    parser = OptionParser(__doc__)


    # data extraction
    parser.add_option("--startdday", dest="startdday", default = None,
               help="choose dday to start the plot")

    parser.add_option("--ndays", dest="ndays", default = None, # i.e. all
               help="choose how many days to plot")

    parser.add_option("-s", "--step", dest="step",
                      default = 30,
                      help="subsample by STEP")

    parser.add_option("-i", "--instnum", dest="instnum", default=1)

    parser.add_option("-o", "--outfile", dest="outfile",
                      default = None,
                      help="save figure as OUTFILE.png")
    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")

    parser.add_option("-q", "--query", dest="query", action="store_true",
                      default=False,
                      help="print data column names (and exit)"
                      )

    (options, args) = parser.parse_args()

    filelist=get_filelist(args)

    if options.query:
        data=BinfileSet(filelist, stop=2)
        print('\n      number   instrument_message')
        print('      -------   -------------------')
        for ii in np.arange(len(data.columns)-1)+1:
            print('%10d      %s' % (ii, data.columns[ii]))
        print('\n')
        sys.exit()

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


    fig=plot_hbins(data, instnum=int(options.instnum))
    fig.text(.5,.95,'hbin dir = %s' % os.path.split(filelist[0])[0],
              ha='center')
    fig.text(.5,.92,'data subsampled by %s' % (options.step), ha='center')




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
