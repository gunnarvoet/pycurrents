#!/usr/bin/env python3
'''

usage:help:notes  --> uhdas/scripts

Script for raw adcp data logging failure during power loss

**Usage**
      uhdas_powerloss.py --uhdas_dir path/to/cruise/dir [options]
      uhdas_powerloss.py [options] *.log.rbin


**Options**

    *data source options*

    You must do one or the other:

    (1) usage with wildcard "*.log.rbin" needs no other data source options

    (2) specify source directory:
       --uhdas_dir     path to CRUISE_DIRECTORY (contains raw, rbin, gbin etc)


    *choosing subsets*

    Optional subsetting:

    --startdday     decimal day to start # default is the beginning
    --ndays         number of days to plot #default is to plot all

    *save/view options*

    --outfile xxx   save information here (otherwise print to screen)

'''


import sys
import os
import glob
import logging
from optparse import OptionParser
from pycurrents.plot.mpltools import nowstr
import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.adcp.uhdas_defaults import uhdas_adcps
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.num.nptools import rangeslice     # subsampling (slice)

import numpy as np

# Standard logging
_log = logging.getLogger(__file__)

#This is to catch UHDAS logging of ADCP data when power is lost.

adcp_powerloss_intro = '''
Loss of power during logging results in NULLs at the end of the .log file
and zeros at the end of the .log.bin file.  There is also junk at the end
of the corresponding raw data file.
'''

adcp_powerloss_help='''
To fix the processing, one needs to 
- COPY THE ORIGINAL DATA FOR SAFEKEEPING
  We will be altering those files in the data directory.

(1) identify the last good line in the .log file
  (printed below - these are PYTHON indexes)

(2) remove the NULLS that follow.  If 1000 is printed, use "head -1001"
  (edit, or use "head"). replace the original log file with a clean one)

(3) remake the .log.bin file: 
  (make_rawlogbin.py <list of .raw.log files>)

(4) similarly, make a new .raw file with the bad parts removed:
  (cut_raw_adcp.py os ukdy2021_137_72000.raw 0 1000 ukdy2021_137_72000A.raw;
       mv ukdy2021_137_72000A.raw ukdy2021_137_72000.raw)

(5) reprocess the data with the new files

'''

def binfile_null_lines(fname):
    '''
    read the log.bin file; report the last good line if there are lines where
    - unix_dday went backwards
    - unix_dday stayed at zero at the end
    return range of bad lines
    (else return [])
    '''
    failed_lines = []
    data = BinfileSet(fname)
    udiff = 86400*np.diff(data.monotonic_dday)
    ijump = np.where(udiff < -0.5)[0] # there should only be one
    if len(ijump) > 0:
        badstart = ijump[0]+1
        failed_lines = range(badstart, len(data.monotonic_dday))
    return failed_lines



def get_filelists(uhdas_dir):
    '''
    return a list of */log.bin filenames for each ADCP (in a list)
    eg. 3 instruments means 3 filename lists
    '''
    rawpaths = pathops.make_filelist(os.path.join(uhdas_dir, 'raw','*'))
    adcp_dirs = []
    for rawpath in rawpaths:
        rawdir = os.path.basename(rawpath)
        if rawdir in uhdas_adcps:
            adcp_dirs.append(rawdir)
    filelists = []
    for adcp_dir in adcp_dirs:
        globstr = os.path.join(uhdas_dir, 'raw', adcp_dir, '*log.bin')
        filelist = glob.glob(globstr)
        if len(filelist) > 0:
            filelists.append(pathops.make_filelist(globstr))
    return filelists


def trim_filelist(filelist, startdday=None, ndays=None, file_hours=2):
    '''
    return a subset of the filelist using file start times, selected
    with startdday, through ndays (using file startime + 2 hours)

    new filelist replaces old filelist
    '''
    if not filelist:
        return
    file_dt = file_hours/24.  # typical duration of UHDAS files
    filelist.sort()
    if not startdday and not ndays:
        return filelist
    data=BinfileSet(filelist)
    if len(data.unix_dday) == 0:
        _log.error('%d files but no data using %s' % (len(filelist),
                                                     ' '.join(filelist)))
        return []

    starts = data.starts['unix_dday']
    maxends = starts + file_dt
    if startdday:
        if ndays:
            if ndays > 0:
                startdd = startdday
                enddd = startdday + ndays + file_dt
            else:
                startdd = startdday + ndays
                enddd = startdday
        else:
            startdd = startdday
            enddd = maxends[-1]
        sl = rangeslice(starts, startdd, enddd)
    else:
        sl = rangeslice(starts, ndays)

    return filelist[sl]


