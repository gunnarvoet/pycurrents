import sys
import os
import numpy as np
import logging
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import (QRadioButton,
    QSpacerItem, QCheckBox, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy)
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import (QKeySequence,
    QGuiApplication, QShortcut, QStandardItem, QStandardItemModel)
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import QSize, Qt

from pycurrents.adcpgui_qt.lib.mpl_widgets import ZapperMplCanvas
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomDropdown, QPushButton,
    CustomFrame, CustomLabel, CustomPanelVLayout, waiting_cursor,
    backGroundKey, red, blue)
from pycurrents.adcpgui_qt.view.generic_plot_window import (
    GenericColorPlotWindow, CustomToolBarZapper)
from pycurrents.adcpgui_qt.lib.plotting_parameters import (
    COLOR_PLOT_LIST, EXCLUDE_PLOT_LIST, U_ALIAS, V_ALIAS, E_ALIAS, AMP_ALIAS, PG_ALIAS)
from pycurrents.adcpgui_qt.lib.zappers import ZapperMaker, TOOL_NAMES

# FIXME: perhaps create a GenericPopUpWindow class for seabed_selector,
#        reset_editing and zappers windows

# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

# Standard logging
_log = logging.getLogger(__name__)

DISPLAY_FEAT = DisplayFeaturesSingleton()

