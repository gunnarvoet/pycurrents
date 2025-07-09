#!/usr/bin/env python

"""
    Time range selector widget for picking time ranges corresponding
    to latitude or longitude sections, etc.

    This module includes a class that can be used with or without
    subclassing in a gui-independent fashion, or that can be
    subclassed to be embedded in a specific gui application.

    Data and selections are managed with an instance of the
    RangeSet class that is independent of the TxySelector widget.

"""

## used in quick_web.py

import numpy as np

from matplotlib.widgets import Button, RadioButtons
from matplotlib.ticker import MaxNLocator, ScalarFormatter
from matplotlib.transforms import blended_transform_factory
from matplotlib.patches import Rectangle

from pycurrents.num import rangeslice

class StateSelector:
    """
    Simulation of radio buttons with mpl buttons.

    It is presently hardwired as to location and dimensions.
    """
    def __init__(self, fig, labels, callback):
        self._fig = fig
        self.labels = labels
        self.callback = callback
        self._state = 0
        self.axes = []
        self.buttons = []
        n = len(self.labels)
        lefts = np.linspace(0.3, 0.7, n, endpoint=False)
        width = (lefts[1] - lefts[0]) * 0.9
        lefts += (width * 0.05)

        self._fig.subplots_adjust(bottom=0.15)

        for i, (left, lab) in enumerate(zip(lefts, labels)):
            ax = fig.add_axes([left, 0.01, width, 0.05])
            self.axes.append(ax)
            b = Button(ax, lab)
            b.on_clicked(self._onclick)
            self.buttons.append(b)
        self.show_active()

    def _onclick(self, event):
        try:
            i = self.axes.index(event.inaxes)
        except IndexError:
            return False
        self._state = i
        self.show_active()
        self.callback(self.labels[i])

    def show_active(self):
        i = self._state
        for j, b in enumerate(self.buttons):
            if j == i:
                b.label.set_color('green')
            else:
                b.label.set_color('red')
        self._fig.canvas.draw()


