"""
Access SSH data: AVISO, MDOT, MDT_CNES-CLS09

Access AVISO gridded SSH directly from their DODS server,
with a local cache file.

Experimental.

Use list_datasets() to see what is available.

Use aviso_auth() to set your username and password.

"""

import os.path
from datetime import timedelta, date

from netCDF4 import Dataset

import numpy as np
from mpl_toolkits.basemap import interp

from pycurrents.num.nptools import rangeslice
from pycurrents.data.navcalc import unwrap
from pycurrents.data.ocean import coriolis
from pycurrents.file import npzfile

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.figure import SubplotParams

from pycurrents.plot.maptools import mercator

cnes_epoch = date(1950, 1, 1)

def yearbase_shift(yearbase):
    """
    Return number of days from the cnes epoch to
    the start of the new yearbase.
    """
    new_epoch = date(yearbase, 1, 1)
    return (new_epoch - cnes_epoch).days

def cnes_jd_to_date(jd):
    return cnes_epoch + timedelta(float(jd))

def YMD_to_cnes_jd(*args):
    if len(args) == 1:
        args = args[0]
        y = args // 10000
        args -= y * 10000
        m = args // 100
        args -= m * 100
        d = args
    else:
        y, m, d = args
    td = date(y, m, d) - cnes_epoch
    return td.days


url_base = "opendap.aviso.oceanobs.com/thredds/dodsC/"

url_data = [
('delayed_msla', 'dataset-duacs-dt-global-allsat-msla-h', 'sla'),
#('delayed_uvanom', dataset-duacs-dt-global-allsat-msla-uv', ('u', 'v')),
('delayed_madt', 'dataset-duacs-dt-global-allsat-madt-h', 'adt'),
]

aviso_urls = dict({(u[0], u[1]) for u in url_data})
sshvars = dict({(u[0], u[2]) for u in url_data})

def list_datasets():
    ds = [rec[0] for rec in url_data]
    print('\n'.join(ds))
    print()

_aviso_username = None
_aviso_password = None

def aviso_auth(username=None, password=None):
    """
    Store username, password as module-level attributes.
    """
    if username is None or password is None:
        print("Usage: aviso_auth(username, password)")
        return
    global _aviso_username, _aviso_password
    _aviso_username = username
    _aviso_password = password

class ncReader:
    def __init__(self, location, cachedir='./'):
        self.location = location
        self._make_description()

    def __str__(self):
        return self._description

    def _make_description(self):
        nc = Dataset(self.location)
        lines = [self.location]
        lines.append(str(nc))
        for v in nc.variables.values():
            lines.append(str(v))
        lines.append('')
        self._description = '\n'.join(lines)



