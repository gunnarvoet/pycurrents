"""
Library for quick_adcp: utility functions, and a mixin class
to handle comprehensive (overwhelming) options dictionary.
"""

import sys
import os
import re
import glob
from subprocess import Popen, PIPE, STDOUT
import logging

from pycurrents.adcp.quick_docs import (print_vardoc,
                                        print_expert,
                                        print_pingdata_commands,
                                        print_ltapy_commands,
                                        print_enrpy_commands,
                                        print_uhdaspy_commands,
                                        print_postproc_commands,
                                        )
from pycurrents.system.yn_query import yn_query
from pycurrents.system.misc import Cachefile, Bunch
from pycurrents.adcp.uhdasconfig import UhdasConfig
from pycurrents.data.timetools import ddtime
from pycurrents.adcp.adcp_specs import Sonar, check_sonar

# Standard logging
_log = logging.getLogger(__name__)

dbinfo_fundamental_keys = ['dbname', 'yearbase', 'pgmin',
                           'beamangle', 'configtype',
                           'ens_len', 'badbeam', 'beam_order', 'pingpref',
                           'xducer_dx', 'xducer_dy', 'fixfile', 'txy_file',
                           'ref_method', 'refuv_source', 'refuv_smoothwin',
                           'datatype', 'cruisename', 'sonar', 'proc_engine']

nodb_times = ['1970/01/01  01:00:00 to 1970/01/01  01:01:01', -10000.0, -10000.0]


class quickFatalError(Exception):
    pass

def system_cmd(cmd):
    p = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True)
    out = p.stdout.read()
    p.stdout.close()
    retcode = p.wait()
    if retcode:
        _log.error('command %s returncode %d\n output:\n %s', cmd, retcode, out)
    return retcode, out

#------------------------------------------------------------------


def runcmd(pq=None, pycmd=None, sq=None, syscmd=None,
           verbose=0, workdir=None, logfile=None):
    '''
    python query and command; system query and command

     get cwd, chdir to working dir, do what is requested in order:
       ask whether to run the python command
       run python command (eg, make scanping.tmp
       as whether to run the system command
       run system command (eg scanping scanping.tmp)
     chdir back to startdir
    ### NOTE: structure of pycmd is (py_fcn_to_call, (tuple), {dict})
    ###       example: a python program that only takes one positional argument:
    ###                  (function, (opts, ))
    ###       example: a python program that only takes named arguments:
    ###                  (function, (), dict)                   #should work
    '''

    if verbose:
        _log.debug('\n'.join([
             '---------------begin verbose in runcmd--------------------',
             'startdir is %s', 'workdir  is %s', 'pq  is: %s',
             'pycmd is %s', 'sq  is: %s','syscmd is %s',
             '---------------- end verbose in runcmd--------------------',
             ]) % (os.getcwd(), workdir, pq, pycmd, sq, syscmd))

    if (pycmd and not pq) or (syscmd and not sq):
        msg = '\nyou must ask before using the command'
        msg += 'but you CAN specify the answer  :)'
        raise quickFatalError(msg)

    ran_dict=dict(pq=False, sq=False)

    startdir = os.getcwd()
    _log.debug('starting in %s', startdir)

    if workdir:
        os.chdir(workdir)
    _log.debug('executing commands from %s', os.getcwd())

    if pq:

        qfunc, args, kwargs = fill_cmd(pq)

        qa = qfunc(*args, **kwargs)
        if (qa and pycmd): #if there is a python command, run it
            _log.debug('running python command "%s"', pycmd[0].__name__)
            func, args, kwargs = fill_cmd(pycmd)
            func(*args, **kwargs)
            ran_dict['pq']=True

    if sq:

        qfunc, args, kwargs = fill_cmd(sq)
        qa = qfunc(*args, **kwargs)
        if (qa and syscmd): #if there is a system command, run it
            if hasattr(syscmd, 'capitalize'):   # duck-typing for string, Py2/3
                _log.debug('about to run %s', syscmd)
                ret, out = system_cmd(syscmd)
                if ret:
                    raise quickFatalError("\nFailure in command:\n%s" % syscmd)
                ran_dict['sq']=True

            elif isinstance(syscmd, list):
                for ii, cmd in enumerate(syscmd):
                    _log.debug('about to run %s', cmd)
                    ret, out = system_cmd(cmd)
                    if ret:
                        raise quickFatalError("\nFailure in command:\n%s" % syscmd)
                    ran_dict['sq']=True
            else:
                msg =  ('\nsyscmd must be a string or a list of strings;\n'
                        'it is a %s\n' % type(syscmd))
                raise quickFatalError(msg)

    if workdir:
        os.chdir(startdir)

    return ran_dict

#-- end runcmd -----------------------------------------------------

def fill_cmd(cmd):
    c = [None, tuple(), dict()]
    c[:len(cmd)] = cmd
    return c

