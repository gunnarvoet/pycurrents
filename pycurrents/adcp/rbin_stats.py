'''
This program (rbin_stats.py) cannot be run on the command line.
This file contains utilities for charactierizing gaps in rbin times
It is leveraged by ../scripts/rbin_gaps.py
'''

import os
import glob
from pycurrents.file.binfile_n import BinfileSet
import numpy as np
from pycurrents import codas


multiplier = dict()
multiplier['secs'] = 24*60*60
multiplier['mins'] = 24*60
multiplier['hrs'] = 24
multiplier['days'] = 1

format_units = dict()
format_units['days'] = '%7.3f'
format_units['hrs'] = '%6.1f'
format_units['mins'] = '%6d'
format_units['secs'] = '%6d'


vv = 0 ## debug: 0 or 1

class RbinSegments:
    def __init__(self, filelist, yearbase=None, ignoresecs=120, units='hrs',alias=None, sonar=''):
        '''
        read binfiles and provide mechanisms to prettyprint chunks of logging/stopped

        eg.
        sfilelist=pathops.make_filelist(os.path.join(dirs[0], '*gps.rbin'))
        LS = LoggingSummary(filelist)
        pstr = LS.pretty_print()

        '''
        self.filelist = filelist
        if not yearbase:
            self.yearbase=int(os.path.basename(filelist[0]).split('_')[0][-4:])
        else:
            self.yearbase = yearbase
        self.units = units
        self.ignoresecs = ignoresecs
        self.alias = alias
        self.sonar = sonar
        self.warning_list = []


    def day_conversion(self, days='decimal'):
        if days=='decimal':
            conversion = 0
            comment = '"days" are CODAS standard decimal day. noon Jan 1 UTC = 0.5'
        elif days == 'julian':
            conversion = 1
            comment = '"days" are JULIAN, (CODAS+1), i.e. noon Jan 1 UTC = 1.5'
        else:
            raise ValueError('must choose "decimal" or "julian" days')
        return conversion, comment


    def pretty_print(self, verbose=False, days='decimal'):
        '''
        days = 'decimal' (codas convention) or 'julian' (codas+1)
        '''
        conversion, comment = self.day_conversion(days) # get the error message here
        self.find_gaps_between()
        if len(self.info) == 0:
            return "no files, or no data in files"

        if verbose:
            self.print_gaps_between(days=days)
        self.find_logging_groups()
        self.consolidate_logging_groups()
        return self.print_consolidated_logging()   #only dates

    def find_gaps_between(self):
        '''
        return tuple with (basename, startdd, enddd, next startdd, gapdday
        - includes last file with None for these: next startdd, secs between files
        '''
        sfilelist=self.filelist
        self.info = []
        infolist = self.info

        if len(sfilelist) == 0:
            return

        b=BinfileSet(sfilelist, alias=self.alias)
        if len(sfilelist) > 1:
            last_ddays = b.ends['u_dday'][0:-1]
            next_ddays = b.starts['u_dday'][1:]
            gaps = next_ddays - last_ddays
            #filebase = os.path.basename(sfilelist[0])
            #msg = filebase.split('.')[-2]   #[LLyyyy_ddd_ssss,msg,'rbin']
            for tup in zip(sfilelist[:-1], b.starts['u_dday'][:-1], last_ddays, next_ddays, gaps ):
                if tup[2] < tup[1]: # testing for 0 at the end of a binfile
                    msg = 'WARNING: ejecting file %s because of bad times' % (tup[0])
                    self.warning_list.append(msg)
                    print(msg)

                else:
                    infolist.append(tup)
        if len(b.starts) > 1:
            last_tup = (sfilelist[-1], b.starts['u_dday'][-1], b.ends['u_dday'][-1], None, None)
            infolist.append(last_tup)


    def print_gaps_between(self, outfile=None, days='decimal'):
        '''
        print info from gaps_between.  (default=stdout, else print to outfile)
        days = 'decimal' (codas convention) or 'julian' (codas+1)
        '''
        self.find_gaps_between()
        conversion, comment = self.day_conversion(days) # get the error message here
        units = self.units
        info = self.info
        mult = multiplier[units]
        outlines = ['\n#' + comment]
        outlines.append('#filename %20s  start           end             next            %s' % (' ', units))
        outlines.append('#         %20s   day            day             start       between' % (' ',))
        for tup in info:
            slist = [os.path.basename(tup[0])]  # string list, to assemble line
            for flday in tup[1:-1]:  ## floating point days
                if flday is None:
                    slist.append('  ---  ')
                else:
                    slist.append('%7.5f' % (flday + conversion))
            if tup[-1] is None:
                slist.append('    --- ')
            else: # gap
                slist.append( format_units[units] % (mult*tup[-1]))
            outlines.append('   '.join(slist))
        #
        if outfile is None:
            print('\n'.join(outlines))
        else:
            if vv:
                print('opening outfile %s' % (outfile))
            with open(outfile, 'a') as file:
                file.write('\n'.join(outlines))


    def find_logging_groups(self):
        '''
        summary of gaps_between tups
        return grouped logging versus not-logging list
        '''
        # info is fname  days days days seconds
        groups = [[]]  # groups of logging segments (each contains tuples ending with a gap)
        for tup in self.info[:-1]:
            gapsecs = tup[-1]*86400
            groups[-1].append(tup)    # active logging segment
            if gapsecs > self.ignoresecs:  #logging segment
                groups.append([])
        # now append the last file:
        last_info = self.info[-1]
        last_logging_segment_last_tup = groups[-1]
        if len(last_logging_segment_last_tup) == 0:
            groups.append([last_info])  # gap, then last file
        else:
            groups[-1].append(last_info)   # last file in last group

        groups_with_data = []
        for g in groups:
            if len(g) > 0:
                groups_with_data.append(g)
        self.groups = groups_with_data

    def consolidate_logging_groups(self):
        '''
        intermediate function: consolidate  groups into 'logging' versus 'stopped'
        stores in self.summary
        '''
        groups=self.groups
        summary=[]
        groupcount=0
        for logging_segment in groups:
            groupcount += 1
            timespent_logging = 0
            filecount = 0
            segment_startdd = logging_segment[0][1]
            segment_enddd = logging_segment[-1][2]
            for fname, startdd, enddd, next_startdd, gap in logging_segment:
                filecount+=1
                fileduration = (enddd-startdd)
                timespent_logging += fileduration
                if filecount == len(logging_segment):
                    summary.append(['logging', segment_startdd, segment_enddd, timespent_logging])
                    summary.append(['stopped', enddd, next_startdd, gap])
        self.summary = summary[:-1]


    def print_consolidated_logging(self):
        '''
        pretty-print the logging/stopped summary
        '''
        units = self.units
        numsum = []
        summary=self.summary
        for slist in summary:
            if slist[0] == 'logging':
                nslist = [1,slist[1], slist[2], slist[3]]
            else: #not logging
                nslist = [0,slist[1], slist[2], slist[3]]
            numsum.append(nslist)
        s_array = np.array(numsum)
        plist = []
        plist.append('# logging summary:')
        plist.append('# "segments" occur when a gap exceeds %d sec' % (self.ignoresecs))
        num_logging_segs = len(np.where(s_array[:,0]==1)[0])
        igaps = np.where(s_array[:,0]==0)[0]
        num_gaps = len(igaps)
        if num_gaps > 0:
            longest_gap = np.max(s_array[igaps,-1]) * multiplier[units]
            fstr = 'longest was '+format_units[units]+units
            longstr = fstr % (longest_gap)
        else:
            longstr=''
        plist.append('# number of separate logging segments = %d' % (num_logging_segs))
        plist.append('# number of gaps was %d %s' %  (num_gaps, longstr))
        plist.append('\n#      status         duration(hours)         time range')
        #format the hours with spaces
        # logging         :  xx.x
        #         stopped :       xx.x

        total_logging_days = 0
        for status, startdd, stopdd, duration in numsum:
            if stopdd is not None:
                if status == 1:
                    ss = 'logging          '
                    sp0, sp1 = ('    ','')
                else:
                    ss = '         stopped '
                    sp0, sp1 = ('','    ')
                fstr = format_units[units]+units
                duration_str =  fstr % ((stopdd - startdd)*multiplier[units])
                startstr = codas.to_datestring(self.yearbase, startdd)
                stopstr = codas.to_datestring(self.yearbase, stopdd)
                plist.append('%s:  %s%s%s,  %s to %s UTC' % (ss, sp0, duration_str, sp1, startstr, stopstr))
                if status == 1:
                    total_logging_days += (stopdd - startdd)

        plist.append('\n\n %s total logging = %1.2f days' % (self.sonar, total_logging_days))

        plist.append('\n\n' + '\n'.join(self.warning_list) + '\n')
        return '\n'.join(plist)

