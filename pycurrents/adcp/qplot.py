"""
Functions for quick plotting of adcp data.

They are intended for easy interactive use, but may also
be used in scripts.

+ :func:`qpc` Quick Pcolor plot
+ :func:`qcf` Quick Contourf
+ :func:`qcont` Quick Contour (for adding line contours)
+ :func:`qnav` Quick Nav plot (xy, plus tx and ty)
+ :func:`qnav1` Quick Nav plot (x,y only)
+ :func:`txy`   Qiuck Nav Plot (tx and ty)
+ :func:`qmessage` Text message in an empty Axes (also 'textfig')

"""

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import logging

from pycurrents.plot.mpltools import get_extcmap
import pycurrents.plot.maptools as mt #(Conic, Mercator, Mapbase)
from pycurrents.data.nmea.qc_rbin import RbinSet
from pycurrents.file.binfile_n import BinfileSet, binfile_n
from pycurrents.data import navcalc # uv_from_txy, unwrap_lon, unwrap ...
from matplotlib.ticker import ScalarFormatter
from pycurrents.plot.mpltools import add_UTCtimes, regrid_for_pcolor

# Standard logging
_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


def _get_fig_ax(ax):
    if ax is None:
        f = plt.gcf()
        if len(f.axes) == 0:
            fig = f
        else:
            fig = plt.figure()
        ax = fig.add_subplot(1,1,1)
    else:
        fig = ax.figure
        plt.sca(ax)
    return fig, ax


def _process_cbar_kw(cbar_kw, ax, discrete=False):
    cbkw = dict(extend='both', aspect=20, shrink=0.8)
    if not discrete:
        cbkw['ticks'] = mpl.ticker.MaxNLocator(nbins=5)
    if cbar_kw is not None:
        cax = cbar_kw.pop('cax', None)
        if cax is None:
            cbkw['ax'] = ax
        else:
            cbkw['cax'] = cax
        cbkw.update(cbar_kw)
    return cbkw

def _adjust_nbins(ax):
    pos = ax.get_position()
    if pos.width < 0.6:
        ax.locator_params('x', nbins=5)
    if pos.height < 0.6 and pos.height > 0.3:
        ax.locator_params('y', nbins=5)
    elif pos.height <= 0.3:
        ax.locator_params('y', nbins=4)


class QFig:
    def __init__(self):
        self.fig = None
        self.drew_cax = False

    def get_fig_ax(self, ax, cbar_kw):
        if ax is None:
            f = plt.gcf()
            if len(f.axes) == 0:
                fig = f
            else:
                fig = plt.figure()
            ax = fig.add_subplot(1,1,1)
        else:
            fig = ax.figure
            plt.sca(ax)
        # now carve off a piece for the colorbar
        cax, kw = mpl.colorbar.make_axes(ax, **cbar_kw)
        self.fig = fig
        self.ax = ax
        self.cax = cax

    def _process_cbar_kw(self, cbar_kw, ax, cax, discrete=False):
        cbkw = dict({'extend':'both'})
        if not discrete:
            cbkw['ticks'] = mpl.ticker.MaxNLocator(nbins=5)

        if cbar_kw is not None:
            if 'cax' in list(cbar_kw.keys()):
                cbkw['cax'] = cbar_kw['cax']
            else:
                cbkw['cax'] = cax
        cbkw.update(cbar_kw)
        return cbkw




