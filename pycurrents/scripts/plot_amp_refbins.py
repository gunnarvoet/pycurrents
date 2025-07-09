#! /usr/bin/env python
'''
run watertrack calibration on specified bins to look for a vertical structure

NOTES:
 - reference layers will not overlap
 - calculations will not go deeper than "last_refbin"
 - shallowest bin is bin=1
 - files (figure and data) are always saved to the current working directory.

eg.
        cd cal/watertrk
        plot_amp_refbins.py -n 2

eg.
        ls cal/watertrk
        plot_amp_refbins -p .


You MUST specify some arguments (num_refbins or procdir) for it to do anything

'''

## TODO : proper use of figure (not "gca())

import sys
import os

import numpy as np

import matplotlib
if '--noshow' in sys.argv:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

from pycurrents.adcp.find_amp_refbins import run_adcpsect, run_timslip
from pycurrents.adcp.find_amp_refbins import get_WT_str, parse_wtstr
from pycurrents.adcp.find_amp_refbins import plot_cals, write_cals, read_cals
from pycurrents.plot.mpltools import savepngs
from pycurrents.codas import get_profiles         # general codasdb reader
from pycurrents.system.misc import Cachefile
from pycurrents.adcp.uhdasfile import guess_dbname

# (1) run from cal/watertrk
# (2) choose endbin and reflayer step

from optparse import OptionParser


def usage():
    print(__doc__)
    sys.exit()



if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    parser = OptionParser(__doc__)

    ## data extraction
    parser.add_option("-f", "--first_refbin", dest="first_refbin",
                      default=1,
                      help="shallowest reference level bin")
    parser.add_option("-l", "--last_refbin", dest="last_refbin",
                      default=80,
                      help="deepest reference level bin")
    parser.add_option("-n", "--num_refbins", dest="num_refbins",
                      default = 1,
                      help="number of bins in the reference layer")
    parser.add_option("-s", "--speed_cutoff", dest="speed_cutoff",
                      default = 3.0,
                      help="speed change to count in WT cal points")
    parser.add_option("--morepts", dest="morepts", action="store_true",
                      default=False,
                      help="less smoothing in the WT calculation")
    parser.add_option("-o", "--outfilebase", dest="outfilebase",
                      default = 'wt_cal_refbins',
          help="save figure and data as OUTFILEBASE.png, OUTFILEBASE.txt]")
    parser.add_option("-p", "--procdir", dest="procdir",
                      default = '../..',
      help="processing directory root (default: running from cal/watertrk)")
    parser.add_option("--ddrange", dest="ddrange",
                      default = 'all',
         help="decimal day range for calculation (eg. if bin size changes)")
    parser.add_option("--noshow", dest="noshow", action="store_true",
                      default=False,
                      help="do not display figure (default shows to screen)")
    parser.add_option("--replot", dest="replot_only", action="store_true",
                      default=False,
                      help="replot from existing data file; do not regenerate data file")
    parser.add_option("--title", dest="title",
          default = None, help="title for figure")


    (options, args) = parser.parse_args()

    first_refbin = int(options.first_refbin)
    last_refbin = int(options.last_refbin)
    num_refbins = int(options.num_refbins)

    if ':' in options.ddrange:
        startdd, enddd = options.ddrange.split(':')
        ddrange = (np.float64(startdd), np.float64(enddd))
    elif options.ddrange == 'all':
        ddrange=None
    else:
        print('cannot parse decimal day range "%s"' % (options.ddrange))
        sys.exit()

    # set up paths, find database
    proc_root = options.procdir
    dbinfofile = os.path.join(proc_root, 'dbinfo.txt')
    if not os.path.exists(dbinfofile):
        print('The file named "dbinfo.txt" does not exist.')
        print('Are you in cal/watertrk?')
        print('Did you need to specify a processing directory?')
        sys.exit()

    try:
        dbinfo = Cachefile(cachefile=dbinfofile)
        dbinfo.read()
        dbpath = guess_dbname(proc_root)
        calfile = 'aship_refl.cal'

        adcp_data = get_profiles(dbpath, ddrange=ddrange)
        # this is a very strong assumption -- i.e. that the bins in the first prfile
        #     represent the settings throughout the dataset.  But watertrack
        #     calibration is done with bins anyway so we already have a problem.
        dep = adcp_data.dep
        print('extracting depth from first profile at %f' % (adcp_data.dday[0]))
    except:
        print('could not read data fron database %s' % (dbpath))
        sys.exit()

    last_refbin = min(len(dep), last_refbin)# don't go deeper than the dataset
    ima = np.ma.masked_array(np.arange(len(dep)), mask=dep.mask)
    max_good_bin = max(np.ma.compressed(ima))
    last_refbin = min(last_refbin, max_good_bin)

    # deal with various display situations
    showfig = True
    if options.noshow:
        showfig = False

    restore_ion = False
    if not showfig and plt.isinteractive():
        plt.ioff()
        restore_ion = True


    # get and plot data
    if options.title is None:
        dirname = os.path.split(os.path.realpath(proc_root))[-1]
        title = '%s: depth-dependent scale factor (watertrack calibration)' % (
            dirname)
    else:
        title = options.title

    caldatafile = options.outfilebase + '.txt'

    if not options.replot_only:
        allcal=[]
        print('running watertrack cal for bins ...')
        for rlstart in np.arange(first_refbin, last_refbin, num_refbins):
            print('%d through %d' % (rlstart, rlstart+num_refbins-1))
            run_adcpsect(dbpath, dbinfo.cachedict.yearbase, rlstart,
                         rlstart+num_refbins-1, ddrange=ddrange)
            txyfile = os.path.join(proc_root, 'nav', dbinfo.cachedict.txy_file)
            run_timslip(txyfile,
                        dbinfo.cachedict.yearbase,
                        calfile,
                        speed_cutoff = float(options.speed_cutoff),
                        morepts = options.morepts)
            try:
                statstr = get_WT_str(calfile, dbinfo.cachedict.yearbase)
            except:
                statstr = ''
            if statstr:
                cal = parse_wtstr(statstr)
                rlmask = np.ma.getmaskarray(dep[rlstart:rlstart+num_refbins-1])
                if np.ma.sum(rlmask) == 0: #nothing masked
                    mid_depth = (dep[rlstart] + dep[rlstart+num_refbins-1])/ 2
                    if cal.num.edited > 10:
                        allcal.append(
                            [rlstart, rlstart+num_refbins-1,
                             mid_depth,
                             cal.num.edited,
                             cal.amp.mean, cal.amp.median, cal.amp.std,
                             cal.phase.mean, cal.phase.median, cal.phase.std
                            ])
        write_cals(allcal, caldatafile=caldatafile)


    data = read_cals(caldatafile=caldatafile) # return a Bunch
    fig=plot_cals(data, title=title)

    savepngs(options.outfilebase, dpi=72, fig=fig)

    if showfig:
        plt.show()

    if restore_ion:
        plt.ion()
