'''
leverage CPlotter to make plots of netCDF data
'''

import os
import logging

import netCDF4 as nc

import numpy as np

import matplotlib.pyplot as plt

from pycurrents.codas import get_profiles         # general codasdb reader
from pycurrents.num import Stats            # mean,std,med (masked)
from pycurrents.adcp._plot_tools import clims, display_opt, reset_display_opt
from pycurrents.adcp.cplotter import CPlotter
from pycurrents.system.misc import Bunch
from pycurrents.num.nptools import rangeslice
from pycurrents.adcp.uhdas_defaults import proc_instrument_defaults
from pycurrents.adcp.uhdasfile import guess_dbname
from pycurrents.codas import to_datestring
from pycurrents.plot.mpltools import add_UTCtimes

from datetime import datetime, timedelta
from pycurrents.data.suntimes import daily_suntimes


# Standard logging
_log = logging.getLogger(__name__)

#names of panels variables and their output to the screen
heading = 'heading, spd'
numpings  = 'numpings, spd'
tr_temp  = 'tr_temp, spd'

ax_sharey = {'u', 'v', 'amp', 'pg'}
ax_defaultlist = ['u','v','amp','pg', 'heading', 'numpings', 'tr_temp']
ax_annotations=Bunch()
ax_annotations.u = '(E/W velocity)'
ax_annotations.v = '(N/S velocity)'
ax_annotations.e = '(Error velocity)'
ax_annotations.amp = '(signal return)'
ax_annotations.pg = '(Percent Good)'

def get_CODAS_data(fname):
    data = get_profiles(fname, diagnostics=True)
    return data


# Formatting (stealing from adcpgui_qt
def utc_formatting(x, pos, yearbase):
    date = datetime(yearbase, 1, 1) + timedelta(x)
    return date.strftime('%m/%d %H:%M')

# removing _add_utcdates: superceded by add_UTCtimes


def get_netCDF_data(fname):
    '''
    read data from compressed, short, or long netCDF file
    TODO: if long file, make short
    '''
    ds = nc.Dataset(fname)
    data=Bunch()
    for varname in ds.variables.keys():
        if varname not in ('trajectory',):
            dvar = ds.variables[varname]
            if varname == 'time':
                data['dday'] = dvar[:]
                units = dvar.units
                ymd=units.split()[2]
                data['yearbase'] = int(ymd.split('-')[0])
            else:
                if dvar.dtype.kind == 'f':
                    data[varname] = np.ma.masked_invalid(dvar[:])
                else:
                    data[varname] = dvar[:]
    data['spd'] = np.hypot(data.uship, data.vship)  # OK for masked arrays
    return data

def get_data(fname):
    '''
    names are based on suffix: *.nc is netCDF, *dir.blk is codas database
    '''
    success = False
    if fname[-2:].lower() == 'nc':
        _log.info('trying netCDF file %s' % (fname))
        data = get_netCDF_data(fname)
        _log.info('netCDF: success')
        success = True
    if not success:
        _log.info('looking for codas db from %s' % (fname))
        _log.info('full path = %s' % (os.path.realpath(fname)))
        dbname = guess_dbname(fname) #this will bomb if cannot find db
        data = get_CODAS_data(dbname)
        _log.info('codasdb: success')
    return data



def extract_ddrange(data, ddrange=None, pad=10/86400.):
    '''
    ddrange follows the same standards as codas.DB.get_profiles
    *ddrange*
        *None* | ndays | (startdd, enddd)
        if ndays > 0, take first ndays;
        if ndays < 0, take last abs(ndays)
    '''
    rs = rangeslice(data.dday, ddrange)
    newdata = Bunch(yearbase=data['yearbase'])
    for varname, var in data.items():
        if not hasattr(var, "ndim") or var.ndim == 0:
            # numpy scalar or general python object
            newdata[varname] = var
        elif var.ndim < 3:
            # numpy array: skip 3-D variables (e.g., raw amplitude).
            newdata[varname] = var[rs]
    return newdata


