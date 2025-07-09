'''
Functions for reading serial data streams, mostly NMEA.

Base class (mixin) for asc2bin and serasc2bin.

Everything will be handled as bytes, not as unicode.

'''
import time
import array
import datetime
from functools import reduce

# Global Variable
BAD_FILL_VALUE = 1e38

try:
    _nan = float("nan")
    # works on Linux, but might not on other systems, so
    # use numpy as a backup
except ValueError:
    from numpy import nan
    _nan = float(nan) # convert to native python float for speed

# start times for leap seconds
gps_leapseconds = [
    (datetime.datetime(2006, 1, 1, 23, 59, 59), 14),
    (datetime.datetime(2009, 1, 1, 23, 59, 59), 15),
    (datetime.datetime(2012, 7, 1, 23, 59, 59), 16),
    (datetime.datetime(2015, 7, 1, 23, 59, 59), 17),
    (datetime.datetime(2016, 12, 31, 23, 59, 59), 18),
]

def split_rvdas(line):
    h, t = line.split(b' ', 1)
    return h.strip(), t.strip()

def get_rvdas_dday(timetag, yearbase, epoch_t):
    parts = timetag.split(':', 3)
    yr2, yd = parts[0].split('+')
    year = 2000 + int(yr2)
    yd = int(yd)
    hr = int(parts[1])
    mn = int(parts[2])
    sec = float(parts[3])
    dsec = hr * 3600 + mn * 60 + sec
    dday = (yd - 1) + dsec / 86400.0
    if year != yearbase:
        yearbase_dif_days = round((time.mktime((year, 1, 1, 0, 0, 0, 0, 0, 0)) -
                             epoch_t) / 86400.0)
        dday = dday + yearbase_dif_days
    return dday

def split_dslog(line):
    '''
    WHOI data logger.  each line is (supposed to be):
    descrip yyy/mm/dd hh:mm:ss.sss model info
    ... where info is the $NMEA message or whatever comes from the instrument
    '''
    parts = line.split()
    descr, h, m, model = parts[0:4]
    parts2 = line.split(model)
    messagestr = parts2[-1].strip()
    #print('<%s>' % (messagestr))
    return b' '.join([h,m]), messagestr  #

def get_dslog_dday(timetag, yearbase, epoch_t):
    ymd, hms = timetag.split()
    year, mon, day = ymd.split(b'/')
    hr, mn, dec_sec = hms.split(b':')
    sec, sec100 = dec_sec.split(b'.')

    # PC time
    dday = float(time.mktime((int(year), int(mon), int(day),
                              int(hr), int(mn), int(sec), 0, 0, 0)) +
                 int(sec100)/100.0 -  epoch_t)/86400.0
    return dday

def split_rsmas(line):
    '''
    RSMAS data logger lines look like this:
    08/19/2023      00:00:08.803    $PASHR,000007.769,84.52,[etc]
    '''
    parts = line.split()
    if len(parts) == 3:
        h = b' '.join(parts[:2])
        t = parts[2]
    return  h.strip(), t.strip()

def get_rsmas_dday(timetag, yearbase, epoch_t):
    '''
    08/19/2023 00:00:38.910
    08/19/2023 00:00:38
    '''
    mdy, hms = timetag.split(b' ')
    parts = mdy.split(b'/')
    mon   = int(parts[0])
    day   = int(parts[1])
    year  = int(parts[2])
    parts = hms.split(b':', 3)
    hr    = int(parts[0])
    mn    = int(parts[1])
    parts = parts[2].split(b'.')
    if len(parts) == 2:
        secleft, secright = parts
        sec = int(secleft)
        divlist = [1,10,100,1000,10000]
        secfrac = int(secright)/float(divlist[len(secright)])
        dday = float(time.mktime((year, mon, day, hr, mn, sec, 0, 0, 0)) +
                 secfrac -  epoch_t)/86400.0
    else:
        sec = int(parts[0])
        dday = float(time.mktime((year, mon, day, hr, mn, sec, 0, 0, 0))
                         - epoch_t)/86400.0
    return dday


def split_scs(line):
    parts = line.split(b',', 2)
    h = b' '.join(parts[:2])
    t = parts[2]
    return h.strip(), t.strip()

def get_scs_dday(timetag, yearbase, epoch_t):
    ''' 04/01/2006,00:00:38.910,$NMEA  ## scs
    '''
    mdy, hms = timetag.split(b' ')
    parts = mdy.split(b'/')
    mon   = int(parts[0])
    day   = int(parts[1])
    year  = int(parts[2])
    parts = hms.split(b':', 3)
    hr    = int(parts[0])
    mn    = int(parts[1])
    secleft, secright   = parts[2].split(b'.')
    sec = int(secleft)
    divlist = [1,10,100,1000,10000]
    secfrac = int(secright)/float(divlist[len(secright)])
    dday = float(time.mktime((year, mon, day, hr, mn, sec, 0, 0, 0)) +
                 secfrac -  epoch_t)/86400.0
    return dday

def split_vids(line):
    parts = line.split()
    h = b' '.join(parts[:2])
    t = parts[2]
    return h.strip(), t.strip()

