'''
Functions for scripts/plot_hbin_gaps.py.
'''

import os
import sys
import logging
import matplotlib.pyplot as plt

import numpy as np

import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.plot.mpltools import add_UTCtimes
from pycurrents import  codas
from pycurrents.num import Blackman_filter
from matplotlib.ticker import ScalarFormatter, MaxNLocator
from pycurrents.data import navcalc


# Standard logging
_log = logging.getLogger(__name__)


def get_filelist(arglist):
    '''
    requires arglist that is
      - UHDAS cruise directory
      - directory to hbins
    returns filelist
    '''
    # list of files
    # input is assumed to be a list

    if len(arglist) > 1:
        return arglist
    #
    # might be a single file
    arg = arglist[0]
    if os.path.isfile(arg) or os.path.islink(arg):
        return(arglist)
    #
    # now assume it is a directory, either UHDAS dir + ash_inst, or the full dir
    contents = []
    count = 0

    # buid rbin directory
    argdir = arglist[0]
    rglob = os.path.join(argdir, 'gbin/heading/*.hbin')
    filelist =  pathops.make_filelist(rglob, allow_empty=True)
    if len(filelist) > count:
        contents = filelist
        count = len(filelist)

    if len(contents) > 0:
        return(contents)
    else:
        _log.warning('==> could not find any hbins here: %s' % (argdir) )
        sys.exit(1)


def plot_gaps(data, inst_msg, halfwinmins=5, yearbase=None, minutes_ago=False):
    '''
    plot reacquisition from data
    timeaxis = 'dday' (default); if "minutes ago" plot as minutes before the end
    '''
    if minutes_ago:
        # minutes ago
        x = (data.dday[-1] - data.dday)*24*60
        # alternate_text = 'minutes ago'
    else:
        x = data.dday
        # alternate_text = '0-based decimal day'

    if inst_msg not in data.columns:
        _log.warning('%s is not a valid instrument_message string.  Choose from %s' % (
            inst_msg, ', '.join(data.columns[1:])))
        sys.exit(1)

    baddata_flag = np.isnan(data.records[inst_msg])

    f,ax = plt.subplots(figsize=(8,10))

    halfwinsecs = int(halfwinmins)*60
    dt = np.median(np.diff(data.dday))*86400 # seconds
    halfwincount = int(halfwinsecs/dt)
    halfwinmins = int(halfwinmins)

    yfilt = Blackman_filter(baddata_flag, halfwincount)[0]
    bad=np.ma.masked_array(baddata_flag, mask=baddata_flag==1)
#    ax.plot(x, baddata_flag,'-', color=[.8,.8,.8])
    ax.fill_between(x, baddata_flag, 0, color=[.9,.9,.9])
    ax.plot(x, yfilt, 'orange', lw=2)
    ax.fill_between(x, yfilt, 0, facecolor='orange', alpha=0.3)    
    ax.plot(x[bad.mask], baddata_flag[bad.mask],'k.', ms=4)
    ax.plot(x[~bad.mask], baddata_flag[~bad.mask],'g.', ms=4)

    ax.set_ylim(-0.1, 1.15)
    ax.set_ylabel('missing')
    ax.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax.set_xlim(x[0], x[-1])

    ax.grid(True)

    percentgood = 100.0*sum(baddata_flag==0)/len(bad)
    ax.text(.03,.03, 'no problem = 0 = GOOD (%d%%)' % (np.floor(percentgood)),
            transform = ax.transAxes, color='g', weight='bold')


    percentbad = 100.0*sum(baddata_flag==1)/len(bad)
    ax.text(.03, .95, 'failure = 1 = BAD (%d%%)' % (np.ceil(percentbad)),
            color='k', weight='bold', transform = ax.transAxes)

    if halfwinmins > 3:
        hstr = '%dmin' % (halfwinmins)
    elif halfwinmins > 1:
        hstr = '%2.1fmin' % (halfwinmins)
    else:
        hstr = '%dsec' % (halfwinsecs)


    fracstr =  'FRACTION missing -- %s Blackman filter' % (hstr)
    ax.text(.03,.9, fracstr, transform = ax.transAxes, color='orange',
            weight='bold')

    if yearbase is not None:
        aa = ax.twinx()
        aa.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        aa.set_yticks([])
        if minutes_ago:
            dstring = codas.to_datestring(int(yearbase), data.dday[-1])
            ax.set_xlabel('minutes before %s' % (dstring))
        else:
            add_UTCtimes(aa, int(yearbase), position='bottom')
            ax.set_xlabel('')
            f.subplots_adjust(bottom=0.25)
    else:
        if minutes_ago:
            ax.set_xlabel('minutes before %5.2f UTC' % (data.dday[-1]))
        else:
            ax.set_xlabel('decimal day')

    return f



def plot_hbins(data, instnum=1):
    colors=['k', 'g','r','b','k','m','c'] #zeroth one is a dummy
    namedict=dict()
    inums = np.arange(len(data.columns)-1) + 1
    fig,ax=plt.subplots(figsize=(8,10), nrows=len(inums), sharex=True)

    for ii in inums:
        namedict[ii]=data.columns[ii]
    #
    for inum in inums:
        ax[0].plot(data.dday, getattr(data,namedict[inum]),
                   '.', color=colors[inum])

    frac=1/(len(inums)+2.0)

    ax[0].text(.05,.85,'heading',size=10,  weight='bold',
                transform=ax[0].transAxes)
    ax[0].grid(True)

    for inum in inums:
        ax[0].text(.95, 1-(inum*frac),
                    '%s ' % (namedict[inum]),
                    color=colors[inum],
                    transform=ax[0].transAxes,
                    size=10, weight='bold',
                    ha='right')

    axnum=1
    hbase = navcalc.unwrap(getattr(data, namedict[instnum]))
    for inum in inums:
        if inum != instnum:
            h2 = navcalc.unwrap(getattr(data, namedict[inum]))
            dh = np.remainder(h2 - hbase + 90, 360)-90
            ax[axnum].plot(data.dday, dh, '.', color=colors[inum])
            ax[axnum].text(.5,.1,'%s' % (namedict[inum]),
                        color=colors[inum],
                        transform=ax[axnum].transAxes,
                            size=12, weight='bold',
                        ha='right')
            ax[axnum].text(.5,.1,'-%s' % (namedict[instnum]),
                        color=colors[instnum],
                        transform=ax[axnum].transAxes,
                            size=12, weight='bold',
                        ha='left')
            ax[axnum].text(.05,.85,'heading difference',
                            weight='bold',size=10,
                            transform=ax[axnum].transAxes)
            ax[axnum].grid(True)
            axnum+=1

    plt.draw()
    ax[-1].xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax[-1].yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax[-1].xaxis.set_major_locator(MaxNLocator(5))

    ax[-1].set_xlabel('decimal day')
    return fig
