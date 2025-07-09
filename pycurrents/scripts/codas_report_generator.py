#!/usr/bin/env python
'''
populate a web page with information about an ADCP dataset processed with CODAS

typical usage:

      codas_report_generator.py -p procdir

      # vmdas LTA data example:
      codas_report_generator.py -t lta_info.txt -p os75nb

      # single-ping processing example:
      codas_report_generator.py -p os75nb os75nb/q_py.cnt os75nb/dbinfo.txt


This program is meant to assemble useful information for a CODAS
processing directory, whether

- creates a 'reports' directory (by default) within the codas processing dir,
- fills with what it can find, selecting from
         - nav plot, plot of database time range
         - settings summary (ancillary instruments used) if possible
         - cals (expanded)
         - webpy (assumed to be inside the reports directory)
         - optional text file (specified -- contents in web page)
         - other text files (links only) -- comes from args

Path notes:
  (1) If you override the 'reports' directory location, you are specifying
      a full path to the new name (it will not default to being procdir/reports)
  (2) text files:
         - The one text file specified has text shown in the index.html page
         - The argument list is a collection of text files that can be
           added to the reports directory (copied in, links provided in index.html)
  (3) settings summary:
         - if a vmdas_info.py output file is specified, guess from that
         - if a config/*proc.py file exists, guess from that

'''
## TODO
## colon-delimited list of plots2run (by option)



import logging
from pycurrents.system import logutils

from pycurrents.system import Bunch
import numpy as np
import os
import time
import glob
import shutil
from optparse import OptionParser

from pycurrents.adcp.uhdas_report import CODAS_ProcInfo, ReportActions
from pycurrents.adcp.uhdas_report import  HTML_page
from pycurrents.plot.mpltools import nowstr
from pycurrents.system.misc import safe_makedirs


alt_text = Bunch()
# category.name = (output type, comment)
alt_text.navplot         = ('png',  'cruise track over topography')
alt_text.db_timerange    = ('png',
       'plot of sonar usage with time, labeled by instrument and ping type')
alt_text.settings_summary   = ('ascii', 'summary of settings and cals')
alt_text.adcp_cals       = ('ascii',
        'report ADCP processing calibration values')
alt_text.webpy     = ('png',    'webpy')
## if these exist, try to add them

catlist = ['overview', 'processed ADCP', 'quality']
names2run = ['navplot', 'db_timerange', 'settings_summary', 'adcp_cals', 'webpy']


def get_namestr():
    lines = []
    for plotname in names2run:
        filetype, txt =  alt_text[plotname]
        lines.append('%20s : %7s : %s' % (plotname, filetype, txt))
    namestr = '.\n'.join(lines)
    return namestr

