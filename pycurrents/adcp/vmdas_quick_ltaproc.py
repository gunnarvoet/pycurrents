'''
automatic processing of LTA data (tries to guess most things)

usage (minimal):


eg:   process LTA data (long term averages)

    vmdas_quick_ltaproc.py --cruisename ZZ1606 data/*LTA


eg:   process LTA data (long term averages)

    vmdas_quick_ltaproc.py --cruisename ZZ1606 data/*LTA


'''
# TODO : add codas_report_generator.py (see below TODO)
# TODO : review multiple text outputs via logging, print, write

import os
import sys
import subprocess
import string
from optparse import OptionParser
import numpy as np
import logging

from pycurrents.system import pathops
from pycurrents.adcp.vmdas import VmdasInfo, guess_sonars, sort_sonars
from pycurrents.adcp.adcp_specs import Sonar
import pycurrents.adcp.uhdas_adcpinfo as uai  # get cals from here

# Standard logging
_log = logging.getLogger(__name__)


def usage():
    ss = '''
    This program creates a root processing directory for a VmDAS dataset.
    The datatype selected ('LTA', 'STA') will be processed in that root directory
        in a location such as      "os75_lta"  or "wh300_sta"
    Watertrack and bottom track calibrations are run, if possible, and a mini-website
        is created with figures from the cruise.
    This is meant as a quick one-step look at LTA or STA data to decide:
         - does the transducer angle change during the dataset?  (eg. operator confusion?)
         - were the LTA files created using a sane heading?
         - are there multiple heading devices?  (for future processing information)
         - does the ADCP work?  (all beams present)
    '''
    return ss

## data_filelist is set below; hardwired
qpy_cnt = '''
    ### q_py.cnt is
    --yearbase ${yearbase}   ## for decimal day conversion
    --cruisename  ${cruisename}   # for titles
    --datatype ${datatype}
    --dbname aship                 # database name; in adcpdb
    --data_filelist      ping/data_filelist.txt # (sorted in time order)
    --sonar ${sonar}        ## sonar (no choice about ping type for LTA)
    --ens_len ${enslen}      ## length in seconds
    ### end of q_py.cnt
'''


class NewCruise:
    '''
    methods to run adcptree.py, generate cntfile
    '''

    def __init__(self, procroot, sonar, yearbase,
                 cruisename=None, enslen=300, datatype='lta',
                 filelist=None, verbose=False, procdir=None):
        '''
        procroot : directory that contains sonar processing dirs
        sonar : (adcptree creates) -- os75nb, os150bb, wh300,...
        yearbase: 2009
        enslen: seconds in average
        cruisename : (used for titles)

        '''
        self.procroot = procroot
        self.sonar = sonar
        self.enslen = enslen
        self.datatype=datatype
        if procdir is None:
            self.procdir =  '%s_%s' % (sonar, datatype)
        else:
            self.procdir = procdir
        self.path_procdir = os.path.join(self.procroot, self.procdir)
        self.verbose = verbose

        if not os.path.isdir(procroot):
            print('%s does not exist. making directory' % procroot)
            os.mkdir(procroot)

        if os.path.isdir(self.path_procdir):
            print('processing directory %s already exists' % self.path_procdir)
            self.made_new = False
        else:
            self.run_adcptree(sonar) # sets self.made_new
            if cruisename is None:
                cruisename = sonar

            s=string.Template(qpy_cnt)
            h=s.substitute(yearbase=yearbase,
                           cruisename=cruisename,
                           datatype=datatype.upper(),
                           sonar=sonar,
                           enslen=enslen)
            cntfile = os.path.join(self.path_procdir,'q_py.cnt')
            with open(cntfile,'w') as file:
                file.write(h)
            print('wrote %s' % cntfile)

            # write full file names so quick can find them
            fullpathlist = []
            for f in filelist:
                fullpathlist.append(os.path.realpath(f))
            sorted_filelist_file = os.path.join(
                self.path_procdir, 'ping', 'data_filelist.txt')
            with open(sorted_filelist_file, 'w') as file:
                file.write('\n'.join(fullpathlist)+'\n')


    def run_adcptree(self, sonar):
        '''run adcptree
        '''
        dest=self.path_procdir
        cmd = 'adcptree.py %s --datatype %s' % (dest, self.datatype.lower())
        status,output=subprocess.getstatusoutput(cmd)
        if self.verbose:
            print('adcptree: status = ', status)
            print('adcptree: output = ', output)
        if status == 0:
            print('adcptree created %s' % dest)
            self.made_new = True
        else:
            self.made_new = False
            raise IOError('FAILED adcptree\n' + output)

        if not os.path.isdir(dest):
            print('adcptree: status = ', status)
            print('adcptree: output = ', output)
            self.made_new = False
            raise ValueError('adcptree did not actually work')

