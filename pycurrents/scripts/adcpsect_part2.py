#! /usr/bin/env python
''' adcpsect_part2.py  Interface to retrieve minimum input necessary to run the
gridding program(s) and run adcpsect in order to produce
the data files needed for the plotting programs.
   Usage: >adcpsect.py  --> which calls this -->adcpsect_part2.py 1 2
   (from adcpsect.py), where:
       sys.argv[1] is the database name (as *dir.blk)
       sys.argv[2] is the output path
'''

import os
import sys
import os.path
from tkinter import filedialog
from tkinter import messagebox
import tkinter as tk
# do not import Pmw

mainwindow2 = tk.Tk()
mainwindow2.title('           ADCP Data Processing')
mainwindow2.geometry('+200+100')

class ADCPproc(object):
    def __init__(self, master = None):
        self.master = master
        self.stopflag = 0
        self.f1 =  tk.Frame(master, width = 650, height = 425, relief = tk.RAISED, bd = 2)
        self.lbltitle =  tk.Label(self.f1, text = 'ADCP DATA SETUP',
                               font = (('MS','Sans','Serif'),'18'), fg = 'blue' )
        self.dbname = sys.argv[1]
        self.pnout = tk.StringVar()
        self.pnout.set(os.path.relpath(sys.argv[2]))
        self.lbldbname =  tk.Label(self.f1, text = 'Using: ' + self.dbname)
        self.lbloutpath =  tk.Label(self.f1, text = 'Outpath: ' + self.pnout.get())

        self.lblvertical = tk.Label(self.f1, text = 'Vertical grid:', relief = tk.RAISED, bg = 'light blue')
        self.varvert = tk.IntVar()
        self.radiovg = tk.Radiobutton(self.f1, text = 'Increment', variable = self.varvert, value = 1,
                                   command = self.toggle_vert)
        self.lblvgstart = tk.Label(self.f1, text = 'Start at (m):')
        self.vgstart = tk.StringVar()
        self.vgstart.set('21')
        self.editvg = tk.Entry(self.f1, textvariable = self.vgstart,
                             width = 5, bg = 'white')
        self.lblvginc = tk.Label(self.f1, text = 'Vert. increment (m):')
        self.vginc = tk.StringVar()
        self.vginc.set('10')
        self.editvginc = tk.Entry(self.f1, textvariable = self.vginc,
                             width = 5, bg = 'white')
        self.lblvgpts = tk.Label(self.f1, text = 'No. of pts.:') #,state = DISABLED
        self.vgpts = tk.StringVar()
        self.vgpts.set('45')
        self.editvgpts = tk.Entry(self.f1, textvariable = self.vgpts,
                             width = 5, bg = 'white') #,state = DISABLED, fg = 'gray'


        self.radiovb = tk.Radiobutton(self.f1, text = 'Boundaries', variable = self.varvert, value = 2,
                                   command = self.toggle_vert)
        self.vb = tk.StringVar()
        self.vb.set('25 75 125 175 225 275 325 375 425') #('21 50 75 100 200 300 400')
        self.editvb = tk.Entry(self.f1, textvariable = self.vb,
                             width = 23, bg = 'white', state = tk.DISABLED, fg = 'gray')


        self.lblbins =  tk.Label(self.f1, text = 'No. bins:')
        self.bins = tk.StringVar()
        self.bins.set('60')
        self.editbins = tk.Entry(self.f1, textvariable = self.bins,
                                 width = 7, bg = 'white')

        self.lblprefix =  tk.Label(self.f1, text = "Outfiles' prefix:")
        self.prefix = tk.StringVar()
        self.prefix.set('c_sect')
        self.editprefix = tk.Entry(self.f1, textvariable = self.prefix,
                                 width = 7, bg = 'white')

        self.lbltimerange =  tk.Label(self.f1, text = 'Time range:',relief = tk.RAISED, bg = 'light blue')
        self.timerange = tk.StringVar()
        #trtight = sys.argv[3] # compressed to send as single arg
        #tr = '%s %s to %s %s' %(trtight[0:10], trtight[10:18], trtight[18:28], trtight[28:])
        tr = sys.argv[3]
        print('timerange is<' + tr + '>')
        self.timerange.set(tr)
        self.edittimerange = tk.Entry(self.f1, textvariable = self.timerange,
                                 width = 36, bg = 'white')

        self.yearbase = tk.StringVar()
        #self.yearbase.set(trtight[0:4])
        self.yearbase.set(tr[0:4])
        self.lblyear =  tk.Label(self.f1, text = 'Year base:')
        self.edityear = tk.Entry(self.f1, textvariable = self.yearbase,
                                 width = 7, bg = 'white')

        self.lblnavref = tk.Label(self.f1, text  = 'Navigation reference:', relief = tk.RAISED, bg = 'light blue')
        self.varnav = tk.IntVar()
        self.radionavship = tk.Radiobutton(self.f1, text = 'Final ship ref', variable = self.varnav, value = 1)
        self.radionavbottom = tk.Radiobutton(self.f1, text = 'Bottom track', variable = self.varnav, value = 2)

        self.lblcontour = tk.Label(self.f1, text = 'ASCII contour file ordinate:', relief = tk.RAISED, bg = 'light blue')
        self.varcont_ord = tk.IntVar()
        self.radiocont_none = tk.Radiobutton(self.f1, text = 'No file', variable = self.varcont_ord, value = 1)
        self.radiocont_lat = tk.Radiobutton(self.f1, text = 'Latitude (.con) file', variable = self.varcont_ord, value = 2)
        self.radiocont_lon = tk.Radiobutton(self.f1, text = 'Longitude (.con) file', variable = self.varcont_ord, value = 3)
        self.radiocont_time = tk.Radiobutton(self.f1, text = 'Time (.con) file', variable = self.varcont_ord, value = 4)

        self.lblvector = tk.Label(self.f1, text = 'ASCII vector file:', relief = tk.RAISED, bg = 'light blue')
        self.varvec = tk.BooleanVar()
        self.checkvec = tk.Checkbutton(self.f1, text = 'Yes (.vec) file <off = none>',
                                    variable = self.varvec)

        self.lblgrid = tk.Label(self.f1, text = 'Extract data by:', relief = tk.RAISED, bg = 'light blue')
        self.lblgrid2 = tk.Label(self.f1, text = '----------------------------------------------------------------------')
        self.vargrid = tk.IntVar()
        self.radiotimegrid = tk.Radiobutton(self.f1, text = 'Time grid (mins):', variable = self.vargrid,
                                       value = 1, command = self.toggle_extract)
        self.time = tk.StringVar()
        self.time.set('60')
        self.edittime = tk.Entry(self.f1, textvariable = self.time,
                                    width = 5, bg = 'white', fg = 'gray', state = tk.DISABLED)

        self.radiollgrid = tk.Radiobutton(self.f1, text = 'Lat/Lon grid (step):', variable = self.vargrid,
                                       value = 2, command = self.toggle_extract)
        self.ll = tk.StringVar()
        self.ll.set('0.1')
        self.editll = tk.Entry(self.f1, textvariable = self.ll,
                                    width = 5, bg = 'white')
        self.radiotrack = tk.Radiobutton(self.f1, text = 'Track dist. (km):', variable = self.vargrid,
                                       value = 3, command = self.toggle_extract, state = tk.DISABLED)
        self.distance = tk.StringVar()
        self.distance.set('10')
        self.editdistance = tk.Entry(self.f1, textvariable = self.distance,
                                  width = 5, bg = 'white', state = tk.DISABLED,
                                  fg = 'gray')
        self.radioall = tk.Radiobutton(self.f1, text = 'All profiles', variable = self.vargrid,
                                       value = 4, command = self.toggle_extract)
        self.radiopreviousfile = tk.Radiobutton(self.f1, text = 'Previous file:', variable = self.vargrid,
                                       value = 5, command = self.toggle_extract)
        self.pfile = tk.StringVar()
        self.pfile.set(os.path.relpath(self.pnout.get()))
        self.editpfile = tk.Entry(self.f1, textvariable = self.pfile,
                                 width = 33, bg = 'white', fg = 'gray', state = tk.DISABLED)
        self.btnpfile = tk.Button(self.f1, text = '. . .', width = 1,
                                font = (('MS','Sans','Serif'),'9','bold'),
                                command = self.filefindprev, state = tk.DISABLED)

        self.lblscale = tk.Label(self.f1, text = 'PG cutoff:')
        self.scale = tk.StringVar()
        self.scale.set('50')
        self.editscale = tk.Entry(self.f1, textvariable = self.scale,
                                 width = 7, bg = 'white')

        self.btnOK = tk.Button(self.f1, text = 'Run adcpsect', command = self.btnOKed, fg = 'blue')
        self.btnCancel = tk.Button(self.f1, text = 'Exit', command = self.f1.quit)
        self.btnBack = tk.Button(self.f1, text = 'Back...', command = self.backup, fg = 'dark blue')

