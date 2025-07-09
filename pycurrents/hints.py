### favorite imports, just the basics, mostly "pycurrents"
'''
This file contains a useful list of python tools in pycurrents
It is set up for use with ipython, to make life easier:

    from pycurrents.imports import *

If programming, write out the imports properly.

Preamble:

- keep executables in 'scripts'
- libraries, modules, packages, imports: all go elsewhere
- write code to be consistent with these imports:
---- begin code ----

#(1) system imports that do not bother other things
import sys, os, glob, time

#(2) # optional: if used, set up logger before other imports
import logging, logging.handlers
from pycurrents.system import logutils
log = logutils.getLogger(__file__)

#(3) # numpy, matplotlib
import numpy as np
# to have no graphics show up, import matplotlib first, and set backend immediately
# eg: import matplotlib
#     matplotlib.use('Agg')
import matplotlib.pyplot as plt

'''

import os, sys, glob, time, shutil, string

import logging

import numpy as np
import numpy.ma as ma

import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.mlab   as mlab

from matplotlib.ticker import ScalarFormatter, MaxNLocator

## data readers
from pycurrents.file.binfile_n import BinfileSet  # concatenated rbins
from pycurrents.data.nmea.qc_rbin import RbinSet  #qc_rbin
from pycurrents.adcp.raw_multi import Multiread      # singleping ADCP
from pycurrents.codas import get_profiles         # general codasdb reader
from pycurrents import codas # DB, ProcEns (for more detailed work)
from pycurrents.adcp import reader #uhdasfile, vmdas

## digging down into components of CODAS processing
from pycurrents.adcp import pingsuite
from pycurrents.adcp.quick_npy import PingAverage
from pycurrents.adcp.gbin import Gbinner
from pycurrents.adcp.uhdasconfig import UhdasConfig
from pycurrents.adcp.attitude import Attitude, Hcorr

#ADCP+UHDAS
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp import adcp_specs
from pycurrents.adcp import uhdasfile
from pycurrents.adcp.uhdasfile import binfile_ddayalias, UHDAS_Tree
from pycurrents.adcp.uhdasfileparts import FileParts
from pycurrents.adcp  import pingedit
from pycurrents.adcp  import pingavg
from pycurrents.adcp  import gbin
from pycurrents.adcp.qplot import qpc, qcf, qcont, qnav, plot_nav
from pycurrents.adcp.qplot import qmessage, textfig
                                # qmessage is a synonym for textfig
                                # plot_nav is a synonym for qnav

## statistics and gridding
from pycurrents.num import interp1           # interpolation
from pycurrents.num import bl_filt        # blackman filter  OBSOLETE
from pycurrents.num import Blackman_filter        # blackman filter PREFERRED
from pycurrents.num import Runstats               # running statistics
from pycurrents.num import Stats            # mean,std,med (masked)
from pycurrents.num import binstats      # binned stats (slow)
from pycurrents.num import regrid      # zgrid interface
from pycurrents.num import nptools   #rangeslice, Flags
from pycurrents.num import segments   #indices from mask (eg. on-station)

import pycurrents.num.grid as numgrid  # or don't bother with it at all

## calculations
from pycurrents.adcp.transform import heading_rotate, Transform
from pycurrents.data import navcalc # uv_from_txy, unwrap_lon, unwrap ...
from pycurrents.plot.maptools import mapper, Mapbase
import pycurrents.plot.maptools as maptools #(Conic, Mercator, Mapbase)
from pycurrents.adcp.refavg import refavg

## other classes
from pycurrents.data.sound import Attenuator      # sound
from pycurrents.data import topo   # smith sandwell topo, etopo

## file and sampling tools
import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.num.nptools import rangeslice     # subsampling (slice)
from pycurrents.num.nptools import Flags          # handling flags
from pycurrents.system.misc import Bunch          # handling dictionaries
from pycurrents.system.misc import Cachefile      # caching
from pycurrents.adcp.raw_base import make_ilist     #only if necessary