if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option('-v', '--verbose',
                        default=False,
                        action='store_true',
                        help='verbose: print status of web page generation')

    parser.add_option('--log',
                        default=None,
                        help='logfile name (replacing stdout)')

    parser.add_option('--testing',
                        action='store_true',
                        default=False,
                        help='testing: show commands, do not run anything')

    parser.add_option('-i', '--remake_index',
                        action='store_true',
                        default=False,
                        help='remake index.html but do not do anything else')

    parser.add_option('-c', '--cruisename',
                        default=None,
                        help='cruisename, for titles')

    parser.add_option('-r', '--report_dir',
                        default=None,
                    help='put reports here: default is subdirectory "reports"'),

    parser.add_option('-p', '--procdir',
                        default=None,
                    help='required: codas processing directory to evaluate'),

    parser.add_option('-t', '--textfile',
                        default=None,
                        help='info file (eg. vmdas_info.py output)'),

    parser.add_option('-T', '--thumbnailsize',
                      default='250',
                      help='thumbnail: number of pixels (default=250 (small)) ')

    options, args = parser.parse_args()
    verbose = options.verbose

    _log = logging.getLogger()
    if verbose:
        _log.setLevel(logging.DEBUG)
    else:
        _log.setLevel(logging.INFO)

    if options.log is None:
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(options.log)
        formatter = logutils.formatterTLM
        handler.setFormatter(formatter)

    _log.addHandler(handler)

    _log.debug('Starting codas_report_generator.py')

    if options.procdir is None:
        raise IOError('must set procdir')
    procdirpath = options.procdir
    procdirbase = os.path.basename(procdirpath)

    txtfiles = args   # txtfiles to add to reports

    # test procdir
    if not os.path.exists(procdirpath):
        raise IOError('processing directory %s does not exist' % (procdirpath))
    infostr = 'found processing directory %s' % (procdirpath)
    _log.debug(infostr)

    infostr = '\n--> environment and path info for debugging:\n '
    _log.debug(infostr)

    if options.cruisename is None:
        cruisename = procdirbase
    else:
        cruisename = options.cruisename

    run_cmd = True
    if options.testing or options.remake_index:
        run_cmd = False

    if run_cmd:
        options.remake_index=True

    if options.report_dir is None:
        report_dir = os.path.join(procdirpath, 'reports')
    else:
        report_dir = options.report_dir

    if run_cmd:
        if not os.path.exists(report_dir):
            safe_makedirs(report_dir)
            infostr = 'making report directory "%s"' % (report_dir)
            _log.debug(infostr)
        else:
            infostr = 'updating report directory %s' % (report_dir)
            _log.debug(infostr)

        _log.info('cruisename is <%s>', cruisename)
        _log.info('procdirpath is <%s>', procdirpath)
        _log.info('procdir name is <%s>', procdirbase)
        _log.info('report_dir is <%s>', report_dir)

        # discovery: get "sonar" name
        globstr = '%s/webpy/*_overview.png' % (report_dir)
        webpy_overview = glob.glob(globstr)
        if len(webpy_overview) == 0:
            sonarname = 'ADCP'
        elif len(webpy_overview) == 1: # should be the case
            sonarname = os.path.basename(webpy_overview[0]).split('_')[0]
        else:
            errstr =  '\n'.join(webpy_overview)
            _log.error('multiple overview files in webpy: %s' % (errstr))
        _log.debug('sonar is %s' % (sonarname))

        # copy info file into reports dir
        # could be relative or absolute
        # on the assumption that a text file is adjacent to the procdir
        if options.textfile:
            infofile_list = [options.textfile,]
        else:
            infofile_list = glob.glob('%s/*%s*info*.txt' % (procdirpath,
                                                            procdirbase))
            if len(infofile_list) == 0:
                infofile_list = glob.glob('%s/*info*.txt' % (procdirpath))
                if len(infofile_list) == 0:
                    _log.info('could not find info file')
        for fname in infofile_list:
            shutil.copy(fname, report_dir)
            _log.info('copying %s into reports dir' % (os.path.basename(fname)))

        ## this is presently managed manually. see above
        _log.debug(get_namestr())

    HP = HTML_page(options.cruisename, report_dir=report_dir, catlist=catlist)

    # namelist = type of plot
    # cmdlist = commands to run
    # celldict:  key=category, value = list of tuples (one per row)
    #   tuple = ('link',     [cat, link,     filenametext]  # link is 'as is'
    #   tuple = ('contents', [cat, filename, filenametext]  # filename must be read
    # - append to namelist
    # - append to cmdlist
    # - add to celldict tups
    namelist=[]
    cmdlist  = []
    celldict  = Bunch()      # table1
    report_log_list = ["===== %s =====" % (nowstr()),]
    stderr_log_list = []
    for cat in HP.catlist:
        celldict[cat]=[]
    removal_list = []  #files to remove


    ## copy processing and logging configurations
    CPI = CODAS_ProcInfo(procdirpath, verbose=verbose, debug=False)
    RA = ReportActions(report_dir=report_dir, runnit=run_cmd, verbose=verbose)


    link_targets = []
    rtextlist = []
    cat = "overview"
    name = 'navplot'
    _log.debug('about to set up navplot section and sonar usage')
    if name in names2run:
        rfile =  'nav_plot_all'
        ## this now makes 2 plots:  nav_plot_all_topo.png and nav_plot_all_txy
        strtmp = 'plot_gpsnav.py --noshow  --title %s --outfilebase %%s  %s' % (
                options.cruisename, CPI.procdir)
        cmd = RA.make_cmd(strtmp, rfile)  # report_dir gets prefixed to rfile
        cmdlist.append(cmd)
        namelist.append(name)
        _log.debug(cmd)

        for suffix in ['_topo', '_txy']:
            rtextlist.append('cruise track (where ADCP was run)')
            link_targets.append(rfile+suffix)
            if run_cmd:
                removal_list.append(os.path.join(
                     CPI.procdir, report_dir, rfile+suffix+'.png'))

    #-------------
    name = 'db_timerange'
    if name in names2run:
        ## list sonar usage
        rfile = 'db_timerange'
        rtextlist.append('plot when each sonar was run')
        outfile = os.path.join(CPI.procdir, report_dir, rfile+".png")
        strtmp = 'plot_db_timeranges.py  --outfile %%s --noshow  %s' % (CPI.procdir)
        if run_cmd:
            removal_list.append(os.path.join(
                CPI.procdir, report_dir, rfile+'.png'))
        cmd=RA.make_cmd(strtmp, rfile+".png")
        cmdlist.append(cmd)
        namelist.append(name)
        _log.debug(cmd)
        link_targets.append(rfile)
    if len(link_targets) > 0:
        plot_entry = [] # two plots in the cell
        text_entry = [] # two names to describe
        for index_lt in range(len(link_targets)):
            link_target = link_targets[index_lt]
            plot_entry.append(HP.make_plot_html0(link_target, link_target+'.png',
                                                 alt_text=rtextlist[index_lt]))
            plot_entry.append(HP.space)
            text_entry.append(link_target+".png" + HP.newline)
            if run_cmd:
                tcmd = HP.thumbnail_cmd(os.path.join(report_dir, link_target), tpix=int(options.thumbnailsize)) #return command
                cmdlist.append(tcmd)
                namelist.append(name)
                _log.debug(tcmd)
        row = HP.make_table_row([cat, ' '.join(plot_entry), ' '.join(text_entry)])
        celldict[cat].append(('link',row))


    #----------------------
    # must make ADCP_cals.txt before settings_summary.txt; put link in after
    # ONLY make the file now
    name = 'adcp_cals'
    _log.debug('about to set up %s section', name)
    if name in names2run:
        namelist.append(name)
        ## show ADCP calibrations from processing
        rfile = 'ADCP_cals.txt'
        rtext = 'heading and scale factor calibrations'
        outfile = os.path.join(report_dir, rfile)
        strtmp = 'codas_check_cals.py --outfile %%s --sonar %s %s ' % (
                                                   procdirbase, CPI.procdir)
        if run_cmd:
            removal_list.append(os.path.join(report_dir, rfile))
        cmd = RA.make_cmd(strtmp, rfile)
        cmdlist.append(cmd)
        _log.debug(cmd)

    #----------------
    cat = "processed ADCP"
    name = 'webpy'
    _log.debug('about to set up %s section' % (name))
    if name in names2run:
        webdir = os.path.join(report_dir, 'webpy')
        if os.path.exists(webdir):
            namelist.append(name)
            # now we have it, we need the relative path
            rfile = 'webpy/index.html'
            rtext = '%s ADCP web page' % (procdirbase)
            shutil.copy(os.path.join(webdir, 'ADCP_vectoverview.png'), report_dir)
            tfile = 'ADCP_vectoverview'
            tsrc = tfile
            tcmd = HP.thumbnail_cmd(os.path.join(report_dir, tfile),
                                tpix=int(options.thumbnailsize)) #return command
            cmdlist.append(tcmd)
            _log.debug(cmd)
            ## show thumbnail, click = index <====
            link_target=os.path.join('../webpy/index.html')
            entry = HP.make_plot_html0( tfile, link_target, alt_text=rtext)
            row = HP.make_table_row([cat, entry, rfile])
            celldict[cat].append(('link',row))


    #-------------------
    name='settings_summary'
    cat = 'quality'
    _log.debug('about to set up %s section', name)
    if name in names2run:
        ## text file with warnings about VmDAS
        rfile = 'settings_summary.txt'
        rtext = 'calibration and settings summary'
        testlist = ['instrument frequency',
                    'beam angle',
                    '(EA)',
                    'ensemble length =']
        outfile = os.path.join(report_dir, rfile)
        if options.textfile:
            filelist= [options.textfile,] + args
        else:
            filelist = args

        _log.debug('outfile is %s' % (outfile))

        slist=[]
        slist.append('-- settings --\n')
        for f in filelist:
            with open(f,'r') as newreadf:
                fstr = newreadf.read()
            if '(EA)' in fstr or ' EA ' in fstr:  ## VmDAS
                lines = fstr.split('\n')
                for line in lines:
                    for t in testlist:
                        if t in line:
                            slist.append(line)
        slist.append('\n-- available calibrations --\n')
        calfile = os.path.join(report_dir, 'ADCP_cals.txt')
        if os.path.exists(calfile):
            with open(calfile,'r') as newreadf:
                lines = newreadf.readlines()
            wtcal_list = []
            num_wtedited = 0
            btcal_list = []
            num_btedited = 0
            xducer_list=[]
            signal = 0
            for line in lines:
                parts = line.split()
                if 'WT' in parts:
                    if 'edited' in parts:
                        num_wtedited = int(parts[7])
                        wtcal_list.append(line.rstrip())
                    if 'median' in parts or 'phase' in parts:
                        wtcal_list.append(line.rstrip())

                if 'BT' in parts:
                    if 'edited:' in parts:
                        btcal_list.append(line.rstrip())
                        num_btedited = int(parts[4])
                    if 'median' in parts or 'phase' in parts:
                        btcal_list.append(line.rstrip())

                if 'xducer_dx' in parts or 'xducer_dy' in parts:
                    xducer_list.append(line.rstrip())
                if 'signal' in parts:
                    xducer_list.append(line.rstrip())
                    signal = float(xducer_list[-1].split()[-1])


            if num_wtedited > 10:
                slist.extend(wtcal_list)
                slist.append('')
            if num_btedited > 10:
                slist.extend(btcal_list)
                slist.append('')

            if signal > 1000:
                slist.extend(xducer_list)
                slist.append('')

        with open(outfile,'w') as file:
            file.write('\n'.join(slist) + '\n')
        action='contents'
        fname=os.path.join(report_dir, rfile)
        row =  [cat, fname, rfile]
        celldict[cat].append((action,row))


