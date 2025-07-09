"""
Functions and classes for working with maps, typically using mpl basemap.

- :func:`mapper`
- :class:`Mercator`
- :func:`mercator`
- :class:`Conic`
- :func:`conic`
- :func:`map_range`
- :class:`LonFormatter`
- :class:`LatFormatter`
- :func:`llticks`

"""
import hashlib
import os.path
import pickle
import warnings

import numpy as np
import numpy.ma as ma

import matplotlib.ticker as ticker
import matplotlib.cbook as cbook
import matplotlib as mpl

from pycurrents.data.topo import best_topo

from pycurrents.plot.mpltools import get_extcmap
from pycurrents.plot.mpltools import draw_if_interactive
from pycurrents.plot.mpltools import sca_if_interactive

_pre38 = mpl.__version_info__ < (3, 8)
_pre37 = mpl.__version_info__ < (3, 7)
_pre36 = mpl.__version_info__ < (3, 6)

try:
    from mpl_toolkits.basemap import Basemap, pyproj
except ImportError:
    warnings.warn("You need to install the mpl_toolkits.basemap package. \n"
                  "Until you do, "
                  "any code that uses it will raise an exception.")

    def _explain(self, name):
        raise Exception(
            "%s doesn't exist; you don't have basemap installed." % name)

    class Basemap:
        def __getattribute__(self, attr):
            _explain(self, "Basemap")

    class _pyproj:
        def __getattribute__(self, attr):
            _explain(self, "pyproj")

    pyproj = _pyproj()    # Fake module.




topocmap = get_extcmap('topo')


class RevScalarFormatter(ticker.Formatter):
    ''' Colorbar tick formatter for removing minus sign from depths.
    '''
    def __init__(self, divide_by=1):
        self.divide_by = float(divide_by)

    def __call__(self, x, pos=None):
        x = -x / self.divide_by
        if abs(x - int(x)) < 0.001:
            return "%d" % int(x)
        return "%s" % x


#-------------

def map_range(x, y, aspect=2, stretch=1.3, smallest=0.5,
                lat_limit=80, round_to=0):
    '''
    lonrange, latrange = map_range(x, y, ...)

    Calculate a bounding box in which to map a set of points.

        arguments:
            x, y: sequences of longitudes and latitudes (not masked)
                    to be mapped, or lower-left and upper-right corners
        kwargs:
            aspect:    2      maximum aspect ratio.
            stretch:   1.3    factor by which box extends beyond the data
            smallest:  0.5    minimum length (degrees lat) of a box side.
            lat_limit: 80     max north or south lat of box boundary
            round_to:  0      Round boundaries to multiple of this.
                                  0 means no rounding.
                                  With basemap, this is mainly
                                  useful with a Mercator projection

        returns:
            lonrange, latrange: ndarrays

     Matlab version, utils/map_range.m, EF 2001/08/09
     '''

    x = ma.masked_invalid(x)
    y = ma.masked_invalid(y)

    lonrange0 = np.array([x.min(), x.max()])
    latrange0 = np.array([y.min(), y.max()])
    ymid = latrange0.mean()
    xmid = lonrange0.mean()
    xsc = np.cos(ymid * np.pi/180)
    h = np.diff(latrange0)
    w = np.diff(lonrange0)*xsc
    s = max([h, w, (smallest * aspect / stretch)])
    h = max([h, s/aspect]) * stretch
    w = max([w, s/aspect]) * stretch

    lonrange = xmid + 0.5 * np.array([-w, w]) / xsc
    latrange = ymid + 0.5 * np.array([-h, h])
    latrange.clip(min=-lat_limit, max=lat_limit, out=latrange)

    if round_to > 0:
        latrange = (latrange / round_to).round() * round_to
        lonrange = (lonrange / round_to).round() * round_to
        # Make sure the data are still inside the box.
        if lonrange[0] > lonrange0[0] - 0.2*round_to:
            lonrange[0] -= round_to
        if lonrange[1] < lonrange0[1] + 0.2*round_to:
            lonrange[1] += round_to
        if latrange[0] > latrange0[0] - 0.2*round_to:
            latrange[0] -= round_to
        if latrange[1] < latrange0[1] + 0.2*round_to:
            latrange[1] += round_to
    return lonrange.ravel(), latrange.ravel()

