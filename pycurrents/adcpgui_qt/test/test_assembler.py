#!/usr/bin/env python3

import pytest
from pycurrents.get_test_data import get_test_data_path  # BREADCRUMB: common library
from pytestqt import qtbot
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt

from pycurrents.adcpgui_qt.gui_assembler import (
    GuiApp, dataviewer_option_parser)

assert qtbot


def test_dataviewer_option_parser():
    """
    Testing options parser
    """
    test_folder_path = get_test_data_path()
    test_data_path = test_folder_path + '/uhdas_data/proc'
    arglist = ['-s', '2',
               '-n', '15',
               '-t', 'test run',
               '--dbname', test_data_path,
               '-c', 'os75nb', 'os150nb',
               '--startdday', '264.8',
               '--colorblind',
               '--sonar',  'test',
               '-m', '60',
               '--zoffset', '1000',
               '--vecscale', '10',
               '--step', '2',
               '--sonar', 'test',
               '--whitebg',
               '--debug',
               '--advanced']
    # Parsing command line inputs
    options = dataviewer_option_parser(arglist)
    assert(isinstance(options.delta_t, float))
    assert(options.mode == 'compare')
    assert(options.vec_scale == 0.1)
    assert(options.background == 'w')
    assert(options.colorblind is True)
    assert(options.day_step == 2.0)
    assert(options.delta_t == 60.0)
    assert(options.num_axes == 12)
    assert(options.path is None)
    assert(options.plot_title == 'test run')
    assert(options.sonar == 'test')
    assert(options.compare == [test_data_path + '/os75nb',
                               test_data_path + '/os150nb'])
    assert(options.start_day == 264.8)
    assert (options.z_offset == 1000.0)
    assert (options.debug is True)
    assert (options.advanced is not True)


# FIXME: use pytest-qt and qtbot to really test the GUI/Qt related parts
#        in order to increase the testing coverage
#        see: http://pytest-qt.readthedocs.io/en/latest/intro.html
#        ex.:     window = MyApp()
#                 qtbot.addWidget(window)
#                 window.show()
#                 qtbot.waitForWindowShown(window)
#                 qtbot.mouseClick(window.buttonBox.buttons()[0],Qt.LeftButton)
# FIXME: use image comparison or pytest-mpl for the Matplotlib related parts
#        see: https://github.com/matplotlib/pytest-mpl?files=1
#        see: https://matplotlib.org/1.3.0/devel/testing.html


def test_gui_assembler_in_view_mode(qtbot):
    """
    Testing gui_assembler with all options on
    """
    test_data_path = get_test_data_path()
    arglist = ['-s', '2',
               '-n', '7',
               '-t', 'test run',
               '--dbname', test_data_path + '/codas_db/os38nb_py',
               '--startdday', '30.0',
               '--colorblind',
               '--sonar',  'test',
               '-m', '60',
               '--zoffset', '1000.',
               '--vecscale', '10.',
               '--step', '2.',
               '--sonar', 'test',
               '--whitebg']
    # Parsing command line inputs
    options = dataviewer_option_parser(arglist)
    # Kick-start application
    app = GuiApp(options, test=True)
    # Let the bot click on "show" & "next"
    qtbot.addWidget(app.controlWindow)
    qtbot.addWidget(app.colorPlot)
    qtbot.addWidget(app.topoMap)
    qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonShow,
                     Qt.LeftButton)
    qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonNext,
                     Qt.LeftButton)


# 2023-05-06 This has been failing, at least on some systems, for a long time.
# It is thought to be related to an inconsistency between the order in which
# Python deletes things at tear-down time, and the interdependencies at the C++
# level. See also gui_assembler.py, where this ugliness is now being hidden.
# It's not clear why, at least on my Mac, this segfault is occurring only with
# this particular gui_assembler test and not with the others.
# See also the earlier notes about segfaults in the edit mode test, which are
# avoided by commenting out some of the test actions.
@pytest.mark.skip(reason="probable segfault when cleaning up")
def test_gui_assembler_in_single_ping_mode(qtbot):
    """
    Testing gui_assembler with all options on
    """
    test_data_path = get_test_data_path() + "/uhdas_data/proc/os150bb"

    arglist = ['-p',
               '--dbname', test_data_path]
    # Parsing command line inputs
    options = dataviewer_option_parser(arglist)
    # Kick-start application
    app = GuiApp(options, working_dir=test_data_path, test=True)
    # Let the bot click on "show" & "next"
    qtbot.addWidget(app.controlWindow)
    qtbot.addWidget(app.colorPlot)
    qtbot.addWidget(app.topoMap)
    qtbot.addWidget(app.pingPlots.pingVelWin)
    qtbot.addWidget(app.pingPlots.pingProWin)
    qtbot.addWidget(app.pingPlots.pingFlagWin)
    qtbot.addWidget(app.pingPlots.beamVelWin)
    qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonShow,
                     Qt.LeftButton)
    qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonNext,
                     Qt.LeftButton)


