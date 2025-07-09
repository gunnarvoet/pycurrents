#!/usr/bin/env python
'''
make lon/lat plots from codas gps file (or any ascii file with
columns dday, lon, lat
optionally save to sequentially-numbered png files

plotnav.py [--savefigs] file1.gps [file2.gps [file3.gps...]]

If "--savefigs" is invoked, the plots are saved, not shown.
Otherwise plots are shown (not saved).

'''
# to do:
#  - add option for map projection (or allow no map projection)


import os
import sys
import glob

import matplotlib

if '--savefigs' in sys.argv:
    sys.argv.pop(sys.argv.index('--savefigs'))

    savefigs = True
    matplotlib.use('Agg')
    from pycurrents.plot.mpltools import savepngs
else:
    savefigs = False


import matplotlib.pyplot as plt
import numpy as np

from pycurrents.adcp.qplot import plot_nav
from pycurrents.system.misc import guess_comment

if len(sys.argv) == 1:
    print(__doc__)
    sys.exit()

if '--help' in sys.argv:
    print(__doc__)
    sys.exit()


filelist=sys.argv[1:]

numgood = 0


if savefigs is True:
    navfilelist = glob.glob('navplot*.png')
    navnums = []
    for navfile in navfilelist:
        num = int(os.path.splitext(navfile)[0][8:])
        navnums.append(num)
    if len(navnums) == 0:
        plotnum = 0
    else:
        plotnum=np.max(np.array(navnums))+1
    print('found %s existing files, maxnum=%d. start saving with %d\n' % (
        len(navnums), plotnum-1, plotnum))



for fname in filelist:   #oklist:
    print('trying ' + fname)
    try:
        cc = guess_comment(fname)
        txy=np.loadtxt(fname, comments=cc)
        if txy is None:
            print('could not load %s' % (fname))
        else:
            dday = txy[:,0]
            lon = txy[:,1]
            lat = txy[:,2]
            plot_nav([dday, lon, lat])
            fig=plt.gcf()
            fig.text(.5, .96, fname, ha='center')
            numgood += 1
            if savefigs is True:
                outbase = 'navplot_%03d' % (plotnum)
                plotnum+=1
                savepngs(outbase, 90, fig=fig)
                print('saving: %s.png is navplot from %s' % (outbase, fname))
                plt.close(fig)
    except:
        raise #IOError('cannot make navplot for %s' % (fname,))

if numgood > 0:
    if savefigs is False:
        plt.show()
