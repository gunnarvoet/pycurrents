#!/usr/bin/env python3

import os
import sys
import logging
import numpy as np
from glob import glob
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import (QLabel, QLineEdit, QWidget, QHBoxLayout,
     QApplication, QTabWidget, QFileDialog, QScrollArea)
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QFont, QDoubleValidator, QIntValidator
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt

# BREADCRUMB: common library, begin block...
from pycurrents.adcp import uhdas_defaults
from pycurrents.adcp.uhdasconfig import Proc_Gen
from pycurrents.system.misc import Bunch
# BREADCRUMB: ...common library, end block
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomLabel,
     CruisenameValidator, FileNameValidator,
     CustomFrame, CustomDropdown, CustomPushButton, CustomCheckboxDropdown,
     backGroundKey, green, red, make_busy_cursor, restore_cursor, )
from pycurrents.adcpgui_qt.forms.generic_form import GenericForm
from pycurrents.adcpgui_qt.forms.adcp_tree_form import ProcSelectorPopUp
from pycurrents.adcpgui_qt.forms.string_templates import (
     PROC_STARTER_END_MSG, SINGLE_PING_READY_MSG)
from pycurrents.adcp.uhdasconfig import ProcConfigChecker
from pycurrents.adcp.uhdas_defaults import (proc_instrument_defaults,
     proc_constant_defaults)
from pycurrents.adcp.raw_multi import Multiread
from pycurrents.adcp.EA_estimator import get_xducer_angle
from pycurrents.num import Stats

# Standard logging
_log = logging.getLogger(__name__)

# FIXME: this is a ugly bandage over an old wound...this gonna get infected for sure.
# TODO: To me, the real long term solution would be to use standard config file
#       formats (yaml. json, INI, ...), use uniform read/write/update mechanisms
#       and have centralized locations with config files templates.
#       We could imagine different config templates for different "Objects" (
#       e.g. Feeds, ADCPs, Instruments, Network, you name it...)
#       In the templates would be defined type and default values for each variables.
#       The read/write/update mechanisms logic would be based on mining those
#       templates thus making the "structural" changes' propagation trivial
#       The set of config files would be ship specific and therefore be
#       independently version-controlled (different repos or branches)...
#       ...those are my two cents - TR Jan 2020


