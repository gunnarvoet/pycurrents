'''
This file contains methods used in the q_npy processor inside quick_adcp.py.
These are calculation methods, not plotting methods.
'''

import os
import glob
import time
import numpy as np
# Add command-line ability later.
#from optparse import OptionParser
import logging
from string import Template

from pycurrents.adcp.nav import RefSmooth
from pycurrents.system.misc import ScripterBase, guess_comment
from pycurrents.adcp.raw_multi import Multiread   # singleping ADCP
from pycurrents.adcp.uhdasfileparts import FileParts
from pycurrents.codas import to_datestring
from pycurrents.file.binfile_n import BinfileSet
import pycurrents.system.pathops as pathops
from pycurrents.adcp.gbin import Gbinner
from pycurrents.adcp.pingavg import Pingavg,  ping_dday_transition
from pycurrents.adcp.quick_setup import quickFatalError
from pycurrents.system.misc import Cachefile, nowstr
from pycurrents.adcp.adcp_specs import Sonar, check_sonar
from pycurrents.adcp.pingedit import CODAS_AutoEditor
from pycurrents.adcp.adcp_specs import ping_editparams, codas_editparams
from pycurrents.adcp.uhdasconfig import UhdasConfig
from pycurrents.adcp.vmdas import LTA_Translate, VmdasInfo
from pycurrents.data.navcalc import lonlat_shifted, xducer_offset
from pycurrents.num import Stats            # mean,std,med (masked)
from pycurrents.num.nptools import rangeslice
from pycurrents.codas import get_profiles
from pycurrents.num.nptools import loadtxt_

# Standard logging
_log = logging.getLogger(__name__)


_runstr = '''
#!/usr/bin/env python

## written by quick_adcp.py-- edit as needed:


'''

class Scripter(ScripterBase):
    script_head = _runstr

#-------------

_refsmstr = '''
from pycurrents.adcp.quick_npy import Refsm

# refuv_inputfile  : identify the filename for determining uship, vship
#                  :     - defaults to position file (t,x,y)
#                  :     - but could be uvship from Pingavg
# refuv_source : identify what the columns mean:
#              :   - 'nav' (for positions) columns 0, 1, 2
#              :   - 'uvship' (for uvship) columns 0, 1, 2
# ens_len      : averaging length in seconds
# bl_half_width: blackman filter halfwidth (number of ensembles)
#              : default = 3
#              : setting to 0 disables smoothing
#              :    still use refsm to write the 'refsm_tuv.asc' file
#              : This variable is called "refuv_smoothwin" in the options
#              :
#  For more details, see pycurrents.adcp.nav.RefSmooth

Ref = Refsm()
Ref(dbname='${dbname}',
    dbpath='${dbpath}',
    proc_yearbase=${proc_yearbase},
    refuv_inputfile='${refuv_inputfile}',
    refuv_source='${refuv_source}',
    ens_len=${ens_len},
    bl_half_width=${bl_half_width},
    pgmin=${pgmin},
    rl_startbin=${rl_startbin},
    rl_endbin=${rl_endbin})
'''

class Refsm(Scripter):
    script_body = _refsmstr

    defaultparams = dict(pgmin=30,       # edit out uv profiles
                         rl_startbin=2,
                         rl_endbin=20,
                         ens_len=300,
                         bl_half_width=None, #refuv_smoothwin
                         proc_yearbase=None,
                         refuv_inputfile=None,
                         refuv_source=None,    #'nav', 'uvship'
                         dbpath='../adcpdb',
                         dbname=None,)

    def process_params(self):
        p = self.params

        if p['proc_yearbase'] is None:
            raise ValueError('proc_yearbase must be set')
        if p['refuv_source']  not in ('nav','uvship'):
            msg = '%s value of %s: not supported'
            _log.debug(msg % ('refuv_source', p['refuv_source']))
            raise ValueError('refuv_source must be set')
        if p['refuv_inputfile'] is None:
            raise ValueError('refuv_inputfile must be set')
        if p['dbname'] is None:
            raise ValueError('dbname must be set')
        if int(p['bl_half_width']) not in np.arange(0,10,1):
            print(p)
            raise ValueError("reflayer smoothing: integer 0-10")
        fn = p['refuv_inputfile']
        if fn is None or not os.path.exists(fn):
            raise ValueError("refuv input file %s does not exist."%(fn,))

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)

        R = RefSmooth(min_maxpg=self.pgmin,
                      ref_top=self.rl_startbin,
                      ref_bot=self.rl_endbin,
                      ensemble_secs=self.ens_len,
                      bl_half_width=int(self.bl_half_width),
                      )
        dbpathname = os.path.join(self.dbpath, self.dbname)
        if not R.read_data(dbpathname,
                           self.refuv_inputfile,
                           self.proc_yearbase,
                           uvsource=self.refuv_source):
            return False

        R.adcp_nav()
        header = Template('''#   yearbase = ${proc_yearbase}
#    refuv_inputfile='${refuv_inputfile}',
#    refuv_source='${refuv_source}',
#    ens_len=${ens_len},
#    bl_half_width=${bl_half_width},
#    pgmin=${pgmin},
#    rl_startbin=${rl_startbin},
#    rl_endbin=${rl_endbin}
''').substitute(self.__dict__)

        R.write_asc('refsm_tuv.asc', header=header)
        return True

