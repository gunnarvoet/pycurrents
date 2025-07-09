"""
Functions, dictionaries, and lists primarily used for setting up the 'config'
directory for UHDAS acquisition and CODAS processing.
"""
from importlib import import_module
import logging

from pycurrents.system import Bunch

# TODO: review exception handling and logging

annotate_time_color = 'purple'

# Standard logging
_log = logging.getLogger(__name__)

## defaults for UH-monitored ships:
## call "uhdas_webgen.py" and "uhdas_config_gen.py" with no "shipinfo"
##  onship/shipnames.py
##  onship  (proc_defaults, uhdas_defaults, cmd_defaults)
##           sensor_cfgs/*_sensor_cfg.*
##           wwwcore (lots of stuff)
##  onship_private (more uhdas_defaults, system_defaults)


## defaults for independent ships: (the name "moreships" is arbitrary
## specify "--shipinfo moreships" using  "uhdas_webgen.py" and "uhdas_config_gen.py"
## pycurrents  (NOT using shipnames from here)
## moreships   (proc_defaults, uhdas_defaults, cmd_defaults, system_defaults)
##             sensor_cfgs/*_sensor_cfg.*
##             wwwcore (lots of stuff)


def get_shipnames(shipinfo = None):
    '''
    get shipnames from file named "shipnames.py"
      if shipinfo is None, get it from onship/shipnames.py
      else from shipinfo/shipnames.py
    return object where object.shipnames is a dictionary
    '''
    if shipinfo is None:
        from onship import shipnames  # for proc_starter_form.py
    elif hasattr(shipinfo, 'keys'):
        shipnames = shipinfo
    else:
        try:
            shipnames = import_module(shipinfo + '.shipnames')
        except ModuleNotFoundError:
            raise ModuleNotFoundError('cannot import "shipnames" from %s' % (shipinfo,))
    return shipnames


# TODO: refactor this function and its usage.  It's very confusing.
def update_defaults(defaults, shipinfo=None, name=None):
    '''
    try to find better defaults, eg name="proc_defaults"

    return a module (if found)
    or True (if 'defaults' was updated)

    '''

    # get proc defaults
    if shipinfo is None:              # default
        newdefs = import_module('onship.' + name)  # eg onship.proc_defaults
        return newdefs                   # return module matching name
    elif hasattr(shipinfo, 'keys'):
        newvars = shipinfo   # its a dictionary of values to update
        for k in newvars.keys():
            defaults[k] = newvars[k]
        return True
    else: #import it: this will be a module
        try:
            newdefs = import_module(shipinfo + '.' + name)
        except ModuleNotFoundError:
            raise ModuleNotFoundError('cannot import module %s from %s' % (name, shipinfo))
        return newdefs



## variable definitions
## Bunches with defaults (for proc_cfg, sensor_cfg, uhdas_cfg, cmd_cfg)
## classes to override from specified source

'''
# processing
    uhdas_adcps : list of UHDAS-supported adcps
    codas_adcps : list of CODAS-supported adcps

# processing defaults -- all are applied to sonar
    proc_constant_defaults: weakprof_numbins, pgmin
    proc_model_defaults : scalefactor, soundspeed, salinity, xducer_dx,[dy]
    proc_inst_defaults:  enslength
    proc_sonar_defaults: max_search_depth (plus all above)

# base classes to inititialize proc_cfg uhdas_cfg, and cmds
   Proc_cfg_base

# fancy classes to fill proc_cfg uhdas_cfg and apply overrides
# if 'source' is 'onship', use ship key; else use Bunch.from_pyfile
   Proc_cfg_defaults


'''

# List of supported instruments.  (It's not clear that the division into UHDAS
# and CODAS is needed, although both variables are used.)
# This order determines the order of the figures in the UHDAS website.
# JH: prefer decreasing in frequency (increasing in range)

uhdas_adcps = ['wh1200',
               'sv1000',
               'bb600','wh600',
               'sv500',
               'wh300', 'nb300','sv300',
               'nb150', 'bb150', 'wh150', 'os150', 'ec150',
               'os75', 'ec75','wh75',
               'pn45',
               'os38', 'ec38',
]
codas_adcps = ['bb300', 'bb75'] + uhdas_adcps


##=================
# defaults for processing -- apply to sonar
##=================
def instpings(adcp):
    if adcp[:2] in ('os', 'pn'):
        return [adcp+'bb', adcp+'nb']
    elif adcp[:2] == 'ec':
        return [adcp+'cw', adcp+'fm']
    else:
        return [adcp]


