#!/usr/bin/env python3

import os
import sys
import logging
from glob import glob
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QLabel, QLineEdit, QWidget, QHBoxLayout, QApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QFont, QDoubleValidator, QIntValidator
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt

# BREADCRUMB: common library, begin block...
from pycurrents.adcp.vmdas import VmdasInfo
from pycurrents.adcp import uhdas_defaults
from pycurrents.adcp.uhdasconfig import Proc_Gen
from pycurrents.system.misc import Bunch
from pycurrents.system.logutils import unexpected_error_msg
# BREADCRUMB: ...common library, end block
from pycurrents.adcpgui_qt.lib.miscellaneous import vars_from_fud
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomLabel,
    CruisenameValidator, CustomFrame, CustomCheckboxDropdown, CustomPushButton,
    backGroundKey, green, red, make_busy_cursor, restore_cursor)
from pycurrents.adcpgui_qt.lib.miscellaneous import (
    list_vmdas_files, EA_estimation_from_enr)
from pycurrents.adcpgui_qt.forms.generic_form import GenericForm
from pycurrents.adcpgui_qt.forms.adcp_tree_form import ProcSelectorPopUp
from pycurrents.adcpgui_qt.forms.string_templates import (
    PROC_STARTER_END_MSG, SINGLE_PING_READY_MSG)

# Standard logging
_log = logging.getLogger(__name__)

# TODO: change text and variable names accordingly with naming convention