#-------------------------------------------------------

def file_msg(filename):
    # send a useful message to the user: 'this file exists' or 'making this file'
    if os.path.exists(filename):
        _log.debug('%s exists', filename)
    else:
        _log.debug('making %s', filename)

#-------------------------------------------------------

def yeslist():
    return (yn_query, ['',''],  {'default':'y', 'auto':1} )   #force 'yes'

#--------------------------------------------------------
def get_filelist(workdir=None, opts=None):
    '''
    STA or LTA processing
    guess filelist
    (1) expand wildcard using "datadir", "datafile_glob"
    (2) read from "data_filelist"  (ascii file with datafiles)
    (3) an explicit "filelist"  # comes in args; broken??

    - datadir could be relative to root processing directory **or** "scan"
    '''

    if workdir is None:
        raise quickFatalError('getting filelist: workdir not specified')

    #make sure opts['filelist'] has a list of valid files
    # NOTE: these files should be valid from the scan or load directory, but
    # if they come in from the command line, they may be relative or
    # full paths, relative to procdir (not procdir/scan)
    if 'filelist' not in list(opts.keys()):
        opts['filelist']=[]



    # if args exist, opts['filelist'] has them  and opts['data_filelist'] == ''
    #
    # at this stage, rewrite the data_filelist with full paths
    # AND specify the name of the data_filelist with full path

    if opts['data_filelist'] is not None: # before chdir, read this file
        # must have specified a filename (then datafile_glob == '')
        opts['data_filelist'] = os.path.realpath(opts['data_filelist'])
        sorted_filelist = []
        with open(opts['data_filelist'],'r') as newreadf:
            flist = newreadf.readlines()
        for f in flist:
            sorted_filelist.append(os.path.realpath(f.rstrip()))
        opts['filelist'] = sorted_filelist
        numfiles = len(opts['filelist'])
        if numfiles > 0:
            msg = 'found %d files in %s' % (numfiles, opts['data_filelist'])
            _log.info(msg)
        else:
            msg = 'no files found in filelist %s' % (opts['data_filelist'])
            raise quickFatalError(msg)
        #rewrite with full paths
        data_fname = opts['data_filelist']
        with open(data_fname,'w') as file:
            file.write('\n'.join(opts['filelist']))
        opts['data_filelist'] = data_fname
        msg = 'rewriting filelist with full paths to %s' % (data_fname)
        _log.info(msg)


    # (1) datadir and fileglob
    startdir = os.getcwd()
    os.chdir(workdir)
    # running from 'scan', or 'load'
    if len(opts['filelist']) == 0:
        # no data_filelist and no args
        # fullpath file list
        if os.path.isabs(opts['datadir']):  #absolute path, so 'ok'
            datadir = opts['datadir']
            _log.debug('data directory: %s' % (datadir))
        else: # relative
            if os.path.exists(opts['datadir']): # exists, so OK. Make absolute
                datadir = opts['datadir']
            else: # specified as from root processing dir? try adding '..'
                msg = '====> NOTE: adding ".." to "datadir" '
                msg += '\n  (makes correct paths when used from "scan" or "load")'
                _log.info(msg)
                datadir = os.path.join('..',opts['datadir'])
                opts['datadir'] = datadir # update if added '..'
            _log.debug('data directory: (relative to %s) is %s' % (workdir, datadir))


        pglob = os.path.join(datadir, opts['datafile_glob'])
        if len(glob.glob(pglob)) > 0:
            opts['filelist'] = glob.glob(pglob)
            opts['filelist'].sort()
        numfiles = len(opts['filelist'])
        msg = 'found %d files using wildcard expansion relative to %s directory' % (
            numfiles, workdir)
        _log.info(msg + '\nwildcard string was:   "%s"' % (pglob))
        if numfiles == 0:
            raise quickFatalError(msg)
        # store it here
        data_fname = os.path.realpath(
            os.path.join(opts['procdir'], 'ping','datafile_list.txt'))
        with open(data_fname,'w') as file:
            file.write('\n'.join(opts['filelist']))
        opts['data_filelist'] = data_fname
        msg = 'presently in %s, writing filelist to %s' % (workdir, data_fname)
        _log.info(msg)


    badfiles = [f for f in opts['filelist'] if not os.path.exists(f)]
    if len(badfiles) > 0:
        msg = 'in %s' % os.getcwd()
        msg += 'WARNING: relative to scan/'
        msg += 'these files from the command line do not exist: %s' % ' '.join(badfiles)
        os.chdir(startdir)
        raise quickFatalError(msg)


    if len(opts['filelist']) == 0:
        os.chdir(startdir)
        msg = 'could not find data files'
        raise quickFatalError(msg)

    os.chdir(startdir)

    _log.info('found %d raw data files', len(opts['filelist']))



#----- end get_filelist ----