def get_vids_dday(timetag, yearbase, epoch_t):
    ''' 04/01/2006 00:00:38.910 $NMEA  ## vids
    '''
    mdy, hms = timetag.split(b' ')
    parts = mdy.split(b'/')
    mon   = int(parts[0])
    day   = int(parts[1])
    year  = int(parts[2])
    parts = hms.split(b':', 3)
    hr    = int(parts[0])
    mn    = int(parts[1])
    secparts  = parts[2].split(b'.')
    if len(secparts) == 2:
        secleft, secright = secparts
        sec = int(secleft)
        divlist = [1,10,100,1000,10000]
        secfrac = int(secright)/float(divlist[len(secright)])
    else:
        sec = int(secparts[0])
        secfrac = 0.0
    dday = float(time.mktime((year, mon, day, hr, mn, sec, 0, 0, 0)) +
                 secfrac -  epoch_t)/86400.0
    return dday


def get_vmdas_dday(str_, yearbase, epoch_t):
    if str_[:7] != b'$PADCP,':
        return None
    ### timetag is:   $PADCP,2137,20030909,000148.26,-148.11
    ### new VmDAS timetag is:   $PADCP,2137,20030909,000148.26
    ### for consistency, leave out sec_pc_minus_utc entirely
    parts = str_.split(b',')
    if len(parts) not in [4,5]:
        return None

    ens_num = parts[1]
    ymd = parts[2]
    hms = parts[3]

    #sec_pc_minus_utc = float(parts[4])
    year = int(ymd[0:4])
    mon =  int(ymd[4:6])
    day =  int(ymd[6:8])
    hr =   int(hms[0:2])
    mn = int(hms[2:4])
    sec = int(hms[4:6])
    sec100 = int(hms[7:])

    # PC time
    dday = float(time.mktime((year, mon, day, hr, mn, sec, 0, 0, 0)) +
                 sec100/100.0 -  epoch_t)/86400.0
    return  [dday, ens_num]


def split_lds(line):
    name, tstamp, nmeamsg = line.split()
    return tstamp.strip(), nmeamsg.strip()

def get_lds_dday(timetag, yearbase, epoch_t):
    year, yday, hour, mins, secs = timetag.split(b':')
    year = int(year)
    yday = int(yday)
    hour = int(hour)
    mins = int(mins)
    secs = float(secs)
    dsec = hour * 3600 + mins * 60 + secs
    dday = (yday - 1) + dsec / 86400.0
    if year != yearbase:
        yearbase_dif_days = round((time.mktime((year, 1, 1, 0, 0, 0, 0, 0, 0)) -
                             epoch_t) / 86400.0)
        dday = dday + yearbase_dif_days
    return dday

def split_osucsv(line):
    # line is:
    #   <data time='20130214T210228.702Z'>$PGRMV,0.0,0.0,0.0*5C</data>
    #   DATA, 2013-02-15T06:00:00.580Z, "$PGRMV,0.0,0.0,0.0*5C"
    parts = line.split(b', ')
    tt=parts[1].replace(b'-', b'').replace(b':', b'')
    nmea = parts[2].replace(b'"', b'')
    # timestring, nmea
    return tt, nmea

#### FIXME: handle Py3 bytes/unicode conversions in samosxml functions

def split_samosxml(line):
    # line is:
    #   <data time='20130214T210228.702Z'>$PGRMV,0.0,0.0,0.0*5C</data>
    import xml.etree.ElementTree as et
    tree = et.fromstring(line)
    # timestring, nmea
    return tree.get('time'), tree.text

def get_samosxml_dday(timetag, yearbase, epoch_t):
    # 20130214T210225.255Z
    import time
    ymdhms,fracsecZ = timetag.split('.')
    fracsec = 1.0*int(fracsecZ[:-1])/(10**(len(fracsecZ)-1))
    tstruc = time.strptime(ymdhms,"%Y%m%dT%H%M%S")
    dsec = tstruc.tm_hour*3600 + tstruc.tm_min*60 + tstruc.tm_sec + fracsec
    dday = (tstruc.tm_yday - 1) + dsec / 86400.0
    if tstruc.tm_year != yearbase:
        secdiff = time.mktime((tstruc.tm_year, 1, 1, 0, 0, 0, 0, 0, 0)) - epoch_t
        yearbase_dif_days = round( (secdiff) / 86400.0)
        dday = dday + yearbase_dif_days
    return dday

## Here and in checksums.pyx, the use of ValueError is convenient
## but not particularly good practice; it would be better to define
## a ChecksumError so as to distinguish between bad checksums and
## other reasons for failure in the message parsing.

## The general strategy is that the message reading functions return
## None if the requested message is not the one in the string, and
## raise an exception if it is the right message but fails in any other
## way.  This includes checksum errors and missing fields.

try:
    from pycurrents.data.nmea.checksums import NMEA as NMEAchecksum
except ImportError:
    def NMEAchecksum(str_):
        if len(str_) < 10:
            raise ValueError
        _bytes = array.array('B')
        _bytes.fromstring(str_[1:-3])   # exclude the $ and the *
                                        # future: use frombytes method,
                                        # or just delete these pure python
                                        # versions.
        cs = int(b'0x' + str_[-2:], 16)
        bcs = reduce(lambda x, y: x ^ y, _bytes)
        if cs != bcs:
            raise ValueError

