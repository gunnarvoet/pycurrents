#!/usr/bin/env  python
import os
import sys
import logging
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
from pycurrents.adcpgui_qt.forms.uhdas_proc_gen_form import UHDASProcGenForm

# Standard logging
_log = logging.getLogger(__file__)

description = """This Tool will help you re-processing a UHDAS database from scratch."""

if __name__ == "__main__":
    # Replacing with new form
    from argparse import ArgumentParser

    arglist = sys.argv[1:]
    parser = ArgumentParser(description=description)
    help = "Path to UHDAS directory. Default: ./"
    parser.add_argument(
        "--uhdas_dir", dest="uhdas_dir",
        nargs='?', type=str, default=os.getcwd(), help=help)
    help = "Path to project directory, Default: ./"
    parser.add_argument(
        "--project_path", dest="project_path",
        nargs='?', type=str, default=os.getcwd(),
        help=help)
    parser.add_argument(
        "--shipkey", dest="shipkey", default=None,
        help="Ship abbreviation. "
             "If not provided, the code will attempt to guess it")
    options = parser.parse_args(args=arglist)
    _log.debug(options)

    app = QApplication(sys.argv)
    form = UHDASProcGenForm(
        uhdas_dir=options.uhdas_dir,
        project_path=options.project_path,
        ship_key=options.shipkey)
    form.show()
    sys.exit(app.exec_())

