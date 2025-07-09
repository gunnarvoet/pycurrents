# BREADCRUMB: common library
# FIXME - TR: based on adcpgui/cplotter.py...should be moved into a common lib

import sys
import os
import logging
import numpy as np
from netCDF4 import Dataset
from datetime import datetime, timedelta

# BREADCRUMB: common library...
from pycurrents.system.logutils import unexpected_error_msg
from pycurrents.system import Bunch
from pycurrents.codas import get_profiles, get_txy, CodasRangeError
from pycurrents.adcp.pingedit import BottomEdit
from pycurrents.adcp.pingedit import ThresholdEdit
from pycurrents.adcp.pingedit import ProfileEdit, get_jitter
from pycurrents.adcp.reader import calculate_fp
from pycurrents.file.mfile import m_to_dict
from pycurrents.num.int1 import interp1
from pycurrents.data import navcalc
# BREADCRUMB: ...end of common library
from pycurrents.adcpgui_qt.presenter.intercommunication import get_dbparam
from pycurrents.adcpgui_qt.lib.plotting_parameters import (
    FLAG_COLOR_PLOT_LIST, COMPARE_PREFIX)
from pycurrents.adcpgui_qt.lib.miscellaneous import blank_function



# Standard logging
_log = logging.getLogger(__name__)

# Global parameters
HMIN = 0.0  # 0 North, positive clockwise, range[0, 360]

# TODO: aggregate var names and such and connect to adcp_nc.py
# Note: Tuple Format = (CData attribute name, NetCDF variable name)
VAR_EQUIVALENCES = [
    # - Vars. common to short and long netcdf files
    ('dday',                'time'),
    ('lon',                 'lon'),
    ('lat',                 'lat'),
    ('depth',               'depth'),
    ('u',                   'u'),
    ('v',                   'v'),
    ('w',                   'w'),
    # - Short-netcdf specific vars.
    ('uship',               'uship'),
    ('vship',               'vship'),
    ('heading',             'heading'),
    ('pg',                  'pg'),
    ('pflag',               'pflag'),
    ('amp',                 'amp'),
    ('tr_temp',             'tr_temp'),
    ('numpings',            'num_pings'),
    # - Short netcdf var. equivalences in Long netcdf
    ('pg',                  'percent_good'),
    ('pflag',               'profile_flags'),
    ('amp',                 'amp_sound_scat'),
    ('heading',             'ANCIL1_mn_heading'),
    ('tr_temp',             'ANCIL1_tr_temp'),
    ('num_pings',           'ANCIL1_pgs_sample'),
    ('uship',               'ACCESS_U_ship_absolute'),
    ('vship',               'ACCESS_V_ship_absolute'),
    # - Long netcdf config. param. & vars.
    #  * Config params
    ('num_bins',            'CONFIG1_num_bins'),
    #  * Vars.
    ('u_bt',                'BT_u'),
    ('v_bt',                'BT_v'),
    ('d_bt',                'BT_depth'),
    ('e',                   'error_vel'),
    ('swcor',               'spectral_width'),
    ('pgs_sample',          'ANCIL1_pgs_sample'),
    ('snd_spd_used',        'ANCIL1_snd_spd_used'),
    ('best_snd_spd',        'ANCIL1_best_snd_spd'),
    ('watrk_hd_misalign',   'ANCIL2_watrk_hd_misalign'),
    ('watrk_scale_factor',  'ANCIL2_watrk_scale_factor'),
    ('botrk_hd_misalign',   'ANCIL2_botrk_hd_misalign'),
    ('botrk_scale_factor',  'ANCIL2_botrk_scale_factor'),
    ('last_temp',           'ANCIL2_last_temp'),
    ('last_heading',        'ANCIL2_last_heading'),
    ('mn_pitch',            'ANCIL2_mn_pitch'),
    ('mn_roll',             'ANCIL2_mn_roll'),
    ('std_pitch',           'ANCIL2_std_pitch'),
    ('std_roll',            'ANCIL2_std_roll'),
    ('lon_raw',             'NAV_longitude'),
    ('lat_raw',             'NAV_latitude'),
]


