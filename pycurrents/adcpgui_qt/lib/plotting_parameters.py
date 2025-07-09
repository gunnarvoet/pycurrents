# N.B.: This script gathers all the plotting parameters needed for the GUI
#       and plotting engine (see panel_plotter.py)

import logging

import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import ScalarFormatter

from matplotlib.pyplot import get_cmap
# We are using pyplot here because its get_cmap is expected to be a stable
# bridge across the evolution of matplotlib.cm and matplotlib.colormaps.
# Once we no longer need to support ubuntu < 22.04, which uses mpl 3.5, we can
# retire get_cmap and use the recommended dictionary syntax, e.g.,
# "colormaps['viridis']".  At that point we should also replace 'get_extcmap()
# with registration of our custom colormaps using colormaps.register(),
# permitting them to be accessed directly, e.g., "colormaps['ob_vel']".

from pycurrents.plot.mpltools import get_extcmap  # BREADCRUMB: common library

# Standard logging
_log = logging.getLogger(__name__)

# Aliases of variables' names and vice versa
HEADING_ALIAS = 'speed, heading'
HDG_CORRECTION_ALIAS = 'heading corr., speed'
JITTER_ALIAS = 'jitter, speed'
NUMPINGS_ALIAS = 'numpings, speed'
PITCH_ALIAS = 'roll STD, pitch STD'
ROLL_ALIAS = 'roll STD'
SPEED_ALIAS = 'ship speed'
TEMPERATURE_ALIAS = 'temperature, speed'
U_ALIAS = 'u ocean vel. (E/W)'
V_ALIAS = 'v ocean vel. (N/S)'
PG_ALIAS = 'percent good (pg)'
AMP_ALIAS = 'signal return (amp)'
FVEL_ALIAS = 'forward ocean vel.'
PVEL_ALIAS = 'port ocean vel.'
E_ALIAS = 'error velocity (e)'
ESTD_ALIAS = 'error velocity std (e_std)'
W_ALIAS = 'vertical vel. (w)'
P_ALIAS = 'profile flags'
RESID_ALIAS = 'residual fwd. vel. std'
COR_ALIAS = 'correlation'

ALIAS2NAME = {
    U_ALIAS:              'u',
    V_ALIAS:              'v',
    PG_ALIAS:             'pg',
    AMP_ALIAS:            'amp',
    FVEL_ALIAS:           'fvel',
    PVEL_ALIAS:           'pvel',
    E_ALIAS:              'e',
    ESTD_ALIAS:           'e_std',
    W_ALIAS:              'w',
    P_ALIAS:              'pflag',
    RESID_ALIAS:          'resid_stats_fwd',
    HEADING_ALIAS:        'spd',  # Quick fix to swap 'heading' & 'spd' axes
    SPEED_ALIAS:          'spd',
    JITTER_ALIAS:         'jitter',
    NUMPINGS_ALIAS:       'pgs_sample',
    PITCH_ALIAS:          'std_pitch',
    ROLL_ALIAS:           'std_roll',
    TEMPERATURE_ALIAS:    'tr_temp',
    HDG_CORRECTION_ALIAS: 'watrk_hd_misalign',
    COR_ALIAS:            'swcor',
}

NAME2ALIAS = {v: k for k, v in ALIAS2NAME.items()}

COMPARE_PREFIX = 'diff. '

# Dictionary of data variables on twin layer
TWIN_DATA_NAME = {
    'heading':           'spd',
    'spd':               'heading',
    'jitter':            'spd',
    'pgs_sample':        'spd',
    'std_pitch':         'std_roll',
    'tr_temp':           'spd',
    'watrk_hd_misalign': 'spd',
}

# Dict. of data range and corresponding display features (see models/display_features_models.py)
TWIN_DATA_RANGE = {
    'spd':               'speed_range',
    'heading':           'heading_range',
    'heading_diff':      'heading_range',
    'pgs_sample':        'numpings_range',
    'std_pitch':         'std_pitch_range',
    'std_roll':          'std_roll_range',
    'tr_temp':           'temperature_range',
    'jitter':            'jitter_range',
    'watrk_hd_misalign': 'hd_corr_range',
}

# Groups/Lists of color plot aliases
# - list of color or 2D plots
COLOR_PLOT_LIST = [U_ALIAS, V_ALIAS, AMP_ALIAS, PG_ALIAS, FVEL_ALIAS,
                   PVEL_ALIAS, W_ALIAS, E_ALIAS, P_ALIAS, RESID_ALIAS, COR_ALIAS, ESTD_ALIAS]
# - list of plots with heading & speed over plotting capability
COLOR_PLOT_TRIPLEX_LIST = [U_ALIAS, V_ALIAS, FVEL_ALIAS, PVEL_ALIAS]
# - list of plots on which staged edits shall be over-plotted
FLAG_COLOR_PLOT_LIST = ['u', 'v', 'fvel', 'pvel', 'w', 'e', 'e_std', 'umeas', 'vmeas', ]
# - list of time-series or 1D plots
TWIN_PLOT_LIST = [TEMPERATURE_ALIAS, HEADING_ALIAS, NUMPINGS_ALIAS,
                  PITCH_ALIAS, HDG_CORRECTION_ALIAS]
