
"""
Access to the GHRSST-FNMOC data.
              GHRSST-OSTIA                        0.05 degree
              GHRSST-MUR                          0.011 degree
              GHRSST-AVHRR-AMSR (Reynolds) OISST2 0.25 degree


This is starting out as network-based, a single time-slice at a time.
All of these SST datasets except FNMOC are archived and served as one
slice (one day) per file.  Access can be very slow, or can
generate obscure errors for no apparent reason.

info is at
http://www.usgodae.org/dods/GDS/fnmoc_ghrsst/FNMOC_GHRSST_sst.info

dods URL is  http://www.usgodae.org:80/dods/GDS/fnmoc_ghrsst/FNMOC_GHRSST_sst
It is a GRADS server, providing access to a single time, lat, lon array.
It is now using netCDF4.

All of the others are served via THREDDS by NODC, with one file
per day, and accessed using netCDF4.

This module was updated on 2013/03/02 to the point where all of
the URLs work, and the NODC GHRSST commonality is mostly factored
out.

There is a bug somewhere in the netCDF software chain such that
extracting some lon ranges can cause stack corruption and an
immediate abort.  Very odd, and not at all clear where the problem
is.

There also appears to be a major memory leak in the netCDF4 access;
redoing the plots from the cache does not cause secular
memory consumption.  This appears to be fixed with netcdf 4.3.0.

It would be good to be able to query the server to find out
what time range of data is available.

The handling of time in the MovieMaker probably could be made
simpler and easier to understand and use.

The time base and format conversion functions in this module probably
should be simplified, reduced in number, and moved out to a utility module.

"""

import os
import sys
import datetime
from datetime import date, timedelta
import time

import numpy as np
import matplotlib as mpl

import netCDF4 as nc

from pycurrents.num.nptools import rangeslice
from pycurrents.data.navcalc import unwrap_lon
from pycurrents.system import safe_makedirs


# We could get the following from the attributes of the time
# variable, but hard-wiring it here should be good enough.

# FNMOC times:
#    Array of 64 bit Reals [time = 0..2810]
#    grads_dim: "t"
#    grads_mapping: "linear"
#    grads_size: "2811"
#    grads_min: "12z20jun2005"
#    grads_step: "24hr"
#    units: "days since 1-1-1 00:00:0.0"
#    long_name: "time"
#    minimum: "12z20jun2005"
#    maximum: "12z28feb2013"

# The following is a somewhat arbitrary pair of values.
FNMOC_start_date = date(2006, 4, 1)
FNMOC_start_time = 732403
# It might have been based on the earliest FNMOC time available
# when I first wrote this.
#In [27]: date2num(datetime.date(2006, 4, 1))
#Out[27]: 732402.0



# The CNES epoch looks as good as any to pick for this sort of
# product, so we will standardize on it.
cnes_epoch = date(1950, 1, 1) # duplicated from ssh.py

oisst2_epoch = date(1978, 1, 1)

start_date = dict(FNMOC=FNMOC_start_date,
                  CNES=cnes_epoch,
                  OISST2=oisst2_epoch,
                  APDRC_wind=datetime.date(2009, 3, 3),
                  )

start_time = dict(FNMOC=FNMOC_start_time,
                  CNES=0,
                  OISST2=0,
                  APDRC_wind=733470,
                  )

def split_YYYYMMDD(arg):
    """
    Split an integer YYYYMMDD into a tuple of integers.
    """
    y = arg // 10000
    arg -= y * 10000
    m = arg // 100
    arg -= m * 100
    d = arg
    return y, m, d

def date_to_YMD(*args):
    """
    Given a datetime.date, a YYYYMMDD integer, or args Y, M, D.
    return Y, M, D.
    """
    if len(args) == 1:
        arg = args[0]
        try:
            return arg.year, arg.month, arg.day
        except AttributeError:
            return split_YYYYMMDD(arg)
    return args

def YMD_to_date(*args):
    """
    Given a datetime.date, a YYYYMMDD integer, or args Y, M, D.
    return a datetime.date.
    """
    if len(args) == 1:
        arg = args[0]
        if isinstance(arg, date):
            return arg
        return date(*split_YYYYMMDD(arg))
    return date(*args)

