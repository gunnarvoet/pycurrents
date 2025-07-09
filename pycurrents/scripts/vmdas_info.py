#!/usr/bin/env python
'''
print vmdas cruise info to screen (or file), for various kinds of data

usage:
  vmdas_info.py  filelist


examples

(1) quick look: get the ensemble lengths and quit (to decide about processing)
NOTE: output goes to screen, not to a log file

vmdas_info.py --guess_enslen  *.LTA
vmdas_info.py --guess_enslen  *.STA

(2) store information in a logfile

vmdas_info.py --logfile LTA_info.txt *.LTA
vmdas_info.py --logfile STA_info.txt *.STA
vmdas_info.py --logfile ENR_info.txt *.ENR

(3) store information in a logfile; also get detailed information

vmdas_info.py --verbose --logfile LTA_info.txt *.LTA



(or if that fails, try specifying the sonar)
  vmdas_info.py SS filelist

  ... where SS is a sonar, from these: (now optional)
          os  Ocean Surveyor
          bb  Broadband
          wh  Workhorse

eg:

vmdas_info.py --logfile LTA_info.txt  os   *.LTA


'''


import logging
import sys
import os
import time
from optparse import OptionParser

from pycurrents.adcp.vmdas import VmdasInfo, guess_sonars, sort_sonars
from pycurrents.system import pathops

# Standard logging
_log = logging.getLogger(__file__)


def usage():
    print(__doc__)
    sys.exit()

vellist = ('lta', 'sta','enr', 'ens', 'enx')

if __name__ == '__main__':


    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    if '--help' in sys.argv:
        print(__doc__)
        sys.exit()


    parser = OptionParser()

    parser.add_option("--logfile", dest="logfile",
                      default=None,
                      help="output logfile here")

    parser.add_option("--verbose", dest="verbose", default=False,
                      action="store_true",
                      help="dump additional information into another file")

    parser.add_option("-g", "--guess_enslen", dest="guess_enslen",
                      default=False, action="store_true",
                      help="just print out the ensemble lengths and quit")

    (options, args) = parser.parse_args()
    # set-up logger so it print to stdout if no log file is defined
    if not options.logfile:
        logging.basicConfig(format='%(message)s', level=logging.INFO)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        _log.addHandler(ch)

    # instrument model is now guessed if it is not specified
    if args[0] not in ('os', 'pn', 'bb', 'wh'):
        filelist = pathops.make_filelist(args)
        instping_tuplist = guess_sonars(filelist) # all
        sonar_info = sort_sonars(instping_tuplist)
        if len(sonar_info.instruments.keys()) > 1:
            print('ERROR: multiple instruments found in dataset.  just do one')
            print(str(instping_tuplist))
            sys.exit()
        #
        model = list(sonar_info.sonars.keys())[0][:2]
        filelist = pathops.make_filelist(args)
    else:
        model = args[0]
        filelist = pathops.make_filelist(args[1:])

    datalist = []
    for f in filelist:
        ext = os.path.splitext(f)[-1]
        if ext[1:].lower() in vellist:
            datalist.append(f)

    if options.logfile:
        if os.path.exists(options.logfile):
            print('\nFile exists:  APPENDING TO %s\n' % (options.logfile))
            print('======= %s APPENDING =======\n\n\n' % (time.asctime()))

    print('\n===Getting detailed information from ADCP data files===')
    vm = VmdasInfo(filelist, model, verbose=options.verbose,
                   quick=options.guess_enslen)

    if options.guess_enslen:
        ddrange = vm.print_scan(include_glossary=False)
        npinglist = vm.get_npings()
        print('\n - Number of pings per ensemble: %s' % (str(npinglist)))
        vm.sort_bytime()
        print('\n - Instrument model: %s' % vm.get_instrument())
        print('\n - Ensemble length from data files: %s' % vm.get_enslen())
        sys.exit(0)
    if options.logfile:
        print('\n===Writing all information to %s===' % options.logfile)
    print('\n- determining summary information about raw data files')
    ddrange = vm.print_scan(outfile=options.logfile)
    print('\n- sorting files in time order')
    vm.sort_bytime(outfile=options.logfile)
    print('\n- guessing instrument model')
    model = vm.get_instrument(outfile=options.logfile)
    print('\n- determining ensemble length from data files')
    enslen = vm.get_enslen(outfile=options.logfile)
    print('\n- about to guess EA from raw data files...')
    EA_angles = vm.get_beaminst_info(outfile=options.logfile)
    print('\n- guessing additional information for single-ping processing')
    vm.get_badfile_info(outfile=options.logfile)
    print('\n- guessing heading source')
    vm.guess_heading_source_lta(outfile=options.logfile)
    print('\n- trying to determine serial NMEA messages')
    vm.guess_serial_msg_types(outfile=options.logfile)

    if options.verbose:
        logfile_parts = os.path.splitext(options.logfile)
        long_logfile = logfile_parts[0] + '_long' + logfile_parts[1]
        print('\n- writing more metadata to %s' % long_logfile)
        vm.print_meta(long_logfile)
