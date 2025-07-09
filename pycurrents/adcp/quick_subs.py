"""
Library for quick_adcp: including mixin class with methods to run the
processing steps.

 listblocks               : listblocks (adcpdb/dbname.lst)
 get_time_range           : get time range from scan or lstlblk
 write_timerange_file     : write time range file
 fill_thisload_timerange  : get time range for partial load
 del_overlapping          :

 scanping                 : pingdata scan
 loadping                 : pingdata load
 ubprint                  : pingdata extract nav, attitude

# most of these just write control files.  The running is in quick_run
 ldcodas                  : load *bin,*cmd from
 setflags                 : setflags
 clearflags               : clearflags
 lst_conf                 : list configuration (load/dbname.cnh)
 catnav                   : catnav
 rotated                  : rotated    (check: rotated?)
 rotate                   : rotate     rotate whole database
 norotate                 : norotate   just print the rotate.tmp file
 as_nav                   : as_nav     navsteps (1)
 refabs                   : refabs     navsteps (2)
 smoothr                  : smoothr    navsteps (3)
 putnav                   : putnav     navsteps (4)
 put_txy                  : put_txy    navsteps (4)
 put_tuv                  : put_tuv    navsteps (4)
 lst_temp                 : lst_temp   list temperature
 lst_npings               : lst_npings   list number of pings per ensemble
 lst_hdg                  : lst_hdg    lsit heading
 lst_btrk                 : lst_btrk   list bottom track
 refabsbt                 : refabsbt   bottom track cal, part 2
 timslip                  : timslip    watertrack part1

"""

import os
import re
import glob
import logging
from subprocess import getstatusoutput

from pycurrents.adcp.quick_setup import (quickFatalError,
                                         get_cmd_timerange)
from pycurrents.adcp.quick_setup import (system_cmd,
                                         nodb_times)
from pycurrents.data.timetools import ddtime

# Standard logging
_log = logging.getLogger(__name__)