def date_to_days(*args, **kw):
    """
    Convert a date to FNMOC, CNES, or OISST2 native day count.

    Default is kind='CNES'.

    Examples::

        days = YMD_to_days(date(year=2011, month=1, day=1),
                           kind='FNMOC')
        days = YMD_to_days(2011, 1, 1, kind='CNES')
        days = YMD_to_days(20110101, kind='OISST2')

    """
    kind = kw.get('kind', 'CNES')
    _date = YMD_to_date(*args)
    td = (_date - start_date[kind]) + timedelta(start_time[kind])
    return td.days

def days_to_date(d, kind='CNES'):
    """
    Convert FNMOC, CNES, OISST2 days to a datetime.date.
    """
    d = int(d)
    _date = start_date[kind] + (timedelta(d)
                                   - timedelta(start_time[kind]))
    return _date


def days_to_YMD(d, kind='CNES'):
    """
    Convert FNMOC, CNES, OISST2 days to Y, M, D.
    """
    _date = days_to_date(d, kind=kind)
    return _date.year, _date.month, _date.day

def convert_day(d, source='FNMOC', dest='CNES'):
    """
    Very inefficient conversion from one day origin to another;
    good enough for now.
    """
    _date = days_to_date(d, kind=source)
    return date_to_days(_date, kind=dest)

def _slices_to_list(*args):
    x = []
    for arg in args:
        s = arg.start
        if s is None:
            s = 0
        x.append(s)

        s = arg.stop
        if s is None:
            s = sys.maxsize # should not happen here
        x.append(s)

        s = arg.step
        if s is None:
            s = 1
        x.append(s)
    return x

class SST_Base:

    lwrapmin=0 # or -180

    def __init__(self, lonrange, latrange, cache=None):
        if cache is not None:
            safe_makedirs(cache)
        self.cache = cache

        self._init_dataset()
        alllon, alllat = self.make_lon_lat()

        self.alllat = alllat
        self.latsl = rangeslice(alllat, latrange)
        self.lat = alllat[self.latsl]

        self.alllon = alllon

        lwrapmin = self.lwrapmin
        lwrapmax = lwrapmin + 360

        if lonrange[0] < lwrapmin and lonrange[1] > lwrapmin:
            lonsl1 = rangeslice(alllon, [lonrange[0]+360, lwrapmax])
            lonsl2 = rangeslice(alllon, [lwrapmin, lonrange[1]])
            self.lon = np.concatenate((alllon[lonsl1]-360, alllon[lonsl2]))
        elif lonrange[0] < lwrapmax and lonrange[1] > lwrapmax:
            lonsl1 = rangeslice(alllon, [lonrange[0], lwrapmax])
            lonsl2 = rangeslice(alllon, [lwrapmin, lonrange[1]-360])
            self.lon = np.concatenate((alllon[lonsl1], alllon[lonsl2]+360))
        else:
            if lonrange[0] < lwrapmin:
                lonrange[0] += 360
                lonrange[1] += 360
            elif lonrange[0] >= lwrapmax:
                lonrange[0] -= 360
                lonrange[1] -= 360
            lonsl1 = rangeslice(alllon, lonrange)
            lonsl2 = None
            self.lon = alllon[lonsl1]

        self.lonsl1 = lonsl1
        self.lonsl2 = lonsl2

        if lonsl2 is None:
            slices = (lonsl1, self.latsl)
        else:
            slices = (lonsl1, self.latsl, lonsl2)
        self.slicenums = _slices_to_list(*slices)

        self.lonrange = lonrange
        self.latrange = latrange

        # convenience for plotting
        self.X, self.Y = np.meshgrid(self.lon, self.lat)

    def _init_dataset(self):
        pass

    def make_lon_lat():
        """
        returns alllon, alllat
        """
        raise NotImplementedError("subclass must provide")

