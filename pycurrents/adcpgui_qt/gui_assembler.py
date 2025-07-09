# This GUI is built around a MVP design pattern:
#   - See pycurrents/adcpgui_qt/lib/images/Model_View_presenter_GUI_Design_Pattern.png
#   - See https://www.codeproject.com/Articles/228214/...
#         ...Understanding-Basics-of-UI-Design-Pattern-MVC-MVP

import os
import sys

from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
# Model
from pycurrents.adcpgui_qt.model.ascii_files_models import (
    ASCIIandPathContainer, ASCIIandPathContainerCompareMode)
from pycurrents.adcpgui_qt.model.display_features_models import (
    DisplayFeaturesSingleton, displayFeatures, displayFeaturesCompare,
    displayFeaturesEdit, displayFeaturesSinglePing)
from pycurrents.adcpgui_qt.model.thresholds_models import (
    Thresholds, ThresholdsCompare)
from pycurrents.adcpgui_qt.model.codas_data_models import (
    CData, CDataEdit, CDataCompare)
# View
from pycurrents.adcpgui_qt.view.control_window import ControlWindow
from pycurrents.adcpgui_qt.view.color_plot_window import ColorPlotWindow
from pycurrents.adcpgui_qt.view.topo_map_window import TopoMapWindow
from pycurrents.adcpgui_qt.view.zapper_plot_window import ZapperPlotWindow
from pycurrents.adcpgui_qt.view.seabed_selector_plot_window import BottomPlotWindow
from pycurrents.adcpgui_qt.view.reset_editing_plot_window import ResetPlotWindow
from pycurrents.adcpgui_qt.view.ping_plot_windows import PingPlotsWindows
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (
    globalStyle, make_busy_cursor, restore_cursor)
# Presenter
from pycurrents.adcpgui_qt.presenter.intercommunication import (
    initialize_display_feat, initialize_display_feat_compare_mode,
    initialize_txycursors)
from pycurrents.adcpgui_qt.presenter.connection_widget_signal_slot import (
    connect_control_panels_topo, connect_popup_control, connect_ascii_models,
    connect_control_panels_pingplots)
# Misc
from pycurrents.adcpgui_qt.argument_parsers import dataviewer_option_parser
from pycurrents.adcpgui_qt.lib.miscellaneous import nowstr

# Standard logging
import logging
_log = logging.getLogger(__name__)