#_______________________________________________

        self.f1.pack()
        self.lbltitle.place(relx = .5, rely = .07, anchor = tk.CENTER)
        self.lbldbname.place(relx = .5, rely = .14, anchor = tk.CENTER)
        self.lbloutpath.place(relx = .5, rely = .18, anchor = tk.CENTER)

        self.lblvertical.place(relx = .05, rely = .25, anchor = tk.W)
        self.radiovg.place(relx = .05, rely = .3, anchor = tk.W)# Increment
        self.lblvgstart.place(relx = .09, rely = .35, anchor = tk.W)#'Start at (m):')
        self.editvg.place(relx = .29, rely = .35, anchor = tk.W) # '30'
        self.lblvginc.place(relx = .09, rely = .4, anchor = tk.W)# 'Vert. increment (m):')
        self.editvginc.place(relx = .29, rely = .4, anchor = tk.W) # '20'
        self.lblvgpts.place(relx = .09, rely = .45, anchor = tk.W)#'No. of pts.:')
        self.editvgpts.place(relx = .29, rely = .45, anchor = tk.W)# '20'

        self.radiovb.place(relx = .05, rely = .5, anchor = tk.W)# Boundaries
        self.editvb.place(relx = .09, rely = .55, anchor = tk.W)

        self.lblnavref.place(relx = .72, rely = .25, anchor = tk.W)
        self.radionavship.place(relx = .72, rely = .3, anchor = tk.W)
        self.radionavbottom.place(relx = .72, rely = .35, anchor = tk.W)

        self.lblvector.place(relx = .39, rely = .25, anchor = tk.W)
        self.checkvec.place(relx = .39, rely = .3, anchor = tk.W)

        self.lblcontour.place(relx = .39, rely = .375, anchor = tk.W)
        self.radiocont_none.place(relx = .39, rely = .425, anchor = tk.W)
        self.radiocont_lat.place(relx = .39, rely = .47, anchor = tk.W)
        self.radiocont_lon.place(relx = .39, rely = .52, anchor = tk.W)
        self.radiocont_time.place(relx = .39, rely = .57, anchor = tk.W)

        self.lblyear.place(relx = .84, rely = .42, anchor = tk.E)
        self.edityear.place(relx = .84, rely = .42, anchor = tk.W)
        self.lblbins.place(relx = .84, rely = .47, anchor = tk.E)
        self.editbins.place(relx = .84, rely = .47, anchor = tk.W)
        self.lblprefix.place(relx = .84, rely = .52, anchor = tk.E)
        self.editprefix.place(relx = .84, rely = .52, anchor = tk.W)
        self.lblscale.place(relx = .84, rely = .57, anchor = tk.E)
        self.editscale.place(relx = .84, rely = .57, anchor = tk.W)

        self.lblgrid.place(relx = .05, rely = .63, anchor = tk.W)
        self.lblgrid2.place(relx = .24, rely = .63, anchor = tk.W)
        self.radiotimegrid.place(relx = .05, rely = .68, anchor = tk.W)
        self.edittime.place(relx = .29, rely = .68, anchor = tk.W) # '30'
        self.radiollgrid.place(relx = .05, rely = .73, anchor = tk.W)
        self.editll.place(relx = .29, rely = .73, anchor = tk.W) # '0.1'
        self.radiopreviousfile.place(relx = .05, rely = .78, anchor = tk.W)
        self.radiotrack.place(relx = .39, rely = .68, anchor = tk.W)
        self.editdistance.place(relx = .59, rely = .68, anchor = tk.W) # '10'
        self.radioall.place(relx = .39, rely = .73, anchor = tk.W)
        self.editpfile.place(relx = .09, rely = .83, anchor = tk.W)
        self.btnpfile.place(relx = .46, rely = .83, anchor = tk.W)

        self.lbltimerange.place(relx = .54, rely = .77, anchor = tk.W)
        self.edittimerange.place(relx = .54, rely = .83, anchor = tk.W)

        self.btnCancel.place(relx = .3, rely = .925, anchor = tk.E)
        self.btnBack.place(relx = .54, rely = .925, anchor = tk.E)
        self.btnOK.place(relx = .65, rely = .925, anchor = tk.W)
