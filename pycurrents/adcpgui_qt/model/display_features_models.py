import sys

# Standard Logging
import logging

from pycurrents.system.misc import Bunch  # BREADCRUMB: common library
from pycurrents.adcpgui_qt.lib.plotting_parameters import (COLOR_PLOT_LIST,
    TWIN_PLOT_LIST, COLOR_PLOT_TRIPLEX_LIST, CLIMS, alias_to_name, U_ALIAS,
    YLIMS, COMPARE_PREFIX, SPEED_ALIAS, HEADING_ALIAS, NUMPINGS_ALIAS,
    PITCH_ALIAS, ROLL_ALIAS, TEMPERATURE_ALIAS, JITTER_ALIAS, HDG_CORRECTION_ALIAS)
from pycurrents.adcpgui_qt.lib.zappers import TOOL_NAMES

# Standard logging
_log = logging.getLogger(__name__)


class DisplayFeaturesSingleton:
    # Inspired from http://snoozy.ninja/python/Monostan_en/
    __instance = None

    class __DisplayFeaturesSingleton:
        # Generates Singleton
        def __init__(self, given_dict=None):
            if given_dict:
                for key in given_dict.keys():
                    setattr(self, key, given_dict[key])

        def __str__(self):
            msg = ""
            for key in self.__dict__.keys():
                msg += "   %s: %s\n" % (key, self.__dict__[key])
            return msg

    def __new__(self, given_dict=None):
        # Return one-and_only singleton
        if DisplayFeaturesSingleton.__instance is None:
            DisplayFeaturesSingleton.__instance = \
                DisplayFeaturesSingleton.__DisplayFeaturesSingleton()
        # Set attributes values if some given
        if given_dict:
            for key in given_dict.keys():
                    setattr(DisplayFeaturesSingleton.__instance,
                            key, given_dict[key])
        return DisplayFeaturesSingleton.__instance
    # FIXME: dev. read/write methods using configParser and *.ini files


def displayFeatures():
    """
    Contains all the display features for the GUI in view mode.

    Returns: Bunch of all the display features
    """
    panel_choices = COLOR_PLOT_LIST + TWIN_PLOT_LIST
    default_numax = 4
    display_feat = Bunch({
        # Default values
        #  - dataviewer mode
        'mode': 'view',
        #  - exper mode
        'advanced': False,
        #  - Dataset features
        'start_day': None,
        'day_range': None,
        'year_base': None,
        'sonar': None,
        # - Time Navigation options
        'day_step': 0.8,
        # - Panels options
        'axes_choices': panel_choices,
        'plot_title': '',
        # N.B.: apperently 'jitter, spd' is not available for view mode
        #       and 'resid_stats_fwd' is not always in CD
        'num_axes': default_numax,
        'axes': panel_choices[:default_numax],
        'axes_indexes': None,
        # - Toggles options
        'show_spd': False,
        'show_heading': False,
        'use_bins': False,
        # - Masking options
        'mask': 'codas',  # or 'no_flags'
        # - Plotting options
        'shared_yaxis_aliases': COLOR_PLOT_TRIPLEX_LIST,
        'vel_range': CLIMS[alias_to_name(U_ALIAS)],
        'ref_bins': [2, 10],
        # - Graphs option
        #  * color plot
        'shared_y': COLOR_PLOT_LIST,
        'background': [.85, .85, .85],  # background color
        'time_margin': .05,  # percent of the time step as margin
        #  * topo map
        'vec_scale': 1., # vector scale: larger number shrinks vectors
        'z_offset': 0., # subtract this altitude from all topo (eg. Lake Superior)
        'delta_t': 30, # number of minutes to average in topo plot
        #  * Y limits
        'autoscale': True,
        'num_bins': None,
        'depth_range': [None, None],
        'user_depth_range': YLIMS[COMPARE_PREFIX],
        'speed_range': YLIMS[alias_to_name(SPEED_ALIAS)],
        'heading_range': YLIMS[alias_to_name(HEADING_ALIAS)],
        'numpings_range': YLIMS[alias_to_name(NUMPINGS_ALIAS)],
        'std_pitch_range': YLIMS[alias_to_name(PITCH_ALIAS)],
        'std_roll_range': YLIMS[alias_to_name(ROLL_ALIAS)],
        'temperature_range': YLIMS[alias_to_name(TEMPERATURE_ALIAS)],
        'jitter_range': YLIMS[alias_to_name(JITTER_ALIAS)],
        'hd_corr_range': YLIMS[alias_to_name(HDG_CORRECTION_ALIAS)],
        #  * date format
        'utc_date': False,
        #  * multi-cursors
        'multicursor': True,
        #  * color-blind friendly
        'colorblind': False,
    })
    return display_feat