## underlying matplotlib tools
from pycurrents.plot.mpltools import savepngs, get_extcmap, shorten_ax
from pycurrents.plot.mpltools import dday_to_mpl
from pycurrents.codas import to_date, to_day, to_datestring
from pycurrents.adcp.uhdasfile import guess_dbname


## specialized plotting tools
from pycurrents.adcp.dataplotter import ADataPlotter, Vecmap, vecplot
from pycurrents.plot.maptools import LonFormatter, LatFormatter, llticks
from pycurrents.plot.txyselect import TXYSelector, RangeSet
from pycurrents.plot.txyselect import TMapSelector, TVelSelector, RangeSet
from pycurrents.plot.mpltools import add_UTCtimes
#S=TMapSelector(fig, RangeSet(t,x,y))
from pycurrents.adcp.hspan import TYSelector

## other matplotlib nuggets
from matplotlib.ticker import ScalarFormatter, MaxNLocator, MultipleLocator

# Standard logging
_log = logging.getLogger(__name__)

#LF.level
#LF.setlevel  #DEBUG, INFO, WARNING, ERROR, CRITICAL.
#
## eg. LF.setlevel('warning') will log these"
#LF.debug       #built in                   not report
#LF.info        #built in                   not report
#LF.warning     #built in          log
#LF.error       #built in          log
#LF.critical    #built in          log
#LF.exception   #built in          same as 'critical' but dump trace
#
#
#LF.debug('test:  debug message')
#LF.info('test:  info message')
#LF.warning('test:  warning message')
#LF.error('test:  error message')
#LF.critical('test:  critical error message')

## eg.
#LF.info('Starting hcorr.py')
#LF.setlevel('debug')

def nosci(xyaxis):
    '''
    make "no scientific notation"
    axname is ax.xaxis or ax.yaxis

    eg.

      nosci(gca().xaxis);draw()
    '''
    xyaxis.set_major_formatter(ScalarFormatter(useOffset = False))

#-------------------------------------------------------

def gtext(tstr,**kwargs):
    '''
    use ginput for point, add text with 'text'
    '''
    x = plt.ginput(1)
    hh= plt.text(x[0][0],x[0][1],tstr,**kwargs)
    return hh

#-------------------------------------------------------

def mtext(x,y,tstr, **kwargs):
    '''
    text in [0,1,0,1] coordinates)
    '''
    ax = plt.gca()
    ax.text(x,y,tstr, transform = ax.transAxes, **kwargs)

#--------------------------------------------------------


def pruneit(xyaxis, num=7, prune='both'):
    '''
    use 'prune'
    '''
    xyaxis.set_major_locator(MaxNLocator(num, prune=prune))

#-------------------------------------------------------


def mid(aa):
    ''' return midpoints
    '''
    return (aa[0:-1] + aa[1:])/2

#----------------------------

def dday_to_str(yearbase, dday):
    '''
    return string for yearbase and decimal day
    yearbase+dday --> mpl datenum --> python epoch secs --> time tupe --> asc
    '''

    y,m,d,hh,mm,ss=to_date(yearbase, dday)
    return '%4d/%02d/%02d %02d:%02d:%02d' % (y,m,d,hh,mm,ss)

    # or, using matplotlib and python 'time'
    #
    # mpl_datenum = dday_to_mpl(yearbase, startdd)
    ## TODO: fix these hints; num2epoch no longer exists
    # secs_since_epoch =  matplotlib.dates.num2epoch(mpl_datenum)
    # timetuple = time.gmtime(secs_since_epoch)
    # return time.asctime(timetuple)

#---------------------------------


def matchbox_width(change_this_one, source_of_width):
    '''
    make source axes have same width as dest
    '''
    source = source_of_width
    dest = change_this_one
    bbox0 = dest.get_position()
    bbox1 = source.get_position()
    dest.set_position([bbox0.x0, bbox0.y0, bbox1.width, bbox0.height])
    plt.draw()

#---------------------------------

