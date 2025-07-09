#!/usr/bin/env python3

# FIXME: use pytest-qt and qtbot to really test the GUI/Qt related parts
#        see: http://pytest-qt.readthedocs.io/en/latest/intro.html
#        ex.:     window = MyApp()
#                 qtbot.addWidget(window)
#                 window.show()
#                 qtbot.waitForWindowShown(window)
#                 qtbot.mouseClick(window.buttonBox.buttons()[0], Qt.LeftButton)
# FIXME: use image comparison or pytest-mpl for the Matplotlib related parts
#        see: https://github.com/matplotlib/pytest-mpl?files=1
#        see: https://matplotlib.org/1.3.0/devel/testing.html

import os
import numpy as np
from tempfile import gettempdir
from pycurrents.adcpgui_qt.lib.qt_compat import QT_API
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt
from pytestqt import qtbot

from pycurrents.adcpgui_qt.view.topo_map_window import TopoMapWindow
from pycurrents.adcpgui_qt.view.color_plot_window import ColorPlotWindow
from pycurrents.adcpgui_qt.view.control_window import ControlWindow
from pycurrents.adcpgui_qt.view.zapper_plot_window import ZapperPlotWindow
from pycurrents.adcpgui_qt.view.reset_editing_plot_window import ResetPlotWindow
from pycurrents.adcpgui_qt.view.seabed_selector_plot_window import BottomPlotWindow
from pycurrents.adcpgui_qt.view.ping_plot_windows import PingPlotsWindows
from pycurrents.adcpgui_qt.lib.mpl_widgets import (
    TXYCursors, TopoMplCanvas, PlotMplCanvas)
from pycurrents.adcpgui_qt.model.display_features_models import (
    displayFeatures, displayFeaturesEdit, displayFeaturesCompare,
    displayFeaturesSinglePing, DisplayFeaturesSingleton)
from pycurrents.adcpgui_qt.model.ascii_files_models import (
    ASCIIandPathContainer, ASCIIandPathContainerCompareMode)
from pycurrents.adcpgui_qt.model.thresholds_models import (
    Thresholds, ThresholdsCompare)
from pycurrents.adcpgui_qt.model.codas_data_models import (
    CDataEdit, CData, CDataCompare)
from pycurrents.adcpgui_qt.presenter.intercommunication import (
    get_dbpath, initialize_display_feat, initialize_display_feat_compare_mode)
from pycurrents.adcpgui_qt.argument_parsers import dataviewer_option_parser
from pycurrents.adcpgui_qt.apps.patch_hcorr_app import PatchDefaultParams
from pycurrents.get_test_data import get_test_data_path  # BREADCRUMB: common library

assert qtbot


def test_color_plot_window(qtbot):
    test_data_path = get_test_data_path()
    path = test_data_path + '/codas_db/os38nb_py'
    arglist = ['--dbname', path]
    options = dataviewer_option_parser(arglist)
    dbpath = get_dbpath(path)
    CD = CData(dbpath, options)
    display_dict = displayFeatures()
    DisplayFeaturesSingleton(display_dict)
    thresholds = Thresholds()
    ascii_container = ASCIIandPathContainer('view', path)
    initialize_display_feat(thresholds, ascii_container, CD, options)
    colorPlotWindow = ColorPlotWindow(CD)
    # colorPlotWindow.show()
    qtbot.addWidget(colorPlotWindow)