class AVISO(dict):
    """
    Provide access to variables from AVISO gridded sea level product.

    Attributes:
        t   in days since the cnes epoch (1950, 1, 1)
        lon
        lat
        ssh in meters   (time, lon, lat)

    """
    def __init__(self, lonrange, latrange, YMDrange=None,
                    tstep=1,
                    dataset='delayed_msla',
                    cache='./'):
        """
        lonrange
        latrange
        YMDrange :  start, end year month day as single integers,
                    e.g. [20080101, 20081231]
                    or as tuples,
                    e.g. [(2008, 1, 1), (2008, 12, 31)]
                    If omitted, all available times will be included.
        tstep : slice step

        There is probably an AVISO constraint on how much can be downloaded
        such that one cannot get daily data for the whole interval, at least
        for any substantial region.
        """
        dict.__init__(self)
        self.__dict__= self
        self.dataset = dataset
        self.lonrange = lonrange
        self.latrange = latrange
        self.YMDrange = YMDrange
        self.tstep = tstep
        if YMDrange is None:
            cachefilename = "%s_%d_%d_%d_%d_%d.cache.npz" % (dataset,
                                                     lonrange[0],
                                                     lonrange[1],
                                                     latrange[0],
                                                     latrange[1],
                                                     tstep)
        else:
            cachefilename = "%s_%d_%d_%d_%d_%d_%d_%d.cache.npz" % (dataset,
                                                     lonrange[0],
                                                     lonrange[1],
                                                     latrange[0],
                                                     latrange[1],
                                                     YMDrange[0],
                                                     YMDrange[1],
                                                     tstep)

        cachefilename = os.path.join(cache, cachefilename)
        try:
            d = npzfile.load(cachefilename)
            self.update(d)
            print("loaded from %s" % cachefilename)
        except IOError:
            url = url_base + aviso_urls[dataset]
            if _aviso_username is None or _aviso_password is None:
                raise RuntimeError(
                    "Execute aviso_auth to set username and password")
            aviso_access = ":".join([_aviso_username, _aviso_password])
            #print "aviso_access", aviso_access
            url = "http://%s@%s" % (aviso_access, url)
            print("url:", url)
            nc = Dataset(url)
            print("opened dataset")
            e = nc.variables
            print("variables are ", list(e.keys()))
            sshvar = e[sshvars[dataset]]

            allt = e['time'][:]
            if 'hours' in e['time'].units:   # no longer needed?
                allt /= 24.0
            if YMDrange is None:
                tsl = slice(None, None, tstep)
                self.t = allt[tsl]
            else:
                t0 = YMD_to_cnes_jd(YMDrange[0])
                t1 = YMD_to_cnes_jd(YMDrange[1])
                tsl = rangeslice(allt, [t0, t1])
                tsl = slice(tsl.start, tsl.stop, tstep)
                self.t = allt[tsl]

            alllat = e['lat'][:]
            latsl = rangeslice(alllat, latrange)
            self.lat = alllat[latsl]

            alllon = e['lon'][:]
            if lonrange[0] < 0 and lonrange[1] > 0:
                lonsl1 = rangeslice(alllon, [lonrange[0]+360, 360])
                lonsl2 = rangeslice(alllon, [0, lonrange[1]])
                self.lon = np.concatenate((alllon[lonsl1], alllon[lonsl2]))
                self.ssh = np.concatenate(
                             (sshvar[tsl, latsl, lonsl1],
                              sshvar[tsl, latsl, lonsl2]), axis=-1)
            else:
                if lonrange[0] < 0:
                    lonrange[0] += 360
                    lonrange[1] += 360
                lonsl1 = rangeslice(alllon, lonrange)
                self.ssh = sshvar[tsl, latsl, lonsl1]
                self.lon = alllon[lonsl1]

            self.ssh = self.ssh.transpose(0, 2, 1)

            self.start_ij = np.array([lonsl1.start, latsl.start], dtype=np.int64)
            self.lon = unwrap(self.lon, centered=True)
            nc.close()
            npzfile.savez(cachefilename, t=self.t,
                                 lon=self.lon, lat=self.lat,
                                 ssh=self.ssh,
                                 start_ij=self.start_ij)
            print("wrote %s" % cachefilename)
#        self._add_grid_params()
        self.Y, self.X = np.meshgrid(self.lat, self.lon)

    def _add_grid_params(self):
        # for the old grid; still needed for anything?
        dy = (1/3.0) * np.pi / 180.0       # radians; not really any delta-Y
        sin_th = np.sin(-82.0*np.pi/180.0)  # -82.0 is first latitude
        self.j_eq = 0.5 * np.log((1-sin_th)/(1+sin_th))/dy
        self.x_step = 1.0/3.0
        self.y_step = 1.0/3.0             # again, not really the step
        self.i_start, self.j_start = self.start_ij


    def add_mdot(self, dir='./'):
        """
        Obsolete.
        """
        # Danger: this requires that we have grabbed the data
        # from the necessary time range.  Later, we will do this
        # once and write it out in a file to be used with mdot.
        tslice = rangeslice(self.t, [YMD_to_cnes_jd(1992, 10, 1),
                                    YMD_to_cnes_jd(2002, 10, 1)])
        self.meanssh = self.ssh[tslice,:,:].mean(axis=0)

        mdot = MDOT(self.lonrange, self.latrange, dir=dir)
        Y, X = np.meshgrid(self.lat, self.lon)
        mdotgridded = interp(mdot.ssh, mdot.lat, mdot.lon,
                                Y, X, masked=True)

        self.mdotssh = mdotgridded
        self.sshbar = self.mdotssh - self.meanssh # Add this to each time sample.
        self.mdot = mdot


