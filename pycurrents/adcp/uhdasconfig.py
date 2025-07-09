'''
one-stop shopping for uhdas processing (data locations) and some defaults.

used by uhdas/scripts/uhdas_config_gen.py
'''

import os
import glob
import logging

from pycurrents.system import Bunch
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp.uhdasfile import UHDAS_Tree
from pycurrents.text.formats import _initvar, Templater
from pycurrents.plot.mpltools import nowstr
from pycurrents.adcp import uhdas_defaults
from pycurrents.adcp.uhdas_cfg_api import get_cfg, get_cfgs, find_cfg_files

# Standard logging
_log = logging.getLogger(__name__)

## adding these components to facilitate python processing
## during the transition when we must use cruise_cfg.m, cruise_proc.m


class UhdasConfig:
    '''
    small parts of uhdas.uhdas.CruiseInfo, translate here
    '''
    def __init__(self, cfgpath = 'config',  cruisename = None,
                 sonar = None,
                 configtype = 'python',
                 uhdas_dir = None, yearbase = None, **kw):
        '''
        cfgpath (where python config files are)
        cruisename (cruiseid) -- to pull info from cruise_proc.py
        **kw passed to UHDAS_Tree

        UC=UhdasConfig(....)
        pingavg_params = UC.get_pingavg_params(pingtype)  # uses sonar
        '''
        # 2013/07/20: removing obsolete parsers
        #configtype = 'matlab', 'python', 'pyproc'
        #         matlab: cruise_[cfg,proc].m     # in processing dir
        #         python: cruise_[proc,sensor].py # in procesing dir
        #         pyproc : proc_cfg.py            # (live) starting 2011 code


        ## pyproc used by ../../uhdas/scripts/run_hcorrstats_mpl.py
        if configtype not in ('python', 'pyproc'):
            raise IOError('configtype should be "python" or "pyproc"')
        self.configtype = 'python'

        if sonar is None:
            raise IOError('must set sonar')
        self.sonar = Sonar(sonar)

        if cruisename is None:
            raise IOError('must set file base, usually cruisename')
        self.cruisename = cruisename

        if not os.path.isdir(cfgpath):
            raise IOError('must set path to config files')
        self.cfgpath = cfgpath
        self.proc_cfg_path = find_cfg_files(cfgpath)["proc"]
        self.proc_cfg = get_cfg(self.proc_cfg_path)

        self.yearbase = yearbase
        self.uhdas_dir = uhdas_dir

        if self.uhdas_dir is None:
            self.uhdas_dir = self._get_uhdasdir()
        self._set_defaultdirs(**kw)

        # FIXME: the next 3 attribute assignments are odd because they don't
        # always occur.  Default to None?  Are they used?
        if self.yearbase is None and self.configtype == 'python':
            self.yearbase = self.proc_cfg['yearbase']
        if 'shipname' in self.proc_cfg:
            self.shipname = self.proc_cfg['shipname']
        if 'acc_heading_cutoff' in self.proc_cfg:
            self.acc_heading_cutoff = self.proc_cfg['acc_heading_cutoff']

        self.gbin_params = self.get_gbin_params()

    def _set_defaultdirs(self, **kw):
        '''
        deduce UHDAS dirs from base + sonar, consistent with UHDAS_Tree
        '''
        tree = UHDAS_Tree(self.uhdas_dir, self.sonar, **kw)
        names = ['raw', 'rbin', 'gbin', 'proc',
                 'rawsonar',    'gbinsonar', 'procsonar']
        for name in names:
            self.__dict__[name] = getattr(tree, name)

    def _get_uhdasdir(self):
        '''
        initialize uhdas_dir
        '''
        # Catch error in case uhdas_dir is not defined in *_proc.py
        try:
            uhdas_dir = self.proc_cfg['uhdas_dir']
        except KeyError:
            msg = (f"\nuhdas_dir is not defined in {self.proc_cfg_path}."
                "\nMake sure that the *_proc.py header is properly defined."
                "\n Example:\n")
            msg += """    uhdas_dir = '/path/to/uhdas/dir'
    yearbase = 2010 # usually year of first data logged
    shipname = 'Kilo Moana' # for documentation
    cruiseid = 'km1001c' # for titles"""
            raise KeyError(msg)

        if uhdas_dir is None or not os.path.exists(uhdas_dir):
            msg = '\n'.join([
                '\n\n"uhdas_dir" %s not found' % (uhdas_dir),
                'Check data paths in command line argument or in *_proc.* file'
            ])
            raise ValueError(msg)
        return uhdas_dir

    def get_gbin_params(self):
        ''' returns gbin_params Bunch
        '''
        d = self.proc_cfg

        ## get the gbin parameters
        gbin_params = Bunch()
        gbin_params.pos_inst   = d['pos_inst']
        gbin_params.pos_msg    = d['pos_msg']
        gbin_params.hdg_inst   = d['hdg_inst']
        gbin_params.hdg_msg    = d['hdg_msg']
        gbin_params.pitch_inst = d['pitch_inst']
        gbin_params.pitch_msg  = d['pitch_msg']
        gbin_params.roll_inst  = d['roll_inst']
        gbin_params.roll_msg   = d['roll_msg']

        # 'hcorr_inst' and 'hcorr_msg' must be specified in CRUISE_proc.py
        if 'hcorr_inst' not in d:
            msg = '\n'.join(['must specify "hcorr_inst" and "hcorr_msg";',
                        '"hcorr_gap_fill" will default to zero if unset'])
            raise ValueError(msg)

        # hcorr is only added as an attribute if it will be used
        hcorr = None
        gapfill = 0.0
        if d['hcorr_inst'] not in (None,''):
            hcorr = [d['hcorr_inst'], d['hcorr_msg']]
            if 'hcorr_gap_fill' in d:
                gapfill = d['hcorr_gap_fill']
                if gapfill is None:
                    gapfill = 0.0
            hcorr.append(gapfill)
