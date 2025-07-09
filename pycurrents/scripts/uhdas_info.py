#!/usr/bin/env python
'''
This is a collection of tools to collect meta-information about
a UHDAS data directory.

usage: uhdas_info.py [--overview] [--settings] [--cals] [--time] [--serial]  uhdas_dir


options:
        --overview    : show file name summary and time ranges
        --settings    : show ADCP ping settings (takes more time)
        --cals        : show watertrack and bottom track calibration
        --gaps        : print info about intermal gaps in ADCP processing
        --time        : check some file and database time ranges
        --rbintimes   : look for outliers in clock diffs -- timeconsuming
        --rbincheck   : see if rbins were made correctly
        --clockcheck  : check computer clock for all messages (eg. rebooted?)
        --serial      : show serial messages (from raw) and rbin translations
                        - takes more time;
                        - order multiple raw messages may not match rbin order
        --logfile FILE:  write output here (instead of the screen)


example:

    uhdas_info.py --overview --settings --cals --serial --time --logfile  km1301_info.txt  km1301
    uhdas_info.py --settings --cals   km1301
    uhdas_info.py --time km1301

    uhdas_info.py --rbintimes km1301


'''

import os
import sys
import glob
import logging
from optparse import OptionParser

from pycurrents.adcp.raw_multi import Multiread
import pycurrents.adcp.uhdas_adcpinfo as uai  # Most of the functions are here.
from pycurrents.system import logutils
from pycurrents.adcp.uhdasfile import guess_dbname

logging.captureWarnings(True)
_log = logging.getLogger()
_log.setLevel(logging.INFO)


def uhdas_info(options, args):
    if options.all:
        options.overview = True
        options.settings = True
        options.cals = True
        options.serial = True
        options.time = True
        options.rbintimes = True
        options.rbincheck = True

    if len(args) == 0:
        _log.error('ERROR: must supply uhdas directory as a command line argument')
        sys.exit(1)

    uhdas_dir = args[0]
    if not os.path.isdir(os.path.abspath(uhdas_dir)):
        _log.error('ERROR: uhdas directory %s does not exist' % uhdas_dir)
        sys.exit(1)

    if not os.path.isdir(os.path.abspath(uhdas_dir)):
        _log.error('ERROR: uhdas directory %s does not exist' % uhdas_dir)
        sys.exit(1)

    if len(args) == 0:
        _log.info(__doc__)
        sys.exit()

    if not (options.overview or options.cals or
            options.gaps or options.settings or
            options.time or options.serial or options.rbintimes or options.rbincheck):
        print("--> No output options selected.  Select from: <--")
        for p in parser.option_list[1:]:
            print('          ' + p.get_opt_string())
        print("")
        sys.exit(1)


    

    if options.logfile is None:
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(options.logfile)
    handler.setFormatter(logutils.formatterMinimal)
    _log.addHandler(handler)

    udirs = [d.name for d in os.scandir(uhdas_dir) if d.is_dir()]
    if 'tsgmet' in udirs:
        udirs.remove('tsgmet')  # It's a fossil we can ignore.

    found_raw = False
    found_rbin = False
    found_gbin = False
    found_proc = False



    _log.info('==================================================================')
    _log.info('======= start of report for %s =====' % (uhdas_dir))
    _log.info('==================================================================')

    ### get overview ###
    if 'raw' in udirs:
        serial_info, adcp_info, md5count = uai.get_raw_info(uhdas_dir)
        if options.overview:
            uai.print_raw_info(serial_info, adcp_info, md5count)
        udirs.remove('raw')
        found_raw=True
    else:
        _log.warning('ERROR no "raw" directory found')

    if 'rbin' in udirs:
        im_names, serial_info, full_baselist, md5count = uai.get_rbin_info(uhdas_dir)
        if options.overview:
            uai.print_rbin_info(im_names, serial_info, full_baselist, md5count)
        udirs.remove('rbin')
        found_rbin = True
    else:
        _log.warning('ERROR no "rbin" directory found')

    if 'gbin' in udirs:
        if options.overview:
            uai.print_gbin_info(uhdas_dir)
        udirs.remove('gbin')
        found_gbin = True
    else:
        _log.warning('ERROR no "gbin" directory found')

    if 'proc' in udirs:
        trdict = uai.get_dbtimeranges(uhdas_dir) #dict with (yearbase, dday0, dday1)
        procdirs = list(trdict.keys())
        procdirs.sort()
        if options.overview:
            _log.info('\n------ database time ranges --------\n')
            for procdir in procdirs:
                if trdict[procdir][1] is None:
                    trstr = 'proc: %10s   No database found' % (procdir)
                else:
                    trstr= 'proc: %10s       %7.3f - %7.3f (%s)' % (
                        procdir, trdict[procdir][1], trdict[procdir][2],
                        uai.tr2str(trdict[procdir]))
                _log.info(trstr)
        udirs.remove('proc')
        found_proc = True
        inst_trdict = uai.combine_trdict(trdict)
    else:
        _log.warning('ERROR no "proc" directory found')
        inst_trdict=dict()

    if 'reports' in udirs:
        udirs.remove('reports')
        found_raw=True
    else:
        _log.warning('(no "reports" directory found)')


    if len(udirs) > 0:
        if options.overview:
            _log.warning('\n...BUT these were found:\n   %s' %('\n   '.join(udirs)))

    ### now deal with other options ###
    if options.time and found_gbin and found_proc:
        _log.info('\n------ checking computer times  --------\n')
        uai.check_computer_times(uhdas_dir, inst_trdict)

        _log.info('\n------ checking gbin and processing times  --------\n')
        uai.check_gbin_proc_times(uhdas_dir, inst_trdict)

    if options.rbintimes and found_rbin:
        _log.info('\n------ checking rbin times  --------\n')
        print('# ... wait ... can be time-consuming')
        uai.check_rbintimes(uhdas_dir)


    if options.clockcheck and found_rbin:
        _log.info('\n------ checking clock times  --------\n')
        uai.check_clock(uhdas_dir)

    if options.rbincheck and found_rbin and found_raw:
        _log.info('\n------ checking raw and rbin: were rbins made correctly?  --------\n')
        uai.check_raw_rbin_times(uhdas_dir, verbose=True)

    if options.cals and found_proc:
        calstrlist = ['==================ADCP calibrations ==================\n',]
        warnlist = []
        procdirs = uai.get_procdirs(uhdas_dir)
        for procdir in procdirs:
            btstr, wtstr = uai.check_cals(procdir, uhdas_dir)
            calstrlist.append('\n'.join([btstr,
                                        '',
                                        wtstr,
                        '-------------\n']))
            warnstr = uai.evaluate_calstr(btstr)
            if warnstr:
                warnlist.append(warnstr)
            warnstr = uai.evaluate_calstr(wtstr)
            if warnstr:
                warnlist.append(warnstr)

            xystr = uai.check_dxdy(procdir, uhdas_dir)
            calstrlist.append('\n'.join(['\n', xystr,
                        '------------------------------------------\n']))

        _log.info('\n'.join(calstrlist))
        if len(warnlist) > 0:
            _log.info('\n'.join(warnlist))
            _log.info('\n')

    if options.gaps and found_proc:
        _log.info('========== Gaps in Processed Data ==========\n')
        procdirs = uai.get_procdirs(uhdas_dir)
        for procdir in procdirs:
            if trdict[procdir][1] is None:
                trstr = 'proc: %10s   No database found' % (procdir)
            else:
                trstr= 'proc: %10s       %7.3f - %7.3f (%s)' % (
                    procdir, trdict[procdir][1], trdict[procdir][2],
                    uai.tr2str(trdict[procdir]))
                _log.info(trstr)
                pdir = os.path.join(uhdas_dir, 'proc', procdir)
                dbname = guess_dbname(pdir)
                infolist = uai.finddb_gaps(dbname)
                uai.print_gaps(infolist, prefix='proc: %10s     ' % (procdir))


    if options.settings and found_raw:
        for instrument in adcp_info.keys():
            model = instrument[:2]
            rawdir = os.path.join(uhdas_dir, 'raw', instrument)
            rawglob = os.path.join(rawdir, '*.raw')

            filelist = [f for f in glob.glob(rawglob) if os.path.getsize(f) > 0]

            _log.info('\n\n======= %s settings: chunked by configuration  =========\n' % (instrument))

            if len(filelist)==0:
                _log.warning('no files with data found using %s\n' %(rawglob,))
            else:
                m=Multiread(rawglob, instrument[:2])
                _log.info('index num  startdday  enddday      BT  (ping, nbins,binsize, blank, pulse) (...)')
                _log.info('---- ---   --------- --------     --- ')
                _log.info(m.list_chunks())


    if options.serial and found_raw:
        uai.print_raw_rbin_messages(uhdas_dir, verbose = True)

    _log.info('---------- end of report for %s --------------' % (uhdas_dir))


