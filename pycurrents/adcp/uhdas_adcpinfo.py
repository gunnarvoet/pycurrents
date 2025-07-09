## this used to be an augmented copy of uhdas_info.py,
## but now, it will hold the parts that uhdas_info
## imports.

import os
import glob
import subprocess
import gzip
import numpy as np
import logging

from pycurrents.adcp.uhdas_defaults import uhdas_adcps
from pycurrents.system.misc import Bunch
from pycurrents.system import pathops
from pycurrents import codas
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp import rbin_stats
from pycurrents.adcp import uhdas_defaults #serial_suffix, serial_msgstr
from pycurrents.num import Stats            # mean,std,med (masked)
from pycurrents.num import segments   #indices from mask (eg. on-station)

# Standard logging
_log = logging.getLogger(__name__)
#-----------
# TODO replace "tail" with a python equivalent

plural = dict()
plural[True]='s'
plural[False]=' '

def uname(fname):
    return os.path.split(fname)[-1].split('.')[0]

def infostr(infobunch):
    istr = ' %5d files ' % (infobunch.numfiles)
    if infobunch.numfiles > 0:
        istr += ' (%s - %s)' % (infobunch.firstfile, infobunch.lastfile)
        if 'Ngzoverlap' in infobunch:
            if infobunch.Ngzoverlap > 0:
                istr += ', %d gz overlap' % (infobunch.Ngzoverlap)
    return istr

def skey(x):
    if x == 'rawlog':
        return 'raw.log'
    if x == 'rawlogbin':
        return 'raw.log.bin'
    return x


def clean_filelist(filelist, matchstr='md5sum'):
    ''' count and remove files (or dirs) that match this string'''
    newfilelist = []
    count = 0
    for f in filelist:
        if matchstr in f:
            count += 1
        else:
            newfilelist.append(f)
    return newfilelist, count, matchstr

def intersect(a, b):
    """ return the intersection of two lists """
    return list(set(a) & set(b))

def union(a, b):
    """ return the union of two lists """
    return list(set(a) | set(b))

def difference(a, b):
    """ show whats in list b which isn't in list a """
    return list(set(b).difference(set(a)))


def gzip_info(filelist):
    gzlist = []
    asciilist = []
    for f in filelist:
        if f[-2:] == 'gz':
            gzlist.append(uname(f))
        else:
            asciilist.append(uname(f))
    both = intersect(gzlist, asciilist)
    return both

# =======================================================

def get_rawtimerange(filelist):
    ##returns unixd
    # assume sorted
    startdd = None
    enddd = None
    for f in filelist:
        if f[-2:] == 'gz':
            opener = gzip.open
        else:
            opener = open
        for line in opener(f, 'rb'):
            if line.startswith(b'$UNIXD'):
                startdd = line.split(',')[1]
                break
            if line.startswith(b'$PYRTM'):
                startdd = line.split(',')[2]
                break
        if startdd:
            break

    for f in reversed(filelist):
        if f[-2:] == 'gz':
            opener = gzip.open
        else:
            opener = open
        for line in reversed(opener(f, 'rb').readlines()):
            if line.startswith(b'$UNIXD'):
                enddd = line.split(',')[1]
                break
            if line.startswith(b'$PYRTM'):
                enddd = line.split(',')[2]
                break
        if enddd:
            break

    return startdd, enddd


def get_rbintimerange(filelist):
    if len(filelist) > 8:
        filelist = filelist[:4] +  filelist[-4:]
    bs = BinfileSet(filelist)
    startdd = bs.starts[0]['u_dday']
    enddd = bs.ends[-1]['u_dday']
    return startdd, enddd


