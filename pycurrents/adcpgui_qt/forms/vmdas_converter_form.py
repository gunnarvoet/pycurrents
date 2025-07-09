#!/usr/bin/env python3

import os
import sys
import logging
from glob import glob
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QFileDialog, QLabel, QLineEdit, QApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QFont
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt
from numpy import unique

# BREADCRUMB: common library, begin block...
from pycurrents.system.logutils import unexpected_error_msg
from pycurrents.adcp.adcp_specs import adcps
from pycurrents.adcp.vmdas import guess_sonars
from pycurrents.adcp.raw_rdi import instname_from_file
# BREADCRUMB: ...common library, end block
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomLabel,
    CustomPushButton, FileNameValidator, CruisenameValidator, make_busy_cursor,
    restore_cursor, )
from pycurrents.adcpgui_qt.lib.miscellaneous import list_vmdas_files
from pycurrents.adcpgui_qt.forms.generic_form import GenericForm
from pycurrents.adcpgui_qt.forms.reform_vmdas_form import ReformVMDASForm
from pycurrents.adcpgui_qt.forms.string_templates import DATAVIEWER_READY_MSG

# Standard logging
_log = logging.getLogger(__name__)

# TODO: change text and variable names accordingly with naming convention


class VmdasConversionForm(GenericForm):
    def __init__(self, vmdas_dir, cruise_dir='',
                 start_path=os.path.expanduser('~'),
                 enr_files=[], lta_files=[], sta_files=[],
                 parent=None):
        """
        Convert VmDAS’ LTA and STA data files to UHDAS-style data
        as well as prepare ENR files for conversion

        Args:
            vmdas_dir: absolute path to VmDAS data, str.
            cruise_dir: absolute path to cruise data directory, str.
            start_path: starting path for browsing system files, str.
            enr_files: list of *.ENR files, [str,...,str]
            lta_files: list of *.LTA files, [str,...,str]
            sta_files: list of *.STA files, [str,...,str]
            parent: PySide6 or PyQt5 parent widget
        """
        super().__init__(parent)
        # Attributes
        self.start_path = start_path
        self.vmdas_dir = vmdas_dir
        self.cruisename = 'cruise_name'
        self.cruise_dir = cruise_dir
        self.enr_files = enr_files
        self.lta_files = lta_files
        self.sta_files = sta_files
        if not (self.enr_files and self.lta_files and self.sta_files):
            self.enr_files, self.lta_files, self.sta_files = list_vmdas_files(
                self.vmdas_dir)
        self.instrument = self._get_instrument()
        # Sanity checks
        is_enr_ready = self.enr_files and self.nr_files_exist()
        is_lta_ready = self.lta_files
        is_sta_ready = self.sta_files
        if not (is_enr_ready or is_lta_ready or is_sta_ready):
            msg = 'No valid files were found in the given VmDAS directory'
            msg += '\nTry again with a different path than %s' % self.vmdas_dir
            if not self.nr_files_exist():
                msg += '\n*.N*R file(s) is(are) missing to proceed with *.ENR files'
            if not self.vmo_files_exist():
                msg += '\n*.VMO file is missing to proceed with *.STA and/or *.LTA'
            _log.error(msg)
            sys.exit(1)
        # Form style
        self.setWindowTitle('VmDAS to UHDAS Form')
        # Widget, layout & connection
        self.row = 0
        # - text label
        msg = "Choose a Project Directory and a cruisename, then"
        msg += '\nChoose a type of data to convert'
        self.textLabel = CustomLabel(msg, style='h2', parent=self)
        self.textLabel.setAlignment(Qt.AlignCenter)
        self.entriesLayout.addWidget(self.textLabel, self.row, 0, 1, 3)
        # - VmDAS dir. info. text
        self.row += 1
        self.vmdasDataPreLabel = CustomLabel(
            'VmDAS data directory:', style='h3')
        self.entriesLayout.addWidget(self.vmdasDataPreLabel, self.row, 0, 1, 1)
        self.vmdasDataLabel = QLabel(self.vmdas_dir, parent=self)
        self.vmdasDataLabel.setWordWrap(True)
        self.entriesLayout.addWidget(self.vmdasDataLabel, self.row, 1, 1, 2)
        # - project dir.
        self.row += 1
        self.browseButton2 = CustomPushButton("Browse", self)
        self.cruiseDirEntry = QLineEdit(self.cruise_dir, parent=self)
        self.cruiseDirEntry.setValidator(FileNameValidator(parent=self))
        self.cruiseDirEntry.textChanged.connect(self.on_cruise_dir_change)
        self.cruiseDirLabel = CustomLabel(
            "Select/Create Project Directory:",
            style='h3', parent=self)
        self.entriesLayout.addWidget(self.cruiseDirLabel, self.row, 0)
        self.entriesLayout.addWidget(self.cruiseDirEntry, self.row, 1)
        self.entriesLayout.addWidget(self.browseButton2, self.row, 2)
        self.browseButton2.clicked.connect(self.on_select_cruise_dir)
        # - cruisename entry
        self.row += 1
        self.cruiseNameEntry = QLineEdit(self.cruisename, parent=self)
        self.cruiseNameEntry.setValidator(CruisenameValidator(parent=self))
        self.cruiseNameLabel = CustomLabel(
          'Specify cruise name (short, e.g.: ps0918):', style='h3', parent=self)
        self.entriesLayout.addWidget(self.cruiseNameLabel, self.row, 0)
        self.entriesLayout.addWidget(self.cruiseNameEntry, self.row, 1, 1, 1)
        self.cruiseNameEntry.textChanged.connect(self.on_cruise_name_change)
        self.row += 1
        self.infoStr = """
This name will be used in 2 places:
    (1) ... In the Project Directory: (processing dir. = %s_%s_ENR)
    (2) ... In the configuration files: (config/%s_%s_proc.py)
                        """
        self.infoLabel = QLabel(
            self.infoStr % (self.cruisename, self.instrument,
                            self.cruisename, self.instrument),
            parent=self)
        self.infoLabel.setWordWrap(True)
        self.infoLabel.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(self.infoLabel, self.row, 0, 1, 3)
        #
        # - action buttons
        self.row += 1
        self.ltaButton = CustomPushButton("Convert *.LTA Files", self)
        self.entriesLayout.addWidget(self.ltaButton, self.row, 0, 1, 3)
        self.ltaButton.clicked.connect(self._run_lta_proc)
        self.row += 1
        self.staButton = CustomPushButton("Convert *.STA Files", self)
        self.entriesLayout.addWidget(self.staButton, self.row, 0, 1, 3)
        self.staButton.clicked.connect(self._run_sta_proc)
        self.row += 1
        self.enrButton = CustomPushButton("Convert *.ENR Files", self)
        self.entriesLayout.addWidget(self.enrButton, self.row, 0, 1, 3)
        self.enrButton.clicked.connect(self._launch_reform_vmdas_form)
        #  * make invisible to start with
        if not is_enr_ready:
            self.enrButton.setVisible(False)
        if not is_lta_ready:
            self.ltaButton.setVisible(False)
        if not is_sta_ready:
            self.staButton.setVisible(False)

    # Slots
    def on_select_cruise_dir(self):
        selected_dir = QFileDialog.getExistingDirectory(
            caption='Select project directory',
            directory=self.start_path,
            parent=self,
            options=QFileDialog.DontUseNativeDialog)
        if selected_dir:
            self.cruise_dir = selected_dir
            self.cruiseDirEntry.setText(selected_dir)

    def on_cruise_dir_change(self):
        typed_text = self.cruiseDirEntry.text()
        self.cruise_dir = typed_text
        _log.debug("Cruise dir: " + self.cruise_dir)

    def on_cruise_name_change(self):
        typed_text = self.cruiseNameEntry.text()
        self.cruisename = typed_text
        msg = self.infoStr % (self.cruisename, self.instrument,
                              self.cruisename, self.instrument)
        self.infoLabel.setText(msg)
        _log.debug("Cruise Name: " + self.cruisename)
        _log.debug("Cruise Data dir: " + self.cruise_dir)

    # Local lib
    def _run_lta_proc(self):
        """
        Run vmdas_quick_ltaproc.py command for lta data (+ some sanity checks)
        """
        # Sanity checks
        if not self.are_entries_filled():
            return
        sonars = self.get_sonars_list_from_files(self.lta_files)
        if not sonars:
            msg = "No available sonars were found in the LTA files."
            msg += "\nSomething is wrong with the raw data"
            self._print(msg, color='red')
            return
        for sonar in sonars:
            print("Sonar: ", sonar)
            lta_dir = os.path.join(self.cruise_dir, sonar + "_LTA")
            if self._exists(lta_dir):
                return
        # Make cruise directory & config
        self.make_cruise_directory()
        # Run command
        arg_list = ["vmdas_quick_ltaproc.py",
                    "--cruisename", self.cruisename,
                    "--procroot", self.cruise_dir,
                    os.path.join(self.vmdas_dir, '*.LTA'),
                    "--force"]
        comment = "- getting data information; processing, generating hints\n"
        comment += '- running this:\n%s' % (' '.join(arg_list))
        self.run_command(arg_list, comment=comment)
        # Inform User
        # - in log area
        info_file_name = self.cruise_dir + "/"
        info_file_name += self.cruisename + "_"
        info_file_name += self.instrument + "_LTA_info.txt"
        # self._print(DATAVIEWER_READY_MSG % (info_file_name, lta_dir),
        #             color='red')
        self._print("", color='red')  # turn text in red
        print(DATAVIEWER_READY_MSG % (info_file_name, lta_dir))

    def _run_sta_proc(self):
        """
        Run vmdas_quick_ltaproc.py command for sta data (+ some sanity checks)
        """
        # Sanity checks
        if not self.are_entries_filled():
            return
        sonars = self.get_sonars_list_from_files(self.sta_files)
        if not sonars:
            msg = "No available sonars were found in the STA files."
            msg += "\nSomething is wrong with the raw data"
            self._print(msg, color='red')
            return
        for sonar in sonars:
            sta_dir = os.path.join(self.cruise_dir, sonar + "_STA")
            if self._exists(sta_dir):
                return
        # Make cruise directory & config
        self.make_cruise_directory()
        # Run command
        arg_list = ["vmdas_quick_ltaproc.py",
                    "--cruisename", self.cruisename,
                    "--procroot", self.cruise_dir,
                    os.path.join(self.vmdas_dir, '*.STA'),
                    "--force"]
        comment = "- getting data information; processing, generating hints\n"
        comment += '- running this:\n%s' % (' '.join(arg_list))
        self.run_command(arg_list, comment=comment)
        # Inform User
        # - in log area
        info_file_name = self.cruise_dir + "/"
        info_file_name += self.cruisename + "_"
        info_file_name += self.instrument + "_STA_info.txt"
        # self._print(DATAVIEWER_READY_MSG % (info_file_name, sta_dir),
        #             color='red')
        self._print("", color='red')  # turn text in red
        print(DATAVIEWER_READY_MSG % (info_file_name, sta_dir))

    def _launch_reform_vmdas_form(self):
        """
        Launch the next form (that is ReformVMDASForm) and close the current
        form.
        """
        make_busy_cursor()
        # - sanity checks
        if not self.are_entries_filled():
            restore_cursor()
            return
        # if self._exists(os.path.join(
        #         self.cruise_dir, self.instrument + "_ENR")):
        #     return
        # - create adcp and config directories
        self.make_cruise_directory()
        # - find instrument type (inst_type)
        if not self.instrument:
            restore_cursor()
            return
        inst_type = self.instrument[:2]  # FIXME: assumes that sonar type contained in the first 2 letters
        # - generate enr_info.txt
        dest_dir = os.path.join(
            self.cruise_dir, self.instrument + '_enr_info.txt')
        arg_list = ["vmdas_info.py", "--logfile",
                    dest_dir,
                    inst_type,
                    os.path.join(self.vmdas_dir, '*ENR')]
        comment = '- getting information about vmdas files\n'
        comment+= '- running this:\n%s' % (' '.join(arg_list))
        self.run_command(arg_list, comment=comment)
        # - launch next form
        # N.B.: defining 'parent' is necessary to launch the next form
        next_form = ReformVMDASForm(proc_dir_path=self.cruise_dir,
                                    vmdas_dir_path=self.vmdas_dir,
                                    cruisename=self.cruisename,
                                    sonar=self.instrument,
                                    start_path=self.start_path,
                                    parent=self)
        # - pass on current text to next form
        next_form._print(self.logTextArea.toPlainText(), color='green')
        next_form._print(
            "\nYou can now proceed and create your conversion file(s)",
            color='red')
        next_form.show()
        self.hide()
        restore_cursor()

    def are_entries_filled(self):
        """
        Check if all entries are filled properly
        """
        if not (self.cruisename and self.vmdas_dir and self.cruise_dir):
            msg = 'Please fill-in every entries and try again.'
            self._print(msg, color='red')
            msg = "cruisename, vmdas_dir, cruise_dir: " + ' '.join(
                [self.cruisename, self.vmdas_dir, self.cruise_dir])
            _log.debug(msg)
            return False
        # Additional sanity check
        elif self.cruisename == 'cruise_name':
            msg = 'Please change the cruise name and try again'
            self._print(msg, color='red')
            return False
        else:
            return True

    def nr_files_exist(self):
        """
        Check if *.N*R are present
        """
        return len(glob(os.path.join(self.vmdas_dir, "*.N*R"))) > 0

    def vmo_files_exist(self):
        """
        Check if *.VMO are present
        """
        return len(glob(os.path.join(self.vmdas_dir, "*.VMO"))) > 0

    def make_cruise_directory(self):
        """
        Make "cruise" and "config" directories if not already there
        """
        if not os.path.exists(self.cruise_dir):
            os.makedirs(self.cruise_dir)
        if not os.path.exists(self.config_path):
            os.makedirs(self.config_path)

    # FIXME: move to common lib
    @staticmethod
    def get_sonars_list_from_files(file_list):
        """
        Get list of available sonars based on files list

        Args:
            file_list: list of file paths, [str,...,str]

        Returns: list of sonars, [str,...,str]
        """
        sonars_tuples = guess_sonars(file_list)
        sonars = []
        for t in sonars_tuples:
            inst_type = t[0]
            ping_types = t[1].keys()
            for ping_type in ping_types:
                # bug fix for Ticket 1325
                if ('bb' in inst_type or 'wh' in inst_type):
                    sonars.append(inst_type)
                else:
                    sonars.append(inst_type + ping_type)
        sonars = list(unique(sonars))
        return sonars

    # Dynamic attributes
    def _get_instrument(self):
        """
        Returns instrument type (str.) from *.LTA, *.STA or *.ENR file(s)
        """
        inst_found = False
        sonar = ''
        if self.enr_files:
            files = self.enr_files
        elif self.sta_files:
            files = self.sta_files
        elif self.lta_files:
            files = self.lta_files
        else:
            return sonar
        for adcp in adcps:
            for f in files:
                try:
                    inst_name = instname_from_file(f)
                except Exception as err:  # super permissive in purpose
                    _log.error(unexpected_error_msg(err))
                    continue
                if adcp == inst_name and not inst_found:
                    sonar = adcp
                    inst_found = True
                elif adcp == inst_name and inst_found and sonar != adcp:
                    msg = 'DATASET CORRUPTED: several sonar were found'
                    _log.critical(msg)
                    msg += '\nAddress and try again'
                    self.textLabel.setText(msg)
                    break
        if not inst_found:
            msg = 'DATASET CORRUPTED: no sonar were found'
            _log.critical(msg)
            msg += '\nAddress and try again'
            print(msg)
            sys.exit(1)
        return sonar

    def _get_config_path(self):
        return os.path.join(self.cruise_dir, 'config')

    # instrument = property(_get_instrument)
    config_path = property(_get_config_path)