#-------------
# docs
# early version: attempt to scan using BinfileSet
# deprecated -- use gbin version instead, "Scanping"


_scanbinstr = '''

from pycurrents.adcp.quick_npy import Scanbin


Sc = Scanbin()
Sc(outfilebase= '${dbname}',
    gbinsonar = '${gbinsonar}',
    yearbase = ${yearbase})
'''

class Scanbin(Scripter):
    '''
    early simpler version of "scan"; does not require gbins
    '''
    script_body = _scanbinstr

    defaultparams = dict(dbname='Scanbin',
                         yearbase=None,
                         gbinsonar = None)

    def process_params(self):
        p = self.params
        for kk in p.keys():
            if p[kk] is None:
                raise ValueError('%s must be set' % (kk,))

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)

        bs=BinfileSet(os.path.join(self.gbinsonar,'time','*tim.gbin'),
               alias = dict(unix_dday='u_dday', monotonic_dday='m_dday',
                            logger_dday='u_dday', bestdday='dday'))

        scnfile = '%s.scn' % (self.dbname,)

        firstfilebase = os.path.split(bs.allfilenames[0])[-1].split('.')[0]
        lastfilebase = os.path.split(bs.allfilenames[-1])[-1].split('.')[0]

        line = '%s-%s, %s to %s (%10.7f, %10.7f)\n' % (
            firstfilebase,
            lastfilebase,
            to_datestring(self.yearbase, bs.dday[0]),
            to_datestring(self.yearbase, bs.dday[-1]),
            bs.dday[0], bs.dday[-1])

        with open(scnfile,'w') as file:
            file.write(line)


#-------------------

_scanpingstr = '''

from pycurrents.adcp.quick_npy import Scanping

Sc = Scanping()
Sc(dbname= '${dbname}',
   cfgpath = '${cfgpath}',
   configtype = '${configtype}',
   cruisename = '${cruisename}',
   py_gbindirbase = '${py_gbindirbase}',
   sonar = '${sonar}',
   )
'''

