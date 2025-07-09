"""
    startstop.py makes a class StartStopControl, providing a
    button box with state information, and a mechanism for
    calling one function upon starting and another upon
    stopping.

   If a stop or start function raises the ChangedMind
   exception, the button press action is not carried out.

   This version uses Tkinter/Pmw; probably it should be
   renamed so an alternative pygtk version can be
   substituted for it.

   EF; written in August, 2002, on the KM transit from
   Panama to Honolulu.

   2003/12/19, after KM test cruise, modified so that the
   start button is disabled as soon as it is pressed, and
   reenabled only if there is an exception (usually the
   ChangedMind exception, unless there is a bug), and
   similarly for the stop button.  This should provide
   better user feedback, as well as preventing problems with
   multiple button presses.

"""

from tkinter import IntVar
import Pmw

class ChangedMind(Exception):
    ''' Raise this exception in a confirmation dialog
        when the action is not confirmed.
    '''
    pass

## I don't know why I used a ButtonBox as the base instead
## of a RadioSelect, which looks like it is closer to what I
## actually want.  Maybe this version is required to get the
## ChangedMind exception mechanism to work.

class StartStopControl(Pmw.ButtonBox):
    states = {'stopped' : 0, 'started' : 1, 'running' : 1}

    def __init__(self, parent, funcs,
                 names = ('Start', 'Stop'),
                 initial_state = 'stopped',
                 enabled = 1, **kw):
        Pmw.ButtonBox.__init__(*(self, parent), **kw)
        self.funcs = funcs
        self._IV_running = IntVar() # 1 if started, 0 if stopped
        # Add the two Pmw buttons.
        self.B_start = self.add(names[0], command = self.C_start)
        self.B_end = self.add(names[1], command = self.C_stop)
        self.alignbuttons('later')
        self.set_state(initial_state)
        self.enabled = enabled
        if enabled:
            self.enable()
        else:
            self.disable()


    def C_start(self, **kw):
        try:
            self.B_start.configure(state = 'disabled')
            self.funcs[0](**kw)
            self.set_started()
        except ChangedMind:
            self.B_start.configure(state = 'normal')
        except:
            self.B_start.configure(state = 'normal')
            raise

    def C_stop(self, **kw):
        try:
            self.B_end.configure(state = 'disabled')
            self.funcs[1](**kw)
            self.set_stopped()
        except ChangedMind:
            self.B_end.configure(state = 'normal')
        except:
            self.B_end.configure(state = 'normal')
            raise

    def set_stopped(self):
        self._IV_running.set(0)
        self.B_start.configure(state = 'normal')
        self.B_end.configure(state = 'disabled')

    def set_started(self):
        self._IV_running.set(1)
        self.B_end.configure(state = 'normal')
        self.B_start.configure(state = 'disabled')

    def is_running(self):
        return self._IV_running.get()

    def set_state(self, state):
        if self.states[state]:
            self.set_started()
        else:
            self.set_stopped()

    def enable(self):
        self.enabled = 1
        if self.is_running():
            self.set_started()
        else:
            self.set_stopped()

    def disable(self):
        self.enabled = 0
        self.B_end.configure(state = 'disabled')
        self.B_start.configure(state = 'disabled')
