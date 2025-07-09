import logging
import sys

import numpy as np

from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Signal
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import (QMainWindow, QSpacerItem,
     QSizePolicy, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QApplication)
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QIcon, QGuiApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import QSize
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from pycurrents.adcpgui_qt.lib import vecplotter
from pycurrents.adcpgui_qt.lib.miscellaneous import is_in_data_range
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (CustomFrame, CustomEntry,
    CustomLabel, CustomDropdown, iconUHDAS, globalStyle)
from pycurrents.adcpgui_qt.lib.mpl_widgets import TopoMplCanvas

# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

_log = logging.getLogger(__name__)

DISPLAY_FEAT = DisplayFeaturesSingleton()


### Custom Formatters & Widgets ###
def _custom_format_coord(bmap, x, y):
    """
    Custom formatter for cursor position indicator from x, y to lon., lat.

    Args:
        bmap: Basemap subclass instance
        x: x plot coordinate in m., float
        y: y plot coordinate in m., float

    Returns: reformatted coordinates indicator, string
    """
    lon, lat = bmap(x, y, inverse=True)
    return 'Lon.: %1.2f, Lat.: %1.2f' % (lon, lat)


class CustomToolBarMap(NavigationToolbar):
    # only display the tools/icons we need
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Home', 'Pan', 'Zoom', 'Save')]
    # Custom Signal
    maptoolbarsignal = Signal()

    def __init__(self, canvas, parent):
        """
        Custom tool bar for topo. map window.
        Custom class derived from matplotlib NavigationToolBar.
        """
        super().__init__(canvas, parent)
        self._parent = parent

    def release_zoom(self, event):
        """
        Overrides and adds functionality to the original release_zoom
        callback.

        Args:
            event: matplotlib event
        """
        # Original callback
        super().release_zoom(event)
        # Additional functionality
        # - change vector sampling proportionally to the zoom in
        new_xlims = self._parent.topax.get_xlim()
        new_ylims = self._parent.topax.get_ylim()
        # - refresh topo. map with new x/y limits
        self._parent.draw_topo_map(xlims=new_xlims, ylims=new_ylims)
        # - emits special signal to be caught in connect_widget_signal_slot.py
        self.maptoolbarsignal.emit()

    def home(self, *args):
        """
        Overrides and adds functionality to the original home callback.

        Args:
            *args: just passes on any arguments
        """
        # Original callback
        super().home(*args)
        # Additional functionality
        # - resets vector sampling rate (delta_t) and refreshes topo. map
        self._parent.reset_xy_lims()
        self._parent.draw_topo_map()
        # - emits special signal to be caught in connect_widget_signal_slot.py
        self.maptoolbarsignal.emit()


