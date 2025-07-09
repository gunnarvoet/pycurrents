import os
import sys
import logging

# Standard imports
from glob import glob
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QIcon, QGuiApplication
from pycurrents.adcp.pingsuite import PingSuite # BREADCRUMB - common lib.
from pycurrents.adcp.uhdasconfig import UhdasConfig # BREADCRUMB - common lib.
from pycurrents.adcpgui_qt.lib.ping_plotter import plot_pings

# Matplotlib imports
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# Local imports
from pycurrents.adcpgui_qt.lib.qtpy_widgets import waiting_cursor, iconUHDAS
from pycurrents.adcpgui_qt.lib.mpl_widgets import GenericPlotMplCanvas

# Standard logging
_log = logging.getLogger(__name__)


class PingPlotsWindows:
    def __init__(self, sonar, working_dir=os.getcwd(),
                 configtype=None, cruisename=None, ibadbeam=None,
                 uhdas_dir=None, parent=None):
        """
        Regroup the 4 single-ping plotting windows
        Class containing 4 PingPlotWindow's objetcs and one group method

        Args:
            sonar: sonar name, ex. os75bb = instrument + frequency + mode, str.
            working_dir: path to working directory, str.
            configtype: type of configuration ('matlab', 'python' or 'pyproc'),
                        str.
            cruisename: cruise name, str.
            ibadbeam: index of the malfunctioning ADCP beam, int.; 0, 1, 2 or 3
            parent: PySide6 or PyQt5 parent widget
        """
        # Attributes
        self.bad_color = (0.8, 0.8, 0.8)  # RGB color associated with bad values
        # - paths & ascii files...and sanity checks
        # FIXME - also use dbpath (if it exist) for crawling
        # config_path, editparam_path
        # TODO: the config discovery works relatively from where you launch the app...change that
        config_path = ''
        for root, dirs, files in os.walk(working_dir):
            if '/config' in root:
                config_path = root
                break
        if not config_path:
            msg = 'COULD FIND config DIRECTORY:'
            msg += '\n - Either your folder structure is compromise'
            msg += '\n - Or the GUI was not been launched from within the sonar proc. dir.'
            print(msg)
            _log.error(msg)
            sys.exit(1)
        editparam_path = ''
        for root, dirs, files in os.walk(working_dir):
            for file in files:
                filename = os.path.join(root, file)
                if '/ping_editparams.txt' in filename:
                    editparam_path = filename
                    break
        if not cruisename:
            proc_files = glob(os.path.join(config_path, '*_proc.py'))
            if len(proc_files) > 1:
                msg = "THERE ARE SEVERAL *_proc.py in %s" % config_path
                msg += "\nSpecify which one to use by using the --cruisename option"
                msg += "\nex. for using CRUISE_NAME_proc.py:"
                msg += "\n  dataviewer.py -p --cruisename CRUISE_NAME"
                print(msg)
                _log.error(msg)
                sys.exit(1)
            elif len(proc_files) == 0:
                msg = "The present database is too old and needs to be "
                msg += "reprocessed with a newer version of UHDAS in order to "
                msg += "be compatible with this mode."
                print(msg)
                _log.error(msg)
                sys.exit(1)
            else:
                cruisename = proc_files[0].split('/')[-1][:-8]
        # - config
        self.uhdas_cfg = UhdasConfig(cfgpath=config_path,
                                     cruisename=cruisename,
                                     sonar=sonar,
                                     configtype=configtype,
                                     uhdas_dir=uhdas_dir)
        self.PS = PingSuite(
            sonar, cfgpath=config_path, cruisename=cruisename,
            uhdas_cfg=self.uhdas_cfg, editparams_file=editparam_path,
            ibadbeam=ibadbeam)
        # - figures
        self.pingVelFig = Figure()
        self.pingVelWin = PingPlotWindow(self.pingVelFig,
                                         title='Ping Velocities',
                                         small=False,
                                         parent=parent)
        self.pingFlagFig = Figure()
        self.pingFlagWin = PingPlotWindow(self.pingFlagFig,
                                          title='Ping Flags',
                                          small=False,
                                          parent=parent)
        self.pingProFig = Figure()
        self.pingProWin = PingPlotWindow(self.pingProFig,
                                         title='Ping Profiles',
                                         parent=parent)
        self.beamVelFig = Figure()
        self.beamVelWin = PingPlotWindow(self.beamVelFig,
                                         title='Beam Velocities',
                                         parent=parent)
        # Initialization
        self.pingVelWin.setVisible(False)
        self.pingProWin.setVisible(False)
        self.pingFlagWin.setVisible(False)
        self.beamVelWin.setVisible(False)

    def group_refresh(self, start_day, nsecs, bin, colorblind=False):
        """
        Refresh all the single-ping plots

        Args:
            start_day: start day, decimal day, float.
            nsecs: time step in seconds, float.
            bin: boolean switch for y-axis in bins
            colorblind: boolean switch for colorblind friendly color-schemes
        """
        self.PS.pinger.get_pings(start_day, nsecs)
        plot_pings(self.PS.pinger.ens, self.PS.pinger.flags,
                   self.pingFlagFig, self.pingVelFig,
                   self.pingProFig, self.beamVelFig, self.bad_color, bin,
                   colorblind)
        self.pingVelWin.refresh()
        self.pingFlagWin.refresh()
        self.pingProWin.refresh()
        self.beamVelWin.refresh()


class PingPlotWindow(QMainWindow):
    # Window counter
    idWin = -1

    def __init__(self, figure, title='Ping Plotting window', small=True,
                 parent=None):
        """
        Factory class for single-ping plotting windows

        Args:
            figure: matplotlib's Figure object
            title: title, str.
            small: boolean switch for making smaller window
            parent: PyQt parent widget
        """
        super().__init__(parent)
        # Increment counter
        PingPlotWindow.idWin += 1
        # Attributes
        self.canvas = GenericPlotMplCanvas(figure, parent=self)
        self.figure = self.canvas.figure
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Layout/central widget
        self.vbox = QWidget(self)
        self.canvas.setParent(self.vbox)
        self.vbox.layout = QVBoxLayout(self.vbox)
        self.vbox.layout.addWidget(self.canvas)
        self.vbox.layout.addWidget(self.toolbar)
        self.vbox.setLayout(self.vbox.layout)
        self.setCentralWidget(self.vbox)

        # Style
        # - decorators
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(iconUHDAS))
        # - size
        sg = QGuiApplication.primaryScreen().geometry()
        if small:
            self.resize(int(sg.width() * 0.25), int(sg.height() * 0.5))
        else:
            self.resize(int(sg.width() * 0.5), int(sg.height() * 0.5))
        # - position
        widget = self.geometry()
        increment = int(0.1 * PingPlotWindow.idWin * sg.height())
        x = sg.width() - widget.width() - increment
        y = increment
        self.move(x, y)

    # Local lib
    def refresh(self):
        if not self.isVisible():
            self.setVisible(True)
        self.canvas.draw()

    # Override close function
    @waiting_cursor
    def closeEvent(self, ce):
        # DO NOT CLOSE but make invisible
        self.setVisible(False)

