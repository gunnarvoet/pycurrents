#!/usr/bin/env python
'''
- make plots of reflayer (u,v) and fdifference as a function of time

plot_reflayer.py [options]  dbpath1 dbpath2

     name        what                                  default
    --zrange     depth range to average for reflayer   30:100
    --ddrange    dday range to extract                 dday1:dday2
    --title      plot title                            current directory
    --outbase    save figs:basename for png file name     (do not save figs)
    --nwin       window for Runstats                   33
    --plotfp     plot forward and port vel             False: plot u,v
    --rscale     ratio plotted 1.0 +/- N*0.01          4: (i.e. .06-1.04)


Comment: The data from dbpath2 are gridded onto dbpath1, so normally dbpath1
would be the higher frequency.  In case there is a reason to apply an angle
or scale factor to dbpath2 (to better align it with the properties of dbpath1)
approximate values are printed for
    rotate_angle (heading alignment: make dbpath2 oriented like dbpath1)
    rotate_amplitude (scalefactor to make dbpath2 act like dbpath1)

NOTE: This program assumes the binsize and number of bins does not change
      for the period selected


'''

import os
import sys
from optparse import OptionParser

import matplotlib

if '--savefigs' in sys.argv:
    sys.argv.remove('--savefigs')
    savefigs = True
    matplotlib.use('Agg')
else:
    savefigs = False

import matplotlib.pyplot as plt

from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.uhdasfile import guess_dbname
from pycurrents.adcp.reflayer import Refl  # class

from pycurrents.adcp.reflayer import get_refdiff, get_refangle, get_refrat
from pycurrents.adcp.reflayer import plot_uv2, plot_fpstats, plot_angle

if len(sys.argv) == 1:
    print(__doc__)
    sys.exit()


#============================================

if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    parser = OptionParser(__doc__)


    parser.add_option("--ddrange", dest="ddrange",
                      default = None,
                      help="colon-delimited decimal day range to extract")

    parser.add_option("--zrange", dest="zrange",
                      default = None,
                      help="colon-delimited depth range to extract")

    parser.add_option("--title", dest="title",
                      default = None,
                      help="figure title")

    parser.add_option("--outbase", dest="outbase",
                      default = None,
                      help="save figure (basename)")

    parser.add_option("--nwin", dest="nwin",
                      default = 33,
                      help="window length for smoothing")

    parser.add_option("--onstation", dest="onstation",
                      default = 2,
                      help="only include underway, i.e. speeds exceeding this (m/s)")

    parser.add_option("--rscale", dest="rscale",
                      default = 4,
                      help="fwd,port stats plotting window (larger gives larger lims),default=4")
    ## options without arguments

    parser.add_option("--plotfp", dest="plotfp", action="store_true",
                      default=False,
                      help="plot fwd, port instead of u,v")

    parser.add_option("--plot_angle", dest="plot_angle", action="store_true",
                      default=False,
                   help="plot angle between transducers as a time series; requires plotfp")

    parser.add_option("--verbose", dest="verbose", action="store_true",
                      default=False,
                      help="output some useful information")

    (options, args) = parser.parse_args()

    if options.ddrange is None:
        ddrange = None
    else:
        parts=options.ddrange.split(':')
        ddrange=[float(parts[0]), float(parts[1])]

    if options.zrange is None:
        zrange = [50,130]
    else:
        print('zrange is', options.zrange)
        parts=options.zrange.split(':')
        print('parts is', parts)
        zrange=[int(parts[0]), int(parts[1])]

    if options.title is None:
        options.title=os.path.split(os.getcwd())[-1]

    if options.plotfp:
        ovars = ['fvel','pvel']
    else:
        ovars = ['u','v']


    onstation = float(options.onstation)

    dbname1=guess_dbname(args[0])
    dbname2=guess_dbname(args[1])

    dbroot1 = os.path.realpath(dbname1).split(os.path.sep)[-3]
    dbroot2 = os.path.realpath(dbname2).split(os.path.sep)[-3]

    R1 = Refl(dbname1, ['u','v','fvel','pvel','fmeas', 'umeas', 'vmeas'],
              ddrange=ddrange, zrange=zrange)
    R2 = Refl(dbname2, ['u','v','fvel','pvel','fmeas', 'umeas', 'vmeas'],
              ddrange=ddrange, zrange=zrange)

    rdiff = get_refdiff(R1, R2, ovars, onstation=onstation)
    fdiff=plot_uv2(R1, R2, rdiff, ovars, names=(dbroot1, dbroot2),
                   title=options.title, nwin=int(options.nwin)) #fig
    frat=None
    if options.plotfp:
        refrat = get_refrat(R1, R2, onstation=onstation)
        rdiff_angle  = get_refangle(R1, R2, onstation=onstation)
        ffpstats = plot_fpstats(R1, R2, rdiff, refrat, rdiff_angle,
                                names=(dbroot1, dbroot2),
                                title=options.title,
                                nwin=int(options.nwin),
                                rscale=float(options.rscale),
                                zrange=zrange)


        if options.plot_angle:
            ffangle = plot_angle(rdiff, rdiff_angle,
                                names=(dbroot1, dbroot2),
                                title=options.title,
                                nwin=int(options.nwin),
                                )

    if options.outbase is None:
        plt.show()
    else:
        if options.plotfp:
            varstr='fp'
        else:
            varstr='uv'
        diffname = '%s_%sdiff' % (options.outbase, varstr)
        savepngs(diffname, 90, fig=fdiff)
        plt.close(fdiff)

        if options.plotfp:
            fpstatsname =  '%s_%sratio' % (options.outbase, varstr)
            savepngs(fpstatsname, 90, fig=ffpstats)
            plt.close(ffpstats)

            if options.plot_angle:
                savepngs('%s_angle_diff' % (options.outbase), 90, fig=ffangle)
                plt.close(ffangle)