### GUI assembler ###
class GuiApp:
    def __init__(self, options, working_dir=None, test=False):
        """
        UHDAS post-processing GUI application

        Args:
            options: set of options, argparse object
            working_dir: path to working directory, str.
                         mostly used for testing purposes
            test: switch to test mode, bool.
        """
        self.mode = options.mode
        if self.mode not in ["view", "edit", "compare", "single ping"]:
            _log.error("=====ERROR=====\n"
                      "Mode %s is not recognized; there is no way you should be able to get here!" % self.mode)
            sys.exit(1)

        # Let qtbot handle the QApplication instances for testing
        self.app = QApplication.instance()
        if not self.app:
            # Normal operation
            self.app = QApplication(sys.argv)
        if not test:
            try:
                self.app.setStyle(globalStyle)
            except RuntimeError:  # in case chosen style not available
                pass

        # Spinning wheel while launching the GUI
        make_busy_cursor()

        # Check if user has writing permission
        write_permission = True
        for path in options.dbpathname:
            if not os.access(path, os.W_OK) and self.mode in ['edit', 'compare']:
                msg = "======WARNING======\n"
                print(msg)
                msg = "Write permission denied in %s" % path
                print(msg)
                _log.debug(msg)
                msg = "Database editing functionality disabled"
                print(msg)
                if self.mode == 'edit':
                    self.mode = 'view'
                    options.mode = 'view'
                write_permission = False
        ### Models ###
        # - ASCII files & paths
        if self.mode == 'compare':
                paths = options.compare
                asciiNpaths = ASCIIandPathContainerCompareMode(paths)
                sonars = list(asciiNpaths.keys())
        else:
            path = options.dbpathname[0]
            asciiNpaths = ASCIIandPathContainer(self.mode, path)
        asciiNpaths.write_to_log(
            "\n\n=== %s: Starting UHDAS post-processing in %s mode ==="
            % (nowstr(), self.mode))
        # - Display features container
        if self.mode == 'edit':
            display_dict = displayFeaturesEdit()
        elif self.mode == 'compare':
            display_dict = displayFeaturesCompare(sonars, write_permission)
        elif self.mode == 'single ping':
            display_dict = displayFeaturesSinglePing()
        else:
            display_dict = displayFeatures()
        display_feat = DisplayFeaturesSingleton(display_dict)
        # - Thersholds
        if self.mode == 'edit':
            thresholds = Thresholds(asciiNpaths.edit_dir_path)  # FIXME: pass on ascii_container rather than its attributes?
        elif self.mode == 'compare':
            thresholds = ThresholdsCompare(
                sonars, asciiNpaths.edit_dir_paths)
        else:
            thresholds = Thresholds()
        # - CODAS database
        if self.mode == 'edit':
            CD = CDataEdit(thresholds, asciiNpaths.db_path, options)
        elif self.mode == 'compare':
            CD = CDataCompare(
                sonars, thresholds, asciiNpaths.db_paths, options)
        else:
            CD = CData(asciiNpaths.db_path, options)
        # - Initialize models and user's options
        if self.mode != 'compare':
            initialize_display_feat(thresholds, asciiNpaths, CD, options)
        else:
            initialize_display_feat_compare_mode(
                sonars, thresholds, asciiNpaths, CD, options)

        ### Views ###
        # Start up views
        self.controlWindow = ControlWindow(
            asciiNpaths.log_path,  # FIXME: pass on ascii_container rather than its attributes?
            mode=self.mode, thresholds=thresholds, test=test
        )
        self.log_tab = self.controlWindow.tabsContainer.logTab
        self.colorPlot = ColorPlotWindow(CD,
                                            parent=self.controlWindow)
        self.topoMap = TopoMapWindow(CD,
                                        ref_sonar=options.ref_sonar,
                                        parent=self.controlWindow)
        colorPlotWinList = [self.colorPlot]
        popup_dict = {}
        if self.mode in ['edit', 'compare']:
            self.zapperPlot = ZapperPlotWindow(CD,
                                                parent=self.controlWindow)
            popup_dict['zap'] = self.zapperPlot
            self.resetPlot = ResetPlotWindow(CD,
                                                parent=self.controlWindow)
            popup_dict['reset'] = self.resetPlot
            colorPlotWinList += [self.zapperPlot, self.resetPlot]
            if self.mode == 'edit':
                self.bottomPlot = BottomPlotWindow(
                    CD, parent=self.controlWindow)
                popup_dict['bottom'] = self.bottomPlot
                colorPlotWinList += [self.bottomPlot]
        if self.mode == 'single ping':
            kwargs = {'cruisename': options.cruisename,
                        'configtype': options.configtype,
                        'ibadbeam': options.ibadbeam,
                        'uhdas_dir': options.uhdas_dir,
                        'parent': self.controlWindow}
            if working_dir:
                kwargs['working_dir'] = working_dir
            try:
                self.pingPlots = PingPlotsWindows(CD.sonar, **kwargs)
            except ValueError:
                # Case where uhdas_dir in *_proc.py is not valid
                msg = "uhdas_dir in *_proc.py is not valid"
                msg += "\nuse the --uhdas_dir option to specify its path"
                _log.error(msg)
                sys.exit(1)

        # Adding txy cursors
        self.txycursors = initialize_txycursors(
            colorPlotWinList, self.topoMap)

        ### Presenter ###
        # Connect widgets, signals and slots
        connect_control_panels_topo(self.mode,
            self.controlWindow, self.colorPlot, self.topoMap,  # Views
            self.txycursors,
            thresholds, asciiNpaths, CD)  # Models
        if self.mode in ['edit', 'compare']:
            connect_popup_control(popup_dict, self.controlWindow)
            connect_ascii_models(self.controlWindow, self.resetPlot,  # Views
                                    thresholds, asciiNpaths, CD)  # Models
        if self.mode == 'single ping':
            connect_control_panels_pingplots(
                self.controlWindow, self.colorPlot, self.pingPlots)

        ### Kick start application ###

        restore_cursor()
        # - Show GUI components
        self.colorPlot.show()
        self.topoMap.show()
        self.controlWindow.show()
        if test:
            return

        # - Hide pop-up windows to start with
        if self.mode in ['edit', 'compare']:
            self.zapperPlot.setVisible(False)
            self.resetPlot.setVisible(False)
            if self.mode == 'edit':
                self.bottomPlot.setVisible(False)
        # - Push var to ipython kernel
        if options.advanced:
            kernel_vars = dict(
                display_feat=display_feat,
                asciiNpaths_container=asciiNpaths,
                CD=CD)
            if self.mode in ['edit', 'compare']:
                kernel_vars['thresholds'] = thresholds
            if self.mode == "single ping":
                kernel_vars['PS'] = self.pingPlots.PS
                kernel_vars['uhdas_cfg'] = self.pingPlots.uhdas_cfg
            self.controlWindow.tabsContainer.consoleTab.push_vars(
                kernel_vars)
            self.controlWindow.tabsContainer.consoleTab.kick_start()
        # - Force click "Refresh"
        self.controlWindow.tabsContainer.plotTab.refreshPanelsButton.click()
        # - Start the loop.
        status = self.app.exec()
        # - Use a trick to avoid a segfault that seems to result from
        #   an inherent problem with pyqt:
        #   https://stackoverflow.com/questions/39107846/segmentation-fault-on-exit-in-pyqt5-but-not-pyqt4
        os._exit(status)


### Example code for debugging purposes ###
if __name__ == '__main__':
    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        from pycurrents.get_test_data import get_test_data_path
        test_folder_path = get_test_data_path()
        # log to stdout
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        logging.basicConfig(handlers=[ch], level=logging.DEBUG,
                            format='%(message)s')

        ### Compare mode
        test_data_path = test_folder_path + '/uhdas_data/proc'
        arglist = ['--dbname', test_data_path,
                   '-c', 'os75nb', 'os75bb', 'os150nb', 'os150bb',
                   '--advanced']
        # test_data_path = test_folder_path + '/uhdas_data/proc'
        # arglist = ['--dbname', test_data_path,
        #            '-c', 'os150nb', 'os150bb',
        #            '--advanced']
        ### Edit mode
        # test_data_path = test_folder_path + '/uhdas_data/proc/os75nb'
        # arglist = ['--dbname', test_data_path,
        #            '-e', '--colorblind',
        #            '--advanced']
        ### View mode
        # test_data_path = test_folder_path + '/uhdas_data/proc/os75bb'
        # arglist = ['--dbname', test_data_path,
        #            '--advanced']
        ### Single ping mode
        # TODO: the config discovery works relatively from where you launch the app...change that
        # test_data_path = test_folder_path + '/uhdas_data/proc/os150nb'
        # arglist = ['--dbname', test_data_path,
        #            '-p', '--ibadbeam', '2']
    else:
        arglist = sys.argv[1:]
    # Parsing command line inputs
    options = dataviewer_option_parser(arglist)
    # Kick-start application
    guiApp = GuiApp(options)


