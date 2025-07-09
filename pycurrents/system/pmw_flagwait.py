import tkinter
import Pmw

import os

waiting_msg = '''Finishing.
Please wait. '''

finished_msg = '''Everything is finished.'''


class Flagwait:
    def __init__(self, master, flagfile, ourflagfile = None,
                                         waiting_msg = waiting_msg,
                                         finished_msg = finished_msg,
                                         keep_running = None,
                                         title = "Flagwait"):
        self.master = master
        self.flagfile = flagfile
        self.ourflagfile = ourflagfile
        if ourflagfile is not None:
            f = open(ourflagfile, 'w')
            f.write("%d" % os.getpid())
            f.close()
        self.finished_msg = finished_msg
        if keep_running is None:
            keep_running = lambda : True
        self._keep_running = keep_running
        self.M = Pmw.MessageDialog(self.master, title = title,
                              message_text = waiting_msg,
                              buttons=tuple())
        self.M.wm_geometry('600x400+10+10')
        self.M.focus_set()
        self.poll_flag()

    def keep_running(self):
        if self._keep_running() and os.path.exists(self.flagfile):
            if self.ourflagfile is None or os.path.exists(self.ourflagfile):
                return True
        return False

    def poll_flag(self):
        if self.keep_running():
            self.M.after(500, self.poll_flag)
        else:
            self.M.configure(message_text = self.finished_msg)
            self.M.configure(buttons = ('OK',))
            self.M.configure(command = self.quit)
            self.M.focus_set()
            try:
                if self.ourflagfile is not None:
                    os.remove(self.ourflagfile)
            except:
                pass

    def quit(self, dummy = None):
        self.master.quit()

def flagwait(master, flagfile, **kwargs):
    if master is None:
        root = tkinter.Tk()
        Pmw.initialise(root, size=24, fontScheme='pmw1')
        root.withdraw()
    else:
        root = master

    Flagwait(root, flagfile, **kwargs)

    if master is None:
        root.mainloop()
        root.destroy()

if __name__ == "__main__":
    import threading, time

    #Case 1: standalone
    flagfile = '/tmp/testpmw_flagwait'
    open(flagfile, 'w').close()

    def wait(flagfile, timeout = 2):
        time.sleep(timeout)
        os.remove(flagfile)

    T = threading.Thread(target=wait, args=(flagfile,))
    T.start()

    flagwait(None, flagfile, waiting_msg = 'Pausing...')
