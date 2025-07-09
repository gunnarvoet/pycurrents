"""
functions and classes for working with LADCP data

"""

import numpy as np
import numpy.ma as ma
from scipy.io import loadmat
from pycurrents.ladcp.ladcp import read_npz


try:
    import netCDF4 as nc
except ImportError:
    print("Cannot import netCDF4; VisbeckNCSection will not be available")

from pycurrents.codas import to_day
from pycurrents.num.grid import interp1

_vdd_base = to_day(1968, [1968, 5, 23, 0, 0, 0])

def vdday_to_dday(yearbase, vdday):
    """
    Convert the "Julian" dday used in Visbeck software to our dday.
    """
    dday1968 = vdday - 2440000 + _vdd_base
    dday = dday1968 - to_day(1968, [yearbase,1,1,0,0,0])
    return dday


class VisbeckMat(dict):
    """
    Read matlab files produced by Visbeck and derivative
    processing software, providing more pythonic access than
    the raw result of scipy's loadmat
    """
    def __init__(self, fname, yearbase=None, keep_raw=False):
        """
        *keep_raw* defaults to False so that we can close the
        file after reading the basic variables.  Otherwise, when
        reading a large number of files, one may run into a
        'too many open files' error.
        """
        self.__dict__ = self
        self.fname = fname
        vmfile = open(fname, "rb")
        raw = loadmat(vmfile, struct_as_record=True,
                             chars_as_strings=True)
                             # squeeze_me seems to leave things
                             # in a state where it is impossible
                             # to extract arrays from their object
                             # containers.
        prof = raw['dr'][0,0]
        self.prof = prof
        self.name = str(prof['name'][0]) # convert from unicode dtype
        for name in prof.dtype.names[1:]:
            var = prof[name].squeeze()
            if var.dtype.kind == 'f' and name != 'z':
                var = ma.masked_invalid(var)
            # convert array scalars to ordinary scalars; maybe not necessary
            if not var.shape:
                var = float(var)
            setattr(self, name, var)
        self.w = self.w_shear_method   # Why did I do this?
        if yearbase is None:
            yearbase = self.date[0]
        self.yearbase = yearbase
        self.dday_range = vdday_to_dday(yearbase, self.tim[[0,-1]].data)
        if keep_raw:
            self.raw = raw
        else:
            vmfile.close()


class UHMat(dict):
    """
    Read LADCP velocity profile from UH-produced matfile.
    """
    def __init__(self, fname, nmin=1):
        self.__dict__ = self
        p = loadmat(fname, struct_as_record=True, squeeze_me=True)
        self.p_mat = p
        for dir in ['dn', 'up', 'mn']:
            mask = p['sn_%s_i' % dir] < nmin
            for var in ['u', 'v', 'w']:
                v = p['s%s_%s_i' % (var, dir)]
                self['%s_%s' % (var, dir)] = ma.array(v, mask=mask)
            self['n_%s' % dir] = p['sn_%s_i' % dir]
        self.z = p['d_samp']
        self.lon, self.lat = p['pxy']
        self.dday_range = p['txy_start_end'][:,0]
        for var in ['u', 'v', 'w', 'n']:
            self[var] = self['%s_mn' % var]


class SectionBase(dict):
    extravars = []
    def __init__(self, fnames, zgrid=None):
        self.__dict__ = self
        self.fnames = fnames
        self.zgrid = zgrid
        nprofs = len(fnames)

        self._set_z()

        self.lat = np.zeros((nprofs,), float)
        self.lon = np.zeros((nprofs,), float)
        self.dday_range = np.zeros((nprofs,2), float)

        nd = len(self.dep)
        varlist = ['u', 'v', 'w', 'n'] + self.extravars
        for var in varlist:
            self[var] = ma.zeros((nprofs, nd), float)

        for i, fname in enumerate(fnames):
            p = self._get_Profile(fname)
            for varname in varlist:
                try:
                    self[varname][i,:] = self._regrid_var(p[varname], p.z)
                except:
                    print('%s: cannot regrid %s' % (fname, varname))
            self.lat[i] = p.lat
            self.lon[i] = p.lon
            self.dday_range[i,:] = p.dday_range

    def _set_z(self):
        raise NotImplementedError("Subclass must implement")

    def _regrid_var(self, var, zorig):
        if self.zgrid is None:
            return var
        vg = interp1(zorig, var, self.dep)
        return vg


class UHMatSection(SectionBase):
    extravars = ['u_dn', 'v_dn', 'u_up', 'v_up']
    def _get_Profile(self, fname):
        return UHMat(fname)

    def _set_z(self):
        if self.zgrid is not None:
            self.dep = self.zgrid
        else:
            p0 = UHMat(self.fnames[0])
            self.dep = p0.z


class UHPySection(SectionBase):
    extravars = ['u_dn', 'v_dn', 'u_up', 'v_up']
    def _get_Profile(self, fname):
        data = read_npz(fname)
        data.z = data.depth
        data.lat = data.lat_start
        data.lon = data.lon_start
        data.dday_range = [data.dday_start, data.dday_up]
        return data

    def _set_z(self):
        if self.zgrid is not None:
            self.dep = self.zgrid
        else:
            p0 = read_npz(self.fnames[0])
            self.dep = p0.depth

class VisbeckMatSection(SectionBase):
    extravars = ['u_do', 'v_do', 'u_up', 'v_up',
                 'u_shear_method', 'v_shear_method', 'w_shear_method',
                 'ctd_t', 'ctd_s', 'p']

    def _get_Profile(self, fname):
        vm = VisbeckMat(fname)
        vm.n = vm.nvel
        return vm

    def _set_z(self):
        if self.zgrid is None:
            self.zgrid = np.arange(10, 6001, 10, dtype=float)
        self.dep = self.zgrid

class VisbeckNCSection(dict):
    """
    Load a single Netcdf file with a section.

    File is as generated by Andreas's software for CLIVAR
    Some variables are missing, compared to sections loaded
    from mat files.
    """
    def __init__(self, fname):
        self.__dict__ = self
        self.fname = fname
        ds = nc.Dataset(fname)
        for varname in ['u', 'v', 'uerr', 'lat', 'lon',
                        'EXTRA.PROFILE.nvel']:
            var = np.ma.masked_invalid(ds.variables[varname][...])
            varname = varname.split('.')[-1]
            self[varname] = var
        self.dep = ds.variables['z'][...]
        dd0 = ds.variables['GEN.Profile_start_decimal_day'][...]
        dd1 = ds.variables['GEN.Profile_end_decimal_day'][...]
        self.dday_range = np.hstack([dd0[:,np.newaxis], dd1[:,np.newaxis]])
        self.station = ds.variables['station'][...]
        for varname in ['GEN.LADCP_station', 'GEN.LADCP_cast']:
            var = ds.variables[varname][...]
            varname = varname.split('.')[-1]
            self[varname] = var.astype(int)

        ds.close()
