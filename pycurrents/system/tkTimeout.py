import time

class Timeout:
    """ Timeout timer for use with Tkinter.
    It uses repeated calls to "after" instead of a single
    call to "after" with a long timeout, because the
    "cancel" routine seems to have a memory leak.
    """
    def __init__(self, master, poll = 1, timeout = 1000, callback = None):
        self.__callback = callback
        self.__poll_ms = int(1000 * poll)
        self.__timeout = timeout
        self.__running = 0
        self.__master = master

    def start(self):
        self.__last_time = time.time()
        self.__run = 1
        if not self.__running:
            self.__master.after(self.__poll_ms, self.__check)
            self.__running = 1

    def stop(self):
        self.__run = 0

    def __check(self):
        if not self.__run:
            self.__running = 0
            return
        if time.time() - self.__last_time > self.__timeout:
            self.__callback()
        self.__master.after(self.__poll_ms, self.__check)
        self.__running = 1
