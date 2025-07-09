"""
Functions and dictionaries primarily used in editing and plotting of ADCP data.
"""

import re

from pycurrents.system.misc import Bunch          # handling dictionaries
from pycurrents.adcp.uhdas_defaults import codas_adcps as adcps


_long_names = dict(
    nb = "RDI Original Narrowband",
    bb = "RDI Original Broadband",
    wh = "RDI Workhorse",
    os = "RDI Ocean Surveyor",
    sv = "RDI Sentinel V",
    pn = "RDI Pinnacle",
    ec = "Simrad EC150",
)

_beam_angles = dict(
    nb = "30",
    bb = "30",
    wh = "20",
    os = "30",
    sv = "25",
    pn = "20",
    ec = "30"
)


class Sonar:
    """
    Given a sonar specification string, e.g., 'os75bb', provide
    useful substrings:

        ss = Sonar("os75bb")
        ss.model        # "os"
        ss.instname     # "os75"
        ss.frequency    # "75"
        ss.pingtype     # "bb"
        ss.sonar        # "os75bb"
        ss.long_name    # "RDI Ocean Surveyor"
        ss.beam_angle   # "30"


    The initializing argument can be a string or another Sonar instance.

        ss2 = Sonar(ss)

    For WH and NB instruments, the initialization is

        ss = Sonar("wh300")
        ss.instname         # "wh300"
        ss.sonar            # "wh300"
        ss.frequency        # "300"
        ss.pingtype         #  "bb"

    Printing the instance gives the initialization string:

        str(ss)             # "wh300"

    If the initialization string is incomplete, an incomplete set of
    substrings is available:

        ss = Sonar("wh")
        ss.model         # "wh"
        # ss.frequency access raises AttributeError

    The Sonar instance is mostly read-only; you cannot assign values to
    attributes other than frequency.

    """
    pat = re.compile(r"(\w\w)(\d{,4})(\w{,2})")
    def __init__(self, arg):
        try:
            self._argstring = arg._argstring
        except AttributeError:
            self._argstring = arg
        mod, freq, ping = self.pat.match(self._argstring).groups()
        self._mod = mod
        self._freq = freq
        self._ping = ping
        if mod in ("wh", "bb", "sv"):
            self._pingtype = "bb"
        elif mod == "nb":
            self._pingtype = "nb"
        else:
            self._pingtype = ping

    def __str__(self):
        return self._argstring

    def get_model(self):
        return self._mod

    model = property(get_model)

    def get_pingtype(self):
        if self.model in ("pn", "os", "ec") and not self._pingtype:
            raise AttributeError("Initialization did not include pingtype")
        return self._pingtype

    def set_pingtype(self, pingtype):
        if pingtype not in ('nb', 'bb', 'fm', 'cw', ''):
            raise ValueError('Unrecognized pingtype')
        self._pingtype = pingtype

    pingtype = property(get_pingtype, set_pingtype)

    def get_instname(self):
        if not self._freq:
            raise AttributeError("Initialization did not include frequency")
        return self._mod + self._freq

    instname = property(get_instname)

    def get_frequency(self):
        if not self._freq:
            raise AttributeError("Initialization did not include frequency")
        return self._freq

    def set_frequency(self, freq):
        self._freq = str(freq)

    frequency = property(get_frequency, set_frequency)

    def get_sonar(self):
        if self.model in ("os", "pn", "ec"):
            return "%s%s%s" % (self.model, self.frequency, self.pingtype)
        return "%s%s" % (self.model, self.frequency)

    sonar = property(get_sonar)

    def isa(self, *args):
        return self.model in args

    def isnot(self, *args):
        return self.model not in args

    def get_model_long_name(self):
        return _long_names[self.model]

    long_name = property(get_model_long_name)

    def get_beam_angle(self):
        return _beam_angles[self.model]

    beam_angle = property(get_beam_angle)


#------------
def check_sonar(ss, msg=None):
    """
    The actual use of this is to determine whether in ss the pingtype
    is nailed down, or whether it is left open and could include more
    than one.

    For now, for the ec, we will short-circuit this by setting mixed_pings
    to False.  Any given file will have only FM or CW.
    """
    # FIXME: this function is confusing and obscure.
    if ss is None:
        raise ValueError('\n sonar not specified') # was quickFatalError
    if msg is None:
        msg = ''

    if isinstance(ss, Sonar):
        sonar = ss
        sonar_str = str(ss)
    else:
        sonar_str = ss
        sonar = Sonar(ss)

    if sonar.model == 'ec':
        return False  # short circuit

    mixed_pings = sonar.model in ('os', 'pn', 'ec') and not hasattr(sonar, 'pingtype')

    if mixed_pings:
        if sonar_str not in adcps:
            raise ValueError('\n sonar %s not correctly specified' % (sonar_str))
    else:
        if sonar.sonar != sonar_str:
            raise ValueError('\n sonar not correctly specified')

    return mixed_pings


