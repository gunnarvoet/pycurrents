#!/usr/bin/env python

"""
This is best run from the "edit" directory of an ADCP processing tree.
Run as:

         gautoedit.py

If it complains about "beamangle missing",
   you must specify the beam angle: (usually 20 or 30)

         gautoedit.py  --beamangle 30

"""

import sys

from pycurrents.system.logutils import setLoggerFromOptions
from pycurrents.adcpgui_qt.argument_parsers import dataviewer_option_parser
from pycurrents.adcpgui_qt.gui_assembler import GuiApp

# Parse inputs & Force edit mode in arglist
arglist = sys.argv[1:]
arglist.append('-e')

# Parsing command line inputs
options = dataviewer_option_parser(arglist)
# set-up logger
setLoggerFromOptions(options)
# Kick-start application
guiApp = GuiApp(options)