class MDOT:
    """
    Extract a rectangular subset from the Niiler-Maximenko
    Mean Dynamic Ocean Topography product.

    attributes:
        lon
        lat
        ssh nlon x nlat

    """
    def __init__(self, lonrange, latrange, dir='./'):
        self.lonrange = lonrange
        self.latrange = latrange
        d = Dataset(os.path.join(dir, '1992-2002MDOT060401.nc'))
        e = d.variables
        alllat = e['latitude'][:]
        latsl = rangeslice(alllat, latrange)
        self.lat = alllat[latsl]

        alllon = e['longitude'][:]
        if lonrange[0] < 0 and lonrange[1] > 0:
            lonsl1 = rangeslice(alllon, [lonrange[0]+360, 360])
            lonsl2 = rangeslice(alllon, [0, lonrange[1]])
            self.lon = np.concatenate((alllon[lonsl1], alllon[lonsl2]))
            self.ssh = np.concatenate(
                         (e['ssh'][lonsl1, latsl],
                          e['ssh'][lonsl2, latsl]), axis=0)
        else:
            if lonrange[0] < 0:
                lonrange[0] += 360
                lonrange[1] += 360
            lonsl = rangeslice(alllon, lonrange)
            self.ssh = e['ssh'][ lonsl, latsl]
            self.lon = alllon[lonsl]
        self.lon = unwrap(self.lon, centered=True)
        self.ssh = np.ma.masked_greater(self.ssh, 1e37) * 0.01
        del(e)
        d.close()
        del(d)


class MDT_CNES:
    """
    Extract a rectangular subset from the Rio MDT-CNES
    Mean Dynamic Topography product.

    attributes:
        lon
        lat
        ssh nlon x nlat
        u   m/s
        v
        ssh_err
        u_err
        v_err

    """
    vars = dict(ssh='Grid_0001',
                u='Grid_0002',
                v='Grid_0003',
                ssh_err='Grid_0004',
                u_err='Grid_0005',
                v_err='Grid_0006',
                flag='Grid_0007')
    def __init__(self, lonrange, latrange, dir='./'):
        self.lonrange = lonrange
        self.latrange = latrange
        d = Dataset(os.path.join(dir, 'MDT_CNES-CLS09_v1.1.nc'))
        e = d.variables
        alllat = e['NbLatitudes'][:]
        latsl = rangeslice(alllat, latrange)
        self.lat = alllat[latsl]

        alllon = e['NbLongitudes'][:]
        if lonrange[0] < 0 and lonrange[1] > 0:
            lonsl1 = rangeslice(alllon, [lonrange[0]+360, 360])
            lonsl2 = rangeslice(alllon, [0, lonrange[1]])
            self.lon = np.concatenate((alllon[lonsl1], alllon[lonsl2]))
            def extract(vn, e):
                return np.concatenate(
                         (e[vn][lonsl1, latsl],
                          e[vn][lonsl2, latsl]), axis=0)
        else:
            if lonrange[0] < 0:
                lonrange[0] += 360
                lonrange[1] += 360
            lonsl = rangeslice(alllon, lonrange)
            self.lon = alllon[lonsl]
            def extract(vn, e):
                return e[vn][lonsl, latsl]
        for attr, vname in self.vars.items():
            # ensure we get a masked array:
            v = np.ma.array(extract(vname, e))
            setattr(self, attr, v)
        # We need additional masking where data are flagged;
        # otherwise we get initial estimates over land near
        # coastlines.
        flag = self.flag
        for attr in self.vars.keys():
            if attr != 'flag':
                var = getattr(self, attr)
                setattr(self, attr, np.ma.masked_where(flag == 1, var))

        self.lon = unwrap(self.lon, centered=True)
        del(e)
        d.close()
        del(d)


######################################################################
# Some of the following may duplicate functionality elsewhere
# in pycurrents, and/or may be useful elsewhere and may be moved;
# don't count on anything here for use outside this module.
######################################################################


def lldif(lon, lat):
    """
    Centered differences of lon and lat 1D arrays in meters;
    output are dx, dy as 2D arrays, because dx depends on y.
    """
    nx = len(lon)
    ny = len(lat)
    dlon = np.zeros((nx, ny), dtype=np.float64)
    dlat = dlon.copy()
    lon = lon[:, np.newaxis]
    lat = lat[np.newaxis, :]
    dlon[1:-1, :] = lon[2:, :] - lon[:-2, :]
    dlat[:, 1:-1] = lat[:, 2:] - lat[:, :-2]
    dx = lon_to_m(dlon, lat)
    dx[0, :] = dx[1, :]
    dx[-1, :] = dx[-2, :]
    dy = lat_to_m(dlat, lat)
    dy[:, 0] = dy[:, 1]
    dy[:, -1] = dy[:, -2]
    return dx, dy


