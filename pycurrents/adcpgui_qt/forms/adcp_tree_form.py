#!/usr/bin/env python3

import os
import sys
import logging
import traceback
from datetime import datetime
from numpy import unique
from glob import glob
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import (QApplication,
    QFileDialog, QTabWidget, QMainWindow, QWidget, QVBoxLayout, QCheckBox,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit)
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QIcon, QFont, QIntValidator

# BREADCRUMB: common library, begin block...
from pycurrents.system import Bunch, pathops
from pycurrents.adcp.adcp_specs import adcps
# BREADCRUMB: ...common library, end block
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomSeparator,
    iconUHDAS, CustomLabel, CustomPushButton, make_busy_cursor, restore_cursor,
    CruisenameValidator, DBNameValidator, backGroundKey, blue, red, green, globalStyle)
from pycurrents.adcpgui_qt.lib.miscellaneous import (
    get_pingtypes, get_adcp_filelist)
from pycurrents.adcpgui_qt.forms.generic_form import GenericForm
from pycurrents.adcpgui_qt.forms.string_templates import (
    CONTROL_FILE_TEMPLATE, CONTROL_FILE_TEMPLATE_HEAD_CORR,
    ARCHITECTURE_REQUIREMENT_MSG)

# Standard logging
_log = logging.getLogger(__name__)

# TODO: change text and variable names accordingly with new naming convention (see documentation website)


class ProcSelectorPopUp(QMainWindow):
    def __init__(self, proc_prefix='', cruise_dir=os.getcwd(),
                 from_enr=False, parent=None):
        """
        Pop-up window that would show up if more than one *_proc.* files are
        contained in the config directory. Otherwise, it will launch
        adcp_tree_form.py directly.

        Args:
            proc_prefix: prefix for finding the right *_proc.* file, str.
            cruise_dir: absolute path to project directory, str.
            from_enr: True if dealing *.ENR files, False otherwise and
                      by default, boolean switch
            parent: PySide6 or PyQt5 parent Widget
        """
        super().__init__(parent=parent)
        # Attributes
        self.proc_prefix = proc_prefix
        self.cruise_dir = cruise_dir
        self.from_enr = from_enr
        self.parent_widget = parent
        # Information discovery
        # - assuming starting form from config
        if not (self.cruise_dir or os.path.exists(self.cruise_dir)):
            self.cruise_dir = os.path.abspath(
                os.path.join(os.getcwd(), '..'))
        self.config_path = os.path.join(self.cruise_dir, 'config')
        # - assuming existing *PROC_PREFIX*_proc.* files
        self.proc_files = glob(os.path.join(self.config_path, '*_proc.toml'))
        self.proc_files.extend(glob(os.path.join(self.config_path, '*_proc.py')))
        if not self.proc_files:
            msg = "No *_proc.* file were found in %s" % self.config_path
            _log.error(msg)
            msg += ARCHITECTURE_REQUIREMENT_MSG
            print(msg)
            # FIXME: send to previous form instead (proc_starter_form.py)
            sys.exit(1)
        # Form style
        self.setWindowIcon(QIcon(iconUHDAS))
        self.setWindowTitle('UHDAS Form Dispatcher')
        # Widget, layout & connection
        # - layout
        self.box = QWidget(parent=self)
        self.boxLayout = QVBoxLayout()
        self.box.setLayout(self.boxLayout)
        # - widgets
        self.textLabel = CustomLabel(
            "- Select the *_proc.* file(s) to process -",
            style='h2', parent=self)
        self.textLabel.setAlignment(Qt.AlignCenter)
        self.boxLayout.addWidget(self.textLabel)
        self.tickBoxes = Bunch()
        for proc_file in self.proc_files:
            filename = proc_file.split('/')[-1]
            widget = QCheckBox(filename)
            if self.proc_prefix in proc_file:
                widget.click()
            self.tickBoxes[filename] = widget
            self.boxLayout.addWidget(widget)
        self.nextButton = CustomPushButton("Next", self)
        self.boxLayout.addWidget(self.nextButton)
        self.setCentralWidget(self.box)
        # - connection
        self.nextButton.clicked.connect(self.on_next)
        # - skip if necessary
        self.show()
        if len(self.proc_files) == 1:
            self.on_next()

    def on_next(self):
        make_busy_cursor()
        proc_files = []
        for filename in self.tickBoxes.keys():
            if self.tickBoxes[filename].isChecked():
                proc_files.append(os.path.join(self.config_path, filename))
        if not proc_files:
            msg = "- No *_proc.* file were selected -"
            _log.error(msg)
            self.textLabel.setText(msg + "\nPick at least one")
            self.textLabel.setAlignment(Qt.AlignCenter)
            restore_cursor()
            return
        next_form = ADCPTreeForm(proc_files=proc_files,
                                 cruise_dir_path=self.cruise_dir,
                                 config_path=self.config_path,
                                 from_enr=self.from_enr,
                                 parent=self.parent_widget)
        next_form.show()
        self.hide()
        restore_cursor()