def find_badness(filelists):
    '''
    return list of tuples: (filename, last good line, and num bad lines trailing)
    '''
    badness = []
    for filelist in filelists:
        for fname in filelist:
            failed_lines = binfile_null_lines(fname)
            if failed_lines:
                badness.append([fname, failed_lines[0]-1, len(failed_lines)])
    outlist = []
    if len(badness) > 0:
        outlist.append('filename,  python index,    number of failed lines')
        for bad in badness:
            outlist.append('%s, last good line = %d, num FAILED %d' % (bad[0], bad[1], bad[2]))
    return '\n'.join(outlist)


if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(1)

    if '--help' in sys.argv:
        print(__doc__)

    parser = OptionParser()

    ##  specify the uhdas_dir or use a filelist of *.gps.rbin
    parser.add_option("--uhdas_dir", dest="uhdas_dir",
                      default = '',
                      help="uhdas directory you want to access")


    parser.add_option("--verbose", dest="verbose", action="store_true",
                      default = False,
                      help="print things")
    
    # data extraction
    parser.add_option("--startdday", dest="startdday", default = None,
               help="choose dday to start testinmg")

    parser.add_option("--ndays", dest="ndays", default = None, # i.e. all
               help="choose how many days to test; negative is from the end")

    parser.add_option("--outfile", dest="outfile", default=None,
                      help="save the text to this file")

    parser.add_option("-o", "--outdir", dest="outdir",
               default = './',  help="save text to this directory")

    (options, args) = parser.parse_args()

    if options.startdday:
        options.startdday= float(options.startdday)
    if options.ndays:
        options.ndays= float(options.ndays)
    verbose = options.verbose
        

    if options.uhdas_dir and len(args)>0:
        _log.error("ERROR: specify '--uhdas_dir' or a collection of log.bin files, not both")
        msg = "ERROR: specify '--uhdas_dir' or a collection of log.bin files, not both"
        raise IOError (msg)

    if options.uhdas_dir and not os.path.exists(options.uhdas_dir):
        msg = "ERROR: uhdas_dir %s does not exist" % (options.uhdas_dir)
        _log.error(msg)
        raise IOError (msg)

    
    if len(args) > 0:
        trylist = pathops.make_filelist(args)
        filelist = []
        for fname in trylist:
            if fname[-11:] == 'raw.log.bin':
                if os.path.exists(fname):
                    filelist.append(fname)
                else:
                    msg = "ERROR %s: (skipping) no such filename" % (fname)
                    _log.error(msg)
                    raise IOError(msg)
            else:
                msg = "%s: must specify .raw.log.bin files only" % (fname)
                _log.error(msg)
                raise IOError(msg)
                
        if len(filelist) > 0:
            filelists = [filelist,]
        else:
            msg = 'no valid filenames found from args'
            _log.error(msg)
            raise IOError(msg)
    else:
        filelists = get_filelists(options.uhdas_dir)
        if verbose:
            print('uhdas_dir is %s' % (options.uhdas_dir))
            print('found filelists:')
            for flist in filelists:
                print(flist)

    shortlists = []
    for filelist in filelists:
        if filelist:
            newlist = trim_filelist(filelist, startdday=options.startdday,
                                ndays=options.ndays)
            shortlists.append(newlist)
    if verbose:
        for flist in shortlists:
            print(flist)


            
    outstr = find_badness(shortlists)
    
    if len(outstr) > 0:
        if options.uhdas_dir:
            uhdas_string = 'testing %s \n\n' % (os.path.realpath(options.uhdas_dir))
        else:
            uhdas_string = '\n'.join(args)
        bigstring='\n'.join([nowstr(), uhdas_string, adcp_powerloss_intro, '\n',
                                 outstr, adcp_powerloss_help])
        if options.outfile:
            open(os.path.join(options.outdir, options.outfile),'w').write(bigstring)
        else:
            print(bigstring)
    else:
        if options.uhdas_dir:
            uhdas_string = 'testing %s \n\n' % (os.path.realpath(options.uhdas_dir))
        else:
            uhdas_string = '\n'.join(args)

        bigstring='\n'.join([nowstr(), uhdas_string, adcp_powerloss_intro, 
         '==> Testing :last 24 hours:',
     '===> No ADCP data problems detected due to unexpected power loss.\n\n'])
        if options.outfile:
            open(os.path.join(options.outdir, options.outfile),'w').write(bigstring)
        else:
            print(bigstring)
            
            
            
                
                


    