def trim_masked(newdata):
    # bug in versions up through mpl1.4.3 cause pcolorfast to
    # not show pcolor if depth ranges change
    min_good_bins = min(sum(newdata.depth.mask is False, axis=1))
    shortdata = Bunch()
    shortdata[u'yearbase'] =  newdata[u'yearbase']
    for varname in newdata.keys():
        try:
            ndim = len(newdata[varname].shape)
            sl = slice(0,min_good_bins)
            if ndim == 2:
                shortdata[varname] = newdata[varname][:,sl]
            # else skip variables with 1 or 3 dimensions
        except:
            shortdata[varname] = newdata[varname]
    return shortdata


def fill_masked_inplace(newdata):
    # bug in versions up through mpl1.4.3 cause pcolorfast to
    # not show pcolor if depth ranges change
    nprofs, nbins = newdata.depth.shape
    xx, depthgrid = np.meshgrid(np.arange(nprofs), np.arange(nbins))
    S=Stats(np.ma.diff(newdata.depth, axis=1), axis=1)
    dz = S.median
    #each bin:  [0,1,2,...N]* dz        +  top bin
    newz = depthgrid.T*dz[:,np.newaxis] +  newdata.depth[:,0][:,np.newaxis]
    newdata.depth = newz


def guess_sonar(filebase):
    lowercase = filebase.lower()
    instnames = list(proc_instrument_defaults['enslength'].keys())
    allsonars = []
    os_nonspecific = []  # in case someone has 'os75' for mixed (eg oleander)
    for iname in instnames:
        if iname[:2] == 'os':
            allsonars.append(iname + 'bb')
            allsonars.append(iname + 'nb')
            os_nonspecific.append(iname)
        else:
            allsonars.append(iname)
    found_sonars=[]
    for s in allsonars:
        if s in lowercase:
            found_sonars.append(s)
    if len(found_sonars) == 0:  #'bb' or 'nb' missing?
        for s in os_nonspecific:
            if s in lowercase:
                found_sonars.append(s)
    return found_sonars


class NCData:
    '''
    set up a chunk of ADCP data for plotting, pass it into CPlotter
    '''
    # stolen from adcp/cplotter

    def __init__(self, data, **kwargs):
        '''
        typical usage:

        # set up 'data' (Bunch) with attributes such as from compressed netcdf
        '''
        self.data=data
        #
    def set_grid(self, ylim=None, use_bins=False):
        '''
        add one timestamp to the end
        add one bin (or depth) to the bottom
        '''
        d = self.data.depth
        nprofs, nbins = d.shape
        #
        x = self.data.dday.copy()
        dx = x[1] - x[0]
        xb = np.insert(x, 0, x[0] - dx)
        X =  np.empty((nprofs+1, nbins+1), dtype=type(x[0]))
        for ii in range(0,nbins+1):
            X[:,ii] = xb
        #
        if use_bins:
            self.yname = 'bins'
            yb = np.arange(self.data.nbins+1, dtype = float)
            self.ylim = [self.data.nbins+1, 0]
        else:
            self.yname = 'meters'
            nprofs, nbins = d.shape
            dy = np.empty(nprofs+1)
            dy[1:] = 0.5*(d[:,1] - d[:,0])
            dy[0] = dy[1]
            #
            yb = np.empty((nprofs+1, nbins+1), dtype=type(d[0,0]))
            yb[:-1,0]=d[:,0]-dy[:-1]
            yb[-1,0] =  yb[-2,0]
            for ii in range(0,nbins):
                yb[:-1,ii+1]=d[:,ii]+dy[1:]
            yb[:,-1] = yb[:,-2]
            #
            if ylim is not None:
                self.ylim = ylim
            else:
                self.ylim = [np.max(self.data.depth), 0]
        #
        self.Yirreg = yb.T
        self.Xirreg = X.T
        #
#        self.xlim = [xb[0], xb[-1]]
        self.xlim = [xb[0], xb[-2]]


