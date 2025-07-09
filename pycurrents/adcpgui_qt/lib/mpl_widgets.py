import numpy as np

# Standard Logging
import logging

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor, MultiCursor
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QSizePolicy
from pycurrents.adcpgui_qt.lib.panel_plotter import make_axes

_log = logging.getLogger(__name__)

_pre36 = mpl.__version_info__ < (3, 6)

### Custom widgets ###
class GenericPlotMplCanvas(FigureCanvas):
    def __init__(self, fig, parent=None):
        """
        Generic plotting canvas for Apps.
        inheriting from Matplotlib's FigureCanvas

        Args:
            fig: Matplotlib's Figure object
            parent: PySide6 or PyQt5 parent widget
        """
        # Inheritance
        FigureCanvas.__init__(self, fig)
        # Attributes
        self.figure = fig
        self.setParent(parent)
        # Style
        self.figure.set_facecolor('gainsboro')
        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def test_plot(self, time_array):
        pass


class PlotMplCanvas(FigureCanvas):
    def __init__(self, ax_list, parent=None):
        """
        Custom Matplotlib/Qt canvas for panel plot(s)

        Args:
            ax_list: list of variables aliases, list of str.
            parent: parent widget, QtWidget
        """
        # TODO: modify make_axes to take advantage of constrained layout.
        #   This will require experimentation; it might not be possible to
        #   get precisely the desired result.
        fig = Figure()
        # Inheritance
        FigureCanvas.__init__(self, fig)
        # Attributes
        self.figure = fig
        self.numaxes = len(ax_list)
        self.axdict = make_axes(fig=self.figure, ax_list=ax_list)
        self.setParent(parent)
        # Style
        self.figure.set_facecolor('gainsboro')
        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def test_plot(self, time_array):
        pass


class TopoMplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        """
        Custom Matplotlib/Qt canvas for topo. plot

        Args:
            parent: parent widget, QtWidget
        """

        # We could use "constrained" for 22.04 (Python 3.5.1), but it has a couple
        # conspicuous redraws when the window is updated, so let's leave it out.
        layout_kw = None if _pre36 else "compressed"
        fig = Figure(layout=layout_kw)
        # Inheritance
        FigureCanvas.__init__(self, fig)
        # Attributes
        self.figure = fig
        self.topax = self.figure.add_subplot(111)
        self.setParent(parent)
        # Style
        self.figure.set_facecolor('gainsboro')
        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def test_plot(self):
        pass


class ZapperMplCanvas(FigureCanvas):
    def __init__(self, ax, parent=None):
        """
        Custom Matplotlib/Qt canvas for zapper plot(s)

        Args:
            ax: variables aliases, str.
                see adcpgui_qt.lib.plotting_parameters.py
            parent: parent widget, QtWidget
        """
        fig = Figure()
        # Inheritance
        FigureCanvas.__init__(self, fig)
        # Attributes
        self.figure = fig
        self.axdict = make_axes(fig=self.figure, ax_list=[ax])
        self.setParent(parent)
        # Style
        self.figure.set_facecolor('gainsboro')
        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def test_plot(self, time_array):
        pass