#           hcorr_msg = attmsg_from_dir(self.rbin, d['hcorr_inst'])
        if hcorr is not None:
            self.hcorr = hcorr

        if 'hdg_inst_msgs' in d.keys():
            hdg_inst_msgs = d['hdg_inst_msgs']
        else:
            hdg_inst_msgs = [(d['hdg_inst'], d['hdg_msg'])]
            if hcorr is not None:
                hdg_inst_msgs.append(hcorr[:2])

        gbin_params.hdg_inst_msgs = hdg_inst_msgs
        return gbin_params

    def get_pingavg_params(self, pingtype=None):
        '''
        return pingavg bunch -- this requires pingtype
        '''
        d = self.proc_cfg

        ## get the pingavg parameters
        if pingtype is not None:
            ss = Sonar(self.sonar.instname + pingtype)  # no effect on wh300 etc
        else:
            ss = self.sonar #wh300, os75bb

        ping_params = Bunch()
        if hasattr(self, 'hcorr'):
            ping_params['hcorr'] = self.hcorr
        ping_params.head_align = d['h_align'][ss.instname]
        ping_params.tr_depth = d['ducer_depth'][ss.instname]

        ping_params.velscale = {}
        if d['salinity'][ss.sonar] is not None:
            ping_params.velscale['salinity'] = d['salinity'][ss.sonar]
        if d['scalefactor'][ss.sonar] is not None:
            ping_params.velscale['scale'] = d['scalefactor'][ss.sonar]
        if d['soundspeed'][ss.sonar] is not None:
            if d['soundspeed'][ss.sonar] == 'calculate':
                ping_params.velscale['calculate'] = True
            else: # should be a number
                ping_params.velscale['calculate'] = False
                ping_params.velscale['soundspeed'] = d['soundspeed'][ss.sonar]
        ping_params.hbest = [d['hdg_inst'], d['hdg_msg']]
        ping_params.pbest = [d['pos_inst'], d['pos_msg']]

        pingavg_params = ping_params
        return pingavg_params

    def __str__(self):
        lines = [
            'yearbase       = %d' % self.yearbase,
            'uhdas_dir      = %s' % self.uhdas_dir,
            'sonar          = %s' % self.sonar,
            '',
            'gbin           = %s' % self.gbin,
            'gbinsonar      = %s' % self.gbinsonar,
            'raw            = %s' % self.raw,
            'rawsonar       = %s' % self.rawsonar,
            'rbin           = %s' % self.rbin,
            'proc           = %s' % self.proc,
            'procsonar      = %s' % self.procsonar,
            '',
            'other attributes: ',
            'gbin_params    = %s ' % (self.gbin_params.__str__()),
            ]

        if hasattr(self, 'hcorr'):
            lines.append('hcorr  = %s ' % (self.hcorr.__str__()))

        if hasattr(self, 'acc_heading_cutoff'):
            lines.append('acc_heading_cutoff  = %s ' %
                         (self.acc_heading_cutoff))
        return "\n".join(lines)


#---------------------------------------------------
def get_configs(cfgdir):
    # this is for compare_cfg
    cfgs = get_cfgs(cfgdir)
    sv = cfgs["sensor"]

    adcpdict = {}
    for a in sv.ADCPs:
        adcpdict[a['instrument']] = a
    sensordict = {}
    for s in sv.sensors:
        sensordict[s['subdir']] = s
    sv.adcpdict = adcpdict
    sv.sensordict = sensordict
    #
    pv = cfgs["proc"]
    pv.update(cfgs["uhdas"])
    return sv, pv


def difference(a, b):
    """ show whats in list b which isn't in list a """
    return list(set(b).difference(set(a)))


def dict_key_diff(orig,new):
    origkeys = sorted(orig.keys())
    newkeys = sorted(new.keys())
    diff_new_orig = difference(newkeys, origkeys)
    if len(diff_new_orig) > 0:
        print("new key(s):", diff_new_orig)
    diff_orig_new = difference(origkeys, newkeys)
    if len(diff_orig_new) > 0:
        print("missing keys:", diff_orig_new)


