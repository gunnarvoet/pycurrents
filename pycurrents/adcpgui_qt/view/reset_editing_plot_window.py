# FIXME: perhaps create a GenericPopUpWindow class for seabed_selector,
#        reset_editing and zappers windows
import os
import logging
import sys
import numpy as np
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import (QSpacerItem, QCheckBox,
    QPushButton, QWidget, QVBoxLayout, QSizePolicy, QHBoxLayout)
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import (QKeySequence,
    QGuiApplication, QShortcut)
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import QSize

from pycurrents.adcpgui_qt.lib.mpl_widgets import ZapperMplCanvas
from pycurrents.adcpgui_qt.view.generic_plot_window import (
    GenericColorPlotWindow, CustomToolBarPlot)
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomDropdown, CustomFrame,
    CustomLabel, CustomPanelVLayout, backGroundKey, blue, waitingNinactive_cursor)
from pycurrents.adcpgui_qt.lib.plotting_parameters import (
    COLOR_PLOT_LIST, EXCLUDE_PLOT_LIST, U_ALIAS, V_ALIAS, E_ALIAS, PG_ALIAS, AMP_ALIAS)
from pycurrents.adcpgui_qt.lib.zappers import ZapperMaker

# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

# Standard logging
_log = logging.getLogger(__name__)

DISPLAY_FEAT = DisplayFeaturesSingleton()


