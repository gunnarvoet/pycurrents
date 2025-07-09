## routines imported by plot_nav plot_rnav

import numpy as np
import matplotlib.pyplot as plt
import os
import glob

from pycurrents.adcp.qplot import qnav1, qtxy
from pycurrents.system.misc import guess_comment


def plot_topo(data, titlestr):
    fig_topo = plt.figure(figsize=(8,7), dpi=90)
    qnav1(data, fig=fig_topo)
    fig_topo.text(.5,.95,'%s' % titlestr, ha='center')
    return fig_topo

def plot_txy(data, titlestr, yearbase=None):
    if yearbase:
        yearbase=int(yearbase)
    fig_txy = plt.figure(figsize=(9,7), dpi=90)
    qtxy(data, fig=fig_txy, yearbase=yearbase)
    fig_txy.text(.5,.95,'%s' % titlestr, ha='center')
    return fig_txy


def guess_txy(procdir):
    #crude guess at gps file name, allowing start at processing root
    navfile = None
    if os.path.isdir(os.path.abspath(procdir)):
        flist = []
        for suffix in ['agt','ags','gps', 'gpst']:
            fglob = os.path.join(procdir, 'nav','*.%s' % (suffix))
            flist += glob.glob(fglob)
        if len(flist) == 0:
            print('no gps file can be guessed')
        elif len(flist) > 1:
            print('%d gps files found' % (len(flist)))
            print('\n'.join(flist))
            print('returning the first one')
            navfile = flist[0]
        else:
            navfile = flist[0]
    if os.path.isfile(os.path.abspath(navfile)):
        comment=guess_comment(navfile)
        try:
            data = np.loadtxt(navfile, comments=comment)
            txy = [data[:,0], data[:,1], data[:,2]]
        except:
            print('could not load file %s' % (navfile))
            txy = None
    else:
        print('no such file %s' % (navfile))
        txy = None

    return txy, navfile