#------- # now put all these into sonar_defaults

proc_constant_defaults = {
    'weakprof_numbins' : None,
    'pgmin'            : 50,
    'top_plotbin'      : 1,
    'num_refbins'      : 2,
}

## specified by model, spread out to sonars
proc_model_defaults = {
    'scalefactor' : {'pn':1.0, 'os':1.0, 'ec':1.0, 'wh':1.0 , 'bb':1.0 , 'sv':1.0 ,'nb':1.0 },
    'soundspeed'  : {'pn':None,'os':None,'ec':None,'wh':None, 'bb':None, 'sv':None,'nb':'calculate'},
    'salinity'    : {'pn':None,'os':None,'ec':None,'wh':None, 'bb':None, 'sv':None,'nb':35.0},
}

# specify by instrument, spread out to sonars
proc_instrument_defaults = {
    # how many seconds to average for a profile
    'enslength'  :  Bunch(
        bb600  =  120,
        bb300  =  300,
        bb150  =  180,
        bb75   =  300,
        wh1200 =  120,
        wh600  =  120,
        wh300  =  120,
        wh150  =  300,
        nb300  =  120,
        nb150  =  300,
        os150  =  300,
        os75   =  300,
        wh75   =  300,
        os38   =  300,
        pn45   =  300,
        ec150  =  300,
        ec75   =  300,
        ec38   =  300,
        sv300  =  120,
        sv500  =  90,
        sv1000 =  60,

        ),
    # if topo says depth is deeper than this, do not use amp to find the bottom
    'max_search_depth' : Bunch(
        bb600  =  500,
        bb300  =  500,
        bb150  =  500,
        bb75   =  1000,
        wh1200 =  500,
        wh600  =  500,
        wh300  =  500,
        wh150  =  1000,
        nb300  =  1000,
        nb150  =  1000,
        os150  =  1000,
        os75   =  2000,
        wh75   =  2000,
        os38   =  2000,
        pn45   =  2000,
        ec150  =  1000,
        ec75   =  2000,
        ec38   =  2000,
        sv300  =  200,
        sv500  =  100,
        sv1000 =  50,
        ),
    # shallowest allowed btrk depth (about bin 2 depth)
    'btrk_mindepth' : Bunch(
        bb600  =  5,
        bb300  =  10,
        bb150  =  10,
        bb75   =  40,
        wh1200 =  2,
        wh600  =  5,
        wh300  =  10,
        wh150  =  20,
        nb300  =  10,
        nb150  =  20,
        os150  =  20,
        os75   =  40,
        wh75   =  40,
        os38   =  80,
        pn45   =  80,
        ec150  =  20,
        ec75   =  40,
        ec38   =  80,
        sv300  =  10,
        sv500  =  5,
        sv1000 =  2,
        ),
    # deepestallowed btrk depth (20% over range)
    'btrk_maxdepth' : Bunch(
        bb600  =  80,
        bb300  =  300,
        bb150  =  800,
        bb75   =  1000,
        wh1200 =  50,
        wh600  =  80,
        wh300  =  300,
        wh150  =  800,
        nb300  =  300,
        nb150  =  800,
        os150  =  800,
        os75   =  1000,
        wh75   =  1000,
        os38   =  1800,
        pn45   =  1800,
        ec150  =  800,
        ec75   =  1000,
        ec38   =  1800,
        sv300  =  120,
        sv500  =  60,
        sv1000 =  25,
        )
}
# add badbeam to the list
proc_instrument_defaults['badbeam'] =  Bunch()
for ip in proc_instrument_defaults['enslength'].keys():
    proc_instrument_defaults['badbeam'][ip] = None

#
proc_sonar_defaults = Bunch()
for dkey in proc_constant_defaults.keys():
    proc_sonar_defaults[dkey] = Bunch()
    for adcp in codas_adcps:
        for ip in instpings(adcp):
            proc_sonar_defaults[dkey][ip] = proc_constant_defaults[dkey]

for dkey in proc_model_defaults:
    proc_sonar_defaults[dkey] = Bunch()
    for adcp in codas_adcps:
        for ip in instpings(adcp):
            proc_sonar_defaults[dkey][ip] = proc_model_defaults[dkey][adcp[:2]]

for dkey in proc_instrument_defaults:
    proc_sonar_defaults[dkey] = Bunch()
    for adcp in proc_instrument_defaults[dkey].keys():
        for ip in instpings(adcp):
            proc_sonar_defaults[dkey][ip] = proc_instrument_defaults[dkey][adcp]