try:
    from pycurrents.data.nmea.checksums import HERC as HERCchecksum
except ImportError:
    def HERCchecksum(str_):
        if len(str_) < 10:
            raise ValueError
        #str_ = str_.strip()
        _bytes = array.array('B')
        _bytes.fromstring(str_[:-3])   # exclude the * but include the $
        cs = int(b'0x' + str_[-2:], 16)
        bcs = reduce(lambda x, y: x ^ y, _bytes)
        if cs != bcs:
            raise ValueError


def frac_to_dday(u_dday, dday_frac):
    return round(u_dday - dday_frac) + dday_frac

def hms_to_sec(hms):
    hh = float(hms[0:2])
    mm = float(hms[2:4])
    ss = float(hms[4:])
    return ss + 60.0 * (mm + 60.0 * hh)

def dm_to_deg(dm, let):
    idec = dm.index(b'.')
    deg = float(dm[:(idec-2)])
    mn = float(dm[(idec-2):])
    if let in b'SW':
        return -(deg + mn/60.0)
    else:
        return (deg + mn/60.0)

def get_degrees(str_):
    if str_[:6] == b'$HEHRC':
        HERCchecksum(str_)
        return [float(str_[6:11])/100.0, ]
    elif str_[3:7] == b'HDT,':
        NMEAchecksum(str_)
        return [float(str_.split(b',')[1]) ]
    else:
        return None

def get_degrees_nochecksum(str_):
    if str_[:6] == b'$HEHRC':
        return [float(str_[6:11])/100.0, ]
    elif str_[3:7] == b'HDT,':
        return [float(str_.split(b',')[1]) ]
    else:
        return None

def get_ssv(str_):
    ''' surface sound-velocity: temperature and soundspeed'''
    parts=str_.split()
    temp = float(parts[0])
    spd = float(parts[1])
    return [temp, spd]

def get_spd(str_):
    return [float(str_), ]

def get_rawspd(str_):
    return  [int(str_), ]

def get_gga(str_):
    ''' returns [t, x, y, qual, hdop] in days, decimal degrees'''
    if str_[3:7] != b'GGA,':
        return None
    NMEAchecksum(str_)
    fields = str_[7:].split(b',')
    hms, latdm, ns, londm, ew, qual, nsat, hdop = fields[:8]
    try:
        f_hdop = float(hdop)
    except:
        f_hdop = 0.0
    return [hms_to_sec(hms)/86400.0, dm_to_deg(londm, ew),
                                dm_to_deg(latdm, ns), int(qual), f_hdop]

def get_gns(str_):
    ''' returns [t, x, y, svs, hdop, orhgt, geosep, age] in days, decimal degrees
    Does NOT return "mode", "age", or "ref station"
    '''
    if str_[3:7] != b'GNS,':
        return None
    NMEAchecksum(str_)
    fields = str_[7:].split(b',')
    hms, latdm, ns, londm, ew = fields[:5]
    try:
        svs = int(fields[6])
    except:
        svs = 0
    try:
        hdop = float(fields[7])
    except:
        hdop = 0.0
    try:
        orhgt = float(fields[8])
    except:
        orhgt = 0.0
    try:
        geosep = float(fields[9])
    except:
        geosep = 0.0

    return [hms_to_sec(hms)/86400.0, dm_to_deg(londm, ew), dm_to_deg(latdm, ns),
             svs, hdop, orhgt, geosep]

def get_gga_nochecksum(str_):
    ''' returns [t, x, y, qual, hdop] in days, decimal degrees'''
    if str_[3:7] != b'GGA,':
        return None
    fields = str_[7:].split(b',')
    hms, latdm, ns, londm, ew, qual, nsat, hdop = fields[:8]
    return [hms_to_sec(hms)/86400.0, dm_to_deg(londm, ew),
                                dm_to_deg(latdm, ns), int(qual), float(hdop)]

def get_rmc(str_):
    """ returns [t, x, y, ok] in days, decimal degrees, 1.0 if OK """
    if str_[3:7] != b"RMC,":
        return None
    NMEAchecksum(str_)
    fields = str_[7:].split(b',')
    (hms, valid, latdm, ns, londm, ew,
        spdkts, cmg, datedmy, magvar, mvardir) = fields[:11]
    return [hms_to_sec(hms)/86400.0, dm_to_deg(londm, ew),
                                dm_to_deg(latdm, ns), float(valid == "A")]

def get_rdi(str_):
    ''' returns [pitch, roll, heading]
    Since we are not dealing with the checksum, we ignore it, present or absent
    '''
    if str_[:7] != b'$PRDID,':
        return None
    #NMEAchecksum(str_)
    #FIXME: chop off the checksum till we write the code for it
    if b'*' in str_:
        str_ = str_.split(b'*')[0]
    fields = str_[7:].split(b',', 3)
    f = list(map(float, fields[:3]))
    return f

def get_rdinc(str_):
    # because we're not dealing with the checksum, these are really the same
    return get_rdi(str_)