def guess_dbname(cachedict=None):
    '''
    return (dbname, errmsg)
    '''
    #regardless, test for dbname
    if cachedict is not None:
        if 'dbname' in list(cachedict.keys()):
            if cachedict['dbname'] is not None:
                return cachedict.dbname, 'using dbname %s' % (cachedict.dbname)
    # else, guess
    dirblks = glob.glob('adcpdb/*dir.blk')
    # try looking for dir.blk and using that
    if len(dirblks) == 0:
        return None, 'MUST SET DATABASE NAME'
    elif len(dirblks) > 1:
        return None,  'Found multiple databases: ' + ','.join(dirblks)
    else:
        dirblk =  os.path.split(dirblks[0])[1][:-7]
        return dirblk, 'found dbname %s' % (dirblk)

    # ----- end check for dbname -------------


def initialize_dbinfo(cachefile='dbinfo.txt', optdict=None):
    dbinfo = Cachefile(cachefile, contents='CODAS quick_adcp.py info')
    _log.info('initializing cachefile %s' % (cachefile))
    # first time through; must have these
    diemsg = '\nERROR -- must set "%s" in control file or command line:'

    dbmsg={'cruisename':''.join(['-used for plot titles ',
            '(and for uhdas singleping processing, config file names)']),
           'yearbase' : '(year when the first ping was collected)',
           'sonar' : '(eg. nb150, wh300, os75bb, os75nb, or os75 (for mixed pings))',
           'dbname' : 'cannot determine dbname'}

    if optdict is not None:
        for name in ['cruisename', 'yearbase', 'sonar', 'dbname']:
            if optdict[name] is None:
                raise quickFatalError(diemsg % (name) + '\n' + dbmsg[name])

    init_dict = Bunch({})
    for name in dbinfo_fundamental_keys:
        init_dict[name] = None
    # fill in values that are None, if possible, from self.opts
    dbinfo.init(init_dict)

    return dbinfo


############################################

def get_cmd_timerange(filename, yearbase=None):
    '''
    read the specified cmd file
    return [time_range, startdd, enddd ]
    '''
    pat = r"\b\d{2,4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\b"
    fid = open(filename,'r')
    lines = fid.readlines()  # read some lines; don't need first one
    fid.close()

    start_time = ''
    end_time = ''

    for iline in range(0,50):
        if lines[iline].split(':')[0] == 'new_profile':
            matchobj = re.findall(pat, lines[iline])
            if len(matchobj) > 0:
                start_time = matchobj[0]
                break

    for iline in range(len(lines)-1, 0, -1):
        if lines[iline].split(':')[0] == 'new_profile':
            matchobj = re.findall(pat, lines[iline])
            if len(matchobj) > 0:
                end_time = matchobj[0]
                break

    start_end_times = start_time+' to '+end_time

    dd0 = ddtime(yearbase, start_time)
    dd1 = ddtime(yearbase, end_time)

    return start_end_times, dd0, dd1

    #----- end get_cmd_timerange -------------------------------


# for use with runcmd (calls yn_query)
def def_qlist(question=None,  auto=None):
    ## default query. override components below if desired
    if (auto is None):
        msg = '\ndebug: must specify default answer as second argument'
        raise quickFatalError(msg)
    if (auto == 'q'):
        print('quitting')
        sys.exit()

    if (auto == 0 or auto == 'n'):
        qa_str = 'n'
        qa_int = 0
    elif (auto == 1 or auto == 'y'):
        qa_str = 'y'
        qa_int = 1
    else:
        msg = '\ndefault must be integer 0 or 1, or character "y", "n", or "q"'
        raise quickFatalError(msg)

    return  (yn_query,
             [question, 'ynq'],
             {'default':qa_str, 'auto':qa_int})
    ## EF: I think the function above should be simplified; it seems
    ## to be doing extensive run-time checking that looks odd--is
    ## it really needed?  Shouldn't the argument checking be done
    ## upstream?