class UHDASProcGenForm(GenericForm):
    def __init__(self,
                 uhdas_dir=os.getcwd(),
                 project_path=os.getcwd(),
                 ship_key=None,
                 called_from_form=True,
                 parent=None):
        """
        Help writing processing config file *_proc.py

        Args:
            uhdas_dir: path to UHDAS dir./database, str.
            project_path: path to current project dir., str.
        Kwargs:
            ship_key: ship abreviation, str.
            called_from_form: backend boolean switch, bool
            parent: Qt widget
        """
        super().__init__(parent=parent)
        # Attributes
        self.called_from_form = called_from_form
        self.uhdas_dir = uhdas_dir
        self.project_dir = project_path
        self.proc_cfg_checker = ProcConfigChecker(
            uhdas_dir=uhdas_dir, ship_key=ship_key)
        self.adcps = self.proc_cfg_checker.available_adcps
        self.required_data = self.proc_cfg_checker.required_cfg_params
        self.found_data = self.proc_cfg_checker.found_cfg_params
        self.shipkey = self.proc_cfg_checker.ship_key
        self.shipname = self.proc_cfg_checker.ship_name
        if self.found_data['cruiseid']:
            self.cruiseid = self.found_data['cruiseid'][0]
        self.available_feeds = self.proc_cfg_checker.available_feeds
        self.config_dir = os.path.join(project_path, 'config')
        self.position_feeds = [
            str(val) for val in self.available_feeds.position]
        self.heading_feeds = [
            str(val) for val in self.available_feeds.heading
                              + self.available_feeds.accurate_heading]
        self.pitch_roll_feeds = [
            str(val) for val in list(
                set(self.available_feeds.pitch + self.available_feeds.roll))]
        self.heading_correction_feeds = [
            str(val) for val in self.available_feeds.accurate_heading]
        # Form style
        self.setWindowTitle('Processing Configuration Form')
        # - General Info.
        #   * ship name
        self.entriesLayout.addWidget(CustomLabel(
            'Ship Name - %s' % self.shipname, style='h1', parent=self),
            self.row, 0, 1, 3)
        self.row += 1
        label = CustomLabel('UHDAS Data Directory: %s' % self.uhdas_dir,
                            style='h3', parent=self)
        label.setWordWrap(True)
        self.entriesLayout.addWidget(label, self.row, 0, 1, 3)
        #   * project directory's path
        self.row += 1
        self.browseButton = CustomPushButton("Browse", self)
        self.projectDirEntry = QLineEdit(self.project_dir, parent=self)
        self.projectDirEntry.setValidator(FileNameValidator(parent=self))
        self.projectDirEntry.setText(self.project_dir)
        self.entriesLayout.addWidget(
            CustomLabel('Select Project Directory:', style='h3',
                        parent=self), self.row, 0)
        self.entriesLayout.addWidget(self.projectDirEntry, self.row, 1, 1, 1)
        self.entriesLayout.addWidget(self.browseButton, self.row, 2, 1, 1)
        self._separator()
        # Widgets
        #   * context
        self.row += 1
        self.entriesLayout.addWidget(CustomLabel(
            '-Found-', style='h3', parent=self), self.row, 1, 1, 1)
        self.entriesLayout.addWidget(CustomLabel(
            '-Final-', style='h3', parent=self), self.row, 2, 1, 1)
        # - common entries
        #   * year base
        self.row += 1
        self.entriesLayout.addWidget(CustomLabel(
            'Year of Cruise: ', style='h3', parent=self), self.row, 0, 1, 1)
        choices = [str(val) for val in self.found_data['yearbase']]
        self.yearbaseDropdown = CustomDropdown(choices, parent=self)
        self.entriesLayout.addWidget(self.yearbaseDropdown, self.row, 1, 1, 1)
        self.yearbaseEntry = QLineEdit(parent=self)
        self.yearbaseEntry.setValidator(QIntValidator())
        if len(choices) == 1:
            self.yearbaseEntry.setText(choices[0])
        self.entriesLayout.addWidget(self.yearbaseEntry, self.row, 2, 1, 1)
        #   * Output File Base
        self.row += 1
        self.entriesLayout.addWidget(
            CustomLabel('Cruise Name:',
                        style='h3', parent=self), self.row, 0)
        choices = [str(val) for val in self.found_data['cruiseid']]
        self.cruiseidDropdown = CustomDropdown(choices, parent=self)
        self.entriesLayout.addWidget(self.cruiseidDropdown, self.row, 1, 1, 1)
        self.cruiseidEntry = QLineEdit(parent=self)
        self.cruiseidEntry.setValidator(CruisenameValidator(parent=self))
        if len(choices) == 1:
            self.cruiseidEntry.setText(choices[0])
        self.entriesLayout.addWidget(self.cruiseidEntry, self.row, 2, 1, 1)
        self.row += 1
        self.cruiseidStr = "File to be created: %s/%s_proc.py"
        self.cruiseidLabel = QLabel(
            self.cruiseidStr % (self.config_dir, self.cruiseidEntry.text()),
            parent=self)
        self.cruiseidLabel.setWordWrap(True)
        self.cruiseidLabel.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(self.cruiseidLabel, self.row, 0, 1, 3)
        self._separator()
        # - Drop downs for feeds
        #   * Position
        self.row += 1
        self.positionFrame = CustomFrame("Position", parent=self)
        self.positionWidget = CustomCheckboxDropdown(
            "Position", self.position_feeds, parent=self.positionFrame)
        self.entriesLayout.addWidget(self.positionFrame, self.row, 0, 1, 3)
        #   * Heading
        self.row += 1
        self.headingFrame = CustomFrame("Heading", parent=self)
        self.headingWidget = CustomCheckboxDropdown(
            "Heading", self.heading_feeds, parent=self.headingFrame)
        self.entriesLayout.addWidget(self.headingFrame, self.row, 0, 1, 3)
        #   * Pitch & Roll
        self.row += 1
        self.pitchNrollFrame = CustomFrame("PitchnRoll", parent=self)
        self.pitchNrollWidget = CustomCheckboxDropdown(
            "Pitch & Roll", self.pitch_roll_feeds,
            checkbox=True, parent=self.pitchNrollFrame)
        self.entriesLayout.addWidget(self.pitchNrollFrame, self.row, 0, 1, 3)
        #   * Heading Correction
        self.row += 1
        self.headingCorrFrame = CustomFrame("HeadingCorrection", parent=self)
        self.headingCorrWidget = CustomCheckboxDropdown(
            "Heading Correction", self.heading_correction_feeds,
            checkbox=True, parent=self.headingCorrFrame)
        self.entriesLayout.addWidget(self.headingCorrFrame, self.row, 0, 1, 3)
        #   * Heading Cutoff
        self.row += 1
        self.entriesLayout.addWidget(CustomLabel(
            '-Found-', style='h3', parent=self), self.row, 1, 1, 1)
        self.entriesLayout.addWidget(CustomLabel(
            '-Final-', style='h3', parent=self), self.row, 2, 1, 1)
        self.row += 1
        self.entriesLayout.addWidget(CustomLabel(
            '$PASHR heading accuracy threshold: ',
            style='h3', parent=self), self.row, 0, 1, 1)
        choices = [str(val) for val in self.found_data['acc_heading_cutoff']]
        self.cutoffDropdown = CustomDropdown(choices, parent=self)
        self.entriesLayout.addWidget(self.cutoffDropdown, self.row, 1, 1, 1)
        self.cutoffEntry = QLineEdit(parent=self)
        self.cutoffEntry.setValidator(QDoubleValidator())
        if len(choices) == 1:
            self.cutoffEntry.setText(choices[0])
        self.entriesLayout.addWidget(self.cutoffEntry, self.row, 2, 1, 1)
        self._separator()
        # - tabs container
        self.row += 1
        self.tabsContainer = QTabWidget(parent=self)
        self.tabsDict = dict()
        for adcp_name in self.adcps:
            param_dict = self._sort_adcp_params(adcp_name)
            tab = UHDASProcTab(
                adcp_name, param_dict, self,
                called_from_form=called_from_form)
            self.tabsContainer.addTab(tab, adcp_name)
            self.tabsDict[adcp_name] = tab
        self.entriesLayout.addWidget(self.tabsContainer, self.row, 0, 1, -1)
        # - action buttons' box
        self.row += 1
        self.buttonsBox = QWidget(parent=self)
        self.buttonsLayout = QHBoxLayout()
        self.buttonsBox.setLayout(self.buttonsLayout)
        # - Make config Button
        self.makeButton = CustomPushButton("Make\nConfig File", self)
        self.makeButton.setStyleSheet(backGroundKey + green)
        self.buttonsLayout.addWidget(self.makeButton, Qt.AlignCenter)
        # - set up Proc. dir. Button
        if self.called_from_form:
            self.setupButton = CustomPushButton(
                "Set up\nProcessing Directories", self)
            self.setupButton.setStyleSheet(backGroundKey + red)
            self.buttonsLayout.addWidget(self.setupButton, Qt.AlignCenter)
            self.setupButton.setEnabled(False)
        self.entriesLayout.addWidget(self.buttonsBox, self.row, 0, 1, 3)
        # Connection Widgets/slots
        self.projectDirEntry.textChanged.connect(self.on_change_project_dir)
        self.browseButton.clicked.connect(self.on_select_project_dir)
        self.yearbaseDropdown.currentIndexChanged.connect(
            lambda: self.yearbaseEntry.setText(
                self.yearbaseDropdown.currentText()))
        self.cruiseidEntry.textChanged.connect(self.on_change_file_base)
        self.cruiseidDropdown.currentIndexChanged.connect(
            lambda: self.cruiseidEntry.setText(
                self.cruiseidDropdown.currentText()))
        self.cutoffDropdown.currentIndexChanged.connect(
            lambda: self.cutoffEntry.setText(
                self.cutoffDropdown.currentText()))
        self.makeButton.clicked.connect(self.write_config)
        if self.called_from_form:
            self.setupButton.clicked.connect(self.on_setup)
        # User Info
        for adcp in self.adcps:
            self._print("Transducer angle estimation for %s" % adcp)
            self.run_command([
                "EA_estimator.py", adcp[:2],
                os.path.join(self.uhdas_dir, 'raw', adcp, '*.raw')])
        # Put the layout into a scroll area (L. Longren, 02/2024)
        scroll = QScrollArea()
        wrapper_widget = QWidget()
        wrapper_widget.setLayout(self.entriesLayout)
        scroll.setWidget(wrapper_widget)
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)

    # Slots
    def on_change_project_dir(self):
        self.project_dir = self.projectDirEntry.text()
        self.config_dir = os.path.join(self.project_dir, 'config')
        self.cruiseidLabel.setText(
            self.cruiseidStr % (self.config_dir, self.cruiseidEntry.text()))

    def on_select_project_dir(self):
        selected_dir = QFileDialog.getExistingDirectory(
            caption='Select your Project directory',
            directory=self.project_dir,
            parent=self,
            options=QFileDialog.DontUseNativeDialog)
        if selected_dir:
            # self.project_dir = selected_dir
            # Update-labels
            self.projectDirEntry.setText(selected_dir)

    def on_change_file_base(self):
        self.cruiseid = self.cruiseidEntry.text()
        self.cruiseidLabel.setText(
            self.cruiseidStr % (self.config_dir, self.cruiseid))

    def on_setup(self):
        make_busy_cursor()
        # sanity check
        list_proc_py = glob(os.path.join(self.config_dir, '*_proc.py'))
        if not list_proc_py:
            msg = "There is no *_proc.py file in %s" % self.config_dir
            msg += "\nAddress & try again."
            restore_cursor()
            return
        # launch next form
        self._print("===Please wait for the next form to pop-up===")
        cruise_dir = os.path.abspath(self.project_dir)
        ProcSelectorPopUp(proc_prefix=self.cruiseid, from_enr=False,
                          cruise_dir=cruise_dir, parent=self)
        self.hide()
        restore_cursor()
        return

    # Methods
    def write_config(self):
        """
        Use values in boxes to generate a Bunch pass that to Proc_Gen
        """
        # Sanity Checks
        # - check if form is filled
        base_str = self.cruiseidEntry.text()
        year_str = self.yearbaseEntry.text()
        cutoff_str = self.cutoffEntry.text()
        angle_dict = dict()
        depth_dict = dict()
        for adcp_name in self.adcps:
            angle_str = self.tabsDict[adcp_name].angleEntry.text()
            depth_str = self.tabsDict[adcp_name].depthEntry.text()
            if not (angle_str and depth_str and base_str and year_str and cutoff_str):
                msg = "\nInformation is missing.\n"
                msg += "Please fill-in every entries and try again."
                self._print(msg, color='red')
                _log.debug(msg + '; angle_str: ' + angle_str +
                          '; depth_str: ' + depth_str +
                          '; base_str: ' + base_str +
                          '; year_str: ' + year_str +
                          '; cutoff_str: ' + cutoff_str)
                return
            else:
                angle_dict[adcp_name] = float(angle_str)
                depth_dict[adcp_name] = int(depth_str)
        # - folder exists?
        if not os.path.exists(self.config_dir):
            os.mkdir(self.config_dir)
        # - check if *proc.py already exists
        outfile = os.path.join(self.config_dir, '%s_proc.py' % base_str)
        if self._exists(outfile):
            return
        # - check if heading feed != heading correction feed
        hdg_feed = self.headingWidget.dropDown.currentText()
        hdg_corr_feed = self.headingCorrWidget.dropDown.currentText()
        if self.headingCorrWidget.dropDown.isEnabled():
            if hdg_feed == hdg_corr_feed:
                msg = "\nHeading feed and heading correction feed must"
                msg += " be different.\n"
                msg += "Change choices accordingly and try again."
                self._print(msg, color='red')
                _log.debug(msg)
                return
        # Retrieve user inputs
        config = Bunch()
        # - values
        config['shipkey'] = self.shipkey
        config['adcp'] = self.adcps
        config['cruiseid'] = self.cruiseid
        config['yearbase'] = int(year_str)
        config['uhdas_dir'] = self.uhdas_dir
        config['h_align'] = angle_dict
        config['ducer_depth'] = depth_dict
        config['acc_heading_cutoff'] = float(cutoff_str)
        # - feeds & messages
        config['pos_inst'], config['pos_msg'] = eval(
            self.positionWidget.dropDown.currentText())
        config['hdg_inst'], config['hdg_msg'] = eval(hdg_feed)
        config['roll_inst'] = ''
        config['roll_msg'] = ''
        if self.pitchNrollWidget.dropDown.isEnabled():
            config['pitch_inst'], config['pitch_msg'] = eval(
                self.pitchNrollWidget.dropDown.currentText())
            config['roll_inst'] = config['pitch_inst']
            config['roll_msg'] = config['pitch_msg']
        config['hcorr_inst'] = ''
        config['hcorr_msg'] = ''
        if self.headingCorrWidget.dropDown.isEnabled():
            config['hcorr_inst'], config['hcorr_msg'] = eval(hdg_corr_feed)
        else:
            config['hcorr_gap_fill'] = '0.0'
        # - feeds & messages list
        config['hdg_inst_msgs'] = []
        config['hdg_inst_msgs'].append(eval(hdg_feed))
        for hhs in self.heading_feeds + self.heading_correction_feeds:
            feed = eval(hhs)
            if feed not in config['hdg_inst_msgs']:
                config['hdg_inst_msgs'].append(feed)
        # - additional variables
        for name in ['max_search_depth', 'enslength', 'salinity', 'soundspeed',
                     'pgmin', 'weakprof_numbins', 'scalefactor', ]:
            config[name] = Bunch()
            for adcp_name in config['adcp']:
                for ip in uhdas_defaults.instpings(adcp_name):
                    config[name][ip] = uhdas_defaults.proc_sonar_defaults[name][ip]
        # FIXME: LEGACY BUG - this does not play well
        P = Proc_Gen(shipinfo=config)
        pstr = 'cruiseid = "%s"  # for titles\n' % config['cruiseid']
        pstr += 'yearbase = %d  # usually year of first data logged\n' % (
            config['yearbase'])
        pstr += 'uhdas_dir = "%s"\n' % config['uhdas_dir']
        pstr = pstr + P.T.pstr

        # write config file
        if os.path.exists(outfile):
            self._print('Cannot write processing config file %s ' % outfile,
                        color='red')
            self._print('---> Remove first, then try again', color='red')
            return
        else:
            with open(outfile, 'w') as file:
                file.write(pstr)
            _log.info('%s has been created.' % outfile)
            _log.info('Your quick_adcp.py control file should start with this:')
            _log.info(' --yearbase  %s' % (config['yearbase']))
            _log.info(' --cruisename %s' % (config['cruiseid']))
            msg = PROC_STARTER_END_MSG % (
                config['yearbase'], config['cruiseid'])
            self._print(msg) # , color='red')
            # Reveal set up button
            if self.called_from_form:
                self.setupButton.setEnabled(True)
            # Inform user on next steps
            cruise_dir = os.path.abspath(os.path.join(self.config_dir, '..'))
            msg = SINGLE_PING_READY_MSG % cruise_dir
            msg += "\nOr create more alternative config. files"
            self._print(msg, color='red')

    def _sort_adcp_params(self, adcp_name):
        # Aggregate found" and "default" values
        params = dict()
        for required_key in self.required_data.keys():
            params[required_key] = []
            # - default values
            default_params = []
            if required_key in proc_instrument_defaults.keys():
                default_params.append(
                    proc_instrument_defaults[required_key][adcp_name])
            if required_key in proc_constant_defaults.keys():
                default_params.append(
                    proc_constant_defaults[required_key])
            #  * Unique values
            if len(default_params) > 1:
                default_params = list(set(default_params))
            params[required_key].extend(default_params)

            # FIXME: I am not adding default values from proc_model_defaults
            #        because its structure is to weird and I can't deal with
            #        this anymore
            # - found values
            found_params = self.found_data[required_key]
            # Note: Different behavior if parameter is a list of dict
            if found_params:
                if isinstance(found_params[0], dict):
                    try:
                        found_params = [part[adcp_name] for part in found_params]
                    except KeyError:
                        found_params = []
                elif isinstance(found_params[0], list):  # quick fix forhdg_inst_msgs
                    found_params = []
            #  * Unique values
            if len(found_params) > 1:
                found_params = list(set(found_params))
            params[required_key].extend(found_params)
        _log.debug("Sorted parameters: %s", params)

        return params


