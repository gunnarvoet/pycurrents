# Standard Logging
import logging
from packaging import version
import numpy as np

import matplotlib as mpl
from matplotlib.backend_bases import KeyEvent
from matplotlib.widgets import SpanSelector, RectangleSelector, PolygonSelector
from matplotlib.widgets import LassoSelector

from pycurrents.adcpgui_qt.lib.miscellaneous import reset_artist
from pycurrents.num.utility import points_inside_poly  # BREADCRUMB: common lib

# Standard logging
_log = logging.getLogger(__name__)

# Global var
TOOL_NAMES = ["Rectangle (R)", "Horizontal span (H)", "Vertical span (Z)", "One click (O)",
              "Polygon (P)", "Lasso (L)"]
TOOL_INFO = {
    TOOL_NAMES[0]: 'Instructions - Click and drag a rectangle',
    TOOL_NAMES[1]: 'Instructions - Click and drag horizontally',
    TOOL_NAMES[2]: 'Instructions - Click and drag vertically',
    TOOL_NAMES[3]: 'Instructions - Click a bin/point',
    TOOL_NAMES[4]: 'Instructions - Click polygon points: last click = first point',
    TOOL_NAMES[5]: 'Instructions - Click and hold: draw, then lift',
    "seabed": 'Instructions - Click along seabed, double-click to finish'}

# N.B.: list's order matters here (also see ../model/display_features_models.py)


