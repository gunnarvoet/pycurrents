#!/usr/bin/env python3

import os
import sys
import logging
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QFileDialog, QLineEdit, QLabel, QWidget
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QHBoxLayout, QApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QFont
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt

# BREADCRUMB: common library, begin block...
from pycurrents.system import pathops
from pycurrents.system.logutils import unexpected_error_msg
from pycurrents.text.formats import Templater
from pycurrents.adcp.vmdas import VmdasNavInfo
from pycurrents.adcp.raw_multi import Multiread
from pycurrents.adcp.adcp_specs import adcps
from pycurrents.adcp.raw_rdi import instname_from_file
from pycurrents.adcp.vmdas import FakeUHDAS
# BREADCRUMB: ...common library, end block
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomPushButton,
    CustomLabel, FileNameValidator, CruisenameValidator, backGroundKey, blue,
    green, red, make_busy_cursor, restore_cursor)
from pycurrents.adcpgui_qt.forms.generic_form import GenericForm
from pycurrents.adcpgui_qt.forms.proc_starter_form import ProcStarterForm
from pycurrents.adcpgui_qt.forms.string_templates import (
    REFORMFILE_TEMPLATE, REFORMVAR_TEMPLATE, ARCHITECTURE_REQUIREMENT_MSG,
    REFORM_SUCCESS_MSG)

# Standard logging
_log = logging.getLogger(__name__)

# TODO: change text and variable names accordingly with naming convention