def test_control_window(qtbot):
    test_data_path = get_test_data_path()
    path = test_data_path + '/uhdas_data/proc/os75nb'
    edit_path = os.path.join(path, 'edit/codas_editparams.txt')
    # Common Models
    thresholds = Thresholds(edit_path)
    ascii_log = os.path.join(gettempdir(), 'test.asclog')

    # View
    display_dict = displayFeatures()
    display_dict.start_day = 100.0  # None  # TBD value
    display_dict.day_range = [100.0, 200.0]  # None  # TBD value
    display_dict.year_base = 2017  # None  # TBD value
    display_dict.time_range = [display_dict.start_day, display_dict.start_day
                               + display_dict.day_step]
    DisplayFeaturesSingleton(display_dict)
    controlWindowView = ControlWindow(ascii_log, mode='view', test=True)
    # controlWindowView.show()
    qtbot.addWidget(controlWindowView)

    # Edit
    display_edit_dict = displayFeaturesEdit()
    display_edit_dict.start_day = 100.0  # None  # TBD value
    display_edit_dict.day_range = [100.0, 200.0]  # None  # TBD value
    display_edit_dict.year_base = 2017  # None  # TBD value
    display_edit_dict.time_range = [
        display_dict.start_day, display_dict.start_day + display_dict.day_step]
    DisplayFeaturesSingleton(display_edit_dict)
    controlWindowEdit = ControlWindow(ascii_log, mode='edit',
                                      thresholds=thresholds, test=True)
    # controlWindowEdit.show()
    qtbot.addWidget(controlWindowEdit)

    # Patch
    patch_container = PatchDefaultParams(10.0, 50.0, 2014)
    DisplayFeaturesSingleton(patch_container)
    controlWindowPatch = ControlWindow(ascii_log, mode='patch', test=True)
    # controlWindowPatch.show()
    qtbot.addWidget(controlWindowPatch)

    # Single ping
    display_single_ping_dict = displayFeaturesSinglePing()
    display_single_ping_dict.start_day = 100.0
    display_single_ping_dict.day_range = [100.0, 200.0]
    display_single_ping_dict.year_base = 2017
    display_single_ping_dict.time_range = [
        display_dict.start_day, display_dict.start_day + display_dict.day_step]
    controlWindowSinglePing = ControlWindow(
        ascii_log, mode='single ping', test=True)
    # controlWindowSinglePing.show()
    qtbot.addWidget(controlWindowSinglePing)

    # Compare
    display_compare_dict = displayFeaturesCompare(['os75bb', 'os75nb'])
    display_compare_dict.start_day = 100.0  # None  # TBD value
    display_compare_dict.day_range = [100.0, 200.0]  # None  # TBD value
    display_compare_dict.year_base = 2017  # None  # TBD value
    display_compare_dict.time_range = [
        display_dict.start_day, display_dict.start_day + display_dict.day_step]
    thresholds_compare = ThresholdsCompare([edit_path, edit_path],
                                           display_compare_dict.sonars)
    controlWindowCompare = ControlWindow(
        ascii_log, mode='compare',
        thresholds=thresholds_compare, test=True)
    # controlWindowCompare.show()
    qtbot.addWidget(controlWindowCompare)


def test_txy_cursors(qtbot):
    # test classes
    class TestTopoMplCanvas(TopoMplCanvas):
        def __init__(self, *args, **kwargs):
            TopoMplCanvas.__init__(self, *args, **kwargs)

        def test_plot(self, time_array):
            xmap = np.cos(3 * np.pi * time_array / 6)
            ymap = 30.0 * time_array
            self.topax.plot(xmap, ymap)
            return xmap, ymap

    class TestPlotMplCanvas(PlotMplCanvas):
        def __init__(self, ax_list, time_array, *args, **kwargs):
            PlotMplCanvas.__init__(self, ax_list, *args, **kwargs)
            self.test_plot(time_array)

        def test_plot(self, time_array):
            for axnum in range(self.numaxes):
                ax = self.axdict['pcolor'][axnum]
                cA = np.random.randint(20, 30)
                cB = np.random.randint(5, 10)
                yrand = cA + np.cos(3 * np.pi * time_array / cB)
                ax.plot(time_array, yrand)

    class TestWindow(QMainWindow):
        # Class counter
        winCounter = 0

        def __init__(self, test_pml_canvas, parent=None):
            QMainWindow.__init__(self, parent=parent)
            TestWindow.winCounter += 1
            self.setAttribute(Qt.WA_DeleteOnClose)
            self.setWindowTitle("Test window number: " +
                                str(TestWindow.winCounter))

            self.main_widget = QWidget(self)
            test_pml_canvas.setParent(self.main_widget)

            layout = QVBoxLayout(self.main_widget)
            layout.addWidget(test_pml_canvas)

            self.main_widget.setFocus()
            self.setCentralWidget(self.main_widget)

            self.statusBar().showMessage("All hail matplotlib!", 2000)

    # Fake time series data
    time_array = np.arange(0.0, 10.0, 300.0 / 86400)
    ax_list = ['a', 'b', 'c', 'd', 'e', 'f']

    # Kick start
    topoCanvas = TestTopoMplCanvas()
    xmap, ymap = topoCanvas.test_plot(time_array)
    plotCanvas1 = TestPlotMplCanvas(ax_list, time_array)
    plotCanvas2 = TestPlotMplCanvas(ax_list, time_array)
    plotCanvas3 = TestPlotMplCanvas(ax_list, time_array)

    axlist1 = []
    axlist2 = []
    axlist3 = []

    for ii in range(len(ax_list)):
        ax1 = plotCanvas1.axdict['pcolor'][ii]
        ax2 = plotCanvas2.axdict['pcolor'][ii]
        ax3 = plotCanvas3.axdict['pcolor'][ii]
        axlist1.append(ax1)
        axlist2.append(ax2)
        axlist3.append(ax3)
        canvasNaxes1 = [plotCanvas1, axlist1]
        canvasNaxes2 = [plotCanvas2, axlist2]
        canvasNaxes3 = [plotCanvas3, axlist3]

    canvasNaxes = [canvasNaxes1, canvasNaxes2, canvasNaxes3]

    topoWin = TestWindow(topoCanvas)
    plotWin1 = TestWindow(plotCanvas1, parent=topoWin)
    plotWin2 = TestWindow(plotCanvas2, parent=topoWin)
    plotWin3 = TestWindow(plotCanvas3, parent=topoWin)
    _ = TXYCursors(time_array, xmap, ymap, topoCanvas, canvasNaxes)
    qtbot.addWidget(topoWin)
    qtbot.addWidget(plotWin1)
    qtbot.addWidget(plotWin2)
    qtbot.addWidget(plotWin3)
    # qtbot.addWidget(txycursors)  # It's not a Widget.