class ProcStarterForm(GenericForm):
    def __init__(self, reform_defs_path, config_path='',
                 start_path=os.path.expanduser('~'),
                 called_from_form=True, parent=None):
        """
        Create a UHDAS configuration file
        (i.e. .../sonar_proc/config/*_proc.py) for processing
        UHDAS-style data (aka converted ENR data)

        Args:
            reform_defs_path: path to reform_defs_*.py, str.
            config_path: path to config directory, str.
            start_path: starting path for browsing file system, str.
            parent: PySide6 or PyQt5 parent widget
        """
        super().__init__(parent)
        # load initial data
        ini_data = vars_from_fud(reform_defs_path)
        msg = "initial data from reform_defs.py:\n" + str(ini_data)
        _log.debug(msg)
        # Attributes
        self.called_from_form = called_from_form
        self.start_path = start_path
        self.shipkey = ini_data.shipkey
        self.cruisename = ini_data.cruisename
        self.sonar = ini_data.adcp
        yearbase = ini_data.yearbase
        if yearbase:
            self.yearbase = ini_data.yearbase
        else:
            msg = 'yearbase is missing in reform_defs.py'
            print(msg)
            _log.error(msg)
            return
        self.transducer_angle = ini_data.h_align
        self.transducer_depth = ini_data.ducer_depth
        self.position_feeds = ini_data.lists.position
        self.heading_feeds = list(reversed(ini_data.lists.heading))
        # N.B.: reversed in order to have synchro last
        self.pitch_roll_feeds = ini_data.lists.rollpitch
        self.heading_correction_feeds = list(reversed(ini_data.lists.hcorr))
        # N.B.: reversed in order to have synchro last
        if not config_path:
            self.config_path = os.getcwd()
        else:
            self.config_path = os.path.abspath(config_path)
        self.uhdas_dir = ini_data.uhdas_dir
        self.vmdas_dir = ini_data.vmdas_dir
        # Form style
        self.setWindowTitle('Proc Starter Form')
        # Widgets
        # - Info labels
        #   * uhdas dir
        self.entriesLayout.addWidget(CustomLabel(
            'UHDAS Data Directory: ', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.uhdasDirLabel = QLabel(self.uhdas_dir, parent=self)
        self.uhdasDirLabel.setWordWrap(True)
        self.entriesLayout.addWidget(self.uhdasDirLabel, self.row, 1, 1, 1)
        #   * year base
        self.row += 1
        self.entriesLayout.addWidget(CustomLabel(
            'Year of Cruise: ', style='h3', parent=self), self.row, 0, 1, 1)
        self.yearbaseLabel = QLabel(str(self.yearbase), parent=self)
        self.entriesLayout.addWidget(self.yearbaseLabel, self.row, 1, 1, 1)
        #   * sonar
        self.row += 1
        self.entriesLayout.addWidget(CustomLabel(
            'Sonar: ', style='h3', parent=self), self.row, 0, 1, 1)
        self.sonarLabel = QLabel(self.sonar, parent=self)
        self.entriesLayout.addWidget(self.sonarLabel, self.row, 1, 1, 1)
        # - User entries
        #   * Output File Base
        self.row += 1
        self.fileBaseEntry = QLineEdit(self.cruisename, parent=self)
        self.fileBaseEntry.setValidator(CruisenameValidator(parent=self))
        self.entriesLayout.addWidget(
            CustomLabel('Output File Base:',
                        style='h3', parent=self), self.row, 0)
        self.entriesLayout.addWidget(self.fileBaseEntry, self.row, 1, 1, 1)
        self.row += 1
        self.fileBaseStr = "File to be created: %s/%s_proc.py"
        self.fileBaseLabel = QLabel(
            self.fileBaseStr % (self.config_path, self.cruisename),
            parent=self)
        self.fileBaseLabel.setWordWrap(True)
        self.fileBaseLabel.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(self.fileBaseLabel, self.row, 0, 1, 2)
        self._separator()
        #   * Transducer Angle
        self.row += 1
        self.angleEntry = QLineEdit(parent=self)
        self.angleEntry.setValidator(QDoubleValidator(-180.00, 180.00, 2))
        self.entriesLayout.addWidget(CustomLabel(
            'Transducer Angle (EA):   ',
            style='h3', parent=self), self.row, 0, 1, 1)
        self.entriesLayout.addWidget(self.angleEntry, self.row, 1, 1, 1)
        self.row += 1
        note1 = QLabel(
            "(deg.), positive clockwise, [-180, 180], see hint below",
            parent=self)
        note1.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note1, self.row, 0, 1, 2)
        #   * Transducer depth
        self.row += 1
        self.depthEntry = QLineEdit(str(self.transducer_depth), parent=self)
        self.depthEntry.setValidator(QIntValidator())
        self.entriesLayout.addWidget(CustomLabel(
            'Transducer Depth below surface: ', style='h3', parent=self),
            self.row, 0, 1, 1)
        self.entriesLayout.addWidget(self.depthEntry, self.row, 1, 1, 1)
        self.row += 1
        note2 = QLabel("(m), positive downwards, eg. 3, 4, 5", parent=self)
        note2.setFont(QFont("?", 10, italic=True))
        self.entriesLayout.addWidget(note2, self.row, 0, 1, 2)
        # - Drop downs
        #   * Position
        self.row += 1
        self.positionFrame = CustomFrame("Position", parent=self)
        self.positionWidget = CustomCheckboxDropdown(
            "Position", self.position_feeds, parent=self.positionFrame)
        self.entriesLayout.addWidget(self.positionFrame, self.row, 0, 1, 2)
        #   * Heading
        self.row += 1
        self.headingFrame = CustomFrame("Heading", parent=self)
        self.headingWidget = CustomCheckboxDropdown(
            "Heading", self.heading_feeds, parent=self.headingFrame)
        self.entriesLayout.addWidget(self.headingFrame, self.row, 0, 1, 2)
        #   * Pitch & Roll
        self.row += 1
        self.pitchNrollFrame = CustomFrame("PitchnRoll", parent=self)
        self.pitchNrollWidget = CustomCheckboxDropdown(
            "Pitch & Roll", self.pitch_roll_feeds,
            checkbox=True, parent=self.pitchNrollFrame)
        self.entriesLayout.addWidget(self.pitchNrollFrame, self.row, 0, 1, 2)
        #   * Heading Correction
        self.row += 1
        self.headingCorrFrame = CustomFrame("HeadingCorrection", parent=self)
        self.headingCorrWidget = CustomCheckboxDropdown(
            "Heading Correction", self.heading_correction_feeds,
            checkbox=True, parent=self.headingCorrFrame)
        self.entriesLayout.addWidget(self.headingCorrFrame, self.row, 0, 1, 2)
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
        self.entriesLayout.addWidget(self.buttonsBox, self.row, 0, 1, 2)
        # Connection Widgets/slots
        self.fileBaseEntry.textChanged.connect(self.on_change_file_base)
        self.makeButton.clicked.connect(self.write_config)
        if self.called_from_form:
            self.setupButton.clicked.connect(self.on_setup)
        # User Info
        self._transducer_angle_info()

    # Slots
    def on_change_file_base(self):
        self.cruisename = self.fileBaseEntry.text()
        self.fileBaseLabel.setText(
            self.fileBaseStr % (self.config_path, self.cruisename))

    def on_setup(self):
        make_busy_cursor()
        # sanity check
        list_proc_py = glob(os.path.join(self.config_path, '*_proc.py'))
        if not list_proc_py:
            msg = "There is no *_proc.py file in %s" % self.config_path
            msg += "\nAddress & try again."
            restore_cursor()
            return
        # launch next form
        self._print("===Please wait for the next form to pop-up===")
        cruise_dir = os.path.abspath(os.path.join(self.config_path, '..'))
        ProcSelectorPopUp(proc_prefix=self.cruisename, from_enr=True,
                          cruise_dir=cruise_dir, parent=self)
        self.hide()
        restore_cursor()
        return

    # Methods
    def write_config(self):
        """
        Use values in boxes to generate a Bunch pass that to Proc_Gen
        """
        # Check if form is filled
        angle_str = self.angleEntry.text()
        depth_str = self.depthEntry.text()
        base_str = self.fileBaseEntry.text()
        if not (angle_str and depth_str and base_str):
            msg = "\nInformation is missing.\n"
            msg += "Please fill-in every entries and try again."
            self._print(msg, color='red')
            _log.debug(msg + '; angle_str: ' + angle_str +
                      'depth_str; : ' + depth_str +
                      'base_str; : ' + base_str)
            return
        # check if *proc.py already exists
        outfile = os.path.join(self.config_path, '%s_proc.py' % base_str)
        if self._exists(outfile):
            return
        # Check if heading feed != heading correction feed
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
        config['adcp'] = self.sonar
        config['cruisename'] = self.cruisename
        config['yearbase'] = self.yearbase
        config['uhdas_dir'] = self.uhdas_dir
        config['h_align'] = {self.sonar: float(angle_str)}
        config['ducer_depth'] = {self.sonar: float(depth_str)}
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
        for hhs in self.heading_feeds:
            config['hdg_inst_msgs'].append(eval(hhs))
        # - additional variables
        for name in ['max_search_depth', 'enslength', 'salinity', 'soundspeed',
                     'pgmin', 'weakprof_numbins', 'scalefactor', ]:
            config[name] = Bunch()
            for ip in uhdas_defaults.instpings(config['adcp']):
                config[name][ip] = uhdas_defaults.proc_sonar_defaults[name][ip]
        # FIXME: LEGACY BUG - this does not play well
        P = Proc_Gen(shipinfo=config)
        pstr = 'cruiseid = "%s"  # for titles\n' % config['cruisename']
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
            _log.info(' --cruisename %s' % (config['cruisename']))
            msg = PROC_STARTER_END_MSG % (
                config['yearbase'], config['cruisename'])
            self._print(msg) # , color='red')
            # Reveal set up button
            if self.called_from_form:
                self.setupButton.setEnabled(True)
            # Inform user on next steps
            cruise_dir = os.path.abspath(os.path.join(self.config_path, '..'))
            msg = SINGLE_PING_READY_MSG % cruise_dir
            msg += "\nOr create more alternative config. files"
            self._print(msg, color='red')

    def _transducer_angle_info(self):
        """
        Estimate transducer angle aka EA from files

        N.B.: adapted legacy code
        """
        # - estimating EA
        #  * from files
        #    N.B.: legacy code
        vmdas_files = []
        if self.vmdas_dir:
            enr_files, lta_files, sta_files = list_vmdas_files(self.vmdas_dir)
            vmdas_files = enr_files
        if vmdas_files:
            VM = VmdasInfo(vmdas_files, model=self.sonar[:2])
            ea_from_files = [str(i) for i in VM.get_beaminst_info()]
            msg = 'Transducer angle(s) used in LTA: '
            msg += ', '.join(ea_from_files)
            _log.debug(msg)
            self._print(msg, color='red')
        #  * from data
        #    N.B.: legacy code
        if enr_files:
            try:
                inst_type = self.sonar[:2]
                msg = EA_estimation_from_enr(enr_files, inst_type)
                self._print(msg, color='red')
            except Exception as e:  # FIXME: too vague! What is the actual exception?
                self._data = None
                _log.error(unexpected_error_msg(e))
                pass


if __name__ == '__main__':
    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        from pycurrents.get_test_data import get_test_data_path
        test_folder_path = get_test_data_path()
        config_path = test_folder_path + '/uhdas_style_data/config/'
        reform_defs_path = config_path + 'reform_defs_os75.py'
        app = QApplication(sys.argv)
        form = ProcStarterForm(reform_defs_path, config_path=config_path,
                               start_path=config_path)
        form.show()
        sys.exit(app.exec_())
    else:
        from argparse import ArgumentParser
        arglist = sys.argv[1:]
        parser = ArgumentParser()
        help = "Path to reform_defs_*.py. Must be in *CRUISE_PROC_DIR*/config/"
        parser.add_argument(
            "reform_defs_path", metavar='reform_defs_path',
            type=str, nargs='?', default='', help=help)
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
                               start_path=options.start_path)
        form.show()
        sys.exit(app.exec_())