class ReformVMDASForm(GenericForm):
    def __init__(self, proc_dir_path='', vmdas_dir_path='', cruisename='',
                 uhdas_source='',
                 sonar='', start_path=os.path.expanduser('~'),
                 called_from_form=True, parent=None):
        """
        Class generating a form which aims to help the conversion/reformatting
        of VmDAS' ENR data into UHDAS-style data.

        Args:
            proc_dir_path: path to "processing directory"
                           (aka "cruise directory"), str.
            vmdas_dir_path: path to directory containing *.LTA, *.STA and/or
                            *.ENR files, str.
            cruisename: name of the cruise, str.
            sonar: name of the sonar used, ex.: os75, wh300,
                   instrument + frequency, str.
            start_path: path from where to start, str.
            parent: PySide6 or PyQt5 parent widget
        """
        super().__init__(parent)
        # Attributes
        self.called_from_form = called_from_form
        self.start_path = os.path.abspath(start_path)
        self.vmdas_dir = os.path.abspath(vmdas_dir_path)
        self.uhdas_source = os.path.abspath(uhdas_source)  # uhdas_style_data
        prefix = ''
        if sonar:
            prefix = "_%s" % sonar
        self.def_script_pyname = "reform_defs" + prefix + ".py"
        self.convert_script_pyname = "vmdas2uhdas" + prefix + ".py"
        self.ENRlist = []
        self.shipkey = 'zzz'
        self.cruisename = cruisename
        self.yearbase = ''
        self.sonar = sonar
        self.navinfo = None
        self.convert_script_path = ''
        self.def_script_path = ''
        self.cruise_dir = os.path.abspath(proc_dir_path)
        self.config = {}
        # This config dictionary will encapsulate all info. needed to be
        #  passed on to the next forms
        self._attribute_list = [
            'vmdas_dir', 'uhdas_dir', 'uhdas_source', 'def_script_pyname',
            'convert_script_pyname', 'ENRlist', 'shipkey',
            'sonar', 'cruisename', 'cruise_dir']
        self.varformat = dict(
            navinfo='list', yearbase='int', cruisename='string',
            uhdas_dir='string', vmdas_dir='string', adcp='string',
            shipkey='string')
        # Form style
        self.setWindowTitle('Reform VMDAS Form')
        # Widgets
        # - User entries
        self.entriesLayout.setColumnStretch(0, 1)
        self.entriesLayout.setColumnStretch(1, 3)
        self.entriesLayout.setColumnStretch(2, 1)
        #   * edit/choose processing directory
        if not self.cruise_dir:
            self.browseButton = CustomPushButton("Browse", self)
            self.dirEntry = QLineEdit(self.cruise_dir, parent=self)
            self.dirEntry.setValidator(FileNameValidator(parent=self))
            self.entriesLayout.addWidget(
                CustomLabel('Select Project Directory:',
                            style='h3', parent=self), self.row, 0)
            self.entriesLayout.addWidget(self.dirEntry, self.row, 1, 1, 2)
            self.entriesLayout.addWidget(self.browseButton, self.row, 3)
            # Connect
            self.browseButton.clicked.connect(self.on_select_cruise_dir)
            self.dirEntry.textChanged.connect(self.on_dir_change)
        else:
            self.entriesLayout.addWidget(CustomLabel(
                'Project directory: ', style='h3', parent=self),
                self.row, 0, 1, 1)
            self.cruiseDirLabel = QLabel(self.cruise_dir, parent=self)
            self.cruiseDirLabel.setWordWrap(True)
            self.entriesLayout.addWidget(self.cruiseDirLabel,
                                         self.row, 1, 1, 3)
        #   * choose VmDAS directory
        self.row += 1
        if not self.vmdas_dir:
            self.browseButton1 = CustomPushButton("Browse", self)
            self.dirEntry1 = QLineEdit(self.vmdas_dir, parent=self)
            self.dirEntry1.setValidator(FileNameValidator(parent=self))
            self.entriesLayout.addWidget(CustomLabel(
                'Select VmDAS data directory:', style='h3', parent=self),
                self.row, 0)
            self.entriesLayout.addWidget(self.dirEntry1, self.row, 1, 1, 2)
            self.entriesLayout.addWidget(self.browseButton1, self.row, 3)
            # Connect
            self.browseButton1.clicked.connect(self.on_select_vmdas_dir)
            self.dirEntry1.textChanged.connect(self.on_dir1_change)
        else:
            self.entriesLayout.addWidget(CustomLabel(
                'VmDAS data directory: ', style='h3', parent=self),
                self.row, 0, 1, 1)
            self.vmdasDirLabel = QLabel(self.vmdas_dir, parent=self)
            self.vmdasDirLabel.setWordWrap(True)
            self.entriesLayout.addWidget(self.vmdasDirLabel, self.row, 1, 1, 3)
        #   * choose UHDAS directory
        self.row += 1
        self.browseButton2 = CustomPushButton("Browse", self)
        self.dirEntry2 = QLineEdit(self.uhdas_source, parent=self)
        self.dirEntry2.setValidator(FileNameValidator(parent=self))
        self.entriesLayout.addWidget(
            CustomLabel('Select/Create directory\nfor UHDAS-style data:',
                        style='h3', parent=self), self.row, 0)
        self.entriesLayout.addWidget(self.dirEntry2, self.row, 1, 1, 2)
        self.entriesLayout.addWidget(self.browseButton2, self.row, 3)
        #   * write cruisename
        self.row += 1
        if not self.cruisename:
            self.cruiseNameEntry = QLineEdit(self.cruisename, parent=self)
            self.cruiseNameEntry.setValidator(CruisenameValidator(parent=self))
            self.entriesLayout.addWidget(CustomLabel(
              'Specify cruise name (short, e.g.: ps0918):',
                style='h3', parent=self), self.row, 0)
            self.entriesLayout.addWidget(self.cruiseNameEntry, self.row, 1, 1, 2)
            # Connect
            self.cruiseNameEntry.textChanged.connect(self.on_cruise_name_change)
        else:
            self.entriesLayout.addWidget(CustomLabel(
                'Cruise name: ', style='h3', parent=self),
                self.row, 0, 1, 1)
            self.cruisenameLabel = QLabel(self.cruisename,parent=self)
            self.entriesLayout.addWidget(self.cruisenameLabel, self.row, 1, 1, 3)
        #   * info label on UHDAS dir
        self.row += 1
        self.entriesLayout.addWidget(CustomLabel(
            'UHDAS-style directory: ', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.uhdasDirLabel = QLabel(parent=self)
        self.uhdasDirLabel.setWordWrap(True)
        self.entriesLayout.addWidget(self.uhdasDirLabel, self.row, 1, 1, 3)
        #   * edit file names for python scripts
        self._separator()
        self.row += 1
        self.fileNameEntry1 = QLineEdit(parent=self)
        self.fileNameEntry1.setValidator(FileNameValidator(parent=self))
        self.fileNameEntry1.setText(self.def_script_pyname)
        self.fileNameEntry2 = QLineEdit(parent=self)
        self.fileNameEntry2.setValidator(FileNameValidator(parent=self))
        self.fileNameEntry2.setText(self.convert_script_pyname)
        self.entriesLayout.addWidget(
            CustomLabel('Filename for variable definitions (*):',
                        style='h3', parent=self), self.row, 0)
        self.entriesLayout.addWidget(self.fileNameEntry1, self.row, 1, 1, 2)
        self.row += 1
        self.entriesLayout.addWidget(
            CustomLabel('Filename for conversion (*):',
                        style='h3', parent=self), self.row, 0)
        self.entriesLayout.addWidget(self.fileNameEntry2, self.row, 1, 1, 2)
        note = QLabel('(*) writes these conversion scripts in the "config" directory')
        note.setFont(QFont("?", 10, italic=True))
        self.row += 1
        self.entriesLayout.addWidget(note, self.row, 1, 1, 3, Qt.AlignRight)
        #   * Action buttons
        self.row += 1
        self.buttonsBox = QWidget(parent=self)
        self.buttonsLayout = QHBoxLayout()
        self.buttonsBox.setLayout(self.buttonsLayout)
        self.buttonMakeConfig = CustomPushButton("Make\nconversion files", self)
        self.buttonMakeConfig.setStyleSheet(backGroundKey + blue)
        self.buttonsLayout.addWidget(self.buttonMakeConfig, Qt.AlignCenter)
        if self.called_from_form:
            self.buttonConvert = CustomPushButton("Convert to\nUHDAS", self)
            self.buttonConvert.setStyleSheet(backGroundKey + green)
            self.buttonsLayout.addWidget(self.buttonConvert, Qt.AlignCenter)
            self.buttonSetup = CustomPushButton(
                "Set up\nprocessing configuration", self)
            self.buttonSetup.setStyleSheet(backGroundKey + red)
            self.buttonsLayout.addWidget(self.buttonSetup, Qt.AlignCenter)
        self.entriesLayout.addWidget(self.buttonsBox, self.row, 0, 1, 4)
        # Connection Widgets/slots
        self.browseButton2.clicked.connect(self.on_select_uhdas_source)
        self.dirEntry2.textChanged.connect(self.on_dir2_change)
        self.fileNameEntry1.textChanged.connect(self.on_file_name1_change)
        self.fileNameEntry2.textChanged.connect(self.on_file_name2_change)
        self.buttonMakeConfig.clicked.connect(self.on_make_config)
        if self.called_from_form:
            self.buttonConvert.clicked.connect(self.on_convert)
            self.buttonSetup.clicked.connect(self.on_setup)
        # Kick start
        # - switch off buttons
        if self.called_from_form:
            self.buttonConvert.setEnabled(False)
            self.buttonSetup.setEnabled(False)
        # - Initialize dict. with kwargs
        self.config['proc_dir'] = proc_dir_path
        if not self.config['proc_dir']:
            # assuming proper folder architecture..2 level up
            dir = os.path.dirname(os.path.dirname(os.getcwd()))
            self.config['proc_dir'] = dir
            self.cruise_dir = dir
            if hasattr(self, 'dirEntry'):
                self.dirEntry.setText(self.cruise_dir)
        self.config['cruisename'] = self.cruisename
        if self.vmdas_dir:
            self.look_for_ENR(self.vmdas_dir)

    # Slots
    def on_select_cruise_dir(self):
        selected_dir = QFileDialog.getExistingDirectory(
            caption='Select destination of the project directory',
            directory=self.start_path,
            parent=self,
            options=QFileDialog.DontUseNativeDialog)
        if selected_dir:
            # self._exists(selected_dir)
            self.cruise_dir = selected_dir
            self.dirEntry.setText(selected_dir)

    def on_select_vmdas_dir(self):
        # User select VmDAS dir. and script check if there is *.ENR in there
        vmdas_dir = QFileDialog.getExistingDirectory(
            caption='Select VmDAS data directory',
            directory=self.start_path,
            parent=self,
            options=QFileDialog.DontUseNativeDialog)
        if vmdas_dir:
            self.look_for_ENR(vmdas_dir)

    def on_select_uhdas_source(self):
        selected_dir = QFileDialog.getExistingDirectory(
            caption='Select/Create root dir. for the UHDAS-style data',
            directory=self.start_path,
            parent=self,
            options=QFileDialog.DontUseNativeDialog)
        if selected_dir:
            # selected_dir += '/uhdas_fake_data'
            # self._exists(selected_dir)
            self.uhdas_source = selected_dir
            self.dirEntry2.setText(selected_dir)

    def on_make_config(self):
        make_busy_cursor()
        self.buttonMakeConfig.setEnabled(False)
        if self.write_config() and self.called_from_form:
            self.buttonConvert.setEnabled(True)
        else:
            self.buttonMakeConfig.setEnabled(True)
        # Add empty line to text area
        self._print("")
        restore_cursor()

    def on_convert(self):
        make_busy_cursor()
        if self._exists(self.uhdas_dir) or not self.uhdas_source:
            self._print("Address and try again", color='red')
            restore_cursor()
            return
        if self.convert_script_path and self.def_script_path and self.config:
            if self.called_from_form:
                self.buttonConvert.setEnabled(False)
            try:  # Very permissive in purpose
                # FIXME: use self.run_command instead for consistency sake with the other forms
                self.vmdas2uhdas()
                if self.called_from_form:
                    self.buttonSetup.setEnabled(True)
                self._print(
                 'Click the "Set up processing" button to launch the next step',
                    color='red')
                self._print(
                    'Or close this form, cd to config directory and run' +
                    'proc_starter_form.py manually',
                    color='red')
            except Exception as err:
                msg = "Could not convert!"
                self._print(msg, color='red')
                _log.error(msg)
                _log.error(unexpected_error_msg(err))
                _log.error(msg)
                if self.called_from_form:
                    self.buttonConvert.setEnabled(True)
        else:
            msg = "Python scripts' filenames are missing."
            self._print(msg)
            _log.error(msg)
        # Add empty line to text area
        self._print("")
        restore_cursor()

    def on_cruise_name_change(self):
        typed_text = self.cruiseNameEntry.text()
        self.cruisename = typed_text
        self.uhdasDirLabel.setText(self.uhdas_dir)

    def on_file_name1_change(self):
        typed_text = self.fileNameEntry1.text()
        self.def_script_pyname = typed_text

    def on_file_name2_change(self):
        typed_text = self.fileNameEntry2.text()
        self.convert_script_pyname = typed_text

    def on_dir_change(self):
        typed_text = self.dirEntry.text()
        self.cruise_dir = typed_text
        # self._exists(typed_text)

    def on_dir1_change(self):
        typed_text = self.dirEntry1.text()
        self.vmdas_dir = typed_text

    def on_dir2_change(self):
        typed_text = self.dirEntry2.text()
        self.uhdas_source = typed_text
        # self._exists(typed_text)
        self.uhdasDirLabel.setText(self.uhdas_dir)

    def on_setup(self):
        make_busy_cursor()
        self._print("===Please wait for the next form to pop-up===")
        config_path = os.path.join(self.cruise_dir, 'config')
        input_path = os.path.join(config_path, self.def_script_pyname)
        next_form = ProcStarterForm(input_path,
                                    config_path=config_path,
                                    start_path=self.start_path,
                                    parent=self)
        self.hide()
        next_form.show()
        restore_cursor()

    # Local lib
    def look_for_ENR(self, vmdas_dir):
        """
        List all the *ENR in a given directory as well as print out information

        Args:
            vmdas_dir: path to VmDAS data directory, str.
        """
        try:
            globstr = os.path.join(vmdas_dir, '*ENR')
            ENRlist = pathops.make_filelist(globstr)
            nb_files = ENRlist
            if nb_files == 0:
                raise ValueError
            msg = 'Found %d ENR files' % len(nb_files)
            _log.info(msg)
            self._print(msg)
        except ValueError:
            msg = "No ENR files found in %s." % vmdas_dir
            _log.error("ValueError: " + msg)
            msg += "\nChoose a different directory\n"
            self._print(msg, color='red')
            self.vmdas_dir = ''
            return
        # Discover which sonar we re dealing with
        sonar_name = self.guess_sonar_name_from_raw_files(ENRlist)
        self.sonar = sonar_name
        # Final step: update attributes & widgets
        self.vmdas_dir = vmdas_dir
        self.ENRlist = ENRlist
        if hasattr(self, "dirEntry1"):
            self.dirEntry1.setText(self.vmdas_dir)

    def write_config(self):
        """
        Write reform_defs.py and vmdas2uhdas.py accordingly with
        the information provided by the user via the form.
        """
        global PASSED
        PASSED = True
        # check if config dir. exists
        config_path = os.path.join(self.cruise_dir, 'config')
        if not os.path.exists(config_path):
            msg = "%s does not exist." % config_path
            msg += ARCHITECTURE_REQUIREMENT_MSG
            self._print(msg, color='red')
            PASSED = False
        # check if all entries are filled
        for attr_name in self._attribute_list:
            attr = getattr(self, attr_name)
            if not attr:
                msg = "Information is missing. Please fill-in every entries."
                self._print(msg, color='red')
                _log.debug("Missing attribute: " + attr_name)
                PASSED = False
                break
        # Info discovery
        if PASSED:
            msg = 'looking for yearbase...'
            _log.info(msg)
            self._print(msg)
            try:
                m = Multiread(self.ENRlist, self.sonar[:2])
                d = m.read(stop=5)
                self.yearbase = d.yearbase
                msg = 'using yearbase %d' % (d.yearbase)
                _log.info(msg)
                self._print(msg)
            except Exception as err:  # FIXME - Too vague
                msg = 'could not get yearbase'
                _log.error(msg)
                _log.error(unexpected_error_msg(err))
                self._print(msg, color='red')
                PASSED = False
        if PASSED:
            msg = 'Scanning %d files for navigation and attitude messages...'
            nb = len(self.ENRlist)
            _log.info(msg % nb)
            self._print(msg % nb)
            try:
                VM = VmdasNavInfo(self.vmdas_dir)
                _log.debug('VmdasNavInfo: ' + str(VM.navinfo))
                navinfo = []
                for nnn in VM.navinfo:
                    if nnn not in navinfo:
                        navinfo.append(nnn)
                self.navinfo = navinfo
                _log.debug('self.navinfo: ' + str(self.navinfo))
            except Exception as err:  # FIXME - Too vague
                _log.error('Could not get navinfo from N*R files')
                _log.error(unexpected_error_msg(err))
                PASSED = False
        # Define config. dict
        if PASSED:
            self.config['cruisename'] = self.cruisename
            self.config['vmdas_dir'] = self.vmdas_dir
            self.config['uhdas_dir'] = self.uhdas_dir
            self.config['yearbase'] = self.yearbase
            self.config['adcp'] = self.sonar
            self.config['shipkey'] = self.shipkey
            self.config['proc_dir'] = self.cruise_dir
            self.config['navinfo'] = self.navinfo
        # Write *.py files
        if PASSED:
            # fill template
            template = Templater(
                REFORMVAR_TEMPLATE, self.config, self.varformat)
            # sanity checks
            def_script_path = os.path.join(config_path, self.def_script_pyname)
            convert_script_path = os.path.join(config_path,
                                               self.convert_script_pyname)
            PASSED = not self._exists(def_script_path)
            PASSED = not self._exists(convert_script_path)
            # writing to files
            if PASSED:
                try:
                    with open(def_script_path, 'w') as file:
                        file.write(template.pstr)
                    self._print('%s has been created.' % def_script_path)
                    with open(convert_script_path, 'w') as file:
                        file.write(REFORMFILE_TEMPLATE % (
                            {'reformvar_file': def_script_path}))
                    msg = REFORM_SUCCESS_MSG % (
                        convert_script_path, convert_script_path)
                    self._print(msg, color='red')
                    # Update attributes
                    self.convert_script_path = convert_script_path
                    self.def_script_path = def_script_path
                except Exception as err:  # FIXME - Too vague
                    msg = 'Could not write config file'
                    _log.error(msg)
                    self._print(msg, color='red')
                    _log.error(unexpected_error_msg(err))
                    self.convert_script_path = ''
                    self.def_script_path = ''
                    PASSED = False
            else:
                self._print('\nAddress and try again', color='red')
        return PASSED

    def vmdas2uhdas(self):
        """
        Reformat VmDAS raw data into UHDAS compatible dataset
        """
        self._print("===Please Wait While the Process is Running===",
                    color='red')
        self._print('\n\nMaking rbins from N1R, N2R, etc',color='red')
        self._print('Converting VmDAS ENR to UHDAS-style data\n',
                    color='red')
        self._print('... this may be time-consuming (taking minutes)...\n\n',
                    color='red')
        dt_factor = 3  # median(dt) * dt_factor = when to break the files in to parts
        # 3   :   allows more variable ping rate (eg. if triggering)
        # 0.5 :   assumes fixed ping rate (might make lots of pieces)
        # Convert vmdas data to uhdas data
        F = FakeUHDAS(yearbase=self.config['yearbase'],
                      sourcedir=self.config['vmdas_dir'],
                      destdir=self.config['uhdas_dir'],
                      sonar=self.config['adcp'],
                      dt_factor=dt_factor,
                      navinfo=self.config['navinfo'],
                      ship=self.config['shipkey'])
        F()

    # BREADCRUMB: common lib.
    # FIXME: turn into function and move to lib/misc
    def guess_sonar_name_from_raw_files(self, ENRlist):
        """
        Guess the sonar name based on given *.ENR files

        Args:
            ENRlist: list of *.ENR files' paths, [str, str,...]

        Returns: sonar name, str
        """
        sonar_found = False
        adcp = ''
        for sonar in adcps:
            for f in ENRlist:
                try:
                    inst_name = instname_from_file(f)
                except AttributeError:
                    msg = "CORRUPTED FILE: %s" % f
                    msg += "\n - sonar name can not be read from ENR file"
                    _log.warning(msg)
                    self._print(msg, color='red')
                    continue
                if os.path.getsize(f) > 0 and inst_name == sonar and adcp != sonar:
                    if sonar_found:
                        msg = "CORRUPTED FILE: %s" % f
                        msg += "\n - several sonars were found"
                        _log.warning(msg)
                        self._print(msg, color='red')
                    else:
                        adcp = sonar
                        msg = 'sonar %s is OK\n' % sonar
                        _log.info(msg)
                        self._print(msg)
                        sonar_found = True
        if not sonar_found:
            msg = "CORRUPTED ENR Files: no sonar were found"
            _log.warning(msg)
            self._print(msg, color='red')
            return
        return adcp

    # Dynamic attributes
    def _get_uhdas_dir(self):
        '''
        if called from script, be consistent with historical usage:
           use the cruisename ONLY for new uhdas_dir (do not tack on sonar)
        '''
        folder_name = self.cruisename
        if self.called_from_form and self.sonar:
            folder_name += "_" + self.sonar
        path = os.path.join(self.uhdas_source, folder_name)
        self._exists(path)
        _log.debug("UHDAS dir.: " + path)
        return path

    uhdas_dir = property(_get_uhdas_dir)


if __name__ == '__main__':
    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        app = QApplication(sys.argv)
        form = ReformVMDASForm()
        form.show()
        sys.exit(app.exec_())
    else:
        from argparse import ArgumentParser
        arglist = sys.argv[1:]
        parser = ArgumentParser()

        help = "Path to project directory"
        parser.add_argument(
            "--project_dir_path", dest="proc_dir_path",
            nargs='?', type=str, default='', help=help)
        help = "Path to VmDAS data directory"
        parser.add_argument(
            "--vmdas_dir_path", dest="vmdas_dir_path",
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
                               sonar=options.sonar,
                               start_path=options.start_path)
        form.show()
        sys.exit(app.exec_())
