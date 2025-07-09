''' ADCP figure tools  '''
import itertools
import logging

import numpy as np
import numpy.ma as ma
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox

import pycurrents.num.grid as grid
from pycurrents.num.stats import Stats
from pycurrents.codas import to_date
from pycurrents.plot.maptools import LonFormatter, LatFormatter
from pycurrents.plot.maptools import mapper
from pycurrents.plot.mpltools import get_extcmap
from pycurrents.adcp.reader import timegrid_cdb
from pycurrents.adcp.uhdas_defaults import annotate_time_color

_pre36 = mpl.__version_info__ < (3, 6)
_pre37 = mpl.__version_info__ < (3, 7)

# Standard logging
_log = logging.getLogger(__name__)

# for debugging
# from IPython.Shell import IPShellEmbed
# ipshell = IPShellEmbed()

#---------------

class Vecmap:
    """
    Plot current vectors on topo map, with color-mapped temperature.
    """

    def __init__(self, lon, lat, u, v,
                 temperature=None,
                 vecscale=None,
                 vec_keyspeed=None,
                 ax=None,
                 bmap_kw=None,
                 grid_kw=None,
                 topo_kw=None,
                 cbar_kw=None, # for temperature cbar
                 zoffset=0,
                 refstr=None,
                 track_ends=True,
                 ):
        """
        Arguments:
            *lon*, *lat*, *u*, *v*: 1-D arrays, possibly masked

        Keyword arguments:
            *temperature*: 1-D array, possibly masked

        See signature and source for other kwargs.
        """
        if len(lon) == 0 or (np.ma.isMaskedArray(lon) and lon.count() == 0):
            raise ValueError('no good positions')

        if bmap_kw is None:
            bmap_kw = {}
        if grid_kw is None:
            grid_kw = {}
        if topo_kw is None:
            topo_kw = {}
        if cbar_kw is None:
            cbar_kw = {}
        goodposmask = ~np.ma.getmaskarray(lon)
        if goodposmask.sum() != len(lon):
            lon = lon[goodposmask]
            lat = lat[goodposmask]
            u = u[goodposmask]
            v = v[goodposmask]
            if temperature is not None:
                temperature = temperature[goodposmask]

        bmap_kw.setdefault('pad', 1)
        bmap_kw.setdefault('min_size', 1)
        bmap_kw.setdefault('aspect', 0.8)

        bmap = mapper(lon, lat, ax=ax, zoffset = zoffset, **bmap_kw)
        self.bmap = bmap
        # bmap.ax is now either the ax that was passed in, or one made by bmap.
        self.ax = bmap.ax
        bmap.grid(**grid_kw)
        if self._using_layout() and "cax" not in topo_kw:
            topo_kw["cax"] = "inset"
        bmap.topo(**topo_kw)

        x, y = bmap(lon, lat)
        self.plot_track(x, y, ends=track_ends)

        if np.ma.isMaskedArray(u) and u.count() == 0:
            return  # nothing more to plot

        if vecscale is None or vec_keyspeed is None:
            _vecscale, _vec_keyspeed = self.get_vecscale(u, v)
            if vecscale is None:
                vecscale = _vecscale
            if vec_keyspeed is None:
                vec_keyspeed = _vec_keyspeed

        urot, vrot = bmap.rotate_vector(u, v, lon, lat, returnxy=False)

        if temperature is None or np.all(temperature==0.0):
            MQ = bmap.quiver(x, y, urot, vrot,
                            units = 'inches',
                            pivot='tail', scale=vecscale,  color='k')
            self.mquiver = MQ
        else:
            arrowwidth = .03
            MQ = bmap.quiver(x,y,urot,vrot, temperature,
                            units = 'inches',
                            width=arrowwidth,
                            pivot='tail',
                            cmap = 'turbo',
                            scale=vecscale,
                            edgecolors='k',)
            self.mquiver = MQ

            MQ.set_clim(*self.scale_temperature(temperature))

            self.cbarTemp = self.add_cbar(**cbar_kw)

        linewidth = .7
        MQ.set_linewidth(linewidth)
        MQ.set_zorder(2.5)

        self.qkey = self.add_key(vec_keyspeed, linewidth, refstr)

    #----

    def _using_layout(self):
        if _pre36:
            layout = self.ax.figure.get_tight_layout() or self.ax.figure.get_constrained_layout()
        else:
            layout = self.ax.figure.get_layout_engine() is not None
        return layout

    def add_key(self, vec_keyspeed, linewidth, refstr, position='below'):
        """
        Add a vector key, positioned 'above' or 'below' (default)
        the topography colorbar.
        """
        ## TODO: add option for position to be a tuple in Axes coordinates,
        # or maybe a string with some more general specification syntax.
        if self._using_layout():
            bottom = self._ticklabel_bottom_axes_units()
            h = 0.2  # A guess...
            xlegend = 1
            ylegend = bottom - h/2 if position == "below" else 1 + h/2
            coordinates = "axes"
            if refstr is not None:
                self.ax.text(xlegend, ylegend - 0.06, refstr,
                                    fontsize=10, ha='center',
                                    transform=self.ax.transAxes)

        else:
            pos = self.bmap.cbar.ax.get_position().bounds
            xlegend = pos[0]  + pos[2]/2

            if position == 'above':
                ylegend = pos[1] + pos[3] + .05
            elif position == 'below':
                ylegend = .5*pos[1]
            else:
                raise ValueError('must choose position "above" or "below"')
            coordinates = 'figure'
            if refstr is not None:
                self.ax.figure.text(xlegend, ylegend-.05, refstr,
                                    fontsize=10, ha='center')

        labelpos = 'N'
        qstr = '%2.1f m/s' % (vec_keyspeed)

        self.ax.quiverkey(self.mquiver, xlegend , ylegend , vec_keyspeed,
                      qstr , color='k',
                      labelpos=labelpos,
                      linewidth=linewidth,
                      coordinates=coordinates)



    @staticmethod
    def get_vecscale(uref, vref):
        '''
        set vector scale; these are m/s
        '''
        spdsq = uref**2 + vref**2
        if len(spdsq) > 10:
            spdsq.sort()
            spdsq = spdsq[:int(0.9*len(spdsq))]
            mag = np.sqrt(spdsq.mean())
        else:
            mag = np.max(spdsq)

        if mag > 1:
            vecscale = 2
            vec_keyspeed = 2
        elif mag > 0.5:
            vecscale = 1
            vec_keyspeed = 1.
        elif mag > 0.25:
            vecscale = 0.6
            vec_keyspeed = 0.5
        else:
            vecscale = 0.4
            vec_keyspeed = 0.2
        return vecscale, vec_keyspeed

    def plot_track(self, x, y, ends=True):
        self.bmap.plot(x, y, 'k', label="_noledgend_")
        if ends:
            self.startmark = self.bmap.plot( x[0], y[0], 'go',
                                            ms=10, mew=1, mec='w',
                                            label="start")
            self.endmark = self.bmap.plot(x[-1], y[-1], 'rX', ms=10, mew=1, mec='w', label="end")
            self.start_end_legend = self.ax.legend(loc='lower left',
                                            facecolor=(1, 1, 1, 0.5),
                                            labelcolor="mfc",
                                            handletextpad=0.2,
                                            )

    @staticmethod
    def scale_temperature(temperature):
        # Ensure the temperature scale spans at least 1 degree.
        cmin, cmax = temperature.min(), temperature.max()
        dc = cmax - cmin
        ac = 0.5 * (cmin + cmax)
        if dc < 1:
            cmin = ac - 0.5
            cmax = ac + 0.5
        return cmin, cmax

    def _ticklabel_bottom_axes_units(self):
        # Find extent in display units of first lon label:
        display_ext = None
        # Ensure the Figure has a renderer.
        self.ax.figure.draw_without_rendering()
        bboxes = [self.ax.get_position().transformed(self.ax.figure.transFigure)]
        for _, textlist in itertools.chain(
            self.bmap.meridians.values(), self.bmap.parallels.values()):
            for t in textlist:
                if t.get_visible():
                    bboxes.append(t.get_window_extent())
        outer_display = Bbox.union(bboxes)
        outer_axes = outer_display.transformed(self.ax.transAxes.inverted())
        return outer_axes.ymin

    def _make_inset_for_temperature(self):
        ticklabel_bottom = self._ticklabel_bottom_axes_units()
        cbar_top = ticklabel_bottom - 0.025
        w, h = 0.7, 0.04
        inset_bounds = (0.5 * (1 - w), cbar_top - h, w, h)
        cax = self.ax.inset_axes(inset_bounds)
        return cax

    def add_cbar(self, **kw):
        if self._using_layout() and "cax" not in kw:
            kw["cax"] = self._make_inset_for_temperature()
        cbar_kw = {}
        if "cax" not in kw:
            make_cax_opts = {'fraction'   : .1,
                            'pad'        : .1,
                            'shrink'     : .7,
                            'aspect'     : 30,
                            'ax': self.ax,
                            }
            cbar_kw.update(make_cax_opts)
        defaults = dict(
            ticks=mpl.ticker.MaxNLocator(nbins=6),
            format=mpl.ticker.ScalarFormatter(useOffset=False),
            )
        if _pre37:
            defaults["orientation"] = "horizontal"
        else:
            defaults["location"] = "bottom"
        cbar_kw.update(defaults)
        cbar_kw.update(kw)

        cbarTemp=self.ax.figure.colorbar(self.mquiver, **cbar_kw)
        cbarTemp.set_label(u'ADCP temperature, \N{DEGREE SIGN}C')
        return cbarTemp