class ZapperMaker:
    # FIXME: turn into proper factory class
    def __init__(self, zapper_name, decorator, eax, canvas, CD):
        """
        Make plot zapper

        Args:
            zapper_name: str.
            decorator: decorator function wrapping zapper's callback
                       (see zapper_plot_window.py for examples)
            eax: staged edit layer, Matplotlib's Axis object
            canvas: canvas in which mouse events are caught,
                    Matplotlib's Canvas object
            CD: codas database, CD object (see codas_data_models.py)
        """
        # Attributes
        self.CD = CD
        self.eax = eax
        self.canvas = canvas
        self.artist = None
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
        if zapper_name == TOOL_NAMES[0]:
            def callback(evt0, evt1):
                return decorator((evt0, evt1), self._rect_callback)
            self.zapper = RectangleSelector(
                self.eax, callback, useblit=True,
                **rect_span_kw)
        elif zapper_name == TOOL_NAMES[1]:
            self.var = self.CD.Xc[:, 0]
            def callback(evt0, evt1):
                return decorator((evt0, evt1), self._prof_callback)
            self.zapper = SpanSelector(
                self.eax, callback, 'horizontal', useblit=True,
                **rect_span_kw)
        elif zapper_name == 'reset':
            self.var = self.CD.Xc[:, 0]
            def callback(evt0, evt1):
                return decorator((evt0, evt1), self._reset_callback)
            self.zapper = SpanSelector(
                self.eax, callback, 'horizontal', useblit=True,
                **rect_span_kw)
        elif zapper_name == TOOL_NAMES[2]:
            self.var = self.CD.Yc[0, :]
            def callback(evt0, evt1):
                return decorator((evt0, evt1), self._bin_callback)
            self.zapper = SpanSelector(
                self.eax, callback, 'vertical', useblit=True,
                **rect_span_kw)
        elif zapper_name == TOOL_NAMES[3]:
            def callback(evt):
                return decorator(evt, self._click_callback)
            self.zapper = self.canvas.mpl_connect('button_press_event',
                                                  callback)
        elif zapper_name == TOOL_NAMES[4]:
            def callback(evt):
                return decorator(evt, self._poly_callback)
            self.zapper = PolygonSelector(
                self.eax, callback, useblit=True,
                **poly_kw)
        elif zapper_name == TOOL_NAMES[5]:
            def callback(evt):
                return decorator(evt, self._lasso_callback)
            self.zapper = LassoSelector(
                self.eax, callback, useblit=True, **lasso_kw)
        elif zapper_name == 'bottom':
            def callback(evt):
                return decorator(evt, self._bottom_callback)
            self.zapper = self.canvas.mpl_connect('button_press_event',
                                                  callback)
            # Specific zapper attributes
            self.xs, self.ys = [], []
            self.previous_point = None
            self.mabs = []  # max amplitude bins
        else:
            self.zapper = None
            _log.warning(
                "---%s selector tool has not been developed yet---"
                % zapper_name)

    def get_zapper(self):
        return self.zapper

    def get_artist(self):
        return self.artist

    def _rect_callback(self, eventClick, eventRelease):
        """
        Callback for rectangle zapper

        Args:
            eventClick: mouse event
            eventRelease: mouse event

        Returns:
            masked array of the selected points, 2D boolean numpy array
        """
        # Catching event positions
        x1, y1 = eventClick.xdata, eventClick.ydata,
        x2, y2 = eventRelease.xdata, eventRelease.ydata
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        # Define mask
        mask = ((self.CD.Xc >= xmin) & (self.CD.Xc <= xmax) &
                (self.CD.Yc >= ymin) & (self.CD.Yc <= ymax))
        return mask

    def _prof_callback(self, xmin, xmax):
        """
        Callback for profile zapper

        Args:
            xmin: mouse event
            xmax: mouse event

        Returns:
            masked array of the selected points, 1D boolean numpy array
        """
        mask = (self.CD.Xc >= xmin) & (self.CD.Xc <= xmax)
        return mask

    def _reset_callback(self, xmin, xmax):
        """
        Callback for reset zapper

        Args:
            xmin: mouse event
            xmax: mouse event

        Returns:
            xrange: data range
            mask: masked array of the selected points, 1D boolean numpy array
        """
        x_range = [xmin, xmax]
        mask = (self.CD.Xc >= xmin) & (self.CD.Xc <= xmax)
        return x_range, mask

    def _bin_callback(self, ymin, ymax):
        """
        Callback for bin zapper

        Args:
            ymin: mouse event
            ymax: mouse event

        Returns:
            masked array of the selected points, 1D boolean numpy array
        """
        mask = (self.CD.Yc >= ymin) & (self.CD.Yc <= ymax)
        return mask

    def _click_callback(self, evt):
        """
        Callback for click zapper

        Args:
            evt: mouse event

        Returns:
            masked array of the selected points, 2D boolean numpy array
        """
        mask = np.zeros(self.CD.Xc.shape)
        xClicked = evt.xdata
        yClicked = evt.ydata
        minInd = self.CD.argnearest_centered_index((xClicked, yClicked))
        mask[minInd] = 1
        return mask

    def _poly_callback(self, verts):
        """
        Callback for polygon zapper

        Args:
            verts: polygon vertices, list of vectors (vector = [pt1, pt2])

        Returns:
            masked array of the selected points, 2D boolean numpy array
        """
        xys = np.hstack((self.CD.Xc.flatten()[:, np.newaxis],
                         self.CD.Yc.flatten()[:, np.newaxis]))
        mask = points_inside_poly(xys, verts)
        mask.shape = self.CD.Xc.shape
        # The PolygonSelector is reset with the escape key.  There is no public
        # function to do this, so we have to simulate *both* the key_press and
        # the key_release.
        self.zapper.on_key_press(KeyEvent("key_press_event", self.canvas, "escape", x=0,  y=0))
        self.zapper.on_key_release(KeyEvent("key_release_event", self.canvas, "escape", x=0,  y=0))

        return mask

    def _lasso_callback(self, verts):
        """
        Callback for lasso zapper

        Args:
            verts: polygon vertices, list of vectors (vector = [pt1, pt2])

        Returns:
            masked array of the selected points, 2D boolean numpy array
        """
        xys = np.hstack((self.CD.Xc.flatten()[:, np.newaxis],
                         self.CD.Yc.flatten()[:, np.newaxis]))
        mask = points_inside_poly(xys, verts)
        mask.shape = self.CD.Xc.shape
        return mask

    def _bottom_callback(self, evt):
        """
        Callback for bottom zapper

        Args:
            evt: mouse event

        Returns:
            either None, None or
            ubb: list of user-identified bottom bins
        """
        # Finding closest point in coordinates
        xClicked = evt.xdata
        yClicked = evt.ydata
        minInd = self.CD.argnearest_centered_index(
            (xClicked, yClicked), use_masked_coordinates=False)
        newX = float(self.CD.Xc[minInd])
        newY = float(self.CD.Yc[minInd])
        # Remove artist
        self.artist = reset_artist(self.artist)
        # When double clicked
        if self.previous_point == [newX, newY]:
            # Sort so that time is increasing, left to right
            ii = np.argsort(self.xs)
            # Build up polygon vertices
            self.xs = np.asarray(self.xs)[ii]
            self.ys = np.asarray(self.ys)[ii]
            xyverts = []
            for x, y in zip(self.xs, self.ys):
                xyverts.append((float(x), float(y)))
            # Add bottom left point
            leftPoint = [(float(self.xs[0]),
                          float(self.CD.Yc[self.CD.Xc == self.xs[0]][-1]))]
            xyverts = leftPoint + xyverts
            # Add bottom right point
            rightPoint = [(float(self.xs[-1]),
                           float(self.CD.Yc[self.CD.Xc == self.xs[-1]][-1]))]
            xyverts += rightPoint
            # Find points below curve
            xys = np.hstack((self.CD.Xc.flatten()[:, np.newaxis],
                             self.CD.Yc.flatten()[:, np.newaxis]))
            mask = points_inside_poly(xys, xyverts)
            mask.shape = self.CD.Xc.shape
            # Find user's bottom bin (aka ubb)
            ubb = np.ma.masked_equal((~mask).sum(axis=1).astype(int),
                                     self.CD.Xc.shape[1])
            ubb -= 1  # correction to python indexes (starting at 0)
            # Flush points
            self.xs, self.ys = [], []
            self.previous_point = None
            return ubb
        else:
            self.previous_point = [newX, newY]
            self.xs.append(newX)
            self.ys.append(newY)
            self.artist = self.eax.plot(
                self.xs, self.ys,
                linestyle='-', color='black', alpha=0.5,
                marker='o', markersize=6, markerfacecolor='w',
                markeredgewidth=1.5, markeredgecolor='k')
            return None, None


# Local lib
def _test_decorator(evt, func, ax, canvas, CD):
    if isinstance(evt, tuple):
        mask = func(evt[0], evt[1])
    else:
        mask = func(evt)
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    ax.plot(CD.Xc[mask], CD.Yc[mask],
            'r.', ms=2, alpha=0.5)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    canvas.draw()