def mapper(lons, lats, projection=None, **kw):
    """
    Return a :class:`Mercator`, :class:`Conic`,
    or :class:`Polar` Basemap subclass instance.

    *lons*, *lats*: matching sequences of at least two values.

    *projection*: 'mercator', 'conic', 'polar', or None (default)

    If *projection* is None, a suitable projection will be
    chosen based on the region in which *lons*, *lats* occur.
    Low latitudes are mapped in Mercator, mid
    and high latitudes usually in Conic.  High latitude data
    with a large range of longitudes, however, are mapped with
    a polar projection.

    For explanations of other kwargs, see :class:`Mapbase`.

    """
    kw.setdefault('cache', False)
    lons = np.ma.masked_invalid(lons).compressed()
    lats = np.ma.masked_invalid(lats).compressed()
    if projection is not None:
        klass = dict(mercator=Mercator, polar=Polar, conic=Conic)[projection]
    else:
        klass = Conic
        latmin = lats.min()
        latmax = lats.max()
        latmid = abs(0.5 * (latmin + latmax))
        if (latmin <= 0 and latmax >= 0) or latmid < 15:
            klass = Mercator
        if latmid > 50:
            hlons = lons % 360
            h, b = np.histogram(hlons, bins=np.arange(0, 360.1, 30))
            h = h > 0
            if h.sum() > 6 or (h[:6] & h[6:]).any():
                klass = Polar
    return _cached_map(klass, lons, lats, **kw)

def _cached_map(klass, lons, lats, cache=None, ax=None, **kw):
    if cache:
        basekw, kwdict = klass.process_params(lons, lats, **kw)
        basekwbytes = str(basekw).encode('ascii')
        basehash = hashlib.sha1(basekwbytes).hexdigest()[:6]
        cachefname = os.path.join(cache, "map_%s.cache" % basehash)
        try:
            m = pickle.load(open(cachefname, 'rb'))
        except (IOError, EOFError):
            m = klass(lons, lats, **kw)
            m.cachefname = cachefname
            try:
                pickle.dump(m, open(cachefname, 'wb'), -1)
            except (IOError, pickle.PicklingError):
                # PicklingError is raised when using "run" in ipython.
                warnings.warn("Cannot write cache %s; ipython oddity?"
                                  % cachefname)
                pass
    else:
        m = klass(lons, lats, **kw)
    m.ax = ax
    return m

def conic(lons, lats, **kw):
    """
    Shortcut to mapper(lons, lats, projection='conic', **kw)
    """
    return _cached_map(Conic, lons, lats, **kw)

def mercator(lons, lats, **kw):
    """
    Shortcut to mapper(lons, lats, projection='mercator', **kw)
    """
    return _cached_map(Mercator, lons, lats, **kw)

def polar(lons, lats, **kw):
    """
    Shortcut to mapper(lons, lats, projection='polar', **kw),
    but with special treatment of *lons*, *lats*.

    *lons*, *lats* can be single-element sequences or scalars
    giving the central (6-o'clock) longitude and the bounding
    latitude.
    """
    if not np.iterable(lons):
        lons = [lons]
    if not np.iterable(lats):
        lats = [lats]
    lons = np.ma.masked_invalid(lons).compressed()
    lats = np.ma.masked_invalid(lats).compressed()
    return _cached_map(Polar, lons, lats, **kw)



def _set_res(resolution, width, height):
    if isinstance(resolution, str) and resolution == 'auto':
        d = (width + height) / 1000 # to kilometers

        if d < 400:
            resolution = 'h'  # 0.2 km (full is 0.04 km)
        elif d < 2000:
            resolution = 'i'   # 1 km
        elif d < 10000:
            resolution = 'l'   # 5 km
        else:
            resolution = 'c'   # 25 km

    return resolution

def _set_round(round_to, dlon, dlat):
    if round_to is None:
        dd = max(dlon, dlat)
        if dd > 50:
            round_to = 5
        elif dd > 10:
            round_to = 1
        elif dd > 5:
            round_to = 0.5
        else:
            round_to = 0.1
    return round_to


