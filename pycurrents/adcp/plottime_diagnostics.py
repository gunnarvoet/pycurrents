
import os
import glob
import logging

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

from pycurrents.adcp.uhdas_cfg_api import SensorCfg
from pycurrents.data import navcalc
from pycurrents.plot.mpltools import add_UTCtimes
from pycurrents.plot.mpltools import savepngs
from pycurrents.system.misc import Bunch


_log = logging.getLogger(__name__)


def find_sensor_cfgs(uhdas_dir):
    # FIXME - should use uhdas_cfg_api for this
    globstrings = ('raw/config/*_sensor.toml', 'proc/*/config/*_sensor.toml',
                   'raw/config/*_sensor.py', 'proc/*/config/*_sensor.py')
    filelist = []
    for globstr in globstrings:
        filelist.extend(glob.glob(os.path.join(uhdas_dir, globstr)))
    return filelist

def sensor_cfg_dday(sensor_list, msglist=None):
    ## NOTE: 'instrument' and "instrument:message" are termonology from the processing side
    ## inside sensor_cfgs, that kind of "instrument" is called "subdir"
    ## NOTE: sensor_cfg.* also has an "instrument" which is a proper name (a model)
    # return all the messages that contain 'dday'
    instruments=[]  ## these are subdirs
    if not msglist:
        msglist = ['gps', 'gga', 'ggn', 'gns', 'gps_sea', 'paq', 'rmc', 'ixgps']
    for d in sensor_list:
        if 'messages' in d.keys() and 'subdir'  in d.keys():
            for gps_msg in msglist:
                if  gps_msg in [msg.lower() for msg in d['messages']]:
                    tp = (d['subdir'], gps_msg)
                    if tp not in instruments:
                        instruments.append(tp)
    return tuple(instruments)


def sensor_cfg_not_dday(sensor_list, msglist=None):
    # return all the messages that DO NOT contain 'dday'
    instruments=[]  ## these are subdirs
    if not msglist:
        msglist = ['gps', 'gga', 'ggn', 'gns', 'gps_sea', 'paq', 'rmc', 'ixgps']
    for d in sensor_list:
        if 'messages' in d.keys() and 'subdir' in d.keys():
            for msg in d['messages']:
                if msg not in msglist:
                    tp=(d['subdir'], msg)
                    if tp not in instruments:
                        instruments.append(tp)
    return tuple(instruments)


def metanames_from_sensors(sensor_file):
    '''
    return a bunch with dirnames as keys, and metaname as value ("instrument" from sensor_cfg)
    '''
    ## NOTE: 'instrument' and "instrument:message" are termonology from the processing side
    ## inside sensor_cfgs, that kind of "instrument" is called "subdir"
    ## NOTE: sensor_cfg.py also has an "instrument" which is a proper name (a model)
    conf = SensorCfg(sensor_file).config
    metanames = {key: value["instrument"] for key, value in conf.sensor_d.items()}
    return Bunch(metanames)


def expand_yaxis(ax, frac=0.1, mindy=0.1):
    '''
    for autoscaling; don't zoom in too much
    to disable: frac=0, mindy=0
    '''
    ylims = ax.get_ylim()
    dy = frac*(ylims[1]-ylims[0])
    expand = max(dy/2, mindy)
    ax.set_ylim(ylims[0]-expand, ylims[1]+expand)


def save_fig(f, inst, msg=None, save_dir='./', prefix='ggatime', zoomname='', thumbnail=True, quant=True):
    if msg:
        outfile = os.path.join(save_dir, '%s_%s_%s_%s' % (prefix, inst, msg, zoomname))
    else:
        outfile = os.path.join(save_dir, '%s_%s_%s' % (prefix, inst, zoomname))
    if thumbnail:
        savepngs((outfile, outfile+'T'), (90, 40), f, quant=quant)
        _log.debug('saving figure to %s.png and %sT.png', outfile, outfile)
    else:
        savepngs((outfile), (90), f, quant=quant)
        _log.debug('saving figure to %s.png', outfile)

