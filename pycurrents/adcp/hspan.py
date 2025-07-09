"""
Single class: TYSelector, a span selector for patch_hcorr.py.

It allows interactive selection of multiple intervals in a
time series.

May be useful elsewhere.

"""

import numpy as np
import matplotlib

from matplotlib.widgets import SpanSelector
from matplotlib.widgets import Button
from matplotlib.ticker import MaxNLocator
from matplotlib.transforms import Bbox, TransformedBbox


class TYSelector:
    '''
    Widget for selecting a range or set of times, given a function of time.

    '''
    tlab = 't'
    ylab = 'y'
    datafmt = '%8.6g   %8.6g'

    def __init__(self, t=None, y=None, ty=None,
                    indices=None, fig=None, margin=0.05,
                    callback=None, cbutton_name='Echo'):
        '''
        kwargs:
            t, and y must be sequences of the same length;
            alternatively they can be omitted, and the ty
            kwarg can be used to provide an ndarray of length
            (N,2).

            indices can be a slice object, or a sequence of two integers
            used to generate a slice, or an ndarray of integers.

            fig is an optional figure object; if None, a new
            figure will be made.

            One button can be attached to a callback.
            The callback is a function taking one argument, the selector
            instance.  use "callback_name" to label the button.
            If not None, the function will be called when
            the button is pressed.  (default is to echo selected)

        Useful attributes:
            saved_sels is the list of saved indexing objects,
            which may be either slice objects or ndarrays of indices.

            Regardless of how the data were entered, the
            object will have t, y, and ty attributes.

        '''

        self.cbutton_name = cbutton_name

        self.margin = margin
        if fig is None:
            tb = matplotlib.rcParams['toolbar']
            matplotlib.rcParams['toolbar'] = 'None'
            import  matplotlib.pyplot as plt
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
        self.set_array(t=t, y=y, ty=ty) # must be after reset_sels()
                # Calls customize_map and update, so it ends with
                # a draw.  There is some duplication of effort between
                # the plotting in set_array and the data setting in
                # update, but I suspect this is negligible.
        self.callback = callback


    def _make_axes(self):
        fig = self._fig

        self.ax_map = fig.add_subplot(2, 1, 1)  # display here
        self.ax_map.xaxis.set_label_position('top')
        self.ax_map.xaxis.tick_top()

        self.ax_ty  = fig.add_subplot(2, 1, 2)  # select here
        self.ax_ty.xaxis.tick_bottom()
        for ax in [self.ax_ty, self.ax_map]:
            ax.grid('on')
            ax.xaxis.set_major_locator(MaxNLocator(5))
            ax.yaxis.set_major_locator(MaxNLocator(4))

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
            ylab = args[1]
        else:
            ylab = self.ylab
        self.ax_ty.set_xlabel('select horizontal span')
        self.ax_ty.set_ylabel(ylab)
        self.ax_map.set_xlabel('show selected')
        self.ax_map.set_ylabel(ylab)

    def _customize_map(self):
        self.ax_map.set_axis_bgcolor((0.7, 0.85, 0.95))
        tr = self._scale_view(self.t.min(), self.t.max())
        yr = self._scale_view(self.y.min(), self.y.max())
        self.ax_map.set_xlim(*tr)
        self.ax_map.set_ylim(*yr)

    def customize_map(self):
        ''' override in subclass '''
        self._customize_map()

    def _add_selectors(self):

        self.ss_ty = SpanSelector(self.ax_ty, self.t_callback,
                                  'horizontal',
                                  useblit=True)

    def _reset(self, event):
        self.reset_sels()
        self._lmap[1].set_mfc('r')
        self.update()

    def _save(self, event):
        s = self.sels[-1]
        if len(self.sels) > 1:         # maybe simpler with try/except
            s0 = self.sels[-2]
            if type(s) == type(s0) and s == s0:
                return  # Don't save a duplicate.
        self.saved_sels.append(self.sels[-1])
        self.ax_map.plot(self.t[s], self.y[s], 'w.')
        self._lmap[1].set_mfc('b')
        self._fig.canvas.draw()

    def _print(self, event):
        print('selections:', self.saved_sels)
        print('time ranges:')
        for s in self.saved_sels:
            print(self.ty[s][0][0], self.ty[s][-1][0])
        if self.callback is not None:
            self.callback(self)

    def _back(self, event):
        self._lmap[1].set_mfc('r')
        if len(self.sels) > 1:
            del(self.sels[-1])
            self.update()

    def _add_buttons(self):
        self._fig.subplots_adjust(bottom=0.2)
        self.ax_reset = self._fig.add_axes([0.15, 0.025, 0.1, 0.075])
        self.ax_back  = self._fig.add_axes([0.3, 0.025, 0.1, 0.075])
        self.ax_print = self._fig.add_axes([0.45, 0.025, 0.1, 0.075])
        self.ax_save  = self._fig.add_axes([0.6, 0.025, 0.1, 0.075])
        self.breset = Button(self.ax_reset, 'Reset')
        self.bback = Button(self.ax_back, 'Back')
        self.bprint = Button(self.ax_print, self.cbutton_name) # Echo
        self.bsave = Button(self.ax_save, 'Save')
        self.breset.on_clicked(self._reset)
        self.bback.on_clicked(self._back)
        self.bprint.on_clicked(self._print)
        self.bsave.on_clicked(self._save)

    def _add_cursor_position(self):
        for ax in [self.ax_reset, self.ax_back, self.ax_print, self.ax_save]:
            ax.set_navigate(False)
        self.msg1 = self._fig.text(0.75, 0.06, '')
        bb = Bbox.from_bounds(0.73, 0.05, 0.25, 0.05)
        self.msgbox = TransformedBbox(bb, self._fig.transFigure)
        self._fig.canvas.mpl_connect('motion_notify_event', self.mouse_move)
        self._fig.canvas.mpl_connect('resize_event', self.resize)
        self.resize()

    def resize(self, *args):
        self.msg_background = self._fig.canvas.copy_from_bbox(self.msgbox)

    def mouse_move(self, event):
        if event.inaxes and event.inaxes.get_navigate():
            try:
                s = self.datafmt % (event.xdata, event.ydata)
            except ValueError: pass
            except OverflowError: pass
            else:
                self.msg1.set_text(s)
        else: self.msg1.set_text('')
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

    def set_array(self, t=None, y=None, ty=None):
        '''
        presently for internal use; not clear whether it will
        be possible or desirable to keep the instance, and its
        figure, alive while changing data sets.
        '''
        if ty is not None:
            self.ty = np.ma.array(ty)
            self.t = np.ma.array(ty[:,0])
            self.y = np.ma.array(ty[:,1])
        else:
            self.t = np.ma.asarray(t, dtype=float).ravel()
            self.y = np.ma.asarray(y, dtype=float).ravel()
            self.ty = np.hstack((self.t[:,np.newaxis],
                                 self.y[:,np.newaxis]))
        self.saved_sels = []
        ii = self.sels[-1]
        # We might do better to generate the line objects
        # directly and then add them to the axes; there would
        # then be 5 line objects.

        tmd = np.ma.getdata(self.t)
        ymd = np.ma.getdata(self.y)

        # colors aren't quite right
        self._lty = self.ax_ty.plot(tmd, ymd, 'm+',
                                    self.t[ii], self.y[ii], 'k.')
        self._lmap = self.ax_map.plot(self.t, self.y, 'k.',
                                      self.t[ii], self.y[ii], 'r.')
        self._lmap[0].set_ms(10)
        self._lmap[1].set_ms(12)
        self.customize_map()
        self.update()

    @staticmethod
    def _event_range(event1, event2):
        t1, y1 = event1.tdata, event1.ydata
        t2, y2 = event2.tdata, event2.ydata
        return min(t1, t2), max(t1, t2), min(y1, y2), max(y1, y2)

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

    def _to_sel(self, tmin, tmax, ymin, ymax, ct, cy):
        t = self.ty[:, ct]
        y = self.ty[:, cy]
        cond = (t >= tmin) & (t <= tmax) & (y >= ymin) & (y <= ymax)
        return self._cond_to_indexer(cond)


    def t_callback(self, tmin, tmax):
        'For use with SpanSelector.'
        t = self.t
        cond = (t >= tmin) & (t <= tmax)
        _sel = self._cond_to_indexer(cond)
        if _sel is not None:
            self._lmap[1].set_mfc('r')
            self.sels.append(_sel)
            self.update()

    def _scale_view(self, tmin, tmax):
        dt = (tmax -tmin) * self.margin
        return tmin - dt, tmax + dt

    def update(self):
        s = self.sels[-1]
        t = self.t[s]
        y = self.y[s]
        self._lty[0].set_data(t, y)
        self._lmap[1].set_data(t, y)
        #yr = self._scale_view(y.min(), y.max())
        tr = self._scale_view(t.min(), t.max())
        self.ax_ty.set_xlim(*tr)
        self._fig.canvas.draw()

def test():

    x = np.arange(3,6.5,.02)
    t = x+123 #dday
    y = 200*np.sin(8*x)/(x*x)
    y=np.ma.masked_where(y>10, y)

    S = TYSelector(t, y)
    import  matplotlib.pyplot as plt
    if not plt.isinteractive():
        plt.show()

    #would be nice to get the chosen indices back from
    # second tab to first tab

    print('selections:', S.saved_sels)
    print('ty ranges:')
    for s in S.saved_sels:
        print(S.ty[s][0], S.ty[s][-1])
    return S

if __name__ == '__main__':
    S = test()