class Scanping(Scripter):
    script_body = _scanpingstr

    defaultparams = dict(dbname=None,
                         cfgpath=None,
                         cruisename=None,
                         configtype=None,
                         sonar = None,
                         py_gbindirbase = None)

    def process_params(self):
        p = self.params
        for kk in p.keys():
            if p[kk] is None:
                raise ValueError('%s must be set' % (kk,))

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)

        uhdas_cfg = UhdasConfig(cfgpath= self.cfgpath,
                                cruisename=self.cruisename,
                                configtype=self.configtype,
                                sonar= self.sonar,
                                gbin = self.py_gbindirbase)

        gstring = os.path.join(uhdas_cfg.gbinsonar,'time','*tim.gbin')
        gbinfiles = sorted(glob.glob(gstring))
        if len(gbinfiles) == 0:
            msg='no gbin time files in %s' % (gstring)
            _log.exception('Failure in: %s', 'Scanping') #traceback in logfile
            raise quickFatalError('Q_npy.runcalc: Scanping failure.\n %s' % (
                                  msg))

        datafiles=pathops.corresponding_pathname(gbinfiles,
                                                 uhdas_cfg.rawsonar, '.raw')

        if uhdas_cfg.sonar.model == 'os':
            mixed_pings = check_sonar(self.sonar)
            if mixed_pings:
                m = Multiread(datafiles, uhdas_cfg.sonar.instname,
                      gbinsonar= uhdas_cfg.gbinsonar)
                pingtype = None
            else:
                m = Multiread(datafiles, uhdas_cfg.sonar.sonar,
                      gbinsonar= uhdas_cfg.gbinsonar)
                pingtype = uhdas_cfg.sonar.pingtype
        else:
            m = Multiread(datafiles, uhdas_cfg.sonar.sonar,
                          gbinsonar= uhdas_cfg.gbinsonar)
            pingtype = uhdas_cfg.sonar.pingtype

        nchunks = len(m.chunks)

        lines=['\n\n# %s ping details' % (pingtype,),
               '#file range                           ' +
               'date range                                  ' +
               '(dday range)',]

        for ichunk in range(nchunks):
            m.select_chunk(ichunk)
            fp = FileParts(m.selected_files(), uhdas_cfg.yearbase)
            #
            ichunkfirst = m.iselect[0]  # first file index for this chunk
            ichunklast = m.iselect[-1]  # last  file index for this chunk
            iddaycol = m.bs.columns.index('dday') # column index for dday
            #
            chunk_startdday = m.bs.starts[ichunkfirst][iddaycol]
            chunk_enddday = m.bs.ends[ichunklast][iddaycol]
            #
            lines.append('%s-%s, %s to %s (%10.7f, %10.7f)' % (
                fp.basenames[0],
                fp.basenames[-1],
                to_datestring(uhdas_cfg.yearbase, chunk_startdday),
                to_datestring(uhdas_cfg.yearbase, chunk_enddday),
                chunk_startdday,
                chunk_enddday))

        dumpstr = ''.join(
            ['# crude configuration dump:\n'
            '#index, #files, startdd, enddd, BT, ',
             '(pingtype, number of bins, bin size(m), blank(m), pulse(m))',
            '\n',
             m.list_chunks(),
            '\n'])

        scnfile = '%s.scn' % (self.dbname,)
        with open(scnfile,'w') as file:
            file.write('\n'.join(lines) + '\n\n' + dumpstr)


#----------------------


_pygbinstr = '''

from pycurrents.adcp.quick_npy import Pygbin

#This stub sets calls the quick_adcp.py Pygbin method,
# which calls pycurrents.adcp.gbin.Gbinner

## add a line like this to control maximum number of files grouped in TimeCal
# max_files_per_seg = 1,

P = Pygbin()
P(cfgpath= '${cfgpath}',
    cruisename='${cruisename}',
    configtype = '${configtype}',
    sonar= '${sonar}',
    gbin_gap_sec = ${gbin_gap_sec},  # do not interpolate if gap is longer
    py_gbindirbase = '${py_gbindirbase}')

'''

class Pygbin(Scripter):
    script_body = _pygbinstr

    defaultparams = dict(cfgpath = '../config',
                         cruisename = None,
                         configtype = None,
                         sonar=None,
                         gbin_gap_sec = 15.,
                         max_files_per_seg = 6, # default
                         py_gbindirbase = None,
                         update =True)

    def process_params(self):
        p = self.params
        for kk in p.keys():
            if p[kk] is None:
                raise ValueError('%s must be set' % (kk,))

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)


        uhdas_cfg = UhdasConfig(cfgpath= self.cfgpath,
                  cruisename=self.cruisename,
                  configtype=self.configtype,
                  sonar= self.sonar,
                  gbin = self.py_gbindirbase)


        if hasattr(uhdas_cfg, 'acc_heading_cutoff'):
            rbin_edit_params=dict(acc_heading_cutoff=uhdas_cfg.acc_heading_cutoff)
        else:
            rbin_edit_params={}

        gb = Gbinner(cruisedir = uhdas_cfg.uhdas_dir,
                     sonar = self.sonar,
                     gbin = uhdas_cfg.gbin,
                     config = uhdas_cfg.gbin_params,
                     timeinst = uhdas_cfg.gbin_params['pos_inst'],
                     gbin_gap_sec = self.gbin_gap_sec, #
                     max_files_per_seg = self.max_files_per_seg,
                     msg = uhdas_cfg.gbin_params['pos_msg'],
                     rbin_edit_params = rbin_edit_params)

        gb(update=self.update)

    #--- end gbinning ---------------------------------------------