#--------------------------



def find_rbindirs(uhdas_dir, verbose=False):
    rbindirs = glob.glob(os.path.join(uhdas_dir,'rbin','*'))
    for ii in range(0,len(rbindirs)):
        rbindirs[ii] = os.path.basename(rbindirs[ii])
    if verbose:
        print('found rbin dirs: %s' % (' '.join(rbindirs)))
    return rbindirs


def find_msgs(rbindir, uhdas_dir, verbose=False):
    '''
    return suffix (msg) list from rbindir
    '''
    filelist = glob.glob(os.path.join(uhdas_dir, 'rbin', rbindir,'*.rbin'))
    filelist.sort()

    suffixes = []
    for fname in filelist:
        rstr= str.split(os.path.basename(fname),'.')
        suffix = rstr[1]
        if suffix not in suffixes:
            suffixes.append(suffix)

    if verbose:
        print('found %s suffixes: %s' % (rbindir, ' '.join(suffixes)))
    return suffixes


def get_slist(rbindir, msg, uhdas_dir, verbose=False):
    globstr = os.path.join(uhdas_dir, 'rbin', rbindir,'*.%s.rbin' % (msg))
    sfilelist = glob.glob(globstr)
    sfilelist.sort()
    return sfilelist



#===============

class Diffstats:
    '''
    Calculate and show statistics for a time series.

    This is intended for use with recorded time information
    from a set of rbin files.

    Example:

    import os
    from glob import glob
    from pycurrents.file.binfile_n import BinfileSet
    from pycurrents.adcp.rbin_stats import Diffstats

    rbindir = '/home/manini/programs/q_demos/uhdas/data/rbin'
    msg = 'adu'
    inst = 'ashtech'
    pat =  os.path.join(rbindir, inst, '*.%s.rbin' % msg)
    filelist = glob(pat)
    filelist.sort()
    bs = BinfileSet(filelist[-15:])
    print Diffstats.labels
    print Diffstats(bs.u_dday)
    print Diffstats(bs.dday)

    '''
    labels = 'ndiff     median   min     max      high   low  vlow  zero   neg'
    def __init__(self, dday):
        '''
        dday is a numpy 1-D array of decimal day times
        '''
        if len(dday) < 2:
            self.ndiffs = 0
            self.median = 0
            self.min = 0
            self.max = 0
            self.n_high = 0
            self.n_low = 0
            self.n_vlow = 0
            self.n_zero = 0
            self.n_negative = 0
            return
        dd = np.diff(dday)*86400.0
        self.ndiffs = len(dd)
        self.median = np.median(dd)
        self.min = dd.min()
        self.max = dd.max()
        self.n_high = (dd > 2.0*self.median).sum()
        self.n_low = (dd < 0.45*self.median).sum()
        self.n_vlow = (dd < 0.05).sum()
        self.n_zero = (dd == 0.0).sum()
        self.n_negative = (dd < 0.0).sum()

    def __str__(self):
        s = '%6d  %6.2f  %6.2f  %8.1f   %5d %5d %5d %5d %5d' % (
             self.ndiffs,
             self.median,
             self.min, self.max,
             self.n_high, self.n_low, self.n_vlow, self.n_zero,
             self.n_negative)
        return s

