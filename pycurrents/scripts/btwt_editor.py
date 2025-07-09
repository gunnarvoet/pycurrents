#!/usr/bin/env python3

from pycurrents.adcp.polygon_editor import PolygonInteractor
import argparse
import os
import sys
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np


## this wrapper is useful for bt+wt but the polygon editor could be used
##     for other things


def make_polygon(dday, ph):
    '''
    return a polygon and number of extra points
      polygon:
          - starts with dday
          - goes right, down, left, and stops before dday[0]
    '''

    # define polygon
    nfit = len(dday)
    trim = -2                 # last index to use
    xs = np.zeros((nfit+4))
    ys = np.zeros((nfit+4))

    xs[:nfit]    = dday       # fill in fitdday
    xs[nfit]     = dday[-1]   # add far right
    xs[nfit+1]   = dday[-1]   # another far right for the return trip
    xs[nfit+2]   = dday[0]    # another far left for the return trip
    xs[nfit+3]   = dday[0]    # start far left

    ys[:nfit]    = ph         # fill in fitdday
    ys[nfit]     = ph[-1]     # add far right
    ys[nfit+1]   = min(ph)-1  # another far right for the return trip
    ys[nfit+2]   = min(ph)-1  # another far left for the return trip
    ys[nfit+3]   = ph[0]      # start far left

    return(Polygon(list(zip(xs, ys)), animated=True, fill=False), trim)


if __name__ == '__main__':


    parser = argparse.ArgumentParser(
        description="provide a graphical editor to modify a line (displayed as a polygon, sorry)")


    parser.add_argument('--rawfile',
                         default='allcals.txt',
         help='filename for combined WT and BT data')

    parser.add_argument('--fitfile',
                         default='calfit.txt',
        help='filename for fitted line of WT+BT')

    parser.add_argument('--outfile',
                        default='calfit_edited.txt',
                        help='prefix for edited points (ascii columns)')

    parser.add_argument('--scheme',
                        default='coarse',
                        help='fixed list of choices for subsampling')



    parser.add_argument('--trim',
                        default=None,
    help='last index for writing fitted points (overrides internal calculation')

    options = parser.parse_args()

    if not os.path.exists(options.rawfile):
        print('ERROR: no such file %s' % (options.rawfile))
        sys.exit(1)

    if not os.path.exists(options.fitfile):
        print('ERROR: no such file %s' % (options.fitfile))
        sys.exit(1)

    if os.path.exists(options.outfile):
        print('ERROR: outfile %s exists.' % (options.outfile))
        print('Delete %s and try agian' % (options.outfile))
        sys.exit(1)

    dday, amp, ph, isbt = np.loadtxt(options.rawfile, comments='#', unpack=True)

    fig, ax = plt.subplots()
    ax.plot(dday[isbt==1], ph[isbt==1], 'k.', ms=3)
    ax.plot(dday[isbt==0], ph[isbt==0], 'c.', ms=6)


    fit_dday, fit_ph = np.loadtxt(options.fitfile, comments='#', unpack=True)
    poly, trimcalc = make_polygon(fit_dday, fit_ph)

    if options.trim:
        trim = int(options.trim)
    else:
        trim = trimcalc


    ax.add_patch(poly)

    pstr = '''

    Key-bindings

      't' toggle vertex markers on and off.  When vertex markers are on,
          you can move them, delete them

      'd' delete the vertex under point

      'i' insert a vertex at point.  You must be within epsilon of the
          line connecting two existing vertices

    '''
    print(pstr)
    print('- delete, move, or insert dots to improve the line\n')
    print('- final data will be output to %s\n' % (options.outfile))

    # write out the core data (not the extened parts to make the polygon)
    p = PolygonInteractor(ax, poly, outfile=options.outfile, trim=trim)

    #ax.add_line(p.line)
    ax.set_title('Click and drag a point to move it')
    daywidth=dday[-1]-dday[0]
    ax.set_xlim((dday[0]-daywidth/100, dday[-1]+daywidth/100))
    ax.set_ylim((min(fit_ph)-1, max(fit_ph)+1))
    plt.show()