def test_zapper_window(qtbot):
    test_data_path = get_test_data_path()
    path = test_data_path + '/uhdas_data/proc/os150nb'
    arglist = ['--dbname', path, '-e']
    options = dataviewer_option_parser(arglist)
    dbpath = get_dbpath(path)
    display_edit_dict = displayFeaturesEdit()
    DisplayFeaturesSingleton(display_edit_dict)
    ascii_container_edit = ASCIIandPathContainer('edit', path)
    thresholds_edit = Thresholds(path)
    CD_edit = CDataEdit(thresholds_edit, dbpath, options)
    initialize_display_feat(thresholds_edit, ascii_container_edit, CD_edit,
                            options)
    zapperPlotWindow_edit = ZapperPlotWindow(CD_edit, test=True)
    # zapperPlotWindow_edit.show()
    qtbot.addWidget(zapperPlotWindow_edit)
    #  N.B.: commented out since it can cause issue during remote install
    # zapperPlotWindow_edit.draw_color_plot(new_axis=True)
    # zapperPlotWindow_edit.canvas.draw()


def test_zapper_window_compare_mode(qtbot):
    test_data_path = get_test_data_path()
    path = test_data_path + '/uhdas_data/'
    proc_path = path + 'proc/'
    # Compare mode
    arglist = ['-c', proc_path + 'os75bb', proc_path + 'os150bb']
    options = dataviewer_option_parser(arglist)
    display_compare_dict = displayFeaturesCompare(['os75bb', 'os150bb'])
    DisplayFeaturesSingleton(display_compare_dict)
    ascii_container_compare = ASCIIandPathContainerCompareMode(
        [proc_path + 'os75bb', proc_path + 'os150bb'])
    thresholds_compare = ThresholdsCompare(
        ['os75bb', 'os150bb'], [proc_path + 'os75bb', proc_path + 'os150bb'])
    CD_compare = CDataCompare(['os75bb', 'os150bb'], thresholds_compare,
                              ascii_container_compare.db_paths,
                              options)
    initialize_display_feat_compare_mode(
        ['os75bb', 'os150bb'], thresholds_compare,
        ascii_container_compare, CD_compare, options)
    zapperPlotWindow_compare = ZapperPlotWindow(CD_compare, test=True)
    qtbot.addWidget(zapperPlotWindow_compare)
    # zapperPlotWindow_compare.show()
    #  N.B.: commented out since it can cause issue during remote install
    # zapperPlotWindow_compare.draw_color_plot(new_axis=True)
    # zapperPlotWindow_compare.canvas.draw()


