'''
Functions for scripts/plot_posmv.py.
'''

import os
import logging
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import numpy as np

import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.plot.mpltools import add_UTCtimes

# Standard logging
_log = logging.getLogger(__name__)


def get_filelist(arglist):
    '''
    guess and return .pmv.rbin filelist
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
        # "heading" directory, with *.rbin; return *rbin
        if 'pmv.rbin' == c[-8:]:
            globstr = os.path.join(arg, '*pmv.rbin')
            return pathops.make_filelist(globstr)
    if 'posmv' in contents:
        globstr = os.path.join(arg,'posmv','*.pmv.rbin')
        return pathops.make_filelist(globstr)
    if 'rbin' in contents:
        globstr = os.path.join(arg,'rbin','posmv','*pmv.rbin')
        return pathops.make_filelist(globstr)
    print('contents: ', contents)
    _log.error('==> could not find posmv "pmv" rbins here')

def plot_posmv(pmv, head_acc_cutoff=0.02, yearbase=None):
    graybox= dict(boxstyle="round", ec=(.2,.2,.2), fc=(.5,.5,.5),alpha=.2)
    last_zoom = 3*head_acc_cutoff

    fig,ax=plt.subplots(nrows=4, sharex=True, figsize=(7,9))
    aa=ax[0]
    aa.plot(pmv.dday, pmv.acc_heading,'r.')
    aa.plot(pmv.dday, pmv.acc_heading,'r.-')
    aa.set_ylim(0,60)
    aa.xaxis.set_visible(False)
    # zoom on 2 days, under 10 units
    #  top plot
    pp= np.ma.masked_where(pmv.acc_heading > 10, pmv.acc_heading)
    aa.hlines(10, pmv.dday[0], pmv.dday[-1],'k')
    aa.plot(pmv.dday, pp,'k.')
    aa.text(.05,.85,'all', size=10, color='r', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    aa.text(.05,.05,'zoomed below', size=10, color='k', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    # second plot
    aa=ax[1]
    aa.plot(pmv.dday, pmv.acc_heading,'k.-')
    aa.set_ylim(0,10)
    aa.xaxis.set_visible(False)
    aa.text(.05,.85,'zoomed', size=12, color='k', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    aa.text(.05,.05,'zoomed below', size=12, color='m', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    ## zoom on 2deg
    pp= np.ma.masked_where(pp > 1, pp)
    aa.hlines(1, pmv.dday[0], pmv.dday[-1],'m')
    aa.plot(pmv.dday, pp,'m.')

    #third plot
    aa=ax[2]
    aa.plot(pmv.dday, pmv.acc_heading,'m.-')
    aa.plot(pmv.dday, pp,'m')
    aa.set_ylim(0,1)
    pp= np.ma.masked_where(pp > head_acc_cutoff, pp)
    aa.plot(pmv.dday, pp,'c.')
    aa.hlines(last_zoom, pmv.dday[0], pmv.dday[-1],'c')
    aa.text(.05,.85,'zoomed', size=14, color='m', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    aa.text(.05,.05,'zoom below', size=10, color='c', weight='bold',
             bbox=graybox, transform=aa.transAxes)


    ## zoom on .2deg
    pp= np.ma.masked_where(pp > last_zoom, pp)
    aa.plot(pmv.dday, pp,'c.')

    #bottomplot
    aa=ax[3]
    aa.plot(pmv.dday, pmv.acc_heading,'c.-')
    aa.plot(pmv.dday, pp,'c')
    aa.set_ylim(0,last_zoom)
    aa.text(.05,.85,'zoomed', size=14, color='c', weight='bold',
             bbox=graybox, transform=aa.transAxes)

    pp= np.ma.masked_where(pp > head_acc_cutoff, pp)
    aa.plot(pmv.dday, pp,'b.')
    aa.hlines(head_acc_cutoff, pmv.dday[0], pmv.dday[-1],'b')
    aa.text(.05,.05,'accepted if\nless than %4.3f' % (head_acc_cutoff),
                   size=10, color='b', weight='bold',
             bbox=graybox, transform=aa.transAxes)


    percent_good = 100.*sum(np.ma.getmaskarray(pp)==False)/len(pp)
    aa.text(.95,.05,'%d percent accepted' % (percent_good),
            size=10, color='b', weight='bold', ha='right',
            bbox=graybox, transform=aa.transAxes)

    aa.set_xlim(pmv.dday[0], pmv.dday[-1])

    plt.draw()
    ax[0].set_title('$PASHR "heading accuracy"')
    ax[-1].set_xlabel('decimal day')
    ax[-1].xaxis.set_major_formatter(ScalarFormatter(useOffset = False))

    if yearbase is not None:
        aa = ax[-1].twinx()
        aa.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        aa.set_xlim(pmv.dday[0], pmv.dday[-1])
        aa.set_yticks([])
        if yearbase is not None:
            add_UTCtimes(aa, yearbase, position='bottom')
            ax[-1].set_xlabel('')
            fig.subplots_adjust(bottom=0.15)

    return fig
