'''Pop up a window that tails a file.

   This is somewhat like "tail -f" in an xterm, but should be portable
   to Windows.  Unlike tail, it displays only whole lines.

   Things to add: a line count display;
                  decent fonts
                  wrap control
                  command-line options
'''
# EF 2004/09/29, derived from tktail.py

import sys
import tkinter as tk
import Pmw

usage = '''
Usage: tktail <filename>
   where <filename> must refer to a file that already
   exists and is readable.
'''

def no_action(event):
    return "break"


class tail(Pmw.LabeledWidget):
    def __init__(self, master=None, filename='', max_lines = 1000, **kw):
        if master == None:
            master = tk.Tk()
            Pmw.initialise(master)
            master.title('tail')
        kw['labelpos'] = 'n'
        kw['label_text'] = filename
        Pmw.LabeledWidget.__init__(self, master, **kw)
        self.pack(fill=tk.BOTH, expand=tk.TRUE)
        self.file = open(filename)
        self.max_lines = max_lines
        self.text = Pmw.ScrolledText(self.interior())
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.TRUE)
        self.text.bind("<KeyPress>", no_action)
        self.BVend = tk.BooleanVar()
        self.BVend.set(True)
        self.CBend = tk.Checkbutton(self.interior(), text="view end",
                                   variable=self.BVend,
                                   onvalue=True,
                                   offvalue=False)

        self.CBend.pack(side=tk.TOP, fill=tk.NONE, expand=tk.FALSE, anchor=tk.E)
        self.run()

    def run(self):
        lines = self.file.readlines()
        if len(lines) > 0:
            self.text.insert(tk.END, ''.join(lines[-self.max_lines:]))
            if self.BVend.get():
                self.text.see(tk.END)
            #self.text.appendtext(''.join(lines[-self.max_lines:]))
            self.text.delete('1.0', 'end - %d lines' % (self.max_lines,))
        self.text.after(100, self.run)

    def mainloop(self):
        self.text.mainloop()

def main():
    if len(sys.argv) != 2:
        print(usage)
        sys.exit()
    T = tail(filename=sys.argv[1])
    T.mainloop()
