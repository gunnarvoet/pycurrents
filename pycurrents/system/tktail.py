'''Pop up a window that tails a file.

   This is somewhat like "tail -f" in an xterm, but should be portable
   to Windows.  Unlike tail, it displays only whole lines.

   Things to add: a line count display;
                  a control to disable/enable the "see(END)"
                  decent fonts
                  wrap control
                  command-line options
'''

# EF 2004/09/28

import sys
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

usage = '''
Usage: tktail <filename>
   where <filename> must refer to a file that already
   exists and is readable.
'''

def no_action(event):
    return "break"


class tail(object):
    def __init__(self, filename, master=None, max_lines = 100, **kw):
        self.file = open(filename)
        self.max_lines = max_lines
        if master is None:
            master = tk.Tk()
            master.title(filename)
        self.text = ScrolledText(master, **kw)
        self.text.pack(fill=tk.BOTH, expand=tk.TRUE)
        self.text.bind("<KeyPress>", no_action)
        self.run()

    def run(self):
        lines = self.file.readlines()
        if len(lines) > 0:
            self.text.insert(tk.END, ''.join(lines[-self.max_lines:]))
            self.text.see(tk.END)
            self.text.delete('1.0', 'end - %d lines' % (self.max_lines,))
        self.text.after(100, self.run)

    def mainloop(self):
        self.text.mainloop()

def main():
    if len(sys.argv) != 2:
        print(usage)
        sys.exit()
    T = tail(sys.argv[1])
    T.mainloop()