class DualSpanSelector:
    """
    Select a min/max range of the x axis of one Axes or the
    y axis of a second Axes.

    This is a modification of the mpl widgets.SpanSelector, with
    a line cursor added.

    """

    def __init__(self, axes, onselect, minspan=None, useblit=True,
                 rectprops=None, lineprops=None,
                 onmove_callback=None,
                 xy_from_t=None):
        """
        Create a span selector in the two Axes instances listed
        in *axes*.  When a selection is made, clear
        the span and call *onselect* with::

            onselect(vmin, vmax)

        If *minspan* is not ``None``, ignore events smaller than *minspan*

        *onmove_callback* is an optional callback that is called on mouse
          move within the span range

        *xy_from_t* is an optional function to calculate x,y
        for a crosshair cursor in the optional third Axes.

        The span rectangle is drawn with *rectprops*; default::
          rectprops = dict(facecolor='red', alpha=0.5)

        When a selection is not underway, the cursor is indicated with
        a line drawn with *lineprops* as a dictionary of properties.

        Set the visible attribute to ``False`` if you want to turn off
        the functionality of the span selector.
        """
        if rectprops is None:
            rectprops = dict(facecolor='red', alpha=0.5)
        if lineprops is None:
            lineprops = dict(color='red')
        self.rectprops = rectprops
        if useblit:
            lineprops['animated'] = True
        self.lineprops = lineprops

        self.axes = None
        self.canvas = None
        self.visible = True
        self.cids=[]

        self.rects = []
        self.lines = []
        self.crosshairs = []
        self.backgrounds = None
        self.pressv = None


        self.onselect = onselect
        self.onmove_callback = onmove_callback
        self.xy_from_t = xy_from_t
        self.useblit = useblit
        self.minspan = minspan

        # Needed when dragging out of axes
        self.buttonDown = False
        self.prev = (0, 0)

        self.new_axes(axes)


    def new_axes(self, axes):
        self.axes = axes
        if self.canvas is not axes[0].figure.canvas:
            for cid in self.cids:
                self.canvas.mpl_disconnect(cid)

            self.canvas = axes[0].figure.canvas

            self.cids.append(self.canvas.mpl_connect(
                                    'motion_notify_event', self.onmove))
            self.cids.append(self.canvas.mpl_connect(
                                    'button_press_event', self.press))
            self.cids.append(self.canvas.mpl_connect(
                                    'button_release_event', self.release))
            self.cids.append(self.canvas.mpl_connect(
                                    'draw_event', self.update_background))

        self.rects.extend(self.make_rects(0, 0, visible=False,
                                                        **self.rectprops))
        self.lines.extend(self.make_lines(**self.lineprops))

        if self.xy_from_t is not None:
            self.crosshairs.extend(self.make_crosshairs(**self.lineprops))

        if not self.useblit:
            for ax, rect in zip(self.axes, self.rects):
                ax.add_patch(rect)
            # lines are already there.

    def make_rects(self, pos, thickness, **kw):
        rects = []
        ax = self.axes[0]
        trans = blended_transform_factory(ax.transData, ax.transAxes)
        rects.append( Rectangle( (pos,0), thickness, 1,
                               transform=trans,
                               **kw
                               ))
        ax = self.axes[1]
        trans = blended_transform_factory(ax.transAxes, ax.transData)
        rects.append( Rectangle( (0,pos), 1, thickness,
                               transform=trans,
                               **kw
                               ))
        return rects

    def make_lines(self, **kw):
        lines = []
        lines.append(self.axes[0].axvline(visible=False, **kw))
        lines.append(self.axes[1].axhline(visible=False, **kw))
        return lines

    def make_crosshairs(self, **kw):
        lines = []
        lines.append(self.axes[2].axvline(visible=False, **kw))
        lines.append(self.axes[2].axhline(visible=False, **kw))
        return lines

    def update_background(self, event):
        'force an update of the background'
        if self.useblit:
            self.backgrounds = [self.canvas.copy_from_bbox(ax.bbox)
                                        for ax in self.axes]
        #print "updated backgrounds"

    def ignore(self, event):
        'return ``True`` if *event* should be ignored'
        return  event.inaxes not in self.axes[:2] or not self.visible

    def press(self, event):
        'on button press event'
        if self.ignore(event):
            return
        self.buttonDown = True

        for r in self.rects:
            r.set_visible(self.visible)
        for line in self.lines:
            line.set_visible(False)
        if event.inaxes == self.axes[0]:
            self.pressv = event.xdata
        else:
            self.pressv = event.ydata
        return False


    def release(self, event):
        'on button release event'
        if self.pressv is None or (self.ignore(event) and not self.buttonDown):
            return
        self.buttonDown = False

        for r in self.rects:
            r.set_visible(False)

        self.canvas.draw()

        for line in self.lines:
            line.set_visible(self.visible)

        vmin = self.pressv
        if event.inaxes == self.axes[0]:
            vmax = event.xdata or self.prev[0]
        else:
            vmax = event.ydata or self.prev[1]

        if vmin>vmax: 
            vmin, vmax = vmax, vmin
        span = vmax - vmin
        self.pressv = None
        if self.minspan is not None and span<self.minspan:
            return False

        self.onselect(vmin, vmax)
        return False

    def onmove(self, event):
        'on motion notify event'
        if not self.visible:
            return False
        if event.inaxes not in self.axes[:2]:
            # possible optimization for later:
            #  don't do all this when not needed.
            for line in self.lines + self.crosshairs:
                line.set_visible(False)
            self.update()
            return False
        x, y = event.xdata, event.ydata
        self.prev = x, y
        if event.inaxes == self.axes[0]:
            v = x
        else:
            v = y
        if self.xy_from_t is not None:
            xx, yy = self.xy_from_t(v)
            self.crosshairs[0].set_visible(self.visible)
            self.crosshairs[1].set_visible(self.visible)
            self.crosshairs[0].set_xdata([xx, xx])
            self.crosshairs[1].set_ydata([yy, yy])

        if self.pressv is None:
            self.lines[0].set_visible(self.visible)
            self.lines[1].set_visible(self.visible)
            self.lines[0].set_xdata([v, v])
            self.lines[1].set_ydata([v, v])
            self.update()
            return False

        minv, maxv = v, self.pressv
        if minv>maxv: 
            minv, maxv = maxv, minv

        self.rects[0].set_x(minv)
        self.rects[0].set_width(maxv-minv)
        self.rects[1].set_y(minv)
        self.rects[1].set_height(maxv-minv)


        if self.onmove_callback is not None:
            vmin = self.pressv
            if event.inaxes == self.axes[0]:
                vmax = event.xdata or self.prev[0]
            else:
                vmax = event.ydata or self.prev[1]

            if vmin>vmax: 
                vmin, vmax = vmax, vmin
            self.onmove_callback(vmin, vmax)

        self.update()
        return False

    def update(self):
        """
        Draw using newfangled blit or oldfangled draw depending
        on *useblit*
        """
        if self.useblit:
            if self.backgrounds is not None:
                for background in self.backgrounds:
                    self.canvas.restore_region(background)
            for ax, rect, line in zip(self.axes, self.rects, self.lines):
                ax.draw_artist(rect)
                ax.draw_artist(line)
                self.canvas.blit(ax.bbox)
            if self.xy_from_t is not None:
                for line in self.crosshairs:
                    self.axes[2].draw_artist(line)
                self.canvas.blit(self.axes[2].bbox)
        else:
            self.canvas.draw_idle()

        return False


