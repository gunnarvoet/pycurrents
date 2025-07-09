''' Classes for controlling groups of threads that execute
      tasks periodically.

      The problem with simpler ways of launching and killing
      sets of threads that do repetitive tasks is that one
      usually uses time.sleep to control the repetition (or
      polling), leading to a delay in killing each thread.

      The approach used here is to start a single control
      thread that frequently checks a flag variable.  When
      the variable is false, the control thread exits. All
      the other threads in the group are waiting until
      either a time increment is over or the control thread
      dies; they loop as soon as the latter occurs, so they
      immediately see the changed flag variable and exit.
'''

# 2004/10/06 EF Added the poll_dt and function arguments,
#               plus more documentation; changed the
#               method of giving the control thread
#               access to the ThreadGroup flag.

# 2002/08/22 EF

from threading import Thread
from pycurrents.system.misc import sleep as safesleep

class controlThread(Thread):
    '''This thread exists solely to provide a means of
    signalling other threads in the group that the group
    is being stopped, without each thread having to poll
    the is_running function.  Instead, the control thread
    does the polling, and other threads use a timer which
    joins it.  See ThreadGroup.timer.
    '''
    def __init__(self, keep_running, poll_dt):
        '''is_running is a function, returns True if the group is running
        '''
        Thread.__init__(self)
        self.setDaemon(1)
        self.poll_dt = poll_dt
        self.keep_running = keep_running

    def run(self):
        while self.keep_running():
            safesleep(self.poll_dt)



class ThreadGroup:
    '''A group of worker threads plus a control thread to stop them all.

    Two methods of stopping the threads are provided.  First,
    the stop() method of the ThreadGroup can be called.  It
    sets a flag.  At intervals of poll_dt, the control thread
    checks this flag and dies if it is zero.  Then any thread
    waiting on the ThreadGroup.timer, or checking the same
    flag via the check_running() method, will exit.  If the
    optional function argument is supplied to the ThreadGroup initializer,
    then it will be called at the same time as the flag, and
    a False return will have the same effect as setting the flag.
    An example of such a function would be os.path.exists(filename).
    Deleting the file would then signal the threads to stop.
    '''
    def __init__(self, poll_dt = 0.2, keep_running = None):
        self.running = 1
        if keep_running:
            self._keep_running = keep_running
        else:
            self._keep_running = lambda : True
        self.cThread = controlThread(self.keep_running, poll_dt)
        self.threadList = []
        self.add(self.cThread)

    def timer(self, t):
        ''' Timer function to be used by a thread. '''
        self.cThread.join(t)  # Blocks for time t, or until cThread dies.
                              # Returns if called after cThread dies.

    def keep_running(self):
        ''' Loop control function for a thread.'''
        return self.running and self._keep_running()

    def add(self, T):
        ''' Register a new thread T in the group. '''
        self.threadList.append(T)

    def start(self):
        ''' Start all threads currently registered. '''
        self.running = 1
        for T in self.threadList:
            T.start()

    def number_alive(self):
        return len([1 for T in self.threadList if T.is_alive()])

    def stop(self, seconds = 2, timer = None):
        ''' Signal all threads to stop, and return when all
        have stopped.  Wait up to "seconds" for threads to
        stop before returning.  "timer" is a timer function,
        accepting a timeout in floating point seconds as an
        argument.  Return the number of threads still alive.'''
        self.running = 0
        if timer is None:
            timer = safesleep
        nloops = int(seconds/0.1)
        for ii in range(nloops):
            timer(0.1)
            N = self.number_alive()
            if N == 0:
                break
        self.threadList = []
        return N

class repeatThread(Thread):
    ''' This is like a regular thread, except that the
    target is a function that will be executed repeatedly
    by a loop inside the run method. It is simply an example
    of one useful type of thread that can be in a threadgroup.
    The start() method is inherited from Thread.
    '''
    def __init__(self, Tgroup, interval = 1, target = None,
                 name = None, args = (), kwargs = {}):
        Thread.__init__(self, name = name)
        self.setDaemon(1)  # So it will always exit if main thread ends.
        self.interval = interval
        self.Tgroup = Tgroup
        self.timer = Tgroup.timer
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs

    def run(self):
        self.name = self.getName()
        print("%s starting" % self.name)
        fn = self.__target
        args = (self,) + self.__args
        while self.Tgroup.keep_running():
            fn(*args, **self.__kwargs)
            self.timer(self.interval)
        print("%s ending" % self.name)


# Test; illustration of how to use the ThreadGroup and subThread

if __name__ == "__main__":
    import sys
    from tkinter import Tk, Button

    def fn1(self, otherstuff, dict_arg1, dict_arg2):
        print(self.name)
        print(otherstuff)
        print(dict_arg1 + dict_arg2)

    def fn2(self):
        print(self.name)
        print("This function only prints its name")

    tg = ThreadGroup()
    tg.add(repeatThread(name = "test_1", target = fn2, Tgroup = tg, interval = 3.1))
    tg.add(repeatThread(name = "test_2", target = fn1, Tgroup = tg, interval = 2,
                     args = ('otherstuff--args',),
                     kwargs = {'dict_arg1': 'DictArg1',
                               'dict_arg2': 'DictArg2'}))
    tg.add(repeatThread(name = "test_3", target = fn2, Tgroup = tg, interval = 1.05))
    tg.start()


    def quit():
        tg.stop()
        #raise SystemExit
        b.configure(text = "Exit", command = sys.exit)

    root = Tk()
    root.option_add('*Button.activeBackground', 'yellow')
    b = Button(root, text = "Stop all threads!", command = quit)
    b.pack(padx=20, pady=20)
    root.mainloop()