def displayFeaturesEdit():
    """
    Contains all the display features for the GUI in edit mode.

    Returns:
        Bunch of all the display features
    """
    display_feat = displayFeatures()
    display_feat.mode = 'edit'
    display_feat['axes_choices'].append(JITTER_ALIAS)
    display_feat['saturate'] = False
    display_feat['show_bottom'] = True
    display_feat['show_threshold'] = True
    display_feat['show_zapper'] = True
    display_feat['tools'] = TOOL_NAMES

    return display_feat


def displayFeaturesCompare(sonars, write_permission=True):
    """
        Contains all the display features for the GUI in compare mode.

    Args:
        sonars: list of sonars, [str., str., ...]
        list_db_paths: list of system paths to codas databases,

    Returns:
        dict of all the display features.
    """
    display_feat = displayFeaturesEdit()
    display_feat.mode = 'compare'
    # Re-set old entries
    display_feat['show_bottom'] = False
    display_feat['show_threshold'] = False
    display_feat['show_spd'] = True
    display_feat['show_heading'] = True
    display_feat['sonar'] = 'Comparison between sonars'
    display_feat['autoscale'] = False
    display_feat['axes_indexes'] = [0, 0, 18, 1, 1, 19, 2, 2] # panels, then lines
    display_feat['num_axes'] = 8
    # Define new entries
    display_feat['diff_range'] = CLIMS[COMPARE_PREFIX]
    display_feat['write_permission'] = write_permission
    display_feat['sonars'] = sonars[:]
    display_feat['sonar_choices'] = sonars[:]
    display_feat['sonars_indexes'] = [0, 1, 0, 0, 1, 0, 0, 1]  # None
    d = {}
    for sonar_name in sonars:
        default_choices = display_feat.axes_choices[:]
        d[sonar_name] = default_choices
    del display_feat['axes_choices']
    display_feat.axes_choices = d

    return display_feat


def displayFeaturesSinglePing():
    """
    Contains all the display features for the GUI in single ping mode.

    Returns:
        Bunch of all the display features
    """
    display_feat = displayFeatures()
    display_feat.mode = 'single ping'
    display_feat['ping_start'] = None
    display_feat['ping_step'] = 120.0

    return display_feat