def get_rnh(str_):
    ''' returns [pitch, roll] #no heading'''
    if str_[:7] != b'$PRDID,':
        return None
    #NMEAchecksum(str_)
    #FIXME: chop off the checksum till we write the code for it
    if b'*' in str_:
        str_ = str_.split(b'*')[0]
    fields = str_[7:].split(b',', 2)
    f = list(map(float, fields[:2]))
    return f

def get_uvh(str_):
    ''' returns [u, v, heading]'''
    if str_[:11] != b'$PUHAW,UVH,':
        return None
    u, v, heading = str_[11:].split(b',', 3)
    return [float(u), float(v), float(heading)]


def get_vbw(str_):
    ''' returns speed through water: [alongtrack, crosstrack, flag]'''
    NMEAchecksum(str_)
    if str_[3:7] != b'VBW,':
        return None
    parts = str_[7:].split(b',')  #longitudinal, transverse, flag
    lw, tw, fw  = parts[:3]
    flag = fw!=b'A'               # 'A' is valid, otherwise bad
    return [float(lw), float(tw), float(flag)]


def get_ths(str_):
    ''' returns [heading, status]'''
    NMEAchecksum(str_)
    if str_[3:6] != b'THS':
        return None
    heading, status = str_[7:-3].split(b',', 2)
    s = dict(a = 0, # autonomous
             e = 1, # estimated (dead reckoning)
             m = 2, # manual input
             s = 3, # simulator mode
             v = 4, # data nov valid (includes standby)
             )[status.lower()]
    return [float(heading), s]

def get_att(str_):
    if str_[:11] != b'$PASHR,ATT,':
        return None
    #str_ = NMEAchecksum(str_)
    NMEAchecksum(str_)
    f = list(map(float, str_[11:-3].split(b',')))
    #f = map(float, str_[11:].split(','))  # version if NMEAchecksum chopped
    f[0] = f[0] / 86400.0
    return f

def get_at2(str_):
    if str_[:11] != b'$PASHR,AT2,':
        return None
    #str_ = NMEAchecksum(str_)
    NMEAchecksum(str_)
    f = list(map(float, str_[11:-3].split(b',')))
    #f = map(float, str_[11:].split(','))  # version if NMEAchecksum chopped
    f[0] = f[0] / 86400.0
    return f

def get_paq(str_):
    if str_[:7] != b'$GPPAT,':
        return None
    #str_ = NMEAchecksum(str_)
    NMEAchecksum(str_)
    fields = str_[7:-3].split(b',')
    hms, latdm, ns, londm, ew, alt, head, pitch, roll, mrms, brms, reacq = fields
    return  [hms_to_sec(hms)/86400.0,
            dm_to_deg(londm, ew),
            dm_to_deg(latdm, ns),
            float(alt),
            float(head),
            float(pitch),
            float(roll),
            float(mrms),
            float(brms),
            int(reacq)]

def get_posmv_pashr(str_):
    if str_[:7] != b'$PASHR,':
        return None
    NMEAchecksum(str_)
    fields = str_[7:-3].split(b',')
    del fields[2]
    f = list(map(float, fields[1:]))
    day = hms_to_sec(fields[0])/86400.0
    return [day,] + f

def get_vector_pashr(str_):
    if str_[:7] != b'$PASHR,':
        return None
    NMEAchecksum(str_)
    fields = str_[7:-3].split(b',')
    del fields[2]
    f = list(map(float, fields[1:]))
    day = hms_to_sec(fields[0])/86400.0
    return [day,] + f

def get_gpgst_str(str_):
    # see https://docs.novatel.com/OEM7/Content/Logs/GPGST.htm
    if str_[3:7] != b'GST,':
        return None
    NMEAchecksum(str_)
    fields = str_[7:-3].split(b',')
    f = list(map(float, fields[1:]))
    day = hms_to_sec(fields[0])/86400.0
    return [day, ] + f

def get_ptnlvhd_str(str_):
    if str_[:10] != b'$PTNL,VHD,':
        return None
    NMEAchecksum(str_)
    fields = str_[10:-3].split(b',')
    # see: https://www.trimble.com/OEM_ReceiverHelp/V4.44/en/...
    #      ...NMEA-0183messages_PTNL_VHD.html
    f = list(map(float, fields[1:]))
    day = hms_to_sec(fields[0])/86400.0
    return [day, ] + f

def get_jratt(str_):
    """For PFEC, GPatt NMEA sentences version 2.1 with checksum"""
    if str_[:12] != b'$PFEC,GPatt,':
        return None
    NMEAchecksum(str_)
    fields = str_[12:-3].split(b',')
    # see http://www.echomastermarine.co.uk/assets/manuals/JRC/...
    #     ...JLR-21%20JLR-31%20Instruction%20Manual.pdf
    f = list(map(float, fields[:]))
    return f

