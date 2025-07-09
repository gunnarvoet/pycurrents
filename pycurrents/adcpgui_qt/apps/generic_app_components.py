from packaging import version
import logging

# Standard imports
import numpy as np
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import (
    QRadioButton, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout)
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QIcon, QGuiApplication

# Matplotlib imports
import matplotlib as mpl
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.ticker import FuncFormatter
from matplotlib.dates import AutoDateLocator
from matplotlib.widgets import (
    SpanSelector, RectangleSelector, PolygonSelector, LassoSelector)

# Local imports
# BREADCRUMB: common lib starts here...
from pycurrents.num.utility import points_inside_poly
# BREADCRUMB: ...common lib finishes here
from pycurrents.adcpgui_qt.lib.miscellaneous import utc_formatting
from pycurrents.adcpgui_qt.lib.plotting_parameters import FORMATTER, tickerUTC
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (
    CustomDropdown, CustomPushButton, CustomLabel, iconUHDAS)
from pycurrents.adcpgui_qt.lib.mpl_widgets import GenericPlotMplCanvas
from pycurrents.adcpgui_qt.lib.zappers import TOOL_NAMES, TOOL_INFO

# Standard logging
_log = logging.getLogger(__name__)


### Generic View Components ###
class CustomToolBarApp(NavigationToolbar):
    def __init__(self, canvas, widgets_to_hide, parent):
        """
        Custom tool bar for zapper window.
        Custom class derived from matplotlib NavigationToolbar

        Args:
            canvas: Matplotlib canvas
            widgets_to_hide: list of PyQt5 or PySide6  widgets to hide
            parent: PySide6 or PyQt5 parent widget
        """
        super().__init__(canvas, parent)
        self.widgets_to_hide = widgets_to_hide
        self._parent = parent

    def pan(self, *args):
        """
        Overrides and adds functionality to the original pan callback.

        Args:
            event: matplolib event
        """
        # Original callback
        super().pan(*args)
        # Additional callbacks - here disables a list of widgets
        for widget in self.widgets_to_hide:
            widget.setEnabled(not self.mode)
        # Update tool info
        self.draw_tool_info()
        # log it
        _log.debug("On custom pan")

    def zoom(self, *args):
        """
        Overrides and adds functionality to the original zoom callback.

        Args:
            event: matplolib event
        """
        # Original callback
        super().zoom(*args)
        # Additional callbacks - here disables a list of widgets
        for widget in self.widgets_to_hide:
            widget.setEnabled(not self.mode)
        # Update tool info
        self.draw_tool_info()
        # log it
        _log.debug("On custom pan")

    def draw_tool_info(self):
        """
        Draw tool's info in top right corner
        """
        try:
            if self.mode:
                msg = 'Pan/zoom active - Selector inactive'
            else:
                if hasattr(self._parent, "dropdownTool"):
                    msg = TOOL_INFO[self._parent.dropdownTool.currentText()]
                else:
                    # special case for seabed selector
                    msg = TOOL_INFO['seabed']
            try:
                self._parent.toolInfo.remove()
            except ValueError:  # when artist not defined or already removed
                pass
            self._parent.toolInfo = self._parent.figure.text(
                0.02, 0.02, msg,
                horizontalalignment='left',
                verticalalignment='bottom',
                color='r', fontweight='bold')
            self._parent.canvas.draw()
        except AttributeError:
            pass