#---------------


def annotate_last_time(fig, dday, yearbase, annotate_str=None, style='subtitle'):
    '''
        annotate axes with timestamp: '%s%s' % (annotate_str, timstring)

        style = 'subtitle' (suitable for annotating vecplot or contour plot)
                'center' (suitable for message in the middle of axes)
    '''
    if style == 'subtitle':
        loc = [.5, .03]
        fontsize=12
        valign='bottom'
    else:
        loc = [.5,.5]
        fontsize=24
        valign='center'
    try:
        y,m,d,hh,mm,ss=to_date(yearbase, dday[-1])
        timestring = ('(dday = %5.3f) %04d/%02d/%02d %02d:%02d:%02d UTC' %  (
            dday[-1], y,m,d,hh,mm,ss))
        if annotate_str is None:
            titletext = timestring
        else:
            titletext = '%s: %s' % (annotate_str, timestring)

        ret = fig.text(loc[0], loc[1], titletext,
                       fontsize=fontsize, weight='bold', ha='center',
                       va=valign)
    except:
        _log.debug('Cannot write subtitle with last time', exc_info=True)
        ret = None
    return ret


def annotate_time_range(fig, dday, yearbase, annotate_str=None, style='subtitle'):
    '''
        annotate axes with timestamp:

                   'time range %5.2f\n%s\n%s' % (duration, startstr, endstr)

        style = 'subtitle' (suitable for annotating vecplot or contour plot)
                'center' (suitable for message in the middle of axes)
    '''
    if style == 'subtitle':
        loc = [.05, .01]
        fontsize=11
        valign='bottom'
    else:
        loc = [.5,.5]
        fontsize=24
        valign='center'
    try:
        y,m,d,hh,mm,ss=to_date(yearbase, dday[-1])
        startstr = ('(dday = %5.3f) %04d/%02d/%02d %02d:%02d:%02d UTC' %  (
            dday[-1], y,m,d,hh,mm,ss))
        y,m,d,hh,mm,ss=to_date(yearbase, dday[0])
        endstr = ('(dday = %5.3f) %04d/%02d/%02d %02d:%02d:%02d UTC' %  (
            dday[0], y,m,d,hh,mm,ss))

        duration = dday[-1]-dday[0]
        titletext = 'time range (%5.2f days)\n%s\n%s' % (
            duration, startstr, endstr)

        ret = fig.text(loc[0], loc[1], titletext,
                       fontsize=fontsize, weight='bold', ha='left',
                       color=annotate_time_color, va=valign)
    except:
        _log.debug('Cannot write subtitle with time range', exc_info=True)
        ret = None
    return ret