def get_jratt_nochecksum(str_):
    """For PFEC, GPatt NMEA sentences version 1.5 without checksum"""
    if str_[:12] != b'$PFEC,GPatt,':
        return None
    fields = str_[12:].split(b',')
    # see http://www.echomastermarine.co.uk/assets/manuals/JRC/...
    #     ...JLR-21%20JLR-31%20Instruction%20Manual.pdf
    # check if there is a checksum...just in case
    if b'*' in fields[-1]:
        # FIXME - user won't know that she/he is using the wrong parser though
        fields[-1] = fields[-1][:-3]
    f = list(map(float, fields[:]))
    return f

def get_jrhve(str_):
    """For PFEC, GPhve NMEA sentences version 2.1 with checksum"""
    if str_[:12] != b'$PFEC,GPhve,':
        return None
    NMEAchecksum(str_)
    fields = str_[12:-3].split(b',')
    # see http://www.echomastermarine.co.uk/assets/manuals/JRC/...
    #     ...JLR-21%20JLR-31%20Instruction%20Manual.pdf
    f = [float(fields[0])]
    # parser QC value
    if b'A' in fields[1]:
        f.append(0.0)
    else:
        f.append(1.0)
    return f

def get_jrhve_nochecksum(str_):
    """For PFEC, GPhve NMEA sentences version 1.5 without checksum"""
    if str_[:12] != b'$PFEC,GPhve,':
        return None
    fields = str_[12:].split(b',')
    # see http://www.echomastermarine.co.uk/assets/manuals/JRC/...
    #     ...JLR-21%20JLR-31%20Instruction%20Manual.pdf
    f = [float(fields[0])]
    # check if there is a checksum...just in case
    if b'*' in fields[-1]:
        # FIXME - user won't know that she/he is using the wrong parser though
        fields[-1] = fields[-1][:-3]
    # parser QC value
    if b'A' in fields[1]:
        f.append(0.0)
    else:
        f.append(1.0)
    return f

def get_psxn20(str_):
    if str_[:9] != b'$PSXN,20,':
        return None
    NMEAchecksum(str_)
    fields = str_[9:-3].split(b',')
    f = list(map(float, fields))
    return f

def get_psxn23(str_):
    if str_[:9] != b'$PSXN,23,':
        return None
    NMEAchecksum(str_)
    #checksums.NMEA(str_)
    fields = str_[9:-3].split(b',')
    f = list(map(float, fields[:3]))
    if fields[3]:
        f.append(float(fields[3]))
    else:
        f.append(_nan)
    return f


tss1_status_letters = ('u', 'g', 'h', 'f',
                       'U', 'G', 'H', 'F')
tss1_status_dict = dict(zip(tss1_status_letters,
                            range(len(tss1_status_letters))))
def get_tss1(str_):
    if str_[0] != b':':
        return None
    try:
        f = [float(tss1_status_dict[str_[13]])]
        f.append(int(str_[1:3],16)*0.0383)  # H accel 3.83 cm/s2 per unit -> m/s2
        f.append(int(str_[3:6],16)*0.000625) # V accel 0.0625 cm/s2
        # space is 6
        f.append(int(str_[7:13])*0.01) # heave; convert cm to m
        # status character is 13
        f.append(int(str_[14:19]) * 0.01) # roll; hundredths to degrees
        # space is 19
        f.append(int(str_[20:26]) * 0.01) # pitch; hundredths to degrees
    except:
        return None
    return f

def get_psathpr(str_):
    if str_[:10] != b'$PSAT,HPR,':
        return None
    NMEAchecksum(str_)
    fields = str_[10:-3].split(b',')
    day = hms_to_sec(fields[0])/86400.0
    if fields[4] == 'N':
        q = 1
    else:
        q = 0
    f = [day]
    for field in fields[1:4]:
        try:
            f.append(float(field))
        except ValueError:
            f.append(BAD_FILL_VALUE)
    f.append(q)
    return f

def get_pat(str_):
    if str_[:7] != b'$GPPAT,':
        return None
    NMEAchecksum(str_)
    fields = str_[7:].split(b',')
    hms, latdm, ns, londm, ew, altitude, heading, pitch, roll, mrms, brms = \
       fields[:11]
    return [hms_to_sec(hms)/86400.0, dm_to_deg(londm, ew), dm_to_deg(latdm, ns),
            float(heading), float(pitch), float(roll),
            float(mrms), float(brms)]


def get_vtg(str_):
    ''' returns [
    course over ground (deg T),
    course over ground (megnetic),
    speed (kts)
    speed (km/hr)
    ]
    '''
    if str_[3:7] != b'VTG,':
        return None
    NMEAchecksum(str_)
    fields = str_[7:].split(b',')
    cogT, Tstr, cogM, Mstr, kts, Nstr, km_per_hr, Kstr = fields[:8]
    return [float(cogT), float(cogM), float(kts), float(km_per_hr)]



#==================================
#---- ixsea phins hydrins ---
# QC 'algorithm'

#### FIXME: modify all the IX functions for Py3

def _bin_from_msg(msg,num):
    pad = '0000'
    bb = bin(int(msg[-(num+1)],16))[2:]
    ss = '%s%s' % (pad[:(4-len(bb))], bb)
    return ss

def _bits_from_msg(msg):
    allbits = []
    for num in range(len(msg)):
        a = list(_bin_from_msg(msg, num))
        allbits += a
    return allbits