def save_hist(outlist, save_dir=None, prefix='ggatime', inst=''):
    '''
    save outlist as string to save_dir/prefix_inst_hist.txt
    '''

    outfile = os.path.join(save_dir, '%s_%s_hist.txt' % (prefix,inst))
    with open(outfile, 'w') as file:
        file.write('\n'.join(outlist))
    _log.info('wrote histogram to %s' % (outfile))

### gga section -------

def plot_gga_times(data, inst, yearbase=None):  # titlestr = 'GPS info'
    uship, vship = navcalc.uv_from_txy(data.dday, data.lon, data.lat, pad=True)
    spd = np.hypot(uship, vship)

    fig, ax = plt.subplots(figsize=(7,9), nrows=4, sharex=True)
    fig.subplots_adjust(left=0.115, bottom=0.06, right=0.97,
                        top=0.95, hspace=0.08)

    ax[0].plot(data.u_dday, 86400*(data.dday-data.u_dday),'.-', ms=4)
    ax[1].plot(data.u_dday[1:], 86400*np.diff(data.u_dday), 'r.-', ms=4)
    ax[2].plot(data.u_dday[1:], 86400*np.diff(data.dday), 'k.-', ms=4)
    ax[3].plot(data.dday, spd, 'g-')
    ax[3].plot(data.dday, uship, 'r.-', ms=4)
    ax[3].plot(data.dday, vship, 'k.-', ms=2)
    if hasattr(data, 'quality'):
        qc6 = np.ma.masked_array(data.quality==6)
        if sum(qc6) > 0:
            ax[1].vlines(data.dday[qc6],-1.5, -0.5, 'm')
            ax[1].text(.95,.55,'%d "free inertial" out of %d' % (sum(qc6), len(data.dday)),
                       transform = ax[1].transAxes, ha='right', color='m')

    ax[0].set_ylabel('seconds')
    ax[1].set_ylabel('seconds')
    ax[2].set_ylabel('seconds')
    ax[3].set_ylabel('meters/sec')

    # no scientific notation
    ax[0].xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax[0].yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax[1].yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax[2].yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax[3].yaxis.set_major_formatter(ScalarFormatter(useOffset = False))

    ax[0].text(.9,.9,' timestamp differences: GGA - UHDAS system',
           ha='right', transform = ax[0].transAxes, weight='bold')


    ax[1].text(.9,.9,'UHDAS system time: first difference', ha='right',
               transform = ax[1].transAxes, color='r', weight='bold')

    ax[2].text(.9,.9,'GGA: first difference', ha='right',
               transform = ax[2].transAxes, color='k', weight='bold')

    ax[3].text(.9,.9,'eastward', ha='right', transform = ax[3].transAxes,
               weight='bold', color='r')
    ax[3].text(.9,.1,'northward', ha='right', transform = ax[3].transAxes,
               weight='bold', color='k')
    ax[3].text(.1,.9,'speed',  ha='left', transform = ax[3].transAxes,
               weight='bold', color='g')
    if yearbase is None:
        xlab = "decimal days"
    else:
        xlab = "0-based decimal day, and HH:MM UTC, %d" % (int(yearbase))
    ax[3].set_xlabel(xlab)

    return fig, ax

def zoom_gga_fig(f,ax, zoomname='auto'):
    '''
    modifies figure in place; save later
    '''
    if zoomname not in ('auto','zoom','fixed'):
        _log.info('not zooming -- no such zoom name as %s' % (zoomname))
        return

    if zoomname == 'fixed':
        ax[0].set_ylim(-20,20)
        ax[1].set_ylim(-5,20)
        ax[2].set_ylim(-5,20)
        ax[3].set_ylim(-8,8)

    if zoomname == 'zoom':
        ax[0].set_ylim(-3,3)
        ax[1].set_ylim(-1,3)
        ax[2].set_ylim(-1,3)
        ax[3].set_ylim(-7,7)

    if zoomname == 'auto':
        expand_yaxis(ax[0])
        expand_yaxis(ax[1])
        expand_yaxis(ax[2])


def add_UTC_fig(f,ax, yearbase=None):
    '''
    modifies figure in place; save later
    '''
    if yearbase is not None:
        '''
        FIXME this is broken
        '''
        aa = ax[3].twinx()
        aa.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        aa.set_yticks([])
        add_UTCtimes(aa, int(yearbase), position='bottom')
        ax[3].set_xlabel('')
        f.subplots_adjust(bottom=0.25)



