import os
import logging


from pycurrents.system.misc import Cachefile, Bunch   # BREADCRUMB: common library
from pycurrents.system.logutils import unexpected_error_msg  # BREADCRUMB: common library
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (
    green, purple, blue, beige, red)
from pycurrents.adcp.adcp_specs import (
    codas_editparams, codas_disableparams, codas_start_disabled,  # ping_editparams
)  # BREADCRUMB: common library

# Standard logging
_log = logging.getLogger(__name__)


# FIXME - turn into class
def Thresholds(path2editparam=None):
    """
    Contains all the thresholds' values and widget features

    Args:
        path2editparam: path to codas_editparams.txt, str.

    Returns:
        Bunch
    """
    # intialize default values from adcp_specs
    defaultThresholds = Bunch(codas_editparams)
    # override defaults reading codas_edit_params.txt
    if path2editparam:
        defaultThresholds = get_codas_editparams(defaultThresholds,
                                                 path2editparam)
    # save copy of defaults values for resetting functionality
    thresholds = Bunch({})
    # Sets of values for thresholds
    thresholds['current_values'] = Bunch(defaultThresholds.copy())  # mutable
    thresholds['default_values'] = Bunch(defaultThresholds.copy())
    thresholds['default_disabled_values'] = Bunch(codas_disableparams.copy())

    # Initialized current values
    for key in codas_start_disabled:
        thresholds.current_values[key] = thresholds.default_disabled_values[key]
    # List of values and features for building frontend (see control_window.py)
    thresholds['widget_features'] = Bunch({
        'edit_names': [
            # Wire interference
            'wire_lastbin', 'onstation', 'wire_ecutoff', 'trimtopbins',
            # Individual bins
            'ecutoff', 'e_std_cutoff', 'wcutoff', 'pgcutoff', 'topbins_pgcutoff',
            'topbins_corcutoff', 'resid_stats_fwd',
            # Percentage good
            'refl_startbin', 'refl_endbin', 'badpgrefl', 'badpgrefl_nbins',
            # Bottom identification
            'bigtarget_ampthresh',
            # Whole profiles
            'jitter_cutoff', 'numfriends', 'shipspeed_cutoff', 'numpings'
        ],
        'labels': [
            # Wire interference
            "Evaluate wire interference in top N bins",
            "Ship speed cut-off (m/s)",
            "Wire: Error Velocity (mm/s) cut-off (on station only)",
            "Ringing: reject this many shallow bins (underway only)",
            # Individual bins
            "Rejected above this Error Velocity (mm/s)",
            "Rejected above this ErrVel Stddev (mm/s) and PG<80",
            "Rejected above this vertical velocity (mm/s)",
            "Reject bins with Percent Good less than this value",
            "Reject shallow low Percent Good",
            "Reject shallow low Correlation",
            "Reject if 'resid_stats_fwd' exceeds this threshold",
            # Percentage good
            "Top bin for Percent Good evaluation",
            "Bottom bin for Percent Good evaluation",
            """"Good bin" requires  Percent Good greater than cutoff""",
            """"Good profile" requires N bins with high Percent Good""",
            # Bottom identification
            "Bottom amplitude bump: larger disables",
            # Whole profiles
            "Reject if jitter greater than cutoff (cm/s)",
            """Require N neighbors on each side of a "good" profile""",
            "Discard profile if ship speed exceeds this (m/s)",
            "Reject profile if fewer pings per ensemble than this number"
        ],
        'background_colors': [
            green, green, green, green,  # Wire interference
            purple, purple, purple, purple, purple, purple, purple,  # individual bins
            blue, blue, blue, blue,  # percentage good
            beige,  # bottom identification
            red, red, red, red  # whole profiles
        ],
        'has_checkbox':
        # N.B.: 0 = widget has not checkbox; 1 = widget has a checkbox
            [
            0, 0, 1, 1,  # Wire interference
            1, 1, 1, 1, 1, 1, 1,  # individual bins
            0, 0, 1, 1,  # percentage good
            1,  # bottom identification
            1, 1, 1, 1  # whole profiles
        ],
        'enabled_thresholds': codas_start_disabled
    })

    return thresholds


# FIXME: move to intercommunication.py
def get_codas_editparams(default_thresholds, path2editparams):
    """
    Overrides default thresholds' values based on codas_editparams.txt content

    Args:
        default_thresholds: default thresholds' values, Bunch
        path2editparams: path to codas_editparams.txt, str

    Returns:
        overridden thresholds' values, Bunch
    """
    if os.path.exists(os.path.join(path2editparams, 'codas_editparams.txt')):
        try:
            cc = Cachefile(cachefile=os.path.join(path2editparams,
                                                  'codas_editparams.txt'))
            cc.read()
            for k in cc.cachedict:
                cc.cachedict[k] = int(cc.cachedict[k])
                default_thresholds.update_values(cc.cachedict)
        except Exception as e:  # FIXME: too vague! What is the actual exception?
            _log.debug('Specify edit to override in codas_editparams.txt')
            _log.debug(unexpected_error_msg(e))
    else:
        _log.debug('could not find codas_editparams.txt file')

    return default_thresholds


class ThresholdsCompare(dict):
    """
    Contains all the thresholds' values and widget features per sonar

    Args:
        sonars: list of instrument names, [str., ]
        edit_dir_paths: list of system path to edit folder, [str., ]

    Returns:
        container, dict.

    """
    def __init__(self, sonars, edit_dir_paths):
        super().__init__()
        for sonar, path in zip(sonars, edit_dir_paths):
            self[sonar] = Thresholds(path2editparam=path)
        # Attributes
        self.current_values = {}
        for sonar in sonars:
            self.current_values[sonar] = self[sonar].current_values