def lon_to_m(dlon, alat):
    """
    dx = lon_to_m(dlon, alat)
    dx   = longitude difference in meters
    dlon = longitude difference in degrees
    alat = average latitude between the two fixes
    """
    rlat = alat * np.pi/180
    p = 111415.13 * np.cos(rlat) - 94.55 * np.cos(3 * rlat)
    dx = dlon * p
    return dx

def lat_to_m(dlat, alat):
    """
    dy = lat_to_m(dlat,alat)
    dy   = latitude difference in meters
    dlat = latitude difference in degrees
    alat = average latitude between the two fixes
    Reference: American Practical Navigator, Vol II, 1975 Edition, p 5
    """
    rlat = alat * np.pi/180
    m = 111132.09  - 566.05 * np.cos(2 * rlat) + 1.2 * np.cos(4 * rlat)
    dy = dlat * m 
    return dy

def cderiv(A, dx, dy):
    """
    Centered difference derivative estimates for a rectilinear array A,
    given centered dx and dy in meters.
    dx and dy are 2D arrays (see lldif).
    A is nx by ny.
    """
    nx, ny = A.shape
    dAdx = np.ma.zeros((nx, ny), dtype=np.float64)
    dAdy = np.ma.zeros((nx, ny), dtype=np.float64)
    dAdx1 = np.ma.zeros((nx, ny), dtype=np.float64)
    dAdx2 = np.ma.zeros((nx, ny), dtype=np.float64)
    dAdy1 = np.ma.zeros((nx, ny), dtype=np.float64)
    dAdy2 = np.ma.zeros((nx, ny), dtype=np.float64)
    for a in [dAdx, dAdy, dAdx1, dAdx2, dAdy1, dAdy2]:
        a[:] = np.ma.masked

    dAdy[:, 1:-1] = (A[:, 2:] - A[:, :-2]) / dy[:, 1:-1]
    dAdx[1:-1, :] = (A[2:, :] - A[:-2, :]) / dx[1:-1, :]

    dAdy.mask[:,0] = True
    dAdy.mask[:,-1] = True
    dAdx.mask[0,:] = True
    dAdx.mask[-1,:] = True

    j0 = slice(0, (ny-2))
    j1 = slice(1, (ny-1))
    j2 = slice(2, ny)
    # Using information to the right of each point:
    dAdy1[:, j0] = (4 * A[:, j1] - 3 * A[:, j0] - A[:, j2]) / dy[:, j1]
    # Using information to the left:
    dAdy2[:, j2] = -(4 * A[:, j1] - 3 * A[:, j2] - A[:, j0]) / dy[:, j1]

    i0 = slice(0, (nx-2))
    i1 = slice(1, (nx-1))
    i2 = slice(2, nx)
    # Using information above each point (if increasing index is increasing lat):
    dAdx1[i0, :] = (4 * A[i1, :] - 3 * A[i0, :] - A[i2, :]) / dx[i1, :]
    # Information from below:
    dAdx2[i2, :] = -(4 * A[i1, :] - 3 * A[i2, :] - A[i0, :]) / dx[i1, :]


    dAdx = np.ma.where(np.logical_and(dAdx.mask, ~dAdx1.mask), dAdx1, dAdx)
    dAdx = np.ma.where(np.logical_and(dAdx.mask, ~dAdx2.mask), dAdx2, dAdx)
    dAdy = np.ma.where(np.logical_and(dAdy.mask, ~dAdy1.mask), dAdy1, dAdy)
    dAdy = np.ma.where(np.logical_and(dAdy.mask, ~dAdy2.mask), dAdy2, dAdy)

    return dAdx, dAdy