def dict_val_diff(orig,new):
    origkeys = sorted(orig.keys())
    newkeys = sorted(new.keys())
    for k in origkeys:
        if k in newkeys:
            if orig[k] != new[k]:
                print("diff for key '%s'" % (k),'old=',orig[k],'new=',new[k])


def compare_cfg(cfg_orig, cfg_new, exclude = []):
    keys_added = []     # [keys]
    keys_missing = []   # [keys]
    values_changed = {} # key : [oldval, newval]
    bothkeys=[]
    origkeys = list(cfg_orig.keys())
    newkeys = list(cfg_new.keys())
    for kk in cfg_orig.keys():
        if kk not in newkeys:
            if kk not in exclude:
                keys_missing.append(kk)
        else:
            if kk not in bothkeys:
                bothkeys.append(kk)
    for kk in cfg_new.keys():
        if kk not in origkeys:
            if kk not in exclude:
                keys_added.append(kk)
        else:
            if kk not in bothkeys:
                print('what happened to %s?' % (kk))
    for kk in bothkeys:
        if cfg_orig[kk] != cfg_new[kk]:
            values_changed[kk] = [cfg_orig[kk], cfg_new[kk]]
    #
    if hasattr(cfg_orig, 'filename'):
        print('comparing %s \n and ' % (cfg_orig.filename))
    if hasattr(cfg_new, 'filename'):
        print('  %s\n'  % (cfg_new.filename))
    print('%d keys added:'   % (len(keys_added)), keys_added)
    print('%d keys missing:' % (len(keys_missing)), keys_missing)
    print('\n')
    for ck in values_changed.keys():
        if ck != 'filename':
            if hasattr(values_changed[ck][0], 'keys'):
                print('values for %s changed:' % (ck))
                dict_val_diff(values_changed[ck][0], values_changed[ck][1])
            else:
                print('values for %s changed:' % (ck))
                print('    orig:', values_changed[ck][0])
                print('    new:',  values_changed[ck][1])



#---------------------------------------------------
# move this here from onship.proc_setup

proc_cfg_template = '''


## for processing
##----------------
## ship name: __shipname__
## at-sea "proc_cfg.*" initialized __date__
##
## This file starts as /home/adcp/config/proc_cfg.py or .toml and
## includes the following information.  Uncomment, left-justify
## and fill these in if you are attempting to generate proc_cfg.*
## from this template.  The file must be named {cruiseid}_proc.py or *.toml
## or for this example, kk1105_proc.py or kk1105_proc.toml.
##
## example values: fill in for your cruise...
#
# yearbase = 2011                  # usually year of first data logged
# uhdas_dir = "/home/data/kk1105"  # path to uhdas data directory
# shipname = "Ka`imikai O Kanaloa" # for documentation
# cruiseid = "kk1105"              # for titles
#
#

#======== serial inputs =========

# choose position instrument (directory and rbin message)

__pos_inst__
__pos_msg__

# choose attitude instruments (directory and rbin message)

__pitch_inst__     # pitch is recorded, but NOT used in transformation
__pitch_msg__      # disable with "" (not None)

__roll_inst__      # roll is recorded, but NOT used in transformation
__roll_msg__       # disable with "" (not None)

__hdg_inst__       # reliable heading, used for beam-earth transformation
__hdg_msg__


## heading correction
## all heading+msg pairs, for hbin files
__hdg_inst_msgs__

## instrument for heading correction to ADCP data (dir and msg)
__hcorr_inst__       # disable with "" (not None)
__hcorr_msg__        # disable with "" (not None)
__hcorr_gap_fill__   ## fallback correction for hcorr gaps
                     ## calculate hdg_inst - hcorr_inst, eg gyro - ashtech
                     ## SAME SIGN CONVENTION as cal/rotate/ens_hcorr.ang

## if there is a posmv
__acc_heading_cutoff__

# =========== ADCP transformations========

# heading alignment:  nominal - (cal/watertrack)
__h_align__

# transducer depth, meters
__ducer_depth__

# velocity scalefactor
# see SoundspeedFixer in pycurrents/adcp/pingavg.py
__scalefactor__

# soundspeed
# Soundspeed is usually None, and should ALWAYS be left as None for Ocean Surveyor
# (it is remotely possible that soundspeed for a WH, BB, or NB might need to
#           be set to a number, but usually that just results in an erroneous
#           scale factor.
__soundspeed__

# salinity
__salinity__

#=================================================================
# =========           values for quick_adcp.py          ==========
# ========= These are set here for at-sea procesing,    ==========
# ========= but are REQUIRED in quick_adcp.py control   ==========
# =========  file for batch mode or reprocessing.       ==========

## choose whether or not to use topography for editing
## 0 = "always use amplitude to guess the bottom;
##          flag data below the bottom as bad"
## -1 = "never search for the bottom"
## positive integer: Only look for the bottom in deep water, where
##      "deep water" is defined as "topo database says greater than this".

__max_search_depth__

# special: weakprof_numbins
__weakprof_numbins__

# set averaging intervals
__enslength__

# Estimate of offset between ADCP transducer and gps:
# - Specify integer values for 'xducer_dx' and 'xducer_dy' for each instrument
# - xducer_dx = ADCP's location in meters, positive starboard with the GPS
#   location as origin
# - xducer_dy = ADCP's location in meters, positive forward with the GPS
#   location as origin
#
# There should be one set of xducer_dx, xducer_dy values per instrument
# Ex. (python version):
#   xducer_dx = dict(
#   wh300 = -2,
#   os38 = 16,
#   )
# Ex. (toml version)
#   xducer_dy = { wh300 = 1, os38 = 6 }
#
# Note that estimates of xducer_dx, xducer_dy can be found in
# cal/watertrk/guess_xducerxy

__xducer_dx__
__xducer_dy__


## If there is a bad beam, create a dictionary modeled after
## enslen (i.e. Sonar-based, not instrument based) and use the
## RDI number (1,2,3,4) to designate the beam to leave out.

__badbeam__
'''