btcal_keys = ('edited','median','amplitude','phase')
wtcal_keys = ('edited','amplitude','phase','nav','median')

def catcals(outfile='cals.txt'):
    clines=[]
    wtfile='cal/watertrk/adcpcal.out'
    btfile='cal/botmtrk/btcaluv.out'
    #
    # tack on the last watertrack record
    if os.path.exists(wtfile):
        with open(wtfile, 'r') as newreadf:
            lines = newreadf.readlines()
        wlines = []
        for line in lines[::-1]:
            wlines.append(line)
            if 'watertrack' in line:
                break
        if len(wlines) < 15: #no watertrack cals
            clines.append('no watertrack cals')
        else:
            clines.append('**WATERTRACK**\n---------------------------')
            for line in wlines[::-1]:
                for ww in wtcal_keys:
                    if ww in line and '=' not in line and 'nav' not in line:
                        clines.append(line.rstrip())
        clines.append('\n')
    # tack on the last bottom record
    if os.path.exists(btfile):
        with open(btfile,'r') as newreadf:
            lines=newreadf.readlines()
        blines=[]
        for line in lines[::-1]:
            blines.append(line)
            if 'bottomtrack' in line:
                break
        if len(blines) < 10: #no bottomtrack cals
            clines.append('no bottomtrack cals')
        else:
            clines.append('**BOTTOMTRACK**\n---------------------------')
            for line in blines[::-1]:
                for ww in btcal_keys:
                    if ww in line:
                        clines.append(line.rstrip())
        clines.append('\n')
    with open(outfile,'w') as file:
        file.writelines('\n'.join(clines))
    print('wrote %s' % outfile)



def test_filelist(filelist):
    '''
    return directory and suffix if that can be done, fail otherwise
    '''
    suffixes = []
    for f in filelist:
        path, fname = os.path.split(f)
        base, ext = os.path.splitext(fname)
        suffix = ext[1:]
        if suffix not in suffixes and len(suffix)>0:
            suffixes.append(suffix)

    if len(suffixes) == 1:
        return suffixes[0]
    if len(suffixes) > 1:
        print('multiple suffixes found.  try again', suffixes)
        sys.exit()
    if len(suffixes) == 0:
        print('nosuffixes found.  try again')
        sys.exit()


