import logging

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QMainWindow
from pycurrents.adcpgui_qt.lib.panel_plotter import CPlotter, make_axes
from pycurrents.adcpgui_qt.lib.miscellaneous import utc_formatting
from pycurrents.adcpgui_qt.lib.plotting_parameters import (
    alias_to_name, COMPARE_PREFIX)
from pycurrents.adcpgui_qt.lib.zappers import TOOL_INFO

# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

# Standard logging
_log = logging.getLogger(__name__)

DISPLAY_FEAT = DisplayFeaturesSingleton()


### Custom Widgets ###
class CustomToolBarPlot(NavigationToolbar):
    # only display the tools and icons we need
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ('Home', 'Pan', 'Zoom', 'Save')]
    # FIXME - this entire zoom paradigm (see home, release_zoom, pan_zoom and
    #         refresh_default_zoomcould be improved with a better
    #         management of the shared axis. It would also enable the use of
    #         "previous zoom" and "next zoom" buttons/functionality

    def __init__(self, canvas, parent):
        """
        Custom tool bar for color plot window.
        Custom class derived from matplotlib NavigationToolBar
        """
        super().__init__(canvas, parent)
        self.canvas = canvas
        self._parent = parent

    def home(self, *args):
        """
        Overrides and adds functionality to the original home callback.

        Args:
            *args: just passes on any arguments
        """
        # Original callback
        super().home(*args)
        # Additional functionality
        # - Reset zoom's limits to the values stored in
        self._parent.draw_over_layer(restore_previous_zoom=False)
        self._parent._restore_default_xlim()
        # Save zoom
        self._parent._save_zoom()
        self.refresh_default_zoom()
        # draw
        self.canvas.draw()
        # log it
        _log.debug("On home")

    def release_zoom(self, event):
        """
        Overrides and adds functionality to the original release_zoom
        callback.

        Args:
            event: matplolib event
        """
        # Original callback
        super().release_zoom(event)
        # Additional callbacks
        self._parent._save_zoom()
        # log it
        _log.debug("On release_zoom")

    def release_pan(self, event):
        """
        Overrides and adds functionality to the original release_pan
        callback.

        Args:
            event: matplolib event
        """
        # Original callback
        super().release_pan(event)
        # Additional callbacks
        self._parent._save_zoom()
        # log it
        _log.debug("On release_pan")

    def mouse_move(self, event):
        """
        Overrides and adds functionality to the original mouse_move callback.

        Args:
            event: matplolib event
        """
        # Original callback
        super().mouse_move(event)
        # Additional callback
        xdata = event.xdata
        if xdata and self._parent:
            # Fix for Ticket 685
            date_str = utc_formatting(xdata, yearbase=self._parent.CD.yearbase)
            self.set_message(
                "Decimal day: %3.2f\nDate in UTC: %s" % (xdata, date_str))

    def refresh_default_zoom(self):
        # FIXME: DO NOT use local (_) lib function from Matplotlib
        self.update()  # new call to clear out views
        self._update_view()


class CustomToolBarZapper(CustomToolBarPlot):
    def __init__(self, canvas, widgets_to_hide, parent):
        """
        Custom tool bar for zapper window.
        Custom class derived from matplotlib CustomToolBarPlot

        Args:
            canvas: Matplotlib canvas
            widgets_to_hide: list of PySide6 or PyQt5 widgets to hide
            parent: PySide6 or PyQt5 parent widget
        """
        super().__init__(canvas, parent)
        self.widgets_to_hide = widgets_to_hide

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
                0.98, 0.98, msg,
                horizontalalignment='right',
                verticalalignment='top',
                color='r', fontweight='bold')
            self._parent.canvas.draw()
        except AttributeError:
            pass