class Proc_GenBase:
    '''
    format and 'write' proc_cfg.py for  UHDAS acquisition
    (does not have yearbase, cruisename, or uhdas_dir)
    '''

    def __init__(self):
        """ship_defs is a Bunch with values for proc_cfg.py"""
        self.varformat = self.define_formats()

    @staticmethod
    def define_formats():
        # TODO: use actual types. Ex.: str not 'string'
        varformat = Bunch()
        # strings

        varformat['shipname'] = 'string'
        varformat['date'] = 'string'

        varformat['pos_inst']   = 'string'
        varformat['pos_msg']   = 'string'
        varformat['hdg_inst']   = 'string'
        varformat['hdg_msg']   = 'string'
        varformat['pitch_inst'] = 'string'
        varformat['pitch_msg'] = 'string'
        varformat['roll_inst']  = 'string'
        varformat['roll_msg']  = 'string'
        varformat['hcorr_inst'] = 'string'
        varformat['hcorr_msg'] = 'string'

        varformat['acc_heading_cutoff'] = 'num'
        varformat['hcorr_gap_fill'] = 'num'

        varformat['hdg_inst_msgs']    = 'list'

        varformat['h_align']          = 'inst_dict'
        varformat['ducer_depth']      = 'inst_dict'

        varformat['weakprof_numbins'] = 'sonar_dict'
        varformat['enslength']        = 'sonar_dict'
        varformat['pgmin']            = 'sonar_dict'
        varformat['soundspeed']       = 'sonar_dict'
        varformat['salinity']         = 'sonar_dict'
        varformat['scalefactor']      = 'sonar_dict'
        varformat['max_search_depth'] = 'sonar_dict'
        varformat['xducer_dx']         = 'inst_dict'
        varformat['xducer_dy']         = 'inst_dict'
        varformat['badbeam']           = 'sonar_dict'

        return varformat

    @staticmethod
    def define_formats_TR():
        # FIXME: closer to long term solution but not quite...vardoc should be a config file
        vardoc = {
            'yearbase': {
                'doc': 'Year base YYYY',
                'type': int},
            'uhdas_dir': {
                'doc': 'UHDAS directory',
                'type': str},
            'shipname': {
                'doc': 'Ship name',
                'type': str},
            'cruiseid': {
                'doc': 'Cruise Id.',
                'type': str},
            'hcorr_gap_fill': {
                'doc': 'Heading correction fill-value (deg.), Default value: 0.0',
                'type': float},
            'acc_heading_cutoff': {
                'doc': 'Accurate heading cut-off, Default value: 0.02',
                'type': float},
            'pos_inst': {
                'doc': 'Position Instrument',
                'type': str},
            'pos_msg': {
                'doc': 'Position message',
                'type': str},
            'pitch_inst': {
                'doc': 'Pitch instrument',
                'type': str},
            'pitch_msg': {
                'doc': 'Pitch message',
                'type': str},
            'roll_inst': {
                'doc': 'Rolling instrument',
                'type': str},
            'roll_msg': {
                'doc': 'Rolling message',
                'type': str},
            'hdg_inst': {
                'doc': 'Heading instrument',
                'type': str},
            'hdg_msg': {
                'doc': 'Heading message',
                'type': str},
            'hcorr_inst': {
                'doc': 'Heading correction instrument',
                'type': str},
            'hcorr_msg': {
                'doc': 'Heading correction message',
                'type': str},
            'hdg_inst_msgs': {
                'doc': 'List of available heading feeds [(inst., msg.),...]',
                'type': list},
            'h_align': {
                'doc': "Heading alignment (deg.), {'sonar0': float, ..., 'sonarN': float}",
                'type': dict},
            'ducer_depth': {
                'doc': "Transducer depth (m), {'sonar0': int, ..., 'sonarN': int}",
                'type': dict},
            'scalefactor': {
                'doc': "Scale factor, {'sonar0': float, ..., 'sonarN': float}",
                'type': dict},
            'salinity': {
                'doc': "Salinity, {'sonar0': float, ..., 'sonarN': float}",
                'type': dict},
            'soundspeed': {
                'doc': "Sound speed, {'sonar0': float, ..., 'sonarN': float}",
                'type': dict},
            'max_search_depth': {
                'doc': "Max. depth for bottom search (m), {'sonar0': int, ..., 'sonarN': int}",
                'type': dict},
            'weakprof_numbins': {
                'doc': "???, {'sonar0': int, ..., 'sonarN': int}",
                'type': dict},
            'enslength': {
                'doc': "Averaging intervals (s), {'sonar0': int, ..., 'sonarN': int}",
                'type': dict},
            'xducer_dx': {
                'doc': "Offset between sonar and GPS (m), {'sonar0': int, ..., 'sonarN': int}",
                'type': dict},
            'xducer_dy': {
                'doc': "Offset between sonar and GPS (m), {'sonar0': int, ..., 'sonarN': int}",
                'type': dict},
            'badbeam': {
                'doc': "Bad beam, RDI terminology (1,2,3,4), {'sonar0': int, ..., 'sonarN': int}",
                'type': dict},
        }

        return vardoc