#---------------

## used by dataviewer
def vecplot(data,
            ax = None,
            vecscale=None,
            bmap_kw=None, #**kw for mapper
            grid_kw=None, #**kw for mapper.grid()
            topo_kw=None, #**kw for mapper.topo()
            refbins=[1,], #default is 0:dz:end, taking averaged bin 1
            startz = None,
            zoffset=0,
            deltat=.02, deltaz=10, offset=0): #offset is 1/2 bin

    gdata = timegrid_cdb(data,  deltat=deltat, startz=startz, deltaz=deltaz)

    if len(refbins) == 1:
        # repeat it so Stats will work
        refbins = [refbins, refbins]
    refbins = np.array(refbins)

    # make sure refbins is an array, with >= 2 elements, and not too long.
    nprofs, nbins = gdata['u'].shape
    okref = np.where(refbins < nbins)[0]
    refbins = refbins[okref]
    if len(okref) == 0:
        utmp = 0.0*gdata['dday']
        vtmp = 0.0*gdata['dday']
        ref_zrangestr = "no good velocities"
    else:
        ustats = Stats(gdata['u'][:,refbins], axis=1)
        vstats = Stats(gdata['v'][:,refbins], axis=1)
        utmp = ustats.mean
        vtmp = vstats.mean
        ref_zrangestr = '%d to %d m' % (
            np.fix(gdata['dep'][refbins[0].item()]-offset),
            np.fix(gdata['dep'][refbins[-1].item()]+deltaz-offset)
        )

    # assuming lon, lat have the same mask, but fewer masked
    posmask = np.ma.getmaskarray(gdata['lon'])
    if np.all(posmask):
        raise ValueError('no good positions')

    londat = gdata['lon'].compressed()
    latdat = gdata['lat'].compressed()

    uref = utmp.compress(~posmask)
    vref = vtmp.compress(~posmask)

    vmap = Vecmap(londat, latdat, uref, vref,
                  refstr = ref_zrangestr,
                  zoffset = zoffset,
                  temperature=gdata['tr_temp'].compress(~posmask),
                  vecscale=vecscale,
                  bmap_kw = bmap_kw,
                  grid_kw = grid_kw,
                  topo_kw = topo_kw,
                  ax=ax)

    return vmap