class CouplerCallbacks:
    """
    Generate callbacks for axis-coupling between a pair of Axes.
    This is just a helper for the Coupler class.
    """
    def __init__(self, ax, auto=False):
        self.ax = ax
        self.auto = auto

    def on_x_y(self, ax):
        self.ax.set_ylim(ax.viewLim.intervalx, emit=False, auto=self.auto)

    def on_y_x(self, ax):
        self.ax.set_xlim(ax.viewLim.intervaly, emit=False, auto=self.auto)

    def on_x_x(self, ax):
        self.ax.set_xlim(ax.viewLim.intervalx, emit=False, auto=self.auto)

    def on_y_y(self, ax):
        self.ax.set_ylim(ax.viewLim.intervaly, emit=False, auto=self.auto)

class Coupler:
    """
    Facilitate connecting Axes.  This can duplicate the effect of
    sharex, sharey, but it can also couple the x axis of one Axes
    to the y axis of another, etc.

    One instance is needed for each pair of Axes to be connected.
    No more than two methods of a given instance should be called.

    The present version is extremely simple and has no error checking
    or means of disconnecting.  If warranted, refinements may be added.
    """
    def __init__(self, ax1, ax2, auto1=False, auto2=False):
        """
        auto1 and auto2 control autoscaling on the targets ax1 and ax2,
        respectively.  They will normally be left as False.
        """
        self.ax1 = ax1
        self.ax2 = ax2
        self.cb1 = CouplerCallbacks(ax1, auto=auto2)
        self.cb2 = CouplerCallbacks(ax2, auto=auto1)

    def xx(self):
        self.ax1.callbacks.connect('xlim_changed', self.cb2.on_x_x)
        self.ax2.callbacks.connect('xlim_changed', self.cb1.on_x_x)

    def yy(self):
        self.ax1.callbacks.connect('ylim_changed', self.cb2.on_y_y)
        self.ax2.callbacks.connect('ylim_changed', self.cb1.on_y_y)

    def xy(self):
        self.ax1.callbacks.connect('xlim_changed', self.cb2.on_x_y)
        self.ax2.callbacks.connect('ylim_changed', self.cb1.on_y_x)

    def yx(self):
        self.ax1.callbacks.connect('ylim_changed', self.cb2.on_y_x)
        self.ax2.callbacks.connect('xlim_changed', self.cb1.on_x_y)