def get_uv_clims(data, maxvel=None):
    if maxvel is None: #autoscale
        absvels = np.ravel( [np.abs(data.u.compressed()),
                             np.abs(data.v.compressed())] )
        if len(absvels) > 20:
            maxvel = 1.2 * np.sort(absvels)[int(np.round(len(absvels)*.95))]
        else:
            maxvel = 1.0  # could be better
        #
        if maxvel < .2:
            maxvel = .2
        elif maxvel <= .4:
            maxvel = .4
        elif maxvel <= .6:
            maxvel = .6
        elif maxvel <= .8:
            maxvel = .8
        else:
            maxvel = 1
    else:
        maxvel = maxvel
    return [-maxvel, maxvel]


# now make a parasite axis for amp labels
def _parasite(axx):
    # create another axes on the same position:
    # - create second axes on top of the first one without background
    # - make the background invisible
    # - set the x scale according to that of `ax1`
    # - set the top ticks on and everything else off
    # - set the size according to the size of `ax1`
    newax = axx.figure.add_axes(axx.get_position(), frameon=False)
    newax.tick_params(labelbottom='off', labelleft="off", labelright='off',
                      bottom='off', left='off', right='off',
                      top = 'on',
                      labeltop='on')

    newax.set_xlim(axx.get_xlim())
    return newax

def _make_axes(fig=None, numax=5, sharex=True):
    """
    Make a stack of 'numax' panels, each with a
    colorbar Axes and a twinx axes, which may or may not
    end up being used.

    Returns a dictionary with parallel lists of these Axes
    corresponding to the stack of panels.  Keys are "pcolor",
    "cbar", and "twinx".

    This is for internal use, and may be replaced by a more modern
    implementation.  It was originally in adcpgui/tools.py.
    """

    axdict = dict(pcolor=[], cbar=[], twinx=[])
    #
    x0 = .08
    totalheight = .78   #.8
    ax_height = totalheight/float(numax)
    starty= 0.1
    #
    pax_width = 0.8
    pad = totalheight*.01
    #pcolor axes; appending from the bottom upwards

    # define one, then sharex with that
    plotnum = 0
    left = x0
    bottom = starty + plotnum*(ax_height+pad)
    width = pax_width
    height = ax_height
    axx=fig.add_axes([left, bottom, width, height])
    axdict['pcolor'].append(axx)

    for plotnum in range(1,numax):
        bottom = starty + plotnum*(ax_height+pad)
        width = pax_width
        height = ax_height
        axdict['pcolor'].append(
            fig.add_axes([left, bottom, width, height], sharex=axx))

    #colorbar axes
    cax_pad = .04
    cax_width = .009
    #
    for plotnum in range(numax):
        left = x0 + pax_width + cax_pad
        bottom = starty +.1*ax_height + plotnum*(ax_height+pad)
        width = cax_width
        height = .8*ax_height
        axdict['cbar'].append(fig.add_axes([left, bottom, width, height]))
        #
    #twinx on pax
    for plotnum in range(numax):
        axdict['twinx'].append(axdict['pcolor'][plotnum].twinx())
    #
    ##
    # reverse the order so 0,1,2,3 starts at the top
    for name, arr in axdict.items():
        axdict[name] = arr[::-1]

    # turn off x axis
    for ax in axdict['twinx']:
        ax.set_xticks([])
        # After mpl commit 6103f64f, we need the following:
        ax.set_frame_on(False)
        # This might be a mpl bug; it remains to be investigated.
        # If it turns out to be a mpl bug, then if there are no
        # released versions with it, our fix above can be removed.
    for ax in axdict['pcolor'][:-1]:
        ax.set_xticks([])

    return axdict