class GHRSST(SST_Base):
    """
    Base class for the GHRSST products as served by NODC.

    No cache implementation in this version.
    """

    urlbase = ""  # derived must provide
    urlvar = ""   # derived must provide
    lwrapmin = -180
    use_offset = True

    def _init_dataset(self):
        self.dataset = None
        self._sst = None
        self._error = None
        self._mask = None
        self._icefrac = None

    def open_day(self, *args, **kw):
        """
        Open Dataset for the date specified by args and kwargs.

        Sets dataset attribute; closes
        """
        kind = kw.get("kind", None)
        if kind is None:
            _date = YMD_to_date(*args)
        else:
            _date = days_to_date(*args, kind=kind)
        yearday = _date.timetuple().tm_yday
        url = self.urlbase + self.urlvar % (_date.year, yearday,
                                              _date.year, _date.month,
                                              _date.day)
        self.url = url
        self.close()
        self.dataset = nc.Dataset(url)

    def close(self):
        """
        Close the netCDF dataset pointed to by the dataset attribute,
        and set the attribute to None.
        """
        if self.dataset is not None:
            self.dataset.close()
            self._init_dataset()

    def _extract(self, ncvar):
        """
        Given a 3-d netcdf array variable, return the 2-D ndarray
        for the given longitude and latitude range.
        """
        if self.lonsl2 is not None:
            arr = np.concatenate((ncvar[0, self.latsl, self.lonsl1],
                                ncvar[0, self.latsl, self.lonsl2]), axis=-1)
        else:
            arr = ncvar[0, self.latsl, self.lonsl1]
        return arr

    @property
    def sst(self):
        if self._sst is None:
            var = self.dataset.variables['analysed_sst']
            arr = self._extract(var)
            if self.use_offset:
                arr -= var.add_offset
            else:  # MUR; something is wrong with their add_offset!
                arr -= 273.15
            self._sst = arr
        return self._sst

    @property
    def error(self):
        if self._error is None:
            var = self.dataset.variables['analysis_error']
            arr = self._extract(var)
            self._error = arr
        return self._error

    @property
    def mask(self):
        if self._mask is None:
            var = self.dataset.variables['mask']
            arr = self._extract(var)
            self._mask = arr
        return self._mask

    @property
    def icefrac(self):
        if self._icefrac is None:
            var = self.dataset.variables['sea_ice_fraction']
            arr = self._extract(var)
            self._icefrac = arr
        return self._icefrac


class GHRSST_cache(SST_Base):
    """
    Base class for the GHRSST products as served by NODC,
    with caching.
    """

    urlbase = ""  # derived must provide
    urlvar = ""   # derived must provide
    lwrapmin = -180
    use_offset = True

    def open_day(self, *args, **kw):
        """
        Loads the data arrays for the specified day.

        Data are then available in the attributes sst,
        error, mask, and icefrac.
        """
        kind = kw.get("kind", None)
        if kind is None:
            _date = YMD_to_date(*args)
        else:
            _date = days_to_date(*args, kind=kind)
        self.date = _date
        yearday = _date.timetuple().tm_yday
        url = self.urlbase + self.urlvar % (_date.year, yearday,
                                              _date.year, _date.month,
                                              _date.day)
        self.url = url
        if self.cache is not None:
            cachename = self._make_cachename()
            try:
                vardict = np.load(cachename)
                self.sst = np.ma.array(vardict['sst'],
                                       mask=vardict['sst_mask'],
                                       )
                self.error = np.ma.array(vardict['error'],
                                       mask=vardict['error_mask'],
                                       )
                self.mask = vardict['mask']
                self.icefrac = vardict['icefrac']
                return
            except IOError:
                pass

        self.dataset = nc.Dataset(url)

        var = self.dataset.variables['analysed_sst']
        arr = self._extract(var)
        if self.use_offset:
            arr -= var.add_offset
        else:  # MUR; something is wrong with their add_offset!
            arr -= 273.15
        self.sst = arr

        var = self.dataset.variables['analysis_error']
        self.error = self._extract(var)

        var = self.dataset.variables['mask']
        self.mask = self._extract(var)

        var = self.dataset.variables['sea_ice_fraction']
        self.icefrac = self._extract(var)

        self.dataset.close()

        if self.cache is not None:
            savedict = dict(sst=np.ma.getdata(self.sst).astype(np.float32),
                            sst_mask=np.ma.getmaskarray(self.sst),
                            error=np.ma.getdata(self.error).astype(np.float32),
                            error_mask=np.ma.getmaskarray(self.error),
                            mask=self.mask,
                            icefrac=np.ma.filled(
                                      self.icefrac, np.nan).astype(np.float32))
            savedict["cache_url"] = self.url
            savedict["cache_lonrange"] = self.lonrange
            savedict["cache_latrange"] = self.latrange
            savedict["cache_slicenums"] = self.slicenums
            np.savez(cachename, **savedict)


    def _make_cachename(self):
        datestr = self.date.strftime("%Y%m%d")
        boxstr = "_".join([str(num) for num in self.slicenums])
        fname = "%s_%s__%s.npz" % (self.product, datestr, boxstr)
        return os.path.join(self.cache, fname)

    def _extract(self, ncvar):
        """
        Given a 3-d netcdf array variable, return the 2-D ndarray
        for the given longitude and latitude range.
        """
        if self.lonsl2 is not None:
            arr = np.concatenate((ncvar[0, self.latsl, self.lonsl1],
                                ncvar[0, self.latsl, self.lonsl2]), axis=-1)
        else:
            arr = ncvar[0, self.latsl, self.lonsl1]
        return arr