### Topographic Map Window ###
class TopoMapWindow(QMainWindow):
    # FIXME - perhaps create a GenericTopoWindow and inherit or
    # FIXME - define TopoMap as a separate class and embed it in a Qt container
    def __init__(self, CD, ref_sonar='', parent=None, test=False):
        """
        Topo. map window class/builder. Custom class derived from QMainWindow.

        Args:
            CD: codas database, CData object (see ../model)
            parent: parent widget, QWidget
            ref_sonar: name of the reference sonar (only in compare mode), str
            test: flag for test/debug purposes, bool
        """
        super().__init__(parent)
        # Attributes
        self.ref_sonar = ref_sonar
        if DISPLAY_FEAT.mode == 'compare':
            self.sonars = CD.sonars
            if not self.ref_sonar:
               self.ref_sonar = DISPLAY_FEAT.sonar_choices[0]
            self.CD = CD[self.ref_sonar]
        else:
            self.CD = CD
        self.vmap = None
        self._delta_t = DISPLAY_FEAT.delta_t / (24. * 60.)
        self._min_delta_t = None
        # Widgets
        # - Topo. plot
        self.canvas = TopoMplCanvas()
        self.figure = self.canvas.figure
        self.topax = self.canvas.topax
        self.toolbar = CustomToolBarMap(self.canvas, self)
        # - controllers
        self.panelBins = CustomFrame("panelBins")
        self.entryBinUpper = CustomEntry(
            size=40, entry_type=int,
            value=DISPLAY_FEAT.ref_bins[0],
            min_value=1)
        self.entryBinLower = CustomEntry(
            size=40, entry_type=int,
            value=DISPLAY_FEAT.ref_bins[1],
            min_value=1)
        self.panelVectScale = CustomFrame("panelVectScale")
        self.entryVectAveraging = CustomEntry(
            size=40, entry_type=int,
            value=DISPLAY_FEAT.delta_t,
            min_value=1)
        self.entryVectScale = CustomEntry(
            size=40, entry_type=float,
            value=1. / DISPLAY_FEAT.vec_scale,
            min_value=0.)

        # Layout
        w = int(0.5 * self.panelBins.sizeHint().width())
        h = int(0.5 * self.panelBins.sizeHint().height())
        spacer = QSpacerItem(w, h, QSizePolicy.Minimum, QSizePolicy.Expanding)
        # - containers
        self.hbox = QWidget(self)  # central widget container
        self.ppBox = QWidget(self)  # panel plot container
        self.zcBox = QWidget(self)  # controllers containers
        # - topo plot layout
        self.ppBox.layout = QVBoxLayout()
        self.ppBox.layout.addWidget(self.canvas)
        self.ppBox.layout.addWidget(self.toolbar)
        self.ppBox.setLayout(self.ppBox.layout)
        #  - ref. CD dropdowmn
        if DISPLAY_FEAT.mode == 'compare':
            # Rearrange list for consistency with dropdown and self.CD
            if self.ref_sonar != self.sonars[0]:
                self.sonars.remove(self.ref_sonar)
                self.sonars.insert(0, self.ref_sonar)
            self.refSonarLabel = CustomLabel("Reference Sonar", style='h3')
            self.refSonarDropdown = CustomDropdown(self.sonars)
        #  - Vec. bins sub-frame
        parent = self.panelBins
        widgets = [CustomLabel("Vec. bins\n[1..N]", style='h3'),
                   QLabel("upper"), self.entryBinUpper,
                   QLabel("lower"), self.entryBinLower]
        self.panelBins.layout = QVBoxLayout()
        for widget in widgets:
            self.panelBins.layout.addWidget(widget)
        parent.setLayout(self.panelBins.layout)
        #  - Vector scale sub-frame
        parent = self.panelVectScale
        widgets = [CustomLabel("Topo.\nVectors", style='h3'),
                   QLabel("Averaging\n(minutes)"), self.entryVectAveraging,
                   QLabel("Scale\nFactor"), self.entryVectScale]
        self.panelVectScale.layout = QVBoxLayout()
        for widget in widgets:
            self.panelVectScale.layout.addWidget(widget)
        parent.setLayout(self.panelVectScale.layout)
        # - controllers layout
        # FIXME: turn this into CustomVBoxLayout and move in qtpy_widgets
        self.zcBox.layout = QVBoxLayout()
        if DISPLAY_FEAT.mode == 'compare':
            widget_list = [self.refSonarLabel, self.refSonarDropdown, spacer]
        else:
            widget_list = []
        widget_list.extend(
            [self.panelBins, spacer, self.panelVectScale, spacer])
        for widget in widget_list:
            if widget == spacer:
                self.zcBox.layout.addItem(widget)
            else:
                self.zcBox.layout.addWidget(widget)
        self.zcBox.layout.addStretch()
        self.zcBox.setLayout(self.zcBox.layout)
        # - central widget layout
        self.hbox.layout = QHBoxLayout()
        self.hbox.layout.addWidget(self.zcBox, 0)
        self.hbox.layout.addWidget(self.ppBox, 10)
        self.hbox.setLayout(self.hbox.layout)
        self.setCentralWidget(self.hbox)

        # Style
        self.setWindowTitle('Topography & Cruise Track')
        self.setWindowIcon(QIcon(iconUHDAS))
        sg = QGuiApplication.primaryScreen().geometry()
        halfScreenHeight = int(0.55 * sg.height())
        defaultSize = QSize(int(halfScreenHeight * 1.3),
                            int(halfScreenHeight * 0.9))
        self.resize(defaultSize)
        # - position
        self.move(0, - halfScreenHeight)
        # - margins
        self.hbox.layout.setContentsMargins(0, 0, 0, 0)
        # Kick start
        if not test:
            self.draw_topo_map()
            self.initial_xlims = self.xlims[:]
            self.initial_ylims = self.ylims[:]

    def draw_topo_map(self, xlims=False, ylims=False):
        """
        Draws the topo. map, method.

        Args:
            xlims: if True, defines current x axis limits as xlims attr., bool.
            ylims: if True, defines current y axis limits as ylims attr., bool.
        """
        # Draws the topo. map
        if self.CD.data is not None:
            try:
                # - clears figure and redefines matplotlib axis topax
                self.figure.clear()
                self.topax = self.figure.add_subplot(111)
                def func(x, y):
                    return _custom_format_coord(self.bmap, x, y)
                self.topax.format_coord = func
                # - defines data's limits and deltas
                topz = self.CD.data.dep[DISPLAY_FEAT.ref_bins[0] - 1]
                endz = self.CD.data.dep[DISPLAY_FEAT.ref_bins[-1] - 1]
                # add dz to include last bin
                cellm = np.diff(self.CD.data.dep)[0]
                deltaz = (endz - topz) + cellm
                # redefine vmap attr. accordingly
                self.vmap = vecplotter.vecplot(
                    self.CD.data,
                    refbins=[0, ],  # we are specifying it now
                    startz=topz,
                    vecscale=DISPLAY_FEAT.vec_scale,
                    zoffset=DISPLAY_FEAT.z_offset,
                    deltaz=deltaz,
                    deltat=self.delta_t,
                    offset=cellm/2.,
                    topo_kw=dict(reset_source=True,
                                 levels='auto'),
                    ax=self.topax,
                    colorblind=DISPLAY_FEAT.colorblind)
                setattr(self, "bmap", self.vmap.bmap)
            except ValueError:  # see vecplotter.py line 45 & 282
                self.default_plot(msg='No good positions')
        else:
            self.default_plot()
        # Make visible
        if not self.isVisible():
            self.setVisible(True)
        # Sets x, y limits
        self.set_xy_lims(xlims=xlims, ylims=ylims)

    def reset_xy_lims(self):
        """Resets x, y limits to default"""
        self.xlims = self.initial_xlims[:]
        self.ylims = self.initial_ylims[:]

    def set_xy_lims(self, xlims=False, ylims=False):
        """
        Propagates current/zoomed x,y axis limits

        Args:
            xlims: if True, defines current x axis limits as xlims attr., bool.
            ylims: if True, defines current y axis limits as ylims attr., bool.
        """
        if xlims:
            self.topax.set_xlim(xlims)
            self.xlims = self.topax.get_xlim()
        else:
            try:
                if not self.xlims == self.topax.get_xlim():
                    self.xlims = self.topax.get_xlim()
                    self.initial_xlims = self.xlims
            except AttributeError:
                self.xlims = self.topax.get_xlim()
                self.topax.set_xlim(self.xlims)

        if ylims:
            self.topax.set_ylim(ylims)
            self.ylims = self.topax.get_ylim()
        else:
            try:
                if not self.ylims == self.topax.get_ylim():
                    self.ylims = self.topax.get_ylim()
                    self.initial_ylims = self.ylims
            except AttributeError:
                self.ylims = self.topax.get_ylim()
                self.topax.set_ylim(self.ylims)

    def _get_min_delta_t(self):
        """Gets the minimum vector sampling rate"""
        if self.CD.data is not None:
            self._min_delta_t = np.median(np.diff(self.CD.data.dday))
        else:
            self._min_delta_t = 5. / (24. * 60.)  # equivalent to 5 minutes
        return self._min_delta_t

    def _get_delta_t(self):
        """Get vector averaging rate"""
        if DISPLAY_FEAT.delta_t > self.min_delta_t:
            self._delta_t = DISPLAY_FEAT.delta_t / (24. * 60.)
        else:
            self._delta_t = self.min_delta_t
        return self._delta_t

    def _change_ref_CD(self, CD):
        setattr(self, 'CD', CD)

    def default_plot(self, msg=''):
        # - alternative if empty data == out of time range request
        _log.debug('no data found')
        self.figure.clear()
        self.topax = self.figure.add_subplot(111)
        if is_in_data_range(DISPLAY_FEAT) and not msg:
            msg = 'No data found in requested time range'
        elif not msg:
            msg = 'Outside of data range'
        self.topax.text(.5, .5, msg, color='r', size=12,
                        transform=self.topax.transAxes, ha='center')

    # Dynamic attributes
    min_delta_t = property(_get_min_delta_t)
    delta_t = property(_get_delta_t)

    def random_topo_map_window_plot(self):
        """Plots some random stuff for testing purposes"""
        import random
        # random data
        data = [random.random() for i in range(10)]
        # make axis
        self.ax = self.figure.add_subplot(111)
        # discards the old graph
        self.ax.cla()
        # plot data
        self.ax.plot(data, '*-')
        # refresh canvas
        self.canvas.draw()


### Example code for debugging purposes ###
if __name__ == '__main__':
    from pycurrents.adcpgui_qt.model.display_features_models import (
        displayFeaturesCompare, DisplayFeaturesSingleton)
    from pycurrents.system.misc import Bunch
    CD = Bunch({'os75bb': None, 'wh300': None, 'sonars': ['os75bb', 'wh300']})
    display_dict = displayFeaturesCompare(CD.sonars)
    DF = DisplayFeaturesSingleton(display_dict)
    app = QApplication(sys.argv)
    app.setStyle(globalStyle)
    topoMapWindow = TopoMapWindow(CD, test=True)
    topoMapWindow.random_topo_map_window_plot()
    topoMapWindow.show()
    sys.exit(app.exec_())