_scanltastr = '''

from pycurrents.adcp.quick_npy import ScanLTA

#This stub sets calls the quick_adcp.py ScanLTA method,
# which calls pycurrents.adcp.vmdas.VmdasInfo

# data_filelist should contain the filenames regardless of
#   how they were presented in the original call to quick_adcp.py


S = ScanLTA()
S(dbname='${dbname}',
  data_filelist='${data_filelist}',
  sonar='${sonar}')

'''

class ScanLTA(Scripter):
    script_body = _scanltastr

    defaultparams = dict(dbname=None,
                         data_filelist=None,
                         sonar=None)

    def process_params(self):
        p = self.params

        # data_filelist is now required

        if not os.path.exists(p['data_filelist']):
            errmsg = 'data files should be in data file %s' % (p['data_filelist'])
            raise ValueError(errmsg)

        with open(p['data_filelist'], 'r') as newreadf:
            firstlist=newreadf.readlines()
        filelist = []
        for f in firstlist:
            if os.path.exists(f.rstrip()):
                filelist.append(f.rstrip())
        if len(filelist) == 0:
            errmsg = 'could not get filelist using data file %s' % (p['data_filelist'])
            raise ValueError(errmsg)

        self.filelist = filelist

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)
        sonar=Sonar(self.sonar)

        v=VmdasInfo(self.filelist, sonar.model)
        tr=v.print_scan(self.dbname + '.scn')
        with open(self.dbname+'.tr','w') as file:
            file.write('%s to %s\n' % (tr[0],tr[1]))

        # update beam angle from raw data just read
        beamangle = v.infodicts[v.filelist[0]]['sysconfig']['angle']
        cc = Cachefile(cachefile='../dbinfo.txt',
                       contents='metadata, %s' % (nowstr()))
        cc.read()
        cc.cachedict.update({'beamangle': beamangle})
        cc.write()

    #--- end scanlta ---------------------------------------------


_loadltastr = '''

from pycurrents.adcp.quick_npy import LoadLTA

#This stub sets calls the quick_adcp.py LoadLTA method,
# which calls pycurrents.adcp.vmdas.LTATranslate


# data_filelist now required; should be written regardless of
#    how quick_adcp.py found the files

L = LoadLTA()
L(dbname='${dbname}',
  data_filelist='${data_filelist}',
  sonar= '${sonar}')

'''

class LoadLTA(Scripter):
    script_body = _loadltastr

    defaultparams = dict(dbname=None,
                         data_filelist=None,
                         sonar=None)

    def process_params(self):
        p = self.params

        if not os.path.exists(p['data_filelist']):
            errmsg = 'data files should be in data file %s' % (p['data_filelist'])
            raise ValueError(errmsg)

        with open(p['data_filelist'], 'r') as newreadf:
            firstlist = newreadf.readlines()
        filelist = []
        for f in firstlist:
            if os.path.exists(f.rstrip()):
                filelist.append(f.rstrip())
        if len(filelist) == 0:
            errmsg = 'could not get filelist using data file %s' % (
                p['data_filelist'])
            raise ValueError(errmsg)

        self.filelist = filelist

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''
        Scripter.__call__(self, **kw)
        LTA_Translate(self.filelist, self.sonar)

    #--- end loadlta ---------------------------------------------


_loadstr = '''

from pycurrents.adcp.quick_npy import PingAverage


# paths are relative to "load" (quick_adcp.py already 'cd load')
# hcorr inst must be set in control files

P = PingAverage()
P(sonar = '${sonar}',
  cruisename = '${cruisename}',
  cfgpath = '${cfgpath}',
  configtype = '${configtype}',
  py_gbindirbase = '${py_gbindirbase}',
  edit_paramfile = 'ping_editparams.txt',
  xducer_dx = ${xducer_dx},
  xducer_dy = ${xducer_dy},
  uvwref_start = ${uvwref_start},
  uvwref_end = ${uvwref_end},
  ping_headcorr = ${ping_headcorr},
  ens_len = ${ens_len},
  max_BLKprofiles = ${max_BLKprofiles},
  dday_bailout = ${dday_bailout},
  new_block_on_start = ${new_block_on_start},
  use_rbins = ${use_rbins},
  incremental = ${incremental},   # required for pingpref
  pingpref = '${pingpref}',     #'bb' or 'nb'; see docs for details
  badbeam = ${badbeam},  # 1,2,3,4
  beam_order = ${beam_order}, # [1,2,3,4] # a list
  yearbase = ${yearbase})

'''