### Color Plot Window ###
class GenericColorPlotWindow(QMainWindow):
    def __init__(self, CD, parent=None):
        """
        Generic color plot window builder.
        Custom class derived from QMainWindow.

        Args:
            CD: codas database, CData object (see ../model)
            parent: parent widget, QWidget
        """
        super().__init__(parent)
        # Attributes
        self.CD = CD
        self.zoom_list = []

    def draw_color_plot(self, new_axis=False, restore_previous_zoom=False,
                        draw_on_all_pcolor=False):
        """
        Draws the panels' color plots, method.

        Args:
            new_axis: if True, generates new axdict and CP attr., bool.
            restore_previous_zoom: if True, zooms back to previous zoom, bool.
            draw_on_all_pcolor: if True, draw staged edits on all pcolor layers
        """
        # Dynamic attributes definition (i.e. axdict and CP)
        if new_axis:
            self.remake_axes()
        # Propagate potential changes in DISPLAY_FEAT
        # FIXME: this block could go in communication_tools as CP could be
        #        considered as a "model" here
        for alias in DISPLAY_FEAT.shared_yaxis_aliases:
            name = alias_to_name(alias)
            if self.CP.clims[name] != DISPLAY_FEAT.vel_range:
                self.CP.clims[name] = DISPLAY_FEAT.vel_range
        # FIXME: this block looks a lot like an ugly patch...me no likie
        if DISPLAY_FEAT.mode == 'compare':
            if self.CP.clims[COMPARE_PREFIX] != DISPLAY_FEAT.diff_range:
                        self.CP.clims[COMPARE_PREFIX] = DISPLAY_FEAT.diff_range
        # Draw panels
        for axnum in range(self.num_axes):
            alias = self.chosenVariables[axnum]
            CD = self._get_CD(axnum)
            if CD.data is not None:
                self.CP.draw(CD, axnum, alias,
                             draw_on_all_pcolor=draw_on_all_pcolor)
            else:
                self.CP.draw(CD, axnum, 'clear')
        self.set_corner_text()
        # update navigation tool bar default zoom
        self.toolbar.refresh_default_zoom()
        # make visible
        if not self.isVisible():
            self.setVisible(True)
        # restore previous zoom
        if restore_previous_zoom:
            self._restore_previous_zoom()
        # or save new zoom limits
        else:
            self._save_zoom()

    def draw_over_layer(self, restore_previous_zoom=True):
        """
        Draws the panels' over layers (i.e. speed and heading), method

        Args:
            restore_previous_zoom: if True, zooms back to previous zoom, bool.
        """
        # Draw panels
        for axnum in range(self.num_axes):
            alias = self.chosenVariables[axnum]
            CD = self._get_CD(axnum)
            if CD.data is not None:
                tax = self.axdict['twinx'][axnum]
                trax = self.axdict['triplex'][axnum]
                self.CP.draw_over_layer(alias, tax, trax, CD)
        # Add legend
        self.set_corner_text()
        # Restore previous zoom
        if restore_previous_zoom:
            self._restore_previous_zoom()

    def utc_date_format(self):
        """
        Format X axis' ticks to UTC time stamps
        """
        axnum = 0  # FIXME - assuming all CDs share the same X axis features
        CD = self._get_CD(axnum)
        self.CP._format_xaxis(DISPLAY_FEAT.utc_date, CD.xlim, CD.yearbase)
        self._restore_previous_zoom()

    def set_corner_text(self):
        """
        Writes legend in bottom corners for both speed and heading over-plots
        """
        # update text of overlayers
        self.CP._del_text_over_layer()
        if DISPLAY_FEAT.show_spd:
            self.CP._add_speed_text()
        if DISPLAY_FEAT.show_heading:
            self.CP._add_heading_text()

    def remake_axes(self):
        """
        Regenerates the axdict (dict. of panels' matplotlib axis)
        """
        self.figure.clear()
        # Re-define attr.
        self.axdict = make_axes(fig=self.figure,
                                ax_list=self.chosenVariables)
        self.CP = CPlotter(self.figure, self.axdict)

    # Local lib
    def _save_zoom(self):
        self.zoom_list = []
        for axnum in range(self.num_axes):
            ax = self.axdict['pcolor'][axnum]
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            self.zoom_list.append([xlim, ylim])

    def _restore_previous_zoom(self):
        for axnum in range(self.num_axes):
            ax = self.axdict['pcolor'][axnum]
            xlim = self.zoom_list[axnum][0]
            ylim = self.zoom_list[axnum][1]
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)

    def _restore_default_xlim(self):
        axnum = 0  # FIXME - assuming all CDs share the same X axis features
        CD = self._get_CD(axnum)
        self.axdict['pcolor'][-1].set_xlim(CD.xlim)

    def _get_CD(self, axnum):
        """
        Resolve compatibility bet ween CDataCompareMode
        and others CData classes

        Args:
            axnum: axis number, int.

        Returns: CData* object
        """
        if DISPLAY_FEAT.mode == 'compare':
            sonar = self.chosenSonars[axnum]
            CD = self.CD[sonar]
        else:
            CD = self.CD
        return CD

    # Dynamic attributes
    def _get_variables(self):
        return DISPLAY_FEAT.axes

    def _get_num_axes(self):
        return DISPLAY_FEAT.num_axes

    def _get_sonars(self):
        return DISPLAY_FEAT.sonars


    chosenVariables = property(_get_variables)
    num_axes = property(_get_num_axes)
    chosenSonars = property(_get_sonars)

