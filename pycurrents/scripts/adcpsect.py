#! /usr/bin/env python
''' adcpsect.py
    Interface to retrieve db name & output path in order
    to run adcpsect_part2.py (the core program).

    Usage:

    NEW: if not provided, database path will be guessed from
              from current working directory


      adcpsect.py [-d PATH/adcpdb/dbname] [-o 'subdir']
      adcpsect.py [--dbname PATH/adcpdb/dbname] [--outdir 'subdir']


'''

import os
import glob
from optparse import OptionParser

from tkinter import filedialog
from tkinter import messagebox
import tkinter as tk

from  pycurrents.adcp.uhdasfile import guess_dbname


# Optional command line prelims________________

parser = OptionParser(__doc__)
parser.add_option("-d",  "--dbname", dest="dbname",
       help="path to database name (including database name base)")

parser.add_option("-o", "--outdir", dest="outdir",
       help="write adcpsect output in this directory")


(options, args) = parser.parse_args()


if options.dbname is None:
    print('guessing database name from current working directory,')
    print(os.getcwd())
    dbname = guess_dbname('./')
else:
    print('guessing database name from %s ' % (options.dbname))
    dbname = guess_dbname(options.dbname)
print('found database %s' % (dbname))



if options.outdir is None:
    outdir = None
elif os.path.isdir(options.outdir):
    outdir = options.outdir
    print('outdir is %s' % (outdir))
else:
    outdir = None


if outdir is None:
    nchar = len(os.getcwd())
else:
    nchar = len(outdir)
FRAMEWIDTH = max(450, 10*nchar)
NCHAR = max(40, nchar)
#print 'NCHAR is ', NCHAR, '; FRAMEWIDTH is', FRAMEWIDTH


#### end optionals ____________________________


mainwindow = tk.Tk()
mainwindow.title('    ADCP Processing: Database Entry Form')
mainwindow.geometry('+300+200')


