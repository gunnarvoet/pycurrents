#!/usr/bin/env python
'''
typical usage:

- at sea, regular updates of reports dir:

      uhdas_report_generator.py --uhdas_dir /home/data/km1501

- for Oleander, run once, cruise tracks are best viewed in longitude

      uhdas_report_generator.py --uhdas_dir $cruise  --full_report  -p lon
'''
# TODO
# - add raw ashtech quality plot
# - refactor so expanded index.html does not require running twice

import logging
import os
import glob
import time
import sys
import argparse
import subprocess
import shutil

import numpy as np

from pycurrents.system import logutils
from pycurrents.system import Bunch
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp.uhdas_report import UHDAS_CruiseInfo, ReportActions
from pycurrents.adcp.uhdas_report import  HeadingSerialReport
from pycurrents.adcp.uhdas_report import  HTML_page
from pycurrents.adcp.uhdasfile import guess_dbname
from pycurrents.plot.mpltools import nowstr
from pycurrents.system.misc import safe_makedirs
from pycurrents.plot.html_table import Convention_to_Html

plot_levels = Bunch()
plot_levels.basic = Bunch()  # this is what gets run at sea -- just assemble and copy -- very quick
plot_levels.better = Bunch() # same as basic, but with quick_web (takes much longer) and a little more detail
plot_levels.detailed = Bunch() # same as better, but with more detail about serial feeds

# category.name = (output type, comment)
plot_levels.basic.navplot         = ('png',
                          'cruise track over topography')
plot_levels.basic.db_timerange    = ('png',
                          'plot of sonar usage with time, labeled by instrument and ping type')
plot_levels.basic.uhdas_overview  = ('ascii',
                          'overview of directories, files, and time ranges')
plot_levels.basic.adcp_settings   = ('ascii',
                          'report settings used in ADCP data acquisition')
plot_levels.basic.adcp_cals       = ('ascii',
                          'report ADCP processing calibration values')
plot_levels.basic.ens_hcorr       = ('png',
                          'plot heading correction used in processing')
plot_levels.basic.hcorr_serial_asc= ('ascii',
                          'report percent of (accurate) heading from the serial data stream')
plot_levels.basic.pycfg           = ('ascii',
                          'copy files with settings for UHDAS serial and CODAS processing')
plot_levels.basic.png_archive     = ('png',
                          '**copy** archive of png plots from at-sea processing (faster)')
## better = basic + these
plot_levels.better.sonar_summary  = ('ascii',
                          'summary of sonar usage, regardless of ping type')
plot_levels.better.hcorr_serial_plot = ('png',
                          'plot quality of (accurate) heading from the serial data stream')
plot_levels.better.quick_web      = ('png',
                          '**create** a mini-web page (takes longer)')
# detailed = better + these
plot_levels.detailed.uhdas_time   = ('ascii',
                         'report on rbin files in detail')
plot_levels.detailed.uhdas_serial = ('ascii',
                         'deduce which NMEA messages are translated into which rbin files')

def get_namestr():
    lines = []
    lines.append('--- "basic:" ---')
    for name, tt in plot_levels.basic.items():
        lines.append('%20s : %7s : %s' % (name, tt[0], tt[1]))
    lines.append('\n--- "better = basic plus these:" ---')
    for name, tt in plot_levels.better.items():
        lines.append('%20s : %7s : %s' % (name, tt[0], tt[1]))
    lines.append('\n--- "detailed = better plus these:" ---')
    for name, tt in plot_levels.detailed.items():
        lines.append('%20s : %7s : %s' % (name, tt[0], tt[1]))
    namestr = '.\n'.join(lines)
    return namestr