def get_gbintimerange(filelist, alias=None):
    ''' returns ((start,end) (start,end))
        for       logger       UTC
       '''
    if alias is None:
        alias = dict(unix_dday='u_dday', monotonic_dday='m_dday',
                     logger_dday='u_dday', bestdday='dday')
    if len(filelist) > 8:
        filelist = filelist[:4] +  filelist[-4:]
    bs = BinfileSet(filelist, alias=alias)
    start_udday = bs.starts[0]['u_dday']
    end_udday = bs.ends[-1]['u_dday']
    start_dday = bs.starts[0]['dday']
    end_dday = bs.ends[-1]['dday']
    return (start_udday, end_udday), (start_dday, end_dday)

# ==================  raw info ==========================

def get_raw_info(uhdas_dir, subdir='raw'):

    md5count = 0

    dirs = glob.glob(os.path.join(uhdas_dir,subdir,'*'))
    newdirlist, count, matchstr = clean_filelist(dirs)
    md5count += count

    adcpdirs = []
    serialdirs = []
    for d in newdirlist:
        bdir = os.path.basename(d)
        if bdir in uhdas_adcps:
            adcpdirs.append(bdir)
        elif bdir not in ['log', 'config']:
            serialdirs.append(bdir)

    adcpdirs.sort()
    serialdirs.sort()

    serial_info = Bunch()
    for dir in serialdirs: #lump together gzipped and not
        filelist = glob.glob(os.path.join(uhdas_dir, subdir, dir, '*'))
        filelist.sort()
        newfilelist, count, matchstr = clean_filelist(filelist)
        md5count += count
    #
        serial_info[dir]=Bunch()
        if len(newfilelist) == 0:
            serial_info[dir].firstfile = 'N.A.'
            serial_info[dir].lastfile = 'N.A.'
            serial_info[dir].numfiles = 0
            serial_info[dir].Ngzoverlap = 0
        else:
            serial_info[dir].firstfile = uname(newfilelist[0])
            serial_info[dir].lastfile = uname(newfilelist[-1])
            serial_info[dir].numfiles = len(newfilelist)
            serial_info[dir].Ngzoverlap = len(gzip_info(newfilelist))

    adcp_info = Bunch()
    for dir in adcpdirs:
        adcp_info[dir] = Bunch(raw=Bunch(),
                               rawlog=Bunch(),
                               rawlogbin=Bunch())
        for suffix in list(adcp_info[dir].keys()):
            globstr=os.path.join(uhdas_dir, subdir, dir, '*.%s' %(skey(suffix)))
            filelist = glob.glob(globstr)
            adcp_info[dir][suffix].numfiles = len(filelist)
            if len(filelist) > 0:
                filelist.sort()
                adcp_info[dir][suffix].firstfile = uname(filelist[0])
                adcp_info[dir][suffix].lastfile = uname(filelist[-1])
                adcp_info[dir][suffix].Ngzoverlap = len(gzip_info(filelist))

    return serial_info, adcp_info, md5count


def print_raw_info(serial_info, adcp_info, md5count):
    '''
    serial_info, adcp_info, md5count = get_raw_info(uhdas_dir)
    print_raw_info(serial_info, adcp_info, md5count)
    '''
    _log.info('\n------raw-------\n')
    serialdirs = list(serial_info.keys())
    serialdirs.sort()
    for s in serialdirs:
        b=serial_info[s]
        _log.info('raw: %18s %s'  % (s, infostr(b)))
    _log.info('')
    for adcp in adcp_info.keys():
        for s in adcp_info[adcp].keys():
            _log.info('adcp: %6s %15s' % (adcp, '.'+skey(s))+infostr(adcp_info[adcp][s]))
    if md5count > 0:
        _log.info('WARNING: found %d files with name including "md5sum"' % (md5count))


# ====================== rbin info ======================