#-------------------

#===================
# supporting tools for sensor_cfg.*
#====================

serial_suffix=Bunch(
    position = ['gps', 'gps_sea', 'ggn', 'gns', 'gga', 'ixgps'],
    heading  = ['hdg', 'hnc', 'gph',
                'rdi', 'rdinc',
                'adu', 'at2', 'pat', 'paq',
                'pmv', 'sea', 'tss1', 'hnc_tss1', 'hdg_tss1',
                'psathpr'],
    accurate_heading = ['adu', 'at2', 'pat', 'paq', # known to be accurate
                'pmv', 'sea', 'tss1', 'hnc_tss1', 'hdg_tss1',
                ],
    rollpitch = ['adu', 'at2', 'pat', 'paq', 'hpr',
                 'pmv', 'sea', 'psxn23',
                 'ixrp'],
    sndspd = ['spd', 'raw_spd'],
    keeldepth = ['madm'],
    )


serial_msgstr = Bunch(
    spd      = ' %f',       # entire line converts as a float (soundspeed)
    raw_spd  = ' %f',       # entire line converts as a float (raw soundspeed)
    madm     = '$PMADM, NOCHECKSUM',  # investigator
    hdg      = '$..H..',     # includes checksum
    gph      = '$..H..',     # includes checksum
    hnc      = '$..H..,NO CHECKSUM',     # no checksum
    ggn      = '$..GGA,NO CHECKSUM',
    gga      = '$..GGA',    # (older datasets)
    gps      = '$..GGA',    #
    rdi      = '$PRDID',
    rdinc    = '$PRDID,NO CHECKSUM',
    adu      = '$PASHR,ATT',  # deprecated
    at2      = '$PASHR,AT2',  # deprecated
    hpr      = '$PASHR,HPR',  # ABXTWO preferred
    paq      = '$GPPAT',  #includes QC (reacq)
    pat      = '$GPPAT',  #no QC (reacq)
    pmv      = '$PASHR',
    psxn20   = '$PSXN,20',
    psxn23   = '$PSXN,23',
    tss1     = ':',
    hnc_tss1     = ':',
    hdg_tss1     = ':',
    psathpr  = '$PSAT,HPR',
    ixrp     = '$PIXSE,ATITUD',
    ixgps    = '$PIXSE,POSITI',
    ixsspd   = '$PIXSE,SPEED_',
    ixalg    = '$PIXSE,ALGSTS',
    )

# now provide dictionary of output messages (list for checking)
serial_strmsg = dict(zip(serial_msgstr.values(), serial_msgstr.keys()))

#=================

def override_defaults(default, override):
    '''
    default    : provides original values to use, if possible
    overrides : replace completely or replace per-sonar
    '''
    # needs help
    if hasattr(override, 'keys') :
        if not hasattr(default, 'keys'):
            _log.exception('default amd override must both have keys')
        ret = Bunch(default)
        ret.update(override)
        return ret
    else:
        return override

#===================
# base classes to initialize variables
#====================

# Every variable that will be used needs to be initialized here
#=========
# FIXME: The following two classes need to be refactored for clarity.

class Proc_cfg_base:
    def get_defaults(self):
        self.defaults=Bunch()
        # defaults that are constant per ship
        self.defaults['hdg_inst_msgs'] = []
        self.defaults['pos_inst_msg'] = ()
        self.defaults['pitch_inst_msg'] = ()
        self.defaults['roll_inst_msg'] = ()
        self.defaults['hcorr_inst_msg'] = ()
        self.defaults['hcorr_gap_fill'] = 0.0
        self.defaults['acc_heading_cutoff'] = 0.02

        # defaults for processing: each sonar gets a value
        # defaults that are set per instrument
        self.defaults['h_align'] = Bunch()
        self.defaults['ducer_depth'] = Bunch()  #transducer depth-per instrument
        # defaults that are set per sonar
        self.defaults['weakprof_numbins'] = Bunch()
        self.defaults['pgmin'] = Bunch()
        self.defaults['scalefactor'] = Bunch()
        self.defaults['soundspeed']  = Bunch()
        self.defaults['salinity'] = Bunch()
        self.defaults['enslength'] = Bunch()
        self.defaults['max_search_depth'] = Bunch()
        self.defaults['xducer_dx'] = Bunch()
        self.defaults['xducer_dy'] = Bunch()
        self.defaults['badbeam'] = Bunch()

    def get_sonar_defaults(self, dname, onship_adcps):
        defaults = dict()
        for adcp in onship_adcps:
            for ip in instpings(adcp):
                defaults[ip] = proc_sonar_defaults[dname][ip]
        return defaults