# moved from py_utils/uhdasfile
pingtype_dict = {'nb' : ('nb',),
                 'wh' : ('bb',),
                 'bb' : ('bb',),
                 'sv' : ('bb',),
                 'os' : ('bb','nb'),
                 'pn' : ('bb','nb'),
                 'ec' : ('fm', 'cw')}


## the following [cor_clim, amp_clim, vel_clim] are being
## used for color scales in the live plots on ships (uhdas installations)

# instrument and pingtype matter, not frequency
cor_clim={'bb600'   : [10,130],
          'bb300'   : [10,130],
          'bb150'   : [10,130],
          'bb75'    : [10,130],
          'sv300'   : [10,130],
          'sv500'   : [10,130],
          'sv1000'  : [10,130],
          'wh150'   : [10,130],
          'wh300'   : [10,130],  # wh different from os
          'wh600'   : [10,130],  # wh different from os
          'wh1200'   : [10,130],  # wh different from os
          'nb150'   : [20,220],  # no 'cor' in nb150, but there is SW
          'nb300'   : [20,220],  # no 'cor' in nb150, but there is SW
          'os150bb' : [0,250],
          'os75bb'  : [0,250],
          'wh75'    : [0,250],      # no idea what is good
          'os38bb'  : [0,250],   # frequency irrelevant,
          'pn45bb'  : [0,130],
          'os150nb' : [90,195],  # osnb different from osbb
          'os75nb'  : [90,195],
          'os38nb'  : [70,195],
          'pn45nb'  : [70,250], # no idea
          'ec150fm' : [0, 95],  # no idea; adjust as needed
          'ec150cw' : [0, 95],
          'ec75fm' : [0, 95],
          'ec75cw' : [0, 95],
          'ec38fm' : [0, 95],
          'ec38cw' : [0, 95],
}

## only inst matters
amp_clim={'bb'   : [20,160],
          'wh'   : [20,160],
          'sv'   : [20,160],
          'nb'   : [10,220],
          'os'   : [10,220],
          'pn'   : [10,160],
          'ec'   : [10,220]}  # raw amp, after subsample_ppd

## Scattering in db relative to an arbitrary reference, used in beam_diagnostics.
sca_clim={'bb'   : [20,160],
          'wh'   : [50,140],
          'sv'   : [50,140],
          'nb'   : [40,160],
          'os'   : [50,180],
          'pn'   : [50,140],
          'ec'   : [50,180],
}

## inst (beam angle) matters
vel_clim = {'bb'   : [-4,4],
            'wh'   : [-4,4],
            'sv'   : [-4,4],
            'nb'   : [-5,5], # in case facing fwd/aft
            'os'   : [-5,5],
            'pn'   : [-5,5],
            'ec'   : [-5, 5]}

## the following are  being used by (at least) 'uhdas_webgen.py'
##
## "adcp_longnames" , "adcp_resolutions", "adcp_ranges"
##
## eg. adcp_longnames = {'nb150'  : 'Narrowband 150 kHz ADCP',}
adcp_longnames={}
for name in adcps:
    s = Sonar(name)
    adcp_longnames[name] = '%s %s kHz ADCP' % (
        {'nb' : 'Narrowband',
         'bb' : 'Broadband',
         'wh' : 'Workhorse',
         'os' : 'Ocean Surveyor',
         'pn' : 'Pinnacle',
         'sv' : 'Sentinel V',
         'ec' : 'EC'}[s.model], s.frequency)


longmodes = dict(bb='broadband', nb='narrowband',
                 fm='FM',
                 cw='CW')

## this is risky if we end up with a PN75 for instance
for freq in ['150', '75', '38']:
    for mode in ['', 'bb', 'nb']:
        key = 'os' + freq + mode
        val = 'Ocean Surveyor %s kHz ADCP' % (freq,)
        if mode:
            val = val + ', %s mode' % (longmodes[mode])
        adcp_longnames[key] = val

