#!/usr/bin/env python

''' interactive txyzoom --
- called on command line, uses dummy data and prints to stdout
'''
import numpy as np

import matplotlib
import  matplotlib.pyplot as plt

from matplotlib.widgets import RectangleSelector, SpanSelector
from matplotlib.widgets import Button
from matplotlib.ticker import MaxNLocator, ScalarFormatter
from matplotlib.transforms import Bbox, TransformedBbox


class TXYSelector:
    '''
    Widget for selecting a range or set of times, given two functions of time.

    This may be used as-is, or customized in a subclass for particular
    variables.  See the TMapSelector and TVelSelector subclasses below,
    for example.
    '''
    tlab = 't'
    xlab = 'x'
    ylab = 'y'
    datafmt = '%8.6g   %8.6g'

    def __init__(self, t=None, x=None, y=None, txy=None,
                    indices=None, fig=None, margin=0.05):
        '''
        kwargs:
            t, x, and y must be sequences of the same length;
            alternatively they can be omitted, and the txy
            kwarg can be used to provide an ndarray of length
            (N,3).

            indices can be a slice object, or a sequence of two integers
            used to generate a slice, or an ndarray of integers.

            fig is an optional figure object; if None, a new
            figure will be made.

            margin is the fractional amount of padding when setting
            the x and y limits of the plots.

        Useful attributes:
            saved_sels is the list of saved indexing objects,
            which may be either slice objects or ndarrays of indices.

            Regardless of how the data were entered, the
            object will have t, x, y, and txy attributes.

        '''

        self.margin = margin
        if fig is None:
            tb = matplotlib.rcParams['toolbar']
            matplotlib.rcParams['toolbar'] = 'None'
            fig = plt.figure()
            matplotlib.rcParams['toolbar'] = tb
        else:
            fig.clf()
        self._fig = fig
        fig.subplots_adjust(wspace=0.05, hspace=0.05)
        self._make_axes()

        self.labels()
        self._add_selectors()
        self._add_buttons()
        self._add_cursor_position()
        self._indices = indices # for re-initialization
        self.reset_sels(indices)
        self.set_array(t=t, x=x, y=y, txy=txy) # must be after reset_sels()
                # Calls customize_map and update, so it ends with
                # a draw.  There is some duplication of effort between
                # the plotting in set_array and the data setting in
                # update, but I suspect this is negligible.


    def _make_axes(self):
        fig = self._fig
        self.ax_xy = fig.add_subplot(2, 2, 2)
        self.ax_xt = fig.add_subplot(2, 2, 4, sharex=self.ax_xy)
        self.ax_ty = fig.add_subplot(2, 2, 1, sharey=self.ax_xy)
        self.ax_map = fig.add_subplot(2, 2, 3)

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
        '''
        Label all subplots; this is called automatically with
        no arguments upon initialization, to use the class attributes.
        As a user-callable method, it should be called with all
        three labels (t, x, y) as arguments.
        The same effect can be obtained by subclassing, as in
        TVelSelector.
        '''
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
        self.ax_map.set_axis_bgcolor((0.7, 0.85, 0.95))
        xr = self._scale_view(self.x.min(), self.x.max())
        yr = self._scale_view(self.y.min(), self.y.max())
        self.ax_map.set_xlim(*xr)
        self.ax_map.set_ylim(*yr)

    def customize_map(self):
        ''' override in subclass '''
        self._customize_map()

    def _add_selectors(self):
        # We could use a lasso for the xy panel...
        self.rs_xy = RectangleSelector(self.ax_xy, self.xy_callback,
                                       drawtype='box', useblit=True,
                                       minspanx=5, minspany=5,
                                       spancoords='pixels')
        self.ss_xt = SpanSelector(self.ax_xt, self.t_callback,
                                  'vertical',
                                  minspan=None,  # maybe use this later
                                  useblit=True)

        self.ss_ty = SpanSelector(self.ax_ty, self.t_callback,
                                  'horizontal',
                                  useblit=True)

        # We could use a kwarg to select these instead of Span.
        #self.rs_xt = RectangleSelector(self.ax_xt, self.xt_callback,
        #                               drawtype='box', useblit=True,
        #                               minspanx=5, minspany=5,
        #                               spancoords='pixels')
        #self.rs_ty = RectangleSelector(self.ax_ty, self.ty_callback,
        #                               drawtype='box', useblit=True,
        #                               minspanx=5, minspany=5,
        #                               spancoords='pixels')

    def _reset(self, event):
        self.reset_sels()
        self._lmap[1].set_mfc('r')
        self.update()

    def _save(self, event):
        s = self.sels[-1]
        if len(self.sels) > 1:         # maybe simpler with try/except
            s0 = self.sels[-2]
            if type(s) is type(s0) and s == s0:
                return  # Don't save a duplicate.
        last_sel = self.sels[-1]
        self.saved_sels.append(last_sel)
        print('txy range:', self.txy[last_sel][0], self.txy[last_sel][-1])

        self._lmap[1].set_mfc('b')
        self._fig.canvas.draw()

    def _back(self, event):
        self._lmap[1].set_mfc('r')
        if len(self.sels) > 1:
            del(self.sels[-1])
            self.update()

    def _add_buttons(self):
        self._fig.subplots_adjust(bottom=0.2)
        self.ax_reset = self._fig.add_axes([0.3, 0.025, 0.1, 0.075])
        self.ax_back  = self._fig.add_axes([0.45, 0.025, 0.1, 0.075])
        self.ax_save  = self._fig.add_axes([0.6, 0.025, 0.1, 0.075])
        self.breset = Button(self.ax_reset, 'Reset')
        self.bback = Button(self.ax_back, 'Back')
        self.bsave = Button(self.ax_save, 'Save')
        self.breset.on_clicked(self._reset)
        self.bback.on_clicked(self._back)
        self.bsave.on_clicked(self._save)

    def _add_cursor_position(self):
        for ax in [self.ax_reset, self.ax_back, self.ax_save]:
            ax.set_navigate(False)
        self.msg1 = self._fig.text(0.75, 0.06, '')
        bb = Bbox.from_bounds(0.73, 0.05, 0.25, 0.05)
        self.msgbox = TransformedBbox(bb, self._fig.transFigure)
        self._fig.canvas.mpl_connect('motion_notify_event', self.mouse_move)
        self._fig.canvas.mpl_connect('resize_event', self.resize)
        self.resize()

    def resize(self, *args):
        self._fig.canvas.draw()
        self.msg_background = self._fig.canvas.copy_from_bbox(self.msgbox)


    def mouse_move(self, event):
        if event.inaxes and event.inaxes.get_navigate():
            try:
                s = self.datafmt % (event.xdata, event.ydata)
            except ValueError: 
                pass
            except OverflowError: 
                pass
            else:
                self.msg1.set_text(s)
        else: 
            self.msg1.set_text('')
        self._fig.canvas.restore_region(self.msg_background)
        self.msg1.draw(self._fig.canvas.renderer)
        self._fig.canvas.blit(self.msgbox)

    def reset_sels(self, indices=None):
        '''
        used internally for initialization and in a callback;
        see set_array docstring.
        '''
        if indices is None:
            self.sels = [slice(0, None)]
        elif isinstance(indices, slice):
            self.sels = [indices]
        elif len(indices) == 2:  # assume a pair indices
            self.sels = [slice(min(indices), max(indices))]
        else:
            self.sels = indices # assume ndarray of integers

    def set_array(self, t=None, x=None, y=None, txy=None):
        '''
        presently for internal use; not clear whether it will
        be possible or desirable to keep the instance, and its
        figure, alive while changing data sets.
        '''
        if txy is not None:
            self.txy = txy
            self.t = txy[:,0]
            self.x = txy[:,1]
            self.y = txy[:,2]
        else:
            self.t = np.asarray(t, dtype=float).ravel()
            self.x = np.asarray(x, dtype=float).ravel()
            self.y = np.asarray(y, dtype=float).ravel()
            self.txy = np.hstack((t[:,np.newaxis],
                                 x[:,np.newaxis], y[:,np.newaxis]))
        self.saved_sels = []
        ii = self.sels[-1]
        # We might do better to generate the line objects
        # directly and then add them to the axes; there would
        # then be 5 line objects.
        self._lxy = self.ax_xy.plot(self.x[ii], self.y[ii], 'k.')
        self._lxt = self.ax_xt.plot(self.x[ii], self.t[ii], 'k.')
        self._lty = self.ax_ty.plot(self.t[ii], self.y[ii], 'k.')
        self._lmap = self.ax_map.plot(self.x, self.y, 'k.',
                         self.x[ii], self.y[ii], 'r.')
        self._lmap[0].set_ms(10)
        self._lmap[1].set_ms(12)
        self.customize_map()
        self.update()

    @staticmethod
    def _event_range(event1, event2):
        x1, y1 = event1.xdata, event1.ydata
        x2, y2 = event2.xdata, event2.ydata
        return min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)

    def _cond_to_indexer(self, cond):
        mask = np.zeros((self.t.size,), bool)
        mask[self.sels[-1]] = True
        ii = np.where(mask & cond)[0]
        if len(ii):
            i0 = ii[0]
            i1 = ii[-1] + 1
            if i1 - i0 == len(ii):  # no gaps; use slice
                return slice(i0, i1)
            else:
                return ii
        else:
            return None

    def _to_sel(self, xmin, xmax, ymin, ymax, cx, cy):
        x = self.txy[:, cx]
        y = self.txy[:, cy]
        cond = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
        return self._cond_to_indexer(cond)

    def xy_callback(self, event1, event2):
        'For use with RectangleSelector'
        xmin, xmax, ymin, ymax = self._event_range(event1, event2)
        _sel = self._to_sel(xmin, xmax, ymin, ymax, 1, 2)
        if _sel is not None:
            self._lmap[1].set_mfc('r')
            self.sels.append(_sel)
            self.update()

    def t_callback(self, tmin, tmax):
        'For use with SpanSelector.'
        t = self.t
        cond = (t >= tmin) & (t <= tmax)
        _sel = self._cond_to_indexer(cond)
        if _sel is not None:
            self._lmap[1].set_mfc('r')
            self.sels.append(_sel)
            self.update()

    def xt_callback(self, event1, event2):
        ' For use with RectangleSelector.'
        xmin, xmax, ymin, ymax = self._event_range(event1, event2)
        _sel = self._to_sel(xmin, xmax, ymin, ymax, 1, 0)
        if _sel is not None:
            self._lmap[1].set_mfc('r')
            self.sels.append(_sel)
            self.update()


    def ty_callback(self, event1, event2):
        ' For use with RectangleSelector.'
        xmin, xmax, ymin, ymax = self._event_range(event1, event2)
        _sel = self._to_sel(xmin, xmax, ymin, ymax, 0, 2)
        if _sel is not None:
            self._lmap[1].set_mfc('r')
            self.sels.append(_sel)
            self.update()

    def _scale_view(self, xmin, xmax):
        dx = (xmax -xmin) * self.margin
        return xmin - dx, xmax + dx

    def update(self):
        s = self.sels[-1]
        t = self.t[s]
        x = self.x[s]
        y = self.y[s]
        self._lxy[0].set_data(x, y)
        self._lxt[0].set_data(x, t)
        self._lty[0].set_data(t, y)
        self._lmap[1].set_data(x, y)
        xr = self._scale_view(x.min(), x.max())
        yr = self._scale_view(y.min(), y.max())
        tr = self._scale_view(t.min(), t.max())
        self.ax_xy.set_xlim(*xr)
        self.ax_xy.set_ylim(*yr)
        self.ax_xt.set_ylim(*tr)
        self.ax_ty.set_xlim(*tr)
        self._fig.canvas.draw()

class TMapSelector(TXYSelector):
    tlab = 'time'
    xlab = 'longitude'
    ylab = 'latitude'

    def customize_map(self):
        self._customize_map()
        midlat = 0.5 * (self.y.max() + self.y.min())*np.pi/180.0
        self.ax_map.set_aspect(1.0/np.cos(midlat))

class TVelSelector(TXYSelector):
    tlab = 'time'
    xlab = 'u'
    ylab = 'v'



def test():
    t = np.arange(0.0,1.0,0.02)
    x = -120.0 + np.sin(2*np.pi*t)
    y = 20.0 + np.exp(-t*3.)*np.cos(3*np.pi*t)

    S = TMapSelector(t, x, y, indices=[10,50])
    if not plt.isinteractive():
        plt.show()
    #else: we need a function that blocks until the window is
    # deleted.

    print('selections:', S.saved_sels)
    print('txy ranges:')
    for s in S.saved_sels:
        print(S.txy[s][0], S.txy[s][-1])
    return S