# --- do not delete: used by process_tarball.py for shoreside vector plots
def simple_vecplot(data, ax = None, bin=None, zoffset=0):
    '''
    plot the top bin
    '''
    ndep=len(data['dep'])

    if ndep > 1:
        dz = data['dep'][1]-data['dep'][0]
    else:
        dz = 0

    #try to get away from the surface
    if ndep==1:
        bin=0
    else:
        bin=1


    if dz == 0:
        midz =  np.fix(data['dep'][bin])
        refstr = '%d m' % (midz)
    else:
        refstr = '%dm to %dm' % (np.floor(data['dep'][bin])-dz/2.,
                                 np.ceil(data['dep'][bin])+dz/2.)

    # assuming lon, lat have the same mask, but fewer masked
    posmask = np.ma.getmaskarray(data['lon'])
    if np.all(posmask):
        raise ValueError('no good positions')

    londat = data['lon'].compressed()
    latdat = data['lat'].compressed()

    try:
        uref = data['u'][:,bin].compress(~posmask)
        vref = data['v'][:,bin].compress(~posmask)
    except IndexError:
        uref = np.ma.masked_all_like(londat)
        vref = np.ma.masked_all_like(londat)

    # use the new 'auto' setting for topo depths
    vmap = Vecmap(londat, latdat, uref, vref,
                  refstr = refstr,
                  zoffset=zoffset,
                  topo_kw = {'levels':'auto',},
                  temperature=data['tr_temp'].compress(~posmask),
                  ax=ax)
    return vmap


#----------------------------------