##-------------
def translate_old_cachefile(cachefile='dbinfo.txt'):
    test_newkey = 'txy_file'

    if not os.path.exists(cachefile):
        _log.debug('no file "%s" exists' % (cachefile))
        return

    dbinfo = Cachefile(cachefile,
                       contents='CODAS quick_adcp.py info')
    dbinfo.read()

    if test_newkey in list(dbinfo.cachedict.keys()):
        return

    # it is too old.
    # move the file to dbinfo.txt.old and translate to a new one.
    savename = cachefile+'.orig'
    if os.path.exists(savename):
        msg= '%s exists and %s is too old.\n' % (cachefile, savename)
        msg += 'investigate (rename?) %s and start over with\n' % (cachefile)
        msg += '     quick_adcp.py --steps2rerun calib'
        raise quickFatalError(msg)
    # save the old one
    os.rename(cachefile, savename)
    _log.info('renaming %s to %s' % (cachefile, savename))
    # make the new one
    newinfo = initialize_dbinfo(cachefile=cachefile)
    newinfo.cachedict.update_None(dbinfo.cachedict)
    cdict = newinfo.cachedict
    # now rationalize fixfile and ref_method
    dbname, msg = guess_dbname(dbinfo.cachedict)
    if dbname is None:
        raise quickFatalError(msg)
    else:
        _log.info(msg)

    cdict.dbname = dbname
    ## now we have a dbname
    if cdict.fixfile is None:
        cdict.fixfile = '%s.gps' % (cdict.dbname)
    if cdict.ref_method is None:
        cdict.ref_method = 'refsm'
    cdict.fixfilexy = cdict.fixfile     # for navsteps and calib consistency



    if cdict.pingpref is None:
        cdict.pingpref = 'nb'
    newinfo.add_comments(['## copied from %s' % (savename)])
    newinfo.write()
    _log.info('writing new cachefile %s' % (cachefile))
    ## include lots of error messages if this will not work.

##-------------