class CustomMultiCursor(MultiCursor):
    def __init__(self, time, xmap, ymap, connectedCanvas, canvas, axes,
                 color='r', lw=1):
        """
        Custom class inheriting from matplotlib.widgets.MultiCursor

        Draws vertical crosshair cursors on all given panels (x,y = time,value)
        In UHDAS GUI, this panels correspond to the 'pcolor' ones

        Calls back to the connected figure by drawing a cross cursor at the
        location associated the vertical cursors' timestamp.
        In UHDAS, the connected figure is the topographic one and
        the associated location correspond to the ship location

        Args:
            time: timestamps, list or 1d array of n elements
            xmap: x coordinates of the connected figure,
                  list or 1d array of n elements
            ymap: y coordinates of the connected figure,
                  list or 1d array of n elements
            connectedCanvas:  connected canvas, custom matplotlib/Qt canvas
            canvas: panels plot canvas, matplotlib FigureCanvas?Agg object
            axes: dictionary of AxesSubplot of the panel plot, object created
                  by pycurrents.adcpgui_qt.lib.panel_plotter.make_axes
            color: cursors' color, standard color string for mpl
            lw: line width, standard line width string for mpl
        """
        MultiCursor.__init__(self, canvas, axes, useblit=True,
                             color=color, lw=lw)
        self.t = time
        # In onmove, we can't use the new mpl check that the event is in
        # one of the listed axes because we have stacked axes with the same
        # position and the same time axis--e.g., a pcolormesh axes and another
        # for ship's speed.  The axes list includes only the pcolormesh axes,
        # but the event might have been recorded as coming from the overlying
        # speed axes.  Therefore we check the positions instead of the axes
        # objects.
        self.positions = [tuple(ax.get_position().extents) for ax in axes]
        self.connected_x = xmap
        self.connected_y = ymap

        self.connected_canvas = connectedCanvas
        self.connected_fig = connectedCanvas.figure
        self.connected_ax = connectedCanvas.topax

        self.connected_background = connectedCanvas.copy_from_bbox(
            self.connected_ax.bbox)
        self.connected_hline = self.connected_ax.axhline(
            visible=False, color=color, lw=lw)
        self.connected_hline.set_animated(True)
        self.connected_vline = self.connected_ax.axvline(
            visible=False, color=color, lw=lw)
        self.connected_vline.set_animated(True)

        self.connected_fig.canvas.mpl_connect('draw_event', self.clear_connected)

    def clear_connected(self, event):
        self.connected_background = self.connected_canvas.copy_from_bbox(
            self.connected_ax.bbox)

    def onmove(self, event):
        """
        Inherited method from MultiCursor.onmove with additional functionality

        Additional functionality: draws cursor on connected figure at location
        associated with timestamp come from mouse position

        Args:
            event: mouse event
        """
        _log.debug("onmove %s", event)
        if event.button == 1:  # Do not show if left click is held
            # This allows a clean blit animation with the zappers.
            return
        try:
            # modified from MultiCursor.onmove(self, event)
            if (self.ignore(event)
                or event.inaxes is None
                or not event.canvas.widgetlock.available(self)):
                return
            source = tuple(event.inaxes.get_position().extents)
            if source not in self.positions:
                return
            for line in self.vlines:
                line.set_xdata((event.xdata, event.xdata))
                line.set_visible(self.visible and self.vertOn)
            for line in self.hlines:
                line.set_ydata((event.ydata, event.ydata))
                line.set_visible(self.visible and self.horizOn)
            if self.visible and (self.vertOn or self.horizOn):
                self._update()
                _log.debug("updated")
            # end of modified MultiCursor.onmove

            if not event.inaxes == self.connected_ax:
                t = event.xdata
                if t is not None:
                    new_x = np.interp(t, self.t, self.connected_x, left=np.nan, right=np.nan)
                    new_y = np.interp(t, self.t, self.connected_y, left=np.nan, right=np.nan)
                    if np.isfinite(new_x):
                        # mpl >= 3.9 requires sequences when setting line data.
                        new_x, new_y = (new_x,), (new_y,)
                        self.connected_hline.set_visible(True)
                        self.connected_vline.set_visible(True)
                        self.connected_hline.set_ydata(new_y)
                        self.connected_vline.set_xdata(new_x)
                        self.connected_canvas.restore_region(
                            self.connected_background)
                        self.connected_ax.draw_artist(self.connected_hline)
                        self.connected_ax.draw_artist(self.connected_vline)
                        self.connected_canvas.blit(self.connected_ax.bbox)
                    else:
                        self.connected_canvas.restore_region(
                            self.connected_background)
                        self.connected_canvas.blit(self.connected_ax.bbox)

        except AttributeError as err:
            _log.debug("in onmove %s", err)
            # draw_artist can only be used after an initial draw which
            # caches the render
            pass

    def _update(self):
        if self.useblit:
            for canvas, info in self._canvas_infos.items():
                if info["background"]:
                    canvas.restore_region(info["background"])
            if self.vertOn:
                for ax, line in zip(self.axes, self.vlines):
                    ax.draw_artist(line)
            if self.horizOn:
                for ax, line in zip(self.axes, self.hlines):
                    ax.draw_artist(line)
            for canvas in self._canvas_infos:
                canvas.blit()
        else:
            for canvas in self._canvas_infos:
                canvas.draw_idle()