for freq in ['45',]:
    for mode in ['', 'bb', 'nb']:
        key = 'pn' + freq + mode
        val = 'Pinnacle %s kHz ADCP' % (freq,)
        if mode:
            val = val + ', %s mode' % (longmodes[mode])
        adcp_longnames[key] = val

for freq in ['150',]:
    for mode in ['', 'fm', 'cw']:
        key = 'ec' + freq + mode
        val = 'EC %s kHz ADCP' % (freq,)
        if mode:
            val = val + ', %s mode' % (longmodes[mode])
        adcp_longnames[key] = val


def default_binsize(sonar):
    ''' return default bin size from sonar
    '''
    S=Sonar(sonar)
    normed_nb_bin = 8.0 * 150.0/int(S.frequency)
    if S.pingtype in ('nb', 'cw'):
        return normed_nb_bin
    if S.pingtype in ('bb', 'fm'):
        return normed_nb_bin/2.0


# increasing order of likely range (resolution)
# use this order for web pages, for example
adcp_plotlist = ['bb600'   ,
                 'bb300'   ,
                 'bb150'   ,
                 'bb75'    ,
                 'sv300'   ,
                 'sv500'   ,
                 'sv1000'  ,
                 'wh600'   ,
                 'wh1200'  ,
                 'wh300'   ,
                 'wh150'   ,
                 'nb300'   ,
                 'os150bb' ,
                 'os150nb' ,
                 'ec150cw' ,
                 'ec150fm' ,
                 'nb150'   ,
                 'wh75'    ,
                 'os75bb'  ,
                 'os75nb'  ,
                 'ec75cw'  ,
                 'ec75fm'  ,
                 'os38bb'  ,
                 'os38nb'  ,
                 'ec38cw'  ,
                 'ec38fm'  ,
                 'pn45bb'  ,
                 'pn45nb'  ,
]



# might end up being ship-dependent
adcp_resolutions = {'bb600'   : '1',
                    'bb300'   : '2',
                    'bb150'   : '4',
                    'bb75'    : '8',
                    'wh150'   : '4',
                    'wh300'   : '4',
                    'wh600'   : '2',
                    'wh1200'  : '1',
                    'sv300'   : '4',
                    'sv500'   : '2',
                    'sv1000'  : '1',
                    'os150bb' : '4',
                    'os150nb' : '8',
                    'ec150fm' : '4',
                    'ec150cw' : '8',
                    'nb150'   : '8',
                    'nb300'   : '4',
                    'wh75'    : '8',
                    'os75bb'  : '8',
                    'os75nb'  : '16',
                    'ec75fm'  : '8',
                    'ec75cw'  : '16',
                    'os38bb'  : '12',
                    'os38nb'  : '24',
                    'ec38fm'  : '12',  ## these are our overrides
                    'ec38cw'  : '24',  ## these are our overrides
                    'pn45bb'  : '16',
                    'pn45nb'  : '32',
                    }

# We may need something fancier for the following to take into
# account the differing ranges on different ships.  Or just make
# a separate dictionary for each ship, and have the ship be one of
# the variables.
adcp_ranges = { 'bb600'  : '60',
                'bb300'  : '120',
                'bb150'  : '300',
                'bb75'   : '600',
                'wh150'  : '400',
                'wh300'  : '120',
                'wh600'  : '60',
                'wh1200' : '30',
                'sv300'  : '120',
                'sv500'  : '50',
                'sv1000' : '20',
                'os150bb': '300',
                'os150nb': '400',
                'ec150fm': '300',
                'ec150cw': '400',
                'nb150'  : '350',
                'nb300'  : '200',
                'os75bb' : '700',
                'wh75'   : '700',  # probably more like 600
                'os75nb' : '850',
                'ec75fm' : '700',
                'ec75cw' : '850',
                'os38bb' : '1300',
                'os38nb' : '1700',
                'ec38fm' : '1300',
                'ec38cw' : '1700',
                'pn45bb' : '1000',
                'pn45nb' : '1300',
                'pn38bb' : '1300',
                'pn38nb' : '1700',
                    }