class Q_setup: ## mixin for Processor class

    #--- end def_qlist --------------------------------------------------

    def check_uhdascfg(self):
        opts=self.opts

        ## NOTE: mixed-ping processing is poorly handled here.
        ## We read the configuration at the beginning, before
        ##   we start.  If mixed-ping processing, select NB traits.

        cruise_info = UhdasConfig(cfgpath = opts['cfgpath'],
                                  cruisename = opts['cruisename'],
                                  configtype = opts['configtype'],
                                      sonar = opts['sonar'])

        opts['uhdas_config'] = cruise_info

        if hasattr(cruise_info, 'hcorr'):
            _log.debug('found cruise_info.hcorr (%s, %s, %d)' % tuple(cruise_info.hcorr))
            opts['hcorr_inst'] = cruise_info.hcorr[0]
        else:
            opts['hcorr_inst'] = None

        # full path
        opts['cfgpath'] = os.path.abspath(opts['cfgpath'])
        opts['datadir'] = cruise_info.rawsonar
        opts['datafile_glob'] = '*.raw'  #for 'scan'


        # in case of python processing
        if opts['py_gbindirbase'] is None:
            opts['py_gbindirbase'] = cruise_info.gbin
        opts['py_gbindirbase'] = os.path.abspath(opts['py_gbindirbase'])

    #----
    ## we do need to read dbinfo.txt after it has been written by Pingavg
    def check_beamangle(self, cachefile='dbinfo.txt'):
        '''
        check for beam angle
        '''
        no_beamangle_msg = 'no beam angle set.  must set once in options'

        # check_dbinfo already updated dbinfo.txt and opts

        dbinfo = Cachefile(cachefile,
                           contents='CODAS quick_adcp.py info')
        dbinfo.read()
        dbinfo.cachedict.update_None(self.opts)
        self.opts.update_None(dbinfo.cachedict)

        if self.opts['beamangle'] in (None, 'None'):
            raise quickFatalError(no_beamangle_msg)

    # ----- end check for beam angle -------------

    def check_time_angle_file(self):
        opts=self.opts

        if opts['datatype'] == 'uhdas':

            self.opts['time_angle_file'] = None
            self.opts['time_angle_base'] = None

            #should have been specified in check_uhdascfg
            if self.opts['hcorr_inst']:  #it is specified
                if self.opts['ping_headcorr']:
                    msg = '\n'.join(['no heading correction will be used within the ',
                                     'ensembles but values are staged in',
                                     'cal/rotate/hcorr.asc'])
                    _log.debug(msg)

                    ## ens_hcorr is the heading correction file base if heading correction is
                    ##      done within the ensembles.
                    ## hcorr is the heading correction applied manually AFTER averaging
                    self.opts['time_angle_file'] = 'ens_hcorr.ang'
                else:
                    self.opts['time_angle_file'] = 'hcorr.ang'
                self.opts['time_angle_base'] = self.opts['time_angle_file'].split('.')[0]
            else:
                if self.opts['ping_headcorr']:
                    msg = '\n'.join(['\n\nno heading correction device specified.',
                                     'Cannot use "--ping_headcorr"',
                                     '(specify this in the config/CRUISE_proc.py file)',
                                     ])
                    raise quickFatalError(msg)

    #----
    def check_rotated_incremental(self):
        opts=self.opts
        if opts['datatype'] == 'uhdas':
            if opts['incremental'] and (opts['rotate_angle'] != 0 or opts['rotate_amplitude'] != 1):
                msg = 'cannot choose rotation angle (or amplitude) in incremental mode'
                raise quickFatalError(msg)


    #----
    def check_gbins(self):
        '''
        batch mode: do not try to remake gbins if they exist
        '''
        opts=self.opts
        if (opts['datatype'] == 'uhdas'    # uhdas data
            and (opts['steps2rerun'] == '') # first time through
            and not opts['incremental']    # batch mode
            and opts['update_gbin']):      # want new gbins

            if 'instrument' in list(opts.keys()):
                gbin_inst = os.path.join(opts['py_gbindirbase'], opts['instrument'])
            else:
                s=Sonar(opts['sonar'])
                gbin_inst = os.path.join(opts['py_gbindirbase'], s.instname)

            if os.path.exists(gbin_inst):
                msg = '\n'.join([
                        '\n\nFATAL error: gbin directory exists: ',
                        opts['py_gbindirbase'],
                        '\nTo remake: ',
                        '- remove entire gbin directory ',
                        '- use option "--update_gbin" to generated new gbins)',
                        '\nTo use "as is" remove "--update_gbin" from options.',
                        '\nNOTE: if changing position or heading devices, '
                        '---> DO remake gbins\n'])
                raise quickFatalError(msg)

    #------------- end hcorr check ---------------

    def check_xducerxy(self, cachedict=None):
        '''
        xducer_dx from q_py.cnt is ADDED to whatever was there before.
        i.e.
           - first time specified, use it, and cache it
           - all later times, see if an incremental change has been specified.
                   store the sum
        '''
        opts=self.opts
        # only check previous (cached) value if we are in postprocessing
        if len(opts['steps2rerun']) > 0:
            opts['sum_xducer_dx'] = opts['xducer_dx'] + cachedict.xducer_dx
            opts['sum_xducer_dy'] = opts['xducer_dy'] + cachedict.xducer_dy
            # only update if increment was specified
            cachedict.xducer_dx = opts['sum_xducer_dx']
            cachedict.xducer_dy = opts['sum_xducer_dy']
            if opts['sum_xducer_dx'] != 0 or opts['sum_xducer_dy'] != 0:
                # write this out in dbinfo.txt
                _log.info('using (xducer_dx, xducer_dy) (%5.3f, %5.3f)'
                         % (opts['sum_xducer_dx'], opts['sum_xducer_dy']))
        else:
            opts['sum_xducer_dx'] = opts['xducer_dx']
            opts['sum_xducer_dy'] = opts['xducer_dy']
            ## update cachedict
            cachedict.xducer_dx = opts['xducer_dx']
            cachedict.xducer_dy = opts['xducer_dy']



    #---- end check_xducerxy

    def check_fixfile(self, cachedict=None):
        # set fixfile (positions)
        #            input for smoothr
        #            input for xducer_dx, xducer_dy
        # heirachy:
        #  if not in dbinfo.txt, check opts
        #  if not in opts, use defaults

        # "txy_file" is used in put_tuv

        # first determine default
        opts=self.opts

        if opts['fixfile'] is None:  #override
            fixfile = None
            if cachedict:
                if 'fixfile' in list(cachedict.keys()):
                    if cachedict['fixfile'] is not None:
                        fixfile = cachedict['fixfile']
                        if opts['debug']:
                            _log.info('got fixfile %s from cachefile' % (fixfile))
            if fixfile is None:
                ## fixfile has original GPS positions
                if opts['datatype'] == 'pingdata':
                    fixfile_suffix = 'ags'
                    if opts['debug']:
                        _log.info('setting default fixfile for pingdata')
                else:
                    fixfile_suffix = 'gps'
                    if opts['debug']:
                        _log.info('setting modern default fixfile')
                ## txy_file is used by put_txy and goes
                fixfile = '%s.%s' % (opts['dbname'], fixfile_suffix)
                if opts['debug']:
                    _log.info('fixfile is %s' % (fixfile))

            opts['fixfile'] = fixfile
            if opts['debug']:
                _log.info('setting opts fixfile to  %s' % (fixfile))

        cachedict['fixfile'] = opts['fixfile']
        if opts['debug']:
            _log.info('setting cache fixfile to  %s' % (opts['fixfile'],))

        if opts['fixfile'][-3:] == 'agt':
            raise quickFatalError('reserved name: cannot override fixfile with suffix "agt"')

        ## must have already checked xducer_dx, xducer_dy
        if (opts['sum_xducer_dx'] == 0 and opts['sum_xducer_dy'] == 0): #no translation
            opts['txy_file'] = opts['fixfile']
            opts['fixfilexy'] = opts['fixfile']  # for consistency in nav and calib steps
        else: # use altered postions
            opts['txy_file'] = '%s.agt' % (opts['dbname'])
            ## try to calculate remaining translation from *.agt to adcp
            ## otherwise (eg older cruise) calculate offset from fixfile
            opts['fixfilexy'] = '%s.agt' % (opts['dbname'])
        cachedict['txy_file'] = opts['txy_file']

        _log.info('fix file is %s', opts['fixfile'])

    # --- done checking fixfile
    def check_refstuff(self, name, cachedict=None):
        '''
        one-stop shopping for ref_method, refuv_source, refuv_smoothwin
        use default, cache, then allow override
        '''
        opts=self.opts
        ref_defaults = Bunch(ref_method = 'refsm',
                            refuv_source = 'nav',
                            refuv_smoothwin=3)
        ref_choices = Bunch(ref_method = ('refsm', 'smoothr'),
                            refuv_source = ('nav', 'uvship'),
                            refuv_smoothwin=['0','1','2','3','4','5','6','7','8','9'],
                            )

        ref_dielist=Bunch(ref_method =
                     ['ref_method %s not supported' % (opts['ref_method']),
                      '    - choose "refsm" or "smoothr", and',
                      '    - check "dbinfo.txt" for an unsupported bad ref_method'],
                     refuv_source =
                     ['refuv_source (ref layer shipspeed source) not supported',
                      '    %s\n' % ('refuv_source'),
                      'choose "nav" or "uvship"'],
                     refuv_smoothwin =
                     ['reference layer smoothing window %s not supported' %
                     (opts['refuv_smoothwin'].__str__())
                     ])

        overrode = False
        # allow override in options
        ref_default = ref_defaults[name]
        # allow override
        if opts[name] is not None:
            ref_default = opts[name]
            overrode = True

        if len(opts['steps2rerun']) > 0 and not overrode:  # post-processing
            if cachedict:
                if name in list(cachedict.keys()):
                    if cachedict[name] is not None:
                        ref_default= cachedict[name]

        # if ref_method is smoothr, the other (refsm) variants don't matter
        if ref_default != 'smoothr':
            if str(ref_default) not in ref_choices[name]:
                raise quickFatalError('\n'.join(ref_dielist[name]))

        opts[name] = ref_default
        cachedict[name] = ref_default
        _log.info('reflayer: %s = %s' % (name, ref_default))

    # ---- end generic refchecker----

    def set_navfiles(self, cachedict):
        # now set these files
        opts=self.opts
        if opts['ref_method'] == 'smoothr': # uses putnav
            opts['smfile'] = '%(dbname)s.sm' % opts
            opts['xducer_dx'] = None; opts['xducer_dy'] = None
            opts['sum_xducer_dx'] = 0; opts['sum_xducer_dy'] = 0
            opts['txy_file'] = None
            opts['refuv_smoothwin'] = None
            cachedict.xducer_dx = None; cachedict.xducer_dy = None
            cachedict.txy_file = None
            cachedict.refuv_smoothwin = None
            cachedict.refuv_source = None

            _log.info('==============   WARNING ==================')
            _log.info('resetting xducer_dx=None, xducer_dy=None ')
            _log.info('cannot use xducer_dx, xducer_dy with smoothr)')
            _log.info('==============   WARNING ==================')
        else: #won't be using putnav
            if opts['refuv_source'] == 'nav': #ship speed from positions
                opts['refuv_inputfile'] = opts['txy_file'] # put in new positions
            elif opts['refuv_source'] == 'uvship' :  #ship speed from pings
                opts['refuv_inputfile'] ='%s.uvship' % (opts['dbname'])
            else:
                raise quickFatalError('refuv_source %s not understood' % (opts['refuv_source']))
            # use RefSmooth output for put_tuv, regardless
            opts['tuv_file'] = 'refsm_tuv.asc'
        for name in ['ref_method','refuv_source','refuv_smoothwin']:
            if name not in list(cachedict.keys()):
                cachedict[name] = opts[name]
        opts['bl_half_width'] = opts['refuv_smoothwin']