def get_ixalg(str_):
    #64bit list
    if str_[:13] == b'$PIXSE,ALGSTS':
        lsb_msg, msb_msg =  str_[14:-3].split(',')
        f = list(map(int,  _bits_from_msg(lsb_msg) + _bits_from_msg(msb_msg)))
        return f
    else:
        return None


# -----
# nav. attitude
def get_ixrp(str_):
    # roll, pitch
    if str_[:13] == b'$PIXSE,ATITUD':
        NMEAchecksum(str_)
        return list(map(float, str_[14:-3].split(',')))
    else:
        return None


def get_ixsspd(str_):
    # ship speed in m/s: east, west, north
    if str_[:13] == b'$PIXSE,SPEED_':
        NMEAchecksum(str_)
        return  list(map(float, str_[14:-3].split(',')))
    else:
        return None


def get_ixgps(str_):
    # decimal lon, lat
    if str_[:13] == b'$PIXSE,POSITI':
        NMEAchecksum(str_)
        return list(map(float, str_[14:-3].split(',')))
    else:
        return None


def get_hpr(str_):
    """
    Parser for hpr NMEA sentence coming from ABX-TWO device
    Sentence tag: $PASHR,HPR
    Sentence format: tag,dday,heading,pitch,roll,mrms,brms,ia,bm,yxxx,pdop*cc
    Where:
        dday: UTC time of attitude (hhmmss.ss)
        heading: True heading angle in deg.
        pitch: Pitch angle in deg.
        roll: Roll angle in deg.
        mrms: Carrier measurement RMS error in m.
        brms: Baseline RMS error in m. (= 0 if not constrained)
        ia: Integer ambiguity (0: Fixed,> 0: Float)
        bm: Baseline mode status (0: operation with fixed baseline length,
            1: calibration in progress, 2: flexible baseline mode on)
        yxxx: Character string "y.xxx" where
              y=="antenna setup" where
              y=0: no length constraint,
              y=1: heading mode,
              y=2 or 3: attitude mode;
              x=="number of double differences per vector", one per vector,
                  value from 0 to 9).
              It is then returned by the parser as 4 distinct values, y, x1,
              x2 and x3.
        pdop: PDOP corresponding to vector V12
        *cc: Checksum

    Returns a list of floats:
        [hms, heading, pitch, roll, mrms, brms, ia, bm, y, x1, x2, x3, pdop]
    """
    if str_[:10] == b'$PASHR,HPR':
        NMEAchecksum(str_)
        try:
            hms, heading, pitch, roll, mrms, brms, ia, bm, yxxx, pdop = \
                str_[11:-3].split(b',')
            pdop = float(pdop)
        except ValueError:  # pdop is missing for some reason
            hms, heading, pitch, roll, mrms, brms, ia, bm, yxxx = \
                str_[11:-4].split(b',')
            pdop = BAD_FILL_VALUE
        # Splitting and converting yxxx values
        y = float(yxxx.split(b'.')[0])
        # Converting to ascii is required to use list
        xxx = (yxxx.split(b'.')[1]).decode('ascii')
        x1, x2, x3 = [float(x) for x in list(xxx)][:]
        return [hms_to_sec(hms) / 86400.0, float(heading), float(pitch),
                float(roll), float(mrms), float(brms), float(ia), int(bm),
                y, x1, x2, x3, pdop]
    else:
        return None


ix_algnames=[
     'lsb00_Navigation_mode',
     'lsb01_Alignment',
     'lsb02_Fine_alignment',
     'lsb03_Dead_reckoning_mode',
     'lsb04_Altitude_calculated_using_GPS',
     'lsb05_Altitude_calculated_using_depth_sensor',
     'lsb06_Altitude_stabilized',
     'lsb07_Altitude_hydro',
     'lsb08_Log_used',
     'lsb09_Log_data_valid',
     'lsb10_Waiting_for_log_data',
     'lsb11_Log_data_rejected',
     'lsb12_GPS_used',
     'lsb13_GPS_data_valid',
     'lsb14_Waiting_for_GPS_data',
     'lsb15_GPS_data_rejected',
     'lsb16_USBL_used',
     'lsb17_USBL_data_valid',
     'lsb18_Waiting_for_USBL_data',
     'lsb19_USBL_data_rejected',
     'lsb20_Depth_sensor_used',
     'lsb21_Depth_sensor_data_valid',
     'lsb22_Waiting_for_Depth_sensor_data',
     'lsb23_Depth_sensor_data_rejected',
     'lsb24_LBL_used',
     'lsb25_LBL_data_valid',
     'lsb26_Waiting_for_LBL_data',
     'lsb27_LBL_data_rejected',
     'lsb28_Altitude_saturation',
     'lsb29_Speed_saturation',
     'lsb30_Reserved',
     'lsb31_Reserved',
     'msb00_Water_track_used',
     'msb01_Water_track_valid',
     'msb02_Waiting_for_water_track_data',
     'msb03_Water_track_rejected',
     'msb04_GPS_2_used',
     'msb05_GPS_2_data_valid',
     'msb06_Waiting_for_GPS_2_data',
     'msb07_GPS_2_data_rejected',
     'msb08_Metrology_used',
     'msb09_Metrology_data_valid',
     'msb10_Waiting_for_metrology_data',
     'msb11_Metrology_data_rejected',
     'msb12_Altitude_used',
     'msb13_Altitude_data_valid',
     'msb14_Waiting_for_altitude_data',
     'msb15_Altitude_data_rejected',
     'msb16_Mode_ZUP',
     'msb17_ZUP_valid',
     'msb18_Mode_ZUP_valid',
     'msb19_ZUP_Bench_valid',
     'msb20_Static_alignment',
     'msb21_Go_to_Nav',
     'msb22_Reserved',
     'msb23_Reserved',
     'msb24_EM_Log_used',
     'msb25_EM_Log_data_valid',
     'msb26_Waiting_for_EM_Log_data',
     'msb27_EM_Log_data_rejected',
     'msb28_GPS_manual_used',
     'msb29_GPS_manual_data_valid',
     'msb30_Waiting_for_GPS_manual_data',
     'msb31_GPS_manual_data_rejected'
     ]

