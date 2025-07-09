#!/usr/bin/env python

import sys
import os
import logging
from argparse import ArgumentParser

# Standard logging
_log = logging.getLogger(__file__)

# Usage:
usage = """
Gui for creating configuration file proc_starter.cnt

Notes: see 'reform_vmdas_form.py' to set up 'reform_defs.py' file prior to
       run "proc_starter.py reform_defs.py"
"""
# Parse inputs
arglist = sys.argv[1:]
# Determine which version of Python we are dealing with
py_version = sys.version_info[0]
# Import accordingly & run GUI accordingly
if py_version >= 3.:
    from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
    from pycurrents.adcpgui_qt.forms.proc_starter_form import ProcStarterForm
    parser = ArgumentParser(usage=usage)
    help = "Path to reform_defs_*.py. Must be in *CRUISE_PROC_DIR*/config/"
    parser.add_argument(
        "reform_defs_path", metavar='reform_defs_path',
        type=str, help=help)
    help = "Switch to "
    help = "Path to config directory"
    parser.add_argument(
        "--config_path", dest="config_path",
        nargs='?', type=str, default='', help=help)
    help = "Starting path for browsing system files"
    parser.add_argument(
        "--start_path", dest="start_path",
        nargs='?', type=str, default=os.path.expanduser('~'),
        help=help)
    options = parser.parse_args(args=arglist)
    _log.debug(options)

    app = QApplication(sys.argv)
    form = ProcStarterForm(options.reform_defs_path,
                           config_path=options.config_path,
                           start_path=options.start_path,
                           called_from_form=False)
    form.show()
    sys.exit(app.exec_())
else:
    print("This script is only supported under python3")
    sys.exit(1)
