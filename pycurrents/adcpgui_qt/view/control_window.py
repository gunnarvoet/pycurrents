import os
import sys
from tempfile import gettempdir
import logging

from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import QSettings, QFileSystemWatcher, QSize, Qt
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QTabWidget, QFileDialog, QMainWindow
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QRadioButton, QStatusBar, QTextEdit, QTextBrowser
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QSpacerItem, QCheckBox, QWidget, QVBoxLayout, QScrollArea
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QLabel, QGridLayout, QApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QIcon, QGuiApplication

from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomLabel, CustomDialogBox,
    CustomPushButton, CustomEntry, CustomButton, CustomFrame, CustomSpinbox,
    CustomCheckboxEntries, CustomDropdownCompareMode, CustomDropdown,
    CustomPanelVLayout, CustomPanelGridLayout, CustomScrollTab,
    CustomCheckboxEntryLabel, CustomSeparator, ConsoleWidget, ClickableSlider,
    leftArrow, rightArrow, globalStyle, iconUHDAS, modeColor, backGroundKey,
    red, blue, green, purple, silver, borderKey, roundCorners, silverBackGroundColor)
from pycurrents.adcpgui_qt.model.display_features_models import (
    DisplayFeaturesSingleton, get_setting_parameter_list,
    get_settings_template)
from pycurrents.adcpgui_qt.lib.miscellaneous import (
    utc_formatting, write_dict2config_file)


# Standard logging
_log = logging.getLogger(__name__)

# Singletons
DISPLAY_FEAT = DisplayFeaturesSingleton()

# For debugging purposes
licensePath = __file__

### Control Window ###
class ControlWindow(QMainWindow):
    def __init__(self, ascii_log, mode="view", thresholds=None,
                 parent=None, test=False):
        """
        Main control window. Custom class derived from QMainWindow

        Args:
            ascii_log: filename/absolute path to ascii log file, str
        Keyword Args:
            mode: str, GUI mode, i.e. "compare", "view", "edit",
                  "patch" or "single ping"
            thresholds: edit thresholds container (only required in edit mode)
            parent: parent QWidget
            test: boolean switch for testing purposes
        """
        super().__init__(parent)
        # Global variables
        global THRESHOLDS, ASCII_LOG
        ASCII_LOG = ascii_log
        if mode == "edit" and not thresholds:
            _log.error("ERROR INPUTS: Thresholds container is missing")
        else:
            THRESHOLDS = thresholds
        # Attributes
        self.test = test
        #  - Gui's mode
        self.mode = mode
        #  - dataset features
        self.yearbase = DISPLAY_FEAT.year_base
        self.day_range = DISPLAY_FEAT.day_range
        # Widgets
        #  - Time range info
        label = "Time range: {0}, {1} - {2} ({3} - {4})".format(
            self.yearbase,
            # Fix for Ticket 685
            utc_formatting(self.day_range[0], yearbase=self.yearbase),
            utc_formatting(self.day_range[1], yearbase=self.yearbase),
            round(self.day_range[0], 2),
            round(self.day_range[1], 2))
        self.timeInfo = CustomLabel(label, style='h3')
        #  - Tabs container
        self.tabsContainer = TabsContainer(parent=self)
        #  - Time navigation bar
        if not DISPLAY_FEAT.mode == "patch":
            self.timeNavigationBar = TimeNavigationBar(parent=self)
        #  - Edit Bar
        if DISPLAY_FEAT.mode in ['compare', 'edit']:
            self.editBar = EditBar()
        #  - Patch Bar + UTC check box
        if DISPLAY_FEAT.mode == "patch":
            self.patchBar = PatchBar()
            self.checkboxUtcDate = QCheckBox("x = UTC dates")
        # Layout: define central widget and other main window decorator
        #  - Adding vertical box
        self.vbox = QWidget()
        self.vbox.layout = QVBoxLayout()
        self.vbox.layout.addWidget(self.timeInfo, 0)
        if not DISPLAY_FEAT.mode == "patch":
            self.vbox.layout.addWidget(self.timeNavigationBar, 0)
        if DISPLAY_FEAT.mode in ['compare', 'edit']:
            self.vbox.layout.addWidget(self.editBar, 0)
        if DISPLAY_FEAT.mode == "patch":
            self.vbox.layout.addWidget(self.patchBar, 0)
            self.vbox.layout.addWidget(self.checkboxUtcDate, 0)
        # self.vbox.layout.addWidget(self.tabsContainer, 0)
        self.vbox.setLayout(self.vbox.layout)
        #  - Status bar
        self.statusBar = QStatusBar(self)
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Work. Dir.: " + os.getcwd())
        #  - scrollable when shrunk
        self.scrollable = QScrollArea()
        self.scrollable.setWidgetResizable(True)
        self.scrollable.setWidget(self.tabsContainer)
        self.vbox.layout.addWidget(self.scrollable, 0)
        #  - define central widget
        self.setCentralWidget(self.vbox)  # self.scrollable)

        # Style
        # - Dimensions
        defaultWidth = int(
            self.tabsContainer.sizeHint().width() +
            2 * self.scrollable.verticalScrollBar().sizeHint().width())
        defaultHeight = int(
            self.tabsContainer.sizeHint().height() +  # FIXME - get height of top panel + top tab individually per mode
            self.timeInfo.sizeHint().height() +
            self.statusBar.sizeHint().height() +
            self.scrollable.horizontalScrollBar().sizeHint().height())
        if not DISPLAY_FEAT.mode == "patch":
            defaultHeight += self.timeNavigationBar.sizeHint().height()
        else:
            defaultHeight += self.patchBar.sizeHint().height()
            defaultHeight += self.checkboxUtcDate.sizeHint().height()
            defaultHeight += int(
                0.2 * self.tabsContainer.patchTab.sizeHint().height())  # FIXME: fudge factor
        if DISPLAY_FEAT.mode in ['compare', 'edit']:
            defaultHeight += self.editBar.height()
        defaultSize = QSize(defaultWidth, defaultHeight)
        # - Aspect
        self.setStyleSheet(modeColor[DISPLAY_FEAT.mode])
        self.statusBar.setStyleSheet(silverBackGroundColor)
        self.scrollable.horizontalScrollBar().setStyleSheet(
            silverBackGroundColor)
        self.scrollable.verticalScrollBar().setStyleSheet(
            silverBackGroundColor)
        self.scrollable.setFrameStyle(0)
        self.setWindowTitle('UHDAS ADCP - Mode: ' + DISPLAY_FEAT.mode)
        self.setWindowIcon(QIcon(iconUHDAS))
        self.resize(defaultSize)
        # - Position
        screen_geometry = QGuiApplication.primaryScreen().geometry()
        widget = self.geometry()
        x = 0
        y = screen_geometry.height() - widget.height()
        self.move(x, y)

        # Settings and standard restoring
        settings = QSettings()
        settings.setValue('MainWindow/State', self.saveState())

        # Local connection
        if DISPLAY_FEAT.mode == "edit":
            self.tabsContainer.currentChanged.connect(self._on_tab_change)

    # Local callbacks
    def _on_tab_change(self, evt):
        """
        Tick checkboxShowThresholdEdit in the plotTab
        when moving to thresholdTab

        Args:
            evt: tab index, int
        """
        if evt == 1:  # equivalent to Thresholds tab's index
            checkBox = self.tabsContainer.plotTab.checkboxShowThresholdEdit
            if not checkBox.isChecked():
                checkBox.click()

    # Overridden Methods
    def closeEvent(self, ce):
        # Check if user reached the end of the dataset
        if DISPLAY_FEAT.mode != 'patch':
            end_time = DISPLAY_FEAT.start_day + DISPLAY_FEAT.day_step
            if end_time < DISPLAY_FEAT.day_range[1] and not self.test:
                # Ask if user wants to save progress
                message = "Do you want to save your DISPLAY"
                message += "\nprogress and settings before closing?"
                question = CustomDialogBox(message)
                # pop-up to chose location and suffix of the restart file
                # FIXME - move this block to .../lib/qtpy_widgets.py and
                #         turn into widget
                if question.answer:
                    # Saving progress
                    dialog_win = QFileDialog()
                    dialog_win.setDefaultSuffix("pgrs")
                    path_pgrs = dialog_win.getSaveFileName(
                        parent=self,
                        caption='Save Progress',
                        directory='./',
                        filter='Progress files(*.pgrs)',
                        initialFilter='pgrs')[0]
                    if path_pgrs:
                        # add suffix if need be
                        suffix = os.path.splitext(path_pgrs)[-1]
                        if not suffix:
                            path_pgrs += ".pgrs"
                        write_dict2config_file(
                            path_pgrs, DISPLAY_FEAT.__dict__,
                            section_name='DISPLAY_FEAT')
                    # saving settings
                    dialog_win = QFileDialog()
                    dialog_win.setDefaultSuffix("ini")
                    path_ini = dialog_win.getSaveFileName(
                        parent=self,
                        caption='Save Settings',
                        directory='./',
                        filter='Setting files(*.ini)',
                        initialFilter='ini')[0]
                    if path_ini:
                        # add suffix if need be
                        suffix = os.path.splitext(path_ini)[-1]
                        if not suffix:
                            path_ini += ".ini"
                        # gather setting parameters
                        params = []
                        for ii, key in enumerate(get_setting_parameter_list(
                                DISPLAY_FEAT.mode)):
                            params.append(DISPLAY_FEAT.__dict__[key])
                        # write the relevant entries
                        tmp = get_settings_template(DISPLAY_FEAT.mode)
                        msg = tmp % tuple(params)
                        file = open(path_ini, 'w')
                        file.write(msg)
                        file.close()
        # Finish by original callback
        super().closeEvent(ce)