def get_rbin_info(uhdas_dir, subdir='rbin'):
    dirs = glob.glob(os.path.join(uhdas_dir,subdir,'*'))
    md5count = 0

    serialdirs = []
    for d in dirs:
        bdir = os.path.basename(d)
        serialdirs.append(bdir)

    serialdirs.sort()
    full_baselist =[]

    serial_info = Bunch()
    for dir in serialdirs: #lump together gzipped and not
        filelist = glob.glob(os.path.join(uhdas_dir, subdir, dir, '*'))
        filelist.sort()
        newfilelist, count, matchstr = clean_filelist(filelist)
        md5count += count
        # find suffixes
        slist=[]
        for f in newfilelist:
            s = os.path.split(f)[-1].split('.')[-2]
            if s not in slist:
                slist.append(s)
        for suffix in slist:
            gstr = os.path.join(uhdas_dir, subdir, dir, '*.%s.rbin' % (suffix))
            filelist = glob.glob(gstr)
            filelist.sort()

            inst_msg = ':'.join([dir, suffix])  #Should not use '_' xxx
            if len(filelist) == 0:
                _log.warning('WARNING: no files with suffix "%s"' % suffix)
            else:
                for ii in np.arange(len(filelist)):
                    filelist[ii] = uname(filelist[ii])

                serial_info[inst_msg]=Bunch()
                serial_info[inst_msg].firstfile = filelist[0]
                serial_info[inst_msg].lastfile = filelist[-1]
                serial_info[inst_msg].numfiles = len(filelist)
                serial_info[inst_msg].filelist = filelist
                for f in filelist:
                    if f not in full_baselist:
                        full_baselist.append(f)
    #
    full_baselist.sort()
    im_names = list(serial_info.keys())
    im_names.sort()
    return im_names, serial_info, full_baselist, md5count

def print_rbin_info(im_names, serial_info, full_baselist, md5count):
    '''
    im_names, serial_info, full_baselist. md5count = get_rbin_info(uhdas_dir)
    print_rbin_info(im_names, serial_info, full_baselist, md5count)
    '''
    _log.info('\n-----rbin-------\n')
    for im in im_names:
        b=serial_info[im]
        _log.info('rbin:       %18s %s'  % (im, infostr(b)))

    for im in im_names:
        b=serial_info[im]
        isect = difference(b.filelist, full_baselist)
        if len(isect) > 5:
            _log.warning('rbin: ERROR %18s: %d files missing'  % (im, len(isect)))
        elif len(isect) > 0:
            _log.warning('rbin: ERROR  %18s missing: %s'  % (im, '\n'.join(isect)))

    if md5count > 0:
        _log.info('WARNING: found %d files with name including "md5sum"' % (md5count))



# ====================== gbin info ======================

def print_gbin_info(uhdas_dir, subdir='gbin'):
    _log.info('\n-----gbin-------\n')
    md5count = 0
    dirs = glob.glob(os.path.join(uhdas_dir,subdir,'*'))
    for inum in range(len(dirs)):
        dirs[inum] = os.path.basename(dirs[inum])
    py_regen =False
    if 'ztimefit.txt' not in dirs:
        _log.warning('No ztimefit found')
        py_regen = True
    if 'heading' not in dirs:
        _log.warning('No "heading" directory found')
        py_regen = True

    adcplist=[]
    filelist = pathops.make_filelist(os.path.join(uhdas_dir,'raw','*'))
    newfilelist, count, matchstr = clean_filelist(filelist)
    md5count += count
    for d in newfilelist:
        bname =  os.path.basename(d)
        if bname in uhdas_defaults.uhdas_adcps:
            adcplist.append(bname)

#xxx need more here

    for d in dirs:
        if d in adcplist:
            adirs = glob.glob(os.path.join(uhdas_dir,subdir,d,'*'))
            adirlist=[]
            for ad in adirs:
                adirlist.append(os.path.basename(ad))
            _log.info('gbin: %10s (%18s)' % (d,','.join(adirlist)))

    if md5count > 0:
        _log.info('WARNING: found %d files with name including "md5sum"' % (md5count))

    if py_regen is True:
        _log.info('gbin: INFO This cruise was probably originally processed using Matlab')
        _log.info('gbin: INFO Must regenerate gbins to use CODAS Python processing')