class Mapbase(Basemap):
    """
    Base class for convenience subclasses of Basemap.

    Must be subclassed; each subclass is specialized
    for a single projection.

    See :class:`Mercator` and :class:`Conic` and their
    respective factory functions, :func:`mercator` and
    :func:`conic`

    """
    def __init__(self, lons, lats,
                    resolution=None,
                    zoffset=0,
                    cache=None,
                    round_to=None,
                    min_size=None,
                    pad=None,
                    aspect=None,
                    **kw):
        """
        *lons*, *lats*:
            matching sequences specifying at least two points
            (lower left, upper right); but they can also give
            a cruise track, for example, to be included in the
            map.

        *resolution*:
            Basemap parameter: boundary resolution, one of
            'c', 'l', 'i', 'h', 'f', 'auto', or None (default)

        *zoffset*:
            integer positive altitude in meters: set the topo origin here
            (e.g., 183 for Lake Superior)

        *cache*: string or None (default); if not None, it
            must be a valid directory for topography and/or
            boundary cache files.  Topography caching is
            implemented in this class; caching of the
            Basemap subclass instance is implemented in
            the factory functions that are normally used
            to instantiate subclasses of this class.

        *round_to*:
            approximate level of parameter rounding in
            nominal degrees

        *min_size*:
            approximate minimum dimensions in nominal degrees

        *pad*:
            width, height will be expanded from their minimum
            values by (1 + pad)

        *aspect*:
            single float, or a sequence of two floats giving minimum
            and maximum aspect ratio of map.

        Remaining kw are passed to Basemap.

        This is a base class that must be subclassed.

        """
        self.cache = cache
        self.round_to = round_to
        self.min_size = min_size
        self.pad = pad
        self.aspect = aspect
        self.zoffset = int(zoffset)

        # We have to pass everything in to process_params because
        # it needs to be a static method, so it can be called
        # from outside, for caching.
        basekw, kwdict = self.process_params(lons, lats,
                                     resolution=resolution,
                                     round_to=round_to,
                                     min_size=min_size,
                                     pad=pad,
                                     aspect=aspect,
                                     **kw)
        Basemap.__init__(self, **kwdict)
        self.basekw = basekw        # hashable: key for cache
        self.kwdict = kwdict
        self.meridians = None
        self.parallels = None
        self._find_gridlims()
        self.cachefname = None      # slot to be filled by caching function
        self.cbar = None
        self.cax = None
        self.contour_set = None
        self.contourf_set = None
        self.continents = None

    def _find_gridlims(self):
        """
        Calculate self.alonrange, self.alatrange, which define
        the boundaries of the block that must be extracted from
        the topography database.
        """
        raise NotImplementedError("subclass must implement this")


    @staticmethod
    def process_params(lons, lats,
                       resolution=None,
                       round_to=None,
                       min_size=None,
                       pad=None,
                       aspect=None,
                       **kw):
        """
        Return the basekw and kwdict.
        """
        raise NotImplementedError("subclass must implement this")

    def ungrid(self, ax=None):
        if self.meridians is not None:
            if ax is None:
                ax = self._check_ax()
            valgen = cbook.flatten(list(self.meridians.values()) +
                                        list(self.parallels.values()))
            for val in valgen:
                val.remove()
            self.meridians = None
            self.parallels = None

    def grid(self, nx=6, ny=6,
                    xlocs=None, ylocs=None,
                    xlabels=None, ylabels=None,
                    centered=False,
                    alpha=None,
                    **kw):
        """
        Add lon-lat grid.

        If called more than once, this will replace the previous
        grid with the new one.

        *xlabels* and *ylabels* are the Basemap *labels* kw for
        the drawmeridians and drawparallels methods, defaulting
        to [0, 0, 0, 1] and [1, 0, 0, 0].

        Additional keyword arguments (e.g., dashes and linewidth)
        are passed on to the Basemap drawmeridians and drawparallels
        methods.

        """
        self.ungrid(ax=kw.get('ax', None))

        if alpha is None:
            alpha = 0.3

        if centered:
            x0 = self.loncen
            if x0 < self.lonmin:
                x0 += 360
            elif x0 > self.lonmax:
                x0 -= 360
            y0 = self.latcen
        else:
            x0 = 0
            y0 = 0

        proj = self.kwdict['projection']

        if xlocs is None:
            xloc = ticker.MaxNLocator(nbins=nx, symmetric=centered)
            xloc.create_dummy_axis()
            bounds = (self.lonmin-x0, self.lonmax-x0)
            xloc.axis.set_data_interval(*bounds)
            xloc.axis.set_view_interval(*bounds)
            xlocs = xloc() + x0
            if proj[1:] == 'plaea':
                xlocs = xlocs[:-1]

        if ylocs is None:
            yloc = ticker.MaxNLocator(nbins=ny, symmetric=centered)
            yloc.create_dummy_axis()
            bounds = (self.latmin-y0, self.latmax-y0)
            yloc.axis.set_data_interval(*bounds)
            yloc.axis.set_view_interval(*bounds)
            ylocs = yloc() + y0

        dlat = abs(self.latmax - self.latmin)

        # Set max latitude for drawing meridians.
        latmax =  max(abs(self.latmax), abs(self.latmin))
        if proj in ['lcc', 'nplaea', 'splaea']:
            if abs(self.latmax) > abs(self.latmin):
                # northern hemisphere
                ii = np.searchsorted((ylocs - self.latmin)/dlat, 0.85) -1
            else:
                ii = np.searchsorted((ylocs - self.latmax)/dlat, -0.85)

            if proj[1:] == 'plaea' or latmax >= 80:
                latmax = abs(ylocs[ii])

        kw.setdefault('latmax', latmax)

        kw.setdefault('dashes', [])
        kw.setdefault('linewidth', 0.8)
        # Basemap uses defaults of 'k'; override that so that styles will work.
        kw.setdefault('color', mpl.rcParams['grid.color'])
        kw.setdefault('textcolor', mpl.rcParams['text.color'])
        if xlabels is None:
            xlabels = [0,0,0,1] # For most cases, label the bottom.
            if proj == 'lcc':
                ullon, ullat = self(self.xmin, self.ymax, inverse=True)
                lrlon, lrlat = self(self.xmax, self.ymin, inverse=True)
                dlontop = (self.urcrnrlon - ullon) % 360
                dlonbot = (lrlon - self.llcrnrlon) % 360
                # We tried adding high-latitude labels on the right (second
                # element in the list) but this interferes with the topo
                # colorbar and doesn't usually look good anyway.
                if self.latmax < -20 and dlonbot/dlontop > 1.5:
                    xlabels = [0,0,1,0] # SH high lats, label top
                if self.latmin > 20 and dlontop/dlonbot > 1.5:
                    xlabels = [0,0,0,1] # NH high lats, label bottom
            elif proj[1:] == 'plaea':
                xlabels = [0,1,0,1]  # right and bottom
        kw['labels'] = xlabels


        meridians = self.drawmeridians(xlocs,  **kw)
        if ylabels is None:
            ylabels = [1,0,0,0]
        kw['labels'] = ylabels
        parallels = self.drawparallels(ylocs,  **kw)

        # Save toplabels state in case we need to use it to
        # reposition the axes and title.
        self.toplabels = xlabels[2] or ylabels[2]

        for obj in cbook.flatten(list(meridians.values()) + list(parallels.values())):
            if isinstance(obj, mpl.lines.Line2D):
                obj.set_alpha(alpha)
        draw_if_interactive() # Ensure drawing after setting alpha.
        self.meridians = meridians
        self.parallels = parallels

    def get_levels(self, levs, z):
        levels = np.array([-5000, -4000, -3000, -2000, -1000, -500, 0])
        slevels = np.arange(-500,50,50)

        if levs is None:
            return levels
        if isinstance(levs, str) and levs == "auto":
            zs = np.ma.masked_greater(z, 0).compressed()
            zs.sort()
            z90 = zs[int(0.1 * len(zs))]

            if z90 < -3000:
                return levels
            if z90 < -1500:
                return levels / 2
            if z90 < -1000:
                return slevels * 3
            if z90 < -500:
                return slevels * 2
            if z90 < -400:
                return slevels
            if z90 < -200:
                return slevels / 2
            if z90 < -100:
                return slevels / 2.5
            return slevels / 5
        return levs

    def topo(self, levels=None, linelevels=None,
             proportional=True,
             coast=True,
             nsub=None,
             reset_source=False,
             xyz=None,
             cax=None,
             location=None,
            ):
        """
        Add topography with filled and/or line contours.

        If called more than once, this will replace the previous
        contours with the new ones, and redraw the colorbar.

        *levels* can be *None* for a standard range, or "auto"
        for one of 6 standard ranges depending on the distribution
        of depths, or it can be a sequence of (negative) depths in
        meters, starting from the deepest.

        If *xyz* is not *None*, it must be *x*, *y*, and *z* such
        as would be returned by best_topo().

        *cax* can be *None*, 'inset', or an existing Axes instance.  If
        it is 'inset', an inset axes will be added on the right instead
        of stealing space from the parent Axes.  This works well only
        when a layout engine is in use.

        """
        self.ax = self._check_ax()  # inherited from Basemap

        if cax is None and location not in (None, "right"):
            raise ValueError(
                "location must be None or 'right' if cax is not specified."
                )
        if isinstance(cax, str) and cax == "inset":
            if location not in (None, "right"):
                raise ValueError(
                    "location must be None or 'right' if cax is 'inset'."
                    )
            if _pre36:
                layout = self.ax.figure.get_tight_layout() or self.ax.figure.get_constrained_layout()
            else:
                layout = self.ax.figure.get_layout_engine() is not None
            if layout:
                # Make a default inset axes.
                cax = self.ax.inset_axes((1.02, 0.1, 0.03, 0.8))
            else:
                cax = None
                warnings.warn("No layout engine is in use; cannot use 'inset' cax.")
        self.untopo()

        if xyz is None:
            x, y, z = best_topo(self.alonrange, self.alatrange,
                                nsub=nsub, cache=self.cache,
                                reset_source=reset_source)
            z -= self.zoffset  # usually zero
        else:
            x, y, z = xyz

        X, Y = np.meshgrid(x, y)
        XX, YY = self(X, Y)

        outside = (XX > self.xmax)
        outside |= (XX < self.xmin)
        outside |= (YY > self.ymax)
        outside |= (YY < self.ymin)
        zz = np.ma.array(z, mask=outside)

        levels = self.get_levels(levels, zz)

        self.XX, self.YY, self.zz = XX, YY, zz

        if self.resolution is None:
            coast = False
        extend = 'both'

        if proportional:
            self.contourf_set = self.contourf(XX, YY, z,
                            levels=levels, extend=extend,
                            cmap = topocmap)
        else:
            self.contourf_set = self.contourf(XX, YY, z,
                            levels=levels, extend=extend,
                            colors = topocmap(np.linspace(0, 1, len(levels)+1)))
        # Default: if the shallowest level is the seashore, use the over-range
        # color from the colormap for land.
        if levels[-1] == 0:
            self.contourf_set.norm.vmax = 0

        divide_by = 1
        label = 'Depth (m)'
        if levels[0] < -2000:
            divide_by = 1000
            label = 'Depth (km)'

        if _pre37:
            cbar_kw = dict(orientation="vertical")
        else:
            cbar_kw = dict(location=location)
        cbar_kw["format"] = RevScalarFormatter(divide_by=divide_by)
        # Four possible cases for self.cax and cax:
        if self.cax is None and cax is None:
            cbar_kw["ax"] = self.ax
            cbar_kw["shrink"] = 0.8
            cbar_kw["anchor"] = (0.8, 0.5)
        if self.cax is not None and cax is None:
            self.cax.cla()
            cbar_kw["cax"] = self.cax
        if self.cax is None and cax is not None:
            cbar_kw["cax"] = cax
        if self.cax is not None and cax is not None:
            self.cax.remove()
            cbar_kw["cax"] = cax

        self.cbar = self.ax.figure.colorbar(self.contourf_set, **cbar_kw)
        self.cbar.set_label(label)
        self.cax = self.cbar.ax

        if linelevels is not None:
            self.contour_set = self.contour(XX, YY, z,
                        levels=linelevels,
                        linestyles='solid',
                        colors='k')
            self.cbar.add_lines(self.contour_set)
        if coast:
            self.fillcontinents([0.4, 0.6, 0.3])
        # Without the following, the current axes would be the colorbar axes.
        sca_if_interactive(self.ax)
        draw_if_interactive()

    def untopo(self):
        if self.cbar is None:
            return
        self.cbar.remove()
        self.cax = None
        if _pre38:
            artists = []
            if self.contourf_set is not None:
                artists.extend(self.contourf_set.collections)
            if self.contour_set is not None:
                artists.extend(self.contour_set.collections)
            if self.continents is not None:
                artists.extend(self.continents)
            for artist in artists:
                artist.remove()
        else:
            if self.contourf_set is not None:
                self.contourf_set.remove()
            if self.contour_set is not None:
                self.contour_set.remove()
            if self.continents is not None:
                for artist in self.continents:
                    artist.remove()
        self.contourf_set = None
        self.contour_set = None
        self.continents = None


    def mplot(self, lon, lat, *args, **kw):
        """
        Plot a single set of points specified via *lon* and *lat*.

        Remaining args and kw are passed to Basemap.plot.
        """
        x, y = self(lon, lat)
        return self.plot(x, y, *args, **kw)


