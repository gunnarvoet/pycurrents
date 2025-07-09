"""
Utility for running a process when one wants to ensure that
no more than one instance is running.

Note: this was developed for UHDAS, and is used as a superclass of
SingleFunction, of which there are GUI and non-GUI variants.
"""

import os
import signal
import sys
import logging

from pycurrents.system.misc import sleep as safesleep

# Standard logging
_log = logging.getLogger(__name__)


class Checker:
    def __init__(self,
                 flagfile = None,
                 stopflagfile = None,
                 action = None,
                 timeout = 1):
        """
        *flagfile* and *stopflagfile* can be None (default) or the path to a
            writeable location.

        *action* can be None (default), "replace", or "keep_old";
            if None, a query window will pop up in case of conflict.
        """
        self.action = action
        self.flagfile = flagfile
        self.stopflagfile = stopflagfile
        self.timeout = timeout
        self.nloops = int(timeout/0.2)
        self.pid = os.getpid()
        self.command = os.path.split(sys.argv[0])[-1]

    def pid_from_flagfile(self):
        if self.flagfile is not None and os.path.isfile(self.flagfile):
            with open(self.flagfile) as newreadf:
                pid = newreadf.readline().strip()
            return pid
        return None

    def check(self):
        _log.debug('check: self.action is %s', self.action)
        if not hasattr(self, 'gui') and self.action is None:
            action = 'replace'
        else:
            action = self.action
        _log.debug('check: action is %s', action)
        plist = self.list_processes()
        if not plist:
            _log.debug('check: no other processes found')
            return
        _log.debug('check: plist is %s', plist)
        _log.debug('check: pid_from_flagfile() is %s', self.pid_from_flagfile())
        if action == 'replace':
            self.end_processes(gui=False)
            return
        if action == 'keep_old':  # keep old one if it matches flagfile
            if len(plist) == 1 and plist[0][0] == self.pid_from_flagfile():
                _log.info('Keeping original; exiting the new process.')
                sys.exit()
            else:                  # something is wrong; run the new one
                _log.debug('plist is %s', plist)
                _log.debug('pid_from_flagfile is %s', self.pid_from_flagfile())
                self.end_processes(gui=False)
                return

        self._gui_check_report(plist)

    def list_processes(self):
        if sys.platform == 'darwin':
            ps = os.popen('ps -o pid,command')
            ps.readline()  # discard header
        else:
            ps = os.popen('ps -C python,python3,%s -o pid,args --no-headers' % self.command)
        procs = ps.readlines()
        procs = [l.strip() for l in procs if l.find(self.command) > 0]
        if sys.platform == 'darwin':
            procs = [l for l in procs if l.find('python') > 0]
        pidcmds = [l.split(None,1) for l in procs]
        pidcmds = [p for p in pidcmds if int(p[0]) != self.pid]
        return pidcmds

    def end_processes(self, gui=True):
        plist = self.list_processes()
        msg = 'Ending %d process(es)' % len(plist)
        _log.debug(msg)

        if gui:
            self._gui_end_processes_prepare(msg)

        if self.stopflagfile is not None and not os.path.exists(self.stopflagfile):
            open(self.stopflagfile, 'w').close()
            for ii in range(self.nloops):
                safesleep(0.2)
                plist = self.list_processes()
                if len(plist) == 0:
                    break
        for p in plist:
            try:
                os.kill(int(p[0]), signal.SIGTERM)
            except:
                pass
        safesleep(0.2)
        plist = self.list_processes()
        for p in plist:
            try:
                os.kill(int(p[0]), signal.SIGKILL)
            except:
                pass

        plist = self.list_processes()
        self.n_left = len(plist)
        if self.n_left:
            msg = 'Failed to kill:\n %s' % str(plist)
            _log.warning(msg)
        else:
            msg = 'Successfully ended duplicate processes'
            _log.debug(msg)

        if gui:
            self._gui_end_processes_report(msg)

        try:
            os.remove(self.stopflagfile)
        except:
            pass
        try:
            os.remove(self.flagfile)
        except:
            pass

    def _gui_check_report(self, plist):
        pass

    def _gui_end_processes_prepare(self, msg):
        pass

    def _gui_end_processes_report(self, msg):
        pass

    def exit(self, dummy = None):
        sys.exit()