#=======================================================
def check_raw_rbin_times(uhdas_dir, verbose=False):
    '''
    print rbin files that are shorter than raw
    '''
    md5count = 0
    rbin_dmlist=[]
    allstr_list=['']
    for rbindir in rbin_stats.find_rbindirs(uhdas_dir):
        suffixes = rbin_stats.find_msgs(rbindir, uhdas_dir)
        for suffix in suffixes:
            rbin_dmlist.append( (rbindir, suffix))
        rmess = Bunch()
        for rbindir, msg in rbin_dmlist:
            if rbindir not in rmess:
                rmess[rbindir] = [msg,]
            else:
                rmess[rbindir].append(msg)
        rbindirs = list(rmess.keys())
        im_names, serial_info, full_baselist, md5count = get_rbin_info(uhdas_dir)
        if verbose:
            print('# testing messages for %d files in %s' % (len(full_baselist),rbindir))

    rbin_strlist = []
    for serdir in rbindirs:
        num_warnings=0
        for base in full_baselist:
            rawpath = os.path.join(uhdas_dir, 'raw', serdir)
            rawfiles = pathops.make_filelist(os.path.join(rawpath, base+'*'))
            newrawfiles, count, matchstr = clean_filelist(rawfiles)
            md5count += count

            if len(newrawfiles) == 0:
                rbin_strlist.append('WARNING: %s raw file missing: base= %s' % (serdir, base))
            elif len(newrawfiles) >1:
                rbin_strlist.append('WARNING: %s raw file multiples:\n%s' % (
                        serdir, '\n'.join(newrawfiles)))
            else:
                fname = newrawfiles[0]
                if fname[-2:] == 'gz':
                    opener = gzip.open
                else:
                    opener = open
                try:
                    lines = opener(fname,'r').readlines()
                    num_rawpairs = len(lines)//2
                except:
                    raise

            #per file
            num_rbinpairs=[]
            messlist=[]
            for msg in rmess[serdir]:
                rbinpath = os.path.join(uhdas_dir, 'rbin', serdir)
                rbinfile = os.path.join(rbinpath, '%s.%s.rbin' % (base, msg))
                if not os.path.exists(rbinfile):
                    rbin_strlist.append('WARNING: %s rbin file missing' % (rbinfile))
                else:
                    rbindata = BinfileSet(rbinfile)
                    num_rbinpairs.append(len(rbindata.records))
                    messlist.append(msg)
            if abs(num_rawpairs - sum(num_rbinpairs)) > 5:
                num_warnings+=1
                line = 'lines: INFO mismatched conversion of raw/%s' % (fname)
                rbin_strlist.append('----\n' + line)

                line='lines: INFO raw/%s has %d pairs' % (fname, num_rawpairs)
                rbin_strlist.append(line)

                for ii in np.arange(len(num_rbinpairs)):
                    line = 'lines: INFO rbin/%s/%s has %d pairs' % (
                        serdir,messlist[ii], num_rbinpairs[ii])
                    rbin_strlist.append(line)

        if num_warnings > 0:
            tag = 'WARNING'
        else:
            tag = 'INFO'
        _log.info('rbin: %s    %d %10s files with mismatched messages' % (
                    tag, num_warnings, serdir ))

    allstr_list.extend(rbin_strlist)

    if len(allstr_list) == 0:
        _log.info('rbin: no warnings')
    else:
        _log.info('\n'.join(allstr_list))

    if md5count > 0:
        _log.info('WARNING: found %d files with name including "md5sum"' % (md5count))


def check_rbintimes(uhdas_dir): # from rbin_gaps.py
    rbindirs = rbin_stats.find_rbindirs(uhdas_dir)
    wlist = []
    slist = ["========= rbintimes =========",]
    slist.append('         ' + rbin_stats.Diffstats.labels)
    for rbindir in rbindirs:
        msgs = rbin_stats.find_msgs(rbindir, uhdas_dir)
        for msg in msgs:
            s, w = rbin_stats.check_rbintimes(rbindir, uhdas_dir, msg)
            wlist.append(w)
            slist.append(s)
        slist.append('\n\n')

    if len(''.join(wlist)) > 0:
        # trim out empty lines
        wstr = '\n'.join(wlist)
        short_wlist = []
        for w in wstr.split('\n'):
            if len(w) > 0:
                rbin_stats.short_wlist.append(w)
        numwarn = len(short_wlist)
        if numwarn>0:
            slist.append("====== rbintimes (%d warnings) =====\n" % (numwarn))
            header = '%20s'%(' ')+'dday ' + rbin_stats.Diffstats.labels + '\n'
            slist.append(header)
            slist.append('\n'.join(short_wlist) + '\n')

    _log.info('\n'.join(slist))


