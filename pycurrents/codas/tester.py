'''
Early test script for codas interface; minimally updated.

This is not intended as a coding example.
'''

from pycurrents.codas import DB, ProcEns
import pylab as P

db = DB('../../qpy_demos/uhdas_data/km1001c/proc/os38nb/adcpdb/a_km', 2010)


# using get_range_length
r =  (db.yearbase, db.dday_start, db.dday_start+0.2)
numprof = db.get_range_length(r,'day')


data = db.get_profiles(r=r)
data2 = db.get_profiles(ndays=2)
data3 = db.get_profiles(ndays=-2)


ax1=P.subplot(121)
ax1.pcolorfast(data['pg'].T)
ax2=P.subplot(122)
ax2.pcolorfast(data['umeas'].T)

fig = P.figure()
ax1 = fig.add_subplot(1,2,1)
ax1.pcolorfast(data2['e'].T)
ax2 = fig.add_subplot(1,2,2)
ax2.pcolorfast(data2['w'].T)

datar = ProcEns(data)

fig = P.figure()
P.subplot(2,2,1)
P.pcolormesh(datar['dday'], datar['depth'].T, datar['amp1'].T)
P.subplot(2,2,2)
P.pcolormesh(datar['u'].T)
P.subplot(2,2,3)
P.pcolormesh(datar['w'].T)
P.subplot(2,2,4)
P.pcolormesh(datar.e.T)


P.show()