# ----- end of check_fixfile ----
    def check_dbinfo(self, cachefile='dbinfo.txt'):
        '''
        if dbinfo.txt exists read it
            if too old, translate it
            checks 'txy_file'
        if dbinfo.txt exists (now it is new enough), read it
        if dbinfo.txt does not exist, make it.
             require yearbase, sonar, datatype (at least)
        '''

        if  os.path.exists(cachefile) :
            if os.path.getsize(cachefile)>=0:
                # read and fill
                dbinfo = Cachefile('dbinfo.txt',
                           contents='CODAS quick_adcp.py info')
                dbinfo.read()
                dbinfo.cachedict.update_None(self.opts)
            else:
                # initialize it
                dbinfo = initialize_dbinfo()
                dbinfo.cachedict.update_None(self.opts)
                _log.info('found empty dbinfo.txt: initializing')
        else:
            # initialize it
            dbinfo = initialize_dbinfo()
            dbinfo.cachedict.update_None(self.opts)
            _log.info('no dbinfo.txt: initializing')

        self.opts['mixed_pings'] = check_sonar(self.opts['sonar'])

        # # do not override these from opts if second run
        if len(self.opts['steps2rerun']) == 0:
            if self.opts['ens_len']  is None:
                dbinfo.cachedict['ens_len'] = 300
            else:
                dbinfo.cachedict['ens_len'] = self.opts['ens_len']

            comments=[]
            if self.opts['datatype'] == 'uhdas':
                # opts['hcorr_inst'] should have been initialized in check_uhdascfg
                # if it was going to be used (comes config/cruiseid_proc.py)
                if 'hcorr_inst' not in list(self.opts.keys()):
                    self.opts['hcorr_inst'] = None

                if self.opts['hcorr_inst']:
                    dbinfo.cachedict['hcorr_inst'] = self.opts['hcorr_inst']
                    comments.append('## ping_headcorr is '+str(self.opts['ping_headcorr']))
                else:
                    if self.opts['ping_headcorr']:
                        _log.warning('no heading correction device.  Ignoring --ping_headcorr')

        # now dbinfo.cachedict has None filled in from opts
        # now: allow certain values from opts to override dbinfo

        # check for things that are missing:
        if 'datatype' not in list(dbinfo.cachedict.keys()):
            dbinfo.cachedict['datatype'] = None
        if dbinfo.cachedict['datatype'] is None:
            if  self.opts['datatype'] is None:
                raise quickFatalError('must set "datatype": ("uhdas", "pingdata", "sta", "lta"')
            else:
                _log.info('setting dbinfo "datatype" to %s' % (self.opts['datatype']))
                dbinfo.cachedict['datatype'] = self.opts['datatype']


        ## deal with sonar, pingtype etc
        # update_None should have filled it (if new) or we need one
        if 'sonar' not in list(dbinfo.cachedict.keys()):
            raise quickFatalError('no SONAR found in dbinfo.txt or options')


        sonar = Sonar(dbinfo.cachedict['sonar'])
        mixed_pings = check_sonar(sonar)
        if mixed_pings:
            self.opts['incremental'] = True   # mixed pings
            if 'pingpref' in list(dbinfo.cachedict.keys()):
                self.opts['pingpref'] = dbinfo.cachedict['pingpref']
            else:
                self.opts['pingpref'] = 'nb'

        comments = []
        # make comments for these
        for name in ['model', 'frequency', 'instname']:
            self.opts[name] =  getattr(sonar, name)
            comments.append('## (determined from "sonar"): %s = %s' % (
                                name, self.opts[name]))

        #self.opts['mixed_pings']  was set in check_uhdascfg
        name = 'pingtype'
        if self.opts['mixed_pings']:
            if self.opts['pingpref'] is None:
                self.opts['pingpref'] = 'nb'
            self.opts['pingtype'] = self.opts['pingpref']
            comments.append('## (mixed pings, chosen from pingpref): %s = %s' % (
                name, self.opts['pingtype']))
        else:
            self.opts['pingtype'] = getattr(sonar, 'pingtype')
            comments.append('## (determined from "sonar"): %s = %s' % (
                name, self.opts['pingtype']))

        dbinfo.cachedict['proc_engine'] = 'python'

        ## we need the database name before doing reflayer
        if not self.opts['dbname']:
            self.opts['dbname'], msg = guess_dbname(self.opts)
            _log.info(msg)
            if self.opts['dbname'] is None:
                raise quickFatalError(msg)

        dbinfo.cachedict['dbname'] = self.opts['dbname']