class Conic(Mapbase):
    """
    Experimental convenience wrapper for Basemap lcc projection.

    This works well for making a map covering the desired lat and
    lon range, provided the ranges are not too large and/or close
    to the pole.
    """
    @staticmethod
    def process_params(lons, lats,
                       resolution=None,
                       round_to=None,
                       min_size=None,
                       pad=None,
                       aspect=None,
                       **kw):
        # assume for now that lonrange is unwrapped
        lons = np.asanyarray(lons)

        lats = np.asanyarray(lats)
        # First guess at lat_0:
        latmax = lats.max()
        latmin = lats.min()
        dlat = latmax - latmin
        lat_0 = 0.5 * (latmax + latmin)

        lonmax = lons.max()
        lonmin = lons.min()
        dlon = lonmax - lonmin
        lon_0 = 0.5 * (lonmax + lonmin)

        round_to = _set_round(round_to, dlon, dlat)

        lon_0 = round(lon_0 / round_to) * round_to

        lat_1 = lat_0 - dlat/6.0
        lat_2 = lat_0 + dlat/6.0

        if abs(lat_1) >= 90 or abs(lat_2) >= 90:
            lat_1 = lat_2 = lat_0
        p = pyproj.Proj(proj='lcc', lat_0=lat_0, lat_1=lat_1, lat_2=lat_2,
                                    lon_0=lon_0)
        if len(lons) == 2:
            lons = np.array([lons[0], lons[0], lon_0,
                             lons[1], lons[1], lon_0])
            lats = np.array([lats[0], lats[1], lats[1],
                             lats[1], lats[0], lats[0]])
        
        x, y = p(lons, lats)

        # Now put lat_0 at the actual center:
        lat_0 = p(lon_0, 0.5*(y.max() + y.min()), inverse=True)[1]
        lat_1 = p(lon_0, 0.35*y.max() + 0.65*y.min(), inverse=True)[1]
        lat_2 = p(lon_0, 0.65*y.max() + 0.35*y.min(), inverse=True)[1]

        lat_0 = round(lat_0 / round_to) * round_to
        lat_1 = round(lat_1 / round_to) * round_to
        lat_2 = round(lat_2 / round_to) * round_to
        if abs(lat_1) >= 90 or abs(lat_2) >= 90:
            lat_1 = lat_2 = lat_0

        # Use revised projection to calculate width, height
        p = pyproj.Proj(proj='lcc', lat_0=lat_0, lat_1=lat_1, lat_2=lat_2,
                                    lon_0=lon_0)
        x, y = p(lons, lats)
        x0, y0 = p(lon_0, lat_0)

        width =  2 * max(x.max() - x0, x0 - x.min())
        height = 2 * max(y.max() - y0, y0 - y.min())


        # expand width and/or height as needed.
        if pad is not None:
            width *= (1+pad)
            height *= (1+pad)
            # Throw in some discretization to aid caching.
            sz = 10 ** (int(np.log10(max(width, height)) - 4))
            width = round(width/sz) * sz
            height = round(height/sz) * sz

        if min_size is not None:
            width = max(width, min_size * 1.1e5)
            height = max(height, min_size * 1.1e5)

        if aspect is not None:
            if np.iterable(aspect):
                asmin, asmax = aspect
            else:
                asmin = asmax = aspect
            a = height/width
            if a > asmax:
                width *= (a/asmax)
            elif a < asmin:
                height *= (asmin/a)

        res = _set_res(resolution, width, height)

        basekw = (('width', width), ('height', height),
                   ('lon_0', lon_0), ('lat_0', lat_0),
                   ('lat_1', lat_1), ('lat_2', lat_2),
                   ('resolution', res),
                   ('projection', 'lcc'))
        kwdict = dict(basekw)
        kwdict.update(kw)
        return basekw, kwdict



    def _find_gridlims(self):
        self.loncen = lon_0 = self.kwdict['lon_0']
        self.latcen = self.kwdict['lat_0']
        # We need to calculate alonrange and alatrange
        # here because as of 2009/12/08, basemap has
        # bug in calculating lonmin, lonmax for conic
        # projections that span the dateline.
        width = self.kwdict['width']
        height = self.kwdict['height']
        cx = [0, width/2, width, width, width/2, 0]
        cy = [0, 0, 0, height, height, height]
        cxl, cyl = self(cx, cy, inverse=True)
        # cxl is now on a range +-180; near the dateline,
        # all values must be adjusted if necessary to the same
        # monotonic range:
        cxl = np.asarray(cxl)
        cxl[cxl - lon_0 > 180] -= 360
        cxl[cxl - lon_0 < -180] += 360
        cyl = np.asarray(cyl)
        self.alonrange = [cxl.min(), cxl.max()]
        self.alatrange = [cyl.min(), cyl.max()]
        # Detect the case where a pole is included.
        if self.alonrange[1] - self.alonrange[0] >= 180:
            self.alonrange = [0, 359.9999]
            if self.latcen > 0:
                self.alatrange[1] = 90
            else:
                self.alatrange[0] = -90


