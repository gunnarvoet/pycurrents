"""
Access APDRC DAP version of World Ocean Atlas 2013, annual or monthly.
Only the 1-deg gridding is supported here at present.

Variables start with a letter:

    a  apparent oxygen utilization
    o  dissolved oxygen
    s  salinity
    t  temperature
    ...

The remaining two letters indicate:

    an  objectively analyzed
    mn  statistical mean
    se  standard error
    sd  standard deviation
    dd  number of obs
    gp  "number of mean values within radius of influence"

Example, to look at temperature near Hawaii:

w = WOA_annual([-170, -140], [15, 30], depthrange=[0, 1000])
t = w.read('tan')
print w.dep[5]
contourf(w.X, w.Y, t[5])

Note: at present, the read() method is not changing the index
order to match our convention; instead, the order is time, depth,
lat, lon.

Most of the code is derived from sst.py.

"""
from netCDF4 import Dataset
import numpy as np

from pycurrents.num.nptools import rangeslice

APDRC_WOA_BASE = 'http://apdrc.soest.hawaii.edu/dods/public_data/WOA/'
url_annual = APDRC_WOA_BASE + 'WOA13/1_deg/annual'
url_monthly = APDRC_WOA_BASE + 'WOA13/1_deg/monthly'

vardirs = dict(t='temp',
               a='aoxy',
               d='doxy',
               n='nit',
               p='pho',
               x='poxy',
               s='salt',
               i='sil',
               )

class WOA:
    lwrapmin = -180  # WOA09 was 0
    def __init__(self, url, lonrange, latrange, depthrange=None):
        self.url = url
        self.lonrange = lonrange
        lonrange = lonrange[:]  #copy to avoid side effect
        self.depthrange = depthrange
        d = Dataset(self.var_url('t'))
        self.varlist = list(d.variables.keys())
        alllevs = d.variables['lev'][:]

        self.alllevs = alllevs
        if depthrange is None:
            self.levsl = slice(0, len(alllevs))
        else:
            self.levsl = rangeslice(alllevs, depthrange)
        self.dep = alllevs[self.levsl]

        # Big chunk of code from sst.py; need to factor it out?

        alllon = d.variables['lon'][:]
        alllat = d.variables['lat'][:]

        self.alllat = alllat
        self.latsl = rangeslice(alllat, latrange)
        self.lat = alllat[self.latsl]

        self.alllon = alllon

        lwrapmin = self.lwrapmin
        lwrapmax = lwrapmin + 360

        lonadj = 0
        if lonrange[0] < lwrapmin and lonrange[1] > lwrapmin:
            lonsl1 = rangeslice(alllon, [lonrange[0]+360, lwrapmax])
            lonsl2 = rangeslice(alllon, [lwrapmin, lonrange[1]])
            self.lon = np.concatenate((alllon[lonsl1]-360, alllon[lonsl2]))
            lonadj = -360
        elif lonrange[0] < lwrapmax and lonrange[1] > lwrapmax:
            lonsl1 = rangeslice(alllon, [lonrange[0], lwrapmax])
            lonsl2 = rangeslice(alllon, [lwrapmin, lonrange[1]-360])
            self.lon = np.concatenate((alllon[lonsl1], alllon[lonsl2]+360))
        else:
            if lonrange[0] < lwrapmin:
                lonrange[0] += 360
                lonrange[1] += 360
                lonadj = 360
            elif lonrange[0] >= lwrapmax:
                lonrange[0] -= 360
                lonrange[1] -= 360
                lonadj = -360
            lonsl1 = rangeslice(alllon, lonrange)
            lonsl2 = None
            self.lon = alllon[lonsl1]

        self.lonsl1 = lonsl1
        self.lonsl2 = lonsl2

        self.lon -= lonadj
        # convenience for plotting
        self.X, self.Y = np.meshgrid(self.lon, self.lat)
        d.close()

    def var_url(self, varname):
        return self.url + '/' + vardirs[varname[0]]

    def read(self, varname, itime=None):
        """
        itime can be an index or a slice
        """
        d = Dataset(self.var_url(varname))
        var = d.variables[varname]
        if self.lonsl2 is None:
            return var[itime, self.levsl, self.latsl, self.lonsl1]

        v = np.ma.concatenate((var[itime, self.levsl, self.latsl, self.lonsl1],
                            var[itime, self.levsl, self.latsl, self.lonsl2]),
                            axis=-1)
        d.close()
        return v

class WOA_annual(WOA):
    def __init__(self, *args, **kw):
        WOA.__init__(self, url_annual, *args, **kw)

    def read(self, varname, itime=0):
        return WOA.read(self, varname, itime=itime)

class WOA_monthly(WOA):
    def __init__(self, *args, **kw):
        WOA.__init__(self, url_monthly, *args, **kw)

    def read(self, varname, itime=None):
        if itime is None:
            itime = slice(None)
        return WOA.read(self, varname, itime=itime)