class Proc_Gen(Proc_GenBase):
    '''
    generate proc_cfg.py from pycurrents.uhdas_defaults and overrides
    - overrrides are from "shipinfo"
            'onship' (uhdas_config_gen.py: use shipkey-based defaults),
            filename (read the file (python or matlab config file)
            dict or Bunch (pass directly)
    call 'write' method to write
    '''

    def __init__(self, shipkey=None, shipinfo=None, filetype="py"):
        super().__init__()
        self.shipkey = shipkey
        self.shipnames = uhdas_defaults.get_shipnames(shipinfo)

        # This will stage
        Pdef = uhdas_defaults.Proc_cfg_defaults(shipkey=shipkey,
                                                shipinfo = shipinfo)

        self.defaults = Pdef.defaults
        if shipinfo is None:
            self.fill_shipkey_vars()
        elif hasattr(shipinfo, 'keys') or os.path.isfile(shipinfo):
            self.fill_filevars()
        else: # module
            self.fill_shipkey_vars()

        self.T = Templater(proc_cfg_template, self.pdict, self.varformat, filetype=filetype)

    def write(self, outfile):
        if os.path.exists(outfile):
            print('cannot write: %s already exists' % (outfile))
        else:
            with open(outfile,'w') as file:
                file.write(self.T.pstr)

    def fill_filevars(self):
        ''' input is variables or overrides from (eg) proc_starter.cnt'''
        pdict = Bunch()
        self.pdict = pdict
        for name in self.varformat.keys():
            pdict[name] = _initvar(self.varformat[name])
        for name in self.defaults.keys():
            self.pdict[name] = self.defaults[name]

    def fill_shipkey_vars(self):
        ''' input is values or overrides from shipkey-based (eg) "onship"'''
        pdict = Bunch()
        self.pdict = pdict
        for name in self.varformat.keys():
            pdict[name] = _initvar(self.varformat[name])

        pdict['shipname']=self.shipnames.shipnames[self.shipkey]
        pdict['date'] =  pdict[name]=nowstr()

        # heading instruments (for hbins), first tuple is (hdg_inst, hdg_msg)
        pdict['hdg_inst_msgs'] = self.defaults['hdg_inst_msgs']
        pdict['hdg_inst'], pdict['hdg_msg'] = pdict['hdg_inst_msgs'][0]
        pdict['hcorr_inst_msg'] = self.defaults['hdg_inst_msgs']

        # get the rest of the strings
        for name in ['pos', 'pitch','roll', 'hcorr']:
            inst = name + '_inst'
            msg  = name + '_msg'
            kk = name + '_inst_msg'
            try:
                pdict[inst], pdict[msg] = self.defaults[kk]
            except (ValueError, KeyError):
                print('inst = ', inst)
                print('msg = ', msg)
                print('kk =', kk)
                print('failed self.defaults[kk]', self.defaults[kk])
                print('check settings for pos, pitch, roll, hcorr ')
                raise

        # ship-based defaults
        for name in ['hcorr_gap_fill', 'ducer_depth', 'acc_heading_cutoff']:
            pdict[name] = self.defaults[name]

        # instrument-based defaults
        for name in ['h_align', 'xducer_dx', 'xducer_dy']:
            pdict[name] = self.defaults[name]

        # instrument+ping defaults
        sdef = uhdas_defaults.proc_sonar_defaults
        for name in sdef.keys():
            pdict[name] = self.defaults[name]


#==================================================================

## move these here from onship/sensor_setup

##=================
##  sensor_cfg dictionaries and helpers
##=================


# expand this to
#   - check sensor_cfg.py 'strings' and  'messages'
#   - check an ascii file to see what kind of messages it contains