class ADCPTreeTab(QWidget):
    def __init__(self, cruise_dir_path, config_path, param_dict, parent):
        """

        Args:
            cruise_dir_path: path to project directory, str.
            config_path: path to config directory, str.
            param_dict: dictionary of various parameters, dict.
            parent: PySide6 or PyQt5 parent Widget
        """
        super().__init__(parent)
        # Attributes
        self.cruise_dir = os.path.abspath(cruise_dir_path)
        self.config_path = os.path.abspath(config_path)
        self.sonar = param_dict['sonar']
        self.prefix = param_dict['prefix']
        self.heading_correction = param_dict['heading_correction']
        self.yearbase = param_dict['yearbase']
        self.cruiseid = param_dict['cruiseid']
        self.uhdas_dir = param_dict['uhdas_dir']
        self.depth = param_dict['depth']
        self.ens_len = param_dict['ens_len']
        self.dx_ducer = param_dict['dx_ducer']
        self.dy_ducer = param_dict['dy_ducer']
        self.acq_sonars = param_dict['acq_sonars']
        self.dbname = param_dict['dbname']
        self.sonar_proc = param_dict['sonar_proc']
        self.proc_file = param_dict['proc_file']
        self.parent = parent
        self.row = 0
        # Widgets
        # - Layout
        self.entriesLayout = QGridLayout()
        self.setLayout(self.entriesLayout)
        # - Info labels
        self.entriesLayout.addWidget(
            CustomLabel('Associated *_proc.* file:', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.procfileLabel = CustomLabel(self.proc_file.split('/')[-1],
                                         style='h3', color='red', parent=self)
        self.procfileLabel.setWordWrap(True)
        self.entriesLayout.addWidget(self.procfileLabel, self.row, 1, 1, 1)
        self.row += 1
        self.entriesLayout.addWidget(
            CustomLabel('Year base:', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.yearbaseLabel = QLabel(str(self.yearbase), parent=self)
        self.entriesLayout.addWidget(self.yearbaseLabel, self.row, 1, 1, 1)
        self.row += 1
        self.cruiseidLabel = QLabel(self.cruiseid, parent=self)
        self.entriesLayout.addWidget(
            CustomLabel('Cruise id.:', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.entriesLayout.addWidget(self.cruiseidLabel, self.row, 1, 1, 1)
        # - Entries
        self._separator()
        #  * processing dir. name
        self.row += 1
        self.entriesLayout.addWidget(
            CustomLabel('Processing dir. name:',
                        style='h3', parent=self),
            self.row, 0, 1, 1)
        self.sonarProcEntry = QLineEdit(self.sonar_proc, parent=self)
        self.sonarProcEntry.setValidator(CruisenameValidator(parent=self))
        self.entriesLayout.addWidget(self.sonarProcEntry, self.row, 1, 1, 1)
        self.row += 1
        note = QLabel(
            'name of the directory to be created in project dir.',
            parent=self)
        note.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note, self.row, 0, 1, 2)
        #  * dbname
        self.row += 1
        self.entriesLayout.addWidget(
            CustomLabel('CODAS database name:', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.dbnameEntry = QLineEdit(self.dbname, parent=self)
        self.dbnameEntry.setValidator(DBNameValidator(parent=self))
        self.entriesLayout.addWidget(self.dbnameEntry, self.row, 1, 1, 1)
        self.row += 1
        note = QLabel(
            'must start with "a", then only letters, numbers and "_"',
            parent=self)
        note.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note, self.row, 0, 1, 2)
        #  * xducer label
        self._separator()
        self.row += 1
        self.entriesLayout.addWidget(
            CustomLabel(
                'Specify the offset from the GPS to\nthe ADCP (if known)',
                style='h2', parent=self), self.row, 0, 1, 2)
        #  * dx xducer
        self.row += 1
        self.entriesLayout.addWidget(
            CustomLabel("ADCP's starboard location:", style='h3', parent=self),
            self.row, 0, 1, 1)
        self.dxEntry = QLineEdit(str(self.dx_ducer), parent=self)
        validator = QIntValidator(parent=self)
        validator.setRange(-1000, 1000)
        self.dxEntry.setValidator(validator)
        self.entriesLayout.addWidget(self.dxEntry, self.row, 1, 1, 1)
        self.row += 1
        note = QLabel("(m), [-1000, 1000], origin = GPS location",
                      parent=self)
        note.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note, self.row, 0, 1, 2)
        #  * dy xducer
        self.row += 1
        self.entriesLayout.addWidget(
            CustomLabel("ADCP's forward location:", style='h3', parent=self),
            self.row, 0, 1, 1)
        self.dyEntry = QLineEdit(str(self.dy_ducer), parent=self)
        validator = QIntValidator(parent=self)
        validator.setRange(-1000, 1000)
        self.dyEntry.setValidator(validator)
        self.entriesLayout.addWidget(self.dyEntry, self.row, 1, 1, 1)
        self.row += 1
        note = QLabel("(m), [-1000, 1000], origin = GPS location",
                      parent=self)
        note.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note, self.row, 0, 1, 2)
        #  * ensemble length
        self._separator()
        self.row += 1
        self.entriesLayout.addWidget(
            CustomLabel('Ensemble length:', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.enslenEntry = QLineEdit(str(self.ens_len), parent=self)
        validator = QIntValidator(parent=self)
        validator.setRange(10, 1800)
        self.enslenEntry.setValidator(validator)
        self.entriesLayout.addWidget(self.enslenEntry, self.row, 1, 1, 1)
        self.row += 1
        note = QLabel("(sec.), [10, 1800]", parent=self)
        note.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note, self.row, 0, 1, 2)
        #  * max search depth
        self.row += 1
        self.entriesLayout.addWidget(CustomLabel(
            'Max. depth for bottom search:', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.maxsearchdepthEntry = QLineEdit(str(self.depth), parent=self)
        validator = QIntValidator(parent=self)
        validator.setRange(1, 5000)
        self.maxsearchdepthEntry.setValidator(validator)
        self.entriesLayout.addWidget(self.maxsearchdepthEntry,
                                     self.row, 1, 1, 1)
        self.row += 1
        note = QLabel("(m), [1, 5000], positive downward", parent=self)
        note.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note, self.row, 0, 1, 2)
        # - Check boxes
        #  * use amp to identify the bottom
        self.row += 1
        self.useampCheckbox = QCheckBox(
            'Always search for the bottom', parent=self)
        self.entriesLayout.addWidget(self.useampCheckbox, self.row, 0, 1, 2)
        #  * never search for the bottom
        self.row += 1
        self.nosearchCheckbox = QCheckBox(
            'Never search for the bottom', parent=self)
        self.entriesLayout.addWidget(self.nosearchCheckbox, self.row, 0, 1, 2)
        # - Action buttons
        self._separator()
        self.row += 1
        #  * sub-layout
        self.buttonsBox = QWidget(parent=self)
        self.buttonsLayout = QHBoxLayout()
        self.buttonsBox.setLayout(self.buttonsLayout)
        #  * run adcp tree
        self.adcptreeButton = CustomPushButton(
            "Create \nProcessing Dir.", self)
        self.adcptreeButton.setStyleSheet(backGroundKey + blue)
        self.buttonsLayout.addWidget(self.adcptreeButton, Qt.AlignCenter)
        #  * create control file
        self.controlfileButton = CustomPushButton(
            "Create q_py.cnt\nControl File", self)
        self.controlfileButton.setStyleSheet(backGroundKey + red)
        self.buttonsLayout.addWidget(self.controlfileButton, Qt.AlignCenter)
        #  * run quick_adcp
        self.runQuickADCPButton = CustomPushButton(
            "Create\nCODAS Database", self)
        self.runQuickADCPButton.setStyleSheet(backGroundKey + green)
        self.buttonsLayout.addWidget(self.runQuickADCPButton, Qt.AlignCenter)
        #  * add buttons' box/layout to central widget
        self.entriesLayout.addWidget(self.buttonsBox, self.row, 0, 1, 2)
        # Connections
        self.dbnameEntry.textChanged.connect(self.on_dbname_change)
        self.sonarProcEntry.textChanged.connect(self.on_sonar_proc_change)
        self.enslenEntry.textChanged.connect(self.on_ens_len_change)
        self.dxEntry.textChanged.connect(self.on_dx_change)
        self.dyEntry.textChanged.connect(self.on_dy_change)
        self.maxsearchdepthEntry.textChanged.connect(self.on_depth_change)
        self.useampCheckbox.stateChanged.connect(self.on_use_amp)
        self.nosearchCheckbox.stateChanged.connect(self.on_never_search)
        self.adcptreeButton.clicked.connect(self.on_run_adcp_tree)
        self.controlfileButton.clicked.connect(self.on_create_cnt_file)
        self.runQuickADCPButton.clicked.connect(self.on_run_quick_adcp)
        # Initialization
        # self.useampCheckbox.click()

    # Slots
    def on_dbname_change(self):
        self.dbname = self.dbnameEntry.text()

    def on_sonar_proc_change(self):
        self.sonar_proc = self.sonarProcEntry.text()
        self._sanity_check()

    def on_ens_len_change(self):
        self.ens_len = self.enslenEntry.text()

    def on_dx_change(self):
        self.dx_ducer = self.dxEntry.text()

    def on_dy_change(self):
        self.dy_ducer = self.dyEntry.text()

    def on_depth_change(self):
        self.depth = self.maxsearchdepthEntry.text()

    def on_use_amp(self):
        # check other checkbox
        if self.nosearchCheckbox.isChecked() and self.useampCheckbox.isChecked():
            self.nosearchCheckbox.setChecked(False)
        if (not self.nosearchCheckbox.isChecked()
            and not self.useampCheckbox.isChecked()):
            self.maxsearchdepthEntry.setEnabled(True)
            self.depth = self.maxsearchdepthEntry.text()
            return
        # Lock depth entry
        if self.useampCheckbox.isChecked():
            self.maxsearchdepthEntry.setEnabled(False)
            # Change depth attribute accordingly
            self.depth = '0'

    def on_never_search(self):
        # check other checkbox
        if self.nosearchCheckbox.isChecked() and self.useampCheckbox.isChecked():
            self.useampCheckbox.setChecked(False)
        if (not self.nosearchCheckbox.isChecked()
            and not self.useampCheckbox.isChecked()):
            self.maxsearchdepthEntry.setEnabled(True)
            self.depth = self.maxsearchdepthEntry.text()
            return
        # Lock depth entry
        if self.nosearchCheckbox.isChecked():
            self.maxsearchdepthEntry.setEnabled(False)
            # Change depth attribute accordingly
            self.depth = '-1'

    def on_run_adcp_tree(self):
        # Check if all entries are filled-in
        self._check_entries()
        # Run adcptree
        arglist = ['adcptree.py', self.sonar_proc,
                   '--cruisedirpath', self.cruise_dir,
                   '--configpath', self.config_path,
                   '--datatype', 'uhdas',
                   '--cruisename', self.cruiseid]
        comment = 'running this :\n%s' % (' '.join(arglist))
        self.parent.run_command(arglist, comment=comment)
        # inform user
        if os.path.exists(self.sonar_dir):
            msg = "%s folder architecture has been created" % self.sonar_dir
            self.parent._print(msg)
            msg = "You can now create the control file"
            self.parent._print(msg, color='red')
            # Lock button
            self.adcptreeButton.setEnabled(False)
        else:
            self.parent._print(
                "%s folder architecture has NOT been created" % self.sonar_dir,
                color='red')

    def on_create_cnt_file(self):
        # Check if all entries are filled-in
        self._check_entries()
        # Check if proc_dir and control file already exist
        if not os.path.exists(self.sonar_dir):
            self.parent._print("Run ADCP Tree first !!!")
            return
        if self.parent._exists(self.cnt_file):
            self.parent._print(
                '\n%s already exists' % self.cnt_file,
                color='red')
            return
        # write control file
        proc_prefix = self.proc_file.split('/')[-1].split('_proc.')[0]
        text = CONTROL_FILE_TEMPLATE % (
            self.yearbase, proc_prefix, self.dbname, self.sonar,
            self.ens_len, self.depth, self.dx_ducer, self.dy_ducer)
        if self.heading_correction:
            text += CONTROL_FILE_TEMPLATE_HEAD_CORR
        with open(self.cnt_file, 'w') as file:
            file.write(text)
        # Lock button
        self.controlfileButton.setEnabled(False)
        # inform user
        msg = '%s has been created' % self.cnt_file
        self.parent._print(msg)
        msg = 'You can now click "Create CODAS Database" or run quick_adcp'
        self.parent._print(msg, color='red')

    def on_run_quick_adcp(self):
        # sanity check
        if not os.path.exists(self.sonar_dir):
            self.parent._print("Create Processing Dir. first !!!")
            return
        if not os.path.exists(self.cnt_file):
            self.parent._print("Create Control File first !!!")
            return
        # run quick adcp
        # FIXME: I really do not like changing dir like that...add keyword arg to quick_adcp.py
        local_dir = os.getcwd()
        os.chdir(self.sonar_dir)
        # sanity check
        gbin_path = os.path.join(self.uhdas_dir, 'gbin')
        if os.path.exists(gbin_path):
            # rename existing gbin with date as suffix
            suffix = datetime.now().strftime("_%Y%b%d_%Hh%Mm%Ss")
            os.rename(gbin_path, gbin_path + suffix)
            self.parent._print('the existing gbin directory has been renamed gbin%s'
                        % suffix)
        arglist = ["quick_adcp.py", "--cntfile", self.cnt_file, '--auto']
        comment = 'running this:\n%s' % (' '.join(arglist))
        comment +='\n\nThis may take some time (minutes)...\n'
        self.parent.run_command(arglist, comment=comment)
        # FIXME: I really do not like changing dir like that
        os.chdir(local_dir)
        # Lock button
        self.runQuickADCPButton.setEnabled(False)
        # inform user
        path = os.path.abspath(os.path.join(self.cruise_dir, self.sonar_proc))
        msg = "Quick_adcp has been run\n"
        msg += "(see above or quick_run.log in %s)\n" % path
        msg += "You can now use dataviewer.py to view the dataset:\n "
        msg += " dataviewer.py  %s" % path
        msg += "\nOr keep on using this form."
        self.parent._print(msg, color='red')

    # Local lib
    def _sanity_check(self):
        """Disable action buttons depending on sanity checks"""
        if os.path.exists(self.sonar_dir):
            self.adcptreeButton.setEnabled(False)
            if os.path.exists(os.path.join(self.sonar_dir, 'q_py.cnt')):
                self.controlfileButton.setEnabled(False)
                if glob(os.path.join(self.sonar_dir, 'adcpdb/*.blk')):
                    self.runQuickADCPButton.setEnabled(False)
        else:
            self.adcptreeButton.setEnabled(True)
            self.controlfileButton.setEnabled(True)
            self.runQuickADCPButton.setEnabled(True)

    def _check_entries(self):
        """Check if all entries are filled in"""
        if not (self.yearbase and self.dbname and self.ens_len
                and self.dx_ducer and self.dy_ducer
                and self.depth):
            self.parent._print('Please fill-in every entries and try again.')
            msg = "Entries are missing"
            _log.debug(msg)
            return

    def _separator(self):
        """
        Add separation line in entries box
        """
        self.row += 1
        self.entriesLayout.addWidget(
            CustomSeparator(parent=self), self.row, 0, 1, -1)

    # Dynamic attributes
    def _get_sonar_dir(self):
        return os.path.join(self.cruise_dir, self.sonar_proc)

    def _get_cnt_file(self):
        return os.path.join(self.sonar_dir, 'q_py.cnt')

    sonar_dir = property(_get_sonar_dir)
    cnt_file = property(_get_cnt_file)


class ADCPTreeForm(GenericForm):
    def __init__(self, proc_files=[], cruise_dir_path=os.getcwd(),
                 config_path='', from_enr=False, parent=None):
        """
        Set up UHDAS ADCP processing directory architecture based
        on existing *_proc.files (i.e. .../sonar_proc/config/*_proc.*)

        Args:
            proc_files: list of path(s) to *_proc.* file(s), [str.,...,str.]
            cruise_dir_path: path to cruise directory, str.
            config_path: path to config dir, str.
            from_enr: ADCP data created from ENR files? bool.
            parent: Qt widget
        """
        super().__init__(parent=parent)
        # Attributes
        self.is_from_enr = from_enr
        self.cruise_dir = cruise_dir_path
        self.config_path = config_path
        self.proc_files = proc_files
        # Form style
        self.setWindowTitle('ADCP Tree Form')
        # - parsing/mining *_proc.* file(s)
        self.proc_dict, self.items = self._discovery(self.proc_files, from_enr)
        # Widgets
        # - tabs container
        self.tabsContainer = QTabWidget(parent=self)
        for sonar_key in self.items:
            param_dict = self.proc_dict[sonar_key]
            tab = ADCPTreeTab(self.cruise_dir, self.config_path,
                              param_dict, self)
            tab._sanity_check()
            setattr(self, sonar_key, tab)
            name = param_dict.sonar
            self.tabsContainer.addTab(getattr(self, sonar_key), name)
        self.entriesLayout.addWidget(self.tabsContainer, self.row, 0, 1, -1)

    def on_go_back_to_dispatch(self):
        make_busy_cursor()
        self._print("===Please wait for the next form to pop-up===")
        # N.B.: import must be done here otherwise infinite loop
        from pycurrents.adcpgui_qt.forms.form_dispatcher import (
            PickDirectoryPopUp)
        next_form = PickDirectoryPopUp(start_path=self.cruise_dir, parent=self)
        next_form.show()
        self.hide()
        restore_cursor()

    def on_change_proc_file(self):
        selected_proc = ''
        while not selected_proc:
            selected_proc = QFileDialog.getOpenFileName(
                caption='Select the *_proc.* file to parse',
                directory=self.config_path,
                parent=self)[0]
            if '_proc.' not in selected_proc:
                msg = "This is not a *_proc.* file."
                msg += "\nChange file name accordingly"
                msg += "\nOr choose a different one."
                self._print(msg, color='red')
                return
        # update attributes
        self.proc_file = selected_proc
        self._discovery()

    # Local lib
    # BREADCRUMB: common lib.
    # FIXME: move to lib.
    @staticmethod
    def _prefix(proc_file, nb_proc_files, common_prefix):
        """
        Find the unique prefix associated with a given *_proc.* file
        Args:
            proc_file: path to *_proc.* file, str.
            nb_proc_files: number of *_proc.* files, int.
            common_prefix: common prefix to all *_proc.* files, str.

        Returns: unique prefix, str.
        """
        if not nb_proc_files > 1:
            prefix = proc_file.split('/')[-1].split('_proc.')[0]
        else:
            prefix = proc_file.replace(common_prefix, '').split(
                'proc.py')[0].replace('_', '')
        return prefix

    # BREADCRUMB: common lib.
    # FIXME: make static and  move to lib.
    def _discovery(self, proc_files, from_enr=False):
        """
        Discover/parse various parameters from given *_proc.* files and
        store them into a dictionary.
        Ex. of params: proc_file, sonar, yearbase, cruiseid, etc.

        Args:
            proc_files: list of paths to *_proc.* files, [str., ..., str.]
            from_enr: boolean switch, bool.

        Returns: dictionary of params which keys are
                 the *proc.py files' unique prefixes (see self._prefix)

        """
        # - evaluating and parse *_proc.*
        proc_dict = {}
        nb_proc_files = len(proc_files)
        common_prefix = ''
        if nb_proc_files > 1:
            common_prefix = os.path.commonprefix(proc_files)
        for proc_file in proc_files:
            prefix = self._prefix(proc_file, nb_proc_files, common_prefix)
            try:
                # figuring out the dict.'s keys
                proc_values = Bunch().from_pyfile(proc_file)
                list_keys = list(proc_values.keys())
                sonars = list(proc_values['enslength'].keys())
                for sonar in sonars:
                    custom_key = prefix + '_' + sonar
                    proc_dict[custom_key] = Bunch()
                    proc_dict[custom_key].proc_file = proc_file
                    proc_dict[custom_key].sonar = sonar
                    proc_dict[custom_key].prefix = prefix
                    # - flags
                    if proc_values['hcorr_inst'] and proc_values['hcorr_msg']:
                        proc_dict[custom_key].heading_correction = True
                    else:
                        proc_dict[custom_key].heading_correction = False
                    # - variables
                    proc_dict[custom_key].yearbase = proc_values['yearbase']
                    proc_dict[custom_key].cruiseid = proc_values['cruiseid']
                    proc_dict[custom_key].uhdas_dir = proc_values['uhdas_dir']
                    proc_dict[custom_key].depth = proc_values[
                        'max_search_depth'][sonar]
                    proc_dict[custom_key].ens_len = proc_values[
                        'enslength'][sonar]
                    # - special treatment...for backward compatibility's sake
                    proc_dict[custom_key].dx_ducer = '0'
                    proc_dict[custom_key].dy_ducer = '0'
                    if 'xducer_dx' in list_keys:
                        for inst_type in proc_values['xducer_dx'].keys():
                            if inst_type in sonar:
                                proc_dict[custom_key].dx_ducer = \
                                    proc_values['xducer_dx'][inst_type]
                    if 'xducer_dy' in list_keys:
                        for inst_type in proc_values['xducer_dy'].keys():
                            if inst_type in sonar:
                                proc_dict[custom_key].dy_ducer = \
                                    proc_values['xducer_dy'][inst_type]
                    # - Other attributes
                    proc_dict[custom_key].acq_sonars = []
                    proc_dict[custom_key].dbname = 'aship'
                    #  * defining acquiring sonars
                    rawdirs = pathops.make_filelist(
                        os.path.join(proc_dict[custom_key].uhdas_dir,
                                     'raw/*'))
                    for rawdir in rawdirs:
                        if os.path.basename(rawdir) in adcps:
                            filelist, aqname = get_adcp_filelist(rawdir)
                            instname = os.path.basename(rawdir)
                            if filelist:
                                for pingtype in get_pingtypes(filelist,
                                                              instname):
                                    proc_dict[custom_key].acq_sonars\
                                        .append(pingtype)
            except KeyError as err:
                # FIXME: send to previous form instead (proc_starter_form.py)?
                msg = "Required variable(s) is(are) not defined in %s\n" % (
                    proc_file)
                print(msg)
                print("Fix it and try again")
                msg += "KeyError:" + ' '.join(
                    [str(err), traceback.format_exc()])
                _log.error(msg)
                sys.exit(1)
        # * compare sonars and acq_sonars
        items = []
        for proc_file in proc_files:
            proc_values = Bunch().from_pyfile(proc_file)
            prefix = self._prefix(proc_file, nb_proc_files, common_prefix)
            sonars = list(proc_values['enslength'].keys())
            for sonar in sonars:
                custom_key = prefix + '_' + sonar
                if sonar in proc_dict[custom_key].acq_sonars:
                    items.append(custom_key)
        # * add os+freq if OS instrument in list and associated dict.
        add_sonars = []
        for custom_key in items:
            prefix = proc_dict[custom_key].prefix
            sonar = proc_dict[custom_key].sonar
            if sonar[:2] in ('os', 'pn'):
                add_sonars.append(prefix + '_' + sonar[:-2])
        add_sonars = list(unique(add_sonars))
        items.extend(add_sonars)
        for add_custom_key in add_sonars:
            for custom_key in proc_dict.keys():
                if add_custom_key == custom_key[:-2]:
                    proc_dict[add_custom_key] = Bunch(
                        proc_dict[custom_key])
                    proc_dict[add_custom_key].sonar =\
                        proc_dict[custom_key].sonar[:-2]
                    break
        # * Processing directory dictionary
        for custom_key in items:
            suffix = ''
            prefix = ''
            if from_enr:
                suffix = '_ENR'
            sonar = proc_dict[custom_key].sonar
            if nb_proc_files > 1:
                prefix = '_' + proc_dict[custom_key].prefix
            sonar_proc = sonar + prefix + suffix
            proc_dict[custom_key].sonar_proc = sonar_proc.replace('__', '_')

        return proc_dict, items


if __name__ == '__main__':
    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        from pycurrents.get_test_data import get_test_data_path
        test_folder_path = get_test_data_path()
        cruise_dir_path = test_folder_path + '/uhdas_data/proc/os75nb/'
        app = QApplication(sys.argv)
        form = ProcSelectorPopUp(cruise_dir=cruise_dir_path,
                                 from_enr=True)
        sys.exit(app.exec_())
    else:
        from argparse import ArgumentParser
        # Parsing command line inputs
        arglist = sys.argv[1:]
        parser = ArgumentParser()
        help = "proc_prefix must be identical to the prefix used in"
        help += "./config/*PROC_PREFIX*_proc.*. \n"
        help += "Ex.: [ps0918_os75_proc.py, ps0918_wh300_proc.py]; "
        help += "Valid proc_prefix = ps0918, ps0918_os75 or ps0918_wh300"
        parser.add_argument(
            "--proc_prefix", dest="proc_prefix",
            nargs='?', type=str, default=[''],
            help=help)
        help = "Path to cruise directory."
        help += "\nN.B: This option should not be used when adcptree_form is "
        help += "\n     launch from your project directory"
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
        # Kick-start application
        from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication

        cruise_dir_path = os.getcwd()
        app = QApplication(sys.argv)
        app.setStyle(globalStyle)
        form = ProcSelectorPopUp(proc_prefix=options.proc_prefix[0],
                                 cruise_dir=options.cruisedir,
                                 from_enr=options.from_enr)
        sys.exit(app.exec_())
