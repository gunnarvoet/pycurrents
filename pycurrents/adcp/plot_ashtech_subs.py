'''
Functions for scripts/plot_ashtech_reacq.py.
'''

import os
import logging
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import matplotlib.patheffects as path_effects

import numpy as np

import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.plot.mpltools import add_UTCtimes
from pycurrents import  codas
from pycurrents.num import Blackman_filter


# Standard logging
_log = logging.getLogger(__name__)


def get_filelist(arglist, ash_inst=None):
    '''
    requires arglist that is
      - UHDAS cruise directory (specify ash_inst)
      - directory to rbins (including ash_inst)
      - filelist or globstr
    returns filelist
    '''
    # list of files
    # input is assumed otbe a list

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
    if ash_inst: # '/home/data/HLY18TA/rbin/%s' % (ash_inst)
        argdir = os.path.join(arglist[0], 'rbin', ash_inst )
    else:       # '/home/data/HLY18TA/rbin/abxtwo'
        argdir = arglist[0]
    for msg in ('adu','at2','paq'):
        rglob = os.path.join(argdir, '*.%s.rbin' % msg)
        filelist =  pathops.make_filelist(rglob, allow_empty=True)
        if len(filelist) > count:
            contents = filelist
            count = len(filelist)
            print('found %d %s files in %s' % (count, msg, argdir))

    if len(contents) > 0:
        return(contents)
    else:
        _log.error('==> could not find any ashtech rbins here: %s' % (argdir) )
        if not ash_inst:
            _log.error('!! specify the instrumentname or give the full path')


def plot_reacquisition(data, halfwinmins=5, yearbase=None, minutes_ago=False):
    '''
    plot reacquisition from data
    timeaxis = 'u_dday' (default); if "minutes ago" plot as minutes before the end
    '''
    if minutes_ago:
        # minutes ago
        x = (data.u_dday[-1] - data.u_dday)*24*60
        # alternate_text = 'minutes ago'
    else:
        x = data.u_dday
        # alternate_text = '0-based decimal day'

    f,ax = plt.subplots(figsize=(7,8))

    halfwinsecs = halfwinmins * 60
    dt = np.median(np.diff(data.u_dday)) * 86400 # seconds
    halfwincount = int(halfwinsecs / dt)

    yfilt = Blackman_filter(data.reacq, halfwincount)[0]
    bad=np.ma.masked_array(data.reacq, mask=data.reacq==1)
#    ax.plot(x, data.reacq,'-', color=[.8,.8,.8])
    ax.fill_between(x, data.reacq, 0, color=[.9,.9,.9])
    ax.plot(x, yfilt, 'r', lw=2)
    ax.fill_between(x, yfilt, 0, facecolor=[.9,0,0], alpha=0.3)
    ax.plot(x[bad.mask], data.reacq[bad.mask],'k.', ms=4)
    ax.plot(x[~bad.mask], data.reacq[~bad.mask],'g.', ms=4)

    ax.set_ylim(-0.1, 1.15)
    ax.set_ylabel('reacquisition')
    ax.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax.set_xlim(x[0], x[-1])

    ax.plot([x[0],x[-1]],[.5,.5], 'k', lw=3)
    ax.plot([x[0],x[-1]],[.5,.5], 'r', lw=1)

    ax.grid(True)

    percentgood = 100.0*sum(data.reacq==0)/len(bad)
    ax.text(.03,.03, 'reacquisition = 0 = GOOD (%d%%)' % (np.floor(percentgood)),
            transform = ax.transAxes, color='g', weight='bold')


    percentbad = 100.0*sum(data.reacq==1)/len(bad)
    ax.text(.03, .95, 'reacquisition = 1 = BAD (%d%%)' % (np.ceil(percentbad)),
            color='k', weight='bold', transform = ax.transAxes)

    if halfwinmins > 3:
        hstr = f"{halfwinmins:.0f} min"
    elif halfwinmins > 1:
        hstr = f"{halfwinmins:.1f} min"
    else:
        hstr = f"{halfwinsecs:.0f} sec"


    fracstr =  'FRACTION with REACQUISITION -- %s Blackman filter' % (hstr)
    ax.text(.03,.9, fracstr, transform = ax.transAxes, color='r', weight='bold')

    onepercent = (data.u_dday[-1]-data.u_dday[0])/100
    tleft = 3*onepercent + data.u_dday[0]
    txt_opts = dict(color='r', weight='bold', size=14, va='center')
    text=ax.text(tleft, .53, 'threshold to', **txt_opts)
    text.set_path_effects([path_effects.Stroke(linewidth=3, foreground='white'),
                       path_effects.Normal()])
    text=ax.text(tleft, .47, 'manually reset', **txt_opts)
    text.set_path_effects([path_effects.Stroke(linewidth=3, foreground='white'),
                       path_effects.Normal()])

    if yearbase is not None:
        aa = ax.twinx()
        aa.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        aa.set_yticks([])
        if minutes_ago:
            dstring = codas.to_datestring(int(yearbase), data.u_dday[-1])
            ax.set_xlabel('minutes before %s' % (dstring))
        else:
            add_UTCtimes(aa, int(yearbase), position='bottom')
            ax.set_xlabel('')
            f.subplots_adjust(bottom=0.25)
    else:
        if minutes_ago:
            ax.set_xlabel('minutes before %5.2f UTC' % (data.u_dday[-1]))
        else:
            ax.set_xlabel('decimal day')

    return f