def main():

    parser = OptionParser(__doc__)

    parser.add_option("-c", "--cruisename", dest="cruisename",
                      default = None,
                      help="cruisename for titles and folder for processing")

    parser.add_option("-s", "--sonar", dest="sonar",
                      default = None,
                      help="(optional) sonar (eg. os75, wh300, bb75")

    parser.add_option("-p", "--procdir", dest="procdir",
                      default = None,
                      help="ADCP processing directory (default is sonar_filetype)")

    parser.add_option("-r", "--procroot", dest="procroot",
                      default=None,
                      help="Root processing directory (default is cruisename_proc)")

    parser.add_option("-v", "--verbose", dest="verbose",
                      default = False, action='store_true',
                      help="output additional messages to screen")

    parser.add_option("-y", "--yearbase", dest="yearbase",
                      default = None,
                      help="(optional) yearbase, it it cannot be deduced")

    parser.add_option("--force", dest="force",
                      default = False, action="store_true",
                      help="if multiple EA or multiple ensemble lengths, process anyway (otherwise abort)")

    (options, args) = parser.parse_args()  #args=sys.argv
    loglist = []  # store strings until we have a logfile

    filelist = pathops.make_filelist(args, allow_empty=True)
    suffix = test_filelist(filelist)

    if not options.cruisename:
        cruisename = 'VmDAS ADCP cruise'
    else:
        cruisename = options.cruisename
    cruisename_filestring = '_'.join(cruisename.split())
    intro_line = '\nusing cruisename "%s"' % (
        cruisename_filestring)
    print(intro_line)
    loglist.append(intro_line)

    lstr = ""
    if suffix.upper() not in ('LTA', 'STA'):
        print(__doc__)
        print('This program only works with STA or LTA data')
        sys.exit()

    if options.yearbase:
        lstr = '- will use %s for yearbase' % options.yearbase
        print(lstr)
        loglist.append(lstr)
    else:
        lstr = '- will deduce yearbase'
        print(lstr)
        loglist.append(lstr)

    lstr = '- if there are multiple EA or multiple ensemble time durations:'
    print(lstr)
    loglist.append(lstr)

    if options.force:
        lstr = '   "--force": ...  will proceed anyway '
        print(lstr)
        loglist.append(lstr)
    else:
        lstr = '   - will stop.  use "--force" to override'
        print(lstr)
        loglist.append(lstr)

    if options.procdir:
        procdir = options.procdir
        procpath = os.path.join(cruisename_filestring, procdir)
        lstr = 'processing will take place in %s' % procpath
        print(lstr)
        loglist.append(lstr)
    else:
        procdir = '%s_%s' % ('SONAR', suffix)
        procpath = os.path.join(cruisename_filestring, procdir)
        lstr = 'processing will take place  %s' % procpath
        print(lstr)
        loglist.append(lstr)
        lstr = '... where "SONAR" is determined as follows:'
        print(lstr)
        loglist.append(lstr)

    if options.sonar:
        lstr = '- will use %s for sonar designation' % options.sonar
        print(lstr)
        loglist.append(lstr)
    else:
        lstr = '- will deduce sonar'
        print(lstr)
        loglist.append(lstr)

    sonar_list = []
    if options.sonar is None:
        instping_tuplist = guess_sonars(filelist) # all
        sonar_info = sort_sonars(instping_tuplist)
        # sanity check
        if len(sonar_info.instruments.keys()) > 1:
            print('ERROR: multiple instruments found in dataset.  just do one')
            print(str(instping_tuplist))
            sys.exit()
        ## eg different ping types: 'bb' and 'nb'

        if len(sonar_info.sonars.keys()) == 1:
            sonar = list(sonar_info.sonars.keys())[0]
            lstr = '  found sonar %s' % (sonar)
            print(lstr)
            loglist.append(lstr)
            sonar_list = [sonar]
        else:
            maxpings = 0
            sonar = ''
            sonarkeys = list(sonar_info.sonars.keys())
            sonarkeys.sort()  # get 'bb' first
            for sonarname in sonarkeys:
                if sonar_info.sonars[sonarname] >= maxpings:
                    maxpings = sonar_info.sonars[sonarname]
                    sonar = sonarname
                    sonar_list.append(sonar)
            lstr = 'mixed pings in original dataset:\n' + str(sonar_info.sonars)
            print(lstr)
            loglist.append(lstr)
            lstr = 'guessing gridding (plots) based on %s' % sonar
            print(lstr)
            loglist.append(lstr)
    else:
        sonar_list = [options.sonar]

    # Quick fix for Ticket 2501
    # Sort files per sonar's ping-type
    file_dict = {}
    for sonar in sonar_list:
        file_dict[sonar] = []
        sonar_specs = Sonar(sonar)
        for f in filelist:
            pingtypes = list(guess_sonars(f)[0][1].keys())
            for pingtype in pingtypes:
                if pingtype in sonar_specs.pingtype:  # look for ping-type match
                    file_dict[sonar].append(f)
        file_dict[sonar] = list(set(file_dict[sonar]))  # remove duplicates
    #
    if options.procroot:
        procroot = options.procroot
    else:
        procroot = '%s_proc' % (cruisename_filestring)
    if not os.path.isdir(procroot):
        print('%s does not exist. making directory' % procroot)
        os.mkdir(procroot)

    for sonar in sonar_list:
        print("  Sonar: ", sonar)
        infofile = '%s_%s_%s_info.txt' % (cruisename_filestring, sonar, suffix)
        proc_logfile = '%s_%s_%s_proc.txt' % (cruisename_filestring, sonar, suffix)
        proc_logfile_path = os.path.join(procroot, proc_logfile)

        if file_dict[sonar]:
            vm = VmdasInfo(file_dict[sonar], model=sonar[:2])
        else:  # Sanity check
            print("---WARNING: No file matching the ping-type of %s were found---" % sonar)
            continue

        if infofile is not None:
            print('Writing additional information to logfile %s:' % infofile)
        lstr = '- determining summary information about %s data files' % suffix
        print(lstr)
        loglist.append(lstr)

        proc_log = open(proc_logfile_path, 'a', encoding='utf-8', errors='ignore')
        _log.debug("proc_logfile_path: " + proc_logfile_path)

        outfile_path = os.path.join(procroot, infofile)

        lstr = '- sorting files in time order'
        print(lstr)  # ; log.info(lstr)
        proc_log.write(lstr + '\n')
        vm.sort_bytime(outfile=outfile_path)

        lstr = 'Determining summary information about data files'
        print(lstr)  # ; log.info(lstr)
        proc_log.write(lstr + '\n')
        vm.print_scan(outfile=outfile_path)

        lstr = '- guessing instrument model'
        print(lstr)  # ; log.info(lstr)
        proc_log.write(lstr + '\n')
        model = vm.get_instrument(outfile=outfile_path)

        lstr = '- about to guess EA from raw data files...'
        print(lstr)  # ; log.info(lstr)
        proc_log.write(lstr + '\n')
        EA_angles = vm.get_beaminst_info(outfile=outfile_path)

        lstr = '- determining ensemble length from %s files' % suffix
        print(lstr)  # ; log.info(lstr)
        proc_log.write(lstr + '\n')
        enslen = vm.get_enslen(outfile=outfile_path)

        lstr = '- guessing additional information for single-ping processing)'
        print(lstr)  # ; log.info(lstr)
        proc_log.write(lstr + '\n')
        vm.get_badfile_info(outfile=outfile_path)

        lstr = '- guessing heading source'
        print(lstr)  # ; log.info(lstr)
        proc_log.write(lstr + '\n')
        vm.guess_heading_source_lta(outfile=outfile_path)

        lstr = '- trying to determine serial NMEA messages'
        print(lstr)  # ; log.info(lstr)
        proc_log.write(lstr + '\n')
        vm.guess_serial_msg_types(outfile=outfile_path)

        if options.verbose:
            infofile_parts = os.path.splitext(infofile)
            long_infofile = infofile_parts[0] + '_long' + infofile_parts[1]
            long_infofile_path = os.path.join(procroot, long_infofile)
            vm.print_meta(long_infofile_path)
            lstr = 'wrote more metadata to %s' % long_infofile_path
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            vm.print_meta(long_infofile)

        if len(model) != 1:
            print(__doc__)
            print('cannot determine model uniquely')
            print('look at %s for more clues' % infofile)
            print('use "--verbose" for even more information')
            sys.exit()
        else:
            model = model[0]

        if len(EA_angles) > 1:
            if not options.force:
                print('multiple EA angles during this cruise.')
                print('to process LTA (or STA) anyway, use "--force"')
                sys.exit()

        if len(enslen) > 1:
            if options.force:
                lstr = 'WARNING: multiple ensemble durations.'
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                lstr = enslen.__str__()
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                enslen = int(np.floor(np.median(np.array(enslen))))
                lstr = 'using ensemble length: using %dsec' % enslen
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
            else:
                print(__doc__)
                print('to process LTA (or STA) anyway, use "--force"')
                print('better suggestion: process using single-ping tools')
                sys.exit()
        else:
            enslen = int(np.floor(enslen)) -1 #
            lstr = 'found one consistent ensemble length: using %dsec' % enslen
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

        yearbase=0
        for fname in vm.filelist_timesorted:
            try:
                yearbase = vm.infodicts[fname]['yearbase']
            except Exception:  # If vm.infodicts is sure to exist, this could be KeyError.
                lstr = 'cannot get yearbase from %s' % fname
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
            if yearbase > 0:
                break

        if yearbase == 0:
            if options.yearbase is None:
                print(__doc__)
                lstr = 'ERROR: must specify yearbase'
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                sys.exit()
            else:
                yearbase = int(options.yearbase)

        nc = NewCruise(procroot, sonar, yearbase,
                       datatype=suffix, procdir=options.procdir,
                       cruisename=cruisename_filestring, enslen=enslen,
                       filelist=vm.filelist_timesorted)

        if nc.made_new:
            startdir=os.getcwd()

            # run quick
            cmd = 'quick_adcp.py --cntfile q_py.cnt --auto  '
            lstr = 'running: %s' % cmd
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

            os.chdir(nc.path_procdir)
            status,output=subprocess.getstatusoutput(cmd)
            if status != 0:
                raise IOError(output)
            else:
                lstr = 'done with quick_adcp.py'
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                #catcals()
                btstr, wtstr = uai.check_cals('./','')
                xystr = uai.check_dxdy('./','')
                calstr = '\n'.join([btstr,
                                    '',
                                    wtstr,
                                    '-------------\n',
                                    xystr,
                                    '-------------------\n'])
                with open('cals.txt', 'w') as file:
                    file.write(calstr)
                os.chdir(startdir)

            #make figs
            cmd = 'quick_web.py --step 2 --ddrange 2 --auto'

            # TODO (1) make webpy in reports dir
            # cmd =  'quick_web.py --step 2 --ddrange 2 --auto --reports  --cruisename %s'  % (cruisename)


            os.chdir(nc.path_procdir)
            try:
                status,output=subprocess.getstatusoutput(cmd)
                if status:
                    print(cmd)
                    print('FAILED to make web page')
                    print(output)
                    # TODO : don't we want to raise an exception here?
                lstr = '\n\nMaking web site with figures using "quick_web.py"'
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                webpydir = os.path.join(nc.path_procdir, 'webpy', 'index.html')
                # This is needed later, so if an exception is raised, this
                # needs to be defined before that occurs. (?)
            except Exception:
                lstr = 'could not finish web plots'
                _log.exception(lstr)
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                lstr = 'try running manually from %s with:' % nc.path_procdir
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                print(cmd)  # ; log.info(cmd)
                proc_log.write(cmd + '\n')

            try:
                from pycurrents.adcp.adcp_nc import make_nc_short
                from pycurrents.adcp.adcp_nc import CODAS_short_variables
                lstr = '\nnetCDF files:'
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                lstr = '-------------:'
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr)
                nc_filename = os.path.join('contour', sonar+'.nc')
                make_nc_short('adcpdb/aship', nc_filename, cruisename_filestring,
                                  sonar, None)
                lstr = '- made short netCDF file %s' % nc_filename
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                nc_vars = os.path.join('contour', 'CODAS_netcfd_variables.txt')
                with open(nc_vars, 'w') as file:
                    file.write(CODAS_short_variables)
                lstr = '- netCDF variables are defined in %s' % nc_vars
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')
                #
                nc_docs = os.path.join('contour', 'CODAS_processing_note.txt')
                with open(nc_docs, 'w') as file:
                    file.write(CODAS_short_variables)
                lstr = '- CODAS processing described in %s' % nc_docs
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')

            except Exception:
                lstr = '(could not make netCDF files)'
                _log.exception(lstr)
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')

            # leave ADCP processing directory
            os.chdir(startdir)
            # now we are back in the root directory

            lstr = 'DONE.\n==================================================='
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

            ## tack on a summary to the top of cals.txt
            summary = [
                'Processed %d %s %s files with %dsec ensemble length\n\n' % (
                    len(vm.filelist), sonar, suffix, enslen), ]
            cals_txt = os.path.join(nc.path_procdir, 'cals.txt')
            with open(cals_txt,'r') as newreadf:
                caltxt_lines = newreadf.readlines()
            newlines = summary + caltxt_lines
            lstr = ''.join(newlines)
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            with open(cals_txt,'w') as file:
                file.write(lstr)

            #-------------------------------------------------------
            # tell where important files are:
            lstr = '============'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '=== Data ==='
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr)
            lstr = '============\n'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '- vmdas_info data summary is in this file:\n %40s\n' % (
                infofile)
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            if options.verbose:
                lstr = '- detailed file-by-file information is here: %40s\n' % (
                     long_infofile)
                print(lstr)  # ; log.info(lstr)
                proc_log.write(lstr + '\n')

            #-------------------------------------------------------
            lstr = '================'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '== Processing =='
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '================\n'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '- Summary processing information is in this file:'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '        %s' % (os.path.join(nc.path_procdir, 'cruise_info.txt'))
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '\n- Calibrations (also shown above) are summarized in:'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '        %s' % (cals_txt)
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

            #-------------------------------------------------------
            lstr = '\n==============='
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '=== Figures ==='
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '===============\n'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

            lstr = '\nTo view all figures generated during processing,'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '        figview.py %s' % nc.path_procdir
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = 'run this command:'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')


            lstr = '\nTo explore the dataset, run this command:'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '        dataviewer.py %s' % nc.path_procdir
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

            lstr = '\nTo look at the web plots, in a web browser'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '    open %s \n' % webpydir
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

            #-------------------------------------------------------
            lstr = '======================'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '=== Postprocessing ==='
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '=====================\n'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

            lstr = 'all postprocessing occurs in %s; change directories first' % (
                nc.path_procdir)
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '\n      cd  %s\n' % nc.path_procdir
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')


            lstr = 'If warranted, apply a rotation calibration using mean or median'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = 'of watertrack or bottom track calibration values.  If mean and'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = 'median agreed at 0.5deg, apply as follows, using 0.5 for XXX:\n'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '     quick_adcp.py --steps2rerun '
            procstr = 'rotate:navsteps:calib --rotate_angle XXX --auto\n'
            print(lstr + procstr)  # ; log.info(lstr + procstr)
            proc_log.write(lstr + procstr + '\n')


            lstr = '\nAfter rotation and editing, to remake the netCDF file:'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '\n     adcp_nc.py %s %s %s %s' % ('adcpdb/aship', nc_filename,
                                           cruisename_filestring, sonar)
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

            lstr = '\n\nAfter rotation and editing, to remake the webpy web site:'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')
            lstr = '\n    quick_web.py --redo'
            print(lstr)  # ; log.info(lstr)
            proc_log.write(lstr + '\n')

            lstr = '\n\n  These notes are written in this file: %s' % (
                proc_logfile_path)
            print(lstr)



            # TODO (2) make the codas reports directory; document its existence
            #--------
#            ## reports
#            cmd =  'codas_report_generator.py -p %s -t %s  -c %s'  % (
#                nc.path_procdir, infofile, cruisename)
#
#            try:
#                status,output=subprocess.getstatusoutput(cmd)
#                if status:
#                    print(cmd)
#                    print('FAILED to make reports')
#                    print(output)
#                lstr = '\n\nMaking reports directory with "codas_report_generator.py"'
#                print(lstr)  # ; log.info(lstr)
#                proc_log.write(lstr + '\n')
#                reportsdir = os.path.join(nc.path_procdir, 'reports', 'index.html')
#            except:
#                lstr = 'could not finish reports directory'
#                print(lstr)  # ; log.info(lstr)
#                proc_log.write(lstr + '\n')
#                lstr = 'try running manually from %s with:' % nc.path_procdir
#                print(lstr)  # ; log.info(lstr)
#                proc_log.write(lstr + '\n')
#                print(cmd)  # ; log.info(lstr)
#                proc_log.write(cmd + '\n')
#

            proc_log.close()