def check_clock(uhdas_dir):
    rbindirs = rbin_stats.find_rbindirs(uhdas_dir)
    wlist = [''] #warnings
    slist=['======= clocks =========',]
    for rbindir in rbindirs:
        msgs = rbin_stats.find_msgs(rbindir, uhdas_dir)
        for msg in msgs:
            s, w = rbin_stats.check_clock(rbindir, uhdas_dir, msg)
            wlist.append(w)
            slist.append(s)
        slist.append('\n\n')

    if len(''.join(wlist)) > 0:
        slist.append("======= clocks (warnings) ========")
        slist.append('\n'.join(wlist))
    _log.info('\n'.join(slist))


#=====================  proc  ==================================

def get_procdirs(uhdas_dir):
    procdir = os.path.join(uhdas_dir, 'proc')
    if not os.path.exists(procdir):
        _log.warning('no "proc" directory found')
        return []
    return  [d.name for d in os.scandir(procdir) if d.is_dir()]


def get_dbtup(procdir):
    dglob = glob.glob(os.path.join(procdir, 'adcpdb', '*dir.blk'))
    if len(dglob) > 0:
        dbname = dglob[0][:-7]
        db = codas.DB(dbname)
        start = db.get_profiles(0.1)
        end = db.get_profiles(-0.1)
        return (db.yearbase, start.dday[0], end.dday[-1])


def get_dbtimeranges(uhdas_dir):
    '''returns times, does not print'''
    trdict = dict()
    procdirs = get_procdirs(uhdas_dir)
    if len(procdirs) == 0:
        _log.warning('proc: no processing directories in "proc"')
        return trdict

    for p in procdirs:
        procdir = os.path.join(uhdas_dir, 'proc', p)
        trtup = get_dbtup(procdir)
        # trdict[procdir] = (string, startdd, enddd)
        if trtup:
            trdict[p] = trtup
    return trdict

def tr2str(timerange):
    (yearbase, tr0, tr1) = timerange
    # return string from (yearbase, tr0, tr1)
    date0 = codas.to_datestring(yearbase, tr0)
    date1 = codas.to_datestring(yearbase, tr1)
    return ' to '.join([date0.split()[0], date1.split()[0]])


### check start, end times

def check_computer_times(uhdas_dir, inst_trdict):
    #
    md5count = 0
    instnames = list(inst_trdict.keys())
    instnames.sort()
    for instname in instnames:
        timedir = os.path.join(uhdas_dir, 'gbin', instname, 'time')
        filelist =pathops.make_filelist(os.path.join(timedir, '*tim.gbin'))
        newfilelist, count, matchstr = clean_filelist(filelist)
        md5count += 1

        (start_udday, end_udday), (start_utc, end_utc) = get_gbintimerange(newfilelist)
        # gbin end dday, database enddday
        _log.info( 'clock: %s last data: clock diff (UTC-PC) = %3.2f sec ' % (
            instname, 86400*(end_utc - end_udday)))

    if md5count > 0:
        _log.info('WARNING: found %d files with name including "md5sum"' % (md5count))


