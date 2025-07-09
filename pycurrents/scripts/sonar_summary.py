#!/usr/bin/env python
'''
logging_summary.py uhdas_dir

--help             : print help and exit

'''

import os
import glob
import logging

from pycurrents.adcp.rbin_stats import RbinSegments
from pycurrents.adcp.uhdas_defaults import uhdas_adcps
import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.system import logutils
import argparse


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description="report about sonar activity (on/off, by frequency)")



    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help='verbose: print everything')

    parser.add_argument('-u', '--uhdas_dir',
                        default='/home/adcp/cruise',
                        help='UHDAS cruise directory')

    parser.add_argument('-o', '--outfile',
                        help='write output to this file (otherwise screen)')

    opts = parser.parse_args()

    uhdas_dir = opts.uhdas_dir
    if uhdas_dir[-1] == '/':
        uhdas_dir=uhdas_dir[:-1]


    logging.captureWarnings(True)
    _log = logging.getLogger()
    _log.setLevel(logging.INFO)

    if opts.outfile is None:
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(opts.outfile)
    handler.setFormatter(logutils.formatterMinimal)
    _log.addHandler(handler)


    rawdirs=pathops.make_filelist(os.path.join(uhdas_dir, 'raw','*'))
    adcps = []
    for rawdir in rawdirs:
        r = os.path.basename(rawdir)
        if r in uhdas_adcps:
            adcps.append(r)

    plist = ['\n============ %s =============\n' % (uhdas_dir)]
    for adcp in adcps:
        fileglob = os.path.join(uhdas_dir, 'raw', adcp, '*bin')
        if len(glob.glob(fileglob)) > 0:
            filelist=pathops.make_filelist(fileglob)
            alias = dict(unix_dday='u_dday', monotonic_dday='m_dday',
                     logger_dday='u_dday', bestdday='dday')
            LS = RbinSegments(filelist, alias=alias, sonar=adcp)
            plist.append('\n'.join(['#------------  %s -----------' % (adcp),
                                 LS.pretty_print(),
                                    '\n']))
        else:
            plist.append('\n'.join(['#------------  %s -----------' % (adcp),
                                    'no files found',
                                    '\n']))
    _log.info('\n'.join(plist) + '\n-------------------------------\n')
