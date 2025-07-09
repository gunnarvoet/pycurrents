"""
Constants, formulae, etc. related to ocean dynamics and waves.

Experimental and embryonic...

"""
import numpy as np

sidereal_day = 86400/1.00273790935
R_earth = 6371000.0 # radius of sphere with earth's volume; Gill, 1982

seconds_per_year = 86400 * 365.25

def coriolis(lat):
    """
    Coriolis parameter in s^-1
    """
    return (4 * np.pi / sidereal_day) * np.sin(np.deg2rad(lat))

def inertial_days(lat):
    """
    Inertial period in days
    """
    return (2 * np.pi / (coriolis(lat) * 86400))

def beta(lat):
    return ((4 * np.pi / sidereal_day) / R_earth) * np.cos(np.deg2rad(lat))

def k_from_wavelength_km(length):
    """
    Given wavelength in km, return wavenumber in m^-1
    """
    return (2 * np.pi / (length * 1000))

class Rossby:
    """
    Mid-latitude Rossby wave dispersion relation.
    """
    def __init__(self, lat, k, l=0, c=3):
        """
        *lat* is latitude in degrees
        *k* is zonal wavenumber in radians/m
        *l* is meridional wavenumber; defaults to 0
        *c* is gravity wave speed; defaults to 3 m/s

        Inputs may be scalars or arrays, but must be mutually
        broadcastable.

        Because phase propagation is always westward, the zonal
        wavenumber input is converted to a negative number
        so that the frequency will always be positive.
        """
        self.lat = lat
        self.k = -np.abs(k)
        self.l = l
        self.c = c
        self.f = coriolis(lat)
        self.beta = beta(lat)
        self.radius = c / self.f

    @property
    def frequency(self):
        omega = -self.beta * self.k / (self.k**2 + self.l**2 + self.radius**-2)
        return omega


    @property
    def period_years(self):
        return (2 * np.pi / (self.frequency * seconds_per_year))

    @property
    def cycles_per_year(self):
        return 1.0 / self.period_years

    # to be continued...


