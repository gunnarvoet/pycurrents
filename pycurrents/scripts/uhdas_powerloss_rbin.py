#!/usr/bin/env python3
'''
Read a collection of rbinfiles; provide a list of rbinfiles that need
to be redone because they have all zeros at the end (happens when
computer loses power)

Usage:

uhdas_powerloss_rbin.py  uhdas_dir

'''

import os
import sys
import glob
#import logging
from optparse import OptionParser
from pycurrents.system.misc import Bunch
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.num.nptools import rangeslice

class RbinTester:
    '''
    Look through all the rbin files within a specified time range;
    Identify all those with zeros at the end (due to unceremonious computer shutdown)
    '''

    def __init__(self, uhdas_dir):
        self.uhdas_dir = uhdas_dir

    def get_rbin_filelist(self):
        subdir='rbin'
        dirs = glob.glob(os.path.join(self.uhdas_dir,subdir,'*'))
        serialdirs = []
        for d in dirs:
            bdir = os.path.basename(d)
            serialdirs.append(bdir)

        serialdirs.sort()

        serial_info = Bunch()
        for dir in serialdirs:
            filelist = glob.glob(os.path.join(self.uhdas_dir, subdir, dir, '*'))
            filelist.sort()
            slist=[]
            for f in filelist:
                s = os.path.split(f)[-1].split('.')[-2]
                if s not in slist:
                    slist.append(s)
            for suffix in slist:
                gstr = os.path.join(self.uhdas_dir, subdir, dir, '*.%s.rbin' % (suffix))
                filelist = glob.glob(gstr)
                filelist.sort()

                inst_msg = ':'.join([dir, suffix])  #Should not use '_' xxx
                if len(filelist) == 0:
#                    log.warning('WARNING: no files with suffix "%s"' % suffix
                    print('WARNING: no files with suffix "%s"' % suffix)
                else:
                    serial_info[inst_msg]=Bunch()
                    serial_info[inst_msg].filelist = filelist

        self.serial_info = serial_info

    def get_badfiles(self, filelist, start_dday=None, ndays=None):
        '''
        Since the point of this exercise is to find files with bad times,
        and those bad times only occur at the end of the file, just use the
        start times for this determination.
        '''
        data=BinfileSet(filelist)
        if start_dday:
            start_dday = float(start_dday)
        if ndays:
            ndays = float(ndays)

        if start_dday is None:
            if ndays is None:
                start_dday=data.starts['u_dday'][0]
                end_dday = float(data.starts['u_dday'][-1]) + 2/24. #proxy for ends
            elif ndays > 0:
                start_dday=data.starts['u_dday'][0]
                end_dday = start_dday + ndays
            else: # negative
                end_dday = float(data.starts['u_dday'][-1]) + 2/24.
                start_dday = end_dday - 2/24. + ndays  # ndays < 0 so add
        else: #start_dday is a float
            if end_dday is None:
                end_dday = float(data.starts['u_dday'][-1]) + 2/24.
            elif ndays > 0:
                end_dday = start_dday + ndays
            else:
                end_dday = start_dday + ndays

        isl = rangeslice(data.starts['u_dday'], start_dday, end_dday)
        ends = data.ends[isl]
        subset=filelist[isl]
        badfiles = []
        for fname, endline in zip(subset, ends):
            if endline['m_dday'] == 0:
                badfiles.append(fname)
        return badfiles

    def remakehint(self,badbunch):
        ''' print out the commandline to use to fix the rbins
        '''
        print('\n\nTo remake the offending rbin files, run these commands')
        print("You'll have to supply the correct year (the year the cruise started)")
        cmd = 'asc2bin.py -y YEAR -m %s -r %s %s' # message raw rbin
        for key in self.serial_info.keys():
            if len(badbunch[key]) > 0:
                for fname in badbunch[key]:
                    inst, msg = key.split(':')
                    rawfile=os.path.splitext(os.path.basename(fname))[0]
                    rawpath=os.path.join(self.uhdas_dir, 'raw', inst, rawfile)
                    print(cmd % (msg, rawpath, fname))


def main():

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    if '--help' in sys.argv:
        print(__doc__)
        sys.exit()

    parser = OptionParser()

    ##  specify the uhdas_dir or use a filelist of *.gps.rbin
    parser.add_option("--uhdas_dir", dest="uhdas_dir",
                      default = '',
                      help="uhdas directory you want to access")
    # data extraction
    parser.add_option("--startdday", dest="startdday", default = None,
               help="choose starting dday check")

    parser.add_option("--ndays", dest="ndays", default = None, # i.e. all
               help="choose how many days to check. >0 is later, <0 is earlier")

    parser.add_option("--verbose", dest="verbose", default=False, action="store_true",
                      help="print out the commands to remake rbfiles")


    (options, args) = parser.parse_args()

    uhdas_dir = options.uhdas_dir
    if not os.path.isdir(os.path.abspath(uhdas_dir)):
        print('ERROR: uhdas directory %s does not exist' % uhdas_dir)
        sys.exit(1)

    RT = RbinTester(uhdas_dir)
    RT.get_rbin_filelist()
    badbunch = Bunch()
    for key in RT.serial_info.keys():
        badbunch[key] = RT.get_badfiles(RT.serial_info[key].filelist,
                                        start_dday = options.startdday,
                                        ndays = options.ndays)
    for key in RT.serial_info.keys():
        if len(badbunch[key]) > 0:
            print('\n'.join(badbunch[key]))

    if options.verbose:
        print(RT.remakehint(badbunch))


if __name__ == '__main__':
    main()
