"""
Library for quick_adcp: Q_run monster mixin for running
python or compiled commands with query.

"""

import os
import glob
import logging

from pycurrents.system.yn_query import yn_query
from pycurrents.adcp.quick_setup import  file_msg, runcmd, yeslist
from pycurrents.adcp.quick_setup import system_cmd, def_qlist
from pycurrents.adcp.quick_setup import quickFatalError
from pycurrents.system.misc import Cachefile
from pycurrents.adcp.adcp_specs import codas_editparams, codas_disableparams
from pycurrents.adcp.adcp_specs import codas_start_disabled, ping_editparams
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp import uhdas_defaults

# Standard logging
_log = logging.getLogger(__name__)


class Q_run:
    ## (1) scan data
    def run_scandata(self):
        opts = self.opts

        trfile = '%(dbname)s.tr' % opts
        timefile = '%(dbname)s.scn' % opts

        _log.debug('step 1: scan data (create .scn file)')

        startdir = os.getcwd()
        workdir =  'scan'
        os.chdir(workdir)


        pqlist =  def_qlist('scan data now??', opts['auto'])

        _log.debug('scanning files for time ranges...')
        if opts['datatype'] == 'pingdata':
            cntfile = 'scanping.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.scanping, (cntfile,)]
            syscmd = 'scanping %s' % (cntfile,)
            runcmd(pq=pqlist, pycmd=pycmd, sq=yeslist(), syscmd=syscmd)
        else:  ## opts['datatype'] in ('sta','lta'):
            pycmd = [self.run_scanlta_npy, ()]
            runcmd(pq=pqlist, pycmd=pycmd)

        trfile = '%(dbname)s.tr' % (opts)
        timefile = '%(dbname)s.scn' % (opts)
        trddlist = self.get_time_range(timefile)
        self.write_timerange_file(trfile, trddlist[0])
        opts['scn_time_range'] = trddlist[0]
        opts['scn_startdd'] = trddlist[1]
        opts['scn_enddd'] = trddlist[2]


        os.chdir(startdir)

    #--- end run_scandata ---------------------------------------------------

    ## (2a)

    def run_updatepygbin(self):
        opts = self.opts

        #now update pygbins
        workdir = 'load'
        pqlist =  def_qlist('generate gbins??', opts['auto'])
        pycmd = [self.run_pygbin_npy, ()]
        runcmd(pq=pqlist, pycmd=pycmd, workdir=workdir)

    #--- end run_updategbin ----

    ## (3) python ping processing
    def run_py_pingeditsetup(self):
        '''
        for python single-ping
        '''
        opts = self.opts

        if os.path.exists('load/ping_editparams.txt'):
            _log.info('file %s exists.  not replacing' ,
                                      'load/ping_editparams.txt')
        else:

            if opts['auto']:
                qa_default = 'y'
            else:
                qa_default = 'n'
            msg = 'write editing defaults file (load/ping_editparams.txt)?'
            qa = yn_query(msg, 'ynq', default=qa_default, auto=opts['auto'])

            if qa:

                #-- doing this to be able to ask the question
                ## FIXME: should pqlist be used?
                # pqlist =  def_qlist(msg, opts['auto'])
                pycmd = [self.write_ping_editdefaults, ()]
                rd=runcmd(pq=yeslist(), pycmd=pycmd, workdir='./')
                if rd['pq']:
                    if os.path.exists('load/ping_editparams.txt'):
                        _log.info('... made file load/ping_editparams.txt')

        #--

    def write_ping_editdefaults(self):
        '''
        this will write the file the first time through only.
        maybe it belongs in run_pingavg_npy?
        '''
        cc=Cachefile(cachefile='load/ping_editparams.txt',
                     contents='codas singleping editing defaults')
        editparams = ping_editparams(self.opts['instname'],
                                     badbeam=self.opts['badbeam'])

        editparams['max_search_depth'] = self.opts['max_search_depth']
        editparams['slc_bincutoff']    =  self.opts['slc_bincutoff']
        editparams['slc_deficit']      =  self.opts['slc_deficit']

        cc.init(editparams)

    #--- end run_py_pingeditsetup ---------------

    ## python load data

    def run_pybincmd_lta(self):
        opts=self.opts
        workdir='load'
        # make Pingavg and run it (creates .cmd, .bin, .gps1, .gps2)
        pqlist =  def_qlist(
              'translate LTA? (bin,cmd files-- using python', opts['auto'])
        pycmd = [self.run_loadlta_npy, ()]
        runcmd(pq=pqlist, pycmd=pycmd, workdir=workdir)

    # ---- end python load LTA data ---
    ## python load data

    def run_pybincmd_uhdas(self):
        opts=self.opts

        workdir='load'
        # make Pingavg and run it (creates .cmd, .bin, .gps1, .gps2)
        if not opts['steps2rerun'] and opts['incremental'] is False: # 1st time, batch
            numfiles = len(glob.glob(os.path.join('load', 'ens*.cmd')))
            if numfiles > 0:
                msg = '\n'.join(['%d "cmd" file(s) found.  Not overwriting' % (numfiles),
                                 '(To make new *bin., *.cmd files, '
                                 'start a new processing directory)'])
                _log.info(msg)
                proceed = False
            else:
                proceed = True
        else:
            proceed = True

        if proceed:
            pqlist =  def_qlist(
                'make averages (bin,cmd files)?', opts['auto'])
            pycmd = [self.run_pingavg_npy, ()]
            runcmd(pq=pqlist, pycmd=pycmd, workdir=workdir)

    # ---- end python load UHDAS data ---

     #------------------------
    def run_loadping(self):
        ''' pingdata.  just load
        '''

        workdir = 'load'
        if self.opts['datatype'] == 'pingdata':
            # make cntfile, use it
            cntfile = 'loadping.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.loadping, (cntfile,)]
            sqlist =  def_qlist('load pingdata now?', self.opts['auto'])
            syscmd = 'loadping %s' %(cntfile,)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                       workdir=workdir)

     #------------------------
    def run_loaddb(self):
        """
        Run ldcodas to load bin and cmd files.
        """
        workdir = 'load'

        opts = self.opts

        if opts['datatype'] == 'uhdas':
            loadblks = self.del_overlapping()
            _log.debug(loadblks)
            cmdlist = []
            for num in loadblks:
                cmdlist.append('./ens_blk%03d.cmd' % (num,))
            _log.debug('cmdlist')
            _log.debug(cmdlist)
        else:
            flist = sorted(glob.glob('load/*cmd'))
            cmdlist = []
            for ff in flist:
                cmdlist.append('./' + os.path.split(ff)[1])

        ## see whether new data are available; fill opts['thisload_timerange']
        ## FIXME: surely there must be a better name for that function.
        ##        Maybe it should just return the 3 variables instead of
        ##        stuffing them in opts.
        if not self.fill_thisload_timerange(cmdlist, loaddir='load'):
            _log.info('No new data available to be loaded')
            return

        blklist = glob.glob('adcpdb/*blk')
        if not blklist or opts['incremental']:
            if blklist:
                _log.info('loaded time range: %s', opts['thisload_time_range'])

            cntfile = 'ldcodas.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.ldcodas, (cntfile, cmdlist)]
            sqlist =  def_qlist('load averaged data (into database) now?',
                                     opts['auto'])
            syscmd = 'ldcodas %s' % (cntfile,)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                   workdir=workdir)
            blklist = glob.glob('adcpdb/*blk')
            _log.info('%d block files present', len(blklist))
        else:
            _log.info('%d existing block files found.  Not loading.', len(blklist))

    #--- end run_loaddb -----------------------------------


    ## lst config
    def run_lstconfig(self):

        workdir = 'adcpdb'
        cntfile = 'lst_conf.tmp'
        pycmd = [self.lst_conf, (cntfile,)]
        syscmd = 'lst_conf %s' %  (cntfile,)
        runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(),
               syscmd=syscmd, workdir=workdir)

    #--- end run_lstconfig --------------------------------------------


    ## (3) editsetup
    def run_write_clearflags(self):

        workdir =  'edit'
        cntfile = 'clearflags.tmp'
        tmpfile =os.path.join(workdir, cntfile)
        if os.path.exists(tmpfile):
            _log.info('file exists (%s). not writing' % (tmpfile))
        else:
            pycmd=[self.write_clearflags, (cntfile,)]
            pqlist =  def_qlist('stage (write) clearflags.tmp?',
                                self.opts['auto'])
            # write clearflags once, because it's useful
            # setflags gets written when it's run
            rd=runcmd(pq=pqlist, pycmd=pycmd, workdir=workdir)
            if rd['pq']:
                outfile = os.path.join(workdir,'clearflags.tmp')
                if os.path.exists(outfile):
                    _log.info('... wrote %s' % (outfile))



    #--- end run_editsetup ------------------------------------

    ## (4) setflags
    def run_clearflags(self, workdir='edit'):
        '''
        for python gautoedit
        '''
        opts = self.opts
        startdir = os.getcwd()
        _log.debug('starting in:\n%s' %startdir)
        if os.path.realpath == os.path.realpath(workdir):
            changeback=False
        else:
            os.chdir(workdir)
            changeback=True
        _log.debug('executing commands from:\n%s', workdir)


        cntfile = 'clearflags.tmp'
        syscmd = 'setflags %s' %  (cntfile)
        sstr='(i.e. set PG=%d)' % (opts['pgmin'])
        sqlist =  def_qlist('run clearflags %s ?' %(sstr), opts['auto'])

        runcmd(pq=yeslist(),  sq=sqlist, syscmd=syscmd,  workdir=workdir)


        #now chdir back to original directory
        if changeback:
            os.chdir(startdir)


    #--- end run_clearflags ------------------------------------

    ## (4) setflags
    def run_setflags(self):
        '''
        for matlab gautoedit
        '''
        opts = self.opts

        workdir = 'edit'
        cntfile = 'setflags.tmp'
        pycmd = [self.write_setflags, (cntfile,)]
        syscmd = 'setflags %s' %  (cntfile,)
        sstr='(i.e. set PG=%d)' % (opts['pgmin'])
        sqlist =  def_qlist('run setflags %s ?' %(sstr), opts['auto'])

        runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                                                            workdir=workdir)

    #--- end run_setflags --------------------------------------------


    ## (5) get navigation fixes
    def run_getnav(self):
        opts = self.opts

        if opts['datatype'] == 'pingdata':
            workdir = 'nav'
            cntfile = 'ubprint.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.ubprint, (cntfile,)]
            sqlist =  def_qlist('run ubprint?', opts['auto'])
            syscmd = 'ubprint %s' %  (cntfile,)
            rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                   workdir=workdir)
            if rd['sq']:
                _log.info('... ran upbrint')
        else: #running ldcodas
            workdir = 'nav'
            pqlist =  def_qlist('create navigation file?', opts['auto'])
            pycmd = [self.catnav, ()]
            rd=runcmd(pq=pqlist, pycmd=pycmd, workdir=workdir)

    #--- end run_getnav --------------------------------------------


    ## (6a)

    def run_lsthdg(self):

        ## start by listing heading  (useful anyway)
        workdir = 'cal/rotate'
        cntfile = 'lst_hdg.tmp'
        file_msg(os.path.join(workdir, cntfile))
        pycmd = [self.lst_hdg, (cntfile,)]
        sqlist =  def_qlist('extract headings?', self.opts['auto'])
        syscmd = 'lst_hdg %s' %  (cntfile,)
        rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                   workdir=workdir)
        if rd['sq']:
            _log.info('... headings extracted')


    ## (6) plot heading correction
    def run_plotheadcorr(self):
        ## FIXME: should workdir be passed to plothcorr_mpl?
        #workdir =  os.path.join('cal', 'rotate')
        _log.debug( 'hcorr_inst is %s', self.opts['hcorr_inst'])
        ## only do this for uhdas

        if self.opts['hcorr_inst']:
            if self.opts['auto']:
                qa_default = 'y'
            else:
                qa_default = 'n'

            qa = yn_query('make heading correction plots??',
                          'ynq', default=qa_default, auto=self.opts['auto'])

            if qa:

                try:
                    self.plothcorr_mpl()
                    _log.info('plots are in cal/rotate/*png')
                except:
                    _log.exception('cannot make heading correction plot')


    #--- end run_getheadcorr --------------------------------------------

    ## (7) rotate database for scan timerange
    def run_rotate(self):
        '''
        allow rotation of existing database in first run or in steps2rerun
        leave a dummy file behind if no rotation is done
        '''
        opts = self.opts
        ## first check to see whether we are re-rotating anything
        workdir = os.path.join('cal', 'rotate')
        msg='\n'

        if opts['rotate_angle'] != 0 or opts['rotate_amplitude'] != 1:
            # notify and rotate by amp and phase if amp~=1 or phase ~= 0

            # running "rotated" sets opts['was_rotated']
            pycmd = [self.rotated, ()]
            runcmd(pq=yeslist(), pycmd=pycmd, workdir=workdir)

            if 'rotate' in opts['steps2rerun'] and opts['was_rotated']:
                msg='\n'.join(['\n\n\n',
                           '**************************************************\n',
                           '****** some of these data are already rotated ****\n',
                           '**************************************************\n'])

            ## ... followed by rotate
            workdir = os.path.join('cal', 'rotate')
            cntfile = 'rotate.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.rotate, (cntfile,)]
            sqlist =  def_qlist(msg + '-> run rotate?', opts['auto'])
            syscmd = 'rotate %s' %  (cntfile,)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                   workdir=workdir)
        if not opts['steps2rerun'] and opts['rotate_angle'] == 0 and opts['rotate_amplitude'] == 1:
          # write a dummy rotate.tmp file
            workdir = os.path.join('cal', 'rotate')
            cntfile = 'norotate.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.norotate, (cntfile,)]
            # don't ask.
            syscmd = 'echo "writing dummy rotate file"'
            runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(), syscmd=syscmd,
                   workdir=workdir)


    # --- end run_rotate --------------------------------------------

    ## (8a) run xducerxy
    def run_xducerxy(self):
        opts = self.opts

        #now run xducerxy
        workdir = 'nav'
        pqlist =  def_qlist('run xducerxy (to estimate gps - ADCP offset)? ', opts['auto'])

        pycmd = [self.run_xducerxy_npy, ()]
        runcmd(pq=pqlist, pycmd=pycmd, workdir=workdir)

    #--- end run_xducerxy --------------------------------------------

    ## (8) run adcpsect
    def run_adcpsect(self, comment=''):
        opts = self.opts

        #now run adcpsect (as_nav)
        workdir = 'nav'
        cntfile = 'as_nav.tmp'
        file_msg(os.path.join(workdir, cntfile))
        pycmd = [self.as_nav, (cntfile,)]
        sqlist =  def_qlist(comment + 'run adcpsect?', opts['auto'])
        syscmd = 'adcpsect %s' %  (cntfile,)
        rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                                                    workdir=workdir)
        if rd['sq']:
            _log.info('... ran adcpsect for navsteps')

    #--- end run_adcpsect --------------------------------------------

    ## (9) run refabs
    def run_refabs(self, comment=''):
        opts = self.opts

        # now run refabs
        workdir = 'nav'
        cntfile = 'refabs.tmp'
        pycmd = [self.refabs, (cntfile,)]
        sqlist =  def_qlist(comment + 'run refabs?', opts['auto'])
        syscmd = 'refabs %s' %  (cntfile,)
        rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                                                    workdir=workdir)
        if rd['sq']:
            _log.info('... ran refabs for navsteps')

    # --- end run_refabs --------------------------------------------

    ## (10) run smoothr
    def run_smoothr(self, comment=''):
        opts = self.opts

        workdir = 'nav'
        cntfile = 'smoothr.tmp'
        file_msg(os.path.join(workdir, cntfile))
        pycmd = [self.smoothr, (cntfile,)]
        sqlist =  def_qlist(comment+'run smoothr?', opts['auto'])
        syscmd = 'smoothr %s' %  (cntfile,)
        rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                                                    workdir=workdir)
        if rd['sq']:
            _log.info('... ran smoothr')

    # python: refsm or uvship
    def run_refsm(self, comment=''):
        """
        Returns True on success, False if there was not enough new data.
        """
        opts = self.opts
        if opts['auto']:
            qa_default = 'y'
        else:
            qa_default = 'n'
        _log.info('smoothing method for ship speed: %s' %(opts['ref_method']))
        _log.info('   smoothing window: %s' %(opts['refuv_smoothwin']))
        _log.info('   ship speed source: %s' %(opts['refuv_source']))
        msg = 'calculate smoothed shipspeeds for database?'
        qa = yn_query(msg, 'ynq', default=qa_default, auto=opts['auto'])

        output = False
        if qa:
            try:
                if opts['ref_method'] == 'refsm':
                    output = self.run_refsm_npy()
                    _log.info('... shipspeed smoothing step done')
                    OK = True
                else:
                    OK = False
            except:
                _log.exception('cannot run numpy reflayer smoothing')
            if not OK:
                raise quickFatalError('Only ref_method "refsm" is allowed')
        return output

    #--- end run_smoothr and run_smoothnav ---------------------------------

    ## (11) putnav
    def run_putnav(self):
        opts = self.opts

        workdir = 'nav'
        cntfile = 'putnav.tmp'
        file_msg(os.path.join(workdir, cntfile))
        pycmd = [self.putnav, (cntfile,)]
        comment = '(put navigation and ship speeds into database)\n'
        sqlist =  def_qlist(comment + 'run putnav?', opts['auto'])
        syscmd = 'putnav %s' %  (cntfile,)
        rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                                                        workdir=workdir)
        if rd['sq']:
            _log.info('... ran putnav')


    ## (11) put_txy
    def run_put_txy(self):
        opts = self.opts

        workdir = 'nav'
        cntfile = 'put_txy.tmp'
        file_msg(os.path.join(workdir, cntfile))
        pycmd = [self.put_txy, (cntfile,)]
        comment = '(put navigation into database: NOTE runs "put_txy", not "putnav")\n'
        sqlist =  def_qlist(comment+'run put_txy?', opts['auto'])
        syscmd = 'put_txy %s' %  (cntfile,)
        rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                                                        workdir=workdir)
        if rd['sq']:
            _log.info('... ran put_txy')


    ## (11) put_tuv
    def run_put_tuv(self):
        opts = self.opts

        workdir = 'nav'
        cntfile = 'put_tuv.tmp'
        file_msg(os.path.join(workdir, cntfile))
        pycmd = [self.put_tuv, (cntfile,)]
        comment = '(put ship speeds into database: NOTE runs "put_tuv", not "putnav")\n'
        sqlist =  def_qlist(comment+'run put_tuv?', opts['auto'])
        syscmd = 'put_tuv %s' %  (cntfile,)
        rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                                                        workdir=workdir)
        if rd['sq']:
            _log.info('... ran put_tuv')



    #--- end putnav --------------------------------------------

    def run_plotnav_mpl(self):
        opts = self.opts
        if opts['auto']:
            qa_default = 'y'
        else:
            qa_default = 'n'
        msg = 'plot navigation?'
        qa = yn_query(msg, 'ynq', default=qa_default, auto=opts['auto'])

        if qa:
            self.plotnav_mpl()
            _log.info('... made navigation plot')



    def run_plotrefl_mpl(self):
        opts = self.opts
        if opts['auto']:
            qa_default = 'y'
        else:
            qa_default = 'n'
        msg = 'make reflayer plots?'
        qa = yn_query(msg, 'ynq', default=qa_default, auto=opts['auto'])

        if qa:
            self.plotrefl_mpl()
            _log.info('... made reflayer plots')


    def write_codas_editdefaults(self):
        '''
        this will write the file the first time through only.
        maybe it belongs in run_autoedit_npy?
        '''
        # NOTE: reference layer and pgmin (from opts) are independent of this
        cc=Cachefile(cachefile='edit/codas_editparams.txt',
                     contents='codas editing defaults')
        edit_params = codas_editparams
        for name in codas_start_disabled:
            edit_params[name] = codas_disableparams[name]
        cc.init(edit_params)


    def run_py_codaseditsetup(self):
        '''
        for python gautoedit
        '''
        opts = self.opts

        if os.path.exists('edit/codas_editparams.txt'):
            _log.debug('file %s exists.  not replacing' ,
                                            'edit/codas_editparams.txt')
        else:
            msg = 'write editing defaults file (edit/codas_editparams.txt)?'
            pqlist =  def_qlist(msg, opts['auto'])
            pycmd = [self.write_codas_editdefaults, ()]
            rd=runcmd(pq=pqlist, pycmd=pycmd, workdir='./')
            if rd['pq']:
                _log.info('... wrote edit/codas_editparams.txt')

    #--- end run_py_codaseditsetup ---------------


    def run_py_findpflags(self):
        opts = self.opts

        if opts['steps2rerun']:  #do the whole database
            opts['edit_startdd'] =  opts['loaded_startdd']
            opts['edit_enddd']   =  opts['loaded_enddd']
        else: # just do the part that was loaded
            opts['edit_startdd'] =  opts['thisload_startdd'] - .3
            opts['edit_enddd']   =  opts['thisload_enddd']


        tstr = '%7.4f to %7.4f' % (opts['edit_startdd'], opts['edit_enddd'])

        opts['fformat'] = 'a%s_tmp.asc'

        workdir = 'edit'
        pqlist =  def_qlist(
            'find profile flags for dday range %s ?' % (tstr), opts['auto'])

        pycmd = [self.run_autoedit_npy, ()]
        rd=runcmd(pq=pqlist, pycmd=pycmd, workdir=workdir)
        if rd['pq']:
            _log.info('... extracted files using automatic editing')

    #--- end run_findpflags--------------------------------------------

    ## (14) apply editing (all kinds)
    def run_applyedit(self, workdir='edit', abs_db_path=None, log_path=None,
                      verbose=True):
        # TODO: docu.
        opts = self.opts

        if opts['auto']:
            qa_default = 'y'
        else:
            qa_default = 'n'
        qa = yn_query('apply all profile flags to database?', 'ynq',
                      default=qa_default, auto=opts['auto'])

        if qa:
            startdir = os.getcwd()
            if verbose:
                _log.debug('starting in:\n%s' %startdir)
            if os.path.realpath == os.path.realpath(workdir):
                changeback=False
            else:
                os.chdir(workdir)
                changeback=True
            if verbose:
                _log.debug('executing commands from:\n%s', workdir)

            # write editing to a file
            elines=[]

            ## go get the files first
            bottom_files = glob.glob('*bottom*.asc')

            dbupdate_files = glob.glob('*badprf*.asc')
            dbupdate_files += glob.glob('*badtim*.asc')

            badbinfiles = glob.glob('*badbin*.asc')


            cntfile = 'setflags.tmp'
            if not abs_db_path:
                dbpath = os.path.join('..', 'adcpdb', opts['dbname'])
            else:
                dbpath = abs_db_path

            # run dbupdate for bottom files
            for ii in range(0, len(bottom_files)):
                syscmd = 'dbupdate %s %s' % (dbpath, bottom_files[ii])
                _log.debug('about to run %s', syscmd)
                system_cmd(syscmd)
                elines.append(syscmd)

            ## 'set_lgb' operates on whole blocks, for blocks with
            ##           data processing bit 8=ON 9=OFF
            ## These data processing bits are what dbupdate sets when
            ##           it is run on bottom files.
            if len(bottom_files) > 0:  # run once after all 'dbupdate' for MAB
                # set_lgb
                syscmd = 'set_lgb %s %d' % (dbpath, opts['beamangle'])
                if verbose:
                    _log.debug('about to run %s', syscmd)
                system_cmd(syscmd)
                elines.append(syscmd)


            # run dbupdate for badprofile files
            for ii in range(0, len(dbupdate_files)):
                syscmd = 'dbupdate %s %s' % (dbpath, dbupdate_files[ii])
                if verbose:
                    _log.debug('about to run %s', syscmd)
                system_cmd(syscmd)
                elines.append(syscmd)

            # run badbin
            for ii in range(0, len(badbinfiles)):
                syscmd = 'badbin %s %s' % (dbpath, badbinfiles[ii])
                if verbose:
                    _log.debug('about to run %s', syscmd)
                system_cmd(syscmd)
                elines.append(syscmd)

            # set_flags
            self.write_setflags(cntfile)
            syscmd = 'setflags %s' % (cntfile,)
            if verbose:
                _log.debug('about to run %s', syscmd)
            system_cmd(syscmd)
            elines.append(syscmd)
            elines.append('\n')

            if log_path:
                message = ['\n  Commands ran by run_applyedit:']
                message.append('====================')
                message.extend(elines)
                with open(log_path, 'a') as file:
                    file.write('\n  '.join(message))
            else:
                with open('edit.log','w') as file:
                    file.write('\n'.join(elines))

            if verbose:
                _log.debug('changing directories back to %s' %startdir)

            #now chdir back to original directory
            if changeback:
                os.chdir(startdir)

    #-- end run_applyedit --------------------------------------------


    ## (16) list temperature
    def run_lstplot_temp(self):
        opts = self.opts

        workdir = 'edit'
        cntfile = 'lst_temp.tmp'
        pycmd = [self.lst_temp, (cntfile,)]
        sqlist =  def_qlist('extract and plot temperature?', opts['auto'])
        syscmd = 'lst_temp %s' %  (cntfile,)
        rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
                workdir=workdir)
        if rd['sq']:
            try:
                self.plottemp_mpl(printformats=opts['printformats'])
                _log.info('plotted temperature')
            except:
                _log.exception('cannot plot temperature')


    #-- end run_lsttemp --------------------------------------------

    ## (16) list npings and plot it
    def run_lstplot_npings(self):
        opts = self.opts

        workdir = 'edit'
        cntfile = 'lst_npings.tmp'
        file_msg(os.path.join(workdir, cntfile))
        pycmd = [self.lst_npings, (cntfile,)]
        sqlist =  def_qlist('extract and plot number of pings per ensemble?', opts['auto'])
        syscmd = 'lst_npings %s' % (cntfile,)
        rd=runcmd(pq=yeslist(), pycmd=pycmd, sq=sqlist, syscmd=syscmd,
               workdir=workdir)

        if rd['sq']:
            ## plot npings
            workdir = 'edit'
            try:
                self.plotnpings_mpl(printformats=opts['printformats'])
                _log.info('... plotted number of pings per ensemble')
            except:
                _log.exception('cannot make npings plot')

    #--- end run_lstnpings --------------------------------------------

    def run_guess_xducerxy(self):
        opts = self.opts

        workdir = 'cal/watertrk'
        pqlist =  def_qlist('guess dx,dy offset of ADCP from GPS?',
                                 opts['auto'])

        pycmd = [self.run_guess_xducerxy_npy, ()]
        rd=runcmd(pq=pqlist, pycmd=pycmd, workdir=workdir)
        if rd['pq']:
            _log.info('... check cal/watertrk for estimate')

    # ----- end guess_xducerxy

    def run_plot_uvship(self):

        if self.opts['auto']:
            qa_default = 'y'
        else:
            qa_default = 'n'

        qa = yn_query(
              'plot uvship??? ',
              'ynq', default=qa_default, auto=self.opts['auto'])

        if qa:
            self.plotuvship_mpl()
            _log.info('plotted  uvship')

    # ----- end plot_uvship

    ## (17) run water track and bottom track calibrations
    def run_calib(self):
        opts = self.opts

        if self.opts['auto']:
            qa_default = 'y'
        else:
            qa_default = 'n'

        qa = yn_query(
              'calculate watertrack and bottomtrack calibrations?? ',
              'ynq', default=qa_default, auto=self.opts['auto'])

        if qa:

            ## (17a: bottom track)
            ## (17a.1)now run lst_btrk
            workdir = os.path.join('cal', 'botmtrk')
            cntfile = 'lst_btrk.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.lst_btrk, (cntfile,)]
            syscmd = 'lst_btrk %s ' %  (cntfile,)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(),
                   syscmd=syscmd, workdir=workdir)

            ## (17a.2) now run refabsbt
            workdir = os.path.join('cal', 'botmtrk')
            cntfile = 'refabsbt.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.refabsbt, (cntfile,)]
            syscmd = 'refabsbt %s' %  (cntfile,)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(),
                   syscmd=syscmd, workdir=workdir)
            _log.info('...bottom track info in check cal/botmtrk')

            ## use settings for nb mode
            if self.opts['mixed_pings']:
                sonar = Sonar(self.opts['sonar'])
                if sonar.model == 'os':
                    params_sonar = sonar.instname + 'nb'
                else:
                    params_sonar = self.opts['sonar']
            else:
                params_sonar = self.opts['sonar']

            try:
                ps_defaults = uhdas_defaults.proc_sonar_defaults
                min_depth = ps_defaults.btrk_mindepth[params_sonar]
                max_depth = ps_defaults.btrk_maxdepth[params_sonar]
                opts['min_depth'] = min_depth
                opts['max_depth'] = max_depth
                self.plotbtcal_mpl()
            except:
                _log.exception('cannot run mpl bottom track')

            ## (17b: water track)
            ## (17b.1) run adcpsect (as_nav)
            workdir = 'nav'
            cntfile = 'as_nav.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.as_nav, (cntfile,)]
            syscmd = 'adcpsect %s' %  (cntfile,)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(),
                   syscmd=syscmd, workdir=workdir)

            ## (17b.2) now run watertrack timeslip
            workdir = os.path.join('cal', 'watertrk')
            cntfile = 'timslip.tmp'
            file_msg(os.path.join(workdir, cntfile))
            pycmd = [self.timslip, (cntfile,)]
            syscmd = 'timslip %s' %  (cntfile,)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(),
                   syscmd=syscmd, workdir=workdir)
            _log.info('... watertrack info in cal/watertrk')
            try:
                self.plotwtcal_mpl(printformats=opts['printformats'])
            except:
                _log.exception('cannot run watertrack calibration')

    #--- end run_calib --------------------------------------------
