#!/usr/bin/env python
'''
Create a profile of amplitude (scale factor) versus depth
- reads the output from plot_amp_refbins.py, plots mean amplitude vs depth
- also plots a smooothed version and allows the user to edit the points
  before saving to a text file (saves saves a figure as well)

usage:

   edit_amp_refbin.py [options] --outfilebase OUTFILE INFILENAME

eg:

   edit_amp_refbin --nwin 5 --outfilebase wh300_amp  wh300.txt
'''



import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon
import sys
import os
from pycurrents.num import Runstats
from pycurrents.plot.poly_editor import PolygonInteractor
from optparse import OptionParser

def usage():
    print(__doc__)
    sys.exit()


if __name__ == '__main__':

    parser = OptionParser(__doc__)
    parser.add_option("--spine", dest="spine",
                      default=0.97,
                      help="minimum value of polygon (default=0.97)")
    parser.add_option("-n", "--nwin", dest="nwin",
                      default=5,
                      help="window for smoothing -- ODD number (default=5)")

    parser.add_option("--outfilebase", dest="outfilebase",
                      default = None,
                      help="specify base for png and text file (REQUIRED)")

    (options, args) = parser.parse_args()

    spine = float(options.spine)
    nwin = int(options.nwin)

    if options.outfilebase:
        outfilebase = options.outfilebase
    else:
        print('outfilebase is required')
        sys.exit()

    for suffix in ('.png', '.ampz'):
        fname =  outfilebase + suffix
        if os.path.exists(fname):
            print('file %s exists; not overwriting.' % (fname))
            print('Remove it and try again')
            sys.exit()

    try:
        data=np.loadtxt(args[0])
    except:
        raise IOError('could not load %s' % (args[0]))


    try:
        z = data[:,2]
        amp = data[:,4]
    except:
        print('failed to get amp and depth.  shape:')
        print(data.shape)
        raise IOError



    # now need to make the line a polygon
    Ramp = Runstats(amp, nwin)

    # make the polygon out of the smoothed one; plot the original for guideance

    amp_smoothed = Ramp.mean
    amp_orig = amp

    amp_use = amp_smoothed
    amp_plot = amp_orig


    dz = np.median(np.diff(z))
    zpoly = [0, 0]            # spine, top of line
    for zz in z:
        zpoly.append(zz)
    zpoly.append(z[-1] + dz)  # last one in the line
    zpoly.append(z[-1] + dz)  # connect back to spine

    ampoly = [spine, amp_use[0]]
    for aa in amp_use:
        ampoly.append(aa)
    ampoly.append(amp_use[-1])
    ampoly.append(spine)

    poly = Polygon(list(zip(ampoly, zpoly)), animated=True,
                   facecolor='none', fill=False)

    fig, ax = plt.subplots(figsize=(6,9))
    ax.plot(amp_plot, z, 'k.-')
    ax.add_patch(poly)
    ax.invert_yaxis()
    ax.grid(True)
    p = PolygonInteractor(ax, poly)

    #ax.add_line(p.line)
    ax.set_title('Click and drag a point to move it')
    ax.set_xlim((spine, max(amp_orig)+0.0005))
    ax.vlines(1, 0, np.max(zpoly), color='k')
    ax.text(.1, .9, 'target values', color='r', transform=ax.transAxes)
    ax.text(.1, .8, 'original', color='k', transform=ax.transAxes)
    ax.set_xlabel('amplitude (scale factor)')
    ax.set_ylabel('depth')

    plt.show()
    fig.savefig(outfilebase + '.png')


    outfile='%s.ampz' % (outfilebase)
    if os.path.exists(outfile):
        os.remove(outfile)
    f=open(outfile, 'a')
    for aa,zz in poly.xy[1:-2]:
        f.write('%7.2f  %7.3f\n' % (zz,aa))
    f.close()

    print('wrote %d (z,amp) pairs to %s' % (len(poly.xy)-2, outfile))
    print('figure saved to %s.png' % (outfilebase))