def check_gbin_proc_times(uhdas_dir, inst_trdict):
    #
    md5count = 0
    instnames = list(inst_trdict.keys())
    instnames.sort()
    for instname in instnames:
        yearbase, db_startdd, db_enddd = inst_trdict[instname]
        if db_startdd is not None:
            timedir = os.path.join(uhdas_dir, 'gbin', instname, 'time')
            filelist =pathops.make_filelist(os.path.join(timedir, '*tim.gbin'))
            newfilelist, count, matchstr = clean_filelist(filelist)
            md5count += 1

            (start_udday, end_udday), (start_utc, end_utc) = get_gbintimerange(newfilelist)
            # gbin end dday, database enddday
            _log.info('\ngbin: %6s gbin  UTC = %7.4f to %7.4f, duration = %5.3f days' % (
                    instname, start_utc, end_utc, end_utc-start_utc))
            _log.info( 'gbin: %6s codas UTC = %7.4f to %7.4f, duration = %5.3f days' % (
                    instname, db_startdd, db_enddd, db_enddd - db_startdd))
            _log.info( 'gbin: %6s gbin-codas UTC starting difference  = %7.4f min' % (
                    instname, (db_startdd - start_utc)*24*60))


            end_diff =  (db_enddd - end_utc)*24*60
            _log.info( 'gbin: %6s gbin-codas UTC ending   difference  = %7.4f min' % (
                    instname, end_diff))

            if abs(end_diff) > 90:
                _log.info( '\nproc: WARNING %6s gbin-codas UTC ending   difference  = %7.4f min' % (
                    instname, end_diff))

            db_duration_days = db_enddd - db_startdd
            utc_duration_days =  end_utc-start_utc

            ddiff = (db_duration_days - utc_duration_days)*24*60
            _log.info('gbin: %6s: gbin data and processed data duration differ by %4.2f min' % (
                    instname, np.abs(ddiff)))

    if md5count > 0:
        _log.info('WARNING: found %d files with name including "md5sum"' % (md5count))


def combine_trdict(trdict):
    # if interleaved pings, account for the whole cruise
    inst_trdict = Bunch()
    for sonar in trdict.keys():
        first_tr = trdict[sonar]
        if first_tr[0] is not None:
            yearbase = first_tr[0]
            instname = Sonar(sonar).instname
            if instname in inst_trdict:
                other_tr = inst_trdict[instname]
                final_tr = (yearbase,
                            min(first_tr[1], other_tr[1]),
                            max(first_tr[2], other_tr[2]))
                inst_trdict[instname] = final_tr
            else:
                inst_trdict[instname] = first_tr
    #
    return inst_trdict

#============ serial =====================

## find out what messages were logged

def _get_key(line):
    '''
    return NMEA key such as '$GPGGA', "$PASHR', '$PASHR,ATT', $PSXN,20'

    This is far too specialized and restrictive, but VmDAS is rude about
    adding $PADCP to serial lines (clobbering some). use regex instead.
    '''
    try:
        if line[0] == ':':
            return ':tss1'

        parts = line.split(',')
        if parts[0] in ('$UNIXD', '$PYRTM'):
            return None
        if parts[0] == '$PASHR':
            if parts[1] in ('ATT', 'AT2', 'POS'):
                key = ','.join([parts[0], parts[1]])
            else:
                key = parts[0]
        elif parts[0] in ('$PSXN', '$PSAT'):
            key = ','.join([parts[0], parts[1]])
        else:
            if parts[0][-3:] in ('DID', 'GGA', 'GLL', 'HDT', 'HDG', 'PAT'):
                key = parts[0]
            else:
                print('could not find "%s"' % (parts[0]))
                # FIXME : log.warning? info? Add context to the message?
                key = None
        #
    except Exception:
        # FIXME : Use log.exception?
        _log.warning('could not parse "%s"' % (line,))
        key = None

    return key


def _messages(filelist, numlines=30):
    '''
    return a dictionary with
       keys that are the rbin directory names
       values are a list of unique NMEA messages in the file
    '''
    msglist = []
    if isinstance(filelist, str):
        filelist=[filelist,]
    for fname in filelist:
        if fname[-2:] == 'gz':
            opener = gzip.open
        else:
            opener = open
        try:
            lines = opener(fname,'r').readlines()
            for line in lines[:numlines]:
                key = _get_key(line)
                if key not in msglist and key is not None:
                    msglist.append(key)
        except Exception:
            _log.exception('cannot read %s', fname)
    #
    return msglist