def plot_data(NCD, axdict=None, speed=False, sonar=None, axlist=None,
              numax=5, add_utc=False, add_suntimes=False,
              maxvel=None,  # velocity clim max; None is auto
              annotation_color='k', extra_names=False, figsize=(10,10)):
    '''
    NCD is an instance of NCData
    make pcolor plots
    default names that will work are
        ['u','v','amp','pg', 'e', 'heading', 'numpings', 'tr_temp']
    ship speed will be added to  'heading' and 'numpings'
    '''
    if sonar is None:
        raise ValueError('must set sonar, eg: "wh300", "os38nb"...')

    # specify by 'heading', 'numpings',
    if axlist is None:  #default order of plotting
        axlist = ax_defaultlist[:numax]
        axlist.append('heading')

    if numax < len(axlist):
        axlist = axlist[:numax]  # just take the first numax of the defaults
    else:
        numax = len(axlist)

    for iplot in range(numax):
        astr = axlist[iplot]
        if astr in ('heading', 'numpings', 'tr_temp'):
            axlist[iplot] = astr + ', ' + 'spd'

    fig=plt.figure(figsize=figsize)
    if not axdict:
        axdict = _make_axes(fig=fig, numax=numax, sharex=True)
    reset_display_opt()
    display_opt['axes']=axlist

    sharey_indices = [idx for idx in range(numax) if axlist[idx] in ax_sharey]
    if len(sharey_indices) > 2:
        first = sharey_indices[0]
        for idx in sharey_indices[1:]:
            axdict['pcolor'][idx].sharey(axdict['pcolor'][first])

    #
    velrange = get_uv_clims(NCD.data, maxvel=maxvel)
    display_opt['velrange'] = velrange
    clims['u'] = velrange
    clims['v'] = velrange
    #
    CP = CPlotter(fig=fig, axdict=axdict)

    for iplot in range(numax):
        astr = axlist[iplot]
        if astr in (heading, numpings, tr_temp):
            try:
                CP.draw_misc(axdict['pcolor'][numax-1], NCD, iplot, astr)
            except:
                _log.warning('cannot plot %s' % (astr))
                raise#pass xxx
        else: # could be 'u','v','e','pg','amp'
            try:
                CP.draw_ax(NCD, iplot, astr, sonar=sonar, speed=speed,
                           annotation = ax_annotations[astr],
                           use_cbarjet=False, set_bad=(.8,.8,.8))
            except:
                _log.warning('cannot plot %s' % (astr))
                pass

    # this has bugs under xenial; maybe it will work under bionic
    if add_utc:
        # ax_utc=_parasite(axdict['pcolor'][0])
        # _add_utcdates(ax_utc, yearbase=NCD.data.yearbase)
        add_UTCtimes(axdict['pcolor'][0],
                yearbase=NCD.data.yearbase, offset=5)

    if add_suntimes:
        # Assume that if anything is masked, it is masked in lon:
        ddays = np.ma.array(NCD.data.dday, mask=np.ma.getmask(NCD.data.lon))
        ddays = ddays.compressed()
        lon = NCD.data.lon.compressed()
        lat = NCD.data.lat.compressed()
        # (We might put logic like the above into daily_suntimes, in
        # which case it can be removed here.)

        try:
            sunrises, sunsets = daily_suntimes(lon, lat, ddays, NCD.data.yearbase)
        except ValueError:
            sunrises = None
            sunsets = None
            _log.warning('could not determine sunrise/sunset')
        try:
            ampnum = axlist.index('amp')
        except ValueError:
            ampnum=0

        if (sunrises is not None) and (sunsets is not None):
            z = np.full(sunrises.shape, NCD.data.depth[0, -3])
            axdict['pcolor'][ampnum].plot(sunrises, z, 'o',
                                      mec='k', mfc=(1,1,0), ms=10)
            axdict['pcolor'][ampnum].plot(sunsets, z, 'o',
                                      mec='w', mfc='k', ms=10)

    axdict['cbar'][numax-1].set_visible(False)
    axdict['pcolor'][numax-1].set_xlabel('decimal day')

    duration = '%3.2f days' % (NCD.data.dday[-1]-NCD.data.dday[0])
    ddaystr = '%s to %s (%s)' % (np.round(NCD.data.dday[0],2),
                               np.round(NCD.data.dday[-1],2),
                               duration)
    yearbase = NCD.data.yearbase
    datestr = '%s to %s' % (to_datestring(yearbase, NCD.data.dday[0])[:-3],
                            to_datestring(yearbase, NCD.data.dday[-1])[:-3])

    fig.text(.03, .02, ddaystr, ha='left', color=annotation_color)
    fig.text(.98, .02, datestr, ha='right', color=annotation_color)

    return fig