class Polar(Mapbase):
    """
    Experimental convenience wrapper for Basemap nplaea and splaea projection.

    """
    @staticmethod
    def process_params(lons, lats,
                       resolution=None,
                       round_to=None,
                       min_size=None,
                       pad=None,     # applied directly to boundinglat
                       aspect=None,  # ignored for polar projection
                       **kw):
        # assume for now that lonrange is unwrapped
        lons = np.asanyarray(lons)
        lats = np.asanyarray(lats)
        # First guess at lat_0:
        latmax = lats.max()
        latmin = lats.min()
        dlmaxmin = abs(latmax) - abs(latmin)

        if dlmaxmin < 0 or (dlmaxmin == 0 and latmax < 0):
            blat = -latmax
            projection = 'splaea'
        else:
            blat = latmin
            projection = 'nplaea'

        dlat = 90 - blat

        lonmax = lons.max()
        lonmin = lons.min()
        dlon = lonmax - lonmin
        lon_0 = 0.5 * (lonmax + lonmin)

        round_to = _set_round(round_to, dlon, dlat)

        lon_0 = round(lon_0 / round_to) * round_to

        if min_size is None:
            min_size = 2

        dlat = max(min_size, dlat)

        if pad is None:
            pad = 0.2
        dlat *= (1+pad)

        boundinglat = 90 - dlat
        if projection == 'splaea':
            boundinglat *= -1

        width = height = 2 * dlat * 1.1e5

        res = _set_res(resolution, width, height)

        basekw = (('boundinglat', boundinglat),
                   ('lon_0', lon_0),
                   ('resolution', res),
                   ('projection', projection))
        kwdict = dict(basekw)
        kwdict.update(kw)
        kwdict.setdefault('anchor', 'W')
        return basekw, kwdict



    def _find_gridlims(self):
        self.loncen = self.kwdict['lon_0']
        boundinglat = self.kwdict['boundinglat']
        northern = self.kwdict['projection'][0] == 'n'

        self.latcen = boundinglat / 2
        if not northern:
            self.latcen += -1

        self.alonrange = [0, 359.9999]
        if northern:
            self.alatrange = [self.latmin, 90]
        else:
            self.alatrange = [-90, self.latmax]