def get_messages(uhdas_dir, subdir='raw', verbose=False):
    md5count = 0
    im_names, serial_info, full_baselist, md5count = get_rbin_info(uhdas_dir)
    if verbose:
        _log.info('checking for serial messages in  %d files in %d raw directories' % (
                len(full_baselist), len(im_names)))
    mess = Bunch()
    for im in im_names:
        parts = im.split(':')  # '_'
        ## awkward:  2-part messages hnc_tss1, hdg_tss1, gps_sea
        ## underscores should be allowed in the dir name
        rawdir = parts[0]   #  should not use this buggy attempt:   '_'.join(parts[:-1])
        filelist = pathops.make_filelist(os.path.join(uhdas_dir, 'raw', rawdir, '*'))
        newfilelist, count, matchstr = clean_filelist(filelist)
        md5count += count
        msglist = _messages(newfilelist)
        mess[rawdir] = msglist

    if md5count > 0:
        _log.warning('WARNING: found %d files with name including "md5sum"' % (md5count))

    return mess

def print_raw_rbin_messages(uhdas_dir, verbose=False):
    mess = get_messages(uhdas_dir, verbose=verbose)
    # find out what messages are in rbins
    rbin_dmlist=[]
    for rbindir in rbin_stats.find_rbindirs(uhdas_dir):
        suffixes = rbin_stats.find_msgs(rbindir, uhdas_dir)
        for suffix in suffixes:
            rbin_dmlist.append( (rbindir, suffix))
    rmess = Bunch()
    for rbindir, msg in rbin_dmlist:
        if rbindir not in rmess:
            rmess[rbindir] = [msg,]
        else:
            rmess[rbindir].append(msg)
    rbindirs = list(rmess.keys())
    rbindirs.sort()
    _log.info('\n-----serial-----\n')
    _log.info('Grouped messages (listed below) are NOT IN ORDER\n')
    for rbindir in rbindirs:
        if rbindir in mess:
            _log.info('serial: %12s: translated raw serial (%s) into rbins (%s)' % (
                    rbindir, ', '.join(mess[rbindir]), ', '.join(rmess[rbindir])))
        else:
            _log.info('serial: unexpected rbin directory %s' % (rbindir))
    for rawdir in mess.keys():
        if rawdir not in rmess:
            _log.info('serial: unexpected raw directory %s' % (rawdir))


#================

## additional processing information

def check_dxdy(procdir, uhdas_dir, name=None):
    if name is None:
        name = os.path.basename(procdir)
    '''
    if uhdas_dir is empty, then don't prefix with uhdas_dir/proc
    '''
    if uhdas_dir:
        procpath = os.path.join(uhdas_dir, 'proc', procdir)
    else:
        procpath = procdir

    cmd = "tail -6 %s/cal/watertrk/guess_xducerxy.out " % (procpath)
    status,sxy = subprocess.getstatusoutput(cmd)
    xylist=[]
    if status == 0:
        lines = sxy.split('\n')
        for line in lines:
            xylist.append('cal: %s   DXDY  %s' % (name, line))
    else:
        xylist.append('cal: %s   DXDY  %s' % (name, 'none'))
    xystr = '\n'.join(xylist)
    return xystr