### GUI elements ###
class EditBar(QFrame):
    def __init__(self, parent=None):
        """
        Editing bar composed of two buttons
        Args:
            parent: parent QWidget
        """
        super().__init__(parent)
        # Attributes and features
        self.setObjectName("EditBar")

        # Widgets
        self.buttonResetEditing = CustomPushButton("Reset Editing", self)
        self.buttonApplyEditing = CustomPushButton("Apply Editing", self)

        # Layout
        self.layout = QHBoxLayout()
        self.layout.setAlignment(Qt.AlignLeft)
        layoutWidgets = [self.buttonResetEditing, self.buttonApplyEditing]
        for widget in layoutWidgets:
            self.layout.addWidget(widget, 1)  # 1 make the buttons stretch
        self.layout.addStretch()
        self.setLayout(self.layout)

        # Style
        self.setFixedHeight(2 * self.buttonApplyEditing.sizeHint().height())
        self.buttonApplyEditing.setStyleSheet(backGroundKey + red)
        self.buttonResetEditing.setStyleSheet(backGroundKey + blue)


class PatchBar(QFrame):
    def __init__(self, parent=None):
        """
        Patching bar composed of 4 buttons
        Args:
            parent: parent QWidget
        """
        super().__init__(parent)
        # Attributes & features
        self.setObjectName("PatchBar")

        # Widgets
        self.buttonEdit = CustomPushButton("Edit", self)
        self.buttonSave = CustomPushButton("Save", self)
        self.buttonApply = CustomPushButton("Apply and Quit", self)
        self.checkboxUtcDate = QCheckBox("x = UTC dates")

        w = int(0.5 * self.buttonSave.sizeHint().width())
        h = int(0.5 * self.buttonSave.sizeHint().height())
        spacer = QSpacerItem(w, h, QSizePolicy.Minimum,
                             QSizePolicy.Expanding)
        # Layout
        self.layout = QHBoxLayout()
        layoutWidgets = [self.buttonEdit, self.buttonSave, self.buttonApply]
        for widget in layoutWidgets:
            if widget == spacer:
                self.layout.addItem(widget)
            else:
                self.layout.addWidget(widget)
        self.setLayout(self.layout)
        # Style
        self.setStyleSheet("#PatchBar {" + modeColor["patch"] +
                           borderKey + silver + roundCorners + "}")
        self.setFixedHeight(60)
        self.buttonEdit.setStyleSheet(backGroundKey + green)
        self.buttonSave.setStyleSheet(backGroundKey + blue)
        self.buttonApply.setStyleSheet(backGroundKey + purple)


