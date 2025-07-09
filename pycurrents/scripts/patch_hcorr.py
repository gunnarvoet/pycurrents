#!/usr/bin/env python

import sys
import os
import logging

from pycurrents.system.logutils import setLoggerFromOptions

# Standard logging
_log = logging.getLogger(__file__)

# Usage
usage = '''
Procedure:
(1) view hcorr*.png
(2) if there are gaps or if the tools above are useful, run "patch_hcorr_app.py"
    from inside the sonar processing, "cal" or "rotate" directories
(3) edit gaps using the patch_hcorr App

This App:
 - reads "ens_hcorr.asc" and plots components
 - allows simple graphical editing of the file to
     + cut out chunks (interpolates through them)
     + trim outliers by
            * using "cleaner" (removes spiks by using 2nd derivative)
            * median filter cutoff (set filter length, threshold)
            * box filter
 - Edit button:
     + mask out points using standard selection tools (rectangle, polygon,...)
 - Save button:
     + write new ascii files:
                 "newhcorr.asc" (for figures)
                 "newhcorr.ang" (apply to the database)
     + make figures showing new heading correction (newhcorr*.png)
     + stages "unrotate.tmp"
     + stages "rotate_fixed.tmp"
 - Apply and Edit button:
     + run "rotate unrotate.tmp" to remove the original heading corrections
     + run "rotate rotate_fixed.tmp" to apply newhcorr.ang to the database
     + rerun the navigation steps using the following command:
           cd ../..     #go back to the root sonar processing directory
           quick_adcp.py --steps2rerun navsteps:calib --auto

NOTES:
(1) You must delete newhcorr* before you start
(2) "unrotate.tmp" resets the calibrations to
     - phase correction 0.0
     - scale factor     1.0
    If you already applied any fixed phase or scale factor
    you must apply them again.
'''

arglist = sys.argv[1:]
from argparse import ArgumentParser
arglist = sys.argv[1:]
parser = ArgumentParser(usage=usage, add_help=True)
help = "Path to ens_hcorr.asc file"
parser.add_argument(
    "--ens_hcorr_path", dest="ens_hcorr_path",
    nargs='?', type=str, default='',
    help=help)
help = "Sonar name, ADCP+frequency+mode (see applicable), ex.: os75nb, wh300"
parser.add_argument(
    "--sonar", dest="sonar",
    nargs='?', type=str, default=None,
    help=help)
help = "Database's year base, YYYY, ex.: 2018"
parser.add_argument(
    "--yearbase", dest="yearbase",
    nargs='?', type=int, default=None,
    help=help)
help = "Switches on debug level logging and writes in ./debug.log"
parser.add_argument("--debug", dest="debug", action='store_true',
                    default=False, help=help)
options = parser.parse_args(args=arglist)
# set-up logger
setLoggerFromOptions(options)
# Kick-start application
from pycurrents.adcpgui_qt.apps.patch_hcorr_app import PatchHcorrApp

PatchHcorrApp(
    working_dir=os.getcwd(),
    sonar=options.sonar,
    yearbase=options.yearbase,
    ens_hcorr_path=options.ens_hcorr_path)