def check_cals(procdir, uhdas_dir, name=None):
    '''
    procdir = adcp processing directory
    if uhdas_dir is empty, then don't prefix with uhdas_dir/proc
    name is preferably the sonar (instrument+pingtype) but requires characters, no spaces
    '''
    if name is None:
        name=os.path.basename(procdir)
    name = ''.join(name.split()) # remove whitespace
    if uhdas_dir:
        procpath = os.path.join(uhdas_dir, 'proc', procdir)
    else:
        procpath = procdir

    cmd = "tail -8 %s/cal/botmtrk/btcaluv.out | egrep '(median|phase|edited|amplitude)' " % (
            procpath)
    status,sb = subprocess.getstatusoutput(cmd)
    btlist = []
    if status == 0:
        lines = sb.split('\n')
        for line in lines:
            btlist.append('cal: %s   BT  %s' % (name, line))
    else:
        btlist.append('cal: %s   BT  %s' % (name, 'none'))

    btstr = '\n'.join(btlist)
    #----
    cmd = "tail -12 %s/cal/watertrk/adcpcal.out | head -8 | egrep '(median|phase|edited|amplitude)' | grep -v '=' " % (
        procpath)

    status,sw = subprocess.getstatusoutput(cmd)
    wtlist = []
    if status == 0:
        lines = sw.split('\n')
        for line in lines:
            wtlist.append('cal: %s   WT  %s' % (name, line))
    else:
        wtlist.append('cal: %s   WT  %s' % (name, 'none'))
    wtstr = '\n'.join(wtlist)

    #---
    return btstr, wtstr

def evaluate_calstr(calstr, nedit_required=10, phase_alert=1.5):
    num_edited = 0
    med_phase = 0

    if 'WT' in calstr:
        edited_index = 7
    elif 'BT' in calstr:
        edited_index = 4
    else:
        edited_index = 0

    if edited_index > 0:
        lines=calstr.split('\n')
        for line in lines:
            parts = line.split()
            if 'edited' in parts:
                num_edited = int(parts[edited_index])

        if num_edited >= nedit_required:
            for line in lines:
                parts = line.split()
                if 'phase' in parts:
                    med_phase = float(parts[4])
                    plparts = parts

        if abs(med_phase) > phase_alert:
            str_ = 'phase calibration requires attention:'
            return '%s WARNING: %s median=%s' % (
                    ' '.join(plparts[:3]), str_, med_phase)

## calculate significant gaps
def finddb_gaps(dbname, mult=[0,1.5,5,10,100,1000]):
    '''
    use attribute txy.dday for calculations,
    '''
    DB=codas.DB(dbname)
    txy=DB.get_profiles(txy_only=True)
    dt = 86400*np.diff(txy.dday)
    S=Stats(dt)
    ens_len = np.round(S.median)

    nominal_sec = 300
    scale = mult[1]
    gapm = np.ma.masked_array(dt > scale*nominal_sec)
    segs = segments(gapm)

    # finite number of dt
    bins=nominal_sec*np.array(mult)
    hist, bin_edges = np.histogram(dt, bins=bins)

    return segs, (hist, bin_edges), ens_len


def print_gaps(infolist, prefix=''):
    segs, (hist, bin_edges), ens_len = infolist
    strlist=[]
    strlist.append('%s %6d ensembles (%d sec = %2.1f min)' % (
            prefix, sum(hist), ens_len, ens_len/60.))
    if sum(hist[1:]) == 0:
        strlist.append('%s    no gaps greater than %d sec ' % (
                prefix, bin_edges[1]))
    else:
        for ib in np.arange(len(bin_edges[:-1])):
            if hist[ib] > 0 and bin_edges[ib] > 0:
                if bin_edges[ib] < 3*ens_len:
                    strlist.append('%s %6d gap%s (%d min - %d min)' % (
                            prefix, hist[ib],
                            plural[hist[ib]!=1],  #add 's' to 'gap'
                            bin_edges[ib]/60.,
                            bin_edges[ib+1]/60.))
                else:
                    strlist.append('%s %6d gap%s (%2.1f hr - %2.1f hr)' % (
                            prefix, hist[ib],
                            plural[hist[ib]!=1],  #add 's' to 'gap'
                            bin_edges[ib]/3660.,
                            bin_edges[ib+1]/3660.))

    strlist.append('%s %6d segments (gap > %2.1f min )' % (
                              prefix, len(segs), bin_edges[1]/60.))
    strlist.append('')
    _log.info('\n'.join(strlist))