def check_rbintimes(rbindir, uhdas_dir, msg, nfiles=None):
    '''
    Look for oddly long, short, or negative time deltas between rbin records.

    All time types that are present will be checked; this is assumed to include
    clock time and monotonic time, and may include the instrument's
    own clock time.
    '''
    slist=[]
    wlist=[]
    label = '%10s %8s' % (rbindir, msg)
    pat = os.path.join(uhdas_dir, 'rbin', rbindir, '*.%s.rbin' % msg)
    filelist = glob.glob(pat)
    filelist.sort()
    if nfiles is None:
        fl = filelist
    else:
        fl = filelist[-nfiles:]
    label += ' %d files' % len(fl)
    slist.append(label)
    if not fl:
        return '\n'.join(slist), '\n'.join(wlist)
    bs = BinfileSet(fl)
    if bs.nrows < 3:
        return '\n'.join(slist), '\n'.join(wlist)
    ds_u_dday = Diffstats(bs.u_dday)
    ds_m_dday = Diffstats(bs.m_dday)
    if ds_u_dday.n_vlow > 0:
        wlist.append('%10s %8s (u) %s' % (rbindir, msg, ds_u_dday))
    if ds_m_dday.n_vlow > 0:
        wlist.append('%10s %8s (m) %s' % (rbindir, msg, ds_m_dday))
    slist.append('u_dday  %s' % ds_u_dday)
    slist.append('m_dday  %s' % ds_m_dday)
    if 'dday' in bs.columns:
        slist.append('dday    %s' % Diffstats(bs.dday))
    slist.append('')
    return '\n'.join(slist), '\n'.join(wlist)