class CodasCore:
    """
    Provides access to ADCP data from a CODAS database or
    compatible NetCDF files.

    This also serves as the base class for subclasses that
    include editing, or that provide the difference between
    two databases.

    Properties are used so that multiple requests for the
    same time range access the database only once.
    """
    def __init__(self, db_path, options):
        # if not options.netcdf:
        """
        CODAS database model in view model.

        Args:
            db_path: path to CODAS database (where *.blk are located), str.
            options: list of options, ArgumentParser object.
        """
        # Attributes
        self.mode = options.mode
        self.netcdf = options.netcdf
        self.dbparam = get_dbparam(db_path, options)
        if self.dbparam['dbpathname'] is None:
            raise ValueError("dbpathname is a required argument")
        self.dbpathname = self.dbparam['dbpathname']
        self.yearbase = self.dbparam['yearbase']
        self.codasMask = np.zeros((), dtype=bool)
        self.xlim = []
        # - add attributes from all elements in options and db_params - Legacy
        self.__dict__.update(self.dbparam)
        # - database switch: CODAS or Netcdf
        if not self.netcdf:
            self.get_data = self._get_data_codas
            data = get_txy(self.dbpathname)
            # - available time range:
            self.startdd_all = data.dday[0]
            self.enddd_all = data.dday[-1]
            if self.yearbase is None:
                self.yearbase = data.yearbase
        else:
            self.get_data = self._get_data_netcdf
            self.netcdf_dataset = Dataset(self.dbpathname, mode='r')
            # There should be no missing values in the time array.
            self.netcdf_dataset["time"].set_auto_mask(False)
            # - available time range:
            self.startdd_all = float(self.netcdf_dataset.variables['time'][0])
            self.enddd_all = float(self.netcdf_dataset.variables['time'][-1])
            if self.yearbase is None:
                self.yearbase = self.netcdf_dataset.yearbase
        # Hidden/Backend Attributes
        self._data = None
        self._last_range = tuple()
        self._startdd = self.startdd_all
        self._ddstep = None

    def _get_data_codas(self, newdata=False):
        """
        Return the requested data structure, or None if the
        requested range is not available or any error occurs.

        Note: CODAS database

        Args:
            newdata: if True, override to the _data and _last_range mechanisms
                     uvship_from_lonlat calculates uship,vship and uses them
                     for ocean u,v.

        Returns: structured ADCP data
        """
        if not newdata:
            if self._data is not None:
                return self._data
        # double check if really new data extraction needed
        ddrange = (self._startdd, self._startdd+self._ddstep)
        if not newdata:
            if ddrange == self._last_range:
                return self._data  # Already extracted this range
        # Ticket 626
        self.xlim = ddrange
        self._last_range = ddrange
        try:
            data = get_profiles(self.dbpathname,
                                ddrange=ddrange,
                                diagnostics=True,
            # FIXME: use_bt not declared...needs more testing before release
                                use_bt=0)  # self.use_bt)
            # additional variables and reformatting
            data.numpings = data.pgs_sample
            data.jitter = get_jitter(data)
            data.heading = ((data.heading - HMIN + 360) % 360) + HMIN
        # FIXME: should write the same msg on screen, instead 'no data found'
        except CodasRangeError:
            _log.info("Requested range %s is outside available range [%s, %s]"
                     % (ddrange, self.startdd_all, self.enddd_all))
            self._data = None
            return None
        except Exception as e:  # FIXME: too vague! What is the actual exception?
            # Ticket 626
            self._data = None
            _log.warning("Unknown exception in get_data; data set to None")
            _log.debug("dbpathname: %s" % self.dbpathname)
            _log.debug("ddrange: [%s, %s]" % ddrange)
            _log.warning(unexpected_error_msg(e))
            return None
        try:
            # Scaled to mm/s to match traditional threshold specifications.
            # FIXME: maybe convert thresholds to m/s.
            data.unflag(vars=['w', 'e'])
            data.w *= 1000.0
            data.e *= 1000.0
            data.e_std *= 1000.0
            data.apply_flags(vars=['w', 'e'])
            if hasattr(data, 'resid_stats'):
                data.resid_stats_fwd = data.resid_stats['ff'] * 1000.0
            if len(data.dday) <= 2:
                msg = '%d profiles found' % (len(data.dday))
                data = None
                _log.info(msg + "; data set to None")
        except Exception as e:  # FIXME: too vague! What is the actual exception?
            data = None
            _log.warning(unexpected_error_msg(e))
        self._data = data
        return data

    def _get_data_netcdf(self, newdata=False):
        """
        Return the requested data structure, or None if the
        requested range is not available or any error occurs.

        Note: Netcdf database

        Args:
            newdata: if True, override to the _data and _last_range mechanisms
                     uvship_from_lonlat calculates uship,vship and uses them
                     for ocean u,v.

        Returns: structured ADCP data
        """
        if not newdata:
            if self._data is not None:
                return self._data
        # double check if really new data extraction needed
        ddrange = (self._startdd, self._startdd+self._ddstep)
        if not newdata:
            if ddrange == self._last_range:
                return self._data  # Already extracted this range
        # Ticket 626
        self.xlim = ddrange
        self._last_range = ddrange
        try:
            # Using Bunch as data container
            data = Bunch()
            # Find indices within ddrange
            start_ind = (np.abs(
                self.netcdf_dataset['time'][:] - ddrange[0])).argmin()
            end_ind = (np.abs(
                self.netcdf_dataset['time'][:] - ddrange[1])).argmin()
            if end_ind < start_ind:
                _log.info("Requested range %s is outside available range [%s, %s]"
                         % (ddrange, self.startdd_all, self.enddd_all))
                self._data = None
                return None

            time_slice = slice(start_ind, end_ind)
            # Fetch all required data
            names = []
            for uhdas_name, nc_name in VAR_EQUIVALENCES:
                if nc_name not in self.netcdf_dataset.variables:
                    continue
                try:
                    # - Extract time slice
                    data[uhdas_name] = self.netcdf_dataset[nc_name][time_slice]
                    names.append(uhdas_name)
                    _data = data[uhdas_name]
                    if np.ma.isMA(_data):
                        _data = np.ma.masked_invalid(_data)
                        # Apparently for historical data sets...
                        _data = np.ma.masked_greater(_data, 1e30)
                except IndexError:
                    # in case of config. params and others scalars
                    data[uhdas_name] = self.netcdf_dataset[nc_name]
                    names.append(uhdas_name)

            # Extra attributes for backend compatibility
            # FIXME: use_bt not declared...needs more testing before release
            # data['use_bt_for_shipspeed'] = self.use_bt
            data['names'] = list(set(names))
            data['yearbase'] = self.netcdf_dataset.yearbase

            # Derived attributes for backend compatibility
            data['nprofs'] = end_ind - start_ind
            data['nbins'] = self.netcdf_dataset['u'].shape[1]
            ymdhms = np.zeros((data.nprofs, 6))
            for ii, dday in enumerate(data.dday):
                d = datetime(data.yearbase, 1, 1) + timedelta(dday)
                ymdhms[ii, :] = list(d.timetuple())[:6]
            data['ymdhms'] = ymdhms
            data['dep'] = data.depth[0]
            data['bins'] = np.arange(data.nbins, dtype=int) + 1
            data['spd'] = np.ma.sqrt(data.uship ** 2 + data.vship ** 2)
            dx, dy = navcalc.diffxy_from_lonlat(data.lon, data.lat)
            data['cog'] = np.ma.remainder(
                90 - np.ma.arctan2(dy, dx) * 180 / np.pi + 360, 360)
            data.jitter = get_jitter(data)
            data.e_std = 0*data['u']

            # Additional variables and reformatting are needed for long netcdf
            if 'lon_raw' in names:
                # - u, v are actually u_meas, v_meas
                data['u'] = data.uship[:, np.newaxis] + data.u
                data['v'] = data.vship[:, np.newaxis] + data.v
                # - then one can calculated port and forward speeds
                data['fvel'], data['pvel'] = calculate_fp(data.u, data.v,
                                                          data.heading)
                # - into mm/s to match traditional threshold specifications.
                if 'w' in data.keys():
                    data.w *= 1000.0
                if 'e' in data.keys():
                    data.e *= 1000.0

            # Change angle convention
            data.heading = ((data.heading - HMIN + 360) % 360) + HMIN

            # Fake methods for compatibility sake
            data['unflag'] = blank_function
            data['apply_flags'] = blank_function

        except Exception as e:  # FIXME: too vague! What is the actual exception?
            data = None
            _log.warning(unexpected_error_msg(e))

        self._data = data
        return data

    # Dynamic attributes
    @property
    def data(self):
        return self.get_data()