## if you use iPython to run this as "run PingAverage_script.py"
## and set the bailout_dday, it will step along and quit at that
## time. Then you can access the raw data as ens = P.gb.ens
## where 'ens' is a Bunch from Multiread, with lots of useful variables.


class PingAverage(Scripter):
    script_body = _loadstr

    defaultparams = dict(sonar = None,
                         cruisename = None,
                         cfgpath = None,
                         configtype=None,
                         py_gbindirbase = None,
                         edit_paramfile =  'ping_editparams.txt',
                         ping_headcorr = False,
                         xducer_dx = None,
                         xducer_dy = None,
                         uvwref_start = None,
                         uvwref_end = None,
                         dday_bailout = None,
                         use_rbins = False,
                         stop_n = None,
                         ens_len = 300,
                         max_BLKprofiles = 300,
                         incremental = True,
                         new_block_on_start = False,
                         pingpref = None,
                         badbeam = None,
                         beam_order = None,
                         yearbase = None,
                         )

    def process_params(self):

        p = self.params
        for kk in p.keys():
            if kk not in ['dday_bailout', 'stop_n', 'badbeam', 'beam_order',
                          'uvwref_start', 'uvwref_end', 'use_rbins',
                          'xducer_dx', 'xducer_dy', 'pingpref']:
                if p[kk] is None:
                    raise ValueError('%s must be set' % (kk,))

    def ping_transition(self):
        instrument = self.sonar.instname
        uhdas_dir = os.path.split(self.py_gbindirbase)[0]
        filelist=pathops.make_filelist(os.path.join(uhdas_dir, 'raw', instrument, '*.raw'))
        if self.pingpref not in ('bb','nb'):
            raise ValueError('pingpref is "%s". can only be "bb" or "nb"' % (self.pingpref))
        m=Multiread(filelist, instrument)  ## get all pings, do not use sonar
        pd = ping_dday_transition(m, pingpref=self.pingpref)
        return pd #pingtype, startdd, enddd

    def __call__(self, **kw):
        '''
        See defaultparams

        at present:

        loader requires two parameter dictionaries:
            params (tr_depth, head_align, hcorr, velscale)
            edit_params (see default_params)

        params comes via UhdasConfig
              matlab config
                  - cruise_cfg.m (uhdas_dir, hcorr_inst)
                  - cruise_proc.m (tr_depth, head_align, velscale)
              python config
                  - cruise_proc.py (uhdas_dir,
                                   hcorr_inst, hcorr_msg, gap fill
                                   tr_depth, head_align, velscale)

        '''
        Scripter.__call__(self,  **kw)

        # Scripter requires this mechanism
        # try to read editparams

        # remove a bad beam from consideration
        if self.badbeam is None:
            self.ibadbeam = None
        else:
            # badbeam is for the user, an integer in 1,2,3,4
            # ibadbeam is 0-based, ultimately for Multiread
            self.ibadbeam = int(self.badbeam) - 1
            _log.info('bad beam number %d, (ibadbeam= %d)' % (
                                     self.badbeam, self.ibadbeam))

        # re-order the beams if the were mis-wired (eg. KM in 2003, RR in 2020)
        if self.beam_order is None:
            self.beam_index = None
        else:
            # beam_order is for the user, a python list with beam order [1,2,3,4]
            # beam_index is 0-based, ultimately for Multiread [0,1,2,3]
            self.beam_index = []
            for beamnum in self.beam_order:
                self.beam_index.append(beamnum - 1)

        sonar=Sonar(self.sonar)
        self.sonar=sonar

        uhdas_cfg = UhdasConfig(cfgpath= self.cfgpath,
                               cruisename=self.cruisename,
                               configtype=self.configtype,
                               sonar= self.sonar)

        # paths are relative to "load" (quick_adcp.py already 'cd load')
        # transducer-adcp offset
        if self.xducer_dx is None and self.xducer_dy is None:
            xducerxy = None
        else:
            if self.xducer_dx is None:
                self.xducer_dx = 0
            if self.xducer_dy is None:
                self.xducer_dy = 0
            xducerxy = [self.xducer_dx, self.xducer_dy]
        _log.debug('xducerxy is ' + str(xducerxy))


        # write out single-ping reflayer values for u,v,w
        if self.uvwref_start is None or self.uvwref_end is None:
            uvwref = None
        else:
            uvwref = [int(self.uvwref_start), int(self.uvwref_end)]
        _log.debug('uvwref is ' + str(uvwref)) #xxx


        # initialize, then override editing parameters
        ## single-ping editing parameters
        # ibadbeam is only needed to alter (skip) the errvel criterion
        editparams = ping_editparams(uhdas_cfg.sonar.instname,
                                             badbeam=self.ibadbeam)
        try:
            cc=Cachefile(cachefile=self.edit_paramfile)
            cc.read()
            editparams.update_values(cc.cachedict)
        except:
            msg='could not read singleping parameters in %s' % (
                                       self.edit_paramfile)
            _log.exception(msg)
            raise quickFatalError(msg)

        _log.debug('singleping editing parameters:')
        for k in editparams.keys():
            if int(editparams[k]) == float(editparams[k]):
                _log.debug('%20s : %d', k, editparams[k])
            else:
                _log.debug('%20s : %f', k, editparams[k])

        mixed_pings = check_sonar(sonar)
        if mixed_pings:
            if self.pingpref is None:
                msg = 'mixed pings, but pingpref is None'
                _log.exception(msg)
                raise quickFatalError(msg)

        if mixed_pings:
            pingdays = self.ping_transition()

            for pingtype, startdday, enddday in pingdays:

                _log.info('==> mixed pings: pingtype %s, ddrange %f-%f' % (
                    pingtype, startdday, enddday))

                instping = self.sonar.instname + pingtype
                pingavg_params = uhdas_cfg.get_pingavg_params(pingtype=pingtype)
                # uhdas_cfg only has the attribute if there is a correction to make
                # heading correction:  this is the opposite convention of pingavg
                pingavg_params.apply_hcorr = False
                if self.ping_headcorr:
                    pingavg_params.apply_hcorr = True


                self.gp = Pingavg(datadir=uhdas_cfg.rawsonar,
                   gbinsonar=os.path.join(self.py_gbindirbase, sonar.instname),
                   loaddir = './',
                   calrotdir = '../cal/rotate',
                   sonar = instping,
                   ens_len = self.ens_len,
                   blk_max_nprofs = self.max_BLKprofiles,
                   update=self.incremental,
                   new_block_on_start=True,
                   yearbase=self.yearbase,
                   ibadbeam=self.ibadbeam,
                   beam_index=self.beam_index,
                   params=pingavg_params,
                   use_rbins=self.use_rbins,
                   uvwref=uvwref,
                   edit_params=editparams,
                   xducerxy=xducerxy)

                if self.dday_bailout is not None:
                    if self.stop_dday < enddday:
                        print('stopping early')
                        stop_dday = self.stop_dday
                    else:
                        stop_dday = enddday
                else:
                    stop_dday = enddday


                N = self.gp.run(stop_dday = stop_dday,
                        stop_n = self.stop_n)
                if N:
                    _log.debug('wrote %d averages\n' % (N))
                else:
                    _log.debug('nothing written')
        else:
            pingavg_params = uhdas_cfg.get_pingavg_params()
            pingavg_params.apply_hcorr = False
            if self.ping_headcorr:
                pingavg_params.apply_hcorr = True

            self.gp = Pingavg(datadir=uhdas_cfg.rawsonar,
                   gbinsonar=os.path.join(self.py_gbindirbase, sonar.instname),
                   loaddir = './',
                   calrotdir = '../cal/rotate',
                   sonar=self.sonar, #Loader deals with it
                   ens_len = self.ens_len,
                   blk_max_nprofs = self.max_BLKprofiles,
                   new_block_on_start=self.new_block_on_start,
                   update=self.incremental,
                   yearbase=self.yearbase,
                   ibadbeam=self.ibadbeam,
                   beam_index=self.beam_index,
                   params=pingavg_params,
                   use_rbins=self.use_rbins,
                   uvwref=uvwref,
                   edit_params=editparams,
                   xducerxy=xducerxy)

            N = self.gp.run(stop_dday = self.dday_bailout,
                        stop_n = self.stop_n)

            _log.debug('wrote %d averages\n' % (N))


        # update beam angle from raw data just read
        sonar = Sonar(self.sonar)
        cc = Cachefile(cachefile='../dbinfo.txt',
                       contents='metadata, %s' % (nowstr()))
        cc.read()
        cc.cachedict.update({'beamangle': self.gp.beam_angle})
        cc.write()