#============
# classes to incorporate defaults and overrides
#============

class Proc_cfg_defaults:
    '''
    class with dictionary "defaults" for proc_cfg.py
    '''
    # use cases:
    # - read a (ship-specific) cruise-specific file    km1301_proc.py
    # - get the dictionary as input (already read)
    # - import proc_defaults from onship and use shipkey to get the right collection
    # - read the dictionaries from a different onship-like directory, use shipkey...

    def __init__(self, shipkey=None, shipinfo=None):
        '''
        shipkey: use ship key if in shipnames
        shipinfo
                None : get from 'onship' package
                dict : use directly
                module : import from here

        '''
        Pdef = Proc_cfg_base()
        Pdef.get_defaults()
        self.defaults = Pdef.defaults  #in case we don't fill everything in

        shipnames = get_shipnames(shipinfo=shipinfo)

        updated = update_defaults(self.defaults, shipinfo=shipinfo, name='proc_defaults')
        if updated is False:
            raise NameError('could not get proc_defaults from %s' % (shipinfo))
        elif updated is True:
            pass
        else:
            # now, if the ship key provided is in the onship list, use the dicts
            # fill dict called 'defaults'
            proc_defaults = updated  #overrides from onship.proc_defaults
            if shipkey in shipnames.shipletters:
                self.shipkey = shipkey
                self.onship_adcps = shipnames.onship_adcps[shipkey]
                onship_sonars = []
                for adcp in self.onship_adcps:
                    for ip in instpings(adcp):
                        onship_sonars.append(ip)
                # get defaults before overrides, now that we know the adcps
                for key in proc_sonar_defaults.keys():
                    self.defaults[key] = Pdef.get_sonar_defaults(key, self.onship_adcps)

                # now look for the overrides:
                # all ships must have these
                for key in ['hdg_inst_msgs','hcorr_inst_msg', 'pos_inst_msg',
                             'pitch_inst_msg', 'roll_inst_msg']:
                    try:
                        sdict = getattr(proc_defaults, key)
                    except AttributeError:
                        _log.exception('could not get %s from proc_defaults' % (key))
                    else:
                        try:
                            self.defaults[key] = sdict[self.shipkey]
                        except KeyError:
                            _log.exception('could not get %s for ship %s ' % (key, self.shipkey))
                # these may have overrides
                for key in ['hcorr_gap_fill', 'acc_heading_cutoff', 'xducer_dx', 'xducer_dy']:
                    try:
                        sdict = getattr(proc_defaults, key)
                        if self.shipkey not in sdict:
                            _log.info('no override for %s for ship %s ' % (key, self.shipkey))
                        else:
                            self.defaults[key] = sdict[self.shipkey]
                    except (AttributeError, KeyError):
                        _log.exception('override failed for %s on ship %s ' % (key, self.shipkey))

                # these must exist; mapped out per instrument

                for key in ['ducer_depth', 'h_align']: ## required for each instrument
                    try:
                        sdict = getattr(proc_defaults, key)
                        if self.shipkey not in sdict.keys():
                            _log.exception('could not get %s from proc_defaults' % (key))
                        else:
                            overrides = sdict[self.shipkey]
                            for inst in overrides.keys():
                                self.defaults[key][inst] = overrides[inst]
                    except (AttributeError, KeyError):
                        _log.exception('could not get %s from proc_defaults' % (key))

                # these are spread out to each sonar; may not be overrides
                #for k in self.defaults.keys():
                #    print(k)
                for key in ['enslength', 'max_search_depth', 'pgmin', 'badbeam',
                             'scalefactor', 'soundspeed', 'weakprof_numbins']:
                    if hasattr(proc_defaults, key):
                        for sname in onship_sonars:
                            self.defaults[key][sname] = proc_sonar_defaults[key][sname]
                        overrides = getattr(proc_defaults, key)
                        if self.shipkey in overrides:
                            soverrides = overrides[self.shipkey]
                            for sname in onship_sonars:
                                if sname in soverrides:
                                    self.defaults[key][sname] = soverrides[sname]
                    else:
                        _log.info('no overrides for %s' % (key))
            else:
                _log.exception('ship letters %s not in onship list' % (shipkey))
