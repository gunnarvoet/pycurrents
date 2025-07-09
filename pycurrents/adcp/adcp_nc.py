"""
Functions for making shipboard adcp netcdf files: a short form
for analysis, a long form to approximately match the
CODAS database, and a compressed form for transferring data
from a ship.

The class can also be used from a script.
"""

import datetime
import argparse
import logging
# from hashlib import md5  # was used for trajectoryProfile
import numpy as np
from netCDF4 import Dataset

from pycurrents.codas import DB, ProcEns, masked_codas, CodasError
from pycurrents.adcp.uhdasfile import guess_dbname
from pycurrents.system import Bunch

# Standard logging
_log = logging.getLogger(__name__)

description = """Generate shipboard adcp netcdf file from a CODAS ADCP database.
One can generate a short form for analysis, and a long form to approximately
match the CODAS database."""
usage = """
adcp_nc.py dbpath outfilebase cruisetitle sonar
           [ -h] [--long | --compressed] [--dday_range DDAY_RANGE]
           [--ship_name SHIP_NAME [SHIP_NAME ...]]
           [--nc4]
eg.
    cd os38nb
    adcp_nc.py adcpdb  contour/os38nb  km1001c_demo os38nb

Test adcp_nc.py output with the standard netcdf command-line tool:

    ncdump -h outfile"""


dvtypes = {'float64':'f8',
           'float32':'f4',
           'uint8':'i2',
           'int16':'i2',
           'uint16':'i2',
           'int8':'i1'}

# For netcdf4 we can use uint8.
dvtypes4 = {'float64':'f8',
            'float32':'f4',
            'uint8':'u1',
            'int16':'i2',
            'uint16':'u2',
            'int8':'i1'}

# Data structure used in the make_short and make_compressed methods:
                            # long_name  units                format
short_vars = [
                ('depth',   ('Depth',
                                        'meter',              '%8.2f')),
                ('u',       ('Zonal velocity component',
                                        'meter second-1',     '%7.2f')),
                ('v' ,      ('Meridional velocity component',
                                        'meter second-1',     '%7.2f')),
                ('amp',     ('Received signal strength',
                                        "",                  '%d')),
                ('pg',      ('Percent good pings',
                                        "",                  '%d')),
                ('pflag',   ('Editing flags',
                                        "",                  '%d')),
                ('heading', ('Ship heading',
                                        'degrees',            '%6.1f')),
                ('tr_temp', ('ADCP transducer temperature',
                                        'degree_Celsius',      '%4.1f')),
                ('pgs_sample', ('Number of pings averaged per ensemble',
                                        "",            '%d')),
                ('uship',   ('Ship zonal velocity component',
                                        'meter second-1',     '%9.4f')),
                ('vship',   ('Ship meridional velocity component',
                                        'meter second-1',     '%9.4f'))]


def _CF_units(vname, db_units):
    """
    Substitute CF units for the units stored in the CODAS db.

    vname: The variable name that will be written to netcdf long format.
    db_units: The original units string from the db.
    """
    if db_units == "none":
        return ""
    if db_units != "deg":
        return db_units
    if "latitude" in vname:
        return "degrees_north"
    if "longitude" in vname:
        return "degrees_east"
    return "degrees"  # heading, pitch, etc.