class Q_subs:
    """
    Mixin for the Processor class.
    """

    #------------------
    def listblocks(self, workdir=None):
        """
        Run lstblock in *workdir*.

        It returns the output file contents of lstblock as a list of lines,
        or None if there is no database.

        It raises quickFatalError if lstblock fails.
        """

        opts = self.opts
        if workdir is None:
            raise quickFatalError('listblocks workdir not specified')

        blockfiles = sorted(glob.glob(os.path.join(workdir, '*.blk')))
        if not blockfiles:
            return None

        outfile = os.path.join(workdir, '%s.lst' % opts['dbname'])
        dbpath = os.path.join(workdir, opts['dbname'])
        cmd = 'lstblock %s %s' % (dbpath, outfile)
        _log.debug('running external command "%s"', cmd)
        status, output = getstatusoutput(cmd)
        if status:
            matchobj = re.findall(r"(ERROR)", output)
            if len(matchobj) > 0 and opts['datatype'] == 'uhdas':
                msg = 'ERROR OPENING DATABASE; deleting database.\n'
                for filename in blockfiles:
                    msg += 'removing file %s\n' %(filename)
                    os.remove(filename)
            else:
                msg = 'lstblock failed with output:\n%s' % output
            raise quickFatalError(msg)

        else:
            _log.debug('lstblock ran successfully.')

        with open(outfile) as f:
            blocklist = f.readlines()
        return blocklist

    def get_time_range(self, timefile, start_end_times=None):
        """
        Extract time range from either of two sources.

        If *start_end_times* is None, *timefile* can be either the output
        from scan or lstblock as a list, or the name of a file containing
        that output.

        Otherwise, *timefile* is ignored, and *start_end_times* must be
        a string in the form 'YYYY/MM/DD hh:mm:ss to YYYY/MM/DD hh:mm:ss'.

        Returns a string in the above form, and floating point numbers with
        the decimal day start and end times.
        """

        opts = self.opts

        # This function reads a file from scan or lstblock and
        # returns the ascii time_range and decimal start and
        # end days of the data also works on the summary
        # file *.tr, generated from same.
        pat = r"\b\d{2,4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\b"

        if start_end_times is None:
            if isinstance(timefile, list):
                timelines = timefile
            else:
                with open(timefile) as f:
                    timelines = f.readlines()
            first = True
            for line in timelines:
                matchobj = re.findall(pat, line)
                if matchobj:
                    if first:
                        start_time = matchobj[0]
                        first = False
                    end_time = matchobj[-1]
                    #if len(matchobj) == 1:    #scanping: one date/ line
                    #    end_time = matchobj[0]
                    #else:              #scan from rawadcp read  or lstblk
                    #    end_time = matchobj[1]

            start_end_times = start_time + ' to ' + end_time
        else:
            matchobj = re.findall(pat, start_end_times)
            start_time = matchobj[0]
            end_time = matchobj[1]

        dd0 = ddtime(opts['proc_yearbase'], start_time)
        dd1 = ddtime(opts['proc_yearbase'], end_time)

        _log.debug('start_end_time %s', start_end_times)
        _log.debug('dd0: %f   dd1: %f' , dd0, dd1)

        return start_end_times, dd0, dd1

    def write_timerange_file(self, trfile, start_end_times):
        with open(trfile, 'w') as TR:
            TR.write(start_end_times)
            TR.write('\n')

    def fill_thisload_timerange(self, cmdlist, loaddir=None):
        '''
        Store time range for unloaded data in opts fields.

        Returns True if there is data available to load,
        otherwise False.
        '''
        opts=self.opts
        if loaddir is None:
            raise quickFatalError('must specify loaddir')
        if len(cmdlist) > 0:
            ## start time of unloaded data from first unloaded file
            trddlist = get_cmd_timerange(
                os.path.join(loaddir,cmdlist[0]),
                yearbase=opts['proc_yearbase'])
            time_range_0 = trddlist[0]
            opts['thisload_startdd'] = trddlist[1]

            trddlist = get_cmd_timerange(
                os.path.join(loaddir,cmdlist[-1]),
                yearbase=opts['proc_yearbase'])

            opts['thisload_enddd'] = trddlist[1]

            starttime = time_range_0.split('to')[0]
            endtime = time_range_0.split('to')[-1]
            opts['thisload_time_range'] = '%s to %s' % (starttime, endtime)
            return True
        else:
            # no data to load
            opts['thisload_time_range'] = ''
            opts['thisload_startdd'] = None
            opts['thisload_enddd'] =   None
            return False

    #---- end fill_thisload_timerange -------------------------
    ##===============    adcp processing routines =====================


    def scanping(self, cntfile):
        opts = self.opts
        # This function scans the pingdata files

        scanping_cnt = '''
        OUTPUT_FILE:         %(dbname)s.scn
        SHORT_FORM:          no
        UB_OUTPUT_FILE:      none
        USER_BUFFER_TYPE:    %(ub_type)s
        UB_DEFINITION:       ub_%(ub_type)s.def
        PINGDATA_FILES:
     ''' % opts

        for scanfilename in opts['filelist']:
            scanping_cnt = scanping_cnt + scanfilename + '\n'

        _log.debug(scanping_cnt)
        scn = open(cntfile, 'w')
        scn.write(scanping_cnt)
        scn.close()

    #--- end of scanping ------------------------------------------


    def del_overlapping(self):
        '''
        delete overlapping blocks from database, redo mkblkdir, rerun listblock
        run this from procdir
        corresponding *.cmd files and block files have the same names
        fills orig_db_time_range with new values
        '''
        opts=self.opts
        dbpath = os.path.join('adcpdb', opts['dbname'])

        ## first find overlaps
        blk_glob_pat = dbpath + '*.blk'
        blkfiles = sorted(glob.glob(blk_glob_pat))
        if len(blkfiles) == 0:
            lastblock = 0
        else:
            if blkfiles[-1][-7:] != 'dir.blk':
                raise quickFatalError('missing blkdir file')
            blkfiles = blkfiles[:-1]
            lastblock = len(blkfiles)
            if blkfiles[-1][-7:] != '%03d.blk' % (lastblock):
                raise quickFatalError('inconsistent blockfiles')

        cmdfiles = glob.glob(os.path.join('load', 'ens_blk*.cmd'))
        cmdfiles.sort()
        lastcmd = len(cmdfiles)
        if len(cmdfiles) > 0:
            if cmdfiles[-1][-7:] != '%03d.cmd' % (lastcmd):
                raise quickFatalError('inconsistent cmd files')

        if not opts['incremental']:
            delblks = []
            if lastblock == 0:
                loadblks = list(range(1,lastcmd+1))
            else: # data exist
                loadblks = []
        else:
            # add one because blockfiles are 1-based origin
            lowestblock = max(1, lastblock)
            delblks = list(range(lowestblock, lastblock+1))
            loadblks = list(range(lowestblock, lastcmd+1))

        _log.debug('in del_overlapping:\n'
                  '  lastblock: %s\n'
                  '  lastcmd: %s\n'
                  '  delblks: %s\n'
                  '  loadblks: %s\n', lastblock, lastcmd, delblks, loadblks)

        # now delete requested blockfiles and run mkblkdir if blocks remain
        if delblks:
            dirblk = dbpath + 'dir.blk'
            if os.path.exists(dirblk):
                os.remove(dirblk)
            for bnum in delblks:
                fname = '%s%03d.blk' % (dbpath, bnum)
                os.remove(fname)

            db_files = sorted(glob.glob(blk_glob_pat))
            if db_files:
                _log.debug('blockfiles remain; running mkblkdir')

                cntfile = os.path.join('adcpdb', 'mkblkdir.tmp')
                mkblkdir = ['DB_NAME %s' % dbpath]
                mkblkdir.append('end')

                for dbfile in db_files:
                    mkblkdir.append('BLOCK_FILE %s' % dbfile)

                mkblkdir.append(' ')
                with open(cntfile, 'w') as mk:
                    mk.write('\n'.join(mkblkdir))

                syscmd = 'mkblkdir %s' % cntfile
                _log.debug('running %s', syscmd)
                system_cmd(syscmd)

        # get the database times for the remaining blockfiles
        lstblk_output = self.listblocks(workdir='adcp')
        if lstblk_output:
            trfile = os.path.join('adcpdb','%(dbname)s.tr' % opts)
            trddlist = self.get_time_range(lstblk_output)
            self.write_timerange_file(trfile, trddlist[0])
            opts['orig_time_range'] = trddlist[0]
            opts['orig_startdd'] = trddlist[1]
            opts['orig_enddd'] = trddlist[2]
        else:
            opts['origdb_time_range'] = nodb_times[0]
            opts['origdb_startdd'] = nodb_times[1]
            opts['origdb_enddd'] =  nodb_times[2]

        return loadblks

    #--- end loaded -------------------------------------------------------
    def loadping(self, cntfile):
        opts = self.opts
        # This function loads pingdata files

        loadping_cnt = '''
          DATABASE_NAME:            ../adcpdb/%(dbname)s
          DEFINITION_FILE:          ../adcpdb/adcp%(ub_type)s.def
          OUTPUT_FILE:              ../adcpdb/%(dbname)s.lod
          MAX_BLOCK_PROFILES:       400
          NEW_BLOCK_AT_FILE?        yes
          NEW_BLOCK_AT_HEADER?      no
          NEW_BLOCK_TIME_GAP(min):  32767
      /*  to skip headers, insert:  skip_header_range:  n1 to n2 */
          PINGDATA_FILES:
     ''' % opts
        for pingfilename in opts['filelist']:
            loadping_cnt = loadping_cnt + pingfilename + ' end \n'


        opts['thisload_time_range'] =   opts['scn_time_range']
        opts['thisload_startdd'] =      opts['scn_startdd']
        opts['thisload_enddd'] =        opts['scn_enddd']


        _log.debug(loadping_cnt)
        ld = open(cntfile, 'w')
        ld.write(loadping_cnt)
        ld.close()

    #--- end loadping -------------------------------------------------------

    def ldcodas(self, cntfile, cmdlist=[]):
        '''
        run from load
        loadblks is a slice coming from
              -- uhdas:     del_overlapping
              -- vmdas:     all

        if loadblks is None, load all
        '''

        opts = self.opts

        ldcodas_cnt = '''
        DATABASE_NAME:   ../adcpdb/%(dbname)s
        DEFINITION_FILE: %(data_def)s
        LOG_FILE:  load.log
        YEAR_BASE: %(proc_yearbase)d
        cmd_file_list          /* use only if specifying cmd paths, not "@" */
        END

     ''' % opts

        _log.debug('filling "thisload" timerange')
        self.fill_thisload_timerange(cmdlist, loaddir='./')

        _log.debug('in ldcodas')
        _log.debug('cmdlist:')
        _log.debug(cmdlist)

        ldcodas_cnt = ldcodas_cnt + '\n'.join(cmdlist)

        cntfile = 'ldcodas.tmp'
        _log.debug(ldcodas_cnt)
        ld = open(cntfile, 'w')
        ld.write(ldcodas_cnt)
        ld.close()

    #--- end ldcodas -------------------------------------------------------

    def write_setflags(self, cntfile):
        ## write setflags.tmp

        setflags_cnt = '''
        dbname:     ../adcpdb/%(dbname)s
        pg_min:      %(pgmin)s
        set_range_bit
        time_ranges:
             all

     ''' % self.opts

        _log.debug(setflags_cnt)
        sf = open(cntfile, 'w')
        sf.write(setflags_cnt)
        sf.close()

    def write_clearflags(self, cntfile, tr='all', db_dir = '../adcpdb'):
        ## also write clearflags.tmp, just because it's useful
        clearflags_cnt = '''
           dbname:     %s
           pg_min:      %s
                clear_range             /* reset range */
                clear_all_bits          /* clear flags except pg_min*/
                clear_bad_profile       /* reset access vars lgb */
           time_ranges:
                %s

        ''' % (db_dir, self.opts['pgmin'], tr)

        _log.debug(clearflags_cnt)
        sf = open(cntfile, 'w')
        sf.write(clearflags_cnt)
        sf.close()

    #--- end setflags --------------------------------------------------------

    def lst_conf(self, cntfile):
        opts = self.opts
        ## make and run setflags

        lst_conf_cnt = '''
        dbname:     %(dbname)s
        output:     %(dbname)s.cnh
        time_ranges:
             all

     ''' % opts

        _log.debug(lst_conf_cnt)
        cf = open(cntfile, 'w')
        cf.write(lst_conf_cnt)
        cf.close()

    #--- end lst_conf -------------------------------------------------------

    def ubprint(self, cntfile):
        opts = self.opts
        # This function reads extracts the ags data from user-buffer in codasdb
        ub_cnt = '''
          dbname:          ../adcpdb/%(dbname)s
          output:          %(dbname)s
          step_size=       1
          year_base=       %(proc_yearbase)s
          variables:
             avg_GPS_summary
             avg_GPS2_summary
             attitude_mat
             position
             end
          time_ranges:
             %(loaded_time_range)s       /* the whole time range */

     ''' % opts

        _log.debug(ub_cnt)
        ub = open(cntfile,'w')
        ub.write(ub_cnt)
        ub.close()


    #--- end ubprint -------------------------------------------------------

    def catnav(self):
        opts = self.opts

        load_suffix=('gps2', 'gpst2')  ##cat these
        nav_suffix=('gps', 'agt')      ## into here
        for num in (0,1):
            #cat gps navigation from ../load/ generated by load_XXX step
            nav_glob = '*.%s' % (load_suffix[num])
            navfilelist = glob.glob(os.path.join('..','load', nav_glob))
            navfilelist.sort()
            numfiles = len(navfilelist)

            if numfiles > 0:
                navfilename = '%s.%s' % (opts['dbname'], nav_suffix[num])
                navfile = open(navfilename, 'w')
                for ii in range (0,len(navfilelist)):
                    infile = open(navfilelist[ii], 'r')
                    lines = infile.readlines()
                    navfile.write(''.join(lines))
                    infile.close()
                navfile.close()

                _log.info('navigation file nav/%s created from load/%s' %
                         (navfilename, nav_glob))

        # just look for the files; cat if present
        if opts['proc_engine'] == 'python':
            uvshiplist = glob.glob('../load/*.uvship')
            if len(uvshiplist) > 0:
                uvshiplist.sort()
                uvshipfile = open('%s.uvship' % (opts['dbname']), 'w')
                for ii in range (0,len(uvshiplist)):
                    infile = open(uvshiplist[ii], 'r')
                    lines = infile.readlines()
                    uvshipfile.write(''.join(lines))
                    infile.close()
                uvshipfile.close()

    #--- end catnav -------------------------------------------------------

    def rotated(self):
        '''
        run from cal/rotate
        '''
        opts = self.opts
        # This return states whether a database has been rotated
        #  (subsequently used to determine whether further rotation should occur)
        _log.debug(os.getcwd())

        rotated_endtime = '1970/01/01  01:01:01'
        if (os.path.exists('rotate.log') == 0):
            _log.debug('No existing file: cal/rotate/rotate.log')
            opts['was_rotated'] = False
            return

        with open('rotate.log','r') as newreadf:
            log_list = newreadf.readlines()
        N = len(log_list)

        if N==0:
            _log.debug('no valid times in rotate.log')
            opts['was_rotated'] = False
            return

        for ii in range(0,N):
            if log_list[ii].find('Processing range') > 0:
                jj = log_list[ii].find(' to ')
                line = log_list[ii]
                rotated_endtime = line[jj+4:-1]

        _log.info(rotated_endtime)
        # lastrotated_dday is end of the rotated data
        # it is either the last time in rotate.log
        # or it is the end of the originally loaded database
        #     (if that is earlier)
        lastrotated_dday = ddtime(opts['proc_yearbase'], rotated_endtime)
        _log.info('last rotate dday')
        _log.info(lastrotated_dday)
        _log.info('first database dday')
        _log.info(opts['loaded_startdd'])

        opts['was_rotated'] = lastrotated_dday > opts['loaded_startdd']

    #--- end rotated -------------------------------------------------------

    def rotate(self, cntfile):
        opts = self.opts
        # The routine rotates the velocities in the database using
        #  both the *.ang file and the rotate_amplitude and rotate_angle

        if  opts['ping_headcorr']:
            _str = '/*  time_angle_file:  (NOT USED -- rotation is done in ensembles) */'
        else:
            _str = '/*  time_angle_file:  (NOT USED) */'


        opts['tempstr'] = _str

        rotate_cnt = '''
           DB_NAME:       ../../adcpdb/%(dbname)s
           LOG_FILE:      rotate.log
           TIME_RANGE:    %(loaded_time_range)s     /* entire database */

           OPTION_LIST:
              water_and_bottom_track:
                year_base=          %(proc_yearbase)s
                %(tempstr)s
                amplitude=          %(rotate_amplitude)s
                angle_0=            %(rotate_angle)s
                end
              end

     ''' % opts

        _log.debug(rotate_cnt)
        rot = open(cntfile,'w')
        rot.write(rotate_cnt)
        rot.close()

        del opts['tempstr']

    #--- end rotate ---------------------------------------------------------

    def norotate(self, cntfile):
        opts = self.opts
        # just write an example of the rotate file

        rotate_cnt = '''

          /* No rotation was done using the "rotate" command, but */
          /* it is useful have the skeleton of a rotate.tmp file  */
          /* to edit, should the need arise.  That is the purpose */
          /* of this file. */

           DB_NAME:       ../../adcpdb/%(dbname)s
           LOG_FILE:      rotate.log
           TIME_RANGE:    %(loaded_time_range)s

           OPTION_LIST:
              water_and_bottom_track:
                year_base=          %(proc_yearbase)s
                /*  time_angle_file:  time_angle.ang */
                amplitude=          1.0
                angle_0=            0.0
                end
              end

     ''' % opts

        _log.debug(rotate_cnt)
        rot = open(cntfile,'w')
        rot.write(rotate_cnt)
        rot.close()

    #--- end rotate ---------------------------------------------------------

    def as_nav(self, cntfile):
        opts = self.opts
        # This routine runs adcpsect to get navgation and heading data
        asnav_cnt = '''
           dbname:             ../adcpdb/%(dbname)s
           output:             %(dbname)s
           step_size:          1
           ndepth:             %(rl_endbin)s
           time_ranges:        separate
           year_base=          %(proc_yearbase)s

           option_list:
             pg_min=           %(pgmin)s
           navigation:
             reference_bins  %(rl_startbin)s  to   %(rl_endbin)s
             end
           statistics:       mean
             units=          0.01       /* cm/s instead of default m/s */
             end
           flag_mask:        ALL_BITS
             end
           end
          %(loaded_time_range)s                 /* the whole time range */

     ''' % opts

        _log.debug(asnav_cnt)
        nav = open(cntfile, 'w')
        nav.write(asnav_cnt)
        nav.close()


    #--- end as_nav -------------------------------------------------------


    def refabs(self, cntfile):
        opts = self.opts
        # Routine runs refabs to get the absolute reference layer velocities
        ref_cnt = '''
           fix_file_type:    simple
           reference_file:   %(dbname)s.nav
           fix_file:         %(fixfilexy)s
           output:           %(dbname)s.ref
           year_base=        %(proc_yearbase)s
           ensemble_length=  %(ens_len)s
           gap_tolerance=    10

     ''' % opts

        _log.debug(ref_cnt)
        ref = open(cntfile,'w')
        ref.write(ref_cnt)
        ref.close()



    #--- end refabs -------------------------------------------------------



    def smoothr(self, cntfile):
        opts = self.opts
        # Routine to smoorth the reference layer velocities
        smoothr_cnt = '''
           reference_file:       %(dbname)s.nav
           refabs_output:        %(dbname)s.ref
           output:               %(dbname)s.sm
           filter_hwidth=        %(filter_hwidth)s
           min_filter_fraction=  0.5
           max_gap_ratio=        0.05
           max_gap_distance=     50
           max_gap_time=         30            /* 0.5  minutes */
           ensemble_time=        %(ens_len)s
           max_speed=            5.0
           min_speed=            1.0
           iterations=           5
           fix_to_dr_limit=      0.00050

     ''' % opts


        _log.debug(smoothr_cnt)
        smth = open(cntfile, 'w')
        smth.write(smoothr_cnt)
        smth.close()


    #--- end smoothr --------------------------------------------------------

    def putnav(self, cntfile):
        opts = self.opts
        # Update the data base with the results of the reference layer smoothing

        putnav_cnt = '''
           dbname:         ../adcpdb/%(dbname)s
           position_file:  %(smfile)s
           year_base=      %(proc_yearbase)s
           tolerance=      5
           navigation_sources:
             gps
             end

     ''' % opts

        _log.debug(putnav_cnt)
        put = open(cntfile, 'w')
        put.write(putnav_cnt)
        put.close()

    #--- end putnav -------------------------------------------------------

    def put_txy(self, cntfile):
        opts = self.opts
        # Update the data base with positions

        put_txy_cnt = '''
           dbname:         ../adcpdb/%(dbname)s
           position_file:  %(txy_file)s
           year_base=      %(proc_yearbase)s
           tolerance=      5

     ''' % opts

        _log.debug(put_txy_cnt)
        put = open(cntfile, 'w')
        put.write(put_txy_cnt)
        put.close()

    #--- end put_txy -------------------------------------------------------

    def put_tuv(self, cntfile):
        opts = self.opts
        # Update the data base with uship, vship (from refsm)

        put_tuv_cnt = '''
           dbname:         ../adcpdb/%(dbname)s
           shipspeed_file:     %(tuv_file)s
           year_base=      %(proc_yearbase)s
           tolerance=      5

     ''' % opts

        _log.debug(put_tuv_cnt)
        put = open(cntfile, 'w')
        put.write(put_tuv_cnt)
        put.close()

    #--- end put_tuv -------------------------------------------------------


    def lst_temp(self, cntfile):
        opts = self.opts
        # list temperature

        lsttemp_cnt = '''
        dbname:         ../adcpdb/%(dbname)s
        output:           %(dbname)s.tem
        step_size=        1
        year_base=        %(proc_yearbase)d
        time_ranges:
        all

        ''' %opts

        _log.debug(lsttemp_cnt)
        ltemp = open(cntfile, 'w')
        ltemp.write(lsttemp_cnt)
        ltemp.close()

    #--- end lst_temp.py --------------------------------------------------

    def lst_npings(self, cntfile):
        opts = self.opts
        # list number of pings

        lstnpings_cnt = '''
        dbname:         ../adcpdb/%(dbname)s
        output:           %(dbname)s_npings.txt
        step_size=        1
        year_base=        %(proc_yearbase)d
        time_ranges:
        all

        ''' %opts

        _log.debug(lstnpings_cnt)
        f = open(cntfile, 'w')
        f.write(lstnpings_cnt)
        f.close()

    #--- end lst_npings.py -------------------------------------------


    def lst_hdg(self, cntfile):
        opts = self.opts
        # list heading from cal/rotate; for calculating gps attitude correction

        lsthdg_cnt = '''
        dbname:          ../../adcpdb/%(dbname)s
        output:          scn.hdg
        step_size=        1
        year_base=        %(proc_yearbase)d
        time_ranges:
             all
        ''' %opts

        _log.debug(lsthdg_cnt)
        lhdg = open(cntfile, 'w')
        lhdg.write(lsthdg_cnt)
        lhdg.close()

    #--- end lst_hdg.py -------------------------------------------------------

    def lst_btrk(self, cntfile):
        opts = self.opts
        # Routine to generate a *.btm file using lst_btrk

        btmtrk_cnt = '''
          dbname:     ../../adcpdb/%(dbname)s
          output:     %(dbname)s.btm
          step_size=  1
          year_base=  %(proc_yearbase)s
          time_ranges:
       %(loaded_time_range)s         /* whole time range */

        ''' %opts
        _log.debug(btmtrk_cnt)
        btrk = open(cntfile, 'w')
        btrk.write(btmtrk_cnt)
        btrk.close()

    # --- end lst_btrk -------------------------------------------------------

    def refabsbt(self, cntfile):
        opts = self.opts
        # Routine to run refabsbt on bottom track data
        ref_cnt = '''
           fix_file_type:    simple
           reference_file:   %(dbname)s.btm
           fix_file:         ../../nav/%(fixfilexy)s
           output:           %(dbname)s.ref
           year_base=        %(proc_yearbase)s
           ensemble_length=  %(ens_len)s
           gap_tolerance=    60

     ''' % opts


        _log.debug(ref_cnt)
        ref = open(cntfile, 'w')
        ref.write(ref_cnt)
        ref.close()


    #--- end refabsbt -------------------------------------------------------

    def timslip(self, cntfile):
        opts = self.opts

        opts['ref_l0'] = 1
        opts['ref_l1'] = int((opts['wtrk_step'] - 3) // 2)
        opts['ref_r0'] = opts['ref_l1'] + 3
        opts['ref_r1'] = opts['wtrk_step'] - 1


        tslip_cnt = '''
        fix_file_type:      simple
        fix_file:           ../../nav/%(fixfilexy)s

        reference_file:     ../../nav/%(dbname)s.nav
        output_file:        %(dbname)s_%(wtrk_step)s.cal

        year_base=          %(proc_yearbase)d
        min_n_fixes=        %(wtrk_step)s /* 5 7 9 */

        n_refs=             %(wtrk_step)s /* 5 7 9 */

        i_ref_l0=           %(ref_l0)s
        i_ref_l1=           %(ref_l1)s /* 1 2 3 */
        i_ref_r0=           %(ref_r0)s /* 4 5 6 */
        i_ref_r1=           %(ref_r1)s /* 4 6 8 */

        up_thresh=          3.0        /* m/s */
        down_thresh=        3.0        /* m/s */
        turn_speed=         2.0        /* m/s */
        turn_thresh=        60         /* degrees */

        dtmax=              360        /* seconds, for 300-second ensembles */
        tolerance=          5.e-5      /* days, about 5 seconds */
        grid:               ensemble

        use_shifted_times?  no

     ''' % opts

        opts['timslip_outfile']= '%s_%s.cal' % (opts['dbname'], opts['wtrk_step'])


        _log.debug(tslip_cnt)
        ref = open(cntfile, 'w')
        ref.write(tslip_cnt)
        ref.close()

        del opts['ref_l0']
        del opts['ref_l1']
        del opts['ref_r0']
        del opts['ref_r1']


    #--- end of timslip -------------------------------------------------------