#-------------


_autoeditstr = '''

from pycurrents.adcp.pingedit import CODAS_AutoEditor

# docs

## if the file 'codas_editparams.txt' exists, values
##        present will override defaults from
##        pycurrents.adcp.adcp_specs.codas_editparams
##
## this file can also be used by gautoedit.py to override
##        defaults (same mechanism)



from pycurrents.adcp.adcp_specs import codas_editparams
A = CODAS_AutoEditor(codas_editparams, '../adcpdb/${dbname}',
                      editparams_file='codas_editparams.txt',
                      verbose=True)
A.set_beamangle(beamangle = ${beamangle}) #from ../dbinfo.txt
A.get_data(ddrange=[${edit_startdd}, ${edit_enddd}])
A.write_flags(fformat='${fformat}', openstyle = 'w')

'''

class AutoEdit(Scripter):
    '''
    quick_adcp.py  should have already written the file
    "codas_editparams.txt"  in the "edit".    The file will
    contain the default codas editing values in
    pycurrents.adcp.adcp_specs.codas_editparams.  That file
    is then read by the Autoeditor (and gautoedit.py).
    '''

    script_body = _autoeditstr

    defaultparams = dict(dbname=None,
                         edit_startdd=None,
                         edit_enddd=None,
                         beamangle = None,
                         fformat=None,
                         )

    def process_params(self):
        p = self.params
        for kk in p.keys():
            if p[kk] is None:
                raise ValueError('%s must be set' % (kk,))

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)


        A=CODAS_AutoEditor(codas_editparams, '../adcpdb/%s' % (self.dbname),
                           editparams_file='codas_editparams.txt')
        A.set_beamangle(beamangle=self.beamangle)
        A.get_data(ddrange=[self.edit_startdd, self.edit_enddd])
        A.write_flags(fformat='a%s_tmp.asc', openstyle='w')