class TimeNavigationBar(QFrame):
    def __init__(self, parent=None):
        """
        Time navigation bar
        Args:
            parent: parent QWidget
        """
        super().__init__(parent)
        # Attributes & features
        self.setObjectName("TimeNavigationBar")

        # Widgets
        self.entryStart = CustomEntry(size=70, entry_type=float,
                                      min_value=0., max_value=999.99,
                                      value=DISPLAY_FEAT.start_day)
        self.labelStart = QLabel("Start :")
        self.entryStep = CustomEntry(size=50, entry_type=float,
                                     min_value=0., max_value=100.,
                                     value=DISPLAY_FEAT.day_step)
        self.labelStep = QLabel("Step :")
        self.buttonPrev = CustomButton(icon_path=leftArrow,
                                       background_color=silverBackGroundColor)
        self.buttonNext = CustomButton(icon_path=rightArrow,
                                       background_color=silverBackGroundColor)
        self.buttonShow = CustomPushButton("Show")
        w = 2 * self.buttonNext.sizeHint().width()
        h = 2 * self.buttonNext.sizeHint().height()
        spacer = QSpacerItem(w, h, QSizePolicy.Minimum,
                             QSizePolicy.Expanding)

        # Layout
        self.layout = QHBoxLayout()
        self.layout.setAlignment(Qt.AlignLeft)
        #  - Add widgets and layouts in containers/Box
        layoutWidgets = [self.labelStart, self.entryStart, self.labelStep,
                         self.entryStep, spacer,
                         self.buttonPrev, self.buttonShow, self.buttonNext]
        for widget in layoutWidgets:
            if widget == spacer:
                # self.layout.addItem(widget)
                self.layout.addStretch(2)
            else:
                self.layout.addWidget(widget)
        self.layout.addStretch(1)
        self.setLayout(self.layout)

        # Style
        #  - widgets
        self.buttonShow.setFixedHeight(self.buttonNext.sizeHint().height() // 2)
        self.buttonShow.setStyleSheet(backGroundKey + green)
        #  - background
        self.setStyleSheet(
            "#TimeNavigationBar {" + modeColor[DISPLAY_FEAT.mode] + borderKey +
            silver + roundCorners + "}")
        self.setFixedHeight(self.buttonNext.sizeHint().height())


class TabsContainer(QTabWidget):
    def __init__(self, parent=None):
        """
        Tabs container
        Args:
            parent: parent QWidget
        """
        super().__init__(parent)
        # Attributes
        tabs = []
        keys = []
        # Load default tabs, i.e. "Plot", "Log"
        self.logTab = LogTab(parent=self)
        self.helpTab = HelpTab(parent=self)
        if DISPLAY_FEAT.mode != "patch":
            tabs.append("Plot")
            self.plotTab = PlotTab(DISPLAY_FEAT.mode,
                                   variables=DISPLAY_FEAT.axes_choices,
                                   parent=self)
            keys.append("plotTab")
        # Load optional tabs
        if DISPLAY_FEAT.mode == "patch":
            tabs.append("Patch")
            self.patchTab = PatchTab(parent=self)
            keys.append("patchTab")
        if DISPLAY_FEAT.mode == "edit":
            tabs.append("Thresholds")
            self.thresholdsTab = ThresholdsTab(parent=self)
            keys.append("thresholdsTab")
        tabs.append("Log")
        keys.append("logTab")
        if DISPLAY_FEAT.advanced:
            tabs.append("Console")
            self.consoleTab = ConsoleTab(parent=self)
            keys.append("consoleTab")
        tabs.append("Help")
        keys.append("helpTab")
        # Add tabs to container
        for name, key in zip(tabs, keys):
            self.addTab(getattr(self, key), name)
        # Style
        self.setStyleSheet(silverBackGroundColor)
        self.setCurrentIndex(0)


class PlotTab(QWidget):
    def __init__(self, nb_fig=3,
                 variables=['u', 'v', 'pg', 'amp', 'e', 'etc'],
                 parent=None):
        """
        Plotting tab

        Args:
            nb_fig: number of figures to display in the figure window
            variables: list of str, variable names available for display
            sonars: list of str, instrument names available for display
                         only available in "compare" mode
            parent: parent QWidget
        """
        super().__init__(parent)

        # Default values
        try:
            nb_fig = DISPLAY_FEAT.num_axes
        except NameError:
            pass

        # Attributes & features
        self.counterFigures = 0
        self.variables = variables
        if DISPLAY_FEAT.mode == 'compare':
            self.sonars = list(self.variables.keys())
            self.max_nb_panels = 12
            # FIXME - move 12 to plotting_parameters.py
        else:
            self.max_nb_panels = min(12, len(self.variables))
            # FIXME - move 12 to plotting_parameters.py
        self.layout = QHBoxLayout(self)
        self.setObjectName("PlotTab")
        self.tabContainer = self.parent()
        self.controlWindow = self.tabContainer.parent()

        # Widgets
        #  - manual edit panel
        if DISPLAY_FEAT.mode in ["edit", "compare"]:
            self.panelManualEdit = CustomFrame("panelManualEdit")
            self.buttonZapper = CustomPushButton("Selectors")
            self.checkboxShowZapperEdit = QCheckBox(
                "show staged selector edits")
            self.checkboxShowZapperEdit.setChecked(DISPLAY_FEAT.show_zapper)
            if DISPLAY_FEAT.mode == "edit":
                self.buttonBottom = CustomPushButton("Seabed selector")
                self.buttonThreshold = CustomPushButton("Threshold")
                self.checkboxShowBottomEdit = QCheckBox(
                    "show staged bottom edits ")
                self.checkboxShowBottomEdit.setChecked(DISPLAY_FEAT.show_bottom)
                self.checkboxShowThresholdEdit = QCheckBox(
                    "show staged threshold edits (x)")
                self.checkboxShowThresholdEdit.setChecked(
                    DISPLAY_FEAT.show_threshold)
        # - Panels panel
        self.panelPanels = CustomFrame("panelPanels")
        self.refreshPanelsButton = CustomPushButton("Refresh Panel(s)")
        self.spinboxNbFigures = CustomSpinbox(range=self.max_nb_panels, step=1,
                                              value=nb_fig,
                                              prefix='Nb. of fig.: ')
        #  - Toggles panel
        self.panelToggles = CustomFrame("panelToggles")
        self.panelMasking = CustomFrame("Masking")
        self.checkboxShowSpeed = QCheckBox("show speed")
        self.checkboxShowSpeed.setChecked(DISPLAY_FEAT.show_spd)
        self.checkboxShowHeading = QCheckBox("show heading")
        self.checkboxShowHeading.setChecked(DISPLAY_FEAT.show_heading)
        self.checkboxShowMCursor = QCheckBox("show multi-cursor")
        self.checkboxShowMCursor.setChecked(DISPLAY_FEAT.multicursor)
        self.checkboxXTicks = QCheckBox("x = UTC dates")
        self.checkboxXTicks.setChecked(DISPLAY_FEAT.utc_date)
        self.checkboxZBins = QCheckBox("z = bins")
        self.checkboxZBins.setChecked(DISPLAY_FEAT.use_bins)
        self.radiobuttonNoFlags = QRadioButton("no flags")
        self.radiobuttonLowPG = QRadioButton("low PG only")
        self.radiobuttonCodas = QRadioButton("codas")
        if DISPLAY_FEAT.mode in ["edit", "compare"]:
            self.checkboxSaturate = QCheckBox("saturate vel. plots")
            self.checkboxSaturate.setChecked(DISPLAY_FEAT.saturate)
            self.radiobuttonAll = QRadioButton("all")
        if DISPLAY_FEAT.mask == "no flags":
            self.radiobuttonNoFlags.setChecked(True)
        elif DISPLAY_FEAT.mask == "codas":
            self.radiobuttonCodas.setChecked(True)
        elif DISPLAY_FEAT.mask == "all":
            self.radiobuttonAll.setChecked(True)
        #  - Plotting panel
        self.panelPlotting = CustomFrame("panelPlotting")
        self.panelPlotting.panelVelRange = CustomFrame("panelVelRange")
        self.entryVelMin = CustomEntry(size=40, entry_type=float,
                                       value=DISPLAY_FEAT.vel_range[0],
                                       min_value=-99.99)
        self.entryVelMax = CustomEntry(size=40, entry_type=float,
                                       value=DISPLAY_FEAT.vel_range[1],
                                       min_value=-99.99)
        if DISPLAY_FEAT.mode == "compare":
            self.panelPlotting.panelDiffRange = CustomFrame("panelDiffRange")
            self.entryDiffMin = CustomEntry(
                size=40, entry_type=float,
                value=DISPLAY_FEAT.diff_range[0],
                min_value=-99.99)
            self.entryDiffMax = CustomEntry(
                size=40, entry_type=float,
                value=DISPLAY_FEAT.diff_range[1],
                min_value=-99.99)
        if DISPLAY_FEAT.mode in ["edit", "compare"]:
            self.panelPlotting.panelDepth = CustomFrame("panelDepth")
            self.depthRange = CustomCheckboxEntries(
                "Depth (m or bin)", DISPLAY_FEAT.user_depth_range,
                enabled=DISPLAY_FEAT.autoscale,
                parent=self.panelPlotting.panelDepth)
        if DISPLAY_FEAT.mode == "edit":
            # Panel for holding the pg cutoff
            self.panelPlotting.panelCutoff = CustomFrame("panelPGCutoff")
            # default this frame to disabled because it isn't selected at start
            self.panelPlotting.panelCutoff.setEnabled(False)
            self.entryPGCutoff = ClickableSlider(Qt.Horizontal)
            self.entryPGCutoff.setTickInterval(100)
            self.entryPGCutoff.setSingleStep(1)
            self.entryPGCutoffText = CustomEntry(value=self.entryPGCutoff.value(),
                                              size=50, min_value=0, max_value=99, entry_type=int)
            self.entryPGCSave = CustomPushButton("Save", self)
            self.checkboxPGCBehavior = QCheckBox("Apply to whole cruise")

        #  - Beam actions panel
        if DISPLAY_FEAT.mode == "single ping":
            self.panelBeamActions = CustomFrame("panelBeamActions")
            self.entryStartPing = CustomEntry(value=DISPLAY_FEAT.ping_start,
                                              size=70, entry_type=float)
            self.entryStepPing = CustomEntry(value=DISPLAY_FEAT.ping_step,
                                             size=50, entry_type=float)
            self.buttonPrevPing = CustomButton(
                icon_path=leftArrow,
                background_color=silverBackGroundColor)
            self.buttonNextPing = CustomButton(
                icon_path=rightArrow,
                background_color=silverBackGroundColor)
            self.buttonPlot = CustomPushButton("Plot Raw")
            self.pingInfoLabel = CustomLabel("Ping info", style='h3')
            self.pingInfoLabel.setWordWrap(True)

        # Layouts
        #  - manual edit layout
        if DISPLAY_FEAT.mode in ["edit", "compare"]:
            if DISPLAY_FEAT.mode == "edit":
                widgets = [CustomLabel("Manual Editing", style='h2'),
                           self.buttonZapper,
                           self.checkboxShowZapperEdit,
                           self.buttonBottom,
                           self.checkboxShowBottomEdit,
                           CustomLabel("Threshold Editing", style='h2'),
                           self.buttonThreshold,
                           self.checkboxShowThresholdEdit
                           ]
            else:
                widgets = [CustomLabel("Manual Editing", style='h2'),
                           self.buttonZapper,
                           self.checkboxShowZapperEdit,
                           ]
            if not (DISPLAY_FEAT.mode == 'compare'
                    and not DISPLAY_FEAT.write_permission):
                parent = self.panelManualEdit
                self.panelManualEdit.layout = CustomPanelVLayout(
                    widgets, parent)
        # - panels layout
        widgets = [CustomLabel("Panels", style='h2'),
                   self.refreshPanelsButton, self.spinboxNbFigures]
        if DISPLAY_FEAT.mode == "compare":
            widgets.append(CustomLabel("Sonar   :   Variable", style='h3'))
        #   N.B.: These are declare but invisible...for now
        for ii in range(self.max_nb_panels):
            if DISPLAY_FEAT.mode == "compare":
                sonar = self.sonars[0]
                # N.B.: did the above so the dropdown have the same sizes
                dropdown = CustomDropdownCompareMode(
                    self.variables[sonar], self.sonars, index=0)
                setattr(self, "button" + str(ii), dropdown)
                getattr(self, "button" + str(ii)).setObjectName(
                    "button" + str(ii))
            else:
                dropdown = CustomDropdown(self.variables, index=ii)
                setattr(self, "button" + str(ii), dropdown)
                getattr(self, "button" + str(ii)).setObjectName(
                    "button" + str(ii))
        parent = self.panelPanels
        self.panelPanels.layout = CustomPanelVLayout(widgets, parent)
        #  - toggles layout
        #    * Masking sub-frame
        widgets = [CustomLabel("Masking", style='h3'), self.radiobuttonNoFlags]
        if DISPLAY_FEAT.mode == "edit":
            widgets.append(self.radiobuttonLowPG)
        widgets.append(self.radiobuttonCodas)
        if DISPLAY_FEAT.mode == "edit":
            widgets.append(self.radiobuttonAll)
        parent = self.panelMasking
        self.panelMasking.layout = CustomPanelVLayout(widgets, parent)
        #
        widgets = [CustomLabel("Toggles", style='h2'),
                   self.checkboxShowSpeed, self.checkboxShowHeading,
                   self.checkboxShowMCursor, self.checkboxXTicks,
                   self.checkboxZBins]
        if DISPLAY_FEAT.mode in ["compare", "edit"]:
            widgets.append(self.checkboxSaturate)
            widgets.append(self.panelMasking)
        parent = self.panelToggles
        self.panelToggles.layout = CustomPanelVLayout(widgets, parent)
        #  - plotting layout
        #   * velocity sub-frame
        widgets = [CustomLabel("Velocity (m/s)", style='h3'),
                   QLabel("min"), self.entryVelMin,
                   QLabel("max"), self.entryVelMax]
        parent = self.panelPlotting.panelVelRange
        self.panelPlotting.panelVelRange.layout = CustomPanelGridLayout(
            widgets, parent)
        widgets = [CustomLabel("Plotting", style='h2'),
                   self.panelPlotting.panelVelRange,
                   ]
        #   * diff sub-frame
        if DISPLAY_FEAT.mode == "compare":
            widgets_diff = [CustomLabel("Velocity Diff. (m/s)", style="h3"),
                       QLabel("min"), self.entryDiffMin,
                       QLabel("max"), self.entryDiffMax]
            parent = self.panelPlotting.panelDiffRange
            self.panelPlotting.panelDiffRange.layout = CustomPanelGridLayout(
                widgets_diff, parent)
            widgets.append(self.panelPlotting.panelDiffRange)
        #   * depth sub-frame
        if DISPLAY_FEAT.mode in ["edit", "compare"]:
            widgets.append(self.panelPlotting.panelDepth)
        #   * percent good cutoff sub-frame
        if DISPLAY_FEAT.mode == "edit":
            parent = self.panelPlotting.panelCutoff
            parent.layout = QGridLayout(parent)

            # Container for save button and text entry
            PGCSubLayout = QHBoxLayout()
            PGCSubLayout.addWidget(self.entryPGCutoffText)
            PGCSubLayout.addWidget(self.entryPGCSave)

            # done manually so that I can add a nested layout
            parent.layout.addWidget(CustomLabel("Percent Good Cutoff", style="h3"))
            parent.layout.addLayout(PGCSubLayout, 1, 0)
            parent.layout.addWidget(self.entryPGCutoff)
            parent.layout.addWidget(self.checkboxPGCBehavior)

            widgets.append(self.panelPlotting.panelCutoff)

        self.panelPlotting.layout = CustomPanelVLayout(
            widgets, self.panelPlotting)
        #   - beam actions layout
        if DISPLAY_FEAT.mode == "single ping":
            widgets = [CustomLabel("Beam (Raw) Actions", style='h2'),
                       QLabel("Ping start: "), self.entryStartPing,
                       QLabel("Step (sec.):"), self.entryStepPing,
                       self.buttonPrevPing,
                       self.buttonPlot,
                       self.buttonNextPing,
                       self.pingInfoLabel]
            self.panelBeamActions.layout = QVBoxLayout()
            self.panelBeamActions.layout.addWidget(widgets[0])
            subGridLayout = QHBoxLayout()
            for w in widgets[1:5]:
                subGridLayout.addWidget(w)
            subGridLayout.setAlignment(Qt.AlignLeft)
            self.panelBeamActions.layout.addLayout(subGridLayout)
            subHLayout = QHBoxLayout()
            subHLayout.addWidget(widgets[5])
            subHLayout.addWidget(widgets[6])
            subHLayout.addWidget(widgets[7])
            self.panelBeamActions.layout.addLayout(subHLayout)
            self.panelBeamActions.layout.addWidget(widgets[-1])
            self.panelBeamActions.layout.addStretch()
            self.panelBeamActions.setLayout(self.panelBeamActions.layout)
        # - tab general layout
        if DISPLAY_FEAT.mode in ["edit", "compare"]:
            self.layout.addWidget(self.panelManualEdit)
        self.layout.addWidget(self.panelPanels)
        self.layout.addWidget(self.panelToggles)
        self.layout.addWidget(self.panelPlotting)
        if DISPLAY_FEAT.mode == "single ping":
            self.layout.addWidget(self.panelBeamActions)
        self.layout.addStretch(1)
        self.layout.setAlignment(Qt.AlignLeft)
        self.setLayout(self.layout)

        # Style
        self.setStyleSheet("#PlotTab {%s} " % silverBackGroundColor)
        self.refreshPanelsButton.setStyleSheet(backGroundKey + green)
        if DISPLAY_FEAT.mode in ["edit", "compare"]:
            self.buttonZapper.setStyleSheet(backGroundKey + blue)
            if DISPLAY_FEAT.mode == "edit":
                self.buttonBottom.setStyleSheet(backGroundKey + green)
                self.buttonThreshold.setStyleSheet(backGroundKey + red)
        if DISPLAY_FEAT.mode == "single ping":
            # FIXME - must be a better way to do this
            self.buttonNextPing.setFixedHeight(
                int(0.6 * self.buttonNextPing.sizeHint().height()))
            self.buttonPrevPing.setFixedHeight(
                int(0.6 * self.buttonPrevPing.sizeHint().height()))
            self.buttonPlot.setFixedHeight(
                int(0.5 * self.buttonNextPing.sizeHint().height()))
            self.buttonPlot.setStyleSheet(backGroundKey + blue)

        # Kick start actions
        #  - buttons
        for ii in range(nb_fig):
            self._add_figure()
        #  - ping info
        if DISPLAY_FEAT.mode == "single ping":
            self.set_info_ping()

        # Local Connection
        self.spinboxNbFigures.valueChanged.connect(self.on_change_value)
        if DISPLAY_FEAT.mode == "edit":
            self.buttonThreshold.clicked.connect(self.on_click_threshold)
        if DISPLAY_FEAT.mode == "compare":
            for ii in range(self.max_nb_panels):
                dropdown = getattr(self, "button" + str(ii))
                dropdown.sonars.currentIndexChanged.connect(
                    self._check_plot_compatibility)
                # Force compatibility check
                dropdown.sonars.currentIndexChanged.emit(ii)
                # Change chosen variables
                dropdown.variables.setCurrentIndex(ii)

        # Re-organise panels' dropdowns
        for ii in range(nb_fig):
            dropD = getattr(self, "button" + str(ii))
            if DISPLAY_FEAT.mode == 'compare':
                if DISPLAY_FEAT.sonars_indexes:
                    try:
                        dropD.sonars.setCurrentIndex(
                            DISPLAY_FEAT.sonars_indexes[ii])
                    except IndexError:
                        dropD.sonars.setCurrentIndex(ii % len(self.sonars))
                if DISPLAY_FEAT.axes_indexes:
                    try:
                        dropD.variables.setCurrentIndex(
                            DISPLAY_FEAT.axes_indexes[ii])
                    except IndexError:
                        dropD.variables.setCurrentIndex(ii)
            else:
                if DISPLAY_FEAT.axes_indexes:
                    try:
                        dropD.setCurrentIndex(DISPLAY_FEAT.axes_indexes[ii])
                    except IndexError:
                        dropD.setCurrentIndex(ii)

    # Methods/Local callbacks
    #  - Actions
    def _add_figure(self):
        if self.counterFigures < self.max_nb_panels:
            ii = self.counterFigures
            # remove stretch
            if self.panelPanels.layout.stretch is not None:
                self.panelPanels.layout.removeWidget(
                    self.panelPanels.layout.stretch)
            # add dropdown
            self.panelPanels.layout.addWidget(
                getattr(self, "button" + str(ii)))
            # add stretch
            self.panelPanels.layout.stretch =\
                self.panelPanels.layout.addStretch()
            # increment counter
            self.counterFigures += 1

    def _del_figure(self):
        if self.counterFigures > 1:
            ii = self.counterFigures
            # safely remove dropdown
            if DISPLAY_FEAT.mode == "compare":
                class_to_look_for = CustomDropdownCompareMode
            else:
                class_to_look_for = CustomDropdown
            widget = self.panelPanels.findChild(
                class_to_look_for, "button" + str(ii-1))
            self.panelPanels.layout.removeWidget(widget)
            widget.setParent(None)
            # increment counter
            self.counterFigures -= 1

    def _check_plot_compatibility(self):
        """
        Check compatibility between instrument and available plots
        (i.e. only few plots are available for diff.)
        """
        inst_dropD = self.sender()
        vars_dropD = inst_dropD.parent().variables
        sonar_name = str(inst_dropD.currentText())  # .lower() # Ticket 708
        items = self.variables[sonar_name]
        vars_dropD.clear()
        vars_dropD.addItems(items)

    # - slots
    def on_change_value(self):
        userChoice = self.spinboxNbFigures.value()
        if userChoice - self.counterFigures > 0:
            self._add_figure()
        else:
            self._del_figure()

    def on_click_threshold(self):
        """Bounce user in Thresholds Tab"""
        self.tabContainer.setCurrentIndex(1)

    # - methods
    def set_info_ping(self):
        self.pingInfoLabel.setText(pingInfoText())


class ThresholdsTab(CustomScrollTab):
    def __init__(self, parent=None):
        """
        Thresholds tab
        Args:
            parent: Plotting tab
        """
        super().__init__(parent)
        # Widgets
        # - reset button
        self.buttonResetThreshold = CustomPushButton("Reset Thresholds", self)
        #  - 18 checkbox/entry/label widgets # see thresholds_models.py (thresholds)
        self.checkboxEntryLabels = {}  # checkboxEntryLabel widget container
        self.names = THRESHOLDS.widget_features.edit_names
        self.background_colors = THRESHOLDS.widget_features.background_colors[:]
        self.has_checkboxes = THRESHOLDS.widget_features.has_checkbox
        self.enabled_thresholds = THRESHOLDS.widget_features.enabled_thresholds
        self.labels = THRESHOLDS.widget_features.labels[:]
        self._ini_thresholds_values()

        # - 5 Frames
        self.frameWire = CustomFrame("frameWire")
        self.frameBins = CustomFrame("frameBins")
        self.frameRefLayer = CustomFrame("frameRefLayer")
        self.frameBottom = CustomFrame("frameBottom")
        self.frameProfile = CustomFrame("frameProfile")

        # Layout
        #  - sub frame layout
        self._build_subframe(self.frameWire,
                             "Wire interference and ringing", 0, 4)
        self._build_subframe(self.frameBins,
                             "Thresholds for excluding individual bins", 4, 7)
        self._build_subframe(self.frameRefLayer,
                             "Percent Good in reference layer", 11, 4)
        self._build_subframe(self.frameBottom,
                             "Identify bottom", 15, 1)
        self._build_subframe(self.frameProfile,
                             "Thresholds for excluding whole profiles", 16, 4)
        #  - Tab general layout
        frames = [self.buttonResetThreshold, self.frameWire, self.frameBins,
                  self.frameRefLayer,  self.frameBottom, self.frameProfile]
        for frame in frames:
            self.layout.addWidget(frame)

        # Style
        self.buttonResetThreshold.setStyleSheet(backGroundKey + blue)

    # Methods
    def _build_subframe(self, subframe, title, start_index, nb_widget):
        subframe.layout = QVBoxLayout()
        subframe.layout.addWidget(CustomLabel(title, style='h3'))
        for name in self.names[start_index:start_index + nb_widget]:
            widget = self.checkboxEntryLabels[name]
            subframe.layout.addWidget(widget)
        subframe.setLayout(subframe.layout)

    def _ini_thresholds_values(self):
        for name, label, c, b in zip(self.names, self.labels, self.has_checkboxes,
                                 self.background_colors):
            if name not in self.enabled_thresholds:
                e = True
            else:
                e = False
            v = THRESHOLDS.default_values[name]
            checkboxEntryLabel = CustomCheckboxEntryLabel(label, c, v, e,
                                                          backGroundKey + b)
            self.checkboxEntryLabels[name] = checkboxEntryLabel


class PatchTab(QWidget):
    def __init__(self, parent=None):
        """
        Patch tab
        Args:
            parent: Plotting tab
        """
        super().__init__(parent)
        # Attributes & features
        self.layout = QHBoxLayout(self)

        # Widgets
        #  - Filtering panel
        self.panelFiltering = CustomFrame("panelFiltering")
        self.checkboxDeglitching = QCheckBox("""Use "cleaner"?""")
        self.checkboxDeglitching.setChecked(DISPLAY_FEAT.deglitch)
        self.entryCutoff = CustomEntry(
            size=50, entry_type=float, value=DISPLAY_FEAT.medcutoff)
        self.entryStdCutoff = CustomEntry(
            size=50, entry_type=float, value=DISPLAY_FEAT.stdcutoff)
        self.entryNbGoodCutoff = CustomEntry(
            size=50, entry_type=int, value=int(DISPLAY_FEAT.goodcutoff))
        self.spinboxHalfwidth = CustomSpinbox(
            range=100, step=1, value=DISPLAY_FEAT.medfilt_win)
        #  - Smoothing panel
        self.panelSmoothing = CustomFrame("panelSmoothing")
        self.checkboxBoxfilt = QCheckBox("""Run boxfilt?""")
        self.checkboxBoxfilt.setChecked(DISPLAY_FEAT.run_boxfilt)
        self.spinboxBoxfilt = CustomSpinbox(
            range=100, step=1, value=DISPLAY_FEAT.smboxwidth)
        # Layouts
        #  - Filtering layout
        self.panelFiltering.layout = QGridLayout(self.panelFiltering)
        self.panelFiltering.layout.setAlignment(Qt.AlignTop)
        row = 0
        self.panelFiltering.layout.addWidget(
            CustomLabel("Filtering", style='h2'), row, 0, 1, 2)
        row += 1
        self.panelFiltering.layout.addWidget(
            QLabel("Optional deglitching"), row, 0)
        self.panelFiltering.layout.addWidget(self.checkboxDeglitching, 1, 1)
        row += 1
        self.panelFiltering.layout.addWidget(CustomSeparator(), row, 0, 1, 3)
        row += 1
        self.panelFiltering.layout.addWidget(
            QLabel("Median filter halfwidth"), row, 0)
        self.panelFiltering.layout.addWidget(self.spinboxHalfwidth, row, 1)
        row += 1
        self.panelFiltering.layout.addWidget(
            QLabel("Median filter cut-off"), row, 0)
        self.panelFiltering.layout.addWidget(self.entryCutoff, row, 1)
        row += 1
        self.panelFiltering.layout.addWidget(CustomSeparator(), row, 0, 1, 3)
        row += 1
        self.panelFiltering.layout.addWidget(
            QLabel("Std. deviation cutoff"), row, 0)
        self.panelFiltering.layout.addWidget(self.entryStdCutoff, row, 1)
        row += 1
        self.panelFiltering.layout.addWidget(CustomSeparator(), row, 0, 1, 3)
        row += 1
        self.panelFiltering.layout.addWidget(
            QLabel("Nb. of good cutoff"), row, 0)
        self.panelFiltering.layout.addWidget(self.entryNbGoodCutoff, row, 1)

        self.panelFiltering.setLayout(self.panelFiltering.layout)
        #  - Smoothing layout
        widgets = [CustomLabel("Smoothing", style='h2'),
                   self.checkboxBoxfilt,
                   QLabel("Boxfilt halfwidth"),
                   self.spinboxBoxfilt]
        parent = self.panelSmoothing
        self.panelSmoothing.layout = CustomPanelVLayout(widgets, parent)
        #  - Tab layout
        self.layout.addWidget(self.panelFiltering)
        self.layout.addWidget(self.panelSmoothing)
        self.layout.addStretch(1)
        self.layout.setAlignment(Qt.AlignLeft)
        self.setLayout(self.layout)
        # Local connection
        self.checkboxBoxfilt.stateChanged.connect(self.on_tick_boxfilt)
        self.on_tick_boxfilt()

    # Local slots
    def on_tick_boxfilt(self):
        self.spinboxBoxfilt.setEnabled(self.checkboxBoxfilt.isChecked())


class LogTab(QTextEdit):
    def __init__(self, parent=None):
        """
        Displays and write to ascii log information on user's activity

        Args:
            parent: TabsContainer
        """
        super().__init__(parent)
        self.logFilePath = os.path.abspath(ASCII_LOG)
        self.setReadOnly(True)
        if os.path.exists(self.logFilePath):
            # file_watcher change text to tab whenever self.logFilePath changes
            self.file_watcher = QFileSystemWatcher()
            self.file_watcher.addPath(self.logFilePath)
            # Initial callback
            self._set_text()
            # Local connection
            self.file_watcher.fileChanged.connect(self._set_text)

    def _set_text(self):
        # Open file and set text in log tab
        with open(self.logFilePath, "rt") as file:
            self.setText(file.read())
        # scroll all the way down
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        self.repaint()


class HelpTab(QTextBrowser):
    def __init__(self, parent=None):
        """
        Displays help documentation

        Args:
            parent: TabsContainer
        """
        # TODO: use QWebView + QUrl or equivalent to display shpinx doc's index.html
        super().__init__(parent=parent)
        self.setReadOnly(True)

        self.setText('\n\n---Help pages under construction---\n')
        if DISPLAY_FEAT.mode == 'patch':
            link = 'https://currents.soest.hawaii.edu/docs/adcp_doc/codas_doc/patch_hcorr/index.html'
        else:
            link = 'https://currents.soest.hawaii.edu/docs/adcp_doc/codas_doc/index.html'
        self.append(
            "Meanwhile consult the on-line documentation " +
            '<a href="%s">here</a>' % link
        )
        # Add text about shortcuts (see reset and zapper pop up windows)
        self.append("\n\n---List of hot-keys for reset and zapper windows---")
        self.append("Selectors:")
        self.append("Rectangle (r)")
        self.append("Hori. span (h)")
        self.append("Verti. span (z)")
        self.append("One click (o)")
        self.append("Polygon (p)")
        self.append("Lasso (l)")
        self.append("\nVariables:")
        self.append("u ocean vel. (u)")
        self.append("v ocean vel. (v)")
        self.append("error velocity (e)")
        # Style
        # - odd work around to center text and deselect text...FIXME
        cursor = self.textCursor()
        self.selectAll()
        self.setAlignment(Qt.AlignCenter)
        self.setTextCursor(cursor)
        # - Highlight hyper links
        self.setOpenExternalLinks(True)


class ConsoleTab(ConsoleWidget):
    def __init__(self, parent=None):
        super().__init__(parent)


# Local lib
def pingInfoText():
    """
    Generates custom message for single ping mode
    """
    DISPLAY_FEAT = DisplayFeaturesSingleton()
    if DISPLAY_FEAT.ping_start:
        msg = "Ping start at %s decimal day - " % round(DISPLAY_FEAT.ping_start, 4)
        msg += utc_formatting(
            DISPLAY_FEAT.ping_start, yearbase=DISPLAY_FEAT.year_base) + " UTC"
        msg += " (see black solid vertical line)"
        return msg
    return ""


### Example code for debugging purposes ###
if __name__ == '__main__':
    from pycurrents.adcpgui_qt.model.thresholds_models import (
        Thresholds)
    from pycurrents.adcpgui_qt.model.display_features_models import (
        displayFeatures, displayFeaturesCompare, displayFeaturesEdit,
        displayFeaturesSinglePing, DisplayFeaturesSingleton)
    from pycurrents.adcpgui_qt.apps.patch_hcorr_app import PatchDefaultParams
    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        from pycurrents.get_test_data import get_test_data_path

        test_data_path = get_test_data_path()
        path = test_data_path + 'uhdas_data/proc/os75nb'
    else:
        path = input("Path to instrument folder")
    edit_path = os.path.join(path, 'edit/codas_editparams.txt')

    app = QApplication(sys.argv)
    app.setStyle(globalStyle)

    # Containers
    thresholds = Thresholds(edit_path)
    ascii_log = os.path.join(gettempdir(), 'test.asclog')
    # View
    display_feat = displayFeatures()
    display_feat.start_day = 100.0  # None  # TBD value
    display_feat.day_range = [100.0, 200.0]  # None  # TBD value
    display_feat.year_base = 2017  # None  # TBD value
    display_feat.time_range = [display_feat.start_day, display_feat.start_day
                               + display_feat.day_step]
    df = DisplayFeaturesSingleton(display_feat)
    controlWindowView = ControlWindow(ascii_log, mode='view', test=True)
    controlWindowView.show()

    # Edit
    display_feat_edit = displayFeaturesEdit()
    display_feat_edit.start_day = 100.0  # None  # TBD value
    display_feat_edit.day_range = [100.0, 200.0]  # None  # TBD value
    display_feat_edit.year_base = 2017  # None  # TBD value
    display_feat_edit.time_range = [
        display_feat.start_day, display_feat.start_day + display_feat.day_step]
    df = DisplayFeaturesSingleton(display_feat_edit)
    controlWindowEdit = ControlWindow(
        ascii_log, mode='edit', thresholds=thresholds, test=True)
    controlWindowEdit.show()

    # Patch
    patch_container = PatchDefaultParams(10.0, 50.0, 2014)
    df = DisplayFeaturesSingleton(patch_container)
    controlWindowPatch = ControlWindow(ascii_log, mode='patch', test=True)
    controlWindowPatch.show()

    # Single ping
    display_feat_single = displayFeaturesSinglePing()
    display_feat_single.start_day = 100.0  # None  # TBD value
    display_feat_single.day_range = [100.0, 200.0]  # None  # TBD value
    display_feat_single.year_base = 2017  # None  # TBD value
    display_feat_single.time_range = [display_feat.start_day,
                                      display_feat.start_day
                                      + display_feat.day_step]
    display_feat_single.start_ping = 100.0
    df = DisplayFeaturesSingleton(display_feat_single)
    controlWindowSinglePing = ControlWindow(
        ascii_log, mode='single ping', test=True)
    controlWindowSinglePing.show()

    # Compare
    display_feat_compare = displayFeaturesCompare(['os75bb', 'os75nb'])
    display_feat_compare.start_day = 100.0  # None  # TBD value
    display_feat_compare.day_range = [100.0, 200.0]  # None  # TBD value
    display_feat_compare.year_base = 2017  # None  # TBD value
    display_feat_compare.time_range = [
        display_feat.start_day, display_feat.start_day + display_feat.day_step]
    df = DisplayFeaturesSingleton(display_feat_compare)
    controlWindowCompare = ControlWindow(ascii_log, mode='compare', test=True)
    controlWindowCompare.show()

    sys.exit(app.exec_())