class OISST2(GHRSST_cache):

    urlbase = ('http://data.nodc.noaa.gov/opendap/ghrsst/' +
               'L4/GLOB/NCDC/AVHRR_AMSR_OI/')
    urlvar = ('%4d/%03d/%4d%02d%02d-NCDC-L4LRblend-GLOB-v01-fv02_0' +
              '-AVHRR_AMSR_OI.nc.bz2')
    product = "OISST2"

    @staticmethod
    def make_lon_lat():
        alllon = -180 + 0.125 + np.arange(1440) * 0.25
        alllat = -89.875 + np.arange(720) * 0.25
        return alllon, alllat

class OSTIA(GHRSST_cache):

    urlbase = 'http://data.nodc.noaa.gov/opendap/ghrsst/L4/GLOB/UKMO/OSTIA/'
    urlvar = '%4d/%03d/%4d%02d%02d-UKMO-L4HRfnd-GLOB-v01-fv02-OSTIA.nc.bz2'
    product = "OSTIA"

    @staticmethod
    def make_lon_lat():
        alllon = -180 +  0.025 + np.arange(7200) * 0.05
        alllat = -89.975 + np.arange(3600) * 0.05
        return alllon, alllat


class MUR(GHRSST_cache):
    """
    Access to the NODC servers seems to be very erratic, often yielding
    an error with MUR, but not with OSTIA.  The NODC server is now
    commented out below, in favor of the JPL server; whether this is
    a good move in the long run remains to be seen.

    It is important to extract only rather small regions, otherwise
    the memory requirement is excessive.
    """
    #urlbase = 'http://data.nodc.noaa.gov/opendap/ghrsst/L4/GLOB/JPL/MUR/'
    #urlbase = 'http://data.nodc.noaa.gov/thredds/dodsC/ghrsst/L4/GLOB/JPL/MUR/'
    urlbase = 'http://opendap.jpl.nasa.gov:80/opendap/OceanTemperature/ghrsst/data/L4/GLOB/JPL/MUR/'
    urlvar = '%4d/%03d/%4d%02d%02d-JPL-L4UHfnd-GLOB-v01-fv04-MUR.nc.bz2'
    use_offset=False
    product = "MUR"

    @staticmethod
    def make_lon_lat():
        alllon, lonstep = np.linspace(-180, 180, num=32768,
                                      endpoint=False, retstep=True)
        alllon += lonstep/2
        alllat, latstep = np.linspace(-90, 90, num=16384,
                                      endpoint=False, retstep=True)
        alllat += latstep/2

        return alllon, alllat