# Local lib
def get_setting_parameter_list(mode):
    """
    Return the list of setting parameters.
    Used to write *.ini setting files.

    Args:
        mode: dataviewer's mode, str.

    Returns: [str., ..., str.]

    """
    if mode == 'view':
        m = ['mode', 'multicursor', 'colorblind', 'advanced',
             'show_spd', 'show_heading', 'use_bins', 'utc_date',
             'time_margin', 'day_step', 'num_axes', 'background', 'plot_title',
             'axes_indexes', 'vel_range', 'speed_range',
             'numpings_range', 'std_pitch_range', 'std_roll_range',
             'temperature_range', 'jitter_range', 'ref_bins', 'vec_scale',
             'z_offset', 'delta_t']
    elif mode == 'edit':
        m = ['mode', 'multicursor', 'colorblind', 'advanced',
             'show_spd', 'show_heading', 'use_bins', 'utc_date', 'saturate',
             'time_margin',
             'day_step', 'num_axes', 'background', 'mask', 'plot_title',
             'axes_indexes', 'autoscale', 'user_depth_range', 'vel_range',
             'speed_range', 'numpings_range',
             'std_pitch_range', 'std_roll_range', 'temperature_range',
             'jitter_range', 'ref_bins', 'vec_scale', 'z_offset', 'delta_t',
             'show_bottom', 'show_threshold', 'show_zapper']
    elif mode == 'compare':
        m = ['mode', 'multicursor', 'colorblind', 'advanced',
             'show_spd', 'show_heading', 'use_bins', 'utc_date', 'mask',
             'time_margin', 'day_step', 'num_axes', 'background', 'plot_title',
             'sonars_indexes', 'axes_indexes', 'autoscale', 'user_depth_range',
             'vel_range', 'diff_range', 'speed_range',
             'numpings_range', 'std_pitch_range', 'std_roll_range',
             'temperature_range', 'jitter_range', 'vec_scale', 'z_offset',
             'delta_t', 'ref_bins', 'show_zapper']
    elif mode == 'single ping':
        m = ['mode', 'multicursor', 'colorblind', 'advanced',
             'show_spd', 'show_heading', 'use_bins', 'utc_date', 'time_margin',
             'day_step', 'num_axes', 'background', 'plot_title',
             'axes_indexes', 'autoscale', 'user_depth_range', 'vel_range',
             'speed_range', 'numpings_range',
             'std_pitch_range', 'std_roll_range', 'temperature_range',
             'jitter_range', 'ref_bins', 'vec_scale', 'z_offset', 'delta_t']
    else:
        m = []

    return m

# FIXME: move all templates across module in a "templates" dir...TBD
view_mode_settings_template = """# View mode setting file (*.ini) template
# N.B.:
#   - the options specified in this file will override the related command line options.
#   - in order to disable a parameter, comment it with "#". WARNING: Avoid in-line comments !!!
#   - further details on formatting can be found at https://docs.python.org/3/library/configparser.html#supported-ini-file-structure

[DISPLAY_FEAT]
#### Command line options ####

### modes ###
mode = '%s'

### display options ###
multicursor = %s
# or False. It enables the multi-cursor (cross-hair cursors)

colorblind = %s
# or True. Switches on colorblind friendly color schemes

advanced = %s
# or True. Enables advanced forensic thanks to a custom Ipython console

show_spd = %s
# or True. It over-plots the ship speed by default

show_heading = %s
# or True. It over-plots the ship heading by default

use_bins = %s
# or True. It forces (or not) to use bins instead of meters on the y-axis

utc_date = %s
# or True. It forces (or not) to use UTC date instead of decimal days on the x-axis

time_margin = %s
# or any float. It defines the percentage (10 percent here) of day_step to use as margin on the panels
### color plots ###

day_step = %s
# or any float. It defines the duration (days) to view in panels")

num_axes = %s
# or any int. It defines the number of panels (<= 12) to display

background = %s
# or any Matplotlib RGB color (ex. [0.0, 0.0, 0.0]. It defines the color plots's background color

plot_title = '%s'
# or any other string. It defines the title for panel and topo plots (overrides default which is dbname)

axes_indexes = %s
# or any list of int. Note that the list is of the length of num_axes. It defines which quantities
# to plot. The choices are the following:
# 0  - u ocean vel. (E/W)
# 1  - v ocean vel. (N/S)
# 2  - signal return (amp)
# 3  - percent good (pg)
# 4  - forward ocean vel.
# 5  - port ocean vel.
# 6  - vertical vel. (w)
# 7  - error velocity
# 8  - profile flags
# 9  - residual fwd. vel. std
# 10 - correlation
# 11  - error velocity std
# 12 - temperature, speed
# 13 - speed, heading
# 14 - numpings, speed
# 15 - roll STD, pitch STD
# 16 - heading corr., speed
# 17 - jitter, speed

vel_range = %s
# or any [max. vel., min. vel.] list. It defines the extremum of the velocity colorbar

speed_range = %s
# or any [max. speed, min. speed] list. It defines the y-axis extremum for 2D speed plots

numpings_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D number-of-ping plots

std_pitch_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D pitch plots

std_roll_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D roll plots

temperature_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D temperature plots

jitter_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D jitter plots

### topo. map ###
ref_bins = %s
# or any [upper bin, lower bin] list. It defines the reference ovrer which the velocity arrows are calculated

vec_scale = %s
# or any int. It defines the vector scale (larger number shrinks vectors)

z_offset = %s
# or any float. This altitude shall be subtracted from all topo. maps (eg. Lake Superior)

delta_t = %s
# or any float. It defines the number of minutes to average in topo. map over (default is 30)"""

