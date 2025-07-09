import logging
import os
import sys
import numpy as np
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import (QRadioButton, QSpacerItem,
    QCheckBox, QPushButton, QWidget, QVBoxLayout, QSizePolicy, QHBoxLayout)
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import QSize
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QGuiApplication

from pycurrents.adcp.pingedit import mask_below  # BREADCRUMB: common library
from pycurrents.adcpgui_qt.lib.miscellaneous import reset_artist
from pycurrents.adcpgui_qt.lib.mpl_widgets import ZapperMplCanvas
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomDropdown, CustomFrame,
    CustomLabel, CustomPanelVLayout, backGroundKey, red, blue, waiting_cursor)
from pycurrents.adcpgui_qt.view.generic_plot_window import (
    GenericColorPlotWindow, CustomToolBarZapper)
from pycurrents.adcpgui_qt.lib.plotting_parameters import COLOR_PLOT_LIST
from pycurrents.adcpgui_qt.lib.zappers import ZapperMaker

# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

# Standard logging
_log = logging.getLogger(__name__)

DISPLAY_FEAT = DisplayFeaturesSingleton()

# FIXME: perhaps create a GenericPopUpWindow class for seabed_selector,
#        reset_editing and zappers windows


### Color Plot Window ###
class BottomPlotWindow(GenericColorPlotWindow):
    def __init__(self, CD, parent=None, test=False):
        """
        Seabed Selector plot window class/builder. Custom class inherited from
        GenericColorPlotWindow

        Args:
            CD: codas database, CData object (see ../model)
            parent: parent widget, QWidget. Here, one expects to have a control
                window as parent so callbacks can be made
            test: flag for test/debug purposes, bool
        """
        super().__init__(CD,parent=parent)
        # Global variables
        # Attributes
        self.zapper_name = 'bottom'
        self.artistBottomLine = None
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
        self.dropdownVar = CustomDropdown([COLOR_PLOT_LIST[2]])  # COLOR_PLOT_LIST)...only signal return
        self.radiobuttonMask = QRadioButton("Mask")
        self.radiobuttonUnmask = QRadioButton("Unmask")
        self.buttonStageEdits = QPushButton("Stage Edits", )
        self.buttonResetEdits = QPushButton("Clear Edits")
        # - custom tool bar
        widgets_to_hide = [self.radiobuttonMask, self.radiobuttonUnmask]
        self.toolbar = CustomToolBarZapper(self.canvas, widgets_to_hide, self)
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
        widgets = [
            CustomLabel("Variables", style='h3'), self.dropdownVar, spacer,
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
                title = 'Seabed Selector Window - Instrument(s): '
                title += DISPLAY_FEAT.sonar
            else:
                title = 'Seabed Selector Window'  # to here
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

        # Custom/Local connection & callbacks
        # - mouseMove: custom message in status bar
        self.canvas.mpl_connect('motion_notify_event', self.toolbar.mouse_move)
        # - variable changes
        self.dropdownVar.currentTextChanged.connect(
            self._panel_refresh)
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
    def get_zapper(self):
        """
        Set/change self.zapper attributes depending on the tool chosen by
        the user
        """
        # Deactivate zapper
        try:
            self.zapper.set_active(False)
        except AttributeError:  # for click zapper
            pass
        try:
            self.canvas.mpl_disconnect(self.zapper)
        except AttributeError:  # for click zapper
            pass
        # Define zapper
        self.zapperMaker = ZapperMaker(self.zapper_name, self._merge_mask,
                                  self.eax, self.canvas, self.CD)
        self.zapper = self.zapperMaker.get_zapper()
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
            ubb = func(evt)
            if type(ubb) in [np.ma.core.MaskedArray, np.ndarray]:
                # Side lode correction & mask
                # - define y coords of the bottom
                mask = self._get_mask_below_indexes(ubb)
                # - apply ubb's mask  to masks
                n = np.ma.getmask(ubb)
                for ii, jj in zip(range(ubb.shape[0]), n):
                    if jj:
                        mask[ii, :] = False
                # Mask or unmask
                if self.masking:
                    if not self.CD.bottomIndexes.shape:
                        self.CD.bottomIndexes = ubb
                    else:
                        self.CD.bottomIndexes.mask = np.logical_and(
                            self.CD.bottomIndexes.mask, ubb.mask)
                        for ii, flag in enumerate(ubb.mask):
                            if not flag:
                                self.CD.bottomIndexes[ii] = ubb[ii]
                    self.CD.bottomMask = self._get_mask_below_indexes(
                        self.CD.bottomIndexes)
                else:
                    self.CD.bottomMask[mask == 1] = 0
                    if self.CD.bottomIndexes.shape:
                        self.CD.bottomIndexes.mask = np.logical_not(
                            self.CD.bottomMask.sum(axis=1) != 0)
                        self.CD.bottomMask = np.logical_and(self.CD.bottomMask,
                                                            ~mask)
                # Draw bottom edits
                self.CP.draw_staged_edits(self.chosenVariables[0], self.eax,
                                          self.CD,
                                          show_bottom=True,
                                          draw_on_all_pcolor=True)
                # - clear previous artist
                if self.artistBottomLine:
                    for art in self.artistBottomLine:
                        art.remove()
                # - draw
                bottomDepths = self.CD.bottomIndexes.copy() * 0.0
                for ii, jj in zip(range(bottomDepths.shape[0]),
                                  self.CD.bottomIndexes):
                    if jj:
                        bottomDepths[ii] = self.CD.Yc[ii, jj]
                self.artistBottomLine = self.eax.plot(self.CD.Xc[:, 0],
                                                      bottomDepths,
                                                      'r.', markersize=5)
            self.canvas.draw()

    def _get_mask_below_indexes(self, ubb):
        yBottom = np.zeros(ubb.shape)
        for ii, jj in zip(range(ubb.shape[0]), ubb):
            if jj:
                yBottom[ii] = self.CD.Yc[ii, jj]
        mask = mask_below(self.CD.Yc, yBottom, self.CD.beamangle)
        # - apply ubb's mask  to masks
        n = np.ma.getmask(ubb)
        for ii, jj in zip(range(ubb.shape[0]), n):
            if jj:
                mask[ii, :] = False
        return mask

    def _reset_mask(self):
        self.artistBottomLine = reset_artist(self.artistBottomLine)
        if self.CD.bottomMask.size != 1:  # otherwise is crashes with empty mask
            self.CD.bottomMask[:] = 0
        self.CD.bottomIndexes = np.zeros((), dtype=bool)  # FIXME: different behavior than other masks...see seabed_selector_plot_window.py
        self.CP.draw_staged_edits(self.chosenVariables[0], self.eax, self.CD,
                                  show_bottom=True, draw_on_all_pcolor=True)
        self.canvas.draw()

    def _panel_refresh(self, options=None):
        self.draw_color_plot(draw_on_all_pcolor=True)
        self.canvas.draw()
        self.get_zapper()

    def _checkbox_refresh(self):
        self.checkboxShowSpeed.setChecked(DISPLAY_FEAT.show_spd)
        self.checkboxShowHeading.setChecked(DISPLAY_FEAT.show_heading)

    def _on_radio_button_clicked(self):
        if self.radiobuttonMask.isChecked():
            self.masking = True
        elif self.radiobuttonUnmask.isChecked():
            self.masking = False

    def _get_edit_ax(self):
        eax = self.axdict['edit'][-1]
        return eax

    # Override close function
    @waiting_cursor
    def closeEvent(self, ce):
        # Make control panel "clickable" again
        if self.parent():
            controlWindow = self.parent()
            controlWindow.setEnabled(True)
            # call back to draw masks on panels
            colorPlotWindow = controlWindow.children()[3]
            for axnum in range(DISPLAY_FEAT.num_axes):
                if colorPlotWindow.CD:
                    alias = colorPlotWindow.chosenVariables[axnum]
                    eax = colorPlotWindow.axdict['edit'][axnum]
                    colorPlotWindow.CP.draw_staged_edits(
                        alias, eax, colorPlotWindow.CD,
                        show_bottom=DISPLAY_FEAT.show_bottom,
                        show_threshold=DISPLAY_FEAT.show_threshold,
                        show_zapper=DISPLAY_FEAT.show_zapper)
            colorPlotWindow.canvas.draw()
        # reset bottom zapper artist
        if hasattr(self, 'zapperMaker'):
            reset_artist(self.zapperMaker.get_artist())
        # DO NOT CLOSE but make invisible
        self.setVisible(False)

    # Local slots
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

    # Override Dynamic attributes
    # N.B.: Local callbacks - to be defined for each instance of this class
    def _get_variables(self):
        return [self.dropdownVar.currentText()]

    def _get_num_axes(self):
        return 1

    chosenVariables = property(_get_variables)
    num_axes = property(_get_num_axes)

    # Dynamic attributes
    eax = property(_get_edit_ax)

### Example code for debugging purposes ###
if __name__ == '__main__':
    from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
    from pycurrents.adcpgui_qt.argument_parsers import dataviewer_option_parser
    from pycurrents.adcpgui_qt.lib.qtpy_widgets import globalStyle
    from pycurrents.adcpgui_qt.model.display_features_models import (
        displayFeaturesEdit, DisplayFeaturesSingleton)
    from pycurrents.adcpgui_qt.model.ascii_files_models import ASCIIandPathContainer
    from pycurrents.adcpgui_qt.model.thresholds_models import Thresholds
    from pycurrents.adcpgui_qt.model.codas_data_models import CDataEdit
    from pycurrents.adcpgui_qt.presenter.intercommunication import (
        get_dbpath, initialize_display_feat
    )

    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        from pycurrents.get_test_data import get_test_data_path

        test_data_path = get_test_data_path()
        path = test_data_path + '/uhdas_data/proc/os75nb'
    else:
        path = input("Path to instrument folder: ")
    arglist = ['--dbname', path, '-e']
    app = QApplication(sys.argv)
    app.setStyle(globalStyle)
    options = dataviewer_option_parser(arglist)
    dbpath = get_dbpath(path)
    display_feat_dict = displayFeaturesEdit()
    DisplayFeaturesSingleton(display_feat_dict)
    ascii_container = ASCIIandPathContainer('edit', path)
    thresholds = Thresholds(path)
    CD = CDataEdit(thresholds, dbpath, options)
    initialize_display_feat(thresholds, ascii_container, CD,
                            options)
    PlotWindow = BottomPlotWindow(CD, test=True)
    PlotWindow.show()
    PlotWindow.draw_color_plot(new_axis=True)
    PlotWindow.canvas.draw()
    sys.exit(app.exec_())