def str2msg(serstr, serstr2=None):
    '''
    return the appropriate "rbin message name" for a single ascii string
    returns None if failure
    '''
    if serstr2 is None:
        serstr = serstr.strip()
        if len(serstr) == 0:
            return None
        if serstr[0] == ':':
            return 'tss1'
        try:
            float(serstr)
            return 'spd'
        except ValueError:
            pass
        if serstr[0] != '$':
            return None


        for mm, ss in uhdas_defaults.serial_msgstr.items():
            parts = serstr.split(',')
            p0 = parts[0]
            if p0[3:6] == 'GGA':
                return 'gps'
            if p0[3:6] == 'GNS':
                return 'gns'
            if serstr[3:5] in ['HD', 'HR']:
                if len(serstr) > 6:
                    msg = {True:'hdg', False: 'hnc'}[serstr[-3] == '*']
                else:
                    # incorrect (ambiguous) if not full line
                    msg = 'hdg'
                return msg
            else:
                try:
                    # this should get exact match, eg. from sensor_cfg.py
                    return uhdas_defaults.serial_strmsg[serstr]
                except KeyError:
                    if ss in serstr:
                        # this should work for most long strings
                        return mm

        # should not have made it this far
        print('problem with str2msg: cannot identify message for', serstr)
        return None

    else:
        msg1 = str2msg(serstr)
        msg2 = str2msg(serstr2)
        # test in both orders
        if (msg1, msg2) in (('hnc', 'tss1'), ('tss1', 'hnc')):
            return 'hnc_tss1'
        elif (msg1, msg2) in (('hdg', 'tss1'), ('tss1', 'hdg')):
            return 'hdg_tss1'
        elif (msg1, msg2) in (('gps', 'psxn20'), ('psxn20', 'gps')):
            return 'gps_sea'
        elif (msg1, msg2) in (('psxn23', 'psxn20'), ('psxn20', 'psxn20')):
            return 'sea'
        else:
            return None


class Sensor_Gen:
    '''
    fill sensor_cfg values from repo.
    call 'write' method to write
    '''

    def __init__(self, shipkey=None, shipinfo=None):
        ''' "onship" indicates using the "onship" repo
            else specify an alternate path with shipconfigdir
        '''
        self.shipkey = shipkey
        self.fill_vars(shipinfo)

    def write(self, outfile):
        if os.path.exists(outfile):
            print('cannot write: %s already exists' % (outfile))
        else:
            with open(outfile, 'w') as file:
                file.write(self.sensor_cfg_str)

    def fill_vars(self, shipinfo=None):
        '''
        read the actual sensor_cfg file (toml or python)
        '''

        check_fnames = []
        for suffix in ('.toml', '.py'):
            check_fnames.append('%s_sensor_cfg%s' % (self.shipkey, suffix))
        if shipinfo is None:
            modname = 'onship'
        else:
            modname = shipinfo
        mod = __import__(modname)
        moddir = os.path.dirname(mod.__file__)
        sensor_pathfiles = [] # full paths to named sensor_cfg.*
        for fname in check_fnames:
            sensor_pathfile = os.path.join(moddir, 'sensor_cfgs', fname)
            if os.path.exists(sensor_pathfile):
                sensor_pathfiles.append(sensor_pathfile)
        self.sensor_comment = ''
        if len(sensor_pathfiles) == 0:
            _log.error('ERROR: no sensor_cfg ".py" or ".toml" found')
        if len(sensor_pathfiles) > 1:
            self.sensor_comment = '\n'.join([
                'WARNING: Found multiple sensor_cfg files:',
                '\n'.join(sensor_pathfiles)])
        # toml is first if it is there
        sensor_pathfile = sensor_pathfiles[0]
        self.sensor_cfg_str = open(sensor_pathfile,'r').read()
        self.sensor_comment += 'using sensor_file %s' % (os.path.basename(sensor_pathfile))
        self.sensor_file = sensor_pathfile # for checking

        # this is for compare_cfg
        sensor_cfg = get_cfg(sensor_pathfile)
        self.sensordict = sensor_cfg.sensor_d
        # Subset of sensors that are ADCPs:
        self.adcpdict = {k: sensor_cfg.sensor_d[k] for k in sensor_cfg.adcp_keys}

    def check_vals(self):
        for instname in self.sensordict.keys():
            serblock = self.sensordict[instname]
            allowed_msg = []
            if serblock['ext'] != 'raw':
                for ss in serblock['strings']:
                    msg = str2msg(ss)
                    if msg:
                        allowed_msg.append(msg)
                if ('$PSXN,20' in serblock['strings']) and (
                        '$PSXN,23' in serblock['strings']):
                    allowed_msg.append('sea')
                if 'tss1' in allowed_msg:
                    if 'hnc' in allowed_msg:
                        allowed_msg.append('hnc_tss1')
                    if 'hdg' in allowed_msg:
                        allowed_msg.append('hdg_tss1')
                if 'gps' in allowed_msg:
                    allowed_msg.append('ggn')
                    if 'psxn20' in allowed_msg:
                        allowed_msg.append('gps_sea')
                for ss in serblock['messages']:
                    if ss not in allowed_msg:
                        print('WARNING: message "%s" not supported' % (ss,))
                if 'hdg' in allowed_msg:
                    allowed_msg.append('gph') #heading from 2 gps
                print('\n', instname ,':')
                print('strings:', serblock['strings'])
                print('messages present:', serblock['messages'])
                print('messages allowed:', set(allowed_msg)) # uniquify
                print('=====')
                print(self.sensor_comment)

#==============================================


