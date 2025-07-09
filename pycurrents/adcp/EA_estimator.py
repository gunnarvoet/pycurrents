#!/usr/bin/env python

import os
import sys
import logging
import numpy as np
from optparse import OptionParser

import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.adcp.raw_multi import Multiread      # singleping ADCP
from pycurrents.num import Stats, cleaner

# Standard logging
_log = logging.getLogger(__name__)

usage = '''
EA_estimator.py [--bin N] [--underway U]  instrument filelist

'bin' defaults to bin 4
'underway' defaults to 3 m/s (cutoff for "fast enough")
'badbeam' is 1,2,3,4 (if a beam is bad)
'beam_order' is a colon-delimited list to remap beams, eg 1:2:4:3
'instrument' is one of these:  wh, os, nb, bb


prints mean, stddev, and number of pts

'''


def get_xducer_angle(data, bin):
    '''
    return [mean, stddev, number of pts ] for EA estimate
    bin is 0:N, if bin==-1, use bottom track
    '''
    if bin == -1:
        u = data.bt_xyze[:,0]
        v = data.bt_xyze[:,1]
    else:
        u = data.xyze[:,bin,0]
        v = data.xyze[:,bin,1]
    uu = np.ma.masked_where(cleaner.multiglitch(u)==1,u)
    vv = np.ma.masked_where(cleaner.multiglitch(v)==1,v)
    #
    igood = np.where(np.ma.getmaskarray(uu+vv) == False)[0]
    ugood = uu[igood]
    vgood = vv[igood]
    #
    mag = np.sqrt(ugood*ugood + vgood*vgood)
    a = 90+np.angle(ugood + 1j*vgood, deg=True)
    #
    return mag, a, igood


def make_pretty(data, underway=2, bin=2, prefix=''):
    '''
    return pretty string with EA estimate
    '''
    prettylist = []
    mag, a, iused = get_xducer_angle(data, bin)
    igood = np.where(mag > float(underway)) [0]
    if len(igood) == 0:
        prettylist.append('# No good points faster than %s' % (underway))
        prettylist.append('# mean speed %3.2f' % (np.mean(mag)))
    else:
        S = Stats(a[igood])
        prettylist.append('# mean   stddev  N')
        prettylist.append('%5.2f   %5.2f  %4d' % (S.mean, S.std, S.N))
    # bottomtrack
    if sum(data.bt_xyze.mask.flatten() == False) == 0:
        prettylist.append('no bottom track data found')
    else:
        mag, a, iused = get_xducer_angle(data, -1)
        if len(iused) == 0:
            prettylist.append('no bottom track points')
        else:
            igood = np.where(mag > float(underway)) [0]
            if len(igood) == 0:
                prettylist.append('# No bottomtrack points exceed %sm/s' % (underway))
                prettylist.append('# mean  BT speed %3.2f' % (np.mean(mag)))
            else:
                S = Stats(a[igood])
                prettylist.append('# mean   stddev  N')
                prettylist.append('%5.2f   %5.2f  %4d' % (S.mean, S.std, S.N))
    #
    outlist = ['']
    for p in prettylist:
        outlist.append(prefix + p)
    return '\n'.join(outlist)

#=======================================================

def main():


    if '--help' in sys.argv or '-h' in sys.argv:
        print(usage)
        sys.exit()



    parser = OptionParser(__doc__)

    parser.add_option("-u", "--underway", dest="underway",
                      default = '5',
       help="use only velocities in excess of this")
    parser.add_option("-s", "--step", dest="step",
                      default = '10',
       help="subsample by this number")
    parser.add_option("-B", "--badbeam", dest="ibad",
                      default = None,
       help="bad beam 1,2,3,4")

    parser.add_option("--beam_order", dest="beam_order",
                      default = None,
       help="colon-delimited list of RDI beam numbers in order (eg. Revelle in 2020)")

    parser.add_option("-b", "--bin", dest="bin", default=4,
                      help='bin number')


    (options, args) = parser.parse_args()



    if args[0] not in ['wh','os','nb','bb','ec','sv']:
        print('\nERROR ==> "%s" not a recognized instrument type' % (args[0]))
        print(usage)
        sys.exit()


    if len(args) < 2:
        print(usage)
        sys.exit()





    underway = int(options.underway)
    bin = int(options.bin)

    if options.ibad:
        options.ibad = int(options.ibad) - 1  ## ibad is zero-based

    if options.beam_order:
        beam_index = []
        for num in options.beam_order.split(':'):
            beam_index.append(int(num)-1)
    else:
        beam_index=None

    prettystr = 'failed'
    instrument = args[0]
    ENRlist_orig=pathops.make_filelist(args[1:])
    ENRlist=pathops.make_filelist(args[1:])
    ENR_0size = []
    for efile in ENRlist:
        if os.path.getsize(efile) == 0:
            ENR_0size.append(efile)
    for efile in ENR_0size:
        ENRlist.remove(efile)
        _log.info('file %s had zero size' % (efile))
    #remaining files
    numenr = len(ENRlist)
    if numenr == 0:
        prettystr = 'could not get EA estimate from ENR files: %s\n ' % (str(ENRlist_orig))
        read_enr = False
    else:
        step = int(options.step)
        read_enr = True
    if read_enr:
        try:
            m = Multiread(ENRlist, instrument, ibad=options.ibad, beam_index=beam_index)
            data = m.read(step=step)
            npts = len(data.dday)
            if npts <=3:
                prettystr = '# got N=%d points from %s\n' % (npts*step, str(ENRlist))
                prettystr += '# subsample by fewer or pick a longer file'
            else:
                prettystr = make_pretty(data, underway=underway, bin=bin)
        except:
            prettystr = 'could not get EA estimate from ENR files: %s\n ' % (str(ENRlist))

    print(prettystr)