class UHDASProcTab(GenericForm):
    def __init__(self, adcp_name, ini_data, main_widget,
                 called_from_form=True):
        """
        Create a new UHDAS configuration file for processing for a given Sonar

        Args:
            adcp_name: ADCP name (wh300, os75, ..., str.
            ini_data: initial data, dict
            required_data: Required data, dict
            called_from_form: backend boolean switch, bool
            parent: parent PyQt widget
        """
        super().__init__(main_widget)
        # Override Generic layout
        self.dock.setVisible(False)
        # load initial data
        if isinstance(ini_data, dict):
            ini_data = Bunch(ini_data)
        msg = "initial data:\n" + str(ini_data)
        _log.debug(msg)
        # Attributes
        self.main_widget = main_widget
        self.called_from_form = called_from_form
        self.cruiseid = ini_data.cruiseid
        self.adcp = adcp_name
        self.transducer_angle = ini_data.h_align
        self.transducer_depth = ini_data.ducer_depth
        # Form style
        self.setWindowTitle('Proc Starter Form')
        # Widgets
        #   * context
        self.row += 1
        self.entriesLayout.addWidget(CustomLabel(
            '-Found-', style='h3', parent=self), self.row, 1, 1, 1)
        self.entriesLayout.addWidget(CustomLabel(
            '-Final-', style='h3', parent=self), self.row, 2, 1, 1)
        #   * Transducer Angle
        self.row += 1
        choices = [str(val) for val in self.transducer_angle]
        self.angleDropdown = CustomDropdown(choices, parent=self)
        self.angleEntry = QLineEdit(parent=self)
        self.angleEntry.setValidator(QDoubleValidator(-180.00, 180.00, 2))
        self.entriesLayout.addWidget(CustomLabel(
            'Transducer Angle (EA):   ',
            style='h3', parent=self), self.row, 0, 1, 1)
        self.entriesLayout.addWidget(self.angleDropdown, self.row, 1, 1, 1)
        self.entriesLayout.addWidget(self.angleEntry, self.row, 2, 1, 1)
        if len(choices) == 1:
            self.angleEntry.setText(choices[0])
        self.row += 1
        note1 = QLabel(
            "(deg.), positive clockwise, [-180, 180], see hint below",
            parent=self)
        note1.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note1, self.row, 0, 1, 2)
        #   * Transducer depth
        self.row += 1
        choices = [str(val) for val in self.transducer_depth]
        self.depthDropdown = CustomDropdown(choices, parent=self)
        self.depthEntry = QLineEdit(parent=self)
        self.depthEntry.setValidator(QIntValidator())
        self.entriesLayout.addWidget(CustomLabel(
            'Transducer Depth below surface: ', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.entriesLayout.addWidget(self.depthDropdown, self.row, 1, 1, 1)
        self.entriesLayout.addWidget(self.depthEntry, self.row, 2, 1, 1)
        if len(choices) == 1:
            self.depthEntry.setText(choices[0])
        self.row += 1
        note2 = QLabel("(m), positive downwards, eg. 3, 4, 5", parent=self)
        note2.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note2, self.row, 0, 1, 2)

        # Connect
        self.angleDropdown.currentIndexChanged.connect(
            lambda: self.angleEntry.setText(self.angleDropdown.currentText()))
        self.depthDropdown.currentIndexChanged.connect(
            lambda: self.depthEntry.setText(self.depthDropdown.currentText()))

    def _estimate_transducer_angle(self):
        """
        Estimate transducer angle aka EA from files

        N.B.: adapted legacy code
        """
        # Inputs
        instrument = self.adcp[:2]
        underway = 5.0
        raw_path = "%s/raw/%s/*.raw" % (self.main_widget.uhdas_dir, self.adcp)
        raw_files = glob(raw_path)
        ea = []
        # Sanity check
        empty_files = []
        for f in raw_files:
            if os.path.getsize(f) == 0:
                empty_files.append(f)
        for f in empty_files:
            raw_files.remove(f)
        # Alignment Estimation
        m = Multiread(raw_files, instrument)
        data = m.read(step=10)
        # - watertrack
        mag, a, iused = get_xducer_angle(data, 4)
        igood = np.where(mag > underway)[0]
        if any(igood):
            S = Stats(a[igood])
            ea.append(np.round(S.mean, 2))
        # - bottomtrack
        if data.bt_xyze.count() > 0:
            mag, a, iused = get_xducer_angle(data, -1)
            if not len(iused) == 0:
                igood = np.where(mag > underway)[0]
                if any(igood):
                    S = Stats(a[igood])
                    ea.append(np.round(S.mean, 2))

        return ea


if __name__ == '__main__':
    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        from pycurrents.get_test_data import get_test_data_path
        test_folder_path = get_test_data_path()
        uhdas_dir = test_folder_path + '/uhdas_data/'
        app = QApplication(sys.argv)
        form = UHDASProcGenForm(uhdas_dir=uhdas_dir)
        form.show()
        sys.exit(app.exec_())
    else:
        from argparse import ArgumentParser
        arglist = sys.argv[1:]
        parser = ArgumentParser()
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