def test_bottom_identification_window(qtbot):
    test_data_path = get_test_data_path()
    path = test_data_path + '/uhdas_data/proc/os150bb'
    arglist = ['--dbname', path, '-e']
    options = dataviewer_option_parser(arglist)
    dbpath = get_dbpath(path)
    display_dict = displayFeaturesEdit()
    DisplayFeaturesSingleton(display_dict)
    ascii_container = ASCIIandPathContainer('edit', path)
    thresholds = Thresholds(path)
    CD = CDataEdit(thresholds, dbpath, options)
    initialize_display_feat(thresholds, ascii_container, CD, options)
    PlotWindow = BottomPlotWindow(CD, test=True)
    qtbot.addWidget(PlotWindow)
    #  N.B.: commented out since it can cause issue during remote install
    # PlotWindow.draw_color_plot(new_axis=True)
    # PlotWindow.canvas.draw()


def test_reset_window(qtbot):
    test_data_path = get_test_data_path()
    path = test_data_path + '/uhdas_data/proc/os75nb'
    arglist = ['--dbname', path, '-e']
    options = dataviewer_option_parser(arglist)
    dbpath = get_dbpath(path)
    display_dict = displayFeaturesEdit()
    DisplayFeaturesSingleton(display_dict)
    ascii_container = ASCIIandPathContainer('edit', path)
    thresholds = Thresholds(path)
    CD = CDataEdit(thresholds, dbpath, options)
    initialize_display_feat(thresholds, ascii_container, CD, options)
    resetPlotWindow = ResetPlotWindow(CD, test=True)
    qtbot.addWidget(resetPlotWindow)
    #  N.B.: commented out since it can cause issue during remote install
    #resetPlotWindow.draw_color_plot(new_axis=True)
    #resetPlotWindow.canvas.draw()


def test_reset_window_compare_mode(qtbot):
    test_data_path = get_test_data_path()
    path = test_data_path + '/uhdas_data/'
    proc_path = path + 'proc/'
    # Compare mode
    arglist = ['-c', proc_path + 'os75nb', proc_path + 'os75bb']
    options = dataviewer_option_parser(arglist)
    display_compare_dict = displayFeaturesCompare(['os75nb', 'os75bb'])
    DisplayFeaturesSingleton(display_compare_dict)
    ascii_container_compare = ASCIIandPathContainerCompareMode(
        [proc_path + 'os75nb', proc_path + 'os75bb'])
    thresholds_compare = ThresholdsCompare(
        ['os75nb', 'os75bb'], [proc_path + 'os75nb', proc_path + 'os75bb'])
    CD_compare = CDataCompare(['os75nb', 'os75bb'], thresholds_compare,
                              ascii_container_compare.db_paths,
                              options)
    initialize_display_feat_compare_mode(
        ['os75nb', 'os75bb'], thresholds_compare,
        ascii_container_compare, CD_compare, options)
    resetPlotWindow_compare = ResetPlotWindow(CD_compare, test=True)
    qtbot.addWidget(resetPlotWindow_compare)
    #  N.B.: commented out since it can cause issue during remote install
    # resetPlotWindow_compare.draw_color_plot(new_axis=True)
    # resetPlotWindow_compare.canvas.draw()


def test_topo_map_window(qtbot):
    display_dict = displayFeatures()
    DisplayFeaturesSingleton(display_dict)
    CD = None
    topoMapWindow = TopoMapWindow(CD, test=True)
    qtbot.addWidget(topoMapWindow)
    #  N.B.: commented out since it can cause issue during remote install
    # topoMapWindow.random_topo_map_window_plot()
    # topoMapWindow.show()


def test_single_ping_plotting_window(qtbot):
    from pycurrents.get_test_data import get_test_data_path
    ppw = PingPlotsWindows(
        'os75nb',  # sonar
        cruisename='HLY18TA_03',  # cruise name
        configtype='python',
        working_dir=get_test_data_path() + '/uhdas_data/proc/os75nb')

    qtbot.addWidget(ppw.pingVelWin)
    qtbot.addWidget(ppw.pingProWin)
    qtbot.addWidget(ppw.pingFlagWin)
    qtbot.addWidget(ppw.beamVelWin)
    ppw.group_refresh(None, 120, False)

    # as of 2025-02-14 removing this causes pytests QApplication to hold stale references.
    # It appears that when the test is done, a signal is sent to a now deleted child which
    # generates the following error. `Internal C++ object (GenericPlotMplCanvas) already deleted`
    # Truly solving this proved very complicated, but it is sufficient to call shutdown
    # this stops the event loop and prevents the signal from triggering after the test
    if QT_API == 'PySide6':
        app = QApplication.instance()
        app.shutdown()