class ADCP_nc:
    """
    Class to make netCDF files from a CODAS ADCP db.

    methods:

        make_short(filename)

        make_long(filename)

    """

    def __init__(self, dbname, cruise_id, inst_ping, attrlist=None,
                 allow_unsigned=True):
        '''
        dbname: path to database name
        cruise_id: netCDF global attribute
        inst_ping: netCDF global attribute
        optionally add global attributes via attrlist, a list of tuples,
           where each tuple is (attr_name , contents)

        *allow_unsigned* is True (default) permits unsigned integers to be used
        with NETCDF4.
        '''
        self.dbname = dbname
        self.cruise_id = cruise_id
        self.inst_ping = inst_ping
        self.allow_unsigned = allow_unsigned

        if attrlist is None:
            self.attrlist=[]
        else:
            self.attrlist = attrlist

        self.db = DB(dbname)
        self.nbins = self.db.get_nbins()

    def create_nc(self, filename, nbins=None, nprofs=None, format="NETCDF3_CLASSIC"):
        '''
        create the netCDF writer for filename (specify nbins, nprofs)

        '''

        nf = Dataset(filename, 'w', format=format)
        # format is stored in nf.data_model

        if nprofs is None:
            nprofs = self.db.nprofs

        if nbins is None:
            nbins = self.nbins

        nf.createDimension('time', nprofs)
        nf.createDimension('depth_cell', nbins)

        ## trajectoryProfile turns out not to be a good match for SADCP
        # tp = nf.createVariable('trajectory', 'i4', tuple()) #scalar
        # tp.cf_role = "trajectory_id"
        # tp.description = ("Trajectory ID: last 3.5 bytes of md5 hash "
        #                   "based on sampled times, "
        #                   "positions, cruise ID, instrument, and ping type")
        # tp.long_name = "Trajectory ID"
        # dbtxy = self.db.get_profiles(txy_only=True)
        # traj = b"".join([dbtxy[k].tobytes() for k in ("dday", "lon", "lat")]
        #                 + [s.encode('ascii') for s in (self.cruise_id, self.inst_ping)])
        # tp.assignValue(int(md5(traj).hexdigest()[-7:], base=16))

        # global attributes:

        # nf.featureType = "trajectoryProfile"

        utc = datetime.datetime.utcnow()
        nf.history = 'Created: %s' % utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        nf.Conventions = 'COARDS CF-1.8'
        nf.software = 'pycurrents'
        changeset = None
        try:
            from pycurrents.hg_status import installed
            lines = installed.split('\n')
            for line in lines:
                if line.startswith('changeset:'):
                    changeset = line.split()[1]
                    nf.hg_changeset = changeset
        except ImportError:
            _log.warning("Cannot import hg_status; skipping hg_changeset attribute.")
        else:
            if changeset is None:
                # (seems highly unlikely)
                _log.warning("Cannot find changeset in hg_status.installed;"
                            " skipping hg_changeset attribute.")

        nf.title = 'Shipboard ADCP velocity profiles'
        nf.summary = ('Shipboard ADCP velocity profiles '
                                + 'from %s using instrument %s'
                                    % (str(self.cruise_id), self.inst_ping))

        nf.cruise_id = str(self.cruise_id)
        nf.sonar = self.inst_ping
        nf.yearbase = np.int32(self.db.yearbase)

        # add optional global attributes at the top
        nf.setncatts(dict(self.attrlist))

        self.nf = nf

    def make_txy_vars(self):
        txy_vars = [ ('dday',  ('Decimal day',
                                'days since %s-01-01 00:00:00'
                                            % self.db.yearbase, '%12.5f')),
                     ('lon',   ('Longitude',   'degrees_east',   '%9.4f')),
                     ('lat',   ('Latitude',    'degrees_north',  '%9.4f')),
                   ]
        return txy_vars

    def add_array_var(self, vname, var, vdat, **varkw):
        allow_ubyte = self.nf.data_model == 'NETCDF4' and self.allow_unsigned
        dvdict = dvtypes4 if allow_ubyte else dvtypes
        vtype = dvdict[str(var.dtype)]
        if vname =='dday':
            ncvname = 'time'
        elif vname == 'pgs_sample':
            ncvname = 'num_pings'
        else:
            ncvname = vname

        dims = {1: ('time',), 2: ('time', 'depth_cell')}[var.ndim]

        # Translate uint8 to int16 when necessary.
        if not allow_ubyte and var.dtype.itemsize == 1 and var.dtype.kind == 'u':
            var = masked_codas(var.astype(np.int16))

        # Our CODAS-based missing value flags replace default _FillValue attrs;
        # this has to be done when the variable is created.
        fill_value = var.dtype.type(var.fill_value) if np.ma.isMA(var) else None
        x = self.nf.createVariable(ncvname, vtype, dims, fill_value=fill_value, **varkw)
        x[:] = var

        #attributes:
        x.long_name = vdat[0]
        if vdat[1] is not None:
            x.units = vdat[1]
        x.C_format = vdat[2]

        # if vname == 'depth':
        #     x.positive = "down"
        #     x.axis = 'Z'

        if vname == 'lon':
            x.standard_name = 'longitude'
            # x.axis = 'X'
        elif vname == 'lat':
            x.standard_name = 'latitude'
            # x.axis = 'Y'
        elif vname == 'dday':
            x.standard_name = 'time'
            x.calendar = 'proleptic_gregorian'
            x.axis = 'T'
            # x.cf_role = 'profile_id'

        if np.ma.count(var) == 0:
            x.data_min = x.data_max = x._FillValue
        else:
            if var.dtype.kind == 'f' and not np.ma.isMaskedArray(var):
                x.data_min = var.dtype.type(np.nanmin(var))
                x.data_max = var.dtype.type(np.nanmax(var))
            else:
                x.data_min = var.dtype.type(var.min())
                x.data_max = var.dtype.type(var.max())

    def _add_configs(self, ddrange=None):
        """
        Optional method of handling configurations, allowing for multiple
        configs.

        It would be possible to allow an optional input array with ping types.
        """
        # config name, nc name, units, long name:
        config1_params = {
            "avg_interval": ("ensemble_seconds", "s", "Ensemble average duration"),
            "num_bins": ("num_depth_bins", "", "Number of depth bins"),
            "tr_depth": ("transducer_depth", "m", "Transducer depth"),
            "bin_length": ("depth_bin_length", "m", "Vertical averaging length"),
            "pls_length": ("pulse_length", "m", "Vertical span of sonar ping"),
            "blank_length": ("blank_length", "m", "Vertical delay between ping and first reception"),
            "ping_interval": ("ping_interval", "s", "Typical time between pings"),
            "hd_offset": ("transducer_orientation", "degrees",
                          "Approximate transducer orientation,"
                           " clockwise rotation of beam 3 from forward"),
                           # Is it also beam 3 for the EC150?
                           # Or say, "clockwise rotation of nominally forward beam"?
        }

        bp_range = None if ddrange is None else self.db.get_range(ddrange)
        config = self.db.get_variable("configuration_1", r=bp_range)[list(config1_params.keys())]
        _c = np.hstack((np.zeros((1,), dtype=config.dtype), config))
        istart = np.nonzero(_c[:-1] != _c[1:])[0]
        num_configs = len(istart)
        self.nf.createDimension("num_configs", num_configs)
        var = self.nf.createVariable("index_config_start", np.int32,
                                     ("num_configs",))
        var[:] = istart
        var.long_name = "First zero-based time index of each configuration"
        var.units = ""
        for field, (dtype, _) in config.dtype.fields.items():
            new_name, units, long_name = config1_params[field]
            var = self.nf.createVariable(new_name, dtype, ("num_configs",))
            var[:] = config[field][istart]
            # attrs = {"long_name": long_name}
            #     attrs["units"] = units
            attrs = {"long_name": long_name, "units": units}
            var.setncatts(attrs)


    def make_short(self, filename, ddrange=None, format="NETCDF3_CLASSIC"):
        '''
        put commonly-used variables in a shorter netcdf file
        optionally extract only for a shorter time duration (short format only)
        '''
        self.pshort = self.db.get_profiles(nbins=self.nbins, ddrange=ddrange)
        self.pshort = ProcEns(self.pshort)  # applies flags, u-> rel to earth
        self.create_nc(filename, nbins = self.pshort.nbins,
                       nprofs=len(self.pshort.dday),
                       format=format)

        self.nf.summary += " - Short Version."

        _txy = {'dday', 'lon', 'lat'}
        for v in self.make_txy_vars() + short_vars:
            vname = v[0]
            vdat = v[1]
            var = self.pshort[vname]
            if vname in ('pg', 'pflag'):
                var = var.astype(np.int8)
            if vname in _txy:
                varkw = {}
            elif self.nf.data_model == "NETCDF4":
                # varkw = {"compression": "zlib"}  # preferred for netcdf 4.9
                # and later
                varkw = {"zlib": True}  # For ubuntu 20.04 and 22.04.
            self.add_array_var(vname, var, vdat, **varkw)
        self._add_configs(ddrange)

        self.nf.close()

    def make_compressed(self, filename, ddrange=None):
        '''
        put commonly-used variables in a compressed netcdf4 file
        optionally extract only for a shorter time duration (short format only)
        '''
        self.pshort = self.db.get_profiles(nbins=self.nbins, ddrange=ddrange)
        self.pshort = ProcEns(self.pshort)
        self.create_nc(filename, nbins = self.pshort.nbins,
                       nprofs=len(self.pshort.dday),
                       format="NETCDF4")

        _txy = {'dday', 'lon', 'lat'}
        for v in self.make_txy_vars() + short_vars:
            vname = v[0]
            vdat = v[1]
            var = self.pshort[vname]
            varkw = {}
            if vname not in _txy:
                # varkw['compression'] = 'zlib'
                varkw["zlib"] = True
                if var.dtype.kind == 'f':
                    lsd = 4 if vname == 'depth' else 3
                    varkw['least_significant_digit'] = lsd
                    var = np.ma.filled(var, np.nan)

            self.add_array_var(vname, var, vdat, **varkw)

        self.nf.close()

    def make_long(self, filename, format="NETCDF3_CLASSIC"):
        '''
        dump the whole database into a netcdf file
        '''
        # whole database, for long form
        self.p = self.db.get_profiles(nbins=self.nbins)
        self.create_nc(filename, format=format)

        self.nf.summary += " - Long Version."
        varkw = {}
        if self.nf.data_model == "NETCDF4":
            # varkw = {"compression": "zlib"}
            varkw = {"zlib": True}  # For ubuntu 20.04 and 22.04.

        for v in self.make_txy_vars():
            vname = v[0]
            vdat = v[1]
            var = self.p[vname]
            self.add_array_var(vname, var, vdat, **varkw)

        vars =  [('DEPTH', None),
                 ('U', 'U: Eastward water velocity relative to transducer'),
                 ('V', 'V: Northward water velocity relative to transducer'),
                 ('W', 'W: Approximate upward scatterer velocity relative to transducer'),
                 ('ERROR_VEL', None),
                 ('PROFILE_FLAGS', None),
                 ('AMP_SOUND_SCAT', None),
                 ('PERCENT_GOOD', None),
                 ('PERCENT_3_BEAM', None),
                 ('SPECTRAL_WIDTH', None),
                ]

        for v, long_name in vars:
            if long_name is None:
                long_name = v
            try:
                var = self.db.get_variable(v, nbins=self.nbins)
            except CodasError:
                _log.warning('Variable %s not found in %s', v, self.dbname)
                continue
            vname = v.lower()
            if vname.startswith('p'):
                var = var.astype(np.int8)
            if var.dtype.kind == 'f':
                fmt = '%9.4f'
            else:
                fmt = '%d'
            db_units = self.db.get_data_list_entry(v)['units']
            vdat = (long_name, _CF_units(vname, db_units), fmt)
            self.add_array_var(vname, var, vdat, **varkw)

        structs = [('ACCESS_VARIABLES', 'ACCESS'),
                   ('NAVIGATION', 'NAV'),
                   ('ANCILLARY_1', 'ANCIL1'),
                   ('ANCILLARY_2', 'ANCIL2'),
                   ('CONFIGURATION_1', 'CONFIG1'),
                   ('BOTTOM_TRACK', 'BT'),
                   ]

        # Making the structure variables takes about 90% of the
        # total runtime.
        for s, sn in structs:
            try:
                a = self.db.get_structure_def(s)
            except CodasError:
                _log.warning('Structure %s not found in %s', s, self.dbname)
                continue
            # need to be tested
            temp =  self.db.get_variable(s)
            for i in range(len(a)):
                sname = a[i]['name']
                if not sname or sname[0:2] =='un' or sname[0:4]=='user':
                    continue
                sunits = a[i]['units']
                var = temp[sname]
                longname = '__'.join([s, sname])
                sname = '_'.join([sn, sname])
                if var.dtype.kind == 'f':
                    fmt = '%9.4f'
                    var = masked_codas(var)
                else:
                    fmt = '%d'
                    if var.dtype.itemsize > 1:
                        var = masked_codas(var)
                units = _CF_units(sname, sunits)
                self.add_array_var(sname, var, (longname, units, fmt), **varkw)

        self.nf.close()