#_______________________________________________

        inweb = os.getcwd().find('htdocs')
        if inweb > -1:
            self.time.set('15')
            self.vargrid.set(1)
            self.toggle_extract


    def toggle_vert(self):
        if self.varvert.get() == 1:
            self.lblvgstart.configure(state = tk.NORMAL)
            self.editvg.configure(fg = 'black')
            self.editvg.configure(state = tk.NORMAL)
            self.lblvginc.configure(state = tk.NORMAL)
            self.editvginc.configure(state = tk.NORMAL)
            self.editvginc.configure(fg = 'black')
            self.lblvgpts.configure(state = tk.NORMAL)
            self.editvgpts.configure(fg = 'black')
            self.editvgpts.configure(state = tk.NORMAL)

            self.editvb.configure(state = tk.DISABLED, fg = 'gray')

            self.vargrid.set(2)
            self.toggle_extract()
            self.prefix.set('c_sect')
        else:
            self.lblvgstart.configure(state = tk.DISABLED)
            self.editvg.configure(fg = 'gray')
            self.editvg.configure(state = tk.DISABLED)
            self.lblvginc.configure(state = tk.DISABLED)
            self.editvginc.configure(state = tk.DISABLED)
            self.editvginc.configure(fg = 'gray')
            self.lblvgpts.configure(state = tk.DISABLED)
            self.editvgpts.configure(fg = 'gray')
            self.editvgpts.configure(state = tk.DISABLED)

            self.editvb.configure(state = tk.NORMAL, fg = 'black')

            self.vargrid.set(1)
            inweb = os.getcwd().find('htdocs')
            if inweb > -1:
                self.time.set('60')
            self.toggle_extract()
            self.prefix.set('v_sect')


    def toggle_extract(self):
        self.radiocont_lat.configure(state = tk.NORMAL) # may have been disabled with ALL
        self.radiocont_lon.configure(state = tk.NORMAL)
        self.radiocont_time.configure(state = tk.NORMAL)
        if self.vargrid.get() == 1: # on time
            self.edittime.configure(fg = 'black', state = tk.NORMAL)
            self.editll.configure(fg = 'gray', state = tk.DISABLED)
            self.editpfile.configure(fg = 'gray', state = tk.DISABLED)
            self.btnpfile.configure(state = tk.DISABLED)
        elif self.vargrid.get() == 2: # on lat/long
            self.edittime.configure(fg = 'gray', state = tk.DISABLED)
            self.editll.configure(fg = 'black', state = tk.NORMAL)
            self.editpfile.configure(fg = 'gray', state = tk.DISABLED)
            self.btnpfile.configure(state = tk.DISABLED)
        elif self.vargrid.get() == 4:  # on all
            self.edittime.configure(fg = 'gray', state = tk.DISABLED)
            self.editll.configure(fg = 'gray', state = tk.DISABLED)
            self.editpfile.configure(fg = 'gray', state = tk.DISABLED)
            self.btnpfile.configure(state = tk.DISABLED)
            self.radiocont_none.select()
            self.radiocont_lat.configure(state = tk.DISABLED)
            self.radiocont_lon.configure(state = tk.DISABLED)
            self.radiocont_time.configure(state = tk.DISABLED)
        else: # == 5 with previous file
            self.edittime.configure(fg = 'gray', state = tk.DISABLED)
            self.editll.configure(fg = 'gray', state = tk.DISABLED)
            self.editpfile.configure(fg = 'black', state = tk.NORMAL)
            self.btnpfile.configure(state = tk.NORMAL)

    def filefindprev(self):
        findprev = filedialog.FileDialog(self.f1)
        pattern = self.prefix.get() + '.*'
        pv = findprev.go(display.pfile.get(),pattern)
        if pv is None: 
            print('cancelled')
        else:
            self.pfile.set(os.path.relpath(pv))

    def llgrid(self):
        dbn = display.dbname
        outf = '%s/%s.llg' %(self.pnout.get(), self.prefix.get())
        year_base = self.yearbase.get()
        latint = self.ll.get()
        lonint = self.ll.get()
        lato = -0.5*float(latint)
        lono = -0.5*float(lonint)
        tr = display.timerange.get()
        # Trick to thwart pyflakes "assigned to but never used":
        (dbn, outf, year_base, latint, lato, lono, lonint, tr)

        ll_cnt_str = '''
          dbname:             %(dbn)s
          output:             %(outf)s
          year_base:          %(year_base)s
          step_size:          1        /* must be 1 for navigation */

          lat_origin:           %(lato).2f
          lat_increment:        %(latint)s
          lon_origin:           %(lono).2f
          lon_increment:        %(lonint)s

          time_ranges:          %(tr)s

        '''
        fname = '%s/%s_llg.cnt' %(self.pnout.get(), self.prefix.get())
        ll_template = open(fname, 'w')
        ll_template.write(ll_cnt_str % vars())
        ll_template.close()
        runstr = 'llgrid %s' %(fname)
        os.system(runstr)
        self.gridfilename = outf

    def timegrid(self):
        filen = '%s/%s.tmg' %(self.pnout.get(), self.prefix.get())
        t_int = display.time.get()
        t_rng = display.timerange.get()
        (t_int, t_rng)  # Silence pyflakes.
        time_cnt_str = '''
            output:             %(filen)s
            time_interval:      %(t_int)s
            time_range:         %(t_rng)s
            '''
        fname = '%s/%s_tmg.cnt' %(self.pnout.get(), self.prefix.get())
        time_template = open(fname, 'w')
        time_template.write(time_cnt_str % vars())
        time_template.close()
        runstr = 'timegrid %s' %(fname)
        os.system(runstr)
        self.gridfilename = filen

    def backup(self):
        mainwindow2.withdraw()
        sysstr = 'adcpsect.py -d %s -o %s' %(display.dbname,
                                          display.pnout.get())
        os.system(sysstr)
        self.btnCancel.invoke()

    def btnOKed(self):
        dbname = display.dbname
        fileoutnm = self.pnout.get() + '/' + self.prefix.get()
        ndep = self.bins.get()
        yb = self.yearbase.get()
        regridline = '''
            regrid:           average
                              depth
            '''
        timer = 'separate'
        vgstart = self.vgstart.get()
        vginterval = self.vginc.get()
        vgpoints = self.vgpts.get()
        vboundaries = self.vb.get().strip()
        vboundaries = vboundaries.replace('  ', ' ')
        vboundaries = vboundaries.replace('  ', ' ')
        vboundaries = vboundaries.replace('  ', ' ')
        vbcount = vboundaries.count(' ') + 1
        if self.vargrid.get() == 1: # time grid
            self.timegrid()
        if self.vargrid.get() == 2: # lat/long grid
            self.llgrid()
        if self.vargrid.get() == 5: # use previous file (3: unavail, 4: above)
            self.gridfilename = self.pfile.get()
        if self.varvert.get() == 1: # increments
            gridline1 = 'grid number= %s' %vgpoints
            gridline2 = 'origin= %s' %vgstart
            gridline3 = 'increment= %s' %vginterval
        else:
            gridline1 = 'grid_list number= %d' %vbcount
            gridline2 = 'boundaries: %s' %vboundaries
            gridline3 = ' '
        if self.vargrid.get() == 4: # all
            gridfilenm = display.timerange.get()  #'all'
            timer = 'single'
            messagebox.showinfo('Note','This may take several minutes.')
        else:
            gridfilenm = '@ %s' %(self.gridfilename) # needed to isolate 'all' version
        pgmin = display.scale.get()
        if self.varnav.get() == 1:
            reftype = 'final_ship_ref'
        else:
            reftype = 'bottom_track'

        conttype = self.varcont_ord.get()
        if conttype == 1:   # no file
            contline1 = ' '
            contline2 = ' '
        elif conttype == 2: # latitude
            contline1 = 'contour: latitude\n  mean\n  minimum_npts= 2\n '
            contline2 = 'units= 5'
        elif conttype == 3: # longitude
            contline1 = 'contour: longitude\n  mean\n  minimum_npts= 2\n '
            contline2 = 'units= 5'
        else :              # time
            contline1 = 'contour: time\n  mean\n  minimum_npts= 2\n '
            contline2 = 'units= 0.01'

        if not self.varvec.get():
            vectline = ' '
        else:
            vectline = 'vector:   minimum_npts= 2'
        # Silence pyflakes:
        (dbname, fileoutnm, ndep, yb, regridline, gridline1, gridline2,
                gridline3, timer, gridfilenm, pgmin, reftype, contline1,
                contline2, vectline)

        asect_cnt_str = '''
          dbname:             %(dbname)s
          output:             %(fileoutnm)s
          step_size:          1        /* must be 1 for navigation */
          ndepth:             %(ndep)s        /* may chg to 128 */
          time_ranges:        %(timer)s
          year_base=          %(yb)s
          option_list:
            pg_min=           %(pgmin)s
            reference:        %(reftype)s
            %(regridline)s
                              %(gridline1)s
                              %(gridline2)s
                              %(gridline3)s
            %(contline1)s
            %(contline2)s
            %(vectline)s
            flag_mask:        ALL_BITS
              end
            end

          %(gridfilenm)s
        '''

        fname = '%s/%s_adcp.cnt' %(self.pnout.get(), self.prefix.get())
        as_template = open(fname, 'w')
        as_template.write(asect_cnt_str % vars())
        as_template.close()
        runstr = 'adcpsect %s/%s_adcp.cnt' %(self.pnout.get(), self.prefix.get())
        os.system(runstr)

        pre = '   ' + display.prefix.get()
        dirn, fn1 = os.path.split(fname)
        fn1 = '   ' + fn1 + '   '
        if self.vargrid.get() == 1:
            fn2 = pre + '_tmg.cnt'
        elif self.vargrid.get() == 2:
            fn2 = pre + '_llg.cnt'
        else:
            fn2 = ''
        if self.vargrid.get() == 4: 
            fn3 = ''
        else:
            dirgrid, fn3 = os.path.split(self.gridfilename)
            fn3 = '   ' + fn3
        if conttype != 1: 
            fn4 = pre + '.con'
        else: 
            fn4 = ''
        if self.varvec.get(): 
            fn5 = pre + '.vec'
        else: 
            fn5 = ''
        minout = '%s_uv.mat\n%s_xy.mat\n%s.sta' %(pre, pre, pre)
        filelist = 'Control files:      \n%s\n%s\n\nData files:\n%s\n%s\n%s\n%s' %(fn1, fn2, minout, fn3, fn4, fn5)

        chk1 = '%s/%s_uv.mat' %(dirn, pre.strip())
        chk2 = '%s/%s_xy.mat' %(dirn, pre.strip())
        chk3 = '%s/%s.sta' %(dirn, pre.strip())

        if os.path.isfile(chk1) and os.path.isfile(chk2)and os.path.isfile(chk3):
            if os.path.getsize(chk1) < 50 or os.path.getsize(chk2) < 50 or os.path.getsize(chk3) < 50:
                messagebox.showinfo('Problem','Data not extracted')
            else:
                messagebox.showinfo('Finished',filelist)
        else:
            print(chk2)
            messagebox.showinfo('Problem','Data not extracted')


display = ADCPproc(mainwindow2)
display.radiovg.select()
display.radiollgrid.select()
inweb = os.getcwd().find('htdocs')
if inweb > -1:
    display.radiotimegrid.select()
    display.edittime.configure(fg = 'black', state = tk.NORMAL) # self.toggle.extract not grabbing above ?
    display.editll.configure(fg = 'gray', state = tk.DISABLED)
display.radionavship.select()
display.radiocont_none.select()
#if __name__ ==  '__main__':
mainwindow2.mainloop()