# at present these must be integers
def ping_editparams(sonar, badbeam=None):
    '''
    single ping editing parameters

    eg

      editparams = ping_editparams('os38bb')
      editparams = ping_editparams('wh300')

    returns Bunch with ping_editparams (tailored to sonar)
    if badbeam is set, return minimal editing (for 3beam solutions)
    '''
    params = Bunch({
    'ecutoff'          :   0.8,
    'estd_cutoff'      :   0,  # electrical interference (0 is disabled) m/s
    'cor_cutoff'       :   120,
    'weakprof_percent' :   30,
    'rl_startbin'      :   2, # 1-based; e.g., 2 means ignore first bin
    'rl_endbin'        :   20, # None to use all bins
    'refavg_valcutoff' :   1,
    'ampfilt'          :   40,
    'slc_deficit'      :   0,  # (e.g., 15 counts)  flag "cor < max_cor - slc_deficit"
    'slc_bincutoff'    :   0,  # (disabled) apply at and above this bin
    'max_search_depth' :   0,   # 0 = always look, -1: never look
    'bigtarget_ampthresh' : 55,
    'bigtarget_mab_window' : 11,   # must be an odd integer
                   })

    if badbeam is not None:
        params.ecutoff = 10000
        params.e_std_cutoff = 10000
        params.refavg_valcutoff = 5
        params.cor_cutoff =0

    else: # more complicated errvel cutoff could be arranged
          # but it would have to happen in pingavg where things
          # like binsize and correlation_lag are known.
        overrides = {'nb':  Bunch( {'ecutoff': 0.5}),
                     'wh':  Bunch( {'ecutoff': 0.5,
                                    'weakprof_percent' : 50,
                                    'cor_cutoff' : 70}),
                     'sv':  Bunch( {'ecutoff': 0.5,
                                    'weakprof_percent' : 50,
                                    'cor_cutoff' : 70}),
                     'bb':  Bunch( {'cor_cutoff' : 70}),
                     'os':  Bunch(),
                     'pn':  Bunch( {'cor_cutoff' : 50}),
                     'ec':  Bunch(cor_cutoff=40),
                     # *Must* match or exceed value applied by EK80, starting
                     # with 'EK80;24.6.0.0;Release'.
                     }
        ss=Sonar(sonar)
        params.update_values(overrides[ss.model])

    return params

# used by dataviewer.py
codas_editparams = {
# settings
    'refl_startbin'        : 2,      # 1-based
    'refl_endbin'          : 20,     # inclusive
    'onstation'            : 100,
    'wire_lastbin'         : 20,  # 1-based, starts at bin 1
# scattered bins
    'ecutoff'              : 200, #mm/s
    'e_std_cutoff'          : 800, #mm/s
    'pgcutoff'             :   50,
    'wire_ecutoff'         : 120,
    'wcutoff'              : 200,
    'resid_stats_fwd'      : 80,  #cm/s
# groups of bins # also uses 'onstation'
    'trimtopbins'          : 2,
# also uses reflayer
    'topbins_pgcutoff'       : 50,
    'topbins_corcutoff'      : 60,
# bottom
    'bigtarget_ampthresh'  : 40,
# bad profiles
    'shipspeed_cutoff'     : 4,
    'badpgrefl'            : 50,
    'badpgrefl_nbins'      : 1,
    'numfriends'           : 0,
    'numpings'             : 40,
    'jitter_cutoff'        : 15}

# overrides to disable codas_editparams
codas_disableparams = {
# scattered bins
    'ecutoff'              : 1000, #mm/s
    'e_std_cutoff'          : 1000, #mm/s
    'pgcutoff'             :   0,
    'wire_ecutoff'         : 1000,
    'wcutoff'              : 1000,
    'resid_stats_fwd'      : 5000,  #cm/s
# groups of bins
    'trimtopbins'          : 0,
    'topbins_pgcutoff'        : 0,
    'topbins_corcutoff'       : 0,
# bottom
    'bigtarget_ampthresh'  : 500,    # disable
# bad profiles
    'shipspeed_cutoff'     : 100,
    'badpgrefl'            : 0,
    'badpgrefl_nbins'      : 0,
    'numfriends'           : 0,
    'numpings'             : 0,
    'jitter_cutoff'        : 500}


codas_start_disabled = [
    'ecutoff',
    'e_std_cutoff',
    'pgcutoff',
    'wire_ecutoff',
    'wcutoff',
    'resid_stats_fwd',
    'trimtopbins',
    'topbins_pgcutoff',
    'topbins_corcutoff',
    'bigtarget_ampthresh',
    'shipspeed_cutoff',
    'badpgrefl',
    'badpgrefl_nbins',
    'numfriends',
    'numpings',
    'jitter_cutoff',  # TR: added after Jules request - March 2nd 2018
 ]