def make_nc_short(dbname, file_name, cruise_id, inst_ping,
                  ddrange=None, attrlist=None, format="NETCDF3_CLASSIC"):
    """
    Convenience function to make a short-form nc file.

    dbname: path to database name
    file_name: netCDF output file
    cruise_id: netCDF global attribute
    inst_ping: netCDF global attribute
    """

    a = ADCP_nc(dbname, cruise_id, inst_ping, attrlist=attrlist)
    a.make_short(file_name, ddrange=ddrange, format=format)
    add_domain_boundaries(file_name)
    add_attrdict(file_name, {'CODAS_variables': CODAS_short_variables,
                             'CODAS_processing_note': CODAS_processing_note})


def make_nc_compressed(dbname, file_name, cruise_id, inst_ping, ddrange,
                       attrlist=None):
    """
    Convenience function to make a short-form nc file.

    dbname: path to database name
    file_name: netCDF output file
    cruise_id: netCDF global attribute
    inst_ping: netCDF global attribute
    """
    a = ADCP_nc(dbname, cruise_id, inst_ping, attrlist=attrlist)
    a.make_compressed(file_name, ddrange=ddrange)


def make_nc_long(dbname, file_name, cruise_id, inst_ping, attrlist=None, format="NETCDF3_CLASSIC"):
    """
    Convenience function to make a long-form nc file.

    dbname: path to database name
    file_name: netCDF output file
    cruise_id: netCDF global attribute
    inst_ping: netCDF global attribute
    """

    a = ADCP_nc(dbname, cruise_id, inst_ping, attrlist=attrlist)
    a.make_long(file_name, format=format)
    add_domain_boundaries(file_name)
    add_attrdict(file_name, {'CODAS_variables': CODAS_long_variables,
                             'CODAS_processing_note': CODAS_processing_note})


