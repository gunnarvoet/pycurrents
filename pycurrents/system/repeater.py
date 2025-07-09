'''A mechanism for repeatedly running a set of tasks.

   I originally intended to use threadgroup for this, but
   rsync won't run from a python thread (at least as of
   python 2.3) because it relies on signals, and python
   blocks signals when starting a thread.  All this should
   be OK as of python 2.4.

   This module uses signals to provide a timeout, so that
   a hung task will be deleted from the queue instead of
   blocking the queue.  Therefore it must be used only in
   the main thread--signals do not work in secondary threads.

   There is an alternative method that uses threads instead.

'''

import sys
import os
import os.path
import time
import signal
from subprocess import Popen, STDOUT, PIPE
from threading import Timer
from _thread import interrupt_main

import logging
from pycurrents.system.misc import sleep as safesleep

_log = logging.getLogger(__name__)


class Timeout(Exception):
    pass


def timeout_handler(signum, frame):
    raise Timeout()


class PeriodicBase:
    def __init__(self, function, args = (), kwargs = {},
                 interval = 60, initial = None, at_exit = 0,
                 delay=0,
                 follower=False,
                 time_fn=None,
                 name = "unnamed", timeout=None, maxtimeouts=0):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.interval = interval
        self.time_fn = time_fn
        self.follower = follower
        self.at_exit = at_exit
        self.name = name
        self.timeout = timeout
        self.maxtimeouts = maxtimeouts
        self.started = time.time()
        self.time_to_run = self.started + interval + delay
        if initial:
            t = ((int(self.started) // 86400) * 86400) + initial
            while t < self.started + 0.2 * interval:
                t += interval
            self.time_to_run = t
        ttr_struc = time.localtime(self.time_to_run)
        _log.info("task %s initial time_to_run is %s"
               % (self.name, time.strftime("%Y/%m/%d %H:%M:%S", ttr_struc)))

    def run(self, force=0):
        t_start = time.time()
        if (t_start >= self.time_to_run) or force:
            _log.info("task %s starting %.1f seconds late",
                                self.name, t_start-self.time_to_run)
            out = self._run()
            if isinstance(out, (bytes, str)) and len(out) > 2:
                if isinstance(out, bytes):
                    out = out.decode('ascii', errors='replace')
                _log.info("task %s output:\n%s", self.name, out)
            t_end = time.time()
            _log.info("task %s ended after %.1f seconds", self.name, t_end-t_start)
            base = self.time_to_run
            if self.time_fn is not None:
                try:
                    tu = os.stat(self.time_fn).st_mtime
                    # The process updated the file, as expected
                    # (but it seems mtime from closing a file can be slightly
                    # earlier than a preceding time.time() )
                    if tu > (t_start - 1) or self.follower:
                        with open(self.time_fn) as newreadf:
                            ts = newreadf.read().strip()
                        tstruc = time.strptime(ts, "%Y/%m/%d %H:%M:%S")
                        t = time.mktime(tstruc)
                        base = t
                        _log.info("task %s: Time from %s: %s",
                                            self.name, self.time_fn, ts)
                    else:
                        _log.warning("task %s: Expected update of %s" +
                                            " did not occur, dt = %.3f",
                                           self.name, self.time_fn, tu-t_start)

                except OSError:
                    _log.warning("task %s: Could not stat or read %s",
                                            self.name, self.time_fn)
                except ValueError:
                    _log.error("taks %s: Could not parse time in %s",
                                            self.name, self.time_fn)

            self.time_to_run = base + self.interval
            if self.time_to_run < t_end:
                n = 1 + int((t_end - self.time_to_run) // self.interval)
                self.time_to_run += (n * self.interval)
                _log.info("task %s: added %d extra increments to time_to_run",
                                     self.name, n)
            ttr_struc = time.localtime(self.time_to_run)
            _log.info("task %s next time_to_run is %s"
                   % (self.name, time.strftime("%Y/%m/%d %H:%M:%S", ttr_struc)))


    def _run(self):
        raise NotImplementedError

    def kill(self):
        pass


class Periodic(PeriodicBase):
    def __init__(self, function, **kw):
        PeriodicBase.__init__(self, function, **kw)
        _log.info('Periodic: %s interval is %d seconds', self.name, self.interval)

    def _run(self):
        out = self.function(*self.args, **self.kwargs)
        return out

class PeriodicSystem(PeriodicBase):
    def __init__(self, function, shell=False, **kw):
        PeriodicBase.__init__(self, function, **kw)
        newkw = self.kwargs.copy()
        self.kwargs = {'stdout':PIPE, 'stderr':STDOUT, 'bufsize':-1}
        self.kwargs.update(newkw)
        self.kwargs['shell'] = shell
        if not shell and hasattr(function, 'split'):
            self.function = function.split()
        if hasattr(function, 'split'):
            self.funcstring = function
        else:
            self.funcstring = ' '.join(function)
        _log.info('PeriodicSystem: %s interval is %d seconds\n        %s',
                             self.name, self.interval, self.funcstring)

    def _run(self):
        self.p = Popen(self.function, **self.kwargs)
        out = self.p.communicate()[0]
        retcode = self.p.returncode
        if retcode:
            _log.error("task %s returncode %d", self.name, retcode)
            # The form above propagates the output only at the
            # info level, leaving it to the underlying process
            # to include the output at the warn or error level.
            # Switch to the block below, or some logic in the
            # run() method itself, if we want the output propagated
            # to a higher level when there is an error.
            #L.error("task %s returncode %d,   output:\n%s\n",
            #                    self.name, retcode, out)
        return out

    def kill(self):
        if self.p is not None and self.p.returncode is None:
            pid = self.p.pid
            _log.info("task %s is pid %d", self.name, pid)
            try:
                os.kill(pid, signal.SIGTERM)
                for i in range(20):
                    safesleep(0.1)
                    ret = self.p.poll()
                    if ret is not None:
                        _log.info("task %s ended with SIGTERM", self.name)
                        break
                if ret is None:
                    _log.warning("task %s did not exit with SIGTERM", self.name)
                    os.kill(pid, signal.SIGKILL)
            except Exception as e:
                _log.exception(f"task {self.name}\nWith exception {e}")
            self.p = None

class PeriodicRsync(PeriodicSystem):
    '''
    This is identical to PeriodicSystem except that it filters
    out returncode 24, which is
    "Partial transfer due to vanished source files",
    and reports it only at the debug level. Given the way rsync
    is used in UHDAS, it is not really an error.
    '''

    def _run(self):
        self.p = Popen(self.function, **self.kwargs)
        out = self.p.communicate()[0]
        retcode = self.p.returncode
        if retcode == 24:
            _log.debug("task %s returncode %d", self.name, retcode)
        elif retcode:
            _log.error("task %s returncode %d", self.name, retcode)
        return out


class Repeater:
    def __init__(self, condition = None, poll_interval = 1,
                 timeout = 3600, flagfile = None):
        if condition is None:
            self.condition = lambda : 1 # loop forever
        else:
            self.condition = condition
        self.poll_interval = poll_interval
        self.timeout = int(timeout)
        self.flagfile = flagfile
        self.tasks = []
        self.running = 1

    def add(self, task):
        if task.timeout is None:
            task.timeout = self.timeout
        task.ntimeouts = 0
        self.tasks.append(task)

    def _start(self):
        """
        Start the repeated loop over the task list.

        A Timer thread is used for the timeout; note that this cannot
        interrupt a blocking system call.
        """

        while self.condition() and self.running:
            for task in self.tasks[:]:
                if self.flagfile:
                    os.utime(self.flagfile, None)
                if self.condition() and self.running:
                    _watchdog = Timer(self.timeout, interrupt_main)
                    _watchdog.setDaemon(True)
                    _watchdog.start()
                    try:
                        task.run()
                        _watchdog.cancel()
                    except KeyboardInterrupt:
                        task.kill()
                        task.ntimeouts += 1
                        _log.error("Timeout %d in  %s", task.ntimeouts,
                                                         task.name)
                        if task.ntimeouts > task.maxtimeouts:
                            self.tasks.remove(task)
                            _log.warning("Deleted task %s", task.name)
                    except Exception as e :
                        _watchdog.cancel()
                        _log.exception(f'non-timeout exception in task {task.name}\nWith exception {e}')
                    finally:
                        _watchdog.cancel()
            if len(self.tasks) == 0:
                _log.info("No tasks in Repeater queue; quitting")
                self.running = 0
                break
            safesleep(self.poll_interval)
        for task in self.tasks:
            if task.at_exit:
                try:
                    _log.info("Running task %s at exit" % (task.name))
                    task.run(force=1)
                except Exception as e:
                    _log.exception(f'exception in at_exit run of {task.name}\nexception: {e}')

    def start(self, repeaterfile=None):
        """
        Start the repeated loop over the task list.

        *repeaterfile* is an optional filename to which the task list may
        be written.
        """

        if repeaterfile:
            # leave a trail for debugging
            rstrlist = []
            txt = 'no repeaters'
            for task in self.tasks:
                rstrlist.append(task.funcstring)
                txt = 'repeaters (check DAS_while_logging.log for timers):\n\n'
                txt += '\n'.join(rstrlist) + '\n'
            with open(repeaterfile,'w') as file:
                file.write(txt)
            _log.info('writing repeaterlist to %s' % (repeaterfile))

        self._start()

    def stop(self):
        '''Stop the loop.
        This might be useful only in a gui context, which might
        in turn require other changes.
        '''
        self.running = 0


# Backwards compatibility
repeater = Repeater
periodic = Periodic
periodic_system = PeriodicSystem

#####################################################################

def demo():
    '''Example for testing.

    This illustrates capturing python output and output
    from system commands, and redirecting it to a file.
    It also shows the use of a sentinal file created by
    the program, the deletion of which stops the loop.
    '''
    import logging
    from pycurrents.system.logutils import formatterTLN
    log = logging.getLogger()
    log.handlers[0].setFormatter(formatterTLN)

    log.setLevel(logging.DEBUG)
    sys.stdout = open('test.tmp', 'w')
    open("/tmp/repeater_test", 'w').close() # make a flag file
    def file_present():
        return os.path.exists("/tmp/repeater_test")
    def printer(s):
        print(s, time.time())
    log.info('Starting the repeater example.')
    R = Repeater(condition = file_present, poll_interval = 0.2, timeout = 5)

    # Run shell commands via shell:
    R.add(PeriodicSystem("ls -ltr | tail -2",
                            shell=True,
                            interval = 2, name="lister"))

    # If the shell is not needed, don't use it:
    R.add(PeriodicSystem("ls -ltr",
                            interval = 2, name="full_lister"))


    R.add(Periodic(printer, args = ("The time is",), interval=10,
                                           initial=10, at_exit=1,
                                           name = "time printer"))

    # This one will be timed out right away.
    R.add(PeriodicSystem("sleep 6", interval = 10, name = "sleeper"))

    R.start()
    sys.stdout.close()

if __name__ == '__main__':
    demo()