if __name__ == "__main__":
    #-----------
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    if '--help' in sys.argv:
        print(__doc__)
        sys.exit()

    parser = OptionParser()

    parser.add_option("--overview", action="store_true",
                    dest="overview", default=False,
                    help="show summary of file names and time ranges")
    parser.add_option("--logfile", dest="logfile",
                    default = None,
                    help="output logfile here")
    parser.add_option("--cals", action="store_true",
                    dest="cals", default=False,
                    help="show calibrations")
    parser.add_option("--gaps", action="store_true",
                    dest="gaps", default=False,
                    help="print info about gaps in processing")
    parser.add_option("--settings", action="store_true",
                    dest="settings", default=False,
                    help="show adcp acquisition settings (takes more time)")
    parser.add_option("--time", action="store_true",
                    dest="time", default=False,
                    help="check some file and database time ranges")
    parser.add_option("--rbincheck", action="store_true",
                    dest="rbincheck", default=False,
                    help="see if rbins were made correctly")
    parser.add_option("--rbintimes", action="store_true",
                    dest="rbintimes", default=False,
                    help="check clock diffs from rbin times")
    parser.add_option("--clockcheck", action="store_true",
                    dest="clockcheck", default=False,
                    help="check computer clock -- rebooted?")
    parser.add_option("--serial", action="store_true",
                    dest="serial", default=False,
                    help="show serial messages from raw and rbin (takes much more time)")
    parser.add_option("--all", action="store_true",
                    dest="all", default=False,
                    help="runs all options: '--overview --settings --cals --serial --time' ")

    (options, args) = parser.parse_args()


    uhdas_info(options, args)