class RangeSet:
    """
    Class for manipulating time ranges within a given time series
    of positions.  Throughout, a time range means a sequence::

        (t_start, t_end)

    Any input sequence that is not a tuple is converted to a tuple
    so that it can be used as a dictionary key.

    The ranges are provided as time ranges via the read/write
    *ranges* property, and as slices via the read-only *slices*
    property. Both return copies of the internal lists, so
    modifying these copies does not affect the internal data.

    The ranges may be modified by assigning a new list of time
    ranges to the *ranges* property, or by calling the
    *delete_range* and *append_range* methods.

    A callable taking no arguments may be assigned to the *onchange*
    attribute, in which case it will be called whenever the ranges
    are modified by any of the above methods.

    """

    def __init__(self, t=None, x=None, y=None, txy=None, ranges=None):

        if ranges is None:
            ranges=[]
        self.onchange = None  # callback to be added by widget;
                              # it can't be a kwarg because the
                              # RangeSet instance has to be created
                              # before the widget that uses it.
                              # It must be initialized before
                              # calling set_ranges.
                              # This could be generalized to use
                              # a CallbackRegistry if we needed
                              # more than a single callback.
        self._set_array(t=t, x=x, y=y, txy=txy)
        self.set_ranges(ranges)

    def _set_array(self, t=None, x=None, y=None, txy=None):
        if txy is not None:
            self.txy = txy
            self.t = txy[:,0]
            self.x = txy[:,1]
            self.y = txy[:,2]
        else:
            self.t = np.asarray(t, dtype=float).ravel()
            self.x = np.asanyarray(x, dtype=float).ravel()
            self.y = np.asanyarray(y, dtype=float).ravel()
            self.txy = np.hstack((t[:,np.newaxis],
                                 np.ma.filled(self.x[:,np.newaxis], np.nan),
                                 np.ma.filled(self.y[:,np.newaxis], np.nan)))

    def set_ranges(self, ranges):
        self._ranges = [tuple(x) for x in ranges]
        self._slices = [rangeslice(self.t, *x) for x in self._ranges]
        if self.onchange is not None:
            self.onchange()

    def get_ranges(self):
        return list(self._ranges)

    ranges = property(get_ranges, set_ranges)

    def get_slices(self):
        return list(self._slices)

    slices = property(get_slices)

    def delete_range(self, trange):
        trange = tuple(trange)
        try:
            ii = self._ranges.index(trange)
        except ValueError:
            try:
                ii = self._slices[trange]
            except ValueError:
                pass
        del(self._ranges[ii])
        del(self._slices[ii])
        if self.onchange is not None:
            self.onchange()

    def append_range(self, trange):
        trange = tuple(trange)
        self._ranges.append(trange)
        self._slices.append(rangeslice(self.t, *trange))
        if self.onchange is not None:
            self.onchange()

    def xy_from_t(self, t):
        i0 = np.searchsorted(self.t, t)
        if i0 == 0:
            return self.txy[0, 1:]
        if i0 >= len(self.t) - 1:
            return self.txy[-1, 1:]
        dt = t - self.t[i0]
        diffs = self.txy[i0+1] - self.txy[i0]
        if diffs[0] == 0:
            return self.txy[i0, 1:]
        return dt * (diffs[1:] /diffs[0]) + self.txy[i0,1:]

