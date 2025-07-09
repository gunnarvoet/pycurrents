"""
Make SADCP time series plots and analysis.

Derived from mixet/scripts/mixet_time.py.

TODO:
    replace regrid
    perform regridding on input instead of at contouring stage
    plot additional variables.
    add to docstrings
    make subclass adding ctd data


"""

from netCDF4 import Dataset

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, ScalarFormatter

from pycurrents.num import rangeslice
from pycurrents.plot.mpltools import get_extcmap
from pycurrents.num.grid import regrid
from pycurrents.system import Bunch
import pycurrents.num.harmfit as hf
import pytide

#zgrid parameters
zg_kw = dict(y_weight=1,
             biharmonic=1,
             interp = 2)

cmap = get_extcmap("ob_vel")

class TimeSeries:
    """
    Access ADCP data as a time series, with optional constraints
    on time range, lon range, and lat range.
    """
    tide_model_name = "PO"
    figext = ".pdf"

    def __init__(self, ncfile, trange=None,
                    lonrange=None, latrange=None,
                    ts_name=""):
        """
        """
        self.ncfile = ncfile
        d = Dataset(ncfile, maskandscale=True)
        self.sonar_name = d.sonar
        self.cruise_id = d.cruise_id
        self.ts_name = ts_name
        ncvars = d.variables
        self.yearbase = int(ncvars['time'].units.split()[2].split("-")[0])
        dday = ncvars['time'][:]
        tsl = rangeslice(dday, trange)
        # initial selection based on a single time slice
        dday = dday[tsl]
        u = ncvars['u'][tsl]
        v = ncvars['v'][tsl]
        lon = ncvars['lon'][tsl]
        lat = ncvars['lat'][tsl]
        depth = ncvars['depth'][tsl]
        d.close()

        ii = np.ones(dday.shape, bool)
        if lonrange is not None:
            ii &= (lon <= lonrange[1]) & (lon >= lonrange[0])
        if latrange is not None:
            ii &= (lat <= latrange[1]) & (lat >= latrange[0])
        if not np.all(ii):
            u = u[ii]
            v = v[ii]
            dday = dday[ii]
            lon = lon[ii]
            lat = lat[ii]
            depth = depth[ii]
        self.u = u
        self.v = v
        self.dday = dday
        self.lon = lon
        self.lat = lat
        self.depth = depth
        self.dep = depth[0]   # should check for uniform values

        self._btide = None

        # shear:
        dz = -np.diff(self.dep)  # negative z positive up
        self.ush = np.ma.diff(self.u, axis=1) / dz
        self.vsh = np.ma.diff(self.v, axis=1) / dz
        self.depsh = 0.5 * (self.dep[:-1] + self.dep[1:])

    def _figax2(self, name="", variable="velocity", suptitle=None):
        """
        Common operations for setting up a two panel u, v plot.

        Returns the figure and two axes.
        """
        fig, (ax1, ax2) = plt.subplots(2, sharex=True, sharey=True,
                                                        figsize=(6,8))

        ax1.xaxis.set_major_locator(MaxNLocator(nbins=7))
        ax1.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax2.set_xlabel("%d decimal days" % self.yearbase)
        ax1.grid(True)
        ax2.grid(True)
        ax1.set_xlim(self.dday[0], self.dday[-1])
        ax1.set_title('Zonal %s' % variable)
        ax2.set_title('Meridional %s' % variable)

        if suptitle is None:
            suptitle = self.suptitle(name)
        fig.suptitle(suptitle, fontsize=14)

        return fig, ax1, ax2

    def suptitle(self, name):
        if self.ts_name:
            st = "%s %s %s, %s" % (name, self.cruise_id, self.ts_name,
                                self.sonar_name)
        else:
            st = "%s %s, %s" % (name, self.cruise_id, self.sonar_name)
        return st

    def uvcontour(self, clevs, ylim, uv=["u", "v"],
                                     tgrid=None,
                                     demean=False,
                                     name="",   # for suptitle
                                     fname=""): # append to file name
        """
        Make generic two-panel contour plot, with u, v by default.

        Other attributes can be specified as the variables to be plotted,
        as when this is called by plot_harmfit.

        By default (*tgrid*=None), the data are regridded to hourly.
        Set it to an empty sequence for no gridding, or specify
        the desired dday grid.

        """
        if tgrid is None:
            tgrid = np.arange(self.dday[0], self.dday[-1], 1.0/24)

        try:
            u = getattr(self, uv[0])
            v = getattr(self, uv[1])
        except TypeError:
            u, v = uv

        if u.shape[1] == self.dep.size:
            dep = self.dep
            units = "m/s"
            variable = "velocity"
            vfn = "UV"
        else:
            dep = self.depsh
            units = "s$^{-1}$"
            variable = "shear"
            vfn = "UVsh"

        if len(tgrid) > 0:
            ugrid = regrid(self.dday, dep, u.T, tgrid, dep, **zg_kw)
            vgrid = regrid(self.dday, dep, v.T, tgrid, dep, **zg_kw)
        else:
            ugrid = u.T
            vgrid = v.T
            tgrid = self.dday

        if demean:
            ugrid = ugrid - ugrid.mean(axis=-1)[:, np.newaxis]
            vgrid = vgrid - vgrid.mean(axis=-1)[:, np.newaxis]

        fig, ax1, ax2 = self._figax2(name=name, variable=variable)

        cs1 = ax1.contourf(tgrid, dep, ugrid, levels=clevs,
                                    cmap=cmap, extend='both')
        cbar1 = fig.colorbar(cs1, ax=ax1, use_gridspec=True, shrink=0.8)
        cbar1.set_label(units)
        ax1.set_ylim(*ylim)

        cs2 = ax2.contourf(tgrid, dep, vgrid, levels=clevs,
                                    cmap=cmap, extend='both')
        cbar2 = fig.colorbar(cs2, ax=ax2, use_gridspec=True, shrink=0.8)
        cbar2.set_label(units)

        fig.savefig(self.fname(vfn, fname) + self.figext)
        return Bunch(fig=fig, cs1=cs1, cbar1=cbar1, cs2=cs2, cbar2=cbar2)

    def fname(self, vfn, fname=""):
        fn0 = "%s_%s" % (self.cruise_id, self.sonar_name)
        if self.ts_name:
            fn0 = "%s_%s" % (fn0, self.ts_name)
        fn0 = "%s_%s" % (fn0, vfn)
        if fname:
            fn = "%s_%s" % (fn0, fname)
        else:
            fn = "%s" % (fn0)
        return fn

    @property
    def btide(self):
        """
        Calculate predicted barotropic tides, leaving the results in
        Bunch attributes, e.g. self.btide.all.u, self.btide.all.v,
        self.btide.semi.u, self.btide.diurnal.u, etc.

        Note: the difference between all and the sum of semi, diurnal,
        and other is the inclusion of the correction for 16 minor
        constituents; it can be quite noticeable.

        """
        if self._btide is None:
            self._btide = Bunch()
            m = pytide.model(self.tide_model_name)
            txyargs = (2012, self.dday, self.lon, self.lat)
            self._btide.all = m.velocity(*txyargs)
                                    # clist=[] would omit the minors
            self._btide.semi = m.velocity(*txyargs,
                                    clist=["m2", "s2", "n2", "k2"])
            self._btide.diurnal = m.velocity(*txyargs,
                                            clist=["o1", "k1", "p1", "q1"])
            self._btide.other = m.velocity(*txyargs,
                                            clist=["m4", "ms4", "mn4"])
        return self._btide

    def harmfit(self, clist=None, trend=True):
        """
        Calculate the fit to a mean, (optional) trend,
        and tidal harmonics.

        Default *clist* of harmonics is ["m2", "s2", "o1", "k1"].

        Access results as self.hfu.x, self.hfu.f, self.hfu.r,
        self.hfu.fit_some(...), etc.
        """
        if clist is None:
            clist = ["m2", "s2", "o1", "k1"]
        self.hclist = clist
        periods = [pytide.hour_period_d[c] / 24.0 for c in clist]
        self.hperiods = periods
        # separate u and v because we don't want rotary amplitudes
        self.hfu = hf.HarmonicFit(self.dday, self.u, periods, trend=trend)
        self.hfv = hf.HarmonicFit(self.dday, self.v, periods, trend=trend)
        self.hfush = hf.HarmonicFit(self.dday, self.ush, periods, trend=trend)
        self.hfvsh = hf.HarmonicFit(self.dday, self.vsh, periods, trend=trend)

    def demod(self, periods, filter=1.5, trend=True, sequential=True):
        """
        Calculate the fit to one or more harmonics using complex demod.

        *filter* can be a scalar, or a sequence with the same length
            as *periods*; it specifies the Blackman filter half-width
            as a multiple of the harmonic period from *periods*.

        If *sequential* is True (default), each successive harmonic
        demodulation will be performed on the residual after having
        subtracted the trend and the previous harmonics.
        """
        try:
            len(filter)
        except TypeError:
            filter = [filter] * len(periods)
        if trend:
            hfu = hf.HarmonicFit(self.dday, self.u, [], trend=True)
            u = hfu.r
            utrend = hfu.f
            hfv = hf.HarmonicFit(self.dday, self.v, [], trend=True)
            v = hfv.r
            vtrend = hfv.f
        else:
            u = self.u
            v = self.v
            utrend = np.zeros_like(u)
            vtrend = np.zeros_like(v)
        demodru = []
        demodrv = []
        demodc = []
        dt = (self.dday[-1] - self.dday[0]) / len(self.dday) # days
        for per, filt in zip(periods, filter):
            nfilt = int(filt * per / (dt * 24))
            demodru.append(hf.demod(self.dday, u, per, nfilt))
            demodrv.append(hf.demod(self.dday, v, per, nfilt))
            demodc.append(hf.demodc(self.dday, u + 1j * v, per, nfilt))
            if sequential:
                u -= demodru[-1].vel
                v -= demodrv[-1].vel
        self.demodru = demodru
        self.demodrv = demodrv
        self.demodc = demodc
        self.utrend = utrend
        self.vtrend = vtrend
        self.demod_periods = periods

    def plot_demod(self, clevs, ylim):
        """
        Set of figures based on self.demod(periods).

        """
        figs = []
        for i, per in enumerate(self.demod_periods):
            u = self.demodru[i].vel
            v = self.demodrv[i].vel
            fig = self.uvcontour(clevs, ylim, uv=[u, v],
                                         demean=False,
                                         name="%.2f hr " % per,
                                         fname="%s_hr_" % per)
            figs.append(fig)
        u = self.u - self.utrend
        v = self.v - self.vtrend
        for i, per in enumerate(self.demod_periods):
            u -= self.demodru[i].vel
            v -= self.demodrv[i].vel
        fig = self.uvcontour(clevs, ylim, uv=[u, v],
                                demean=False,
                                name="demod resid",
                                fname="demod_resid")
        figs.append(fig)
        return figs


    def plot_barotide(self):
        """
        Basic plot, after running self.barotide().
        """
        fig, ax1, ax2 = self._figax2(name="baro tide")
        fig.subplots_adjust(left=0.2)
        ax1.plot(self.dday, self.btide.all.u, label="all")
        ax1.plot(self.dday, self.btide.semi.u, label="semidiurnal")
        ax1.plot(self.dday, self.btide.diurnal.u, label="diurnal")
        ax1.set_ylabel("m/s")

        ax2.plot(self.dday, self.btide.all.v, label="all")
        ax2.plot(self.dday, self.btide.semi.v, label="semidiurnal")
        ax2.plot(self.dday, self.btide.diurnal.v, label="diurnal")
        ax2.set_ylabel("m/s")

        if self.btide.all.u.max() < self.btide.all.v.max():
            axlegend = ax1
        else:
            axlegend = ax2
        axlegend.legend(loc="upper right", fontsize="small")

        if self.ts_name:
            fname = "%s_%s_btide" % (self.cruise_id, self.ts_name)
        else:
            fname = "%s_btide"
        fig.savefig(fname + self.figext)
        return fig

    def plot_harmfit(self, clevs, ylim):
        """
        Set of figures based on self.harmfit().

        Customization or generalization to alternative list
        of constituents remains to be done.
        """
        self.harmfit()
        u = self.hfu.fit_some([0,1])
        v = self.hfv.fit_some([0,1])
        figsemi = self.uvcontour(clevs, ylim, uv=[u, v],
                                     demean=False,
                                     name="semidiurnal",
                                     fname="IWsemi")

        u -= self.btide.semi.u[:, np.newaxis]
        v -= self.btide.semi.v[:, np.newaxis]
        figsemi2 = self.uvcontour(clevs, ylim, uv=[u, v],
                                     demean=False,
                                     name="semi, no baro",
                                     fname="IWseminobaro")

        u = self.hfu.fit_some([2,3])
        v = self.hfv.fit_some([2,3])

        figdi = self.uvcontour(clevs, ylim, uv=[u, v],
                                     demean=False,
                                     name="diurnal",
                                     fname="IWdiurnal")

        u -= self.btide.diurnal.u[:, np.newaxis]
        v -= self.btide.diurnal.v[:, np.newaxis]
        figdi2 = self.uvcontour(clevs, ylim, uv=[u, v],
                                     demean=False,
                                     name="diurnal, no baro",
                                     fname="IWdiurnalnobaro")

        u = self.hfu.r
        v = self.hfv.r
        figres = self.uvcontour(clevs, ylim, uv=[u, v],
                                     demean=False,
                                     name="residual",
                                     fname="IWresidual")


        return Bunch(figsemi=figsemi, figsemi2=figsemi2,
                     figdi=figdi, figdi2=figdi2, figres=figres)