def make_gga_hist(data, inst, titlestr=''):
    '''
    provide rbin gps data, instrument name
    '''
    bins = np.array([-100, -10, -2, -1, 0, 1,2,3,4,5, 10, 15, 20, 30, 60, 120, 300]) + 0.3
    flist = []
    for ii in np.arange(len(bins)):
        flist.append('%5d ')

    d_hist, d_bins = np.histogram(86400*np.diff(data.dday), bins=bins)  #hh,bb
    u_hist, u_bins = np.histogram(86400*np.diff(data.u_dday), bins=bins)  #hh,bb
    m_hist, m_bins = np.histogram(86400*np.diff(data.m_dday), bins=bins)  #hh,bb

    outlist = []
    outlist.append('## %s instrument=%s' % (titlestr, inst))
    outlist.append('bins:      ' + ''.join(["%6.1f, " % d for d in bins]))
    # dday
    line = '%s %10.7f to %10.7f dday count:   ' % (inst, data.dday[0], data.dday[-1])
    outlist.append(line + ''.join(["%6d, " % d for d in d_hist]))
    # u_dday
    line = '%s %10.7f to %10.7f u_dday count:   ' % (inst, data.u_dday[0], data.u_dday[-1])
    outlist.append(line + ''.join(["%6d, " % d for d in u_hist]))
    # dday
    line = '%s %10.7f to %10.7f m_dday count:   ' % (inst, data.m_dday[0], data.m_dday[-1])
    outlist.append(line + ''.join(["%6d, " % d for d in m_hist]))
    outlist.append('\n\n')

    return outlist


##### udday section  -----


def plot_udday_times(data, inst, titlestr, yearbase=None):  # titlestr = 'UHDAS logging info'
    fig, ax = plt.subplots(figsize=(9,4))

    ax.plot(data.u_dday[1:], 86400*np.diff(data.u_dday), 'r.-', ms=4)
    ax.set_ylabel('seconds')

    # no scientific notation
    ax.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))

    ax.text(.9,.9,' consecutive timestamp differences: UHDAS system',
           ha='right', transform = ax.transAxes, weight='bold')

    if yearbase is None:
        xlab = "decimal days"
    else:
        xlab = "0-based decimal day, and HH:MM UTC, %d" % (int(yearbase))
    ax.set_xlabel(xlab)
    fig.suptitle(titlestr)

    return fig, ax



def zoom_udday_fig(f,ax, inst, yearbase=None, zoomname='auto'):
    '''
    modifies figure in place; save later
    '''
    if zoomname not in ('auto','zoom','fixed'):
        _log.info('not zooming -- no such zoom name as %s' % (zoomname))
        return

    if zoomname == 'fixed':
        ax.set_ylim(-5,20)

    if zoomname == 'zoom':
        ax.set_ylim(-1,3)

    if zoomname == 'auto':
        expand_yaxis(ax)

    if yearbase is not None:
        '''
        FIXME this is broken
        '''
        aa = ax.twinx()
        aa.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        aa.set_yticks([])
        add_UTCtimes(aa, int(yearbase), position='bottom')
        ax.set_xlabel('')
        f.subplots_adjust(bottom=0.3)



def make_udday_hist(data, inst, titlestr=''):
    '''
    provide rbin gps data, instrument name
    '''
    bins = np.array([-100, -10, -2, -1, 0, 1,2,3,4,5, 10, 15, 20, 30, 60, 120, 300]) + 0.3
    flist = []
    for ii in np.arange(len(bins)):
        flist.append('%5d ')

    u_hist, u_bins = np.histogram(86400*np.diff(data.u_dday), bins=bins)  #hh,bb

    outlist = []
    outlist.append('## %s instrument=%s' % (titlestr, inst))
    outlist.append('bins:      ' + ''.join(["%6.1f, " % d for d in bins]))
    # u_dday
    line = '%s %10.7f to %10.7f u_dday count:   ' % (inst, data.u_dday[0], data.u_dday[-1])
    outlist.append(line + ''.join(["%6d, " % d for d in u_hist]))
    outlist.append('\n\n')

    return outlist