edit_mode_settings_template = """# Edit mode setting file (*.ini) template
# N.B.:
#   - the options specified in this file will override the related command line options.
#   - in order to disable a parameter, comment it with "#". WARNING: Avoid in-line comments !!!
#   - further details on formatting can be found at https://docs.python.org/3/library/configparser.html#supported-ini-file-structure

[DISPLAY_FEAT]
##### Command line options ####

### modes ###
mode = '%s'

### Display options ###
multicursor = %s
# or False. It enables the multi-cursor (cross-hair cursors)

colorblind = %s
# or True. Switches on colorblind friendly color schemes

advanced = %s
# or True. Enables advanced forensic thanks to a custom Ipython console")

show_spd = %s
# or True. It over-plots the ship speed by default

show_heading = %s
# or True. It over-plots the ship heading by default

use_bins = %s
# or True. It forces (or not) to use bins instead of meters on the y-axis

utc_date = %s
# or True. It forces (or not) to use UTC date instead of decimal days on the x-axis

saturate = %s
# or True. Changes y limits in order to make the colors look saturated

time_margin = %s
# or any float > 0. It defines the percentage (10 percent here) of day_step to use as margin on the panels
### color plots ###

day_step = %s
# or any float > 0.0. It defines the duration (days) to view in panels")

num_axes = %s
# or any int. It defines the number of panels (<= 12) to display

background = %s
# or any Matplotlib RGB color (ex. [0.0, 0.0, 0.0]. It defines the color plots's background color

mask = '%s'
# or 'no flags' or 'all'. Sets the mask radio button

plot_title = '%s'
# or any other string. It defines the title for panel and topo plots (overrides default which is dbname)

axes_indexes = %s
# or any list of int. Note that the list is of the length of num_axes. It defines which quantities
# to plot. The choices are the following:
# 0  - u ocean vel. (E/W)
# 1  - v ocean vel. (N/S)
# 2  - signal return (amp)
# 3  - percent good (pg)
# 4  - forward ocean vel.
# 5  - port ocean vel.
# 6  - vertical vel. (w)
# 7  - error velocity
# 8  - profile flags
# 9  - residual fwd. vel. std
# 10 - correlation
# 11  - error velocity std
# 12 - temperature, speed
# 13 - speed, heading
# 14 - numpings, speed
# 15 - roll STD, pitch STD
# 16 - heading corr., speed
# 17 - jitter, speed

autoscale = %s
# or True. Enables the y-axis autoscaling

user_depth_range = %s
# or any [max. depth, min. depth] list. It defines the y-axis extremum for colorpolts

vel_range = %s
# or any [max. vel., min. vel.] list. It defines the extremum of the velocity colorbar

speed_range = %s
# or any [max. speed, min. speed] list. It defines the y-axis extremum for 2D speed plots

numpings_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D number-of-ping plots

std_pitch_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D pitch plots

std_roll_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D roll plots

temperature_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D temperature plots

jitter_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D jitter plots

### topo. map ###
ref_bins = %s
# or any [upper bin, lower bin] list. It defines the reference ovrer which the velocity arrows are calculated

vec_scale = %s
# or any int. It defines the vector scale (larger number shrinks vectors)

z_offset = %s
# or any float. This altitude shall be subtracted from all topo. maps (eg. Lake Superior)

delta_t = %s
# or any float. It defines the number of minutes to average in topo. map over (default is 30)

##### Edit options ####
show_bottom = %s
# or False. It enables the visualization of the staged bottom-editing

show_threshold = %s
# or False. It enables the visualization of the staged threshold-editing

show_zapper = %s
# or False. It enables the visualization of the staged manual-editing

"""