#    #-----------------------
#    # not in names2run
#    name = 'data_overview'  # uhdas_info.py --overview
#    if name in names2run:
#        ## logging summary
#        rfile = infofile_list[0]
#        rtext = "overview of data contents and settings"
#        cat = "overview"
#        action = 'contents'
#        fname=os.path.join(report_dir, rfile)
#        row =  [cat, fname, rfile]
#        celldict[cat].append((action,row))
#
#        if run_cmd:
#            removal_list.append(os.path.join(report_dir, rfile))
#        cmd = RA.make_cmd(strtmp, rfile)
#        cmdlist.append(cmd)
#        LF.debug(cmd)
#        namelist.append(name)


    #----------------------
    # must make ADCP_cals.txt before settings_summary.txt; put link in after
    name = 'adcp_cals'
    cat = 'quality'
    _log.debug('making link for  %s section', name)
    ## show ADCP calibrations from processing
    rfile = 'ADCP_cals.txt'
    rtext = 'heading and scale factor calibrations'
    action = 'link'
    link_target = rfile
    entry = HP.make_html_entry(rfile, rfile)
    row = HP.make_table_row([cat, entry, ''])
    celldict[cat].append(('link',row))

   #--------------------------------------------
    ## make links for other files
    cat = 'quality'
    name = 'other text files'
    for fpath in filelist:
        rfile = os.path.basename(fpath)
        rtext = rfile
        fname=os.path.join(report_dir, rfile+'.txt') # so browser can read it
        shutil.copy(fpath, fname)
        action = 'link'
        link_target=rfile
        entry = HP.make_html_entry(rfile+".txt", rfile)
        row = HP.make_table_row([cat, entry, ''])
        celldict[cat].append(('link',row))


    #-------
    # run commands
    if len(namelist) != len(cmdlist):
        _log.warning('ERROR: namelist length not equal cmdlist length')
        _log.warning('namelist ' + '\n--> '.join(namelist))
        _log.warning('cmdlist ' + '\n==> '.join(cmdlist))

    # remove files that are appended to, from uhdas_info.py and sonar_summary.py
    for fname in removal_list:
        if os.path.exists(fname):
            os.remove(fname)

    first_starttime = time.time()

    for icmd, cmd in enumerate(cmdlist):
        namestr = '%20s: %s' % (namelist[icmd], cmd)
        if run_cmd:
            starttime = time.time()
            stdout, stderr = RA.run_cmd(cmd)
            tstr = '%3.1f sec : %s' % (np.round(time.time()-starttime), namestr)
            report_log_list.append(tstr)
            stderr_log_list.append(tstr + stderr)
            _log.info(tstr)
            if stderr:
                _log.warning(stderr)
        else:
            infostr = 'not running ' + namestr
            _log.info(infostr)


    # if this is for real, make the index.html page
    html_list = [HP.comment('INDEX_LINKS'),]
    if os.path.exists(report_dir) and options.remake_index:
        cell_list = [HP.make_table_row( ('CATEGORY', 'DESCRIPTION', 'FILE')) ]
        for cat in HP.catlist:
            if len(celldict[cat]) > 0:
                for instr,row in celldict[cat]:  #instructions
                    if instr == 'link':
                        newrow = row
                    elif instr == 'contents':
                        fname = row[1]
                        ftxt = row[2]
                        entry = HP.make_expanded_html_entry(fname) # read file
                        newrow =  HP.make_table_row([cat, entry, ftxt],
                                    alignments=['center', 'left', 'center'])
                    else:
                        estr = 'element is "link" or "contents", not "%s"' % (instr)
                        raise ValueError(estr)


                    cell_list.append(newrow)

        table1 = HP.make_table(cell_list)
        html_list.append(table1)

        html_list.append(HP.newline)

        html_list.append(HP.comment('INDEX_LINKS'))

        hstr = HP.make_html_index(html_list)
        with open(os.path.join(report_dir, 'index.html'), 'w') as file:
            file.write(hstr)

    tstr = '\n\n%3.1f  seconds elapsed\n' % (np.round(time.time()-first_starttime))
    report_log_list.append(tstr)
    _log.info(tstr)
    if run_cmd:
        infostr = 'html page starts here: %s' % (os.path.join(report_dir, 'index.html'))
        _log.info(infostr)

    report_str = '\n'.join(report_log_list)
    stderr_str = '\n'.join(stderr_log_list)

    if run_cmd:
        with open(os.path.join(report_dir, 'codas_report_generator.log'), 'a') as file:
            file.write(report_str)
        with open(os.path.join(report_dir, 'codas_report_generator_err.log'), 'a') as file:
            file.write(stderr_str)
