#!/usr/bin/env python

import sys
import logging

from argparse import ArgumentParser

from pycurrents.system.logutils import setLoggerFromOptions
from pycurrents.adcpgui_qt.apps.plot_rbins_app import PlotRbinApp

# Standard logging
_log = logging.getLogger(__file__)


usage = '''
This is a simple rbin plotter -- plot one or 2 sets of y versus the same x
-  choose abcissa (radio button)
-  plot against chosen ordinates in subplots
-  one color per instrument; one subplot per ordinate
-  for each field that is duplicated, plot the difference as well.
-       differences in lon or lat ar plotted in meters


specify rbin directory, instrument directory, and message name:
 eg:
plot_rbins.py --ser1 posmv:pmv --ser2 gyro:hnc uhdasdir
plot_rbins.py  -s gyro:hnc --step 10  uhdasdir
'''

arglist = sys.argv[1:]
parser = ArgumentParser(usage=usage)
parser.add_argument("uhdas_dir", help="path to UHDAS directory")
parser.add_argument("--ser1", "-s", dest='ser1', required=True,
                    help="inst:msg1 - serial instrument #1"
                         "  inst=directory, msg=rbin message")
parser.add_argument("--ser2", dest='ser2', default=None,
                    help="inst:msg2 - serial instrument #2"
                         "  inst=directory, msg=rbin message")
parser.add_argument("--step", dest='step', default=1,
                    help="step size - extract every Nth message"
                         " (default is every step)\n"
                         "(speeds up plotting, might create problems"
                         " with differences)")
parser.add_argument("--splitchar", dest='splitchar', default=':',
                    help="specify different splitter. Ex.: "
                         "use  --splitchar ','  and --ser1 inst,msg "
                         "--ser2 inst,msg")
parser.add_argument("--shift", dest='shift', default=0,
                    help='add seconds to ser1')
parser.add_argument("--ddrange", dest='ddrange', default=None,
                    help='colon-delimited integer decimal day range')
parser.add_argument("--masked", action="store_true", dest="masked",
                    default=False,
                    help="use QC masks when plotting "
                         "(eg. ashtech, posmv, seapath)")
parser.add_argument("--markersize", dest="marker_size", default=2,
                    type=int, help="Marker size. default is 2; max. is 6")
parser.add_argument("--max_dx", dest="max_dx", default=None, type=float,
                    help="maximum gap for interpolation")
parser.add_argument("--debug", dest="debug", action='store_true',
                    default=False, help="Switches on debug level logging and "
                                        "writes in ./debug.log")
options = parser.parse_args(args=arglist)

# set-up logger
setLoggerFromOptions(options)

# Kick-start application
PlotRbinApp(uhdas_dir=options.uhdas_dir,
            rname1=options.ser1,
            rname2=options.ser2,
            step=options.step,
            shift=options.shift,
            splitchar=options.splitchar,
            marker_size=options.marker_size,
            max_dx=options.max_dx,
            ddrange=options.ddrange,
            masked=options.masked)


