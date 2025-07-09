#!/usr/bin/env python

import sys
import os
import logging

# Standard logging
_log = logging.getLogger(__file__)
# Usage
usage = """
This graphical tool  aims to help the conversion/reformatting of
VmDAS' ENR data into UHDAS-style data."""
# Parse inputs
arglist = sys.argv[1:]
# Determine which version of Python we are dealing with
py_version = sys.version_info[0]
# Import accordingly & run GUI accordingly
if py_version >= 3.:
    from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
    from pycurrents.adcpgui_qt.forms.reform_vmdas_form import ReformVMDASForm
    # Parsing command line inputs
    from argparse import ArgumentParser
    arglist = sys.argv[1:]
    parser = ArgumentParser(usage=usage)

    help = "Path to project directory"
    parser.add_argument(
        "--project_dir_path", dest="proc_dir_path",
        type=str, default='./', help=help)

    help = "Path to VmDAS data directory"
    parser.add_argument(
        "--vmdas_dir_path", dest="vmdas_dir_path",
        nargs='?', type=str, default='', help=help)

    help = "Path to a location where uhdas-style cruise data will go  "
    help += " (ex.: uhdas_style_data)"
    parser.add_argument(
        "--uhdas_style_dir", dest="uhdas_source",
        nargs='?', type=str, default='', help=help)

    help = "Cruise name must be identical to the prefix used in *_proc.py"
    help += "\nEx.: ps0918_proc.py; cruisename = ps0918"
    parser.add_argument(
        "--cruisename", dest="cruisename",
        nargs='?', type=str, default='', help=help)

    help = "Sonar name (instrument type + frequency + ping type"
    help += " (ex.: os75bb)"
    parser.add_argument(
        "--sonar", dest="sonar",
        nargs='?', type=str, default='', help=help)

    help = "Starting path for browsing system files"
    parser.add_argument(
        "--start_path", dest="start_path",
        nargs='?', type=str, default=os.path.expanduser('~'),
        help=help)
    options = parser.parse_args(args=arglist)
    _log.debug(options)

    cruise_dir_path = os.getcwd()
    app = QApplication(sys.argv)
    form = ReformVMDASForm(proc_dir_path=options.proc_dir_path,
                           vmdas_dir_path=options.vmdas_dir_path,
                           cruisename=options.cruisename,
                           uhdas_source=options.uhdas_source,
                           sonar=options.sonar,
                           start_path=options.start_path,
                           called_from_form=False)
    form.show()
    sys.exit(app.exec_())
else:
    print("This script is only supported under python3")
    sys.exit(1)
