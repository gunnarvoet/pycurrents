"""
    Time range selector widget for picking time ranges corresponding
    to latitude or longitude sections, etc.

    This module includes a class that can be used with or without
    subclassing in a gui-independent fashion, or that can be
    subclassed to be embedded in a specific gui application.

    Data and selections are managed with an instance of the
    RangeSet class that is independent of the TxySelector widget.

    This can be run as a script on the command line for demonstration
    and testing.

"""
import numpy as np

from matplotlib.widgets import RadioButtons
from matplotlib.ticker import ScalarFormatter
from matplotlib.transforms import blended_transform_factory
from matplotlib.patches import Rectangle

from pycurrents.num import rangeslice
from pycurrents.plot.txyselect import StateSelector
from matplotlib.widgets import SpanSelector

class TYRangeSet:
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

    def __init__(self, t=None, y=None, ty=None, ranges=None):
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
        self._set_array(t=t, y=y)
        self.set_ranges(ranges)

    def _set_array(self, t=None, y=None, ty=None):
        if ty is not None:
            self.ty = ty
            self.t = ty[:,0]
            self.y = ty[:,1]
        else:
            self.t = np.asarray(t, dtype=float).ravel()
            self.y = np.asarray(y, dtype=float).ravel()
            self.ty =  np.hstack((t[:,np.newaxis], y[:,np.newaxis]))

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


class TYSelector:
    """
    Widget for selecting a time range, given two functions of time,
    typically longitude and latitude.

    This may be used as-is, or customized in a subclass for particular
    variables.  See the TMapSelector and TVelSelector subclasses below,
    for example.
    """
    tlab = 't'
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

    def _make_axes(self, *args):
        fig = self._fig
        self.ax = fig.add_subplot(111)
        self.ax.grid('on')
        self.ax.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        self.ax.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        if args:
            tlab, ylab = args
        else:
            tlab, ylab = self.tlab, self.ylab

        self.ax.set_xlabel(tlab)
        self.ax.set_ylabel(ylab)

    def _add_selectors(self):
        self.ss = SpanSelector(self.ax, self.t_select,
                                   'horizontal',  useblit=True)
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
        self._lty = self.ax.plot(self.rs.t, self.rs.y, 'k.')
        #self._lmap[0].set_ms(10)
        self.patchdict = dict()  # for patches in ty and xt
        self.show_ranges()
        self.update()

    def t_select(self, tmin, tmax):
        self.rs.append_range((tmin, tmax)) # triggers plot update via callback
                                           # to show_ranges
    def show_ranges(self):
        pd = self.patchdict
        pdkeys = set(pd.keys())
        ranges = set(self.rs.ranges)
        to_delete = pdkeys.difference(ranges) # in pdkeys but not ranges
        to_add = ranges.difference(pdkeys)    # in ranges but not pdkeys
        for k in to_delete:
            rect = pd.pop(k)
            rect.remove()
        for r in to_add:
            rect = self.make_rect(r[0], r[1] - r[0],
                           facecolor='b', alpha=0.15,
                            picker=True)
            pd[r] = rect
            self.ax.add_patch(rect)
        self._fig.canvas.draw()

    def make_rect(self, pos, thickness, **kw):
        ''' lifted from DualSpanSelector; one rectangle only'''
        ax = self.ax
        trans = blended_transform_factory(ax.transData, ax.transAxes)
        return(Rectangle( (pos,0), thickness, 1,transform=trans, **kw))

    def on_pick(self, event):
        """
        Callback for picking a range to be deleted.
        """
        #print "pick", event
        a = event.artist
        if not isinstance(a, Rectangle):
            return
        if event.mouseevent.inaxes == self.ax:
            rdict = dict([(v, k) for k, v in self.patchdict.items()])
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
        t, y = self.rs.t, self.rs.y

        self._scale_view(y.min(), y.max())
        self._scale_view(t.min(), t.max())
        self._fig.canvas.draw()


class TZSelector(TYSelector):
    tlab = 'time'
    ylab = 'depth'



def test():
    import  matplotlib.pyplot as plt
    # dummy data: 10 days of 5-min samples.
    # FIXME: make a more cruise-track-like demo data generator,
    # perhaps by specifying a set of velocities for different
    # time ranges, and then integrating from an initial position
    # to generate x, y.
    t = np.arange(0.0, 10.0, 300.0/86400)
    y = 20.0 + np.exp(-t*3.)*np.sin(3*np.pi*t/10)

    selections = [[0.1, 1.15], [2, 4.4]]

    fig = plt.figure()

    rs = TYRangeSet(t, y, ranges=selections)
    print('initial selections as time ranges:', rs.ranges)
    print('initial selections as slices:', rs.slices)


    TYSelector(fig, rs, minspan=600.0/86400) # min is 10 minutes
    if not plt.isinteractive():
        plt.show()

    if not plt.isinteractive():
        plt.show()

    return rs
