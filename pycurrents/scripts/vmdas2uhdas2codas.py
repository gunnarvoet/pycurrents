#!/usr/bin/env python

import sys
import os
import logging

from pycurrents.system.logutils import setLoggerFromOptions

# Standard logging
_log = logging.getLogger(__file__)

# Parse inputs
arglist = sys.argv[1:]
# Determine which version of Python we are dealing with
py_version = sys.version_info[0]
# Import accordingly & run GUI accordingly
if py_version >= 3.:
    # Parsing command line inputs
    from argparse import ArgumentParser
    arglist = sys.argv[1:]
    parser = ArgumentParser()
    help = "Starting path for browsing system files"
    parser.add_argument(
        "--start_path", dest="start_path",
        nargs='?', type=str, default=os.getcwd(),
        help=help)
    help = "Switches on debug level logging and writes in ./debug.log"
    parser.add_argument("--debug", dest="debug", action='store_true',
                        help=help)
    options = parser.parse_args(args=arglist)
    # adding launch_path variable
    options.launch_path = os.getcwd()
    # set-up logger
    setLoggerFromOptions(options)
    # Kick-start application
    from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
    from pycurrents.adcpgui_qt.forms.vmdas_dispatch_form import PickDirectoryPopUp
    from pycurrents.adcpgui_qt.lib.qtpy_widgets import globalStyle
    app = QApplication(sys.argv)
    app.setStyle(globalStyle)
    form = PickDirectoryPopUp(start_path=options.start_path,
                              launch_path=options.launch_path)
    form.show()
    sys.exit(app.exec_())
else:
    print("This script is only supported under python3")
    sys.exit(1)