def add_attrdict(file_name, attrdict):
    nc = Dataset(file_name, "r+")
    nc.setncatts(attrdict)
    nc.close()


def add_domain_boundaries(file_name):
    nc = Dataset(file_name, "r+")
    dday = nc["time"]
    epoch = np.datetime64(dday.units.split()[2])
    start = np.timedelta64(int(dday.data_min * 86400), "s") + epoch
    end = np.timedelta64(int(dday.data_max * 86400), "s") + epoch
    attdict = Bunch()
    attdict.time_coverage_start = str(start) + "Z"
    attdict.time_coverage_end = str(end) + "Z"
    attdict.geospatial_lat_min = nc["lat"].data_min.astype(np.float32)
    attdict.geospatial_lat_max = nc["lat"].data_max.astype(np.float32)
    attdict.geospatial_lat_units = "degrees_north"
    attdict.geospatial_lon_min = nc["lon"].data_min.astype(np.float32)
    attdict.geospatial_lon_max = nc["lon"].data_max.astype(np.float32)
    attdict.geospatial_lon_units = "degrees_east"
    attdict.geospatial_vertical_min = nc["depth"].data_min
    attdict.geospatial_vertical_max = nc["depth"].data_max
    # geospatial_vertical_resolution is not necessarily constant, so omit it
    attdict.geospatial_vertical_units = "m"
    attdict.geospatial_vertical_positive = "down"
    nc.setncatts(attdict)
    nc.close()