class SSH_Grid:
    """
    A rectilinear grid on which SSH is specified, and on which
    fields of interest can be calculated.  Changed SSH fields
    can be set directly, and need not be set upon initialization
    of the object.  Properties are used extensively so that
    fields are calculated only when requested and only when they
    have changed.  MKS units are used throughout, with the exception
    of longitude and latitude.

    Calculated properties include:

        ug, vg: geostrophic velocity
        ua, va: first order linearized advective correction (experimental)
        vort: vorticity
        div: divergence
        OW: Okubo-Weiss parameter

    """
    def __init__(self, lon, lat, ssh=None,
                 min_lat = 5):
        """
        lon, lat are in degrees
        ssh is in meters, shape is (nlon, nlat)

        min_lat = 5         # minimum latitude for geostrophic calculation
        """
        self.lon = lon
        self.lat = lat
        self.dx, self.dy = lldif(lon, lat)
        self._ssh = ssh
        self._clear()
        self.min_lat = min_lat # minimum latitude for geostrophic calculation
        self.f = coriolis(lat)[np.newaxis,:] # shape = (1, nlat)

    def _clear(self):
        self._ug = self._vg = None
        self._ua = self._va = None
        self._dudx = self._dudy = self._dvdx = self._dvdy = None
        self._vort = None
        self._OW = None
        self._div = None
        self._NS = None
        self._SS = None

    def get_ssh(self):
        return self._ssh
    def set_ssh(self, ssh):
        self._ssh = ssh
        self._clear()
    def del_ssh(self):
        self._ssh = None
        self._clear()
    ssh = property(get_ssh, set_ssh, del_ssh)


    def _velocity(self):
        if self._ug is not None:
            return

        g = 9.8
        dx, dy = self.dx, self.dy
        ssh = np.ma.array(self.ssh, copy=True)
        cond = (np.fabs(self.lat) < self.min_lat)
        ssh[:,cond] = np.ma.masked
        dHdx, dHdy = cderiv(ssh, dx, dy)
        self._ug = -g * dHdy / self.f
        self._vg =  g * dHdx / self.f

    def get_ug(self):
        self._velocity()
        return self._ug
    ug = property(get_ug)

    def get_vg(self):
        self._velocity()
        return self._vg
    vg = property(get_vg)

    def _advective(self):
        """
        Calculate the first order advective corrections;
        that is, velocity correction from coriolis term
        equals advective term based on geostrophic velocity.
        This may have no usefulness in practice.
        """
        if self._ua is not None:
            return
        u = self.get_ug()
        v = self.get_vg()
        ux, uy = cderiv(u, self.dx, self.dy)
        vx, vy = cderiv(v, self.dx, self.dy)
        self._ua = - (u * vx + v * vy) / self.f
        self._va =   (u * ux + v * uy) / self.f

    def get_ua(self):
        self._advective()
        return self._ua
    ua = property(get_ua)

    def get_va(self):
        self._advective()
        return self._va
    va = property(get_va)

    def _vderivs(self):
        self._dudx, self._dudy = cderiv(self.ug, self.dx, self.dy)
        self._dvdx, self._dvdy = cderiv(self.vg, self.dx, self.dy)

    def get_dudx(self):
        if self._dudx is None:
            self._vderivs()
        return self._dudx
    dudx = property(get_dudx)

    def get_dudy(self):
        if self._dudy is None:
            self._vderivs()
        return self._dudy
    dudy = property(get_dudy)

    def get_dvdx(self):
        if self._dvdx is None:
            self._vderivs()
        return self._dvdx
    dvdx = property(get_dvdx)

    def get_dvdy(self):
        if self._dvdy is None:
            self._vderivs()
        return self._dvdy
    dvdy = property(get_dvdy)


    def get_vorticity(self):
        if self._vort is None:
            self._vort = self.dvdx - self.dudy
        return self._vort
    vort = property(get_vorticity)

    def get_divergence(self):
        if self._div is None:
            self._div = self.dudx + self.dvdy
        return self._div
    div = property(get_divergence)

    def get_normal_strain(self):
        if self._NS is None:
            self._NS = self.dudx - self.dvdy
        return self._NS
    NS = property(get_normal_strain)

    def get_shear_strain(self):
        if self._SS is None:
            self._SS = self.dudy + self.dvdx
        return self._SS
    SS = property(get_shear_strain)

    def get_Okubo_Weiss(self):
        if self._OW is None:
            self._OW = self.NS**2 + self.SS**2 - self.vort**2
        return self._OW
    OW = property(get_Okubo_Weiss)