class CData(CodasCore):
    """
    Provides access to ADCP data from a CODAS database.

    This also serves as the base class for subclasses that
    include editing, or that provide the difference between
    two databases.

    Properties are used so that multiple requests for the
    same time range access the database only once.
    """
    def __init__(self, db_path, options):
        """
        CODAS database model in view model.

        Args:
            db_path: path to CODAS database (where *.blk are located), str.
            options: list of options, ArgumentParser object.
        """
        super().__init__(db_path, options)

    def set_startdd(self, startdd):
        """
        Set decimal starting day

        Args:
            startdd: decimal day, float
        """
        if abs(startdd - self._startdd) <= 3e-2:  # FIXME:  Is this too coarse?
            return
        self._startdd = startdd
        self._data = None

    def get_startdd(self):
        """Return decimal starting day, float"""
        return self._startdd

    def set_ddstep(self, ddstep):
        """
        Set decimal-day time-step

        Args:
            ddstep: time step in decimal day, float
        """
        if ddstep == self._ddstep:
            return
        self._ddstep = ddstep
        self._data = None

    def get_ddstep(self):
        """Return time-step in decimal-day """
        return self._ddstep

    def fix_flags(self, masking):
        """
        Mask or unmask staged edits accordingly with the chosen masking mode.

        Args:
            masking: masking mode, str., "no flags", "low pg" or "codas"
        """
        self.data.unflag()
        if masking in (1, 'codas'):
            self.data.apply_flags(vars=FLAG_COLOR_PLOT_LIST)

    # FIXME: do I need this method?
    def set_grid1D(self, ylim=None, use_bins=False):
        """
        Define Ye and Xe (depth and time coordinates at edges) as well as
        Yc and Xc (depth and time coordinates at centers) CData attributes

        Args:
            ylim: y axis limits, [y min., y max.], list
            use_bins: if True, y axis in bins else in meters
        """
        # Time coordinates
        x = self.data.dday.copy()
        dx = x[1] - x[0]
        xE = np.insert(x, 0, x[0] - dx)  # x at edges
        xC = 0.5 * (xE[1:] + xE[:-1])  # x at centers
        # Depth coordinates
        if use_bins is True:
            self.yname = 'bins'
            yE = np.arange(self.data.nbins+1, dtype=float)
            self.ylim = [self.data.nbins+1, 0]
        else:
            self.yname = 'meters'
            d = self.data.dep
            dy = 0.5*(d[1:] - d[:-1])
            yE = np.empty((len(d)+1,), dtype=type(d[0]))
            yE[0] = d[0] - dy[0]
            yE[1:-1] = d[1:] + dy
            yE[-1] = yE[-2] + dy[-1]
            if ylim is not None:
                self.ylim = ylim
            else:
                self.ylim = [np.max(self.data.dep), 0]
            yC = 0.5 * (yE[1:] + yE[:-1])
        # Gridded coordinates
        self.Ye, self.Xe = np.meshgrid(yE, xE)  # x at edges
        self.Yc, self.Xc = np.meshgrid(yC, xC)  # x at centers
        # Define codas mask
        self.codasMask = np.ma.getmask(self.data.u)

    def set_grid(self, ylim=None, use_bins=False):
        """
        Use full depth array
        Add one timestamp to the end and one bin (or depth) to the bottom.
        Define Ye, Xe, Xc, yc, xb and yb attributes

        Args:
            ylim: y axis limits, [y min., y max.], list
            use_bins: if True, y axis in bins else in meters
        """
        # Time coordinates
        d = self.data.depth
        nprofs, nbins = d.shape
        x = self.data.dday.copy()
        dx = x[1] - x[0]
        xE = np.insert(x, 0, x[0] - dx)  # x at edges
        xC = 0.5 * (xE[1:] + xE[:-1])  # x at centers
        # Depth coordinates
        yE = np.arange(nbins + 1, dtype=type(d[0, 0]))
        yC = 0.5 * (yE[1:] + yE[:-1])
        # Grid coordinates
        self.Ye, self.Xe = np.meshgrid(yE, xE)
        self.Yc, self.Xc = np.meshgrid(yC, xC)
        if use_bins is True:
            self.yname = 'bins'
            self.ylim = [nbins + 1, 0]
        else:
            self.yname = 'meters'
            # override Yc & Ye
            self.Ye = np.zeros((nprofs+1, nbins+1), dtype=type(d[0,0]))
            self.Ye[1:, 1:] = d
            self.Ye[0, 1:] = d[0, :] - np.ma.median(np.diff(d, axis=1))
            self.Ye[:, 0] = 2.0 * self.Ye[:, 1] - self.Ye[:, 2]
            self.Yc = 0.5 * (self.Ye[1:, 1:] + self.Ye[:-1, :-1])
            # TR = correction
            self.Yc[0, :] = self.Yc[1, :]

            if ylim is not None:
                self.ylim = ylim
            else:
                self.ylim = [np.max(d), 0]
        # Define codas mask
        self.codasMask = np.ma.getmask(self.data.u)

    def argnearest_centered_index(self, point, use_masked_coordinates=True):
        """
        Returns index of the nearest centered coordinates to given point
        Args:
            point: given coordinates, (x, y), tuple
            use_masked_coordinates: if true, finds nearest index even if masked

        Returns: array indices, tuple
        """
        xClicked, yClicked = point
        # Normalize coordinates
        xc_min = np.nanmin(self.Xc)
        xc_max = np.nanmax(self.Xc)
        xc_range = xc_max - xc_min
        yc_min = np.nanmin(self.Yc)
        yc_max = np.nanmax(self.Yc)
        yc_range = yc_max - yc_min
        x_relative = (self.Xc - xc_min) / xc_range
        y_relative = (self.Yc - yc_min) / yc_range
        xClicked_relative = (xClicked - xc_min) / xc_range
        yClicked_relative = (yClicked - yc_min) / yc_range
        x = x_relative - xClicked_relative
        y = y_relative - yClicked_relative

        # Computing distances
        if use_masked_coordinates:
            distance = np.ma.masked_array(np.sqrt(np.square(x) + np.square(y)),
                                          mask=self.codasMask)
            min_dist = np.ma.MaskedArray.min(distance)
            index2D = np.ma.where(distance == min_dist)
        else:
            distance = np.sqrt(np.square(x) + np.square(y))
            min_dist = np.min(distance)
            index2D = np.where(distance == min_dist)
        # FIXME: Quick fix when nb. bin changes part way through the dataset
        if index2D[0].shape[0] > 1 or index2D[1].shape[0] > 1:
            xIndex = index2D[0][-1]  # N.B. always composed of the same index
            yIndices = index2D[1]
            y = (self.Yc[xIndex, yIndices] - yClicked)
            if use_masked_coordinates:
                distance = np.ma.masked_array(np.sqrt(np.square(y)),
                                              mask=self.codasMask)
                min_dist = np.ma.MaskedArray.min(distance)
                yIndex = np.ma.where(distance == min_dist)
            else:
                distance = np.sqrt(np.square(y))
                min_dist = np.min(distance)
                yIndex = np.where(distance == min_dist)
            return tuple([np.asarray(xIndex), np.asarray(yIndex)])
        else:
            return index2D

    def argnearest_edge_index(self, point, use_masked_coordinates=True):
        """
        Returns index of the nearest edge coordinates to given point
        Args:
            point: given coordinates, (x, y), tuple
            use_masked_coordinates: if true, finds nearest index even if masked

        Returns: array indices, tuple
        """
        xClicked, yClicked = point

        # Normalize coordinates
        xe_min = np.nanmin(self.Xe)
        xe_max = np.nanmax(self.Xe)
        xe_range = xe_max - xe_min
        ye_min = np.nanmin(self.Ye)
        ye_max = np.nanmax(self.Ye)
        ye_range = ye_max - ye_min
        x_relative = (self.Xe - xe_min) / xe_range
        y_relative = (self.Ye - ye_min) / ye_range
        xClicked_relative = (xClicked - xe_min) / xe_range
        yClicked_relative = (yClicked - ye_min) / ye_range
        x = x_relative - xClicked_relative
        y = y_relative - yClicked_relative

        # Computing distances
        if use_masked_coordinates:
            distance = np.ma.masked_array(np.sqrt(np.square(x) + np.square(y)),
                                          mask=self.codasMask)
            min_dist = np.ma.MaskedArray.min(distance)
            index2D = np.ma.where(distance == min_dist)
        else:
            distance = np.sqrt(np.square(x) + np.square(y))
            min_dist = np.min(distance)
            index2D = np.where(distance == min_dist)

        return index2D

    # Dynamic attributes
    startdd = property(get_startdd, set_startdd)
    ddstep = property(get_ddstep, set_ddstep)