compare_mode_settings_template = """# Compare mode setting file (*.ini) template
# N.B.:
#   - the options specified in this file will override the related command line options.
#   - in order to disable a parameter, comment it with "#". WARNING: Avoid in-line comments !!!
#   - further details on formatting can be found at https://docs.python.org/3/library/configparser.html#supported-ini-file-structure
[DISPLAY_FEAT]
#### Command line options ####

### modes ###
mode = '%s'

### display options ###
multicursor = %s
# or False. It enables the multi-cursor (cross-hair cursors)

colorblind = %s
# or True. Switches on colorblind friendly color schemes

advanced = %s
# or True. Enables advanced forensic thanks to a custom Ipython console")

show_spd = %s
# or True. It over-plots the ship speed by default

show_heading = %s
# or True. It over-plots the ship heading by default

use_bins = %s
# or True. It forces (or not) to use bins instead of meters on the y-axis

utc_date = %s
# or True. It forces (or not) to use UTC date instead of decimal days on the x-axis

mask = '%s'
# or 'no flags'. Sets the mask radio button

time_margin = %s
# or any float. It defines the percentage (10 percent here) of day_step to use as margin on the panels

### color plots ###
day_step = %s
# or any float. It defines the duration (days) to view in panels")

num_axes = %s
# or any int. It defines the number of panels (<= 12) to display

background = %s
# or any Matplotlib RGB color (ex. [0.0, 0.0, 0.0]. It defines the color plots's background color

plot_title = '%s'
# or any other string. It defines the title for panel and topo plots (overrides default which is dbname)

sonars_indexes = %s
# or any list of int. Note that the list is of the length of num_axes. It defines which sonar
# to plot. The choices are 0 (reference sonar) or 1 (compared sonar)

axes_indexes = %s
# or any list of int. Note that the list is of the length of num_axes. It defines which quantities
# to plot. The choices are the following:
# 0  - u ocean vel. (E/W)
# 1  - v ocean vel. (N/S)
# 2  - signal return (amp)
# 3  - percent good (pg)
# 4  - forward ocean vel.
# 5  - port ocean vel.
# 6  - vertical vel.
# 7  - error velocity
# 8  - profile flags
# 9  - residual fwd. vel. std
# 10 - correlation
# 11  - error velocity std
# 12 - temperature, speed
# 13 - speed, heading
# 14 - numpings, speed
# 15 - roll STD, pitch STD
# 16 - heading corr., speed
# 17 - jitter, speed
# 18 - diff.  u other_sonar
# 19 - diff.  v other_sonar
# 20 - diff.  fvel other_sonar
# 21 - diff.  pvel other_sonar


autoscale = %s
# or True. Enables the y-axis autoscaling

user_depth_range = %s
# or any [max. depth, min. depth] list. It defines the y-axis extremum for colorpolts

vel_range = %s
# or any [max. vel., min. vel.] list. It defines the extremum of the velocity colorbar

diff_range = %s
# or any [max. vel., min. vel.] list. It defines the extremum of the velocity diff. colorbar

speed_range = %s
# or any [max. speed, min. speed] list. It defines the y-axis extremum for 2D speed plots

numpings_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D number-of-ping plots

std_pitch_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D pitch plots

std_roll_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D roll plots

temperature_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D temperature plots

jitter_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D jitter plots

### topo. map ###
vec_scale = %s
# or any int. It defines the vector scale (larger number shrinks vectors)

z_offset = %s
# or any float. This altitude shall be subtracted from all topo. maps (eg. Lake Superior)

delta_t = %s
# or any float. It defines the number of minutes to average in topo. map over (default is 30)

ref_bins = %s
# or any [upper bin, lower bin] list. It defines the reference ovrer which the velocity arrows are calculated


#### Edit options ####
show_zapper = %s
# or False. It enables the visualization of the staged manual-editing
"""