def test_elevation1(R=1, amp=0.2):
    """
    Make Gaussian bump and dip of height 0.2 m;
    returns lon, lat, ssh
    ssh.shape is (nx, ny); ssh units are meters
    """
    lon = np.arange(0, 15, 0.25)
    lat = np.arange(4, 15, 0.25)
    x0, x1 = 5, 10
    y0 = lat.mean()
    X = lon[:,np.newaxis]
    Y = lat[np.newaxis,:]
    arg1 = (X-x0)**2 + (Y-y0)**2
    arg2 = (X-x1)**2 + (Y-y0)**2
    ssh = amp * (np.exp(-arg1/(2*R)) - np.exp(-arg2/(2*R)))
    return lon, lat, ssh

####################################################################
# Another block of code modified from ssh_mapping.py; experimental,
# may not stay here, may be highly modified later.
#



class MovieMaker:
    def __init__(self,
                 lonrange,
                 latrange,
                 avisokw={},
                 mdotkw=None,
                 dpi=100,
                 figsize=None,
                 out_dir='./',
                 titlestr = '', # e.g., AVISO + MDOT
                 figname = 'ssh',
                 units = 'm',
                 mapkw={},
                 gridkw={},
                 contourkw={},
                 contourfkw={},   # e.g., {'levels':np.arange(0.2, 1.2, 0.1)}
                 subplotkw={},
                 cbarkw={},
                 ):

        lonrange = unwrap(lonrange, centered=True)
        mapkw.setdefault('resolution', 'i')
        self.map = mercator(lonrange, latrange, **mapkw)
        biglonrange = [lonrange[0] - 1, lonrange[1] + 1]
        biglatrange = [latrange[0] - 1, latrange[1] + 1]
        self.aviso = AVISO(biglonrange, biglatrange, **avisokw)
        if mdotkw is not None:
            self.aviso.add_mdot(**mdotkw)
            self.ssh = self.aviso.ssh + self.aviso.sshbar
        else:
            self.ssh = self.aviso.ssh
        self.nframes = len(self.aviso.t)
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
        self.sshgrid = SSH_Grid(self.aviso.lon, self.aviso.lat, **gridkw)
        self.x, self.y = self.map(self.aviso.X, self.aviso.Y)
        if subplotkw:
            sp = SubplotParams(**subplotkw)
        else:
            sp = SubplotParams(left=0.1, right=1.0,
                           top=0.92, bottom=0.07)
        self.fig = Figure(subplotpars=sp)
        self.canvas = FigureCanvas(self.fig)
        cbarkw.setdefault('shrink', 0.8)
        self.cbarkw = cbarkw

    def frame_setup(self, i):
        self.fig.clf()
        self.ax = self.fig.add_subplot(1,1,1)
        self.map.grid(ax=self.ax)
        self.map.fillcontinents(zorder=10, ax=self.ax)

    def frame_time(self, i):
        return cnes_jd_to_date(self.aviso.t[i]).strftime('%Y/%m/%d')
        # Or we could use self.aviso.Year[i] etc.

    def frame_finish(self, i):
        t = self.frame_time(i)
        self.ax.set_title(self.titlestr + ' ' + t, family='monospace')
        if self.figsize is not None:
            self.fig.set_figsize_inches(self.figsize)
        fname = os.path.join(self.out_dir, self.figname + '.%04d.png' % i)
        self.canvas.print_figure(fname,
                                dpi=self.dpi,
                                #bbox_inches='tight',
                                #pad_inches=0.2,
                                )
        print(i)

    def frame_content(self, i):
        z = self.ssh[i, :,:]
        kw = dict(self.contourfkw)
        kw.setdefault('extend', 'both')
        CS = self.map.contourf(self.x, self.y, z, ax=self.ax, **kw)
        cb = self.fig.colorbar(CS, ax=self.ax, **self.cbarkw)
        cb.set_label(self.units, fontsize=14)

    def frame(self, i):
        self.frame_setup(i)
        self.frame_content(i)
        self.frame_finish(i)

    def movie(self):
        for i in range(self.nframes):
            self.frame(i)


def test_movie():
    mm = MovieMaker(
                 [-165, -145],
                 [15, 30],
                 avisokw={},
                 mdotkw={},
                 dpi=100,
                 figsize=None,
                 out_dir='./testmovie',
                 titlestr = 'AVISO + MDOT',
                 figname = 'ssh',
                 units = 'm',
                 mapkw={},
                 gridkw={},
                 contourkw={},
                 contourfkw={'levels':np.arange(0.2, 0.901, 0.05)},   # e.g., {'levels':np.arange(0.2, 1.2, 0.1)}
                 )
    #mm.movie()
    mm.frame(0)