dbpath_help = """dbpath: path to the database, or just the
        processing directory (or 'adcpdb' directory) if there
        is only one database."""


def main():
    parser = argparse.ArgumentParser(description=description, usage=usage)
    parser.add_argument("dbpath", help=dbpath_help)
    parser.add_argument("outfile",
                        help="output netcdf file path (without '.nc')")
    parser.add_argument("cruise_id",
                       help='cruise title, used as part of the netcdf metadata')
    parser.add_argument("sonar", help="sonar: e.g., 'os75bb', 'wh300', 'nb150'")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--long",
                        help='write full CODAS DB dump instead of short form',
                        action="store_true")
    group.add_argument("--compressed",
                        help='write netcdf4 short form with lossy compression',
                        action="store_true")
    parser.add_argument("--dday_range",
                        help='colon-separated decimal day interval, only for\n'
                             '        short and compressed forms.\n'
                             '        E.g., "278.2:278.7" (no spaces).',
                        )
    parser.add_argument("--ship_name",
                        nargs='+',
                        help='Ship Name, used as part of the netcdf metadata',
                        default=None,
                        type=str,
                        )
    parser.add_argument("--nc4",
                        help="Use netcdf 4 with zlib compression",
                        action="store_true",
                        )

    args = parser.parse_args()
    dbpath    = guess_dbname(args.dbpath)
    outfile   = args.outfile
    if not outfile.endswith('.nc'):
        outfile += '.nc'
    cruise_id = args.cruise_id
    sonar     = args.sonar

    if args.dday_range:
        ddrange = [float(s) for s in args.dday_range.split(':')]
    else:
        ddrange = None

    if args.ship_name:
        ship_name = " ".join(args.ship_name)
        attrlist = [("platform", ship_name), ]
    else:
        attrlist = None

    format = "NETCDF4" if args.nc4 else "NETCDF3_CLASSIC"
    if args.long:
        make_nc_long(dbpath, outfile, cruise_id, sonar, attrlist=attrlist, format=format)
    elif args.compressed:
        make_nc_compressed(dbpath, outfile, cruise_id, sonar,
                           attrlist=attrlist, ddrange=ddrange)
    else:
        make_nc_short(dbpath, outfile, cruise_id, sonar,
                      attrlist=attrlist, ddrange=ddrange, format=format)
    _log.info('test your file by running \n\n  ncdump -h %s\n\n' % (outfile))


