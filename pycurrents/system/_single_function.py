"""
Mixin for making SingleFunction classes with and without a GUI.
"""

import os, time

from pycurrents.system.misc import sleep as safesleep

class _SingleFunction:
    """
    This must be in the middle of an inheritance hierarchy.
    It will have some version of Checker as a superclass.
    Subclass must define a run() method.

    Execute the start() method to begin execution.

    This ensures only one instance is running at a time, and
    allows control over how to handle duplicates.
    """
    def __init__(self, flagdir=None, args=None, kwargs=None, **kw):
        """
        If *flagdir* is not None, a flag file is used to record
        the start time and pid, and a stopflagfile can be used to
        signal the process to end.

        *args* and *kwargs* are a tuple and dictionary, respectively,
        for supplying arguments and options to the run method.

        \*\*kw are passed to Checker.__init__().
        """
        super().__init__(self, **kw)
        if args is None:
            args = ()
        self._args = args
        if kwargs is None:
            kwargs = {}
        self._kwargs = kwargs
        self.name = os.path.splitext(self.command)[0]
        if flagdir is None:
            self.flagfile = None
            self.stopflagfile = None
        else:
            self.flagfile = os.path.join(flagdir, self.name + '.running')
            self.stopflagfile = os.path.join(flagdir, self.name + '.stop')
            try: os.remove(self.stopflagfile)
            except: 
                pass
        self.check()

    def start(self):
        """
        Write out the flagfile, and execute the run method.

        The flagfile has two lines: the pid, and the start time.
        """
        self.start_time = time.gmtime()
        tstr = time.strftime('%Y/%m/%d %H:%M:%S', self.start_time)
        ffstr = '%s\n%s\n' % (str(self.pid), tstr)
        try:
            if self.flagfile:
                with open(self.flagfile, 'w') as file:
                    file.write(ffstr)
                while not os.path.exists(self.flagfile):
                    safesleep(0.1)  # in case there is a delay
            self.run(*self._args, **self._kwargs)
        finally:
            self.cleanup()

    def run(self, *args, **kwargs):
        """
        Override this.

        If the run method includes a loop, then one can monitor it
        by updating the modification time of the flagfile with the
        following line in the loop:

        os.utime(self.flagfile, None)
        """
        raise NotImplementedError("Subclass must define this method.")

    def cleanup(self):
        if self.flagfile:
            try: 
                os.remove(self.flagfile)
            except: 
                pass
        if self.stopflagfile:
            try: 
                os.remove(self.stopflagfile)
            except: 
                pass