### Color Plot Window ###
class ZapperPlotWindow(GenericColorPlotWindow):
    def __init__(self, CD, parent=None, test=False):
        """
        Zapper plot window class/builder. Custom class inherited from
        GenericColorPlotWindow

        Args:
            CD: codas database, CData object (see ../model)
            parent: parent widget, QWidget. Here, one expects to have a control
                window as parent so callbacks can be made
            test: flag for test/debug purposes, bool
        """
        super().__init__(CD, parent=parent)
        # Attributes
        self.tools = DISPLAY_FEAT.tools
        self.zapper = None
        self.test = test
        # Widgets
        # - plot side
        self.canvas = ZapperMplCanvas(COLOR_PLOT_LIST[0])
        self.figure = self.canvas.figure
        self.axdict = self.canvas.axdict
        self.toolInfo = self.figure.text(0.99, 0.99, 'Tool Info',
                                         horizontalalignment='right',
                                         verticalalignment='top',
                                         color='r', fontweight='bold')
        # - zappers
        self.masking = True  # True == masking; False == unmasking
        # - control side
        self.checkboxShowSpeed = QCheckBox("show speed")
        self.checkboxShowHeading = QCheckBox("show heading")
        self.dropdownTool = CustomDropdown(self.tools)
        # Add information about keyboard shortcuts to variable dropdown
        var_shortcuts = {
            U_ALIAS: "U",
            V_ALIAS: "V",
            E_ALIAS: "E",
            PG_ALIAS: "G",
            AMP_ALIAS: "A",
        }
        var_names = [
            v if v not in var_shortcuts.keys() else f"{v} ({var_shortcuts[v]})"
            for v in COLOR_PLOT_LIST
        ]
        model = QStandardItemModel()
        for i, (name, data) in enumerate(zip(var_names, COLOR_PLOT_LIST)):
            item = QStandardItem()
            item.setText(name)
            item.setData(data, Qt.UserRole)
            model.setItem(i, item)
        self.dropdownVar = CustomDropdown([])
        self.dropdownVar.setModel(model)
        self.radiobuttonMask = QRadioButton("Mask")
        self.radiobuttonUnmask = QRadioButton("Unmask")
        self.buttonStageEdits = QPushButton("Stage Edits")
        self.buttonResetEdits = QPushButton("Clear Edits")
        if DISPLAY_FEAT.mode == 'compare':
            self.dropdownSonar = CustomDropdown(DISPLAY_FEAT.sonar_choices)
        # - custom tool bar
        widgets_to_hide = [self.dropdownTool, self.radiobuttonMask,
                           self.radiobuttonUnmask]
        self.toolbar = CustomToolBarZapper(self.canvas, widgets_to_hide, self)
        # - shortcuts
        self._selector_shortcuts()
        self._variable_shortcuts()
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
        #  * sub panel Mask/Unmask
        self.panelMaskUnmask = CustomFrame("maskUnmask")
        widgets = [
            CustomLabel("Mode toggle", style='h3'), self.radiobuttonMask,
            self.radiobuttonUnmask, self.buttonResetEdits
        ]
        self.panelMaskUnmask.layout = CustomPanelVLayout(widgets,
                                                         self.panelMaskUnmask)
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
            CustomLabel("Select by", style='h3'), self.dropdownTool, spacer,
            self.panelSpeedHeading, spacer,
            self.panelMaskUnmask, spacer,
            self.buttonStageEdits
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

        # Style
        # - decorators
        self.buttonStageEdits.setStyleSheet(backGroundKey + red)
        self.buttonResetEdits.setStyleSheet(backGroundKey + blue)
        if DISPLAY_FEAT.plot_title:
            title = DISPLAY_FEAT.plot_title
        else:
            if DISPLAY_FEAT.sonar:
                title = 'Selector Window - Instrument(s): '
                title += DISPLAY_FEAT.sonar
            else:
                title = 'Selector Window'
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
            self.set_zapper()
            if DISPLAY_FEAT.mode == 'compare':
                self._check_plot_compatibility()
        # Custom/Local connection & callbacks
        # - mouseMove: custom message in status bar
        self.canvas.mpl_connect('motion_notify_event', self.toolbar.mouse_move)
        # - sonar changes
        if DISPLAY_FEAT.mode == 'compare':
            self.dropdownSonar.currentTextChanged.connect(
                self._check_plot_compatibility)
        # - variable changes
        self.dropdownVar.currentTextChanged.connect(
            self._panel_refresh)
        # - tool changes
        self.dropdownTool.currentTextChanged.connect(
            self.set_zapper)
        # - radio button
        self.radiobuttonMask.setChecked(True)
        self.radiobuttonMask.clicked.connect(self._on_radio_button_clicked)
        self.radiobuttonUnmask.clicked.connect(self._on_radio_button_clicked)
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
        # - edits buttons
        self.buttonStageEdits.clicked.connect(self.close)
        self.buttonResetEdits.clicked.connect(self._reset_mask)

    # Methods
    def set_zapper(self):
        """
        Set/change self.zapper attributes depending on the tool chosen by
        the user
        """
        CD = self._get_local_CD()
        # Deactivate zapper
        try:
            self.zapper.set_active(False)
        except AttributeError:  # for click zapper
            pass
        try:
            self.zapper.disconnect_events()
            self.zapper.clear()
        except AttributeError:  # for click zapper
            pass
        # Define zapper
        zapper_name = self.dropdownTool.currentText()
        zapperMaker = ZapperMaker(zapper_name, self._merge_mask,
                                  self.eax, self.canvas, CD)
        self.zapper = zapperMaker.get_zapper()
        # Activate zapper
        try:
            self.zapper.set_active(True)
        except AttributeError:  # for click zapper
            pass
        # Update tool info
        self.toolbar.draw_tool_info()

    def _merge_mask(self, evt, func):
        """
        Decorator like function which merges and plots the staged edits

        Args:
            evt: mouse event
            func: python function object
        """
        if not self.toolbar.mode:  # avoid zapping while zooming or panning
            CD = self._get_local_CD()
            # Fix for Ticket 626 (non-overlapping datasets)
            # Sanity check
            if not CD.data:
                return
            # Wrapping zapping functions
            if isinstance(evt, tuple):
                mask = func(evt[0], evt[1])
            else:
                mask = func(evt)
            if not self.test:
                # substract existing codas mask
                # FIXME: perhaps move this somewhere more central like codas_data_models.py
                mask[CD.codasMask] = False
                if self.masking:
                    CD.zapperMask = np.logical_or(CD.zapperMask, mask)
                else:
                    if CD.zapperMask.ndim != 0:  # Is there anything to unmask?
                        CD.zapperMask[mask == 1] = 0
                self.CP.draw_staged_edits(
                    self.chosenVariable, self.eax, CD,
                    show_zapper=True,
                    show_threshold=DISPLAY_FEAT.show_threshold,
                    draw_on_all_pcolor=True)
            else:
                self.CP.draw_staged_edits(
                    self.chosenVariable, self.eax, CD,
                    show_zapper=True,
                    show_threshold=DISPLAY_FEAT.show_threshold,
                    draw_on_all_pcolor=True,
                    specific_mask=mask)
            self.canvas.draw()

    def _draw_selected_points(self):
        CD = self._get_local_CD()
        # substract existing codas mask
        # FIXME: perhaps move this somewhere more central like codas_data_models.py
        self.CP.draw_staged_edits(
            self.chosenVariable, self.eax, CD,
            show_zapper=True,
            show_threshold=DISPLAY_FEAT.show_threshold,
            draw_on_all_pcolor=True)

    def _reset_mask(self):
        CD = self._get_local_CD()
        if CD.zapperMask.size != 1:  # otherwise is crashes with empty mask
            CD.zapperMask[:] = 0
        self.CP.draw_staged_edits(self.chosenVariable, self.eax, CD,
                                  show_zapper=True,
                                  show_threshold=DISPLAY_FEAT.show_threshold,
                                  draw_on_all_pcolor=True)
        self.canvas.draw()

    def _panel_refresh(self, options=None):
        try:
            self.draw_color_plot(draw_on_all_pcolor=True)
            self._draw_selected_points()
            self.canvas.draw()
            self.set_zapper()

        except KeyError:  # due to race condition in local callbacks
            pass

    def _checkbox_refresh(self):
        self.checkboxShowSpeed.setChecked(DISPLAY_FEAT.show_spd)
        self.checkboxShowHeading.setChecked(DISPLAY_FEAT.show_heading)

    def _get_local_CD(self):
        if DISPLAY_FEAT.mode == 'compare':
            CD = self.CD[self.chosenSonar]
        else:
            CD = self.CD
        return CD

    # Override close function
    @waiting_cursor
    def closeEvent(self, ce):
        # Make control panel "clickable" again
        if self.parent():
            controlWindow = self.parent()
            controlWindow.setEnabled(True)
            # call back to draw masks on panels
            colorPlotWindow = controlWindow.children()[3]  # FIXME - would be better with name rather than index
            for axnum in range(DISPLAY_FEAT.num_axes):
                if DISPLAY_FEAT.mode == 'compare':
                    CD = self.CD[DISPLAY_FEAT.sonars[axnum]]
                else:
                    CD = self.CD
                if CD:
                    alias = colorPlotWindow.chosenVariables[axnum]
                    eax = colorPlotWindow.axdict['edit'][axnum]
                    colorPlotWindow.CP.draw_staged_edits(
                        alias, eax, CD,
                        show_bottom=DISPLAY_FEAT.show_bottom,
                        show_threshold=DISPLAY_FEAT.show_threshold,
                        show_zapper=DISPLAY_FEAT.show_zapper)
            colorPlotWindow.canvas.draw()
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
        sonar_name = str(inst_dropD.currentText())  # .lower() # Ticket 708
        items = []
        for item in DISPLAY_FEAT.axes_choices[sonar_name]:
            if item not in EXCLUDE_PLOT_LIST:
                items.append(item)
        vars_dropD.clear()
        vars_dropD.addItems(items)

    def _on_radio_button_clicked(self):
        if self.radiobuttonMask.isChecked():
            self.masking = True
        elif self.radiobuttonUnmask.isChecked():
            self.masking = False

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
        self.set_zapper()

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
        self.set_zapper()

    def _get_tool(self):
        return self.dropdownTool.currentText()

    def _get_variable(self):
        # For editing the alias is in data so that text can include shortcuts
        data = self.dropdownVar.currentData(Qt.UserRole)
        if data is None:
            return self.dropdownVar.currentText()
        return data

    def _get_sonar(self):
        return self.dropdownSonar.currentText()

    # Create actions and connect them buttons and keyboard shortcuts
    def _selector_shortcuts(self):
        """
        This method defines all the selector shortcuts/hot-keys that the user
        could make through the interface
        """
        # Changing tool
        # 0: Rectangle
        # 1: Horizontal span
        # 2: Vertical span
        # 3: One click
        # 4: Polygon
        # 5: Lasso
        self.rectangleShortcut = QShortcut(QKeySequence("R"), self)
        self.rectangleShortcut.activated.connect(
            lambda: self.tool_shortcut(0))
        self.horiSpanShortcut = QShortcut(QKeySequence("H"), self)
        self.horiSpanShortcut.activated.connect(
            lambda: self.tool_shortcut(1))
        self.vertiSpanShortcut = QShortcut(QKeySequence("Z"), self)
        self.vertiSpanShortcut.activated.connect(
            lambda: self.tool_shortcut(2))
        self.clickShortcut = QShortcut(QKeySequence("O"), self)
        self.clickShortcut.activated.connect(
            lambda: self.tool_shortcut(3))
        self.polyShortcut = QShortcut(QKeySequence("P"), self)
        self.polyShortcut.activated.connect(
            lambda: self.tool_shortcut(4))
        self.lassoShortcut = QShortcut(QKeySequence("L"), self)
        self.lassoShortcut.activated.connect(
            lambda: self.tool_shortcut(5))

    def tool_shortcut(self, tool_index):
        """
        Change selector drop down via tool_index

        Args:
            tool_index: tool index, int., see TOOL_NAMES list
        """
        for ii in range(self.dropdownTool.count()):
            if self.dropdownTool.itemText(ii) == TOOL_NAMES[tool_index]:
                self.dropdownTool.setCurrentIndex(ii)
                break
        self.set_zapper()

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
            if self.dropdownVar.itemData(ii) == variable_alias:
                self.dropdownVar.setCurrentIndex(ii)
                break

    # Override Dynamic attributes
    # N.B.: Local callbacks - to be defined for each instance of this class)
    def _get_variables(self):
        return [self._get_variable()]  # N.B.: has to be a list for consistancy

    def _get_num_axes(self):
        return 1

    def _get_edit_ax(self):
        eax = self.axdict['edit'][-1]
        return eax

    def _get_sonars(self):
        return [self._get_sonar()]

    # Dynamic attribute declaration
    chosenTool = property(_get_tool)
    chosenVariable = property(_get_variable)
    chosenSonar = property(_get_sonar)
    # N.B.: It is primordial to keep the same variable names as they override
    #       inherited ones
    chosenSonars = property(_get_sonars)
    chosenVariables = property(_get_variables)
    num_axes = property(_get_num_axes)
    eax = property(_get_edit_ax)


