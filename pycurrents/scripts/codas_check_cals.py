#!/usr/bin/env python
'''
codas_check_cals.py [--outfile cals.txt] --sonar sonarname procdir

sonarname is a required comment--no spaces: eg.

         codas_check_cals.py  --sonar os75bb procdir

This program reads 3 files in procdir:
   - cal/watertrk/adcpcal.out
   - cal/botmtrk/btcaluv.out
   - cal/watertrk/guess_xducerxy.out
and produces a file procdir/ADCP_cals.txt with a calibration summary.

'''

import logging
import sys
from optparse import OptionParser

import pycurrents.adcp.uhdas_adcpinfo as uai
from pycurrents.system import logutils


def usage():
    print(__doc__)
    sys.exit()

if __name__ == '__main__':


    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    if '--help' in sys.argv:
        print(__doc__)
        sys.exit()


    parser = OptionParser()

    parser.add_option("--outfile", dest="logfile",
                      default=None,
                      help="output cals here")

    parser.add_option("--sonar", dest="sonar",
                      default=None,
                      help="add this name to cals output report")

    (options, args) = parser.parse_args()
    if args:
        procdir = args[0]
    else:
        print('must specify processing directory')
        print(__doc__)
        sys.exit()


    if options.sonar is None:
        print('must specify sonar name (string, no spaces)')
        print(__doc__)
        sys.exit()

    logging.captureWarnings(True)
    _log = logging.getLogger()
    _log.setLevel(logging.INFO)

    if options.logfile is None:
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(options.logfile)
    handler.setFormatter(logutils.formatterMinimal)
    _log.addHandler(handler)

    calstrlist = ['============== ADCP calibrations =============\n',]
    warnlist = []


    procdirs = args[0]
    try:

        btstr, wtstr = uai.check_cals(procdir, '', name=options.sonar)
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

        xystr = uai.check_dxdy(procdir, '', name=options.sonar)
        calstrlist.append('\n'.join(['\n', xystr,
                      '------------------------------------------\n']))

        _log.info('\n'.join(calstrlist))
        if len(warnlist) > 0:
            _log.info('\n'.join(warnlist))
            _log.info('\n')

    except:
        raise(IOError, 'could not write calibration information')