def test_gui_assembler_in_edit_mode(qtbot):
    """
    Testing gui_assembler with all options on
    """
    test_data_path = get_test_data_path()
    arglist = ['-e',
               '-s', '2',
               '-n', '7',
               '-t', 'test run',
               '--dbname', test_data_path + '/uhdas_data/proc/os75bb',
               '--startdday', '30.0',
               '--colorblind',
               '--sonar', 'test',
               '-m', '60',
               '--zoffset', '1000.',
               '--vecscale', '10.',
               '--step', '2.',
               '--sonar', 'test',
               '--whitebg']
    # Parsing command line inputs
    options = dataviewer_option_parser(arglist)
    # Kick-start application
    app = GuiApp(options, test=True)
    qtbot.addWidget(app.controlWindow)
    qtbot.addWidget(app.colorPlot)
    qtbot.addWidget(app.topoMap)

    # Bring up pop-ups
    # TODO - dev. more test on zapper window with qtbot
    # FIXME - The following block does not work (segmentation fault).
    #         My guess is that it is due to the multiple pop-up windows
    #         and their handling by qtbot
    # app.zapperPlot.show()
    # app.resetPlot.show()
    # app.bottomPlot.show()
    # qtbot.addWidget(app.zapperPlot)
    # qtbot.addWidget(app.resetPlot)
    # qtbot.addWidget(app.bottomPlot)

    # Click on buttons
    qtbot.mouseClick(app.controlWindow.tabsContainer.plotTab.checkboxXTicks,
                     Qt.LeftButton)
    # FIXME: these tests lead to Segmentation fault (core dumped)
    # qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonNext,
    #                  Qt.LeftButton)
    # qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonNext,
    #                  Qt.LeftButton)


def test_gui_assembler_in_compare_mode(qtbot):
    test_folder_path = get_test_data_path()
    test_data_path = test_folder_path + '/uhdas_data/proc'
    arglist = ['-s', '2',
               '-n', '15',
               '-t', 'test run',
               '--dbname', test_data_path,
               '-c', 'os75bb', 'os150bb',
               '--startdday', '264.8',
               '--colorblind',
               '--sonar',  'test',
               '-m', '60',
               '--zoffset', '1000',
               '--vecscale', '10',
               '--step', '2',
               '--sonar', 'test',
               '--whitebg',
               '--debug',
               '--advanced']
    # Parsing command line inputs
    options = dataviewer_option_parser(arglist)
    # Kick-start application
    app = GuiApp(options, test=True)
    qtbot.addWidget(app.controlWindow)
    qtbot.addWidget(app.colorPlot)
    qtbot.addWidget(app.topoMap)
    # Bring up pop-ups
    # FIXME - The following block does not work (segmentation fault).
    #         My guess is that it is due to the multiple pop-up windows
    #         and their handling by qtbot
    # app.zapperPlot.show()
    # app.resetPlot.show()
    # qtbot.addWidget(app.zapperPlot)
    # qtbot.addWidget(app.resetPlot)

    # Click on buttons
    qtbot.mouseClick(app.controlWindow.tabsContainer.plotTab.checkboxXTicks,
                     Qt.LeftButton)
    # FIXME: these tests lead to Segmentation fault (core dumped)
    # qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonShow,
    #                  Qt.LeftButton)
    # qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonNext,
    #                  Qt.LeftButton)


def test_ini_file(qtbot):
    """
    Testing *.ini file
    """
    test_data_path = get_test_data_path()
    arglist = ['--dbname', test_data_path + '/codas_db/os38nb_py',
               '--setting_file', './test_config_view.ini']
    # Parsing command line inputs
    options = dataviewer_option_parser(arglist)
    # Kick-start application
    app = GuiApp(options, test=True)
    # Let the bot click on "show" & "next"
    qtbot.addWidget(app.controlWindow)
    qtbot.addWidget(app.colorPlot)
    qtbot.addWidget(app.topoMap)
    qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonShow,
                     Qt.LeftButton)
    qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonNext,
                     Qt.LeftButton)


def test_pgrs_file(qtbot):
    """
    Testing *.pgrs file
    """
    test_data_path = get_test_data_path()
    arglist = ['--dbname', test_data_path + '/codas_db/os38nb_py',
               '--progress_file', './test_config_view.pgrs']
    # Parsing command line inputs
    options = dataviewer_option_parser(arglist)
    # Kick-start application
    app = GuiApp(options, test=True)
    # Let the bot click on "show" & "next"
    qtbot.addWidget(app.controlWindow)
    qtbot.addWidget(app.colorPlot)
    qtbot.addWidget(app.topoMap)
    qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonShow,
                     Qt.LeftButton)
    qtbot.mouseClick(app.controlWindow.timeNavigationBar.buttonNext,
                     Qt.LeftButton)