class Formdb(object):
    def __init__(self, master = None, framewidth=450,textwidth=50):
        self.master = master
        self.stopflag = 0
        self.f1 =  tk.Frame(master, width = framewidth, height = 200, relief = tk.RAISED, bd = 2)
        self.lbldbname = tk.Label(self.f1, text = 'dbname is %s' % (dbname),
                         fg = 'dark blue',font = (('MS','Sans','Serif'),'12'))
        self.dbname = dbname #from above

        self.lbloutpath = tk.Label(self.f1, text = 'Enter output path:',
                                fg = 'dark blue',font = (('MS','Sans','Serif'),'14','bold'))
        self.outp = tk.StringVar()
        if outdir is None:
            self.outp.set(os.getcwd())
        else:
            self.outp.set(os.path.relpath(outdir))
        self.editoutpath = tk.Entry(self.f1, textvariable = self.outp,
                                width = textwidth, bg = 'white')
        self.btnoutp = tk.Button(self.f1, text = '. . .', width = 1,
                                font = (('MS','Sans','Serif'),'9','bold'),
                                command = self.filefindop, state = tk.NORMAL)

        self.btnOK = tk.Button(self.f1, text = '   OK   ', command = self.btnOKed,fg = 'blue')
        self.btnCancel = tk.Button(self.f1, text = 'Exit', command = self.f1.quit)

        ####___________________________________
        self.f1.pack()

        self.lbldbname.place(relx = .5, rely = .25, anchor = tk.CENTER)

        self.lbloutpath.place(relx = .5, rely = .5, anchor = tk.CENTER)
        self.editoutpath.place(relx = .87, rely = .63, anchor = tk.E)
        self.btnoutp.place(relx = .87, rely = .63, anchor = tk.W)

        self.btnCancel.place(relx = .2, rely = .85, anchor = tk.W)
        self.btnOK.place(relx = .8, rely = .85, anchor = tk.E)
        ####___________________________________


    def filefindop(self):
        x = 1
        while x == 1:
            findout = filedialog.FileDialog(self.f1)
            findout.top.geometry('+300+200')
            cntop = findout.go()  #  using pwd
            if cntop is None:
                print('cancelled')
                x = 2
            else:
                self.outp.set(os.path.relpath(cntop))
                if os.path.isdir(cntop):
                    x = 2
                else:
                    messagebox.showerror('Output path name','Invalid path, or = file')

    def outpathchk(self): # validate
        if not os.path.isdir(displayone.outp.get()):
            displayone.stopflag = 1
            messagebox.showerror('Output path name','Invalid path, or = file')
        lck = displayone.outp.get()
        if lck[-1:] == '/':
            lck = lck[:-1]
            displayone.outp.set(lck)

    def timechk(self): # validate
        if len(self.tr) < 10:
            displayone.stopflag = 1
            messagebox.showerror('','Time range incorrect or not found')

    def establishtimes(self):
        # assumes adcptree directory structure
        dbdir, dbshortfn = os.path.split(self.dbname)
        basedir = os.path.split(dbdir)[0]
        trfile = '%s/scan/%s.tr' %(basedir, dbshortfn)
        trfile2 = '%s/scan/*.tr' %(basedir)
        trfle = glob.glob(trfile2)
        if os.path.exists(trfile):  # first try to find *.tr file (much faster)
            trf = open(trfile, 'r')
            strlist = trf.readline().strip()
            #print 'timerange is<' + strlist + '>'
            trf.close()
            self.tr = '"' + strlist + '"'
            #self.tr = '%s%s%s%s' \
            #          %(strlist[0:10], strlist[11:19], \
            #            strlist[23:33], strlist[34:])
        elif os.path.exists(trfle[0]):  # still much faster
            trf = open(trfle[0], 'r')
            strlist = trf.readline().strip()
            #print 'timerange is<'+ strlist + '>'
            trf.close()
            self.tr = '"' + strlist + '"'
            #self.tr = '%s%s%s%s' \
            #          %(strlist[0:10], strlist[11:19], \
            #            strlist[23:33], strlist[34:])
        else:
            print('THIS MAY TAKE A MINUTE !')
            db = self.dbname
            filen = '%s/g_prof.lst' %(self.outp.get())
            lstprof_cnt_str = '''
                dbname:             %(db)s
                output:             %(filen)s
                step_size:          1
                time_ranges:
                        all
                '''
            fname = '%s/g_lstprof.cnt' %(self.outp.get())
            lstpf = open(fname, 'w')
            lstpf.write(lstprof_cnt_str % dict(db=db, filen=filen))
            lstpf.close()
            runstr = 'lst_prof %s' %(fname)
            os.system(runstr)
            lstout = open(filen, 'r')
            strlist = [line.strip() for line in lstout.readlines()]
            #print 'timerange is<' + strlist + '>'
            lstout.close()
            os.remove(fname)
            os.remove(filen)
            #endstr2 = strlist[-2] # chg. to reg. expression later ?
            #begstr5 = strlist[5]
            self.tr = '"' + strlist + '"'
            #self.tr = '%s%s%s%s' \
            #          %(begstr5[0:10], begstr5[12:20], \
            #            endstr2[0:10], endstr2[12:20])

    def btnOKed(self):
        displayone.stopflag = 0
        displayone.outpathchk()
        displayone.establishtimes()
        displayone.timechk()
        if not displayone.stopflag:
            mainwindow.withdraw()
            sysstr = 'adcpsect_part2.py %s %s %s' %(displayone.dbname,
                                                    os.path.relpath(displayone.outp.get()),
                                                    displayone.tr)
            print('running %s' % (sysstr))
            os.system(sysstr)
            self.btnCancel.invoke()


displayone = Formdb(mainwindow, framewidth=FRAMEWIDTH, textwidth=NCHAR)
#if __name__ ==  '__main__':
mainwindow.mainloop()