def qpc(data, profs=None, bins=None,
            ax=None, qfig=None,
            title=None,
            cmapname='jet',
            cbar_kw=None,
            set_bad=True,
            dx_max=None,
            color_num=256,
            reverse=True,   # for oceanography plots: bin or depth increases down.
            **kwargs):
    '''
    quick pcolor plot, designed for ADCP data

    *args*

        + *data* is an array (masked or not), shape is (nprofs, nbins)

    *kwargs*

        + *profs* : override index number with this x-axis variable
        + *bins* : override bin number with this y-axis variable
        + *ax* : if none, a subplot(1,1,1) will be made
        + *qfig* : QFig instance -- for updating; overrides ax
        + *title* : title for plot
        + *cmapname* : colormap name (default, or from get_extcmap)
        + *cbar_kw* : sent to colorbar
        + *set_bad* : True (default -- color masked values light gray)
                      - To disable, use "set_bad=False"
                      - To change color, specify valid color value
        + *dx_max* : if not None (default), insert a nan column where
                        the width of a column would exceed this value.
        + *color_num* : the number of discrete colors in the colorbar.
        + other kwargs are passed to pcolorfast

    *returns*

        * pcolorfast instance


    '''

    if cbar_kw is None:
        cbar_kw = dict()

    nprofs, nbins  = data.shape
    if profs is None:
        pp=np.arange(nprofs+1)-.5
    else:
        if dx_max is not None:
            pp, data = regrid_for_pcolor(profs, data, dx_max=dx_max, axis=0)
            nprofs = len(pp)
        else:
            # This original code is not actually needed, but
            # regrid_for_pcolor handles it slightly differently.
            pp=np.zeros(len(profs)+1)
            dt = np.median(np.diff(profs))
            pp[0] = profs[0] - dt/2
            pp[1:] = profs + dt/2
    if bins is None:
        bb = np.arange(nbins+1)-.5
    else:
        bb=np.zeros(len(bins)+1)
        dt = np.median(np.diff(bins))
        bb[0] = bins[0] - dt/2
        bb[1:] = bins + dt/2

    ## new fig versus update mode
    if qfig is None: # new fig
        QF=QFig()
        QF.get_fig_ax(ax, cbar_kw)  # Also makes the cbar; needs some kwargs.
    else: # instantiate QF elsewhere, use to update
        QF = qfig

    cmap = get_extcmap(name=cmapname, lut=color_num)
    if set_bad is True:
        cmap.set_bad([.9,.9,.9])
    elif set_bad:
        try:
            cmap.set_bad(set_bad)
        except:
            _log.exception('cannot parse "set_bad" color')

    QF.ax.cla()
    pcf = QF.ax.pcolorfast(pp, bb,  data.T,  cmap=cmap, **kwargs)
    QF.ax.ticklabel_format(style='plain', useOffset=False)

    QF.ax.set_xlim(pp[0], pp[-1])
    if reverse:
        QF.ax.set_ylim(bb[-1], bb[0])
    else:
        QF.ax.set_ylim(bb[0], bb[-1])
    if title:
        QF.ax.set_title(title)

    if QF.drew_cax is False:
        QF.cax.cla()
        cbkw = QF._process_cbar_kw(cbar_kw, QF.ax, QF.cax)
        QF.fig.colorbar(pcf, **cbkw)
        QF.drew_cax = True

    _adjust_nbins(QF.ax)
    plt.draw_if_interactive()
    return pcf


#-------------

def qcf(data, profs=None, bins=None, ax=None, title=None,
        cmapname='jet',
        levels=12,
        cbar_kw=None,
        zeroline=None,
        **kwargs):

    '''
    (contourf version of qpc)

    quick contourf plot, designed for ADCP data

    *args*

        + *data* is an array (masked or not), shape is (nprofs, nbins)

    *kwargs*

        + *profs* : override index number with this x-axis variable
        + *bins* : override bin number with this y-axis variable
        + *ax* : if none, a subplot(1,1,1) will be made
        + *title* : title for plot
        + *cmapname* : colormap name (default, or from get_extcmap)
        + *levels* : number of levels, or sequence of contourf boundaries
        + *cbar_kw* : sent to colorbar
        + *zeroline* : None, True, False
        + other kwargs are passed to contourf and to contour

    *returns*

        * contourf instance

    '''
    nprofs, nbins  = data.shape
    if profs is None:
        pp=np.arange(nprofs)
    else:
        pp=profs

    if bins is None:
        bb = np.arange(nbins)
    else:
        bb=bins

    X, Y = np.meshgrid(pp,bb)
    X = X.T
    Y = Y.T

    fig, ax = _get_fig_ax(ax)

    cmap = get_extcmap(name=cmapname)

    extend = 'both'
    try:
        if levels[0] == 0: # It's probably something like std dev.
            extend = 'max'
        if zeroline is None:
            if levels[0] >= 0 or levels[-1] <= 0:
                zeroline = False
    except TypeError:
        pass               # levels is a scalar
    if zeroline is None:
        zeroline = True


    cset = plt.contourf(X,Y,data, levels, extend=extend, cmap=cmap, **kwargs)
    if zeroline:
        cset1 = plt.contour(X,Y,data, [0], colors='k', **kwargs)

    ax.ticklabel_format(style='plain', useOffset=False)

    ax.set_xlim(pp[0], pp[-1])
    ax.set_ylim(max(bb), min(bb))
    if title:
        ax.set_title(title)

    cbkw = _process_cbar_kw(cbar_kw, ax, discrete=True)

    cbar = fig.colorbar(cset, **cbkw)
    if zeroline:
        try:
            cbar.add_lines(cset1)
        except ValueError:
            pass # colorbar bug: it fails when given a line
                 # outside its range.

    _adjust_nbins(ax)

    plt.draw_if_interactive()

    return cset