### Color Plot Window ###
class ResetPlotWindow(GenericColorPlotWindow):
    def __init__(self, CD, parent=None, test=False):
        """
        "Reset Editing"  plot window class/builder. Custom class inherited from
        GenericColorPlotWindow

        Args:
            CD: codas database, CData object (see ../model)
            parent: parent widget, QWidget. Here, one expects to have a control
                window as parent so callbacks can be made
            test: flag for test/debug purposes, bool
        """
        super().__init__(CD, parent=parent)
        # Attributes
        self.zapper_name = 'reset'
        self.resetMask = np.zeros((), dtype=bool)
        self.clear_edit_ranges = []
        # Widgets
        # - plot side
        self.canvas = ZapperMplCanvas(COLOR_PLOT_LIST[0])
        self.figure = self.canvas.figure
        self.axdict = self.canvas.axdict
        self.toolbar = CustomToolBarPlot(self.canvas, self)
        # - zappers
        self.masking = True  # True == masking; False == unmasking
        # - control side
        self.checkboxShowSpeed = QCheckBox("show speed")
        self.checkboxShowHeading = QCheckBox("show heading")
        self.buttonResetEdits = QPushButton(
            "Reset all edits over\nthe selected section(s)")
        if DISPLAY_FEAT.mode == 'compare':
            self._chosenSonar = DISPLAY_FEAT.sonar_choices[0]
            self.dropdownSonar = CustomDropdown(DISPLAY_FEAT.sonar_choices)
            self.dropdownVar = CustomDropdown(
                DISPLAY_FEAT.axes_choices[self._chosenSonar])
        else:
            self.dropdownVar = CustomDropdown(COLOR_PLOT_LIST)
        # Layouts
        # - containers
        self.hbox = QWidget(self)  # central widget container
        self.ppBox = QWidget(self)  # panel plot container
        self.zcBox = QWidget(self)  # zapper controllers
        # - panel plot layout
        self.ppBox.layout = QVBoxLayout()
        self.ppBox.layout.addWidget(self.canvas)
        self.ppBox.layout.addWidget(self.toolbar)
        self.ppBox.setLayout(self.ppBox.layout)
        #  * sub panel show speed & heading
        self.panelSpeedHeading = CustomFrame("speedHeading")
        widgets = [
            CustomLabel("Overlays", style='h3'), self.checkboxShowSpeed,
            self.checkboxShowHeading
        ]
        self.panelSpeedHeading.layout = CustomPanelVLayout(
            widgets, self.panelSpeedHeading
        )
        #  * spacer
        w = int(0.5 * self.dropdownVar.sizeHint().width())
        h = int(0.5 * self.dropdownVar.sizeHint().height())
        spacer = QSpacerItem(w, h, QSizePolicy.Minimum, QSizePolicy.Expanding)
        #  * sub layout
        if DISPLAY_FEAT.mode == 'compare':
            widgets = [CustomLabel("Sonars", style='h3'),
                       self.dropdownSonar]
        else:
            widgets = []
        widgets += [
            CustomLabel("Variables", style='h3'), self.dropdownVar, spacer,
            self.panelSpeedHeading, spacer,
            self.buttonResetEdits
        ]
        # - zapper controllers layout
        # FIXME: turn this into CustomVBoxLayout and move in qtpy_widgets
        self.zcBox.layout = QVBoxLayout()
        for widget in widgets:
            if widget == spacer:
                self.zcBox.layout.addItem(widget)
            else:
                self.zcBox.layout.addWidget(widget)
        self.zcBox.layout.addStretch()
        self.zcBox.setLayout(self.zcBox.layout)
        # - central widget layout
        self.hbox.layout = QHBoxLayout()
        self.hbox.layout.addWidget(self.zcBox)
        self.hbox.layout.addWidget(self.ppBox)
        self.hbox.setLayout(self.hbox.layout)
        self.setCentralWidget(self.hbox)
        # - shortcuts
        self._variable_shortcuts()

        # Style
        # - decorators
        self.buttonResetEdits.setStyleSheet(backGroundKey + blue)
        if DISPLAY_FEAT.plot_title:
            title = DISPLAY_FEAT.plot_title
        else:
            if DISPLAY_FEAT.sonar:
                title = 'Reset Editing Window - Instrument(s): '
                title += DISPLAY_FEAT.sonar
            else:
                title = 'Reset Editing Window'
        self.setWindowTitle(title)
        # - size
        sg = QGuiApplication.primaryScreen().geometry()
        defaultSize = QSize(int(0.8 * sg.width()), int(0.4 * sg.height()))
        self.resize(defaultSize)
        # - margins
        self.hbox.layout.setContentsMargins(0, 0, 0, 0)
        # - position
        widget = self.geometry()
        x = sg.width() - widget.width()
        y = 0
        self.move(x, y)

        # Kick start
        if not test:
            self.draw_color_plot(new_axis=True)
            self.get_zapper()
            if DISPLAY_FEAT.mode == 'compare':
                self._check_plot_compatibility()

        # Custom/Local connection & callbacks
        # - mouseMove: custom message in status bar
        self.canvas.mpl_connect('motion_notify_event', self.toolbar.mouse_move)
        # - sonar changes
        if DISPLAY_FEAT.mode == 'compare':
            self.dropdownSonar.currentIndexChanged.connect(
                self._check_plot_compatibility)
        # - variable changes
        self.dropdownVar.currentTextChanged.connect(
            self._panel_refresh)
        # - overlay buttons
        self._checkbox_refresh()
        if self.parent():
            self.checkboxShowSpeed.clicked.connect(
                self._on_local_show_speed)
            self.checkboxShowHeading.clicked.connect(
                self._on_local_show_heading)
        else:
            self.checkboxShowSpeed.clicked.connect(lambda: _log.debug(
                "Callback ERROR - parent control window must be provided"
            ))
            self.checkboxShowHeading.clicked.connect(lambda: _log.debug(
                "Callback ERROR - parent control window must be provided"
            ))

    # Methods
    def get_zapper(self):
        """
        Set/change self.zapper attributes depending on the tool chosen by
        the user
        """
        CD = self._get_local_CD()
        # Deactivate zapper
        try:
            self.zapper.set_active(False)
            self.canvas.mpl_disconnect(self.zapper)
        except AttributeError:  # zapper attr. not defined yet
            pass
        # Define zapper
        # Ticket 626
        # Sanity check - due to non-overlapping datasets in compare mode
        if CD.data is not None:
            zapperMaker = ZapperMaker(self.zapper_name, self._merge_mask,
                                      self.eax, self.canvas, CD)
            self.zapper = zapperMaker.get_zapper()
            # Activate zapper
            self.zapper.set_active(True)

    def _merge_mask(self, evt, func):
        """
        Decorator like function which merges and plots the staged edits

        Args:
            evt: mouse event
            func: python function object
        """
        if not self.toolbar.mode:  # avoid zapping while zooming or panning
            CD = self._get_local_CD()
            x_range, mask = func(evt[0], evt[1])
            self.resetMask = np.logical_or(self.resetMask, mask)
            self.clear_edit_ranges.append(x_range)
            self.CP.draw_staged_edits(
                self.chosenVariable, self.eax, CD,
                specific_mask=self.resetMask, draw_on_all_pcolor=True)
            self.canvas.draw()

    def _reset_edits(self):
        self.resetMask = np.zeros((), dtype=bool)
        self.clear_edit_ranges = []
        self._draw_selected_points()
        self.canvas.draw()

    def _panel_refresh(self, options=None):
        try:
            self.draw_color_plot(draw_on_all_pcolor=True)
            self._draw_selected_points()
            self.canvas.draw()
            self.get_zapper()
        except KeyError:  # due to race condition in local callbacks
            pass

    def _checkbox_refresh(self):
        self.checkboxShowSpeed.setChecked(DISPLAY_FEAT.show_spd)
        self.checkboxShowHeading.setChecked(DISPLAY_FEAT.show_heading)

    def _get_edit_ax(self):
        eax = self.axdict['edit'][-1]
        return eax

    def _draw_selected_points(self):
        CD = self._get_local_CD()
        if hasattr(self, 'CP'):  # Due to bug during testing phase
            self.CP.draw_staged_edits(self.chosenVariable, self.eax, CD,
                                      specific_mask=self.resetMask,
                                      draw_on_all_pcolor=True)

    def _get_local_CD(self):
        if DISPLAY_FEAT.mode == 'compare':
            CD = self.CD[self.chosenSonar]
        else:
            CD = self.CD
        return CD

    # Create actions and connect them buttons and keyboard shortcuts
    # FIXME: the next 2 methods are common to zapper and reset pop-up window...
    #        ...perhaps dev. common PopUpWindow class !?
    def _variable_shortcuts(self):
        """
        This method defines all the selector shortcuts/hot-keys that the user
        could make through the interface
        """
        self.uVelShortcut = QShortcut(QKeySequence("U"), self)
        self.uVelShortcut.activated.connect(
            lambda: self.variable_shortcut(U_ALIAS))
        self.vVelShortcut = QShortcut(QKeySequence("V"), self)
        self.vVelShortcut.activated.connect(
            lambda: self.variable_shortcut(V_ALIAS))
        self.errShortcut = QShortcut(QKeySequence("E"), self)
        self.errShortcut.activated.connect(
            lambda: self.variable_shortcut(E_ALIAS))
        self.pgShortcut = QShortcut(QKeySequence("G"), self)
        self.pgShortcut.activated.connect(
            lambda: self.variable_shortcut(PG_ALIAS))
        self.ampShortcut = QShortcut(QKeySequence("A"), self)
        self.ampShortcut.activated.connect(
            lambda: self.variable_shortcut(AMP_ALIAS))

    def variable_shortcut(self, variable_alias):
        """
        Change selector drop down via tool_index

        Args:
            variable_alias: variable alias, str, see plotting_parameters.py
        """
        for ii in range(self.dropdownVar.count()):
            if self.dropdownVar.itemText(ii) == variable_alias:
                self.dropdownVar.setCurrentIndex(ii)
                break

    # Override close function
    @waitingNinactive_cursor
    def closeEvent(self, ce):
        # Reset masks
        self._reset_edits()
        # Make control panel "clickable" again
        if self.parent():
            controlWindow = self.parent()
            controlWindow.setEnabled(True)
            colorPlotWindow = controlWindow.children()[3]  # FIXME - would be better with name rather than index
            if colorPlotWindow.CD:
                # refresh plot and re-extract data by proxy
                controlWindow.timeNavigationBar.buttonShow.click()
        # DO NOT CLOSE but make invisible
        self.setVisible(False)

    # Local slots & callbacks
    def _check_plot_compatibility(self):
        """
        Check compatibility between instrument and available plots
        (i.e. only few plots are available for diff.)
        """
        inst_dropD = self.dropdownSonar
        vars_dropD = self.dropdownVar
        sonar_name = str(inst_dropD.currentText())  # .lower() - see Ticket 708
        items = []
        for item in DISPLAY_FEAT.axes_choices[sonar_name]:
            if item not in EXCLUDE_PLOT_LIST:
                items.append(item)
        vars_dropD.clear()
        vars_dropD.addItems(items)

    def _on_local_show_speed(self):
        controlWin = self.parent()
        tickBox = controlWin.tabsContainer.plotTab.checkboxShowSpeed
        controlWin.setEnabled(True)
        tickBox.click()
        controlWin.setEnabled(False)
        for child in controlWin.children():
            child.setEnabled(True)
        self.draw_over_layer()
        self.canvas.draw()
        self.get_zapper()

    def _on_local_show_heading(self):
        controlWin = self.parent()
        tickBox = controlWin.tabsContainer.plotTab.checkboxShowHeading
        controlWin.setEnabled(True)
        tickBox.click()
        controlWin.setEnabled(False)
        for child in controlWin.children():
            child.setEnabled(True)
        self.draw_over_layer()
        self.canvas.draw()
        self.get_zapper()

    def _get_variable(self):
        return self.dropdownVar.currentText()

    def _get_sonar(self):
        requested_sonar = self.dropdownSonar.currentText()
        # If change sonar, previously selected points are lost
        if requested_sonar != self._chosenSonar:
            self.resetMask = np.zeros((), dtype=bool)
            self._chosenSonar = requested_sonar
        return requested_sonar

    # Override Dynamic attributes
    # N.B.: Local callbacks - to be defined for each instance of this class
    def _get_variables(self):
        return [self._get_variable()]  # N.B.: has to be a list for consistancy

    def _get_num_axes(self):
        return 1

    def _get_sonars(self):
        return [self._get_sonar()]

    # Dynamic attributes
    eax = property(_get_edit_ax)
    chosenVariable = property(_get_variable)
    chosenSonar = property(_get_sonar)
    # N.B.: It is primordial to keep the same variable names as they override
    #       inherited ones
    chosenVariables = property(_get_variables)
    chosenSonars = property(_get_sonars)
    num_axes = property(_get_num_axes)