### Example code for debugging purposes ###
if __name__ == '__main__':
    from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
    from pycurrents.adcpgui_qt.argument_parsers import dataviewer_option_parser
    from pycurrents.adcpgui_qt.lib.qtpy_widgets import globalStyle
    from pycurrents.adcpgui_qt.model.display_features_models import (
        # displayFeaturesEdit,
        displayFeaturesCompare, DisplayFeaturesSingleton)
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
        # initialize_display_feat, get_dbpath,
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
    # display_dict = displayFeaturesEdit()
    # display_feat = DisplayFeaturesSingleton(display_dict)
    # ascii_container = ASCIIandPathContainer('edit', edit_path)
    # thresholds = Thresholds(path)
    # CD = CDataEdit(thresholds, dbpath, options)
    # initialize_display_feat(thresholds, ascii_container, CD,
    #                         options)
    # zapperPlotWindow = ZapperPlotWindow(CD, test=True)
    # zapperPlotWindow.show()
    # zapperPlotWindow.draw_color_plot(new_axis=True)
    # zapperPlotWindow.canvas.draw()

    # Compare mode
    arglist = ['-c', proc_path + 'os75nb', proc_path + 'os75bb']
    options = dataviewer_option_parser(arglist)
    display_dict_compare = displayFeaturesCompare(['os75nb', 'os75bb'])
    display_feat_compare = DisplayFeaturesSingleton(display_dict_compare)
    ascii_container_compare = ASCIIandPathContainerCompareMode(
        [proc_path + 'os75nb', proc_path + 'os75bb'])
    thresholds_compare = ThresholdsCompare(
        ['os75nb', 'os75bb'], [proc_path + 'os75nb', proc_path + 'os75bb'])
    CD_compare = CDataCompare(['os75nb', 'os75bb'], thresholds_compare,
                              ascii_container_compare.db_paths,
                              options)
    initialize_display_feat_compare_mode(
        ['os75nb', 'os75bb'], thresholds_compare,  ascii_container_compare,
        CD_compare, options)
    zapperPlotWindow_compare = ZapperPlotWindow(CD_compare, test=True)
    zapperPlotWindow_compare.show()
    zapperPlotWindow_compare.draw_color_plot(new_axis=True)
    zapperPlotWindow_compare.canvas.draw()

    sys.exit(app.exec_())
