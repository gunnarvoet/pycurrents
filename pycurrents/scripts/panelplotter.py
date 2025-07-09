#!/usr/bin/env python
'''
make panel plots of UHDAS netCDF data (short or compressed form)
     or CODAS database

default: plot 'u','v','amp', 'pg', and heading+shipspeed,
    with shipspeed included in u,v

default: plot the whole dataset

specialized: to plot the last N days, use "--lastndays" rather
    than startdd and enddd

usage:

    panelplotter.py [options] netCDF_filename
    panelplotter.py [options] dbpath

'''

#TODO
#-----
#
#- wrapper, save fig
#- options
#    figsize
#    plots     (colon-delimited list)
#    ddrange
#- title
#- also thumbnail?


import sys
import os
from optparse import OptionParser

import matplotlib
if '--noshow' in sys.argv:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

import pycurrents.adcp.panelplotter as pp
from pycurrents.plot.mpltools import savepngs
from pycurrents.codas import to_datestring


dpi = 90
ax_defaultstr = ':'.join(pp.ax_defaultlist)

parser = OptionParser(__doc__)
parser.add_option("--startdd" , dest="startdd",
                  help='\n'.join(["decimal day to start (default=beginning)"]))
parser.add_option("--enddd" , dest="enddd",
                  help='\n'.join(["decimal day to end (default=end)"]))
parser.add_option("--lastndays" , dest="lastndays",
                  help='\n'.join(["decimal day to start (default=beginning)"]))
parser.add_option("--cruisename", dest="cruisename",
                  help="cruise ID or title for plots (or use 'cruiseid'")
parser.add_option("--cruiseid", dest="cruisename",
                  help="cruise ID or title for plots (or use 'cruisename'")
parser.add_option("--sonar", dest="sonar",
                  help="set sonar for labels, eg. os38nb, wh300, os75 (if mixed)")
parser.add_option("--numpanels", dest="numpanels",
                  default=5,
                  help='\n'.join(['specfiy how many panels to plot.',
                                  'default is the first 4 plots from this list: ',
                                   ax_defaultstr,
                                   'Heading is the last panel']))
parser.add_option("--panellist", dest="panellist",
                  default=None,
                  help='\n'.join(['specfiy the order of plots.  If NOT specfied,',
                                  'the first N-1 plots are generated from the default list',
                                  'and heading is plotted at the end.',
                                  'If this list is explicitly chosen, all plots come from this list,',
                                  'so be sure to include heading if it is desired.',
                                  '  --panellist="u:v:amp  or  --panellist="u:v:amp:heading"',
                                  ]))

parser.add_option("--shipspeed", dest="plot_spd",
                  help="add ship speed to u,v",
                  action="store_true",
                  default=False)
parser.add_option("-o", "--outfile", dest="outfile",
                  default = None,
                  help="save figure as OUTFILE.png (do not display)")
parser.add_option("--noshow", dest="noshow",
                  action="store_true",
                  default=False,
                  help="do not display figure")
parser.add_option("--add_UTC", dest="add_UTC",
                  action="store_true",
                  default=False,
                  help="use UTC times on the figures")

parser.add_option("--add_suntimes", dest="add_suntimes",
                  action="store_true",
                  default=False,
                  help="add sunrise,sunset indicators on the figures")

parser.add_option("-d", "--showdayrange", dest="showdayrange",
                  action="store_true",
                  default=False,
                  help="output decimal day and date range of file")


options, args = parser.parse_args()


if len(sys.argv[1:]) == 0:
    print(__doc__)
    sys.exit()


if len(args) != 1:
    print("must specify exactly one filename")
    sys.exit()

fname = args[0]
data=pp.get_data(fname)  # based on suffix


numpanels=int(options.numpanels)
if options.panellist is None:
    panellist = pp.ax_defaultlist[:numpanels-1]
    panellist.append('heading')
else:
    panellist = options.panellist.split(':')

print('decimal day range: %5.3f to %5.3f' % (data.dday[0], data.dday[-1]))
print('date range: %s to %s' % (to_datestring(data.yearbase, data.dday[0]),
                                to_datestring(data.yearbase, data.dday[-1])))
if options.showdayrange:
    sys.exit()

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
        except:
            print('could not parse startdd and enddd', options.startdd,
                                                       options.enddd)
            sys.exit()


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

# trim in time
shortdataT=pp.extract_ddrange(data, ddrange=ddrange)
# fill in vertical
pp.fill_masked_inplace(shortdataT)


NCD=pp.NCData(shortdataT)
if len(NCD.data.dday) <= 2:
    print(f'cannot make panel plot with only {len(NCD.data.dday)} times')
NCD.set_grid()


fig=pp.plot_data(NCD, speed=options.plot_spd, sonar=sonar, axlist=panellist,
                 add_utc=options.add_UTC, add_suntimes = options.add_suntimes)

if options.noshow is False: # do show
    plt.show()

if options.outfile:
    savepngs(options.outfile, dpi=dpi, fig=fig)
