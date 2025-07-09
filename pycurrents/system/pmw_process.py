"""
Utility for running a process when one wants to ensure that
no more than one instance is running.

This is linux-specific because of its use of the "ps" command.
It might work on a Mac, but this would have to be checked.

Note: this was developed for UHDAS.
"""

import tkinter
import Pmw
import logging

from pycurrents.system.checker import Checker as CheckerBase
from pycurrents.system._single_function import _SingleFunction

# Standard logging
_log = logging.getLogger(__name__)


class Checker(CheckerBase):
    gui = True  # Flag used by check() from CheckerBase.

    def _gui_check_report(self, plist):
        root = tkinter.Tk()
        Pmw.initialise(root, size=24, fontScheme='pmw1')
        root.withdraw()
        self.root = root
        self.M = Pmw.MessageDialog(root,
                    title = '%s duplicate process checker' % self.command,
                    message_text = 'Duplicate process(es):\n%s' % str(plist),
                    buttons=('Kill Earlier Duplicate(s)',
                                'Recheck', 'Cancel Latest'),
                    command=self.choices)
        self.M.wm_geometry('900x400+10+10')
        self.M.focus_set()
        root.mainloop()

    def choices(self, button):
        if button is None or button == 'Cancel Latest':
            self.exit()
        if button == 'Kill Earlier Duplicate(s)':
            self.end_processes()
            return
        if button == 'Recheck':
            plist = self.list_processes()
            if not plist:
                self.finished()
            else:
                self.M.configure(message_text =
                               'Duplicate process(es):\n%s' % str(plist))
                return
        if button == 'OK':
            if self.n_left:
                self.exit()
            else:
                self.finished()

    def finished(self, dummy = None):
        self.root.destroy()

    def _gui_end_processes_prepare(self, msg):
        self.M.configure(message_text = msg, buttons=tuple())

    def _gui_end_processes_report(self, msg):
        self.M.configure(message_text = msg, buttons = ('OK',))


class SingleFunction(_SingleFunction, Checker):
    pass