CODAS_short_variables = '''
Variables in this CODAS short-form Netcdf file are intended for most end-user
scientific analysis and display purposes. For additional information see
the CODAS_processing_note global attribute and the attributes of each
of the variables.


============= =================================================================
time          Time at the end of the ensemble, days from start of year.
lon, lat      Longitude, Latitude from GPS at the end of the ensemble.
u,v           Ocean eastward and northward velocity component profiles.
uship, vship  Eastward and northward velocity components of the ship.
heading       Mean ship heading during the ensemble.
depth         Bin centers in nominal meters (no sound speed profile correction).
tr_temp       ADCP transducer temperature.
pg            Percent Good pings after editing in vector-averaged velocities.
pflag         Profile Flags based on editing, used to mask velocities.
amp           Received signal strength in ADCP-specific units; no correction
              for spreading or attenuation.
============= =================================================================

'''


CODAS_long_variables = '''
Variables in this CODAS long-form netcdf file are taken directly from the
original CODAS database used in processing.  For additional information see
the CODAS_processing_note global attribute and the attributes of each
of the variables.

The term "bin" refers to the depth cell index, starting from 1
nearest the transducer.  Bin depths correspond to the centers of
the depth cells.

short_name                  description
---------                   --------------
time                      : Time at the end of the ensemble, days from start
                            of year.
lon, lat                  : Longitude, Latitude at the end of the ensemble.
u, v                      : Zonal and meridional velocity component profiles
                            relative to the moving ship, not to the earth.
w                         : Vertical velocity -- Caution: usually dominated by
                            ship motion and other artifacts.
error_vel                 : Error velocity -- diagnostic, scaled difference
                            between 2 estimates of vertical velocity (w).
amp_sound_scat            : Received signal strength (ADCP units; not corrected
                            for spreading or attenuation).
profile_flags             : Editing flags for averaged data.
percent_good              : Percentage of pings used for averaging u, v after
                            editing.
spectral_width            : Spectral width for NB instruments; correlation for
                            WH, BB, OS instruments.

CONFIG1_tr_depth          : Transducer depth, meters.
CONFIG1_top_ref_bin       : Reference layer averaging: top bin.
CONFIG1_bot_ref_bin       : Reference layer averaging: bottom bin.
CONFIG1_pls_length        : Pulse length projected on vertical (meters).
CONFIG1_blank_length      : Blank length (vertical; meters).
CONFIG1_bin_length        : Bin length (vertical; meters).
CONFIG1_num_bins          : Number of bins.
CONFIG1_ping_interval     : Approximate mean time between pings or ping groups.
CONFIG1_hd_offset         : Transducer azimuth approximation prior to
                            data processing, clockwise rotation of beam 3 from
                            forward.
CONFIG1_freq_transmit     : Nominal (round number) instrument frequency.
CONFIG1_ev_threshold      : Error velocity editing threshold (if known).
CONFIG1_bot_track         : Flag: does any bottom track data exist?
CONFIG1_avg_interval      : Ensemble-averaging interval (seconds).

BT_u                      : Eastward ship velocity from bottom tracking.
BT_v                      : Northward ship velocity from bottom tracking.
BT_depth                  : Depth from bottom tracking.

ANCIL2_watrk_scale_factor : Scale factor; multiplier applied to measured
                            velocity.
ANCIL2_watrk_hd_misalign  : Azimuth correction used to rotate measured
                            velocity.
ANCIL2_botrk_scale_factor : Scale factor for bottom tracking.
ANCIL2_botrk_hd_misalign  : Azimuth correction for bottom tracking.
ANCIL2_mn_roll            : Ensemble-mean roll.
ANCIL2_mn_pitch           : Ensemble-mean pitch.
ANCIL1_mn_heading         : Ensemble-mean heading.
ANCIL1_tr_temp            : Ensemble-mean transducer temperature.
ANCIL2_std_roll           : Standard deviation of roll.
ANCIL2_std_pitch          : Standard deviation of pitch.
ANCIL2_std_heading        : Standard deviation of heading.
ANCIL2_std_temp           : Standard deviation of transducer temperature.
ANCIL2_last_roll          : Last measurement of roll in the ensemble.
ANCIL2_last_pitch         : Last measurement of pitch.
ANCIL2_last_heading       : Last measurement of heading.
ANCIL2_last_temp          : Last measurement of transducer temperature.
ANCIL2_last_good_bin      : Deepest bin with good velocities.
ANCIL2_max_amp_bin        : Bin with maximum amplitude based on bottom-
                            detection, if the bottom is within range.
ANCIL1_snd_spd_used       : Sound speed used for velocity calculations.
ANCIL1_pgs_sample         : Number of pings averaged in the ensemble.

ACCESS_last_good_bin      : Last bin with good data. (-1 if the entire profile
                            is bad.)
ACCESS_first_good_bin     : First bin with good data.
ACCESS_U_ship_absolute    : Ship's mean eastward velocity component.
ACCESS_V_ship_absolute    : Ship's mean northward velocity component.

The following historical variables are not currently used.
----------------------------------------------------------
NAV_speed                 :
NAV_longitude             :
NAV_latitude              :
NAV_direction             :

CONFIG1_rol_offset        :
CONFIG1_pit_offset        :
CONFIG1_compensation      :
CONFIG1_pgs_ensemble      :  Number of pings averaged in the instrument;
                             always 1 for SADCP.
CONFIG1_heading_bias      :  Only relevant for narrowband ADCP data
                             collected with DAS2.48 or earlier (MS-DOS).
CONFIG1_ens_threshold     :

ANCIL2_rol_misalign       :
ANCIL2_pit_misalign       :
ANCIL2_ocean_depth        :
ANCIL1_best_snd_spd       :

percent_3_beam            : This may have different meanings depending on
                            the data acquisition system, processing method,
                            and software versions; it is not useful without
                            this context.

.............................................................................

'''


