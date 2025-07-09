#!/usr/bin/env python3
'''
make vector-over-topography plot from codas database
or netCDF file.

- optionally save
- optionally display

plot_topovec.py [options] os75nb.nc
plot_topovec.py [options] path/to/dbname
plot_topovec.py [options] processsing_dir

'''
# to do:
#  - add option for map projection (or allow no map projection)


import os
import sys
import matplotlib

if '--noshow' in sys.argv:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

from pycurrents.system.misc import Bunch
from optparse import OptionParser

from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.dataplotter import vecplot
import pycurrents.adcp.panelplotter as pp
from pycurrents.codas import to_datestring
from pycurrents.num import rangeslice
from pycurrents.num import Stats


class Refl:
    def __init__(self, data, varnames, zrange=None, ddrange=None):
        '''
        get data from dbpath (guess_db);
        return tuple: (mean over reference layer, bins used)
        '''
        if zrange is None:
            zrange = [50,130]
        self.zrange = zrange
        self.data = data
        self.dday = self.data.dday
        self.izsl = rangeslice(self.data.dep, zrange[0], zrange[1])
        self.ref = Bunch()
        for var in varnames:
            self.ref[var] = self.get_ref(var)
    #
    def get_ref(self,varname):
        S=Stats(getattr(self.data, varname)[:,self.izsl], axis=1)
        return S.mean

#--------------------------------------------


parser = OptionParser(__doc__)
parser.add_option("--startdd" , dest="startdd",
                  help='\n'.join(["decimal day to start (default=beginning)"]))
parser.add_option("--enddd" , dest="enddd",
                  help='\n'.join(["decimal day to end (default=end)"]))
parser.add_option("--lastndays" , dest="lastndays",
                  help='\n'.join(["decimal day to start (default=beginning)"]))
parser.add_option("--cruisename", dest="cruisename",
                  help="cruise ID or title for plots (or use 'cruiseid'")
parser.add_option("--sonar", dest="sonar",
                  help="set sonar for labels, eg. os38nb, wh300, os75 (if mixed)")

parser.add_option("-z", "--zrange", dest="zrange",
                  default = '50:150',
                  help="default range 50m-150m")

parser.add_option("-o", "--outfile", dest="outfile",
                  default = None,
                  help="save figure as OUTFILE.png")

parser.add_option("--noshow", dest="noshow",
                  action="store_true",
                  default=False,
                  help="do not display figure")

parser.add_option("-d", "--showdayrange", dest="showdayrange",
                  action="store_true",
                  default=False,
                  help="output decimal day and date range of file")

parser.add_option("--vecscale", dest="vecscale",
                  default=1,
                  help='\n'.join(["basemap vector scale: default=1,",
                                 " smaller number makes longer vectors"]))

parser.add_option("--figsize", dest="figsize",
                  default="7:9",
                  help='\n'.join("figure size, colon-delimited width:height (default 7:9)"))

parser.add_option("--zoffset", dest="zoffset",
                  default=0,
                  help="altitude(m) of sea level, eg Lake SUperior=183. (default=0)")

parser.add_option("--deltat", dest="deltat",
                  default=30,
                  help="time average (minutes) for vectors, default=30min")

options, args = parser.parse_args()


if len(sys.argv[1:]) == 0:
    print(__doc__)
    sys.exit()


if len(args) != 1:
    print("choose netCDF file, adcptree directory, or path to database")
    sys.exit()

fname = args[0]

data=pp.get_data(fname)  # based on suffix

#--------------------------------------------
# show dates

# this is for the whole dataset
if options.showdayrange:
    ddaystr = 'decimal day range: %5.3f to %5.3f' % (data.dday[0], data.dday[-1])
    datestr = 'date range: %s to %s' % (to_datestring(data.yearbase, data.dday[0]),
                                to_datestring(data.yearbase, data.dday[-1]))
    dstr = '%s\n%s' % (ddaystr, datestr)

    print(dstr)
    sys.exit()

#--------------------------------------------
# set ddrange
if options.lastndays:
    ddrange = -1*float(options.lastndays)
else:
    if options.startdd is None  and options.enddd is None:
        ddrange = None #i.e. all
    elif (options.startdd and not options.enddd) or (options.enddd and not options.startdd):
        print('must use startdd AND enddd; cannot use just one')
        sys.exit()
    else:
        try:
            ddrange = (float(options.startdd), float(options.enddd))
            print('extracting decimal day range %f-%f' % (ddrange[0], ddrange[1]))
        except Exception as e:
            print('could not parse startdd and enddd', options.startdd,
                                                       options.enddd)
            print(f"threw exception {e}")
            sys.exit()

#--------------------------------------------
# set zrange
parts=options.zrange.split(':')
zrange = [int(parts[0]), int(parts[1])]

try:
    parts = options.figsize.split(':')
    width = float(parts[0])
    height = float(parts[1])
except Exception as e:
    print(f'incorrect figsize specification: {e}')
    sys.exit()
                  
#============================================
# guess sonar, for labels

if options.sonar:
    sonar=options.sonar
else:
    basename = os.path.splitext(os.path.basename(fname))[0]
    sonar_list=pp.guess_sonar(basename)
    if len(sonar_list) == 0:
        print('could not determine sonar from filename %s' % (fname))
        print('specify sonar for titles with "--sonar xxx"')
        sonar = 'SONAR'
    elif len(sonar_list) >= 2:
        print('ambiguous or multiple sonars in filename %s' % (fname))
        sys.exit()
    else:
        sonar = sonar_list[0]

#--------------------------------------------
# trim in time

shortdataT=pp.extract_ddrange(data, ddrange=ddrange)
# fill in vertical
pp.fill_masked_inplace(shortdataT)

NCD=pp.NCData(shortdataT)
if len(NCD.data.dday) <= 2:
    print('cannot make panel plot with only %d times' % (len(NCD.data.dday)))
NCD.data.dep = NCD.data.depth[0,:]

dday=NCD.data.dday
# now get the time range for that part that was extracted
ddaystr = 'decimal day range: %5.2f to %5.2f' % (dday[0], dday[-1])
datestr = 'date range: %s to %s' % (to_datestring(NCD.data.yearbase, dday[0]),
                                to_datestring(NCD.data.yearbase, dday[-1]))
dstr = '%s\n%s' % (ddaystr, datestr)



#--------------------------------------------

topofig=plt.figure(figsize=(width, height))
ax = topofig.add_subplot(111)

R = Refl(NCD.data, ['u','v'], ddrange=ddrange, zrange=zrange)

# import IPython; IPython.embed()

vecplot(R.data,
        ax=ax,
        zoffset=int(options.zoffset),
        vecscale=float(options.vecscale),
        refbins=[R.izsl.start, R.izsl.stop],
        startz = zrange[0],
        deltat=float(options.deltat)/(24*60),  #days
        )

ax.set_title('%s (%s)\n%s' % (options.cruisename, sonar, dstr))
#--------------------------------------------

if options.noshow is False: # do show
    plt.show()

if options.outfile:
    print('saving figure to %s' % (options.outfile))
    savepngs(options.outfile, dpi=90, fig=topofig)