### Example code for debugging purposes ###
if __name__ == '__main__':
    from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
    from pycurrents.adcpgui_qt.argument_parsers import dataviewer_option_parser
    from pycurrents.adcpgui_qt.lib.qtpy_widgets import globalStyle
    from pycurrents.adcpgui_qt.model.display_features_models import (
        # displayFeaturesEdit,
        displayFeaturesCompare,
        # displayFeatures,
        DisplayFeaturesSingleton)
    from pycurrents.adcpgui_qt.model.ascii_files_models import (
        # ASCIIandPathContainer,
        ASCIIandPathContainerCompareMode)
    from pycurrents.adcpgui_qt.model.thresholds_models import (
        # Thresholds,
        ThresholdsCompare)
    from pycurrents.adcpgui_qt.model.codas_data_models import (
        # CDataEdit,
        CDataCompare)
    from pycurrents.adcpgui_qt.presenter.intercommunication import (
        # get_dbpath, initialize_display_feat,
        initialize_display_feat_compare_mode)

    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        from pycurrents.get_test_data import get_test_data_path

        test_data_path = get_test_data_path()
        path = test_data_path + '/uhdas_data/'
    else:
        path = input("Path to instrument folder: ")

    app = QApplication(sys.argv)
    app.setStyle(globalStyle)

    edit_path = path + 'proc/os75nb/edit'
    proc_path = path + 'proc/'

    # Edit mode
    # arglist = ['--dbname', edit_path, '-e']
    # options = dataviewer_option_parser(arglist)
    # dbpath = get_dbpath(edit_path)
    # display_feat = DisplayFeaturesSingleton(displayFeaturesEdit())
    # ascii_container = ASCIIandPathContainer('edit', edit_path)
    # thresholds = Thresholds(edit_path)
    # CD = CDataEdit(thresholds, dbpath, options)
    # initialize_display_feat(thresholds, ascii_container, CD, options)
    # resetPlotWindow = ResetPlotWindow(CD, test=True)
    # resetPlotWindow.show()
    # resetPlotWindow.draw_color_plot(new_axis=True)
    # resetPlotWindow.canvas.draw()

    # Compare mode
    arglist = ['-c', proc_path + 'os75nb', proc_path + 'os75bb']
    options = dataviewer_option_parser(arglist)
    display_feat_compare = DisplayFeaturesSingleton(
        displayFeaturesCompare(['os75nb', 'os75bb']))
    ascii_container_compare = ASCIIandPathContainerCompareMode(
        [proc_path + 'os75nb', proc_path + 'os75bb'])
    thresholds_compare = ThresholdsCompare(
        ['os75nb', 'os75bb'], [proc_path + 'os75nb', proc_path + 'os75bb'])
    CD_compare = CDataCompare(['os75nb', 'os75bb'], thresholds_compare,
                              ascii_container_compare.db_paths,
                              options)
    initialize_display_feat_compare_mode(
        ['os75nb', 'os75bb'], thresholds_compare, ascii_container_compare,
        CD_compare, options)
    resetPlotWindow_compare = ResetPlotWindow(CD_compare, test=True)
    resetPlotWindow_compare.show()
    resetPlotWindow_compare.draw_color_plot(new_axis=True)
    resetPlotWindow_compare.canvas.draw()

    sys.exit(app.exec_())