def find_names(level):
    '''
    "level" is either "basic", "better", or "detailed", (from plot_levels)
    -or-
    it is a collection of colon-delimited names (subset of any elements of above)

    returns a list of specific names to invoke
    '''
    basicnames = list(plot_levels.basic.keys())
    betternames = list(plot_levels.better.keys())
    detailednames = list(plot_levels.detailed.keys())
    all = basicnames + betternames + detailednames
    if level == 'basic':
        return basicnames
    if level == 'better':
        return basicnames + betternames
    if level == 'detailed':
        return all
    names = level.split(':')
    if len(names) == 0:
        _log.error('"--level" should be "basic", "better", "detailed" or colon-delimited list')
        sys.exit() ## FIXME
    names2run = []
    for name in names:
        if name not in all:
            _log.error('name %s not in allowed list: %s' % (name, ', '.join(all)))
            sys.exit() ## FIXME
        names2run.append(name)
    return names2run



if __name__ == '__main__':


    parser = argparse.ArgumentParser(
        description="populate a directory with useful information about a UHDAS cruise")

    parser.add_argument('-v', '--verbose',
                        default=False,
                        action='store_true',
                        help='verbose: print status of web page generation')

    parser.add_argument('--log',
                        default=None,
                        help='logfile name (replacing stdout)')

    parser.add_argument('--testing',
                        action='store_true',
                        default=False,
                        help='testing: show commands, do not run anything')

    parser.add_argument('-l', '--links_only',
                        action='store_true',
                        default=False,
                        help='rows are links, no expanded text')

    parser.add_argument('-i', '--remake_index',
                        action='store_true',
                        default=False,
                        help='remake index.html but do not do anything else')

    parser.add_argument('-u', '--uhdas_dir',
                        default=None,
                        help='UHDAS cruise directory')

    parser.add_argument('--level',
                        default='basic',
                        help='"basic" (default, fast), "better" (remake web plots), or "detailed"\n or specific colon-delimited list of plot types to generate.\n - run first using "--testing" to see options\n')

    parser.add_argument('--hacc_cutoff',
                        default=0.02,
                        help='posmv PASHR heading accuracy cutoff')

    parser.add_argument('-c', '--cruisename',
                        default=None,
                        help='UHDAS cruise name')

    parser.add_argument('-m', '--hcorr_msg',
                        default=None,
                        help='heading correction message (eg. "pmv", "adu") if it cannot be deduced')

    parser.add_argument('-d', '--report_dir',
                        default=None,
                        help='default is "uhdas_dir/reports" put reports here (make directory if necessary'),

    parser.add_argument('-f', '--full_report',
                      default=False,
                      action='store_true',
                      help='run more commands that take longer (looking in serial data)')

    parser.add_argument('-t', '--thumbnailsize',
                      default='200',
                      help='thumbnail: number of pixels (default=300 (small)) ')

    parser.add_argument('-p', '--plot_type',
                      default='dday',
                      help='plot contours as a function of this variable (eg. transit)')


    opts = parser.parse_args()
    verbose = opts.verbose

    _log = logging.getLogger()
    if verbose:
        _log.setLevel(logging.DEBUG)
    else:
        _log.setLevel(logging.INFO)

    if opts.log is None:
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(opts.log)
        formatter = logutils.formatterTLM
        handler.setFormatter(formatter)

    _log.addHandler(handler)

    _log.debug('Starting uhdas_report_generator.py')

    if opts.uhdas_dir is None:
        raise IOError('must set uhdas_dir')
    else:
        uhdas_dir = opts.uhdas_dir.rstrip(os.sep)

    if not os.path.exists(uhdas_dir):
        raise IOError('uhdas directory %s does not exist' % (uhdas_dir))
    infostr = 'found uhdas_directory %s' % (uhdas_dir)
    _log.debug(infostr)

    infostr = '\n--> environment and path info for debugging:\n '
    _log.debug(infostr)

    if opts.cruisename is None:
        opts.cruisename = os.path.basename(uhdas_dir)

    expand_text = True
    if opts.links_only:
        expand_text = False

    run_cmd = True
    if opts.testing or opts.remake_index:
        run_cmd = False

    if run_cmd:
        opts.remake_index=True

    if opts.report_dir is None:
        report_dir = os.path.join(uhdas_dir, 'reports')
    else:
        report_dir = opts.report_dir

    if run_cmd:
        if not os.path.exists(report_dir):
            safe_makedirs(report_dir)
            infostr = 'making report directory "%s"' % (report_dir)
            _log.debug(infostr)
        else:
            infostr = 'updating report directory %s' % (report_dir)
            _log.debug(infostr)

        _log.info('cruisename is <%s>', opts.cruisename)
        _log.info('report_dir is <%s>', report_dir)
        _log.info('uhdas_dir is <%s>', uhdas_dir)

        ## this is presently managed manually. see above
        _log.debug(get_namestr())

    ##
    HP = HTML_page(opts.cruisename, report_dir=report_dir)

    # namelist = type of plot
    # cmdlist = commands to run
    # celldict:  key=category, value = list of tuples (one per row)
    #            tuple = ('link',     [cat, link,     filenametext]  # link is 'as is'
    #            tuple = ('contents', [cat, filename, filenametext]  # filename must be read

    namelist=[]
    cmdlist  = []
    celldict  = Bunch()      # table1
    namelist2=[]
    cmdlist2 = []
    celldict2 = Bunch()      # table2
    report_log_list = ["===== %s =====" % (nowstr()),]
    stderr_log_list = []
    for cat in HP.catlist:
        celldict[cat]=[]
        celldict2[cat]=[]
    removal_list = []  #files to remove


    ## copy processing and logging configurations
    # FIXME: try to eliminate the "verbose" kwargs
    CI = UHDAS_CruiseInfo(verbose=verbose, debug=False)
    RA = ReportActions(report_dir=report_dir, runnit=run_cmd, verbose=verbose)

    CI(uhdas_dir)

    if CI.hcorr_info.hcorr_msg is not None and CI.hcorr_info.hcorr_msg is None:
        CI.hcorr_info.hcorr_msg = opts.hcorr_msg
    if opts.hacc_cutoff is None:
        acc_heading_cutoff = CI.acc_heading_cutoff
        infostr = 'getting posmv heading accuracy cutoff from cruise setup (proc_cfg)'
        _log.debug(infostr)
    else:
        acc_heading_cutoff = float(opts.hacc_cutoff)
        infostr = 'getting posmv heading accuracy cutoff from specified options'
        _log.debug(infostr)

    cmd = 'du -sh %s' % (uhdas_dir)
    proc=subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    infostr = '\n\nuhdas_directory size is %s' % (stdout)
    _log.debug(infostr)
    report_log_list.append(infostr)

    #----------------
    names2run = find_names(opts.level)
    #----------------

    link_targets = []
    rtextlist = []
    cat = "overview"

    name = 'navplot'
    _log.debug('about to set up navplot section and sonar usage')
    if name in names2run:
        if 'pos_inst' in CI.gps_info.keys():
            gps_fileglob = '*.%s.rbin' % (CI.gps_info.pos_msg)
            rbinglob =  os.path.join('rbin', CI.gps_info.pos_inst, gps_fileglob)
            rfile =  'nav_plot_all'
            ## this now makes 2 plots:  nav_plot_all_topo.png and nav_plot_all_txy
            filelist = glob.glob(gps_fileglob)
            subsample=int(max(300, 60*len(filelist)/24.))
            infostr = 'plot_rnav: subsample by %d to speed things up' % (subsample)
            _log.debug(infostr)
            strtmp = 'plot_rnav.py -s%d --noshow  --title %s --outfile %%s  %s' % (
                    subsample, opts.cruisename, os.path.join(CI.uhdas_dir, rbinglob))
            cmd = RA.make_cmd(strtmp, rfile)
            cmdlist.append(cmd)
            namelist.append(name)
            _log.debug(cmd)
            for suffix in ['_topo', '_txy']:
                rtextlist.append('cruise track (where UHDAS was run)')
                link_targets.append(rfile+suffix)
                if run_cmd:
                    removal_list.append(os.path.join(report_dir, rfile+suffix+'.png'))

    #-------------
    name = 'db_timerange'
    if name in names2run:
        ## list sonar usage
        rfile = 'db_timerange'
        rtextlist.append('plot when each sonar was run')
        strtmp = 'plot_db_timeranges.py  --outfile %%s --noshow  %s ' % (CI.uhdas_dir)

        if run_cmd:
            removal_list.append(os.path.join(report_dir, rfile+'.png'))
        cmd=RA.make_cmd(strtmp, rfile)
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
                tcmd = HP.thumbnail_cmd(os.path.join(report_dir, link_target), tpix=int(opts.thumbnailsize)) #return command
                cmdlist.append(tcmd)
                namelist.append(name)
                _log.debug(tcmd)
        row = HP.make_table_row([cat, ' '.join(plot_entry), ' '.join(text_entry)])
        celldict[cat].append(('link',row))


    #----------------
    name = 'quick_web'
    _log.debug('about to set up %s section' % (name))
    if name in names2run:
        for procdir in CI.procpaths:
            db_globstr = os.path.join(procdir, 'adcpdb', '*dir.blk')
            filelist = glob.glob(db_globstr)
            if len(filelist) > 0:
                sonar = Sonar(os.path.basename(procdir))
                ## webdir is reports/os38nb_web
                webdir = '%s_web' % (sonar.sonar)
                # if we will fill it, remove it first
                if run_cmd:
                    if os.path.exists(webdir):
                        shutil.rmtree(webdir)
                rfile = os.path.join(webdir, 'index.html')
                strtmp = 'quick_web.py --webdir %%s --sonar %s  --auto --cruiseid %s --dbname %s --refbins 2:3 --redo' % (
                    sonar.sonar, opts.cruisename, guess_dbname(procdir))
                rtext = '%s ADCP web page' % (sonar.sonar)
                cat = "processed ADCP"
                tfile = '%s_%scont000' % (sonar.sonar, opts.plot_type)
                ## run quick_web before trying to make thumbnails...
                cmd = RA.make_cmd(strtmp,  webdir)
                cmdlist.append(cmd)
                _log.debug(cmd)
                namelist.append(name)

                tsrc = os.path.join(webdir, tfile)
                tcmd = HP.thumbnail_cmd(os.path.join(report_dir, tsrc), tpix=int(opts.thumbnailsize)) #return command
                cmdlist.append(tcmd)
                _log.debug(cmd)
                namelist.append(name)

                ## show thumbnail, click = index <====
                link_target=link_target=os.path.join(webdir, 'index.html')
                entry = HP.make_plot_html0( tsrc, link_target, alt_text=rtext)
                row = HP.make_table_row([cat, entry, rfile])
                celldict[cat].append(('link',row))


    #----------------------
    name = 'png_archive'
    _log.debug('about to set up %s section', name)
    if name in names2run:
        for procdir in CI.procpaths:
            sonar = Sonar(os.path.basename(procdir))
            png_archive = os.path.join(procdir, 'png_archive')
            if len(glob.glob(os.path.join(png_archive, '*.png'))) > 0:
                dest = '%s_pngarchive' % (sonar.sonar)
                rdest = os.path.join(report_dir, dest)
                if run_cmd and not os.path.exists(rdest):
                    safe_makedirs(rdest)
                ## TODO -- if no index.html, make one.
                rtext = '%s png archive from at-sea processing' % (sonar.sonar)
                cat = "processed ADCP"
                cmd = 'rsync -au %s/ %s' % (png_archive, rdest)

                # we need to run this command to get the pngs over before making index.html
                if run_cmd:
                    starttime = time.time()
                    stdout, stderr = RA.run_cmd(cmd)
                    tstr = '%3.1f sec : png archive rsync' % (np.round(time.time()-starttime))
                    report_log_list.append(tstr)
                    stderr_log_list.append(tstr +  stderr)
                    _log.info(tstr)
                    if stderr:
                        _log.warning(stderr)

                    ## for html, this is within report dir
                    index = os.path.join(rdest, 'index.html')
                    if not os.path.exists(index) and not opts.testing:
                        try:
                            Convention_to_Html(figdir = rdest,
                                               convention = 'uhdas',
                                               columns = ['shallow','ddaycont',
                                                          'latcont','loncont'],
                                               )
                        except Exception as e:
                            _log.exception(f'cannot make {png_archive}/index.html\nError: {e}')

                # let run_cmd take care of this down below
                if os.path.exists(os.path.join(rdest, 'index.html')):
                    rfile = os.path.join(dest, 'index.html')
                else:
                    rfile = dest
                report_log_list.append(cmd)
                row = HP.make_table_row([cat, HP.make_html_entry(rfile, rtext), rfile])
                celldict[cat].append(('link',row))
                cmdlist.append(cmd)
                _log.debug(cmd)
                namelist.append(name)

    #-----------------------
    name = 'uhdas_overview'
    _log.debug('about to set up %s section' % (name))
    if name in names2run:
        ## logging summary
        rfile = 'uhdas_overview.txt'
        rtext = "overview of UHDAS directory contents, with WARNINGS and ERRORS"
        strtmp = 'uhdas_info.py --overview --logfile  %%s %s' % (CI.uhdas_dir)
        cat = "overview"
        if expand_text:
            fname=os.path.join(report_dir, rfile)
            row =  [cat, fname, rfile]
            celldict[cat].append(('contents',row))
        else:
            entry = HP.make_html_entry(rfile, rtext)
            row =  HP.make_table_row([cat, entry, rfile])
            celldict[cat].append(('link',row))

        if run_cmd:
            removal_list.append(os.path.join(report_dir, rfile))
        cmd = RA.make_cmd(strtmp, rfile)
        cmdlist.append(cmd)
        _log.debug(cmd)
        namelist.append(name)




    #----------------------
    name = 'sonar_summary'
    _log.debug('about to set up %s section', name)
    if name in names2run:
        ## list sonar usage
        rfile = 'sonar_summary.txt'
        rtext = 'overall list of times when each sonar was run'
        strtmp = 'sonar_summary.py --outfile %%s --uhdas_dir %s ' % (CI.uhdas_dir)
        cat = "raw ADCP"
        if expand_text:
            fname=os.path.join(report_dir, rfile)
            row =  [cat, fname, rfile]
            celldict[cat].append(('contents',row))
        else:
            entry = HP.make_html_entry(rfile, rtext)
            row =  HP.make_table_row([cat, entry, rfile])
            celldict[cat].append(('link', row))


        if run_cmd:
            removal_list.append(os.path.join(report_dir, rfile))
        cmd=RA.make_cmd(strtmp, rfile)
        cmdlist.append(cmd)
        _log.debug(cmd)
        namelist.append(name)



    #----------------------
    name = 'adcp_settings'
    _log.debug('about to set up %s section', name)
    if name in names2run:
        ## list raw ADCP settings
        rfile =  'ADCP_settings.txt'
        rtext = 'from raw data: listing of ADCP settings'
        strtmp = 'uhdas_info.py --settings --logfile  %%s %s' % (CI.uhdas_dir)
        cat = "raw ADCP"
        if expand_text:
            fname=os.path.join(report_dir, rfile)
            row =  [cat, fname, rfile]
            celldict[cat].append(('contents',row))
        else:
            entry = HP.make_html_entry(rfile, rtext)
            row =  HP.make_table_row([cat, entry, rfile])
            celldict[cat].append(('link', row))

        if run_cmd:
            removal_list.append(os.path.join(report_dir, rfile))
        cmd = RA.make_cmd(strtmp, rfile)
        cmdlist.append(cmd)
        _log.debug(cmd)
        namelist.append(name)



    #----------------------
    name = 'adcp_cals'
    _log.debug('about to set up %s section', name)
    if name in names2run:
        ## show ADCP calibrations from processing
        rfile = 'ADCP_cals.txt'
        rtext = 'heading and scale factor calibrations'
        strtmp = 'uhdas_info.py --cals    --logfile  %%s %s' % (CI.uhdas_dir)
        cat = "processed ADCP"
        if expand_text:
            fname=os.path.join(report_dir, rfile)
            row =  [cat, fname, rfile]
            celldict[cat].append(('contents',row))
        else:
            entry = HP.make_html_entry(rfile, rtext)
            row =  HP.make_table_row([cat, entry, rfile])
            celldict[cat].append(('link',row))

        if run_cmd:
            removal_list.append(os.path.join(report_dir, rfile))
        cmd = RA.make_cmd(strtmp, rfile)
        cmdlist.append(cmd)
        _log.debug(cmd)
        namelist.append(name)



    #----------------------
    ## Heading cor
    name = 'ens_hcorr'
    _log.debug('about to set up %s section' % (name))
    if name in names2run and 'hcorr_inst' in CI.hcorr_info.keys():
        # plot ens_hcorr
        plot_entry = [] # two plots in the cell
        text_entry = [] # two names to describe
        rfilelist = []
        enspath = os.path.join('cal','rotate', 'ens_hcorr.asc')
        for procdir in CI.procpaths:
            if os.path.exists(os.path.join(procdir, enspath)):
                procname = os.path.basename(procdir)
                rfile = procname + '_hcorr'
                link_target=rfile+'.png'
                try:
                      titlestr = '%s_%s' % (name,  CI.hcorr_info.hcorr_msg)
                except:
                    titlestr = '(fill in heading device here)'
                rtext = " %s heading correction plot from %s" % (procname, titlestr)
                strtmp = 'plot_enshcorr.py --infile %s --outfile %%s --yearbase %d --titlestring %s' %(
                    os.path.join(procdir, enspath), CI.proc_cfg.yearbase, titlestr)
                cat = "quality"
                cmd = RA.make_cmd(strtmp, rfile)
                cmdlist.append(cmd)
                _log.debug(cmd)
                namelist.append(name)
                ## more complicated; show the thumbnail as well
                plot_entry.append( HP.make_plot_html0(rfile, link_target, alt_text=rtext))
                plot_entry.append(HP.space)
                text_entry.append(rfile+".png" + HP.newline)
                rfilelist.append(rfile)
                if run_cmd:
                    tcmd = HP.thumbnail_cmd(os.path.join(report_dir, rfile), tpix=int(opts.thumbnailsize)) #return command
                    cmdlist.append(tcmd)
                    _log.debug(tcmd)
                    namelist.append(name)
        row = HP.make_table_row([cat, ' '.join(plot_entry), ' '.join(text_entry)])
        celldict[cat].append(('link',row))




    #----------------------
    ## quality plot of hcorr inst (add adu)
    name = 'hcorr_serial_plot'
    _log.debug('about to set up %s section', name)
    if name in names2run and 'hcorr_inst' in CI.hcorr_info.keys():
        if CI.hcorr_info.hcorr_inst[:5] == 'posmv':
            posmvdirs = glob.glob(os.path.join(CI.uhdas_dir, 'rbin', 'posmv*'))
            for posmv in posmvdirs:
                rfile = '%s_quality' % (os.path.basename(posmv))
                rtext = 'quality plot of posmv accuracy'
                globstr = os.path.join(uhdas_dir, 'rbin',
                              CI.hcorr_info.hcorr_inst, '*%s.rbin' %  CI.hcorr_info.hcorr_msg)
                infostr = 'looking for posmv rbins here:\n' + globstr
                _log.debug(infostr)
                filelist=glob.glob(globstr)
                subsample=int(max(60, 60*len(filelist)/24.))
                infostr = 'plot_posmv: subsample by %d to speed things up' % (subsample)
                _log.debug(infostr)
                strtmp = 'plot_posmv.py --cutoff %6.3f -s %d -o %%s --noshow %s' % (
                    acc_heading_cutoff, subsample, CI.uhdas_dir)
                infostr = 'posmv QC plot made with\n%s' % (strtmp % (rfile))
                _log.debug(infostr)
                cat = "quality"
                row = HP.make_table_row([cat, HP.make_html_entry(rfile+".png", rtext), rfile])
                celldict[cat].append(('link', row))
                cmd = RA.make_cmd(strtmp, rfile)
                cmdlist.append(cmd)
                _log.debug(cmd)
                namelist.append(name)



    #----------------------
    name = 'pycfg'
    _log.debug('about to set up %s section', name)
    if name in names2run:
        ## get *proc.py and sensor_cfg.py
        ctext=Bunch()
        ctext[CI.proc_file] = ("ADCP CODAS processing settings", "UHDAS settings")
        ctext[CI.sensor_file] = ("UHDAS serial acquisition settings", "UHDAS settings")
        for fname in (CI.proc_file, CI.sensor_file):
            if fname is not None:
                rfile = os.path.basename(fname) + ".txt"
                rtext = ctext[fname][0]
                cat = ctext[fname][1]
                row = HP.make_table_row([cat, HP.make_html_entry(rfile, rtext), rfile])
                celldict[cat].append(('link', row))
                strtmp = 'cp -p %s %%s' % (fname)
                cmd = RA.make_cmd(strtmp, rfile)
                cmdlist.append(cmd)
                _log.debug(cmd)
                namelist.append(name)
                infostr = 'found %s' % (os.path.basename(fname))
                _log.debug(infostr)
            else:
                _log.warning('missing one configuration file')

    #========  more  time-consuming info ============

    ## sumarize heading quality by line
    if opts.full_report:
        name = 'hcorr_serial_asc'
        _log.debug('about to set up %s section', name)
        if name in names2run and 'hcorr_inst' in CI.hcorr_info.keys():
            inst = CI.hcorr_info.hcorr_inst
            msg =  CI.hcorr_info.hcorr_msg
            HSR = HeadingSerialReport()
            rfile =  '%s_%s_hcorr.txt' % (inst, msg)
            outfile=os.path.join(report_dir, rfile)
            rtext = '%s heading quality' % (inst)
            cat = "quality"
            if expand_text:
                fname=os.path.join(report_dir, rfile)
                row =  [cat, fname, rfile]
                celldict2[cat].append(('contents',row))
            else:
                entry = HP.make_html_entry(rfile, rtext)
                row =  HP.make_table_row([cat, entry, rfile])
                celldict2[cat].append(('link', row))

            cmd = "## make ascii serial quality statistics file"
            namelist2.append(name)
            cmdlist2.append(cmd) # should not execute
            _log.debug(cmd)
            if run_cmd:
                HSR(uhdas_dir, inst, msg, outfile=outfile, cruisename=opts.cruisename, cutoff=float(opts.hacc_cutoff))


        name = 'uhdas_time'
        _log.debug('about to set up %s section', name)
        if name in names2run:
            rfile = 'uhdas_time.txt'
            rtext = 'raw logging file information: computer clock and rbin conversion'
            strtmp= 'uhdas_info.py --time --logfile %%s %s' % (CI.uhdas_dir)
            cat = "serial logging"
            row = HP.make_table_row([cat, HP.make_html_entry(rfile, rtext), rfile])
            celldict2[cat].append(row)
            cmd = RA.make_cmd(strtmp,  rfile)
            cmdlist2.append(cmd)
            _log.debug(cmd)
            namelist2.append(name)

        name = 'uhdas_serial'
        _log.debug('about to set up %s section', name)
        if name in names2run:
            rfile = 'uhdas_serial.txt'
            rtext = 'mapping of NMEA messages to rbin suffix'
            strtmp = 'uhdas_info.py --serial   --logfile %%s %s' % (CI.uhdas_dir)
            cat = "serial logging"
            row = HP.make_table_row([cat,  HP.make_html_entry(rfile, rtext), rfile])
            celldict2[cat].append(('link', row))
            cmd = RA.make_cmd(strtmp, rfile)
            cmdlist2.append(cmd)
            _log.debug(cmd)
            namelist2.append(name)

    #-------
    # run commands
    if len(namelist) != len(cmdlist):
        _log.warning('ERROR: namelist length not equal cmdlist length')
        _log.warning('namelist ' + '\n--> '.join(namelist))
        _log.warning('cmdlist ' + '\n==> '.join(cmdlist))

    if len(namelist2) != len(cmdlist2):
        _log.warning('ERROR: namelist2 length not equal cmdlist2 length')
        _log.warning('namelist2 ' + '\n--> '.join(namelist2))
        _log.warning('cmdlist2 ' + '\n==> '.join(cmdlist2))


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

    # run more commands
    if opts.full_report:
        for icmd, cmd in enumerate(cmdlist2):
            namestr = '%20s: %s' % (namelist2[icmd], cmd)
            if run_cmd:
                stdout, stderr = RA.run_cmd(cmd)
                tstr = '%3.1f sec: %s' % (np.round(time.time()-starttime), namestr)
                report_log_list.append(tstr)
                stderr_log_list.append(tstr+ stderr)
                _log.info(tstr)
            else:
                infostr = 'not running ' + namestr
                _log.info(infostr)

    # if this is for real, make the index.html page
    html_list = [HP.comment('INDEX_LINKS'),]
    if os.path.exists(report_dir) and opts.remake_index:
        cell_list = [HP.make_table_row( ('CATEGORY', 'DESCRIPTION', 'FILE')) ]
        for cat in HP.catlist:
            if len(celldict[cat]) > 0:
                for instructions,row in celldict[cat]:
                    if instructions == 'link':
                        cell_list.append(row)
                    elif instructions == 'contents':
                        cat, fname, rfile = row
                        entry = HP.make_expanded_html_entry(fname) # read file
                        newrow =  HP.make_table_row([cat, entry, rfile],
                                                    alignments=['center', 'left', 'center'])
                        cell_list.append(newrow)
                    else:
                        raise ValueError('row element is "link" or "contents", not "%s"' % (instructions))

                cell_list.append( HP.make_table_row( (HP.space, HP.space, HP.space)  ))
        table1 = HP.make_table(cell_list)
        html_list.append(table1)

        if opts.full_report:
            cell_list = []
            for cat in HP.catlist:
                if len(celldict2[cat]) > 0:
                    for instructions,row in celldict[cat]:
                        if instructions == 'link':
                            cell_list.append(row)
                        elif instructions == 'contents':
                            cat, fname, rfile = row
                            entry = HP.make_expanded_html_entry(fname) # read file
                            newrow =  HP.make_table_row([cat, entry, rfile],
                                                        alignments=['center', 'left', 'center'])
                            cell_list.append(newrow)
                        else:
                            raise ValueError('row element is "link" or "contents", not "%s"' % (instructions))

                    cell_list.append( HP.make_table_row( (HP.space, HP.space, HP.space)  ))
            table2 = HP.make_table(cell_list)

        html_list.append(HP.newline)
        html_list.append(HP.newline)

        if opts.full_report:
            html_list.append('More information:')
            html_list.append(HP.newline)
            html_list.append(HP.newline)
            html_list.append(table2)

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
        with open(os.path.join(report_dir, 'uhdas_report_generator.log'), 'a') as file:
            file.write(report_str)
        with open(os.path.join(report_dir, 'uhdas_report_generator_err.log'), 'a') as file:
            file.write(stderr_str)

    '''

UHDAS_DIR=/home/data/uhdas_data_archive/thompson/TN305

# to see short list of commands:

uhdas_report_generator.py --verbose --uhdas_dir $UHDAS_DIR

#to execute short list of commands

uhdas_report_generator.py --report_dir reports --run_cmd --uhdas_dir  $UHDAS_DIR

# to execute long list of commands

uhdas_report_generator.py --report_dir reports  --run_cmd --uhdas_dir   $UHDAS_DIR --full_report


'''