class TXYCursors:
    def __init__(self, t, xmap, ymap, connectedCanvas, canvasNaxes,
                 color='r', lw=1):
        """
        Wrapper class for CustomMultiCursor and associated connected figures
        and callbacks

        Args:
            t: timestamps, list or 1d array of n elements
            xmap: x coordinates of the connected figure,
                        list or 1d array of n elements
            ymap: y coordinates of the connected figure,
                        list or 1d array of n elements
            connectedCanvas: connected canvas, custom matplotlib/Qt canvas
            canvasNaxes: list of [canvas, axes] pairs,
                         Qt canvas objects and AxesSubplot matplotlib objects
            color: cursors' color, standard color string for mpl
            lw: line width, standard line width string for mpl
        """
        self.color = color
        self.lw = lw
        self.topoCursor = Cursor(connectedCanvas.topax,
                                 useblit=True, color=color, lw=lw)
        self.topoCanvas = connectedCanvas
        self.topoFig = connectedCanvas.figure
        self.nb_multicursors = len(canvasNaxes)
        set_plot_multicursors(
            self, t, xmap, ymap, connectedCanvas, canvasNaxes)

    def update_data(self, new_t, new_xmap, new_ymap):
        """
        Updates data for the CustomMultiCursor in the panels plot
        when UHDAS GUI steps in time or updates

        Args:
            new_t: timestamps, list or 1d array of n elements
            new_xmap: x coordinates of the connected figure,
                        list or 1d array of n elements
            new_ymap: y coordinates of the connected figure,
                        list or 1d array of n elements
        """
        _log.debug("class TXYCursors - In update_data")
        for ii in range(self.nb_multicursors):
            multiCursor = getattr(self, 'multiCursor'+str(ii))
            multiCursor.t = new_t
            multiCursor.connected_x = new_xmap
            multiCursor.connected_y = new_ymap

    def update_topocursor(self, ax):
        """
        Reloads cursor on map when UHDAS GUI steps in time or updates

        Args:
            ax: connected ax, matplotlib AxesSubplot object

        """
        _log.debug("class TXYCursors - In update_topocursor")
        # remove topo Cursor
        del self.topoCursor

        # re-define
        self.topoCursor = Cursor(
            ax, useblit=True, color=self.color, lw=self.lw)
        for ii in range(self.nb_multicursors):
            multiCursor = getattr(self, 'multiCursor'+str(ii))
            multiCursor.connected_ax = ax
            multiCursor.connected_hline = ax.axhline(
                visible=False, color=self.color, lw=self.lw)
            multiCursor.connected_hline.set_animated(True)
            multiCursor.connected_vline = ax.axvline(
                visible=False, color=self.color, lw=self.lw)
            multiCursor.connected_vline.set_animated(True)


    def update_plotcursors(self, txycursors, canvasNaxes):
        _log.debug("class TXYCursors - In plotcursors")
        self.nb_multicursors = len(canvasNaxes)
        xmap = self.multiCursor0.connected_x.copy()
        ymap = self.multiCursor0.connected_y.copy()
        t = self.multiCursor0.t.copy()
        self.multiCursor0.connected_hline.set_visible(False)
        self.multiCursor0.connected_vline.set_visible(False)
        for ii in range(self.nb_multicursors):
            try:
                multiC = getattr(txycursors, 'multiCursor'+str(ii))
                del multiC
            except AttributeError:
                _log.debug(
                    "No attribute 'multiCursor{0}' in TXYCursors".format(ii))
                pass
        set_plot_multicursors(txycursors, t, xmap, ymap,
                              self.topoCanvas, canvasNaxes)

    def set_visible(self, flag):
        _log.debug("class TXYCursors - In set_visible")
        flag = float(flag)
        for ii in range(self.nb_multicursors):
            multiC = getattr(self, 'multiCursor'+str(ii))
            for line in multiC.vlines + multiC.hlines:
                line.set_alpha(flag)
        self.topoCursor.lineh.set_alpha(flag)
        self.topoCursor.linev.set_alpha(flag)
        self.multiCursor0.connected_hline.set_alpha(flag)
        self.multiCursor0.connected_vline.set_alpha(flag)


### Lib ###
def set_plot_multicursors(txycursors, t, xmap, ymap,
                          connectedCanvas, canvasNaxes):
    """
    Set connected multicursors between topo. map and panel(s)

    Args:
        txycursors: TXYCursors object
        t: time steps, list of floats
        xmap: x coordinates, list of floats
        ymap: y coordinates, list of floats
        connectedCanvas: connected canvas, custom matplotlib/Qt canvas
        canvasNaxes: list of [canvas, axes] pairs,
                     Qt canvas objects and AxesSubplot matplotlib objects
    """
    _log.debug("In set_plot_multicursors")
    for ii, aNc in enumerate(canvasNaxes):
        canvas = aNc[0]
        axes = aNc[1]
        multiCursor = CustomMultiCursor(t, xmap, ymap, connectedCanvas, canvas,
                                        tuple(axes), color='r', lw=1)
        setattr(txycursors, 'multiCursor'+str(ii), multiCursor)