class PlotDefaults:
    vardat = [
        [   'pg', 'PERCENT GOOD',         (0,100)    ,'pg3080',   'percent'],
        [  'amp', 'AMPLITUDE',            (10,230)   ,'jet',      'units'],
        [  'amp1', 'Beam 1 AMP',          (10,230)   ,'jet',      'units'],
        [   'sw', 'SPECTRAL WIDTH',       (30,260)   ,'jet',      'units'],
        ['umeas', 'MEASURED U',           (None,None),'ob_vel',   'm/s'],
        ['vmeas', 'MEASURED V',           (None,None),'ob_vel',   'm/s'],
        [    'w', 'W',                    (None,None),'ob_vel',   'm/s'],
        [    'e', 'ERROR VELOCITY',       (-70,70)   ,'ob_vel',   'm/s'],
        [    'u', 'Ocean U',              (-60,60)   ,'ob_vel',   'm/s'],
        [    'v', 'Ocean V',              (-60,60)   ,'ob_vel',   'm/s'],
        [   'uv', 'Ocean velocity',       (-60,60)   ,'ob_vel',   'm/s'],
        [  'fwd', 'Ocean velocity (fwd)', (-60,60)   ,'ob_vel',   'm/s'],
        [ 'port', 'Ocean velocity (port)',(-60,60)   ,'ob_vel',   'm/s'],
        ]
    vardict = dict([(vd[0], vd[1:]) for vd in vardat])
    def __init__(self, var):
        try:
            vars = self.vardict[var]
            self.label, self.lims, self.cmapname, self.units = vars
            if var in ['pg', 'amp', 'amp1', 'sw', 'umeas', 'vmeas']:
                self.symmetric = False
            else:
                self.symmetric = True
        except KeyError:
            self.label = 'data'
            self.lims = 'auto'
            self.cmapname = 'ob_vel',
            self.units = 'units'
            self.symmetric = False