class CDataEdit(CData):
    def __init__(self, thresholds, db_path, options):
        """
        Subclass of CData, with editing parameters added
        Provides methods for BottomEdit, ThresholdEdit, ProfileEdit

        Args:
            thresholds: singleton containing thresholds info., Bunch
            db_path: path to CODAS database (where *.blk are located), str.
            options: list of options, ArgumentParser object
        """
        # Inherit from CDdata
        super().__init__(db_path, options)
        # PFC: Profile Flag Cutoffs, dictionary with key, value pairs
        self.thresholds = thresholds  # direct to threshold singleton
        self.default_thresholds = thresholds.default_values
        if self.beamangle is None:
            if os.path.exists('asetup.m'):
                with open('asetup.m') as newreadf:
                    asetup_str = newreadf.read()
                asetup_dict = m_to_dict(asetup_str)
                if 'config.beamangle' in list(asetup_dict.keys()):
                    self.beamangle = asetup_dict['config.beamangle']

            msg = '\n'.join(
                [ '', 'beam angle not set.  easiest solution:',
                  '', 'call dataviewer.py with --beamangle option'])
            _log.error(msg)
            sys.exit(1)

        # Thresholds editing objects - Legacy code
        # (self.BE can't be initialized until we have read the data on which it
        # will operate.)
        self.TE = ThresholdEdit(self.default_thresholds)
        self.PE = ProfileEdit(self.default_thresholds)

        # Editing masks
        self.zapperMask = np.zeros((), dtype=bool)
        self.thresholdsMask = np.zeros((), dtype=bool)
        self.bottomMask = np.zeros((), dtype=bool)
        self.bottomIndexes = np.zeros((), dtype=bool)

    def set_grid(self, ylim=None, use_bins=False):
        """
        Use full depth array
        Add one timestamp to the end and one bin (or depth) to the bottom.
        Define Ye, Xe, Xc, yc, xb and yb attributes

        Args:
            ylim: y axis limits, [y min., y max.], list
            use_bins: if True, y axis in bins else in meters
        """
        super().set_grid(ylim=ylim, use_bins=use_bins)
        self.reset_masks()

    def set_grid1D(self, ylim=None, use_bins=False):
        """
        Define Ye and Xe (depth and time coordinates at edges) as well as
        Yc and Xc (depth and time coordinates at centers) CData attributes

        Args:
            ylim: y axis limits, [y min., y max.], list
            use_bins: if True, y axis in bins else in meters
        """
        super().set_grid1D(ylim=ylim, use_bins=use_bins)
        self.reset_masks()

    def fix_flags(self, masking, thresholds=None, pg_cutoff=None):
        """
        Mask or unmask staged edits accordingly with the chosen masking mode.

        Args:
            masking: masking mode, str., "no flags", "codas, or "all"
            thresholds: dict. of thresholds' values to override
        """
        # reset
        self.data.unflag()
        # apply staged edits accordingly with masking mode
        if masking in (2, 'codas'):
            self.data.apply_flags(vars=FLAG_COLOR_PLOT_LIST)
        elif masking in (3, 'all'):
            # find and add threshold flags
            mask = self._get_thresholds_mask(thresholds=thresholds)
            # consolidate with the zapper masks
            mask |= np.logical_or(self.bottomMask, self.zapperMask)
            self.data.apply_flags(vars=FLAG_COLOR_PLOT_LIST,
                                  keep_mask=True, mask=mask)
        elif masking in (1, 'low pg'):
            self.data.apply_flags(vars=FLAG_COLOR_PLOT_LIST, pg_cutoff=pg_cutoff, pflag=False)

    def reset_masks(self, force_reset=False):
        """
        Reset the edits' masks (i.e. zapper, bottom and thresholds masks)

        Args:
            force_reset: switch to force reset, bool.
        """
        # reset only if masks are "empty"
        if self.zapperMask.sum() == 0 or force_reset:
            self.zapperMask = np.zeros((), dtype=bool)
        if self.bottomMask.sum() == 0 or force_reset:
            self.bottomMask = np.zeros((), dtype=bool)
        if self.thresholdsMask.sum() == 0 or force_reset:
            self.thresholdsMask = np.zeros((), dtype=bool)
        if self.bottomIndexes.sum() == 0 or force_reset:
            self.bottomIndexes = np.zeros((), dtype=bool)  # FIXME: different behavior than other masks...see seabed_selector_plot_window.py

    def _get_thresholds_mask(self, thresholds=None):
        """
        Return the edits' masks (i.e. zapper, bottom and thresholds masks)
        """
        if not isinstance(thresholds, dict):
            thresholds = self.thresholds.current_values
        # find and add threshold flags
        # N.B.: DO THE NEXT LINES IN ORDER - Legacy Code
        self.BE = BottomEdit(self.default_thresholds,
                             beam_angle=self.beamangle,
                             bin_offset=self.data.Bin1Dist / self.data.depth_interval,
                             )

        self.BE.get_flags(self.data, override_pfc=thresholds)
        self.TE.get_flags(self.data,
                          mask=self.BE.cflags.flags > 0,
                          override_pfc=thresholds)

        self.PE.get_flags(self.data,
                          mask=(self.TE.cflags.flags +
                                self.BE.cflags.flags) > 0,
                          override_pfc=thresholds)

        profilemask = np.tile(self.PE.cflags.flags, (self.data.nbins, 1)).T
        mask = self.BE.cflags.flags + self.TE.cflags.flags
        # substract existing codas mask
        mask[self.codasMask] = 0
        # add profile mask
        mask = (mask + profilemask) > 0
        # check if new mask points with codasMask
        if mask[~self.codasMask].any():
            return mask
        else:
            # no new points so return ini. mask
            return np.zeros(self.Xc.shape, dtype=bool)

    def update_thresholds_mask(self, thresholds=None):
        """
        Update the thresholds mask based on the current thresholds values
        Args:
            thresholds: dict. of thresholds' values to override
        """
        self.thresholdsMask = self._get_thresholds_mask(thresholds=thresholds)

    def get_masks(self):
        """
        Return:
            editsMask: bin wise edits, numpy bool. array
            profileMask: profile wise edits, 1D numpy bool. array
            bottomIndexes: bottom indexes, 1D masked array
        """
        editsIndexes = self.bottomIndexes.copy()
        thresholdsIndexes = self.BE.mab.copy()
        # a. Consolidate CD.BE.mab and bottomIndexes.
        #    The rule being: shallower index wins
        if editsIndexes.shape and thresholdsIndexes.shape:
            bottomIndexes = np.ma.masked_array(
                np.zeros(editsIndexes.shape), mask=np.ones(editsIndexes.shape)
            ).astype(int)
            # FIXME: We might want different rules (user over algo., algo. over user)
            # FIXME: thus injecting a user option here might be relevant here
            zipIter = zip(editsIndexes.data, editsIndexes.mask,
                          thresholdsIndexes.data, thresholdsIndexes.mask,
                          range(editsIndexes.shape[0]))
            for valE, maskE, valT, maskT, ii in zipIter:
                if not maskE or not maskT:
                    # change default value (i.e. 0)
                    if valE == 0 and maskE:
                        valE = np.inf
                    if valT == 0 and maskT:
                        valT = np.inf
                    # chose shallower index/val
                    bottomIndexes.data[ii] = min(valE, valT)
                    bottomIndexes.mask[ii] = False
        elif editsIndexes.shape:
            bottomIndexes = editsIndexes
        elif thresholdsIndexes.shape:
            bottomIndexes = thresholdsIndexes
        else:
            bottomIndexes = np.zeros((), dtype=bool)
        # b. Consolidate thresholds and user edits masks as well as
        #     subtract the redundant CD.BE.Cflags
        zapperMask = self.zapperMask.copy()
        thresholdsMask = self.thresholdsMask.copy()
        try:
            bottomMask = self.BE.cflags.flags.copy().astype(bool)
        except AttributeError:  # cause: CD.BE.cflags not yet defined
            # FIXME at __init__ level
            bottomMask = np.zeros((), dtype=bool)
        editsMask = zapperMask + thresholdsMask ^ bottomMask
        #  c. Find full profiles in editsMask
        if editsMask.shape:
            nx, ny = editsMask.shape
            profileMask = editsMask.sum(axis=1) == ny
            #  d. cut them from zapperMask and move them to profileMask
            editsMask[profileMask, :] = False
        else:
            profileMask = np.zeros((), dtype=bool)

        return editsMask, profileMask, bottomIndexes


