"""
Load subset of gridded wind product as served by APDRC.

Experimental, in progress.

Note: the ccmp winds
(http://apdrc.soest.hawaii.edu/datadoc/ccmp_6hourly.php)
are provided as velocity.  We could use them, estimating
stress via a constant drag coefficient, but we would need to
add subsampling by time.

"""

import numpy as np

from pycurrents.num.nptools import rangeslice
from pycurrents.data.navcalc import unwrap
# The following is probably a temporary location:
from pycurrents.data.sst import (days_to_date,
                                 date_to_days)
                                 # Use here with type="APDRC_wind".
from pycurrents.file import npzfile

from netCDF4 import Dataset

# In case we need the imports when using this module, placate pyflakes:
(days_to_date, date_to_days)

# temporary kluge: (first 5 characters are used for indexing)
tx_set = {'ecmwf': 'taux',
          'ecmwf_hope' : 'taux',
          'qscat': 'tx',
          'ccmp': 'u',
          'ccmp_monthly' : 'uwnd',
          'ascat': 'uwnd_stress'}

ty_set = {'ecmwf': 'tauy',
          'ecmwf_hope' : 'tauy',
          'qscat': 'ty',
          'ccmp': 'v',
          'ccmp_monthly' : 'vwnd',
          'ascat': 'vwnd_stress'}

ecmwf_url ='http://apdrc.soest.hawaii.edu:80/dods/public_data/Reanalysis_Data/ORA-S3/1x1_grid'
ecmwf2_url ='http://apdrc.soest.hawaii.edu:80/dods/public_data/Reanalysis_Data/ORA-S3/hope_vector'
qscat_url = 'http://apdrc.soest.hawaii.edu:80/dods/public_data/satellite_product/QSCAT/qscat_monthly'
ccmp_monthly_url = 'http://apdrc.soest.hawaii.edu:80/dods/public_data/satellite_product/CCMP/monthly_v2'
ccmp_url = 'http://apdrc.soest.hawaii.edu:80/dods/public_data/satellite_product/CCMP/6hourly_v2'
ascat_url = 'http://apdrc.soest.hawaii.edu:80/dods/public_data/satellite_product/ASCAT/daily'

urls = {'ecmwf': ecmwf_url,
        'ecmwf_hope': ecmwf2_url,
        'qscat': qscat_url,
        'ccmp': ccmp_url,
        'ccmp_monthly' : ccmp_monthly_url,
        'ascat': ascat_url,
        }

rho_air = 1.178 # kg m^{-3}
Cdrag = 1.2e-3
scalefacs = {'ecmwf': 1,
             'ecmwf_hope' : 1,
             'qscat': rho_air * Cdrag,
             'ccmp': 1,
             'ccmp_monthly' : 1,
             'ascat': 1}


class Wind(dict):
    """
    Provide access to variables from a wind product.
    """
    def __init__(self, dataset, lonrange, latrange):
        """
        time range, other options may be added later
        """
        dict.__init__(self)
        self.__dict__=self
        self.dataset = dataset
        dset = dataset
        self.lonrange = lonrange
        self.latrange = latrange
        cachefilename = "%s_%d_%d_%d_%d.cache.npz" % (dataset,
                                                     lonrange[0],
                                                     lonrange[1],
                                                     latrange[0],
                                                     latrange[1])


        try:
            d = npzfile.load(cachefilename)
            self.update(d)
            print("loaded from %s" % cachefilename)
        except (IOError, FileNotFoundError):
            #e = open_url(urls[dset])
            ncdataset = Dataset(urls[dset])
            e = ncdataset.variables
            # The following are the names of two "grid types".
            tx = tx_set[dset]
            ty = ty_set[dset]

            self.t = e['time'][:]

            alllat = e['lat'][:]
            latsl = rangeslice(alllat, latrange)
            self.lat = alllat[latsl]

            alllon = e['lon'][:]
            # For each extraction of a grid type, the data attribute
            # is a tuple in which the first entry is the data array,
            # and successive entries are the dimension variables.
            # Alternatively, accessing the array attribute and then
            # indexing into it extracts exactly what we want.
            if lonrange[0] < 0 and lonrange[1] > 0:
                lonsl1 = rangeslice(alllon, [lonrange[0]+360, 360])
                lonsl2 = rangeslice(alllon, [0, lonrange[1]])
                self.lon = np.concatenate((alllon[lonsl1], alllon[lonsl2]))
                #self.taux = np.concatenate((e[tx].array[:, latsl, lonsl1],
                #                       e[tx].array[:, latsl, lonsl2]), axis=-1)
                #self.tauy = np.concatenate((e[ty].array[:, latsl, lonsl1],
                #                       e[ty].array[:, latsl, lonsl2]), axis=-1)
                self.taux = np.concatenate((e[tx][:, latsl, lonsl1],
                                       e[tx][:, latsl, lonsl2]), axis=-1)
                self.tauy = np.concatenate((e[ty][:, latsl, lonsl1],
                                       e[ty][:, latsl, lonsl2]), axis=-1)
            else:
                lonsl = rangeslice(alllon, lonrange)
                #self.taux = e[tx].array[:, latsl, lonsl]
                #self.tauy = e[ty].array[:, latsl, lonsl]
                self.taux = e[tx][:, latsl, lonsl]
                self.tauy = e[ty][:, latsl, lonsl]
                self.lon = alllon[lonsl]

            if dset.startswith == 'ccmp':
                self.u = self.taux.copy()
                self.v = self.taux.copy()
                self.taux = self.taux**2 * Cdrag * rho_air
                self.tauy = self.tauy**2 * Cdrag * rho_air
            else:
                # FIXME: ECMWF ORA includes u and v, but we aren't reading them
                self.u = None
                self.v = None

            self.lon = unwrap(self.lon, centered=True)
            #self.badval = e[tx].attributes['missing_value']
            self.badval = e[tx].missing_value
            npzfile.savez(cachefilename, t=self.t,
                                 lon=self.lon, lat=self.lat,
                                 u=self.u, v=self.v,
                                 taux=self.taux, tauy=self.tauy,
                                 badval=self.badval)
            print("wrote %s" % cachefilename)
            ncdataset.close()

        scalefac = scalefacs[dset]
        self.taux = np.ma.masked_values(self.taux, self.badval)*scalefac
        self.tauy = np.ma.masked_values(self.tauy, self.badval)*scalefac

        # convenience for plotting
        self.X, self.Y = np.meshgrid(self.lon, self.lat)



def curl(lon, lat, taux, tauy):
    """
    Return midlon, midlat, curl(tau) based on first differences.

    N-D grids have shape  (..., nlat, nlon)
    """

    re = 6371e3
    latrad = np.deg2rad(lat)
    lonrad = np.deg2rad(lon)

    midlon = 0.5 * (lon[:-1] + lon[1:])
    midlat = 0.5 * (lat[:-1] + lat[1:])

    # See Vallis page 59.

    rfac = (1.0 / re) / np.cos(np.deg2rad(midlat))

    dvdlon = np.diff(tauy, axis=-1) / np.diff(lonrad)
    dvdlon = 0.5 * (dvdlon[..., 1:, :] + dvdlon[..., :-1, :])

    du = np.diff(taux * np.cos(latrad)[:,np.newaxis], axis=-2)
    dudlat = du / np.diff(latrad)[:, np.newaxis]
    dudlat = 0.5 * (dudlat[..., 1:] + dudlat[..., :-1])

    curltau = rfac[:, np.newaxis] * (dvdlon - dudlat)

    return midlon, midlat, curltau
