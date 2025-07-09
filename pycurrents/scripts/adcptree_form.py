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
    help = "proc_prefix must be identical to the prefix used in"
    help += "./config/*PROC_PREFIX*_proc.py. \n"
    help += "Ex.: [ps0918_os75_proc.py, ps0918_wh300_proc.py]; "
    help += "Valid proc_prefix = ps0918, ps0918_os75 or ps0918_wh300"
    parser.add_argument(
        "--proc_prefix", dest="proc_prefix",
        nargs='?', type=str, default=[''],
        help=help)
    help = "Path to cruise directory."
    help += "\nN.B: This option should not be used when adcptree_form is "
    help += "\n     launch from your cruise processing directory"
    parser.add_argument(
        "--cruisedirpath", dest="cruisedir",
        nargs='?', type=str, default=os.getcwd(),
        help=help)
    help = "Use if ADCP data was created from ENR files"
    parser.add_argument("--from_enr", dest="from_enr", action='store_true',
                        help=help)
    help = "Switches on debug level logging and writes in ./debug.log"
    parser.add_argument("--debug", dest="debug", action='store_true',
                        help=help)
    options = parser.parse_args(args=arglist)
    # set-up logger
    setLoggerFromOptions(options)
    # Kick-start application
    from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
    from pycurrents.adcpgui_qt.forms.adcp_tree_form import ProcSelectorPopUp
    from pycurrents.adcpgui_qt.lib.qtpy_widgets import globalStyle

    options.cruisedir = os.path.abspath(options.cruisedir)
    app = QApplication(sys.argv)
    app.setStyle(globalStyle)
    form = ProcSelectorPopUp(proc_prefix=options.proc_prefix[0],
                             cruise_dir=options.cruisedir,
                             from_enr=options.from_enr)
    sys.exit(app.exec_())
else:
    print("This script is only supported under python3")
    sys.exit(1)