def rbin_file_times(globstr, yearbase):
    '''
    output dday and date range for file gps rbin filelist
    '''
    filelist=pathops.make_filelist(globstr)
    #
    for f in filelist:
        rbin = BinfileSet(f)
        base = os.path.basename(f).split('.')[0]
        startdday = rbin.starts['dday'][0]
        enddday = rbin.ends['dday'][0]
        lstart = codas.to_date(yearbase,startdday)
        lend = codas.to_date(yearbase,enddday)
        fstr = '%02d/%02d %02d:%02d'
        startdate = fstr % tuple(lstart[1:5])
        enddate = fstr % tuple(lend[1:5])
        #
        print('%s   %s - %s  (%6.3f-%6.3f)' % (base,
                                               startdate, enddate,
                                               startdday, enddday))

#--------------------------------------------

def colorN(y, cmapname='rainbow'):
    '''
    inputs: array y,

    return a list of colors, len(y) suitable for this:

    colors = colorN(y)
    for ii in range(len(y)):
        plot(x[ii], y[ii], 'o', color=colors[i])
    '''
    if np.iterable(y):
        ncolors = len(y)
    else:
        ncolors = y
    cm = get_extcmap(cmapname)
    return cm(np.linspace(0, 1, ncolors))

#--------------------------------------------


def plot5(var3d, bin=40, varline=None, profs=None, **kwargs):
    '''
    plot 4x1 subplots of variable AND one line-plot with values at a bin
    **kwargs passed to qpc
    eg. plot5(data.vel[::5,:,:], profs=data.dday, clim=[-4,4])
    '''
    nprofs, nbins, nbeams  = var3d.shape
    if profs is None:
        pp=np.arange(nprofs+1)-.5
        profs = np.arange(nprofs)
    else:
        pp=np.zeros(len(profs)+1)
        dt = np.median(np.diff(profs))
        pp[0] = profs[0] - dt/2
        pp[1:] = profs + dt/2

    f,ax=plt.subplots(nrows=5, sharex=True)
    for ii in [0,1,2,3]:
        qpc(var3d[:,:,ii], ax=ax[ii], profs=profs, **kwargs)

    colors = ['r','g','b','k']
    for beam in [0,1,2,3]:
        ax[4].plot(profs, var3d[:,bin,beam], '.-',
                   color=colors[beam])
    if varline is not None:
        ax[4].plot(profs, varline+np.zeros(profs.shape), 'y')

    matchbox_width(ax[4], ax[0])

    plt.draw()
    return f,ax


def plot4(var3d, profs=None, figsize=None, **kwargs):
    '''
    plot 4x1 subplots of variable
    **kwargs passed to qpc
    eg. plot5(data.vel[::5,:,:], profs=data.dday, clim=[-4,4])
    '''
    nprofs, nbins, nbeams  = var3d.shape
    if profs is None:
        pp=np.arange(nprofs+1)-.5
        profs = np.arange(nprofs)
    else:
        pp=np.zeros(len(profs)+1)
        dt = np.median(np.diff(profs))
        pp[0] = profs[0] - dt/2
        pp[1:] = profs + dt/2

    f,ax=plt.subplots(figsize=figsize, nrows=4, sharex=True)
    for ii in [0,1,2,3]:
        qpc(var3d[:,:,ii], ax=ax[ii], profs=profs, **kwargs)

    plt.draw()
    return f,ax

def subsample_ec_raw(rawdata):
    '''
    subsample (in place) raw ec data.
    eg.  data=Multiread(filelist,'ec')
         data.read(stop=400)
         subsample_ec_raw(data)
    '''
    from pycurrents.adcp.raw_simrad import subsample_ppd
    subsample_ppd(rawdata)  # Modified in place!



def set_rgbk():
    ''' new color cycler with r,g,b,k first
    '''
    from cycler import cycler
    mpl.rcParams['axes.prop_cycle'] = cycler(
                 color=['r','g','b','k','m','c','y'])

def read_nc(fname):
    ''' read an adcp netcdf file
    '''
    import pycurrents.adcp.panelplotter as pp
    data=pp.get_data(fname)  # based on suffix
    return data
