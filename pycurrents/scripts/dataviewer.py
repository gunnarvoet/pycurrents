#!/usr/bin/env python


import sys
import logging
from pycurrents.adcpgui_qt.argument_parsers import dataviewer_option_parser
from pycurrents.adcpgui_qt.gui_assembler import GuiApp

from pycurrents.system.logutils import setLoggerFromOptions

# Standard logging
_log = logging.getLogger(__file__)

# Parse command line inputs
options = dataviewer_option_parser(sys.argv[1:])
# set-up logger
setLoggerFromOptions(options)
# Kick-start application
guiApp = GuiApp(options)