single_ping_mode_settings_template = """# Single Ping mode setting file (*.ini) template
# N.B.:
#   - the options specified in this file will override the related command line options.
#   - in order to disable a parameter, comment it with "#". WARNING: Avoid in-line comments !!!
#   - further details on formatting can be found at https://docs.python.org/3/library/configparser.html#supported-ini-file-structure

[DISPLAY_FEAT]
#### Command line options ####

### modes ###
mode = '%s'

### display options ###
multicursor = %s
# or False. It enables the multi-cursor (cross-hair cursors)

colorblind = %s
# or True. Switches on colorblind friendly color schemes

advanced = %s
# or True. Enables advanced forensic thanks to a custom Ipython console

show_spd = %s
# or True. It over-plots the ship speed by default

show_heading = %s
# or True. It over-plots the ship heading by default

use_bins = %s
# or True. It forces (or not) to use bins instead of meters on the y-axis

utc_date = %s
# or True. It forces (or not) to use UTC date instead of decimal days on the x-axis

time_margin = %s
# or any float. It defines the percentage (10 percent here) of day_step to use as margin on the panels

### color plots ###
day_step = %s
# or any float. It defines the duration (days) to view in panels")

num_axes = %s
# or any int. It defines the number of panels (<= 12) to display

background = %s
# or any Matplotlib RGB color (ex. [0.0, 0.0, 0.0]. It defines the color plots's background color

plot_title = '%s'
# or any other string. It defines the title for panel and topo plots (overrides default which is dbname)

axes_indexes = %s
# or any list of int. Note that the list is of the length of num_axes. It defines which quantities
# to plot. The choices are the following:
# 0  - u ocean vel. (E/W)
# 1  - v ocean vel. (N/S)
# 2  - signal return (amp)
# 3  - percent good (pg)
# 4  - forward ocean vel.
# 5  - port ocean vel.
# 6  - vertical vel. (w)
# 7  - error velocity
# 8  - profile flags
# 9  - residual fwd. vel. std
# 10 - correlation
# 11  - error velocity std
# 12 - temperature, speed
# 13 - speed, heading
# 14 - numpings, speed
# 15 - roll STD, pitch STD
# 16 - heading corr., speed
# 17 - jitter, speed

autoscale = %s
# or True. Enables the y-axis autoscaling

user_depth_range = %s
# or any [max. depth, min. depth] list. It defines the y-axis extremum for colorpolts

vel_range = %s
# or any [max. vel., min. vel.] list. It defines the extremum of the velocity colorbar

speed_range = %s
# or any [max. speed, min. speed] list. It defines the y-axis extremum for 2D speed plots

numpings_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D number-of-ping plots

std_pitch_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D pitch plots

std_roll_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D roll plots

temperature_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D temperature plots

jitter_range = %s
# or any [max., min.] list. It defines the y-axis extremum for 2D jitter plots

### topo. map ###
ref_bins = %s
# or any [upper bin, lower bin] list. It defines the reference ovrer which the velocity arrows are calculated

vec_scale = %s
# or any int. It defines the vector scale (larger number shrinks vectors)

z_offset = %s
# or any float. This altitude shall be subtracted from all topo. maps (eg. Lake Superior)

delta_t = %s
# or any float. It defines the number of minutes to average in topo. map over (default is 30)


"""


def get_settings_template(mode):
    """
    Return the appropriate settings template depending on the given mode

    Args:
        mode: mode name, str.

    Returns: str.
    """
    if mode == 'view':
        return view_mode_settings_template
    elif mode == 'edit':
        return edit_mode_settings_template
    elif mode == 'compare':
        return compare_mode_settings_template
    elif mode == 'single ping':
        return single_ping_mode_settings_template
    else:
        _log.error("%s: This mode does not exist" % mode)
        sys.exit(1)