#---------------------------------------------------
# FIXME: this is not updated for uhdas_cfg_api and toml.
class ProcConfigChecker:
    """Mine and Check UHDAS processing configuration"""
    def __init__(self, uhdas_dir='./', ship_key=None):
        # Sanity Checks & Minimum Requirements
        self.uhdas_dir = os.path.abspath(uhdas_dir)
        # - Does UHDAS dir. exist?
        if not os.path.isdir(self.uhdas_dir):
            raise Exception(
                'uhdas directory "%s" does not exist for comparison' % uhdas_dir)
        # - Does UHDAS dir. have both raw and rbin folders? == minimum requirement
        for dir in ('raw', 'rbin'):
            if not os.path.isdir(os.path.join(self.uhdas_dir, dir)):
                raise Exception(
                    'required subdirectory %s is missing. Change uhdas_dir.' % dir)

        # - Required Processing configuration parameters
        # Note: the following dict. should be changed when *_proc_cfg.py
        #       template changes
        # FIXME: import from *_proc_cfg.py template to avoid
        #        omission based trip-hazard
        # TODO: Move this dict. at the top of the file or somewhere else
        self.required_cfg_params = Proc_Gen.define_formats_TR()

        # NMEA msg vs feed type
        ssdict = uhdas_defaults.serial_suffix
        self._pos_msgs = ssdict['position']
        self._hdg_msgs = ssdict['heading']
        self._acc_hdg_msgs = ssdict['accurate_heading']
        self._pitch_msgs = ssdict['rollpitch']
        self._roll_msgs = ssdict['rollpitch']

        # Initialize Attributes
        self.inconsistencies = dict()
        self.found_cfg_params = dict()
        for key in self.required_cfg_params.keys():
            self.found_cfg_params[key] = list()
        # - default values
        self.found_cfg_params['uhdas_dir'].append(self.uhdas_dir)
        self.found_cfg_params['hcorr_gap_fill'].append(0.0)
        self.found_cfg_params['acc_heading_cutoff'].append(0.02)

        # - fetching latest values
        self.ship_key = ship_key
        if not self.ship_key:
            self.ship_key = self.get_ship_key()

        self._new_params = Proc_Gen(shipkey=self.ship_key).pdict
        self._update_found_params(self._new_params)
        self.ship_name = self._new_params.shipname

        # Crawl for config files.  FIXME - deal with tomls as well
        # This is to identify directories with multiple processing configuration files
        self.cfg_files = []
        for dirpath, dirnames, filenames in os.walk(
                self.uhdas_dir, topdown=False, followlinks=True):
            for fn in filenames:
                # FIXME: file name logic...me no likey
                if fn.endswith("_proc.py"):
                    abs_name = os.path.join(dirpath, fn)
                    self.cfg_files.append(abs_name)
        _log.info("List of *_proc_cfg.py files: %s", self.cfg_files)

        # Collect parameters from existing config files
        self._parse_old_cfg()

        # Find available adcps
        self.available_adcps, self.available_sonars = self.get_available_adcps_and_sonars()

        # Find available feeds
        self.available_feeds = self.get_available_feeds()

        # Look for inconsistencies between available feeds and found parameters
        self._check_cfg_consistency()

    def get_ship_key(self):
        raw_files = glob.glob(os.path.join(self.uhdas_dir, 'raw/*/*.raw'))
        if not raw_files:
            raise Exception("Cannot determine ship key. Use ship_key option.")
        # Stripping file name
        # FIXME: file name logic...me no likey
        ship_key = raw_files[0].split("/")[-1].split("_")[0][:-4]

        return ship_key

    def get_available_feeds(self):
        rbin_inst_msg = self.get_rbin_inst_msg(self.uhdas_dir)
        return self._sort_feeds(rbin_inst_msg)

    @staticmethod
    def get_rbin_inst_msg(uhdas_dir):
        """
        Return a list of available feeds, [(inst0, msg0),.., (instN, msgN)]

        Args:
            uhdas_dir: path to UHDAS directory, str
        """
        inst_msg_list = []
        rbindir = os.path.join(uhdas_dir, 'rbin')
        instruments = []
        for dir in glob.glob(os.path.join(rbindir, '*')):
            instruments.append(os.path.basename(dir))

        # Sanity Check
        if len(instruments) == 0:
            raise Exception("CRITICAL: no rbins found in %s'" % rbindir)

        for instrument in instruments:
            globstr = os.path.join(rbindir, instrument, '*.rbin')
            filelist = glob.glob(globstr)
            for fname in filelist:
                parts = fname.split('.')
                inst = instrument
                msg = parts[-2]
                if (inst, msg) not in inst_msg_list:
                    inst_msg_list.append((inst, msg))

        return inst_msg_list

    def get_available_adcps_and_sonars(self):
        """
        Return a list of available ADCPs, [adcp_name0, ..., adcp_nameN]
        and sonars, [adcp_name0, ..., adcp_nameN]

        Args:
            uhdas_dir: path to UHDAS directory, str
        """
        rawdir = os.path.join(self.uhdas_dir, 'raw')
        adcps = []
        raws = []
        for dir in glob.glob(os.path.join(rawdir, '*')):
            raws.append(os.path.basename(dir))

        # Sanity Check
        if len(raws) == 0:
            raise Exception("CRITICAL: no *.raw file found in %s'" % rawdir)

        for instrument in raws:
            globstr = os.path.join(rawdir, instrument, '*.raw')
            filelist = glob.glob(globstr)
            for fname in filelist:
                inst = instrument
                if inst not in adcps:
                    adcps.append(inst)

        # Find possible modes
        sonars = []
        for adcp in adcps:
            sonars.extend(uhdas_defaults.instpings(adcp))

        return adcps, sonars

    def _sort_feeds(self, inst_msg_list):
        # FIXME: get those info from centralized location
        instbunch = Bunch()
        for name in ('position', 'heading', 'accurate_heading', 'pitch',
                     'roll', 'unknown'):
            instbunch[name] = []
        for inst, msg in inst_msg_list:
            known = False
            if msg in self._pos_msgs:
                instbunch['position'].append((inst, msg))
                known = True
            if msg in self._hdg_msgs: #hdg_tss1, hnc, hpr:
                instbunch['heading'].append((inst, msg))
                known = True
            if msg in self._acc_hdg_msgs:
                instbunch['accurate_heading'].append((inst, msg))
                known = True
            if msg in self._pitch_msgs:
                instbunch['pitch'].append((inst, msg))
                known = True
            if msg in self._roll_msgs:
                instbunch['roll'].append((inst, msg))
                known = True
            if not known:
                instbunch['unknown'].append((inst, msg))
                _log.error("Unknown feed: (%s, %s)", inst, msg)

        return instbunch

    def _check_cfg_consistency(self):
        """Check consistency between available feeds and specified cfg. params"""
        # FIXME: This method should be reviewed/refactored when proc_cfg.py
        #        template is changed...
        # Checking heading feeds
        if self.found_cfg_params['hdg_inst_msgs']:
            hdg_feeds = (self.available_feeds['heading'] +
                         self.available_feeds['accurate_heading'])
            for feed_list in self.found_cfg_params['hdg_inst_msgs']:
                for feed in feed_list:
                    if feed not in hdg_feeds:
                        if 'hdg_inst_msgs' not in self.inconsistencies.keys():
                            self.inconsistencies['hdg_inst_msgs'] = list()
                        self.inconsistencies['hdg_inst_msgs'].append(feed)

        # Checking position feed
        self._check_feed_consistency('pos_inst', 'pos_msg', 'position')
        # Checking pitch feed
        self._check_feed_consistency('pitch_inst', 'pitch_msg', 'pitch')
        # Checking roll feed
        self._check_feed_consistency('roll_inst', 'roll_msg', 'roll')
        # Checking primary heading feed
        self._check_feed_consistency('hdg_inst', 'hdg_msg', 'heading')
        # Checking primary heading feed
        self._check_feed_consistency('hcorr_inst', 'hcorr_msg', 'accurate_heading')

    def _check_feed_consistency(self, inst_key, msg_key, feed_key):
        if self.found_cfg_params[inst_key] and self.found_cfg_params[msg_key]:
            pos_feeds = self.available_feeds[feed_key]
            for pos_inst in self.found_cfg_params[inst_key]:
                for pos_msg in self.found_cfg_params[msg_key]:
                    feed = (pos_inst, pos_msg)
                    if feed not in pos_feeds:
                        if inst_key not in self.inconsistencies.keys():
                            self.inconsistencies[inst_key] = list()
                        self.inconsistencies[inst_key].append(feed)
                        if msg_key not in self.inconsistencies.keys():
                            self.inconsistencies[msg_key] = list()
                        self.inconsistencies[msg_key].append(feed)

    def _parse_old_cfg(self):
        for fn in self.cfg_files:
            cfg_params = Bunch().from_pyfile(fn)
            self._update_found_params(cfg_params)

    def _update_found_params(self, d):
        keys = list(d.keys())
        for key in self.required_cfg_params.keys():
            if key in keys:
                val = d[key]
                # Little conversion...me no likey either
                if isinstance(val, Bunch):
                    val = dict(val)

                if val not in self.found_cfg_params[key]:
                    # Sanity check
                    if isinstance(val, self.required_cfg_params[key]['type']):
                        self.found_cfg_params[key].append(val)
                    else:
                        _log.error("%s has the wrong type: %s", key, type(val))

    def __repr__(self):
        shipname = self.ship_name
        available_adcps = self.available_adcps
        available_sonars = self.available_sonars
        found_params = Bunch(self.found_cfg_params)
        available_feeds = Bunch(self.available_feeds)
        inconsistencies = Bunch(self.inconsistencies)
        return f"""
Process Configuration Assessment for {shipname}:
================================================
- Available ADCPs:
  ---------------
{available_adcps}

- Available Sonars:
  ---------------
{available_sonars}

- Parameters Found:
  ----------------
{found_params}
- Available Feeds:
  ---------------
{available_feeds}
- Inconsistencies:
  ---------------
{inconsistencies}
"""