if __name__ == '__main__':
    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        from pycurrents.get_test_data import get_test_data_path
        test_folder_path = get_test_data_path()
        vmdas_dir_path = test_folder_path + '/vmdas_data/os75/'
        app = QApplication(sys.argv)
        form = VmdasConversionForm(vmdas_dir_path)
        form.show()
        sys.exit(app.exec_())
    else:
        from argparse import ArgumentParser
        arglist = sys.argv[1:]
        parser = ArgumentParser()
        help = 'Path to VmDAS data directory'
        parser.add_argument(
            "vmdas_dir", metavar='vmdas_dir',
            type=str, nargs='?', default='',
            help=help)
        help = "Path to project directory"
        parser.add_argument(
            "--project_dir", dest="cruise_dir",
            nargs='?', type=str, default='',
            help=help)
        help = 'list of *.ENR files'
        parser.add_argument("--enr_files", dest="enr_files", nargs='+',
                            default=[], help=help)
        help = 'list of *.LTA files'
        parser.add_argument("--lta_files", dest="lta_files", nargs='+',
                            default=[], help=help)
        help = 'list of *.STA files'
        parser.add_argument("--sta_files", dest="sta_files", nargs='+',
                            default=[], help=help)
        help = "Starting path for browsing system files"
        parser.add_argument(
            "--start_path", dest="start_path",
            nargs='?', type=str, default=os.path.expanduser('~'),
            help=help)
        options = parser.parse_args(args=arglist)

        app = QApplication(sys.argv)
        form = VmdasConversionForm(options.vmdas_dir,
                                   cruise_dir=options.cruise_dir,
                                   lta_files=options.lta_files,
                                   sta_files=options.sta_files,
                                   enr_files=options.enr_files,
                                   start_path=options.start_path)
        form.show()
        sys.exit(app.exec_())