#----

function_dict = {'gps': get_gga, # alias for gga
                 'gga': get_gga,
                 'ggn': get_gga_nochecksum,  #absurd
                 'gns': get_gns,
                 'rmc': get_rmc,
                 'spd': get_spd,
                 'ssv': get_ssv,
                 'raw_spd': get_rawspd,
                 'hdg': get_degrees,
                 'hnc': get_degrees_nochecksum,
                 'gph': get_degrees, # heading from 2 GPS, no inertial
                 'ths': get_ths, #heading with status
                 'adu': get_att,
                 'at2': get_at2,
                 'pat': get_paq,
                 'paq': get_paq,
                 'rdi': get_rdi,
                 'rdinc': get_rdinc,
                 'rnh': get_rnh,
                 'uvh': get_uvh,
                 'vbw': get_vbw,
                 'vtg': get_vtg,
                 'pmv': get_posmv_pashr,
                 'pvec': get_vector_pashr,
                 'psxn20': get_psxn20,
                 'psxn23': get_psxn23,
                 'tss1': get_tss1,
                 'psathpr': get_psathpr,
                 'ixrp': get_ixrp,
                 'ixgps': get_ixgps,
                 'ixsspd': get_ixsspd,
                 'ixalg': get_ixalg,
                 'gpgst': get_gpgst_str,
                 'ptnlvhd': get_ptnlvhd_str,
                 'jratt': get_jratt,
                 'jrattn': get_jratt_nochecksum,
                 'jrhve': get_jrhve,
                 'jrhven': get_jrhve_nochecksum,
                 'hpr': get_hpr,
                 'sea': None, # These will be filled in later,
                 'gps_sea': None,  # when an instance copy of the
                 'hnc_tss1': None,  # dictionary is made.
                 'hdg_tss1': None,
                 }


