#!/usr/bin/env python
'''
make a vector-profile plot from a codas database
'''
import sys
from optparse import OptionParser

import numpy as np
np.seterr(invalid='ignore')

import matplotlib.pyplot as plt

from pycurrents.codas import to_date
from pycurrents.adcp.uhdasfile import guess_dbname
from pycurrents.codas import get_profiles, DB     # general codasdb reader
from pycurrents.adcp.ensplot import Ensplot

####### get options

usage = '\n'.join(["usage: %prog --startdd DDD --nprofs NN --refbin N  dbpath"
                   " eg.",
                   "  %prog --startdd 24.5 --nprofs 3 --refbin 2  dbpath  "])

parser = OptionParser(usage)
parser.add_option("--startdd", dest="startdd",
                  default = None,
                  help="start at decimal day STARTDD (default = first profile)")

parser.add_option("--startprof", dest="startprof",
                      default = None,
                      help="start at profile N (index; overrides startdd)")

parser.add_option("--nprofs", dest="nprofs",
                      default = 3, #15min
                      help="average N profs for figure (default=3)")

parser.add_option("--refbin", dest="refbin",
                      default = 2,
                      help="show bin N as reference (default=2)")

parser.add_option("--vecscale", dest="vecscale",
                      default = None,
        help="(default = autoscale);\n smaller number makes bigger vectors")

(options, args) = parser.parse_args()

try:
    dbpath = args[0]
except:
    print('must specify database path')
    sys.exit(1)

#--------------

def get_dbpath(path):
    """ For a given path retuns database path """
    try:
        dbpath = guess_dbname(path)
    except:
        print('Could not find a dbname starting in %s' % (path))
        sys.exit()
    return dbpath

fulldbpath = get_dbpath(dbpath)
db = DB(fulldbpath)


#txy=db.get_profiles(txy_only=True)  # busted at the moment
txy=db.get_profiles()


if options.startdd is None and options.startprof is None:
    startdd = txy.dday[0]
else:
    if options.startdd is not None:
        startdd = float(options.startdd)
    if options.startprof is not None:
        startdd = txy.dday[int(options.startprof)]



nprofs = int(options.nprofs)

mean_dt = np.median(np.diff(txy.dday))  # in days
ndays = nprofs*mean_dt # fraction of day

data=get_profiles(fulldbpath, ddrange=[startdd, startdd+ndays])
data.corr_dday = data.dday


y,m,d,hh,mm,ss=to_date(data.yearbase, data.dday[0])
start_timestring = '%04d/%02d/%02d %02d:%02d:%02d' % (y,m,d,hh,mm,ss)
y,m,d,hh,mm,ss=to_date(data.yearbase,data.dday[-1])
end_timestring = '%04d/%02d/%02d %02d:%02d:%02d' % (y,m,d,hh,mm,ss)

print('vecprof ensemble time range:')
print('%s to %s, (%6.4f to %6.4f)' % (start_timestring,
                                     end_timestring,
                                     data.dday[0], data.dday[-1]))

#Instantiate
E = Ensplot(data=data, procdirname = dbpath)

# add vecprof
fig = E.plot_vecprof_ktvec(zbin=int(options.refbin), vecscale=options.vecscale)
plt.show()