class FNMOC(SST_Base):
    """
    Access a GRADS server that presents the FNMOC product as a 3-D array.
    """
    url = "http://www.usgodae.org:80/dods/GDS/fnmoc_ghrsst/FNMOC_GHRSST_sst"
    lwrapmin = 0

    def _init_dataset(self):
        self.ncd = nc.Dataset(self.url)
        self.ncvars = self.ncd.variables
        self.allt = self.ncvars['time'][:].astype(int)

    def make_lon_lat(self):
        alllon = self.ncvars['lon'][:]
        alllat = self.ncvars['lat'][:]
        return alllon, alllat

    def open_day(self, *args, **kw):
        """
        Open Dataset for the date specified by args and kwargs.

        Sets dataset attribute; closes
        """
        kind = kw.get("kind", None)
        if kind is None:
            _date = YMD_to_date(*args)
        else:
            _date = days_to_date(*args, kind=kind)
        d = date_to_days(_date, kind="FNMOC")

        itime = np.searchsorted(self.allt, d)
        sst = self.ncvars['sst']
        if self.lonsl2 is not None:
            d = np.concatenate((sst[itime, self.latsl, self.lonsl1],
                                sst[itime, self.latsl, self.lonsl2]), axis=-1)
        else:
            d = sst[itime, self.latsl, self.lonsl1]
        d = np.ma.masked_greater(d, 100)
        self.sst = d


####################################################################
#
#  Taken from ssh.py and modified; we may be able to factor something
#  out into a base class common to ssh and sst.
#

from matplotlib import is_interactive, interactive
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.figure import SubplotParams

from pycurrents.plot.maptools import mapper

class MovieMakerBase:
    def __init__(self,
                 lonrange,
                 latrange,
                 cache=None,
                 margin=1, # pad to add to each side of domain
                 dpi=100,
                 figsize=None,
                 out_dir='./',
                 titlestr = '',
                 figname = 'sst',
                 units = u'\N{DEGREE SIGN}C',
                 mapkw={},
                 gridkw={},
                 contourkw={},
                 contourfkw={},   # e.g., {'levels':np.arange(0.2, 1.2, 0.1)}
                 subplotkw={},
                 cbarkw={},
                 ):

        lonrange = unwrap_lon(lonrange)
        mapkw.setdefault('resolution', 'i')
        self.map = mapper(lonrange, latrange, **mapkw)

        biglonrange = [self.map.lonmin - margin, self.map.lonmax + margin]
        biglatrange = [self.map.latmin - margin, self.map.latmax + margin]

        self.dpi = dpi
        self.figsize=figsize
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        self.out_dir = out_dir
        self.titlestr = titlestr
        self.figname = figname
        self.units = units
        self.contourkw=contourkw
        self.contourfkw=contourfkw
        if subplotkw:
            sp = SubplotParams(**subplotkw)
        else:
            sp = SubplotParams(left=0.1, right=1.0,
                           top=0.92, bottom=0.07)
        self.fig = Figure(subplotpars=sp)
        self.canvas = FigureCanvas(self.fig)
        cbarkw.setdefault('shrink', 0.8)
        self.cbarkw = cbarkw

        self.ghrsst = self.sst_class(biglonrange, biglatrange, cache=cache)
        if self.map.lonmin - self.ghrsst.lon[0] < -180:
            self.ghrsst.X -= 360
        if self.map.lonmin - self.ghrsst.lon[0] > 180:
            self.ghrsst.X += 360
        self.x, self.y = self.map(self.ghrsst.X, self.ghrsst.Y)

    def frame_fname(self, i):
        fname = os.path.join(self.out_dir, self.figname + '.%07d.png' % i)
        return fname

    def frame_setup(self, i):
        self.fig.clf()
        self.ax = self.fig.add_subplot(1,1,1)
        self.map.grid(ax=self.ax)
        self.map.fillcontinents(zorder=10, ax=self.ax)

    def frame_time(self, i):
        return days_to_date(i, kind='CNES').strftime('%Y/%m/%d')

    def frame_finish(self, i):
        t = self.frame_time(i)
        self.ax.set_title(self.titlestr + ' ' + t, family='monospace')
        if self.figsize is not None:
            self.fig.set_figsize_inches(self.figsize)
        fname = self.frame_fname(i)
        self.canvas.print_figure(fname,
                                dpi=self.dpi,
                                #bbox_inches='tight',
                                #pad_inches=0.2,
                                )

    def frame_content(self, i):
        #z = self.ghrsst.extract_day(i, kind='CNES').T
        self.ghrsst.open_day(i, kind='CNES')
        z = self.ghrsst.sst
        kw = dict(self.contourfkw)
        kw.setdefault('extend', 'both')
        CS = self.map.contourf(self.x, self.y, z, ax=self.ax, **kw)
        cb = self.fig.colorbar(CS, ax=self.ax, **self.cbarkw)
        if self.contourkw:
            CS2 = self.map.contour(self.x, self.y, z, ax=self.ax,
                                    **self.contourkw)
            cb.add_lines(CS2)
        cb.set_label(self.units, fontsize=14)

    def frame(self, i, redo=True):
        if not redo and os.path.exists(self.frame_fname(i)):
            return
        tic = time.time()
        self.frame_setup(i)
        self.frame_content(i)
        self.frame_finish(i)
        print("memory: %s  time: %s" % (mpl.cbook.report_memory(),
                                        time.time() - tic))

    def movie(self, t0=None, t1=None, redo=False):
        inter = is_interactive()
        interactive(False)
        t0, t1 = self.process_timerange(t0, t1)

        for i in range(t0, t1):
            try:
                print(i)
                self.frame(i, redo=redo)
            except Exception as arg:
                print(i, 'failed:', arg)
                raise

        interactive(inter)

    def process_timerange(self, t0, t1):
        """
        Return t0, t1 as CNES times after handling
        negative values and Nones.

        Subclass must provide this.
        """
        raise NotImplementedError("subclass must provide this")

    @staticmethod
    def process_time_indices(t0, t1, first, last):
        " Helper for process_timerange."
        if t0 is None:
            t0 = first
        if t0 < 0:
            t0 = last + 1 + t0
        if t1 is None:
            t1 = last + 1
        if t1 < 0:
            t1 = last + 1 + t1
        return t0, t1


