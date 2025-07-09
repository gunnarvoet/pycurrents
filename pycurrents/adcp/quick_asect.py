"""
Library for quick_adcp.

One class: Q_asect, for generating control files related
to adcpsect.
"""

import os
import logging

from pycurrents.adcp.quick_setup import runcmd, yeslist
from pycurrents.system.yn_query import yn_query

# Standard logging
_log = logging.getLogger(__name__)


class Q_asect:

    # send in default options, return default values for adcpsect subroutines
    # ask is "adcpsect key+word"

    def get_asvars(self):
        opts = self.opts

        ## these are reasonable defaults for nb150
        as_vars = {'dbname'        :    opts['dbname'],
                   'dbpath'        :    '../adcpdb',
                   'outdir'        :    '.',
                   'prefix'        :    'allbins_',
                   'cbasename'     :    'contour',
                   'vbasename'     :    'vector',
                   'timegrid'      :    60,       ## 60 minutes,
                   'loaded_time_range'    :    'all',
                   'firstdepth'    :    opts['firstdepth'],
                   'numbins'       :    opts['numbins'],
                   'ss_string'     :    'separate',
                   'rl_startbin'   :    opts['rl_startbin'],
                   'rl_endbin'     :    opts['rl_endbin'],
                   'proc_yearbase'      :    opts['proc_yearbase'],
                   'pgmin'         :    opts['pgmin']}

                                 #          nb150
                                 #          os150, os75, os38
                                 #          hr50, hr140
                                 #          wh150, wh300, wh600, wh1200
                                 #          bb75, bb150

        if opts['instname']:
            freqstr = opts['instname'][2:]
        else: #defaults for adcpsect extraction
            opts['instname'] = 'os75'
            freqstr = opts['instname'][2:]

        # for contours: by frequency
        increment={}
        increment['38'] = '20'
        increment['75'] = '10'
        increment['50'] = '10'
        increment['45']= '10'
        increment['150'] = '5'
        increment['140'] = '5'
        increment['300'] = '2'
        increment['500'] = '1'
        increment['600'] = '1'
        increment['1200'] = '1'

        gridnum='80'

        # for vectors: by frequency

        firstdepth={}
        firstdepth['38'] = 45
        firstdepth['45'] = 40
        firstdepth['75'] = 30
        firstdepth['150'] = 20
        firstdepth['300'] = 15
        firstdepth['500'] = 10
        firstdepth['600'] = 10
        firstdepth['1200'] = 5

        deeper={}
        deeper['38'] = list(range(100,1650,50))
        deeper['75'] = list(range(50, 800, 25))
        deeper['45'] = deeper['75']
        deeper['50'] = deeper['75']
        deeper['150'] = list(range(50, 400, 25))
        deeper['140'] = deeper['150']
        deeper['300'] = list(range(40,140,20))
        deeper['500'] = list(range(20, 80, 10))
        deeper['600'] = list(range(20, 80, 10))
        deeper['1200'] = list(range(10, 80, 5))


        ## default is reasonable for os75
        if not as_vars['firstdepth']:
            as_vars['firstdepth'] = firstdepth[freqstr]
        as_vars['increment'] = increment[freqstr]
        as_vars['gridnum'] = gridnum
        as_vars['deeper_boundaries'] = deeper[freqstr]

        _log.debug('extracting matlab files for %s' % (opts['sonar']))

        ## top_plotbin wins if chosen; requires codas python extensions
        if opts['top_plotbin']:
            dbpathname = os.path.join('adcpdb',opts['dbname'])
            dirblk = '%sdir.blk' % (dbpathname,)
            if os.path.exists(dirblk):
                from pycurrents.adcp.quick_codas import binmaxdepth
                # set firstdepth using max_plotbin.
                #  NOTE users expect 1-based; codas reader is zero-based
                try:
                    as_vars['firstdepth'] = int(binmaxdepth(dbpathname, opts['top_plotbin']-1))
                except:
                    _log.debug('FAILED to determine top_plotbin. reverting to firstdepth')
            else:
                _log.debug('cannot determine top_plotbin. reverting to firstdepth')

        return as_vars

    # ---  end get_asvars --------------------------------------------


    def timegrid(self, as_vars, cntfile):

        tmgrd_cnt = '''
        output: %(dbname)s.tmg
        time_interval: %(timegrid)s
        time_range: %(loaded_time_range)s
        ''' %as_vars

        if (as_vars['timegrid'] == 0):
            # this is staged here, but never used
            as_vars['ss_string'] = 'single'
            #must use time range at bottom instead of file, don't run timegrid
            as_vars['timegridstring'] = as_vars['loaded_time_range']
            as_vars['run_timegrid'] = 0
        else:
            as_vars['ss_string'] = 'separate'
            #use timegrid file at the bottom, must run timegrid
            as_vars['timegridstring'] = '@%s.tmg' % (as_vars['dbname'])
            run_timegrid = 1

        if run_timegrid:
            fid = open(cntfile, 'w')
            fid.write(tmgrd_cnt)
            fid.close()

    #--- end timegrid -------------------------------------------------------

    def llgrid(self, as_vars, cntfile):             #### not yet implimented
        # make llgrid
        llgrid_cnt = '''

        dbname:        %(dbpath)s
        output:        %(dbname)s.llg
        year_base:     %(proc_yearbase)d
        step_size:     1
        lat_origin:    -0.05   /* center bins */
        lat_increment:  0.10   /* grid by 1/10 degree latitude */
        lon_origin:    -0.05
        lon_increment:  0.10   /* and 1/10 degree longitude */
        time_ranges:
        time_range: %(loaded_time_range)s

     ''' % as_vars

        fid = open(cntfile, 'w')
        fid.write(llgrid_cnt)
        fid.close()

    #--- end llgrid -------------------------------------------------------

    def as_vect(self, as_vars, cntfile):
        #adcpsect for vectors

        as_vars['dbpathname']  = os.path.join(as_vars['dbpath'], as_vars['dbname'])
        as_vars['outpathname'] = os.path.join(as_vars['outdir'], as_vars['vbasename'])

        boundaries = '%s ' % (as_vars['firstdepth'],)
        for val in as_vars['deeper_boundaries']:
            if val > as_vars['firstdepth']:
                boundaries = boundaries + '%d ' % (val,)
        as_vars['deeper_boundaries'] = boundaries
        as_vars['grid_list_number'] = len(as_vars['deeper_boundaries'].split())


        asvect_cnt = '''
        dbname:             %(dbpathname)s
        output:             %(outpathname)s
        step_size:          1        /* must be 1 for navigation */
        ndepth:             %(numbins)d
        time_ranges:        %(ss_string)s
        year_base=          %(proc_yearbase)d

        option_list:
            pg_min=                %(pgmin)s
            reference:             final_ship_ref
            regrid:                average
               depth
               grid_list number=  %(grid_list_number)d
               boundaries:        %(deeper_boundaries)s
                                  /* The 1st boundary must */
                                  /* start at or below the */
                                  /* shallowest depth bin  */
         vector:
           minimum_npts=        2


            ascii:
                    minimum_percent= .50
                    end

          flag_mask:        ALL_BITS
            end
          end                     /* one big time range (if "single") or if "separate", */
     %(gridfilestring)s           /* explicit time ranges or of the form "@gridfile" */

     ''' % as_vars

        # do vector
        fid = open(cntfile, 'w')
        fid.write(asvect_cnt)
        fid.close()

        del as_vars['dbpathname']
        del as_vars['outpathname']

    #--- end as_vec -------------------------------------------------------


    def as_cont(self, as_vars, cntfile):
        #adcpsect for contours

        as_vars['dbpathname']  = os.path.join(as_vars['dbpath'], as_vars['dbname'])
        as_vars['outpathname'] = os.path.join(as_vars['outdir'], as_vars['cbasename'])

        ### need to fix grid number and increment

        ascont_cnt = '''
        dbname:             %(dbpathname)s
        output:             %(outpathname)s
        step_size:          1        /* must be 1 for navigation */
        ndepth:             %(numbins)d
        time_ranges:        %(ss_string)s
        year_base=          %(proc_yearbase)d

        option_list:
            pg_min=                %(pgmin)s
            reference:             final_ship_ref

            regrid:         average
                            depth

                            grid number=    %(gridnum)s
                            origin=         %(firstdepth)s
                            increment=      %(increment)s


            ascii:
                    minimum_percent= .50
                    end

          flag_mask:        ALL_BITS
            end
          end
     %(gridfilestring)s             /* explicit time ranges or of the form "@gridfile" */

     ''' % as_vars

        # do vector
        fid = open(cntfile, 'w')
        fid.write(ascont_cnt)
        fid.close()

        del as_vars['dbpathname']
        del as_vars['outpathname']

    #--- end as_cont -------------------------------------------------------


    def getmat(self, as_vars):

        as_vars['dbpathname']  = os.path.join(as_vars['dbpath'], as_vars['dbname'])

        ### need to fix grid number and increment
        command = \
           '''getmat -qrs -f %(prefix)s %(dbpathname)s ''' % as_vars

        del as_vars['dbpathname']
        del as_vars['prefix']

        return command


    #--- end as_cont -------------------------------------------------------


    ## (18) get matlab files for plotting
    def run_matfiles(self, as_vars):
        opts = self.opts

        _log.debug('step 18: make matlab files for plotting')
        as_vars['loaded_time_range'] = opts['loaded_time_range']  #do all times

        if (opts['auto'] == 1):
            qa_default = 'y'
        else:
            qa_default = 'n'

        qa = yn_query('make matlab files for plotting?', 'ynq',
                      default=qa_default, auto=opts['auto'])
        if qa:
            #force all yn_query answers to be yes

            # go to vector/ directory, make timegrid...
            workdir = 'vector'
            cntfile = opts['dbname'] + '.tmp'
            as_vars['timegrid'] = 60
            pycmd = [self.timegrid, (as_vars, cntfile)]
            syscmd = 'timegrid %s' %  (cntfile)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(), syscmd=syscmd,
                   workdir=workdir)
            as_vars['gridfilestring'] = as_vars['timegridstring']
            # ... run adcpsect to get the vector matlab file
            cntfile = 'as_vect.tmp'
            pycmd = [self.as_vect, (as_vars, cntfile)]
            syscmd = 'adcpsect %s' %  (cntfile)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(), syscmd=syscmd,
                   workdir=workdir)
            _log.debug('done making vector matfiles')

            # go to contour/ directory, make timegrid...
            workdir = 'contour'
            cntfile = opts['dbname'] + '.tmp'
            as_vars['timegrid'] = 15
            pycmd = [self.timegrid, (as_vars, cntfile)]
            syscmd = 'timegrid %s' %  (cntfile)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(), syscmd=syscmd,
                   workdir=workdir)
            as_vars['gridfilestring'] = as_vars['timegridstring']
            # ... run adcpsect to get the vector matlab file
            cntfile = 'as_cont.tmp'
            pycmd = [self.as_cont, (as_vars, cntfile)]
            syscmd = 'adcpsect %s' %  (cntfile)
            runcmd(pq=yeslist(), pycmd=pycmd, sq=yeslist(), syscmd=syscmd,
                   workdir=workdir)

            # go to contour/ to run getmat
            #
            syscmd = self.getmat(as_vars)
            runcmd(pq=yeslist(),  sq=yeslist(), syscmd=syscmd,  workdir=workdir)

            _log.debug('done running getmat with "allbins" ')

    #--- end run_matfiles --------------------------------------------

    ## (19) get netcdf file for plotting
    def run_adcp_nc(self, as_vars):
        opts = self.opts

        _log.debug('step 19: make netcdf file for plotting')

        if (opts['auto'] == 1):
            qa_default = 'y'
        else:
            qa_default = 'n'

        qa = yn_query('make netcdf file?', 'ynq',
                      default=qa_default, auto=opts['auto'])
        if qa:
            #force all yn_query answers to be yes
            workdir = 'contour'
            # go to contour/ directory
            sonar = opts.sonar
            if opts.cruisename:
                cruisename = opts.cruisename
            else:
                _log.exception('not making netCDF file: must specify "--cruisename CRUISENAME"')
            syscmd = f'adcp_nc.py ../adcpdb {sonar} {cruisename} {sonar}'
            if opts.shipname:
                shipname = opts.shipname
                syscmd += f' --ship_name {shipname}'

            runcmd( sq=yeslist(), syscmd=syscmd, workdir=workdir)

            _log.debug('done generating netcdf file ')
            _log.debug('test with "ncdump -h contour/%s.nc"' % (sonar))

    #--- end run_matfiles --------------------------------------------