class Mercator(Mapbase):
    """
    Experimental convenience wrapper for Basemap merc projection.

    This works well for making a map covering the desired lat and
    lon range, provided the ranges are not too large and/or close
    to the pole.  It is best suited to the near-equatorial region;
    the Lambert (conic) is better for higher latitudes, except when
    the region to be mapped is small.
    """
    def _find_gridlims(self):
        lonrange = [self.kwdict['llcrnrlon'], self.kwdict['urcrnrlon']]
        latrange = [self.kwdict['llcrnrlat'], self.kwdict['urcrnrlat']]
        self.alonrange = lonrange
        self.alatrange = latrange
        self.loncen = 0.5 * (lonrange[0] + lonrange[1])
        self.latcen = 0.5 * (latrange[0] + latrange[1])

    @staticmethod
    def process_params(lons, lats,
                       resolution=None,
                       round_to=None,
                       min_size=None,
                       pad=None,
                       aspect=None,
                       **kw):
        # assume for now that lonrange is unwrapped
        lons = np.asanyarray(lons)
        lats = np.asanyarray(lats)

        # First guess at lat_0:
        latmax = lats.max()
        latmin = lats.min()
        dlat = latmax - latmin
        lat_0 = 0.5 * (latmax + latmin)

        lonmax = lons.max()
        lonmin = lons.min()
        dlon = lonmax - lonmin
        lon_0 = 0.5 * (lonmax + lonmin)

        round_to = _set_round(round_to, dlon, dlat)

        lon_0 = round(lon_0 / round_to) * round_to

        p = pyproj.Proj(proj='merc')
        x, y = p(lons-lon_0, lats)

        width = np.ptp(x)
        height = np.ptp(y)
        y0 = 0.5 * (y.max() + y.min())
        # nominal degrees (111 km) to map coords
        scale = 1.1e5 / np.cos(np.deg2rad(lat_0))

        # expand width and/or height as needed.
        if pad is not None:
            width *= (1+pad)
            height *= (1+pad)

        if min_size is not None:
            width = max(width, min_size * scale)
            height = max(height, min_size * scale)

        if aspect is not None:
            if np.iterable(aspect):
                asmin, asmax = aspect
            else:
                asmin = asmax = aspect
            a = height/width
            if a > asmax:
                width *= (a/asmax)
            elif a < asmin:
                height *= (asmin/a)

        lonrange, latrange = p([-width/2,  width/2],
                               [y0 - height/2, y0 + height/2],
                               inverse=True)

        _set_res(resolution, width, height)

        lon0 = np.floor(0.01 + lonrange[0] / round_to) * round_to + lon_0
        lon1 = np.ceil(-0.01 + lonrange[1] / round_to) * round_to + lon_0
        lat0 = np.floor(0.01 + latrange[0] / round_to) * round_to
        lat1 = np.ceil(-0.01 + latrange[1] / round_to) * round_to

        basekw = (('llcrnrlon', lon0),
                  ('llcrnrlat', lat0),
                  ('urcrnrlon', lon1),
                  ('urcrnrlat', lat1),
                  ('resolution', resolution),
                  ('projection', 'merc'))
        kwdict = dict(basekw)
        kwdict.update(kw)
        return basekw, kwdict