# - list of time-series or 1D plots to exclude from manual edits
EXCLUDE_PLOT_LIST = [TEMPERATURE_ALIAS, HEADING_ALIAS, NUMPINGS_ALIAS,
                     PITCH_ALIAS, JITTER_ALIAS, HDG_CORRECTION_ALIAS]

# Features for over layers
MARKER_SIZE = 1.0
LINE_SIZE = 1.0
FORMATTER = ScalarFormatter(useOffset=False)
OVERPLOT_ALPHA = 0.7
STAGED_EDITS_ALPHA = 0.5
SINGLE_PING_ALPHA = 0.5

# Color maps
CMAP_PG3080 = get_extcmap('pg3080')
CMAP_JET = get_cmap('jet')
CMAP_GAUTOEDIT = get_extcmap('gautoedit')
CMAP_OB = get_extcmap('ob_vel')
CMAP_RBVEL = get_extcmap('rb_vel')
CMAP_DIFF = get_extcmap('blue_white_red')
CMAP_COR =  get_extcmap('gist_ncar')

CMAP_ESTD = get_cmap('viridis')
CMAP_ESTD_CBLIND = get_cmap('viridis')

CMAP_PG3080_CBLIND = get_cmap('viridis')
CMAP_JET_CBLIND = get_cmap('plasma')

CMAP_OB_CBLIND = get_cmap('magma')
CMAP_RBVEL_CBLIND = get_cmap('inferno')
# - discrete color bar for Error flags
N = 9
CMAP_PFLAG = LinearSegmentedColormap.from_list(
    'Flag cmap',
    [CMAP_PG3080(i * int(CMAP_PG3080.N / N)) for i in range(N)], N)
CMAP_PFLAG_CBLIND = LinearSegmentedColormap.from_list(
    'Flag cmap',
    [CMAP_PG3080_CBLIND(i * int(CMAP_PG3080.N / N)) for i in range(N)], N)
N = 2
CMAP_PING_FLAG = LinearSegmentedColormap.from_list(
    'Flag cmap',
    [CMAP_PG3080(i * int(CMAP_PG3080.N / N)) for i in range(N)], N)
CMAP_PING_FLAG_CBLIND = LinearSegmentedColormap.from_list(
    'Flag cmap',
    [CMAP_PG3080_CBLIND(i * int(CMAP_PG3080.N / N)) for i in range(N)], N)

CMAPDICT = {
    'pg':              CMAP_PG3080,
    'pflag':           CMAP_PFLAG,
    'ping flag':       CMAP_PING_FLAG,
    'amp':             CMAP_JET,
    'ramp':            CMAP_JET,
    'sw':              CMAP_JET,
    'umeas':           CMAP_RBVEL,
    'vmeas':           CMAP_RBVEL,
    'w':               CMAP_RBVEL,
    'e':               CMAP_RBVEL,
    'u':               CMAP_OB,
    'v':               CMAP_OB,
    'fvel':            CMAP_OB,
    'pvel':            CMAP_OB,
    'resid_stats_fwd': CMAP_RBVEL,
    'swcor':           CMAP_COR,
    'e_std':           CMAP_ESTD,
    COMPARE_PREFIX:    CMAP_DIFF
}

CMAPDICT_CBLIND = {
    'pg':              CMAP_PG3080_CBLIND,
    'pflag':           CMAP_PFLAG_CBLIND,
    'ping flag':       CMAP_PING_FLAG_CBLIND,
    'amp':             CMAP_JET_CBLIND,
    'ramp':            CMAP_JET_CBLIND,
    'sw':              CMAP_JET_CBLIND,
    'umeas':           CMAP_RBVEL,  # _CBLIND,
    'vmeas':           CMAP_RBVEL,  # _CBLIND,
    'w':               CMAP_RBVEL,  # _CBLIND,
    'e':               CMAP_RBVEL_CBLIND,
    'u':               CMAP_OB,  # _CBLIND,
    'v':               CMAP_OB,  # _CBLIND,
    'fvel':            CMAP_OB,  # _CBLIND,
    'pvel':            CMAP_GAUTOEDIT,  # _CBLIND,
    'resid_stats_fwd': CMAP_RBVEL_CBLIND,
    'swcor':           CMAP_RBVEL_CBLIND,
    'e_std':           CMAP_ESTD_CBLIND,
    COMPARE_PREFIX:    CMAP_DIFF
}

# Color plots limits
CLIMS = {
    'u':               [-0.6, 0.6],
    'v':               [-0.6, 0.6],
    COMPARE_PREFIX:    [-0.12, 0.12],
    'pg':              [0.0, 100.0],
    'amp':             [0.0, 200.0],
    'fvel':            [-0.6, 0.6],
    'pvel':            [-0.6, 0.6],
    'e':               [-100.0, 100.0],
    'w':               [-100.0, 100.0],
    'pflag':           [0.0, 8.0],
    'resid_stats_fwd': [0.0, 100.0],
    'swcor':           [60,160],
    'e_std':           [200, 400.0],
}