field_dict1 = {'gps': ['u_dday', 'dday', 'lon', 'lat', 'quality', 'hdop'],
               'gga': ['u_dday', 'dday', 'lon', 'lat', 'quality', 'hdop'],
               'ggn': ['u_dday', 'dday', 'lon', 'lat', 'quality', 'hdop'],
               'gns': ['u_dday', 'dday', 'lon', 'lat',
                            'svs', 'hdop', 'orhgt', 'geosep',],
               'rmc': ['u_dday', 'dday', 'lon', 'lat', 'ok'],
               'pmv': ['u_dday', 'dday', 'heading',
                       'roll', 'pitch', 'heave',
                       'acc_roll', 'acc_pitch', 'acc_heading',
                       'flag_GAMS', 'flag_IMU'],
               'pvec': ['u_dday', 'dday', 'heading',
                       'roll', 'pitch', 'heave',
                       'acc_roll', 'acc_pitch', 'acc_heading',
                       'flag_IMU'],
               'spd': ['u_dday', 'sndspd'],
               'ssv': ['u_dday', 'temp', 'sndspd'],
               'raw_spd': ['u_dday', 'raw_sndspd'],
               'hdg': ['u_dday', 'heading'],
               'hnc': ['u_dday', 'heading'],
               'gph': ['u_dday', 'heading'],
               'ths': ['u_dday', 'heading', 'status'],
               'adu': ['u_dday', 'dday', 'heading',
                                 'pitch', 'roll', 'mrms', 'brms',
                                 'reacq'],
               'at2': ['u_dday', 'dday', 'heading',
                                 'pitch', 'roll', 'mrms', 'brms',
                                 'reacq', 'lstate', 'ddiff', 'pdop'],
               'pat': ['u_dday', 'dday', 'lon', 'lat', 'alt', 'heading',
                                 'pitch', 'roll', 'mrms', 'brms'],
               'paq': ['u_dday', 'dday', 'lon', 'lat', 'alt', 'heading',
                                 'pitch', 'roll', 'mrms', 'brms', 'reacq'],
               'rdi': ['u_dday', 'pitch', 'roll', 'heading'],
               'rdinc': ['u_dday', 'pitch', 'roll', 'heading'],
               'rnh': ['u_dday', 'pitch', 'roll'],
               'uvh': ['u_dday', 'u', 'v', 'heading'],
               'vbw': ['u_dday', 'fwd_w', 'stbd_w', 'flag_w'],
               'vtg': ['u_dday', 'cogT', 'cogM', 'kts', 'mps'],
               'psxn20': ['u_dday', 'horiz_qual', 'height_qual',
                           'head_qual', 'rp_qual'],
               'psxn23': ['u_dday', 'roll', 'pitch', 'heading', 'heave'],
                             # Note: heave is not always present; it will
                             # be filled with NaN if absent.
               'psathpr': ['u_dday', 'dday', 'heading',
                                     'pitch', 'roll', 'flag_gps'],
               'sea': ['u_dday', 'dday', 'roll', 'pitch', 'heading', 'heave',
                        'height_qual', 'head_qual', 'rp_qual'],
               'gps_sea': ['u_dday', 'dday', 'lon', 'lat',
                            'quality', 'hdop', 'horiz_qual'],
               'tss1': ['u_dday', 'status', 'haccel', 'vaccel',
                             'heave', 'roll', 'pitch'],
               'hnc_tss1': ['u_dday', 'heading', 'status', 'haccel', 'vaccel',
                             'heave', 'roll', 'pitch'],
               'hdg_tss1': ['u_dday', 'heading', 'status', 'haccel', 'vaccel',
                             'heave', 'roll', 'pitch'],
               'ixrp': ['u_dday', 'roll', 'pitch'],
               'ixgps': ['u_dday', 'lat', 'lon', 'altitude'],
               'ixsspd': ['u_dday', 'uship', 'vship', 'zship'],
               'ixalg': ['u_dday', ] + ix_algnames,
               'gpgst': ['u_dday', 'dday', 'resid_rms_rng', 'smjr_std',
                             'smnr_std', 'orient', 'lat_std', 'lon_std',
                             'alt std'],

               'ptnlvhd': ['u_dday', 'dday', 'mmddyy', 'azth', 'aztht',
                             'vert_ang', 'vertt', 'range', 'ranget', 'gpsqi',
                             'nb_sat', 'pdop'],
               'jratt': ['u_dday', 'yaw', 'pitch', 'roll'],
               'jrattn': ['u_dday', 'yaw', 'pitch', 'roll'],
               'jrhve': ['u_dday', 'heav', 'qc_r'],
               'jrhven': ['u_dday', 'heav', 'qc_r'],
               'hpr': ['u_dday', 'dday', 'heading', 'pitch', 'roll', 'mrms', 'brms',
                       'ia', 'bm', 'y', 'x1', 'x2', 'x3', 'pdop'],
               }


class Asc2binBase:
    """
    Base class for asc2bin in asc2bin.py and serasc2bin.py.

    It is purely a mixin, factoring out the few methods that
    are identical.
    """
    def get_UNIX_dday(self, str_):
        if str_[:7] == b'$UNIXD,':
            fields = str_[7:].split(b',')
            log_dday = float(fields[0])  # this was dday for log_yearbase
            #returns [u_dday, m_dday] or [u_dday, u_dday] for older $UNIXD
            return [log_dday + self.yearbase_dif_days, float(fields[-1])]
        elif str_[:7] == b'$UNIXT,':
            ut = float(str_[7:])
            return [(ut - self.epoch_t)/86400.0, 0.0]
        elif str_[:7] == b'$PYRTM,':
            fields = str_[7:].split(b',')
            yearbase = int(fields[0])
            dday = float(fields[1])
            m_dday = float(fields[2])
            if yearbase != self.yearbase:
                log_days = datetime.date(yearbase, 1, 1).toordinal()
                dday += (log_days - self.yearbase_ordinal)
            return [dday, m_dday]
        else:
            raise ValueError

    def check_gga_dday(self, r):
        r[1] = frac_to_dday(r[0], r[1])
        if abs(r[1] - self.last_dday) < 1e-7: # around 0.01 s
            return []
        self.last_dday = r[1]
        return r

    def check_adu_dday(self, r):
        """
        ATT message uses GPS time.  We have to correct for leap seconds.
        """
        pctime = datetime.datetime(self.yearbase, 1, 1) + datetime.timedelta(days=r[0])
        leap = 13  # We probably won't have any data old enough to need this.
        for dt, seconds in reversed(gps_leapseconds):
            if pctime > dt:
                leap = seconds
                break
        r[1] = frac_to_dday(r[0], r[1] - leap / 86400)
        if abs(r[1] - self.last_dday) < 1e-7: # around 0.01 s
            return []
        self.last_dday = r[1]
        return r

    def get_sea(self, str_):
        f = get_gga(str_)
        if f:
            self.last_gga = f
            return None
        f = get_psxn20(str_)
        if f:
            self.last_psxn20 = f
            return None
        f = get_psxn23(str_)
        if f and self.last_psxn20 and self.last_gga:
            return self.last_gga[0:1] + f + self.last_psxn20[1:]

    def get_gps_sea(self, str_):
        f = get_gga(str_)
        if f:
            self.last_gga = f
            return None
        f = get_psxn20(str_)
        if f and self.last_gga:
            return self.last_gga + f[0:1]
