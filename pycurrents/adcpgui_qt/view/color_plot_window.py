import os
import sys
import logging
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication, QWidget, QVBoxLayout
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QIcon, QGuiApplication

from pycurrents.adcpgui_qt.lib.mpl_widgets import PlotMplCanvas
from pycurrents.adcpgui_qt.view.generic_plot_window import (
    GenericColorPlotWindow, CustomToolBarPlot)
from pycurrents.adcpgui_qt.lib.qtpy_widgets import iconUHDAS, globalStyle

# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

# Standard logging
_log = logging.getLogger(__name__)

DISPLAY_FEAT = DisplayFeaturesSingleton()


class ColorPlotWindow(GenericColorPlotWindow):
    def __init__(self, CD, parent=None, test=False):
        """
        Color plot window class. Custom class inherited from GenericColorPlotWindow

        Args:
            CD: codas database, CData object (see ../model)
            parent: parent widget, QWidget
            test: flag for test/debug purposes, bool
        """
        super().__init__(CD, parent=parent)
        # Widgets
        self.canvas = PlotMplCanvas(self.chosenVariables)
        self.figure = self.canvas.figure
        self.axdict = self.canvas.axdict
        self.toolbar = CustomToolBarPlot(self.canvas, self)

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
        if DISPLAY_FEAT.plot_title:
            title = DISPLAY_FEAT.plot_title
        else:
            if DISPLAY_FEAT.sonar:
                title = 'Panels - Instrument(s): ' + DISPLAY_FEAT.sonar
            else:
                title = 'Panels'
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(iconUHDAS))
        # - size
        sg = QGuiApplication.primaryScreen().geometry()
        defaultSize = 0.7 * sg.size()
        self.resize(defaultSize)
        # - position
        widget = self.geometry()
        x = sg.width() - widget.width()
        y = 0
        self.move(x, y)

        # Custom connection - custom message in status bar
        # - mouseMove
        self.canvas.mpl_connect('motion_notify_event', self.toolbar.mouse_move)

        # Kick start
        if not test:
            self.draw_color_plot(new_axis=True)


### Example code for debugging purposes ###
if __name__ == '__main__':
    from pycurrents.adcpgui_qt.argument_parsers import dataviewer_option_parser
    from pycurrents.adcpgui_qt.model.display_features_models import (
        displayFeatures, DisplayFeaturesSingleton)
    from pycurrents.adcpgui_qt.model.thresholds_models import Thresholds
    from pycurrents.adcpgui_qt.model.ascii_files_models import ASCIIandPathContainer
    from pycurrents.adcpgui_qt.model.codas_data_models import CData
    from pycurrents.adcpgui_qt.presenter.intercommunication import (
        get_dbpath, initialize_display_feat)

    # PyCharm-specific switch for debugging purposes
    if 'PYCHARM_HOSTED' in os.environ:
        from pycurrents.get_test_data import get_test_data_path

        test_data_path = get_test_data_path()
        path = test_data_path + '/codas_db/os38nb_py'
    else:
        path = input("Path to instrument folder")

    arglist = ['--dbname', path]
    app = QApplication(sys.argv)
    app.setStyle(globalStyle)
    options = dataviewer_option_parser(arglist)
    dbpath = get_dbpath(path)
    CD = CData(dbpath, options)
    display_feat = displayFeatures()
    DisplayFeaturesSingleton(display_feat)
    thresholds = Thresholds()
    ascii_container = ASCIIandPathContainer('view', path)
    initialize_display_feat(thresholds, ascii_container, CD, options)
    colorPlotWindow = ColorPlotWindow(CD)
    colorPlotWindow.show()
    colorPlotWindow.draw_color_plot(new_axis=True)
    colorPlotWindow.canvas.draw()
    sys.exit(app.exec_())