class MovieMakerFNMOC(MovieMakerBase):
    sst_class = FNMOC

    def process_timerange(self, t0, t1):
        first = convert_day(self.ghrsst.allt[0], 'FNMOC', 'CNES')
        last = convert_day(self.ghrsst.allt[-1], 'FNMOC', 'CNES')
        t0, t1 = self.process_time_indices(t0, t1, first, last)
        return t0, t1


class MovieMakerOSTIA(MovieMakerBase):
    sst_class = OSTIA

    def process_timerange(self, t0, t1):
        first = date_to_days(date(2006,0o4,0o1), kind='CNES')
        last = date_to_days(date.today(), kind='CNES')
        t0, t1 = self.process_time_indices(t0, t1, first, last)
        return t0, t1

class MovieMakerOISST2(MovieMakerBase):
    sst_class = OISST2

    def process_timerange(self, t0, t1):
        first = date_to_days(date(2006,0o4,0o1), kind='CNES')
        last = date_to_days(date.today(), kind='CNES')
        t0, t1 = self.process_time_indices(t0, t1, first, last)
        return t0, t1

class MovieMakerMUR(MovieMakerOSTIA):
    sst_class = MUR

MMdict = dict(FNMOC=MovieMakerFNMOC,
              OSTIA=MovieMakerOSTIA,
              OISST2=MovieMakerOISST2,
              MUR=MovieMakerMUR,
              )

def test_movie(source='OISST2'):

    mmclass = MMdict[source]

    mm = mmclass(
                 [360-165, 360-145],
                 [15, 30],
                 out_dir='./Hawaii_test',
                 figname=source,
                 titlestr=source,
                 mapkw={},
                 gridkw={},
                 contourkw={},
                 contourfkw={'levels':np.arange(21, 28.01, 0.25)},
                 cbarkw={'ticks':np.arange(21, 28.01)},
                 )
    mm.movie(22000, 22002, redo=True)

    print(mm.map.lonmin)
    print(mm.ghrsst.X.min())