#        import IPython; IPython.embed()
        #xxx  FIXME - see what dbinfo.cachedict['dbname'] is
        for name in ('yearbase', 'ens_len', 'cruisename', 'dbname'):  # also check dbname here?
            if self.opts[name] is None:
                raise quickFatalError('must set %s' % (name))
        self.opts['proc_yearbase'] = self.opts['yearbase']


        self.check_xducerxy(cachedict=dbinfo.cachedict)
        self.check_fixfile(cachedict=dbinfo.cachedict)
        self.check_refstuff('ref_method', cachedict=dbinfo.cachedict)
        self.check_refstuff('refuv_source', cachedict=dbinfo.cachedict)
        self.check_refstuff('refuv_smoothwin', cachedict=dbinfo.cachedict)
        self.set_navfiles(cachedict=dbinfo.cachedict)

        dbinfo.add_comments(comments)
        self.opts.update_None(dbinfo.cachedict)

        dbinfo.write()

    ## --- end dbinfo check -----------------------------------


    def check_opts(self):
        opts = self.opts

        # print stdout if needed
        if opts['vardoc']:
            print_vardoc()
            sys.exit(0)

        if opts['expert']:
            print_expert()
            sys.exit(0)

        ## FIXME: function is missing
        ##if opts['overview']:
        ##    print_overview()
        ##    sys.exit(0)


        if opts['commands']:
            opts['commands'] = opts['commands'].lower()
            if opts['commands'] in  ('ltapy', 'stapy'):
                print_ltapy_commands()
                sys.exit(0)
            if opts['commands'] in  ('enrpy'):
                print_enrpy_commands()
                sys.exit(0)
            elif opts['commands'] in ('uhdaspy',):
                print_uhdaspy_commands()
                sys.exit(0)
            elif opts['commands'] in ('postproc'):
                print_postproc_commands()
                sys.exit(0)
            elif opts['commands'] in ('pingdata'):
                print_pingdata_commands()
                sys.exit(0)
            else:
                print('\n\n==> command "%s" not recognized. choose from the following:' % (
                                                   opts['commands']))
                print('\n'.join(['ltapy', 'stapy','enrpy', 'uhdaspy', 'pingdata']))
                sys.exit(1)

        # preliminary error messages
        for kk in ('datatype', 'sonar'):
            if opts[kk] is not None:
                opts[kk] = opts[kk].lower()

        for dname in ['adcpdb', 'scan', 'load', 'edit']:
            if not os.path.exists(dname):
                msg = '\n'.join(['directory %s does not exist' % (dname),
                                 'present directory = %s:\n' %(os.getcwd()),
                                 'Are you starting in the right directory?'])
                raise quickFatalError(msg)


        if opts['datatype'] == 'pingdata':
            if opts['ref_method'] != 'smoothr':
                _log.warning('only ref_method=smoothr is supported for pingdata')
            opts['ref_method'] = 'smoothr'


        msglist = []
        if 'use_smoothr' in list(opts.keys()):
            msglist.append('option "--use_smoothr" no longer supported')
        if 'use_refsm' in list(opts.keys()):
            msglist.append('option "--use_refsm" no longer supported')
        if msglist:
            msg = '\n'.join(msglist +
                            ['use option "--ref_method" with one of these:',
                             '     --ref_method smoothr',
                             '     --ref_method refsm'])
            raise quickFatalError(msg)

        # read dbinfo (if possible); update opts (None) to dbinfo
        # keep fixfile values for check_fixfile

        if opts['steps2rerun']:
            # copy and translate old file if necessary
            cachefile='dbinfo.txt'
            translate_old_cachefile(cachefile=cachefile)

            # now get the information needed if it is there
            if  os.path.exists(cachefile) or (
                        os.path.exists(cachefile) is True
                        and os.path.getsize(cachefile)>=0):
                dbinfo = Cachefile(cachefile, contents='CODAS quick_adcp.py info')
                dbinfo.read()
                opts.update_None(dbinfo.cachedict) # clobbers fixfile
                _log.info('found dbinfo.txt: use values if otherwise unspecified')

        # take care of this right away
        if opts['proc_engine'] != 'python':
            raise quickFatalError('proc_engine can only be python')
        if opts['configtype'] != 'python':
            raise quickFatalError('configuration type can only be python')

        datatype_list =  ['uhdas', 'lta', 'sta', 'pingdata']
        if opts['datatype'] is None:
            msg= '\nMust select datatype from:\n' + ', '.join(datatype_list)
            raise quickFatalError(msg)

        if opts['datatype'] not in datatype_list:
            msg = '\ndata type "%s" not supported' % opts['datatype']
            raise quickFatalError(msg)

        if opts['datatype'] != 'uhdas' and opts['incremental']:
            msg = '\n"incremental" can only be used with uhdas data:'
            raise quickFatalError(msg)

        if 'hcorr_inst' in list(opts.keys()):
            msg = '\n'.join(['"hcorr_inst" can only be used with uhdas data, ',
                             '(not LTA, STA, or PINGDATA)',
                             'and is set in config/CRUISE_proc.py'])
            raise quickFatalError(msg)

        # these do not require dbinfo.txt
        if opts['datatype'] == 'uhdas':
            if len(opts['steps2rerun']) == 0: # first time through
                self.check_uhdascfg() # hcorr_inst, hcorr, ping_headcorr
                self.check_rotated_incremental()  # rotate_angle?
                self.check_gbins()    # update_gbin, incremental, err msg
                self.check_time_angle_file()   # requires check_uhdascfg

        # now read/write contents of dbinfo
        self.check_dbinfo()

        if opts['steps2rerun']:
            self.check_beamangle()      # dbinfo or opts; updated

        ## string for globbing on adcp data files
                ## (for uhdas raw, it is set above by check_uhdascfg())
        if not opts['datafile_glob'] and opts['datatype'] != 'uhdas':
            opts['datafile_glob'] = dict(sta='*.STA',
                                         lta='*.LTA',
                                         pingdata='PINGDATA.???',
                                         )[opts['datatype']]

        ## set path to data directory
        if not opts['datadir']:
            opts['datadir'] = os.path.join('..','ping')

        if  opts['datatype'] == 'pingdata':
            opts['data_def'] = 'ub_%(ub_type)s.def' % opts
        else:
            opts['data_def'] = 'vmadcp.def'

        if opts['max_BLKprofiles'] > 512:
            _log.warning('max_BLKprofiles must 512 or less. Resetting to 512\n')
            opts['max_BLKprofiles'] = 512