CODAS_processing_note = '''
CODAS processing note:
======================

Overview
--------
The CODAS database is a specialized storage format designed for
shipboard ADCP data.  "CODAS processing" uses this format to hold
averaged shipboard ADCP velocities and other variables, during the
stages of data processing.  The CODAS database stores velocity
profiles relative to the ship as east and north components along with
position, ship speed, heading, and other variables. The netCDF *short*
form contains ocean velocities relative to earth, time, position,
transducer temperature, and ship heading; these are designed to be
"ready for immediate use".  The netCDF *long* form is just a dump of
the entire CODAS database.  Some variables are no longer used, and all
have names derived from their original CODAS names, dating back to the
late 1980's.

Post-processing
---------------
CODAS post-processing, i.e. that which occurs after the single-ping
profiles have been vector-averaged and loaded into the CODAS database,
includes editing (using automated algorithms and manual tools),
rotation and scaling of the measured velocities, and application of a
time-varying heading correction.  Additional algorithms developed more
recently include translation of the GPS positions to the transducer
location, and averaging of ship's speed over the times of valid pings
when Percent Good is reduced. Such post-processing is needed prior to
submission of "processed ADCP data" to JASADCP or other archives.

Full CODAS processing
---------------------
Whenever single-ping data have been recorded, full CODAS processing
provides the best end product.

Full CODAS processing starts with the single-ping velocities in beam
coordinates.  Based on the transducer orientation relative to the
hull, the beam velocities are transformed to horizontal, vertical, and
"error velocity" components.  Using a reliable heading (typically from
the ship's gyro compass), the velocities in ship coordinates are
rotated into earth coordinates.

Pings are grouped into an "ensemble" (usually 2-5 minutes duration)
and undergo a suite of automated editing algorithms (removal of
acoustic interference; identification of the bottom; editing based on
thresholds; and specialized editing that targets CTD wire interference
and "weak, biased profiles".  The ensemble of single-ping velocities
is then averaged using an iterative reference layer averaging scheme.
Each ensemble is approximated as a single function of depth, with a
zero-average over a reference layer plus a reference layer velocity
for each ping.  Adding the average of the single-ping reference layer
velocities to the function of depth yields the ensemble-average
velocity profile.  These averaged profiles, along with ancillary
measurements, are written to disk, and subsequently loaded into the
CODAS database. Everything after this stage is "post-processing".

note (time):
------------
Time is stored in the database using UTC Year, Month, Day, Hour,
Minute, Seconds.  Floating point time "Decimal Day" is the floating
point interval in days since the start of the year, usually the year
of the first day of the cruise.


note (heading):
---------------
CODAS processing uses heading from a reliable device, and (if
available) uses a time-dependent correction by an accurate heading
device.  The reliable heading device is typically a gyro compass (for
example, the Bridge gyro).  Accurate heading devices can be POSMV,
Seapath, Phins, Hydrins, MAHRS, or various Ashtech devices; this
varies with the technology of the time.  It is always confusing to
keep track of the sign of the heading correction.  Headings are written
degrees, positive clockwise. setting up some variables:

X = transducer angle (CONFIG1_heading_bias)
    positive clockwise (beam 3 angle relative to ship)
G = Reliable heading (gyrocompass)
A = Accurate heading
dh = G - A = time-dependent heading correction (ANCIL2_watrk_hd_misalign)

Rotation of the measured velocities into the correct coordinate system
amounts to (u+i*v)*(exp(i*theta)) where theta is the sum of the
corrected heading and the transducer angle.

theta = X + (G - dh) = X + G - dh


Watertrack and Bottomtrack calibrations give an indication of the
residual angle offset to apply, for example if mean and median of the
phase are all 0.5 (then R=0.5).  Using the "rotate" command,
the value of R is added to "ANCIL2_watrk_hd_misalign".

new_dh = dh + R

Therefore the total angle used in rotation is

new_theta = X + G - dh_new
          = X + G - (dh + R)
          = (X - R) + (G - dh)

The new estimate of the transducer angle is: X - R
ANCIL2_watrk_hd_misalign contains: dh + R

====================================================

Profile flags
-------------
Profile editing flags are provided for each depth cell:

binary    decimal    below    Percent
value     value      bottom   Good       bin
-------+----------+--------+----------+-------+
000         0
001         1                            bad
010         2                  bad
011         3                  bad       bad
100         4         bad
101         5         bad                bad
110         6         bad      bad
111         7         bad      bad       bad
-------+----------+--------+----------+-------+
'''