class ADataPlotter:
    """
    Shipboard ADCP color contour plotter.

    This started out as a Swiss Army Knife, but functionality
    has been broken out so that now only the U,V contour plotting
    function remains.

    Methods:

        =============   =======================
        cuvplot         u+v color contour plot
        save            write to disk
        get_cinfo       clip and color ranges
        =============   =======================


    """
    def __init__(self,  data,
                 x = None, y = None,
                 xname = None, yname = None, zname = None,
                 units = None, yearbase = None,
                 cmapname = None, #useless; fix this when reworking.
                 xlim = None, ylim = None, zlim = None):
        """
        usage::

            AP = ADataPlotter(data ,
                 x = None,         # abcissa  (name or array)
                 y = None,         # ordinate (name or array)
                 xname = None,     # name for abcissa, if passing in data
                 yname = None,     # name for ordinate if passing in data
                 zname = None,     # key for data dictionary  (if relevant)
                 units = None      # units for colorbar
                 xlim = None,      # abcissa range
                 ylim = None,      # ordinate range
                 zlim = None)      # variable range
                                     None: use preset defaults if data was dict
                                           autoscale if data was an array

        """

        self.xlim = xlim
        self.ylim = ylim

        self.zlim = zlim
        if zname is None:
            zname = 'uv'
        self.zname = zname

        data = data.copy() # to avoid side effects
        # define, and later plot, with self.data or self.datadict
        # figure out data
        if hasattr(data, 'keys'):
            if yearbase is not None:
                _log.debug("yearbase kwarg is being ignored; "
                          + "yearbase must be provided in the data dictionary")
            self.yearbase = data['yearbase']
            #log.debug('data comes in from dictionary')
            try:
                self.data = data[zname]
            except KeyError:
                if zname == 'uv':
                    data['uv'] = data['u'] + 1j*data['v']
                    self.data = data['uv']
                elif zname in data:
                    self.data = data[zname]
                else:
                    self.data = None
                    self.zname = None
            self.datadict = data
        else:
            if yearbase is None:
                raise ValueError("If data is not a dictionary, yearbase "
                                 + "must be specified as a kwarg")
            self.data = data
            self.yearbase = yearbase

        # now working with self.data: if bad, replace with None
        if self.data is not None:
            self.data = ma.asarray(self.data)
            if self.data.ndim != 2:
                raise ValueError("self.data must be 2-D but ndim=%d",
                                    self.data.ndim)
            self.nprofs, self.nbins = self.data.shape
            if self.data.size==0:
                _log.debug("No data; nbins=%d, nprofs=%d",
                                self.nbins, self.nprofs)
                self.data = None


        if self.data is not None:
            # figure out abcissa
            if hasattr(data, 'keys') and isinstance(x, str):
                self.x = data[x]
                self.xname = x
            elif x is not None:
                self.x = x
                self.xname = xname
            else:
                self.x = np.arange(self.nprofs)
                self.xname = 'index'

            # figure out ordinate
            if hasattr(data, 'keys') and isinstance(y, str):
                self.y = data[y]
                self.yname = y
            elif y is not None:
                self.y = y
                self.yname = yname
            else:
                self.y = np.arange(self.nbins)
                self.yname = 'bins'
            # set up colors, cmap, levels, etc (for plotting)
            self.get_cinfo(cmapname = cmapname)

    # ----------

    def save(self, outfilebase, dpi=70, fig=None):
        '''
        Save active figure to disk.

        If outfilebase and dpi are iterable, iterate.
        '''
        if not fig:
            fig = plt.gcf()
        try:
            for name, dpii in zip(outfilebase, dpi):
                fig.savefig(name, dpi=dpii) # dpi has to be a kwarg
        except TypeError:
            fig.savefig(outfilebase, dpi=dpi)


    ## --------  get color info,  clips and levels -------------
    def get_cinfo(self, cmapname = None):
        ''' figure out xlim, ylim, zlim, cmap, zlabel, color levels
        '''

        if self.xlim is None:
            self.xlim= (self.x[0], self.x[-1])
        xlim_pad=1e-6
        if np.diff(self.xlim) == 0:
            self.xlim=[self.xlim[0]-xlim_pad, self.xlim[1]+xlim_pad]

        if self.ylim is None:
            self.ylim= (np.max(self.y), np.min(self.y))

        defaults = PlotDefaults(self.zname)
        self.zlabel = defaults.label
        if cmapname is None:
            self.cmapname = defaults.cmapname
        else:
            self.cmapname = cmapname
        self.units = defaults.units
        self.symmetric = defaults.symmetric

        # try to get color limits
        if self.zlim is None:    # not set
            self.zlim = defaults.lims
        if self.zlim == 'auto':
            self.zlim = (self.data.min(), self.data.max())

        loc = mpl.ticker.MaxNLocator(nbins=15, symmetric=self.symmetric)
        self.contourf_levels = loc.tick_values(*self.zlim)[1:-1]


    def _nodata(self, ax):
        # This can be enhanced as needed: bigger font,
        # suppress axis ticks, etc.
        ax.text(0.5, 0.5,'%s: Insufficient Data' % (self.zname),
                 horizontalalignment='center',
                 verticalalignment='center',
                 transform = ax.transAxes)
        plt.draw_if_interactive()


    ## -----------  contourf for u,v specifically  ------------------

    ## used by at-sea processing: data from timegrid_cdb(get_profiles(dbname))
    ## used by shoreside plotting of txyzbin (pre-gridded)
    def cuvplot(self, title_base = None, figsize=None,
                suptitle=None,
                maxvel=None, nxticks = 5,
                major_minor = None,
                xout=None, yout=None,
                y_weight = 1, biharmonic = 1, interp = 2,
                fill_color = None,
                add_amp=False, aclim = [20,200]):
        ''' contour u and v together, presently as a function of dday
            same time axis for both plots; same velocity scale
        '''

        if major_minor is not None:
            major_locator   = mpl.ticker.MultipleLocator(major_minor[0])
        else:
            major_locator = mpl.ticker.MaxNLocator(nbins=nxticks)


        if figsize is None:
            if add_amp:
                figsize = (7.5,9.5)
            else:
                figsize = (7.5,8.5)

        # background color for masked data
        if fill_color is None:
            fill_color = [.85,.85,.85]  # explicitly set to light gray

        # if using datadict['uv'] or data, how to we get masked
        # but truly real values back (now using datadict['u']
        # to get around that obstacle)

        self.cuv_fig = plt.figure(figsize=figsize)
        self.cuv_fig.subplots_adjust(left=0.15, right=0.97,
                                        hspace=0.11, bottom=0.14)
        if suptitle is None:
            self.cuv_fig.subplots_adjust(top=0.95)

        if add_amp is False:
            ax1 = self.cuv_fig.add_subplot(211)
            ax2 = self.cuv_fig.add_subplot(212)#, sharex=ax1)  ## broken
        else:
            ax1 = self.cuv_fig.add_subplot(311)
            ax2 = self.cuv_fig.add_subplot(312)#, sharex=ax1)  ## broken
            ax3 = self.cuv_fig.add_subplot(313)#, sharex=ax1)  ## broken
            self.cuv_ax3 = ax3

        if self.data is None:
            self._nodata(ax1)
            self._nodata(ax2)
            return

        if self.xname == 'lat':
            ax1.xaxis.set_major_formatter(LatFormatter())
            ax2.xaxis.set_major_formatter(LatFormatter())
        elif self.xname == 'lon':
            ax1.xaxis.set_major_formatter(LonFormatter())
            ax2.xaxis.set_major_formatter(LonFormatter())
        else:
            ax1.xaxis.set_major_formatter(
                    mpl.ticker.ScalarFormatter(useOffset = False))
            ax2.xaxis.set_major_formatter(
                    mpl.ticker.ScalarFormatter(useOffset = False))

        ax1.xaxis.set_major_locator(major_locator)
        ax2.xaxis.set_major_locator(major_locator)

        if xout is not None and yout is not None:
            # try to regrid
            ugrid = grid.regrid(self.x, self.y, self.datadict['u'].T, xout, yout,
                  y_weight=y_weight, biharmonic=biharmonic, interp=interp)
            vgrid = grid.regrid(self.x, self.y, self.datadict['v'].T, xout, yout,
                  y_weight=y_weight, biharmonic=biharmonic, interp=interp)
            if add_amp:
                agrid = grid.regrid(self.x, self.y, self.datadict['amp'].T, xout, yout)
        else:
            ugrid = self.datadict['u'].T
            vgrid = self.datadict['v'].T
            if add_amp:
                agrid = self.datadict['amp'].T
            xout = self.x
            yout = self.y


        # make it all zeros
        if ugrid.count() < 4 or vgrid.count() < 4:
            ugrid = ma.zeros(ugrid.shape)
            vgrid = ma.zeros(vgrid.shape)
            if add_amp:
                agrid = ma.zeros(agrid.shape)

        # ideally, autoscale based on a histogram, picking the
        # 90th or 95th percentile; here we use max as a quick
        # substitute.

        if maxvel is None: #autoscale
            try:
                absvels = np.ravel( [np.abs(ugrid.compressed()),
                                np.abs(vgrid.compressed())] )
                if len(absvels) > 20:
                    ind = int(np.round(len(absvels) * 0.95))
                    maxval = 1.2 * np.sort(absvels)[ind]
                else:
                    maxval = max(ma.abs(ugrid).max().filled(0),
                             ma.abs(vgrid).max().filled(0))
            except (AttributeError, ValueError):
                # ValueError is raised if ugrid.compressed and vgrid.compressed
                # are different sizes--which they should not be, but
                # evidently can, as inferred from Melville tracebacks.
                maxval = max(np.abs(ugrid).max(), np.abs(vgrid).max())
        else:
            maxval = maxvel


        if maxval < 0.25:
            levs = np.linspace(-20, 20, 9)
        elif maxval < 0.5:
            levs = np.linspace(-40, 40, 9)
        elif maxval < 1.0:
            levs = np.linspace(-80, 80, 9)
        elif maxval < 1.8:
            levs = np.linspace(-160, 160, 9)
        else:
            levs = np.linspace(-240, 240, 9)

        # swtiching to m/s
        levs = levs/100.


        # contour u
        ax1.patch.set_color(fill_color) # set background color for masked data

        if len(xout) < 2:
            self._nodata(ax1)
            self._nodata(ax2)
            return

        pp1 = ax1.contourf(xout, yout, ugrid,
                        levs,
                        extend='both',
                        cmap = get_extcmap(name=self.cmapname))

        #ax1.contour(xout, yout, ugrid, [0,], colors='k')
        ax1.set_ylabel(self.yname)
        ax1.set_ylim(self.ylim)

        ax1.set_title('Ocean U (east)')
        plt.setp(ax1.get_xticklabels(), visible=False)

        cbar1 = self.cuv_fig.colorbar(pp1, ax=ax1, shrink=0.8)
        cbar1.set_label(self.units)

        # contour v
        ax2.patch.set_color(fill_color)
        pp2 = ax2.contourf(xout, yout, vgrid,
                        levs,
                        extend='both',
                        cmap = get_extcmap(name=self.cmapname))

        if add_amp:
            self.add_cuvamp(xout, yout, agrid, major_minor=major_minor,
                            nxticks=nxticks, aclim=aclim)

        #ax2.contour(xout, yout, vgrid, [0,], colors='k')
        ax2.set_ylabel(self.yname)
        ax2.set_ylim(self.ylim)
        ax2.set_title('Ocean V (north)')

        cbar2 = self.cuv_fig.colorbar(pp2, ax=ax2, shrink=0.8)
        cbar2.set_label(self.units)

        ## finish it off
        ax1.set_xlim(self.xlim)
        ax2.set_xlim(self.xlim)
        ax1.set_ylabel('depth')
        ax2.set_ylabel('depth')

        if add_amp:
            plt.setp(ax1.get_xticklabels(), visible=False)
            plt.setp(ax2.get_xticklabels(), visible=False)
            if self.xname not in ['lat', 'lon']:
                ax3.set_xlabel(self.xname)
        else:
            ax2.set_xlabel(self.xname)

        if suptitle is not None:
            self.cuv_fig.text(0.5, 0.95, suptitle, fontsize=14,
                              weight='bold', ha='center')

        plt.draw_if_interactive()

        self.cuv_ax1 = ax1
        self.cuv_ax2 = ax2
        self.cuv_pp1 = pp1
        self.cuv_pp2 = pp2
        self.cuv_cbar1 = cbar1
        self.cuv_cbar2 = cbar2

    #-----------

    def add_cuvamp(self, xout, yout, agrid,
                   major_minor = None,
                   nxticks=5,
                   aclim=[20,200]):

        if major_minor is not None:
            major_locator   = mpl.ticker.MultipleLocator(major_minor[0])
        else:
            major_locator = mpl.ticker.MaxNLocator(nbins=nxticks)

        ax3 = self.cuv_ax3

        if self.data is None:
            self._nodata(ax3)
            return

        if self.xname == 'lat':
            ax3.xaxis.set_major_formatter(LatFormatter())
        elif self.xname == 'lon':
            ax3.xaxis.set_major_formatter(LonFormatter())
        else:
            ax3.xaxis.set_major_formatter(
                    mpl.ticker.ScalarFormatter(useOffset = False))

        ax3.xaxis.set_major_locator(major_locator)

        ## used by run_3dayplots and process_tarball (OK)
        ## KLOOJ:  used by quick_web (fail)

        try:
            p = ax3.pcolorfast(xout, yout, agrid, cmap='jet',
                           vmin=aclim[0], vmax=aclim[1])
        except:
            p = ax3.pcolorfast(xout, yout, agrid[:-1,:-1], cmap='jet',
                           vmin=aclim[0], vmax=aclim[1])
            _log.warning("plot_cuvamp: trimming one row and one col from AMP")


        cbarloc = mpl.ticker.MaxNLocator(nbins=6, steps=[1, 2, 4, 5, 10])
        cbar3 = self.cuv_fig.colorbar(p, ax=ax3, extend='both', ticks=cbarloc)
        cbar3.ax.set_ylabel('RSSI counts', fontsize='10', style='normal', color='k')
        cbar3.ax.yaxis.set_label_position('right')

        ax3.set_ylabel(self.yname)
        ax3.set_ylim(self.ylim)

        ax3.set_title('Signal Strength RSSI)')

        ax3.set_xlim(self.xlim)
        if self.xname not in ['lat', 'lon']:
            ax3.set_xlabel(self.xname)

        self.cuv_cbar3 = cbar3

    #-----------
