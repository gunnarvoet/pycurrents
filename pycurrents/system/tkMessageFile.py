""" Objects with write methods, for use with tee.py.
"""

# 2002/08/27 EF

import tkinter as tk
from tkinter.messagebox import showwarning, showerror

class tkWarningFile:
    def __init__(self, title = None):
        self.title = title

    def write(self, str):
        showwarning(title = self.title, message = str)

class tkErrorFile:
    def __init__(self, title = None):
        self.title = title

    def write(self, str):
        showerror(title = self.title, message = str)

class tkStringVarFile:
    def __init__(self, mode = 'w'):  # 'w' to overwrite, 'a' to append
        self.SV = tk.StringVar()
        self.mode = mode

    def write(self, str):
        if self.mode == 'w':
            self.SV.set(str)
        else:
            ss = self.SV.get()
            self.SV.set(ss + str)

    def rewind(self):
        self.SV.set('')

# More could be added...


if __name__ == "__main__":
    msg = '''
 1. This is an example error message.  It is rather long.
 2. This is an example error message.  It is rather long.
 3. This is an example error message.  It is rather long.
 4. This is an example error message.  It is rather long.
 5. This is an example error message.  It is rather long.
 '''
    tEF = tkErrorFile(title = "tkErrorFile test")
    tEF.write(msg)