class DegFormatter(ticker.Formatter):
    def __init__(self, fmt=u"%s\N{DEGREE SIGN}", round=3):
        self.fmt = fmt
        self.round = round

    def __call__(self, x, pos=None):
        x = round(x, self.round)
        if x == round(x, 0):
            x = int(x)
        return self.fmt % x

class LonFormatter(ticker.Formatter):
    def __init__(self, fmt=u"%s\N{DEGREE SIGN}", round=3):
        self.fmt = fmt
        self.round = round

    def __call__(self, x, pos=None):
        x = x - round(x/360.0) * 360.0
        x = round(x, self.round)
        if x == round(x, 0):
            x = int(x)
        if x == 0 or x == 180:
            return self.fmt % x
        if x > 0:
            return (self.fmt % x) + 'E'
        else:
            return (self.fmt % -x) + 'W'


class LatFormatter(ticker.Formatter):
    def __init__(self, fmt=u"%s\N{DEGREE SIGN}", round=3, eq=False):
        self.fmt = fmt
        self.round = round
        self.eq = eq

    def __call__(self, x, pos=None):
        x = round(x, self.round)
        if x == round(x, 0):
            x = int(x)
        if x == 0:
            if self.eq:
                return 'EQ'
            return self.fmt % 0
        if x > 0:
            return (self.fmt % x) + 'N'
        else:
            return (self.fmt % -x) + 'S'