class CDataCompare(dict):
    def __init__(self, sonars, thresholds_compare, list_db_paths, options):
        """
        Container/Wrapper class including a dictionnary of CDataEdit models
        (i.e. one per sonar) as well as wrapping methods (i.e. get_data,
        fix_flags, set_grid, update_thresholds_mask and reset_masks)

        Args:
            sonars: list of sonars, [str., str., ...]
            thresholds_compare: singleton containing thresholds info.,
                dictionary of Bunches (one Bunch per sonar plus wrappers)
            list_db_paths: list of paths to the respective databases
                (one per sonar), [str., str., ...]
            options: list of options, ArgumentParser object
        """
        super().__init__()
        # Attributes
        self.mode = 'compare'
        self.sonars = sonars
        self._diff_plots = ['u', 'v', 'fvel', 'pvel']
        for sonar_name, db_path in zip(sonars, list_db_paths):
            thresholds = thresholds_compare[sonar_name]
            CD = CDataEdit(thresholds, db_path, options)
            # - Override some attributes
            CD.sonar = sonar_name  # for custom names like os75nb_uvship
            #  - Append new attributes to CDataEdit objects
            remaining_sonars = sonars[:]
            remaining_sonars.remove(sonar_name)
            diff_aliases = []
            for other_sonar in remaining_sonars:
                for name in self._diff_plots:
                    diff_aliases.append(
                        COMPARE_PREFIX + ' %s %s' % (name, other_sonar))
            setattr(CD, 'diff_aliases', diff_aliases)
            self[sonar_name] = CD

    # Special Methods
    def get_data(self, newdata=False):
        """
        Wrapping methods extracting requested data structure.
        Equals None if the requested range is not available or any error occurs.

        Args:
            newdata: if True, override to the _data and _last_range mechanisms
                     uvship_from_lonlat calculates uship,vship and uses them
                     for ocean u,v.
        """
        # Run get_data for all compared CDs
        for sonar in self.sonars:
            self[sonar].get_data(newdata=newdata)
        # Generate and append diff. quantities to the original CD.data
        for sonar in self.sonars:
            remaining_sonars = self.sonars[:]
            remaining_sonars.remove(sonar)
            for other_sonar in remaining_sonars:
                CDRef = self[sonar]
                CDComp = self[other_sonar]
                if CDRef.data and CDComp.data:
                    # - interpolate onto ref. grid
                    x_old = CDComp.data.dday
                    x_new = CDRef.data.dday
                    for name in self._diff_plots:
                        y_old = self.grid_on_depth(CDRef.data.dep,
                                                   CDComp.data.depth,
                                                   CDComp.data[name])
                        y_new = interp1(x_old, y_old, x_new)
                        # - append diff. quantities
                        diff_name = COMPARE_PREFIX + ' %s %s' % (
                            name, other_sonar)
                        CDRef.data[diff_name] = CDRef.data[name] - y_new
                # Ticket 626
                # in the case of non-overlapping datasets
                elif not CDRef.data or not CDComp.data:
                    if CDRef.data:
                        for name in self._diff_plots:
                            diff_name = COMPARE_PREFIX + ' %s %s' % (
                            name, other_sonar)
                            CDRef.data[diff_name] = None

    # Wrapper methods
    def fix_flags(self, masking, thresholds=None):
        """
        Wrapping method masking or unmasking staged edits accordingly with
        the chosen masking mode.

        Args:
            masking: masking mode, str., "no flags", "codas, or "all"
            thresholds: dict. of thresholds' values to override
        """
        for sonar in self.sonars:
            CD = self[sonar]
            if CD.data:
                values = None
                if thresholds:
                    values = thresholds[sonar]
                self[sonar].fix_flags(masking, thresholds=values)
        # Re-calculate diffs.
        self.get_data()

    def set_grid(self, *args, **kwargs):
        """
        Wrapping method defining Ye and Xe (depth and time coordinates at
        edges) as well as Yc and Xc (depth and time coordinates at centers)
        CData attributes
        """
        for sonar in self.sonars:
            CD = self[sonar]
            if CD.data:
                CD.set_grid(*args, **kwargs)

    def update_thresholds_mask(self, *args, **kwargs):
        """
        Wrapping method updating thresholds masks
        """
        for sonar in self.sonars:
            CD = self[sonar]
            if CD.data:
                self[sonar].update_thresholds_mask(*args, **kwargs)

    def reset_masks(self, *args, **kwargs):
        """
        Wrapping method reseting thresholds masks
        """
        for sonar in self.sonars:
            CD = self[sonar]
            if CD.data:
                self[sonar].reset_masks(*args, **kwargs)

    def _get_yearbase(self):
        # FIXME - Assuming same yearbase between sonars
        # FIXME - choosing the first one could be problematic as CDs don't
        #         share the same value
        yearbase= self[self.sonars[0]].yearbase
        return yearbase

    def _get_startdd(self):
        # FIXME - Assuming same yearbase between sonars
        # FIXME - choosing the first one could be problematic as CDs don't
        #         share the same value
        startdd = self[self.sonars[0]].startdd
        return startdd

    def _set_startdd(self, startdd):
        # FIXME - Assuming same yearbase between sonars
        for sonar in self.sonars:
            self[sonar].startdd = startdd

    def _get_ddstep(self):
        # FIXME - Assuming same yearbase between sonars
        # FIXME - choosing the first one could be problematic as CDs don't
        #         share the same value
        ddstep = self[self.sonars[0]].ddstep
        return ddstep

    def _set_ddstep(self, ddstep):
        for sonar in self.sonars:
            self[sonar].ddstep = ddstep

    def _get_startdd_all(self):
        # FIXME - Assuming same yearbase between sonars
        # Special treatment for day_range - # Ticket 626
        startdd_list = []
        for sonar in self.sonars:
            startdd_list.append(self[sonar].startdd_all)
        startdd_all = min(startdd_list)
        return startdd_all

    def _get_enddd_all(self):
        # FIXME - Assuming same yearbase between sonars
        # Special treatment for day_range - # Ticket 626
        enddd_list = []
        for sonar in self.sonars:
            enddd_list.append(self[sonar].enddd_all)
        enddd_all = max(enddd_list)
        return enddd_all

    def _get_data(self):
        for sonar in self.sonars:
            if self[sonar].data:
                return True
        return None

    # Local lib
    @staticmethod
    def grid_on_depth(zout, depth, var):
        """
        Re-grid depth onto 'zout'

        Args:
            zout: 1D numpy array
            depth: 2D numpy array
            var: 2D numpy array

        Returns: gridded depth, 1D numpy array
        """
        nprofs, ndep = var.shape
        Zout = np.ma.zeros((nprofs, len(zout)), dtype=float)
        for iprof in np.arange(nprofs):
            Zout[iprof, :] = interp1(depth[iprof, :], var[iprof, :], zout)
        return Zout

    # Dynamic wrapper attributes
    startdd = property(_get_startdd, _set_startdd)
    ddstep = property(_get_ddstep, _set_ddstep)

    # Dynamic attributes
    yearbase = property(_get_yearbase)
    startdd_all = property(_get_startdd_all)
    enddd_all = property(_get_enddd_all)
    data = property(_get_data)