# 1D plots limits
YLIMS = {
    'spd':               [0.0, 8.0],
    'heading':           [0.0, 360.0],
    'pgs_sample':        [0.0, 320.0],
    'std_pitch':         [-5.0, 5.0],
    'std_roll':          [-5.0, 5.0],
    'tr_temp':           [10.0, 20.0],
    'jitter':            [0.0, 32.0],
    'watrk_hd_misalign': [-5.0, 5.0],
}

# Diff. plots limits
YLIMS[COMPARE_PREFIX] = [800, 0]

# Plot titles
TITLES = {
    'u':                 'ocean u',
    'v':                 'ocean v',
    'pg':                'percent good',
    'amp':               'signal return',
    'fvel':              'ocean forward.',
    'pvel':              'ocean port',
    'e':                 'error velocity',
    'w':                 'vertical velocity',
    'pflag':             'profile flags',
    'resid_stats_fwd':   'residual fwd. vel. std.',
    'tr_temp':           'temperature',
    'spd':               'ship speed & heading',
    'heading':           'heading',
    'pgs_sample':        'number of pings',
    'std_pitch':         'roll STD (orange) & pitch STD (purple)',
    'std_roll':          'roll STD',
    'jitter':            'jitter',
    'watrk_hd_misalign': 'heading correction',
    'swcor':             'correlation (or spectral width)',
    'e_std':              'error velocity std.',
}

# Plot units
UNITS = {
    'u':                 'm/s',
    'v':                 'm/s',
    'pg':                'percent',
    'amp':               'counts',
    'fvel':              'm/s',
    'pvel':              'm/s',
    'e':                 'mm/s',
    'w':                 'mm/s',
    'pflag':             '',
    'resid_stats_fwd':   'mm/s',
    'tr_temp':           'deg. Cel.',
    'spd':               'm/s',
    'heading':           'direction',
    'pgs_sample':        'counts',
    'std_pitch':         'deg.',
    'std_roll':          'deg.',
    'jitter':            'cm/s',
    'watrk_hd_misalign': 'deg.',
    'swcor':               '',
    'e_std':              'mm/s',
}

# 1D plots' plotting properties/parameters
tickerHd = mpl.ticker.FixedLocator([90, 180, 270])
formatterHd = ['E.', 'S.', 'W.']  # mpl.ticker.FixedFormatter(['E.', 'S.', 'W.'])
tickerJt = mpl.ticker.MaxNLocator(4, prune='both')# mpl.ticker.FixedLocator([5, 10, 15, 20, 25])
tickerTp = mpl.ticker.MaxNLocator(4, prune='both')# mpl.ticker.FixedLocator([12, 14, 16, 18])
tickerNp = mpl.ticker.MaxNLocator(4, prune='both')# mpl.ticker.FixedLocator([50, 100, 150, 200, 250])
tickerSpdR = mpl.ticker.FixedLocator([1, 3, 5, 7])
tickerSpd = mpl.ticker.MaxNLocator(4, prune='both')# mpl.ticker.FixedLocator([2, 4, 6])
tickerPnR = mpl.ticker.MaxNLocator(4, prune='both')# mpl.ticker.FixedLocator([-4, -2, 0, 2, 4])
tickerHdgCorr = mpl.ticker.MaxNLocator(4, prune='both')
tickerUTC = mpl.ticker.MaxNLocator(nbins=9, prune='both')


PLOT_PARAM = {
    'spd':
        (UNITS['spd'], 'g',  '-', tickerSpd),
    'heading':
        (UNITS['heading'], 'magenta',  '.', tickerHd, formatterHd),
    'heading_diff':
        (UNITS['heading'], 'magenta', '.', tickerHd),
    'pgs_sample':
        (UNITS['pgs_sample'],  'k',  '.', tickerNp),
    'std_pitch':
        (UNITS['std_pitch'],  'darkmagenta',  '.', tickerPnR),
    'std_roll':
        (UNITS['std_roll'], 'darkorange', '.', tickerPnR),
    'tr_temp':
        (UNITS['tr_temp'], 'c', '.', tickerTp),
    'jitter':
        (UNITS['jitter'], 'crimson', '.-', tickerJt),
    'spd_right':
        (UNITS['spd'], 'g',  '-', tickerSpdR),
    'watrk_hd_misalign':
        (UNITS['watrk_hd_misalign'], 'cadetblue',  '.', tickerHdgCorr),
}


# Local lib.
def alias_to_name(alias):
    """
    Convert alias to CODAS variable name

    Args:
        alias: quantity's alias, str

    Returns: associated CODAS variable name, str
    """
    if alias in ALIAS2NAME.keys():
        name = ALIAS2NAME[alias]
    else:
        name = alias
    return name