#--------------

def qcont(x,y,Z, *args, **kwargs):
    '''
    assumes x,y match Nprofs, Nbins for Z
    creates X,Y to match size of Z
    pass the rest of the arguments to contour
    assumes gca() has the contour plot

    Intended for adding line contours to qpc pcolor plots

    returns contour instance

    This needs to be updated to better match qcf.

    '''

    X, Y = np.meshgrid(x, y)
    cset = plt.contour(X.T, Y.T, Z, *args, **kwargs)

    ax=plt.gca()

    ax.set_xlim(x[0], x[-1])
    ax.set_ylim(max(y), min(y))

    plt.draw_if_interactive()

    return cset




def qnav1(data, fig=None, projection=None, title=None, dt=900, **kwargs):
    '''
    make a single plot with navigation over topograpy

    **call signature**:

    ``qnav1(data, fig=None, projection=None, **kwargs)``

    *args*

        * *data* is 'dday', 'lon', 'lat', input as:

           (1) binfile (or BinfileSet or RbinSet)
           (2) rangeslice (from rbinrs)
           (3) list of [dday, lon, lat]
           (4) glob or list of files suitable for RbinSet

    *kwargs*

        + *projection* is  'Conic' or 'Mercator' or None (autoselect)
        + *dt* is the target sampling interval in seconds.
           Default is 900 s (15 minutes)

    *returns*:

        * maptools.mapper instance (Basemap subclass instance)

    '''
    dday = None
    lon = None
    lat = None

    try:
        data = RbinSet(data)
    except:
        pass

    if isinstance(data, (RbinSet, BinfileSet, binfile_n)):
        dday = data.records['dday']
        lon = data.records['lon']
        lat = data.records['lat']
    elif isinstance(data, np.ndarray):
        try:
            if 'dday' in data.dtype.names:
                dday = data['dday']
                lon = data['lon']
                lat = data['lat']
            else:
                _log.warning('"dday" not found in dtype.names')
        except TypeError:  # dtype.names is None
            ss = data.shape
            if len(ss) > 1 and ss[1] == 3:
                dday = data[:,0]
                lon = data[:,1]
                lat = data[:,2]
            else:
                _log.warning('data array is not Nx3')
                return
    elif isinstance(data, list):
        if len(data) == 3:
            dday, lon, lat = data
    else:
        _log.warning('data not binfiles, records, array, or list.  What is it?')

    if dday is None or len(dday) == 0:
        _log.warning('no t,x,y data found')
        return

    rawdt = np.median(np.diff(dday*86400))
    step = max(1, int(dt // rawdt))
    if step > 1:
        dday = dday[::step]
        lon = lon[::step]
        lat = lat[::step]

    # stage, and plot
    lon = navcalc.unwrap_lon(lon)
    if fig is None:
        fig = plt.figure(figsize=(8,6), dpi=110)

    fig.subplots_adjust(bottom=0.05)
    # subplot
    ax = fig.add_subplot(111)

    bmap = mt.mapper(lon, lat,
                              projection=projection,
                              aspect=0.8,
                              pad = 0.4,
                              min_size=1,
                              resolution=None,
                              ax=ax)
    bmap.topo()
    bmap.grid(nx=4, ny=4)
    bmap.mplot(lon,lat,'k.')
    bmap.mplot(lon[0], lat[0], 'go', ms=15)
    bmap.mplot(lon[-1], lat[-1], 'rx', ms=15, mew=4)

    if title is not None:
        fig.suptitle(title)

    return bmap


def qtxy(data, fig=None, title=None, dt=900, yearbase=None, **kwargs):
    '''
    make a 1-panel nav plot with

        * top panel = time/lon and time/lat

    **call signature**:

    ``qtxy(data, fig=None, **kwargs)``

    *args*

        * *data* is 'dday', 'lon', 'lat', input as:

           (1) binfile (or BinfileSet or RbinSet)
           (2) rangeslice (from rbinrs)
           (3) list of [dday, lon, lat]
           (4) glob or list of files suitable for RbinSet

    *kwargs*

        + *dt* is the target sampling interval in seconds.
           Default is 900 s (15 minutes)

        + *yearbase* -- required to get UTC times


    '''
    dday = None
    lon = None
    lat = None

    try:
        data = RbinSet(data)
    except:
        pass

    if isinstance(data, (RbinSet, BinfileSet, binfile_n)):
        dday = data.records['dday']
        lon = data.records['lon']
        lat = data.records['lat']
    elif isinstance(data, np.ndarray):
        try:
            if 'dday' in data.dtype.names:
                dday = data['dday']
                lon = data['lon']
                lat = data['lat']
            else:
                _log.warning('"dday" not found in dtype.names')
        except TypeError:  # dtype.names is None
            ss = data.shape
            if len(ss) > 1 and ss[1] == 3:
                dday = data[:,0]
                lon = data[:,1]
                lat = data[:,2]
            else:
                _log.warning('data array is not Nx3')
                return
    elif isinstance(data, list):
        if len(data) == 3:
            dday, lon, lat = data
    else:
        _log.warning('data not binfiles, records, array, or list.  What is it?')

    if dday is None or len(dday) == 0:
        _log.warning('no t,x,y data found')
        return

    rawdt = np.median(np.diff(dday*86400))
    step = max(1, int(dt // rawdt))
    if step > 1:
        dday = dday[::step]
        lon = lon[::step]
        lat = lat[::step]

    # stage, and plot
    lon = navcalc.unwrap_lon(lon)
    if fig is None:
        fig = plt.figure(figsize=(8,5), dpi=110)

    # subplot
    ax1 = fig.add_subplot(111)
    ax2 = ax1.twinx()
    ax1.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    if yearbase is None:
        fig.subplots_adjust(bottom=0.05, right=.85, left=.15)
        ax1.set_xlabel('decimal day')
    else:
        fig.subplots_adjust(bottom=0.18, right=.85, left=.15)

    ax1.plot(dday, lon, 'b.')
    ax2.plot(dday, lat, 'g.')
    ax1.yaxis.set_major_formatter(mt.LonFormatter())
    ax2.yaxis.set_major_formatter(mt.LatFormatter())
    ax1.set_ylabel('Longitude')
    ax2.set_ylabel('Latitude')

    ax1.set_xlim(dday[0], dday[-1])
    ax2.set_xlim(dday[0], dday[-1])
    ax1.grid(True)
    ax1.tick_params('y', colors='b')
    ax2.tick_params('y', colors='g')
    ax1.locator_params(nbins=5)
    ax2.locator_params('y', nbins=5)

    if yearbase is not None:
        add_UTCtimes(ax1, yearbase, position='bottom')

    if title is not None:
        fig.suptitle(title)

    return fig, ax1

def qnav(data, fig=None, projection=None, title=None, dt=900, **kwargs):
    '''
    make a 2-panel nav plot with

        * top panel = time/lon and time/lat
        * bottom panel =   lon/lat


    **call signature**:

    ``plot_nav(data, fig=None, projection=None, **kwargs)``

    *args*

        * *data* is 'dday', 'lon', 'lat', input as:

           (1) binfile (or BinfileSet or RbinSet)
           (2) rangeslice (from rbinrs)
           (3) list of [dday, lon, lat]
           (4) glob or list of files suitable for RbinSet

    *kwargs*

        + *projection* is  'Conic' or 'Mercator' or None (autoselect)
        + *dt* is the target sampling interval in seconds.
           Default is 900 s (15 minutes)

    *returns*:

        * maptools.mapper instance (Basemap subclass instance)

    '''
    dday = None
    lon = None
    lat = None

    try:
        data = RbinSet(data)
    except:
        pass

    if isinstance(data, (RbinSet, BinfileSet, binfile_n)):
        dday = data.records['dday']
        lon = data.records['lon']
        lat = data.records['lat']
    elif isinstance(data, np.ndarray):
        try:
            if 'dday' in data.dtype.names:
                dday = data['dday']
                lon = data['lon']
                lat = data['lat']
            else:
                _log.warning('"dday" not found in dtype.names')
        except TypeError:  # dtype.names is None
            ss = data.shape
            if len(ss) > 1 and ss[1] == 3:
                dday = data[:,0]
                lon = data[:,1]
                lat = data[:,2]
            else:
                _log.warning('data array is not Nx3')
                return
    elif isinstance(data, list):
        if len(data) == 3:
            dday, lon, lat = data
    else:
        _log.warning('data not binfiles, records, array, or list.  What is it?')

    if dday is None or len(dday) == 0:
        _log.warning('no t,x,y data found')
        return

    rawdt = np.median(np.diff(dday*86400))
    step = max(1, int(dt // rawdt))
    if step > 1:
        dday = dday[::step]
        lon = lon[::step]
        lat = lat[::step]

    # stage, and plot
    lon = navcalc.unwrap_lon(lon)
    if fig is None:
        fig = plt.figure(figsize=(6,8), dpi=110)

    fig.subplots_adjust(bottom=0.05)
    # subplot 1
    ax1 = fig.add_subplot(211)
#    bb = ax1.get_position()
#    bbs = bb.shrunk(0.93,0.96)
#    ax1.set_position(bbs.anchored('C', bb))
    ax2 = ax1.twinx()
    ax1.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))

    ax3 = fig.add_subplot(212)


    ax1.plot(dday, lon, 'b.')
    ax2.plot(dday, lat, 'g.')
    ax1.yaxis.set_major_formatter(mt.LonFormatter())
    ax2.yaxis.set_major_formatter(mt.LatFormatter())
    ax1.set_xlabel('decimal day')

    ax1.set_xlim(dday[0], dday[-1])
    ax2.set_xlim(dday[0], dday[-1])
    ax1.grid(True)
    ax1.tick_params('y', colors='b')
    ax2.tick_params('y', colors='g')
    ax1.locator_params(nbins=5)
    ax2.locator_params('y', nbins=5)

    ## subplot 2

    bmap = mt.mapper(lon, lat,
                              projection=projection,
                              aspect=0.8,
                              pad = 0.4,
                              min_size=1,
                              resolution=None,
                              ax=ax3)
    bmap.topo()
    bmap.grid(nx=4, ny=4)
    bmap.mplot(lon,lat,'k.')
    bmap.mplot(lon[0], lat[0], 'go', ms=15)
    bmap.mplot(lon[-1], lat[-1], 'rx', ms=15, mew=4)

    if title is not None:
        fig.suptitle(title)

    return bmap

# Keep original name available
plot_nav = qnav

def qmessage(tstr, ax=None, title=None, dpi=70, outfilebase=None, **kwargs):
    '''
    Write a string to an empty axes.

    *args*:

      * *tstr*: text string to put in the blank figure

    *kwargs*:

      * *ax* : axes instance, or None
      * *dpi* : save at this dpi
      * *outfilebase* : save to this file
      * remaining kwargs are passed to text()

    Returns the figure instance.

    '''

    fig, ax = _get_fig_ax(ax)

    ax.xaxis.set_major_locator(mpl.ticker.NullLocator())
    ax.yaxis.set_major_locator(mpl.ticker.NullLocator())

    ax.text(0.5, 0.5, tstr, ha='center',va='center',
                            transform=ax.transAxes, **kwargs)

    if title:
        ax.set_title(title)

    if outfilebase is not None:
        if not np.iterable(dpi):
            dpi = [dpi]
            outfilebase = [outfilebase]

        for d, outf in zip(dpi, outfilebase):
            plt.savefig(outf, dpi=d)

    plt.draw_if_interactive()

    return fig

textfig = qmessage

#----------------