def llticks(ax, x=None, y=None, xnbins=None, ynbins=None, **kw):
    '''
    re-label x ticks and/or y ticks as specified

    x = 'lon' | 'lat' | 'deg' : relabel xaxis with E/W | N/S
    y = 'lon' | 'lat' | 'deg' : relabel yaxis with E/W | N/S

    If nxticks and/or nyticks is supplied, the corresponding
    axis locator is set to MaxNLocator with the specified
    number of ticks, and any additional kwargs are passed
    to the locator.

    Note: as of 2010/04/18, mpl provides an easier and more
    flexible way of controlling the locators.

    '''

    if x == 'lat':
        ax.xaxis.set_major_formatter(LatFormatter())
    elif x == 'lon':
        ax.xaxis.set_major_formatter(LonFormatter())
    elif x == 'deg':
        ax.xaxis.set_major_formatter(DegFormatter())
    elif x is not None:
        raise ValueError("x must be 'lat' or 'lon' or 'deg'")


    if y == 'lat':
        ax.yaxis.set_major_formatter(LatFormatter())
    elif y == 'lon':
        ax.yaxis.set_major_formatter(LonFormatter())
    elif y == 'deg':
        ax.yaxis.set_major_formatter(DegFormatter())
    elif y is not None:
        raise ValueError("y must be 'lat' or 'lon' or 'deg'")

    if xnbins is not None:
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=xnbins, **kw))
    if ynbins is not None:
        ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=ynbins, **kw))

    draw_if_interactive()