#---------------------

_xducerxystr = '''


# docs
# call from "nav" subdirectory

from pycurrents.adcp.quick_npy import XducerXY

# fixfile is *.gps (input points from GPS)
# fixfilexy is *.agt, transposed positions
#           calculation of offset done on new positions

# initialize
XY = XducerXY(dbname='../adcpdb/${dbname}',
              headingfile = '../cal/rotate/scn.hdg',
              fixfile = '${fixfile}',
              fixfilexy = '${fixfilexy}',
              xducerxy_dx = ${sum_xducer_dx},
              xducerxy_dy = ${sum_xducer_dy},
              )

# call
XY()

'''

class XducerXY(Scripter):
    '''
    create a new fix file that accounts for the offset between ADCP and GPS
    uses 'dx' (ADCP starboard of GPS) and 'dy' (ADCP fwd of GPS)
    '''

    script_body = _xducerxystr

    defaultparams = dict(dbname=None,
                         headingfile = '../cal/rotate/scn.hdg',
                         fixfile = None,
                         fixfilexy=None,
                         sum_xducer_dx = 0,
                         sum_xducer_dy = 0,
                         )

    def process_params(self):
        p = self.params
        for kk in p.keys():
            if p[kk] is None:
                raise ValueError('%s must be set' % (kk,))

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)

        comment = guess_comment(self.fixfile)
        txy = loadtxt_(self.fixfile, comments=comment)
        t,x,y = txy[:,0], txy[:,1], txy[:,2]

        comment = guess_comment(self.headingfile)
        thhc = loadtxt_(self.headingfile, comments=comment)
        ## FIXME: should "correction" be used somewhere?
        #dday, lasthead, correction  = thhc[:,0], thhc[:,-2], thhc[:,-1],
        dday, lasthead  = thhc[:,0], thhc[:,-2]

        if len(t) != len(dday):
            _log.debug('\n'.join(['returning from xducerxy with no output',
                                 'fix file and heading file unequal lengths']))
            return
        newlon, newlat = lonlat_shifted(x,y, lasthead,
                                      starboard=self.sum_xducer_dx,
                                      forward=self.sum_xducer_dy)
        fid=open(self.fixfilexy, 'w')
        lines = ['# inputfile %s' % (self.fixfile),
                 '# xducer_dx = %f' % (self.sum_xducer_dx),
                 '# xducer_dy = %f' % (self.sum_xducer_dy)]
        for ll in zip(dday, newlon, newlat):
            lines.append('%10.7f   %10.6f  %10.6f' % ll)
        fid.write('\n'.join(lines))
        fid.close()

#---------------------