def check_clock(rbindir, uhdas_dir, msg, nfiles=None):
    '''
    Look for jumps in the difference between clock time and monotonic time.
    '''
    wlist=['']
    pat = os.path.join(uhdas_dir, 'rbin', rbindir, '*.%s.rbin' % msg)
    filelist = glob.glob(pat)
    filelist.sort()
    if nfiles is None:
        fl = filelist
    else:
        fl = filelist[-nfiles:]
    if not fl:
        return '', ''
    bs = BinfileSet(fl)
    if len (bs.u_dday) == 0: #no data
        return '', ''
    dt = (bs.u_dday - bs.m_dday) * 86400
    mdt = np.median(dt)
    dt = dt - mdt
    ddt = np.diff(dt)
    jumpf = ddt > 1  # computer clock jumped forward relative to monotonic
    jumpb = ddt < -1 #                       back
    tlist = []
    wlist = []
    tag = '%s_%s' % (rbindir, msg)
    tlist.append('%s median (clock-monotonic): %f days' % (tag, mdt/86400.0,))
    tlist.append('%s dt extremes after removing median: %f %f seconds'
                                                % (tag, dt.min(), dt.max()))
    if jumpf.sum() or jumpb.sum():
        s = '%s jumps forward: %d   jumps back: %d' % (tag, jumpf.sum(), jumpb.sum())
        tlist.append(s)
        wlist.append(s)
        if jumpf.sum():
            ii = ddt[jumpf].argmax()
            s = '%s max forward %d seconds at dday %f' % (tag, ddt[ii], bs.u_dday[ii])
            tlist.append(s)
            wlist.append(s)
        if jumpb.sum():
            ii = ddt[jumpb].argmin()
            s = '%s max backward %d seconds at dday %f' % (tag, -ddt[ii], bs.u_dday[ii])
            tlist.append(s)
            wlist.append(s)
    return '\n'.join(tlist) + '\n', '\n'.join(wlist)
