#! /usr/bin/env python

'''
script to :
- estimate transducer offset (relative to GPS)
- write a new (translated) "fix" file
- write a calibration note about the calculation
'''

import os
from optparse import OptionParser

from pycurrents.data.navcalc import lonlat_shifted, xducer_offset
from pycurrents.codas import get_profiles
from  pycurrents.adcp.uhdasfile import guess_dbname
from pycurrents.num.nptools import rangeslice
from pycurrents.num import Stats            # mean,std,med (masked)

import numpy as np

np.seterr(all='ignore')


usage = '\n'.join(["usage: %prog [--dbname xxx]  ",
                   " eg.",
                   "  %prog --dbname PATH/adcpdb/aship",
                   "  %prog --outfile nav/aship.agt"])

parser = OptionParser(usage)
parser.add_option("-d",  "--dbname", dest="dbname",
       help="path to database name (including database name base)")

parser.add_option("-o", "--outfile", dest="outfile",
       help="write file with [dday, lon, lat] in this location")

(options, args) = parser.parse_args()


if options.dbname is None:
    dbname = guess_dbname('./')
else:
    dbname = guess_dbname(options.dbname)



dd = get_profiles(dbname,diagnostics=True)

## needs work!!
zrange = [30,200]
zsl = rangeslice(dd.dep, zrange[0], zrange[-1])


refl=dict(uship = Stats(dd.umeas[:,zsl], axis=1).mean.flatten(),
          vship = Stats(dd.vmeas[:,zsl], axis=1).mean.flatten())


dx, dy, signal = xducer_offset(dd.dday, dd.lon, dd.lat,
                               refl['uship'], refl['vship'],
                               dd.last_heading, ndiff=2)

print('\n'.join(['',
                 'xducer_dx = %f' % (dx),
                 'xducer_dy = %f' % (dy),
                 'signal = %f' % (signal),
                 '']))

if options.outfile is not None:
    if os.path.exists(options.outfile):
        raise IOError('file %s exists; not overwriting' % (options.outfile))
    newlon, newlat = lonlat_shifted(dd.lon, dd.lat, dd.heading,
                                      starboard=dx, forward=dy)
    fid=open(options.outfile, 'w')
    lines = []
    for t,x,y in zip(dd.dday, newlon, newlat):
        lines.append('%10.7f   %10.6f  %10.6f' % (t,x,y))
    fid.write('\n'.join(lines))
    fid.close()
