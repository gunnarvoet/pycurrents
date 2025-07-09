#!/usr/bin/env python3

import os
import sys
import logging
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QFileDialog, QMainWindow, QWidget, QGridLayout, QApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QIcon
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt

from pycurrents.adcpgui_qt.lib.qtpy_widgets import (iconUHDAS, CustomLabel,
    CustomPushButton, make_busy_cursor, restore_cursor, globalStyle)
from pycurrents.adcpgui_qt.lib.miscellaneous import list_vmdas_files
from pycurrents.adcpgui_qt.forms.string_templates import ARCHITECTURE_REQUIREMENT_MSG
from pycurrents.adcpgui_qt.forms.vmdas_converter_form import VmdasConversionForm


# Standard logging
_log = logging.getLogger(__name__)

# TODO: change text and variable names accordingly with naming convention


class PickDirectoryPopUp(QMainWindow):
    def __init__(self, launch_path=os.getcwd(),
                 start_path=os.path.expanduser('~'),
                 parent=None):
        """
        Pop-up browsing window aiming to help user setting up their data for
        post-processing with dataviewer & co.

        Args:
            launch_path: starting path for the next forms, str.
            start_path: starting path for browsing file system, str.
            parent: PySide6 or PyQt5 parent widget
        """
        super().__init__(parent)
        # Attributes
        self.launch_path = os.path.abspath(launch_path)
        self.start_path = os.path.abspath(start_path)
        self.data_dir = ''
        self.enr_files = []
        self.lta_files = []
        self.sta_files = []
        # Form style
        self.setWindowIcon(QIcon(iconUHDAS))
        self.setWindowTitle('UHDAS Form Dispatcher')
        # Widget, layout & connection
        # - central widget
        self.textLabel = CustomLabel('\n'.join([
            "         - Select VMDAS ADCP data directory - \n",
            "Notes: contains *.LTA, *.STA, *.ENR, *.N1R,... type files",
            ]),
                                     style='h2', parent=self)
#        self.textLabel.setAlignment(Qt.AlignCenter)
        self.textLabel.setAlignment(Qt.AlignLeft)
        self.browseButton = CustomPushButton("Browse", self)
        self.browseButton.clicked.connect(self.on_select_dir)
        self.row = 0
        self.box = QWidget(parent=self)
        self.boxLayout = QGridLayout()
        self.box.setLayout(self.boxLayout)
        self.boxLayout.addWidget(self.textLabel, self.row, 0, 1, 3)
        self.row += 1
        self.boxLayout.addWidget(self.browseButton, self.row, 1, 1, 1)
        self.setCentralWidget(self.box)

    # Slots
    def on_select_dir(self, selected_dir=''):
        make_busy_cursor()
        if not selected_dir:
            selected_dir = QFileDialog.getExistingDirectory(
                caption='Select VMDAS ADCP data directory',
                directory=self.start_path,
                parent=self,
                options=QFileDialog.DontUseNativeDialog)
        self.data_dir = selected_dir
        self.enr_files, self.lta_files, self.sta_files = list_vmdas_files(
            selected_dir)
        if not (self.enr_files or self.lta_files or self.sta_files):
            msg = '- NO VALID DATA WERE FOUND -\n'
            msg += 'VmDAS dir. must contain either *.ENR, *.LTA or *.STA files\n'
            msg += '- Try again -'
            self.textLabel.setText(msg)
            restore_cursor()
            return
        elif self.enr_files or self.lta_files or self.sta_files:
            # N.B.: defining 'parent' is necessary to launch the next form
            next_form = VmdasConversionForm(
                cruise_dir=self.launch_path,
                vmdas_dir=self.data_dir, start_path=self.start_path,
                enr_files=self.enr_files, lta_files=self.lta_files,
                sta_files=self.sta_files, parent=self)
            next_form.show()
            self.hide()
            restore_cursor()
            return
        else:
            msg = "Your data structure is corrupted"
            _log.error(msg)
            _log.debug(msg)
            print(ARCHITECTURE_REQUIREMENT_MSG)
            sys.exit(1)


if __name__ == '__main__':
    from argparse import ArgumentParser
    ch = logging.StreamHandler(sys.stdout)
    logging.basicConfig(handlers=[ch], level=logging.DEBUG)

    arglist = sys.argv[1:]
    parser = ArgumentParser()
    help = "Starting path for browsing system files"
    parser.add_argument(
        "--start_path", dest="start_path",
        nargs='?', type=str, default=os.path.expanduser('~'),
        help=help)
    options = parser.parse_args(args=arglist)

    app = QApplication(sys.argv)
    app.setStyle(globalStyle)
    form = PickDirectoryPopUp(start_path=options.start_path)
    form.show()
    sys.exit(app.exec_())