_guess_xducerxystr = '''


# docs
# call from "cal/watertrk" subdirectory

from pycurrents.adcp.quick_npy import Guess_Xducerxy

# initialize
GuessXY = Guess_Xducerxy(dbname='${dbname}',
                         fixfilexy='${fixfilexy}')

# call
GuessXY()

'''

class Guess_Xducerxy(Scripter):
    '''
    write a file with a guess of xducerxy dx,dy
    '''

    script_body = _guess_xducerxystr

    defaultparams = dict(dbname=None,
                         fixfilexy=None
                         )

    def process_params(self):
        p = self.params
        for kk in p.keys():
            if p[kk] is None:
                raise ValueError('%s must be set' % (kk,))

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)

        dd=get_profiles(os.path.join('../../adcpdb',self.dbname))


        ## needs work!!
        zrange=[0,200]
        zsl=rangeslice(dd.dep, zrange[0], zrange[-1])

        refl=dict(uship = Stats(dd.umeas[:,zsl], axis=1).mean.flatten(),
                  vship = Stats(dd.vmeas[:,zsl], axis=1).mean.flatten())

        dx, dy, signal = xducer_offset(dd.dday, dd.lon, dd.lat,
                                       refl['uship'], refl['vship'],
                                       dd.last_heading, ndiff=2)

        if np.ma.getmask(dx+dy+signal) is True:
            _log.warning("Cannot compute transducer offset")
            return

        fid=open('guess_xducerxy.out','a')
        fid.write('\n'.join(
            ['',
             'guessing ADCP (dx=starboard, dy=fwd) meters from GPS',
             'positions from %s' % (self.fixfilexy),
             'calculation done at ' + time.strftime("%Y/%m/%d %H:%M:%S"),
             'xducer_dx = %f' % (dx),
             'xducer_dy = %f' % (dy),
             'signal = %f' % (signal),
             '']))
        fid.close()


#---------------------

dirdict = dict(refsm='nav',
               refsm_uvship='nav',
               scanbin='scan',
               scanping='scan',
               autoedit='./',     #chdir in quick_run.py beforehand
               pygbin='./',       #chdir in quick_run.py beforehand
               scanlta='./',      #chdir in quick_run.py beforehand
               loadlta='./load',
               pingavg='./',      #chdir in quick_run.py beforehand
               xducerxy='./',     #chdir in quick_run.py beforehand
               guess_xducerxy='./',     #chdir in quick_run.py beforehand
            )

classdict = dict(refsm=Refsm,
                 scanbin=Scanbin,
                 scanping=Scanping,
                 autoedit=AutoEdit,
                 pygbin=Pygbin,
                 scanlta=ScanLTA,
                 loadlta=LoadLTA,
                 pingavg=PingAverage,
                 xducerxy=XducerXY,
                 guess_xducerxy=Guess_Xducerxy,
            )
#---------------------

class Q_npy:
    '''Calculation methods.'''

    #-------

    def run_calc(self, calcname, **kw):
        _log.debug('Starting: %s', calcname)
        calcdir = dirdict[calcname]
        startdir = os.getcwd()
        os.chdir(calcdir)
        output = None
        try:
            Calc = classdict[calcname](self.opts, **kw)
            Calc.write()
            output = Calc()
        except:
            _log.exception('Failure in: %s', calcname) #traceback in logfile
            raise quickFatalError('Q_npy.runcalc: %s failure ', calcname)
        finally:
            os.chdir(startdir)
            _log.debug('Ending: %s', calcname)
            return output

    #========= the rest use Scripter ========================

    def run_refsm_npy(self, **kw):
        return self.run_calc('refsm', **kw)

    def run_scanbin_npy(self, **kw):
        return self.run_calc('scanbin', **kw)

    def run_scanping_npy(self, **kw):
        return self.run_calc('scanping', **kw)

    def run_pygbin_npy(self, **kw):
        return self.run_calc('pygbin', **kw)

    def run_scanlta_npy(self, **kw):
        return self.run_calc('scanlta', **kw)

    def run_loadlta_npy(self, **kw):
        return self.run_calc('loadlta', **kw)

    def run_pingavg_npy(self, **kw):
        return self.run_calc('pingavg', **kw)

    def run_autoedit_npy(self, **kw):
        return self.run_calc('autoedit', **kw)

    def run_xducerxy_npy(self, **kw):
        return self.run_calc('xducerxy', **kw)

    def run_guess_xducerxy_npy(self, **kw):
        return self.run_calc('guess_xducerxy', **kw)