class TXYSelector:
    """
    Widget for selecting a time range, given two functions of time,
    typically longitude and latitude.

    This may be used as-is, or customized in a subclass for particular
    variables.  See the TMapSelector and TVelSelector subclasses below,
    for example.
    """
    tlab = 't'
    xlab = 'x'
    ylab = 'y'
    datafmt = '%8.6g   %8.6g'

    def __init__(self, fig, rangeset, margin=0.05, minspan=None):
        """
        args:
            *fig* is a matplotlib Figure object

            *rangeset* is a RangeSet instance

        kwargs:
            *margin* is the fractional amount of padding when setting
            the x and y limits of the plots.

            *minspan* is a minimum selection size, passed to DualSpanSelector

        """

        fig.clf()
        self._fig = fig
        self.rs = rangeset
        self.rs.onchange = self.show_ranges
        self._close_id = self._fig.canvas.mpl_connect(
                                'close_event', self._close)
        self.margin = margin
        self.minspan = minspan

        self._tbmode = ""
        self._pick_id = None
        self._nav_off_cid = None

        fig.subplots_adjust(wspace=0.05, hspace=0.05)
        self._make_axes()
        self.labels()
        self._add_selectors()
        self.add_buttons()

        self._init_plot()

    def _close(self, *args):
        self.rs.onchange = None
        self._fig.canvas.mpl_disconnect(self._close_id)

    def add_buttons(self):
        """
        This may be overridden in a subclass to use gui-specific
        buttons in place of the mpl radiobutton widget.

        It must provide gui control of the mode_change() callback
        method.  See _add_mpl_buttons for an example.
        """
        self._add_mpl_buttons2()

    def _make_axes(self):
        fig = self._fig
        self.ax_xy = fig.add_subplot(2, 2, 2)
        self.ax_xt = fig.add_subplot(2, 2, 4, sharex=self.ax_xy)
        self.ax_ty = fig.add_subplot(2, 2, 1, sharey=self.ax_xy)
        self.ax_map = fig.add_subplot(2, 2, 3)
        self._coupler = Coupler(self.ax_xt, self.ax_ty)
        self._coupler.yx()  # share the time axis

        self.ax_xy.xaxis.tick_top()
        self.ax_xy.xaxis.set_label_position('top')
        self.ax_xy.yaxis.tick_right()
        self.ax_xy.yaxis.set_label_position('right')


        self.ax_xt.yaxis.tick_right()
        self.ax_xt.yaxis.set_label_position('right')

        self.ax_ty.xaxis.tick_top()
        self.ax_ty.xaxis.set_label_position('top')

        for ax in [self.ax_xy, self.ax_xt, self.ax_ty, self.ax_map]:
            ax.grid('on')
            ax.xaxis.set_major_locator(MaxNLocator(4))
            ax.yaxis.set_major_locator(MaxNLocator(4))
            ax.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
            ax.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))


    def labels(self, *args):
        """
        Label all subplots; this is called automatically with
        no arguments upon initialization, to use the class attributes.
        As a user-callable method, it should be called with all
        three labels (t, x, y) as arguments.
        The same effect can be obtained by subclassing, as in
        TVelSelector.
        """
        if args:
            tlab, xlab, ylab = args
        else:
            tlab, xlab, ylab = self.tlab, self.xlab, self.ylab
        self.ax_ty.set_xlabel(tlab)
        self.ax_ty.set_ylabel(ylab)
        self.ax_xt.set_xlabel(xlab)
        self.ax_xt.set_ylabel(tlab)
        self.ax_xy.set_xlabel(xlab)
        self.ax_xy.set_ylabel(ylab)
        self.ax_map.set_xlabel(xlab)
        self.ax_map.set_ylabel(ylab)

    def _customize_map(self):
        try:
            self.ax_map.set_facecolor((0.7, 0.85, 0.95))
        except:
            self.ax_map.set_axis_bgcolor((0.7, 0.85, 0.95)) #deprecated as of mpl2.0
        xr = self._scale_view(self.rs.x.min(), self.rs.x.max())
        yr = self._scale_view(self.rs.y.min(), self.rs.y.max())
        self.ax_map.set_xlim(*xr)
        self.ax_map.set_ylim(*yr)

    def customize_map(self):
        """
        Hook for subclassing if desired.
        """
        self._customize_map()

    def _add_selectors(self):
        #self.ss = DualSpanSelector([self.ax_ty, self.ax_xt], self.t_select,
        #                            useblit=True, minspan=self.minspan)
        self.ss = DualSpanSelector([self.ax_ty, self.ax_xt, self.ax_xy],
                                    self.t_select,
                                    useblit=True,
                                    minspan=self.minspan,
                                    xy_from_t=self.rs.xy_from_t)
        self.ss.visible = False

    def _add_mpl_buttons2(self):
        self.radiobuttons = StateSelector(self._fig,
                                ["nav", "select", "delete"],
                                self.mode_change)

    def _add_mpl_buttons(self):
        self._fig.subplots_adjust(bottom=0.2)
        self.ax_mode   = self._fig.add_axes([0.60, 0.015, 0.1, 0.09])
        self.bmode = RadioButtons(self.ax_mode, ['nav', 'select', 'delete'])
        self.bmode.on_clicked(self.mode_change)
        self.mode_change('nav')

    def mode_change(self, mode):
        """
        add_buttons() needs to hook up a callback to this method,
        and initialize it.

        *mode* must be one of 'nav', 'select', 'delete'
        """
        if mode != 'delete' and self._pick_id is not None:
            self._fig.canvas.mpl_disconnect(self._pick_id)
            self._pick_id = None
            #print "delete is disconnected"

        tb = self._fig.canvas.toolbar
        if mode == 'nav':
            self.ss.visible = False
            if self._tbmode == "pan" and not tb.mode.startswith("pan"):
                tb.pan()
            elif self._tbmode == "zoom" and not tb.mode.startswith("zoom"):
                tb.zoom()
            if self._nav_off_cid is not None:
                self._fig.canvas.mpl_disconnect(self._nav_off_cid)
                self._nav_off_cid = None
            return

        # Not nav mode, so turn off any nav function.
        self._nav_off()
        self._nav_off_cid = self._fig.canvas.mpl_connect(
                                    'figure_enter_event', self._nav_off)

        if mode == 'select':
            self.ss.visible = True
        else:  # must be delete mode
            self.ss.visible = False
            self._pick_id = self._fig.canvas.mpl_connect(
                                    'pick_event', self.on_pick)
            #print "delete is connected"

    def _nav_off(self, event=None):
        tb = self._fig.canvas.toolbar
        if tb.mode.startswith("pan"):
            tb.pan()
            self._tbmode = "pan"
        elif tb.mode.startswith("zoom"):
            tb.zoom()
            self._tbmode = "zoom"


    def _init_plot(self):
        self._lxy = self.ax_xy.plot(self.rs.x, self.rs.y, 'k.')
        self._lxt = self.ax_xt.plot(self.rs.x, self.rs.t, 'k.')
        self._lty = self.ax_ty.plot(self.rs.t, self.rs.y, 'k.')
        self._lmap = self.ax_map.plot(self.rs.x, self.rs.y, 'k.')
        #self._lmap[0].set_ms(10)
        self.customize_map()
        self.patchdict = dict()  # for patches in ty and xt
        self.linedict = dict()   # for markers in xy and map
        self.show_ranges()
        self.update()

    def t_select(self, tmin, tmax):
        self.rs.append_range((tmin, tmax)) # triggers plot update via callback
                                           # to show_ranges
    def show_ranges(self):
        pd = self.patchdict
        ld = self.linedict
        pdkeys = set(pd.keys())
        ranges = set(self.rs.ranges)
        to_delete = pdkeys.difference(ranges) # in pdkeys but not ranges
        to_add = ranges.difference(pdkeys)    # in ranges but not pdkeys
        for k in to_delete:
            p1, p2 = pd.pop(k)
            p1.remove()
            p2.remove()
            line1, line2 = ld.pop(k)
            line1.remove()
            line2.remove()
        for r in to_add:
            rects = self.ss.make_rects(r[0], r[1] - r[0],
                            facecolor='b', alpha=0.15,
                            picker=True)
            pd[r] = rects
            self.ax_ty.add_patch(rects[0])
            self.ax_xt.add_patch(rects[1])
            lines = self.make_lines(r)
            ld[r] = lines
            color = lines[0].get_markerfacecolor()
            for rect in rects:
                rect.set_facecolor(color)
        self._fig.canvas.draw()

    def make_lines(self, r):
        """
        For range *r*, plot markers in the xy and map panels,
        and return the list of two Line2D objects.
        """
        lines = []
        sl = self.rs.slices[self.rs.ranges.index(r)]
        line, = self.ax_xy.plot(self.rs.x[sl], self.rs.y[sl], 'o')
        lines.append(line)
        line, = self.ax_map.plot(self.rs.x[sl], self.rs.y[sl], 'o')
        line.set_markersize(10)
        lines.append(line)
        for line in lines:
            line.set_markeredgecolor('none')
            line.set_alpha(0.15)
        return lines


    def on_pick(self, event):
        """
        Callback for picking a range to be deleted.
        """
        #print "pick", event
        a = event.artist
        if not isinstance(a, Rectangle):
            return
        if event.mouseevent.inaxes == self.ax_ty:
            rdict = dict([(v[0], k) for k, v in self.patchdict.items()])
        elif event.mouseevent.inaxes == self.ax_xt:
            rdict = dict([(v[1], k) for k, v in self.patchdict.items()])
        else:
            return
        try:
            r = rdict[a]
        except KeyError:
            return
        self.rs.delete_range(r)  # Triggers show_ranges via callback.


    def _scale_view(self, xmin, xmax):
        dx = (xmax -xmin) * self.margin
        return xmin - dx, xmax + dx

    def update(self):
        # This may be doing much more than necessary, but
        # it is good enough for now.
        t, x, y = self.rs.t, self.rs.x, self.rs.y

        xr = self._scale_view(x.min(), x.max())
        yr = self._scale_view(y.min(), y.max())
        tr = self._scale_view(t.min(), t.max())
        self.ax_xy.set_xlim(*xr)
        self.ax_xy.set_ylim(*yr)
        self.ax_xt.set_ylim(*tr)
        self._fig.canvas.draw()


class TMapSelector(TXYSelector):
    tlab = 'time'
    xlab = 'longitude'
    ylab = 'latitude'

    def customize_map(self):
        self._customize_map()
        midlat = 0.5 * (self.rs.y.max() + self.rs.y.min())*np.pi/180.0
        self.ax_map.set_aspect(1.0/np.cos(midlat), adjustable='datalim')

class TVelSelector(TXYSelector):
    tlab = 'time'
    xlab = 'u'
    ylab = 'v'



def test(t,x,y,selections):
    import  matplotlib.pyplot as plt
    # dummy data: 10 days of 5-min samples.
    # FIXME: make a more cruise-track-like demo data generator,
    # perhaps by specifying a set of velocities for different
    # time ranges, and then integrating from an initial position
    # to generate x, y.

    fig = plt.figure()

    rs = RangeSet(t, x, y, ranges=selections)
    print('initial selections as time ranges:', rs.ranges)
    print('initial selections as slices:', rs.slices)

    TMapSelector(fig, rs, minspan=600.0/86400) # min is 10 minutes
    if not plt.isinteractive():
        plt.show()

    return rs