class GenericPlotWindow(QMainWindow):
    def __init__(self, figure, title='Generic Plotting window', utc_date=False,
                 yearbase=None, ref_axis=None, with_toolbar=False,
                 parent=None):
        """
        Generic plotting window for Apps. inheriting from Qt's QMainWindow

        Args:
            figure: Matplotlib's Figure object
            title: window title, str.
            utc_date: boolean switch
            yearbase: year base, int.
            ref_axis: reference x axis, Matplotlib's axis object
            with_toolbar: boolean switch
            parent: PySide6 or PyQt5 parent widget
        """
        super().__init__(parent)
        # Attributes
        self.canvas = GenericPlotMplCanvas(figure, parent=self)
        self.figure = self.canvas.figure
        if with_toolbar:
            self.toolbar = NavigationToolbar(self.canvas, self)
        self.utc_date = utc_date
        self.yearbase = yearbase
        self.ref_axis = ref_axis

        # Layout/central widget
        self.vbox = QWidget(self)
        self.canvas.setParent(self.vbox)
        self.vbox.layout = QVBoxLayout(self.vbox)
        self.vbox.layout.addWidget(self.canvas)
        if with_toolbar:
            self.vbox.layout.addWidget(self.toolbar)
        self.vbox.setLayout(self.vbox.layout)
        self.setCentralWidget(self.vbox)

        # Style
        # - decorators
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(iconUHDAS))
        # - size
        sg = QGuiApplication.primaryScreen().geometry()
        self.resize(sg.width() // 2, sg.height())
        # - position
        widget = self.geometry()
        x = sg.width() - widget.width()
        y = 0
        self.move(x, y)

    # Local lib
    def refresh(self):
        self._format_xaxis(utc_date=self.utc_date)
        self.canvas.draw()

    def _format_xaxis(self, utc_date=False):
        """
        Format X axis ticks
        """
        # FIXME - really close to _format_axis in panel_plotter.py
        #         make static and move to lib
        # sanity check
        if not (self.yearbase and self.ref_axis):
            return
        # set new ticks
        if not utc_date:
            self.ref_axis.xaxis.set_major_locator(tickerUTC)
            self.ref_axis.xaxis.set_major_formatter(FORMATTER)
            xtext_rotation = 0
            fontsize = 10
            alignment = 'center'
        else:
            # Fix for Ticket 685
            self.ref_axis.xaxis.set_major_locator(AutoDateLocator())
            utc_formatter = FuncFormatter(
                lambda x, pos: utc_formatting(x, pos, self.yearbase))
            self.ref_axis.xaxis.set_major_formatter(utc_formatter)
            fontsize = 9
            xtext_rotation = 20
            alignment = 'right'
        try:
            for label in self.ref_axis.get_xticklabels():
                label.set_fontsize(fontsize)
                label.set_ha(alignment)
                label.set_rotation(xtext_rotation)
        except ValueError:
            _log.debug("""
            ---panel_plotter.py known bug---
            ValueError: ordinal must be >= 1. For more details see
            https://github.com/matplotlib/matplotlib/issues/6023
            """)
            pass


class GenericZapperWindow(GenericPlotWindow):
    def __init__(self, xdata, ydata, figure,
                 title='Generic Plotting window',
                 utc_date=False, yearbase=None,
                 shared_axis=None, parent=None, parent_app=None):
        """
        Generic zapper window for Apps. inheriting from GenericPlotWindow

        Args:
            xdata: x-axis data set, 1D numpy array
            ydata: y-axis data set, 1D numpy array
            figure: Matplotlib's Figure object
            title: window's title, str.
            utc_date: boolean switch
            yearbase: year base, int.
            shared_axis: shared x axis, Matplotlib's axis object
            parent: PySide6 or PyQt5 parent widget
            parent_app: Pyside6 or PyQt5 parent widget (control panel here)
        """
        super().__init__(
            figure, title=title, utc_date=utc_date, yearbase=yearbase,
            ref_axis=shared_axis, parent=parent)
        # Attributes
        self.parent_app = parent_app
        self.tools = TOOL_NAMES
        self.masking = True
        self.fig = figure
        self.ax = figure.axes[0]
        self.xdata = xdata
        self.ydata = ydata
        self.temp_mask = np.zeros((), dtype=bool)
        self.mask = np.zeros(self.xdata.shape, dtype=bool)
        self.rs = None
        self.toolInfo = self.figure.text(0.02, 0.02, 'Tool Info',
                                         horizontalalignment='left',
                                         verticalalignment='bottom',
                                         color='r', fontweight='bold')
        # Widgets
        # - zappers
        self.masking = True  # True == masking; False == unmasking
        # - control side
        self.dropdownTool = CustomDropdown(self.tools)
        self.radiobuttonMask = QRadioButton("Mask")
        self.radiobuttonUnmask = QRadioButton("Unmask")
        self.resetButton = CustomPushButton('Reset edits')
        # - custom tool bar
        widgets_to_hide = [self.dropdownTool, self.radiobuttonMask,
                           self.radiobuttonUnmask, self.resetButton]
        self.toolbar = CustomToolBarApp(self.canvas, widgets_to_hide, self)
        self.vbox.layout.addWidget(self.toolbar)
        # Layouts
        # - sub-container
        self.hbox = QWidget(self)  # widget container
        self.hbox.layout = QHBoxLayout()
        widgets = [
            CustomLabel("Select by: ", style='h3'), self.dropdownTool,
            CustomLabel(" | Mode: ", style='h3'), self.radiobuttonMask,
            self.radiobuttonUnmask,
            CustomLabel(" | ", style='h3'), self.resetButton]
        for widget in widgets:
            self.hbox.layout.addWidget(widget)
        self.hbox.layout.addStretch()
        # - layout
        self.hbox.setLayout(self.hbox.layout)
        self.vbox.layout.insertWidget(1, self.hbox, 0)
        self.vbox.setLayout(self.vbox.layout)
        # Custom/Local connection & callbacks
        # - tool changes
        self.dropdownTool.currentTextChanged.connect(
            self.set_zapper)
        # - radio button
        self.radiobuttonMask.setChecked(True)
        self.radiobuttonMask.clicked.connect(self._on_radio_button_clicked)
        self.radiobuttonUnmask.clicked.connect(self._on_radio_button_clicked)
        # - reset button
        self.resetButton.clicked.connect(self._reset_mask)
        # Style
        # - size
        sg = QGuiApplication.primaryScreen().geometry()
        self.resize(sg.width() // 2, sg.height() // 2)
        # - position
        self.move(0, 0)
        # Initialization
        self.set_zapper()

    # Slots
    def set_zapper(self):
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
        self._get_zapper()
        # Activate zapper
        try:
            self.zapper.set_active(True)
        except AttributeError:  # for click zapper
            pass
        # update tool info
        self.toolbar.draw_tool_info()

    def _on_radio_button_clicked(self):
        if self.radiobuttonMask.isChecked():
            self.masking = True
        elif self.radiobuttonUnmask.isChecked():
            self.masking = False

    def _get_zapper(self):
        """
        Set zapper/selector type based on dropdownTool current choice
        """
        zapper_name = self.dropdownTool.currentText()
        rectprops = dict(alpha=0.25, facecolor='red', edgecolor='k')
        lineprops = dict(alpha=0.5, color='red')
        markerprops = dict(alpha=0.5, color='red')

        if version.parse(mpl.__version__) < version.parse('3.5'):
            rect_span_kw = dict(rectprops=rectprops)
            poly_kw = dict(lineprops=lineprops, markerprops=markerprops)
            lasso_kw = dict(lineprops=lineprops)
        else:
            rect_span_kw = dict(props=rectprops)
            poly_kw = dict(props=lineprops, handle_props=markerprops)
            lasso_kw = dict(props=lineprops)

        # Calling the right zapper
        if zapper_name == self.tools[0]:
            self.zapper = RectangleSelector(
                self.ax, self._rect_callback, useblit=True,
                **rect_span_kw)
        elif zapper_name == self.tools[1]:
            self.zapper = SpanSelector(
                self.ax, self._prof_callback, 'horizontal', useblit=True,
                **rect_span_kw)
        elif zapper_name == self.tools[2]:
            self.zapper = SpanSelector(
                self.ax, self._bin_callback, 'vertical', useblit=True,
                **rect_span_kw)
        elif zapper_name == self.tools[3]:
            self.zapper = self.canvas.mpl_connect('button_press_event',
                                                  self._click_callback)
        elif zapper_name == self.tools[4]:
            self.zapper = PolygonSelector(
                self.ax, self._poly_callback, useblit=True,
                **poly_kw)
        elif zapper_name == self.tools[5]:
            self.zapper = LassoSelector(
                self.ax, self._lasso_callback, useblit=True,
                **lasso_kw)
        else:
            self.zapper = None
            _log.warning(
                "---%s selector has not been developed yet---"
                % zapper_name)

    def _rect_callback(self, eventClick, eventRelease):
        """
        Callback for rectangle zapper

        Args:
            eventClick: mouse event
            eventRelease: mouse event
        """
        # Catching event positions
        x1, y1 = eventClick.xdata, eventClick.ydata,
        x2, y2 = eventRelease.xdata, eventRelease.ydata
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        # Define mask
        mask = ((self.xdata >= xmin) & (self.xdata <= xmax) &
                (self.ydata >= ymin) & (self.ydata <= ymax))
        # return mask
        self._merge_n_refresh(mask)

    def _prof_callback(self, xmin, xmax):
        """
        Callback for profile zapper

        Args:
            xmin: mouse event
            xmax: mouse event

        Returns:
            masked array of the selected points, 1D boolean numpy array
        """
        mask = (self.xdata >= xmin) & (self.xdata <= xmax)
        # return mask
        self._merge_n_refresh(mask)

    def _bin_callback(self, ymin, ymax):
        """
        Callback for bin zapper

        Args:
            ymin: mouse event
            ymax: mouse event

        Returns:
            masked array of the selected points, 1D boolean numpy array
        """
        mask = (self.ydata >= ymin) & (self.ydata <= ymax)
        # return mask
        self._merge_n_refresh(mask)

    def _click_callback(self, evt):
        """
        Callback for click zapper

        Args:
            evt: mouse event

        Returns:
            masked array of the selected points, 2D boolean numpy array
        """
        mask = np.zeros(self.xdata.shape, dtype=bool)
        # normalising distances
        xmax = self.xdata.max()
        xmin = self.xdata.min()
        ymax = self.ydata.max()
        ymin = self.ydata.min()
        xdataNorm = (self.xdata[:] - xmin) / (xmax - xmin)
        ydataNorm = (self.ydata[:] - ymin) / (ymax - ymin)
        xClicked = (evt.xdata - xmin) / (xmax - xmin)
        yClicked = (evt.ydata - ymin) / (ymax - ymin)
        # find index of the closest points
        x = xdataNorm - xClicked
        y = ydataNorm - yClicked
        distance = np.hypot(x, y)
        mask[distance.argmin()] = 1
        # return mask
        self._merge_n_refresh(mask)

    def _poly_callback(self, verts):
        """
        Callback for polygon zapper

        Args:
            verts: polygon vertices, list of vectors (vector = [pt1, pt2])

        Returns:
            masked array of the selected points, 2D boolean numpy array
        """
        xys = np.hstack((self.xdata.flatten()[:, np.newaxis],
                         self.ydata.flatten()[:, np.newaxis]))
        mask = points_inside_poly(xys, verts)
        mask.shape = self.xdata.shape
        # return mask
        self._merge_n_refresh(mask)
        # FIXME: this quick fix for the disappearance of the polygon tool is ugly
        self.set_zapper()

    def _lasso_callback(self, verts):
        """
        Callback for lasso zapper

        Args:
            verts: polygon vertices, list of vectors (vector = [pt1, pt2])

        Returns:
            masked array of the selected points, 2D boolean numpy array
        """
        xys = np.hstack((self.xdata.flatten()[:, np.newaxis],
                         self.ydata.flatten()[:, np.newaxis]))
        mask = points_inside_poly(xys, verts)
        mask.shape = self.xdata.shape
        # return mask
        self._merge_n_refresh(mask)

    def _merge_n_refresh(self, mask):
        # N.B.: this method is app dependent and would need to be changed in a different app
        if not self.toolbar.mode:  # avoid zapping while zooming or panning
            # merge new points
            if self.masking:
                self.mask = np.logical_or(self.mask, mask)
            else:
                self.mask[mask] = False
            self.refresh()
            #  Trigger parent_app.refresh (e.g PatchHcorr)
            if self.parent_app:
                self.parent_app.refresh()

    def _reset_mask(self):
        self.mask = np.zeros(self.xdata.shape, dtype=bool)
        mask = np.zeros(self.xdata.shape, dtype=bool)
        self._merge_n_refresh(mask)


### Generic Model Components ###

