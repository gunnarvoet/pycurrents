#!/usr/bin/env python

## JH, Jan 2006

'''
looks through a pingdata scan file and writes to loadping_info.txt:
- potential time change problems at the top
- a complete loadping.cnt file which skips unknown positions (99999)

Run this from the 'load' directory in an adcptree processing directory

usage:
       mk_loadping.py      -d dbname   -s scanfile
       mk_loadping.py --dbname  dbname --scanfile scanfile
'''


import sys
import os
import re
import getopt

if len(sys.argv) == 1:
    print(__doc__)
    sys.exit()


try:
    options, args = getopt.getopt(sys.argv[1:], 'd:s:v',
       ['dbname=', 'scanfile=', 'verbose' ])
except getopt.GetoptError:
    print(__doc__)
    sys.exit()

verbose = 0
dbname = None
scanfile = None
outfile = 'loadping.tmp'


for o, a in options:
    if o in ('-d', '--dbname'):
        dbname = a
    if o in ('-o', '--outfile'):
        dbname = a
    if o in ('-s', '--scanfile'):
        scanfile = a
    elif o in ('-v', '--verbose'):
        verbose = 1



def write_info(scanfile = None, dbname = None):

    if not dbname:
        print('must set dbname\n')
        print(__doc__)
        sys.exit()
        if not dbname:
            print('must set scanfile\n')
            print(__doc__)
            sys.exit()


    ########
    if not os.path.exists(scanfile):
        print('cannot find file %s\n' %(scanfile,))
        sys.exit()

    try:
        sfid = open(scanfile,'r')
    except:
        raise



    timepat = r"\b\d{2,4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\b"
    filepat = r"PINGDATA\.\d{3}"


    # get the contents of scanfile
    fullstr = sfid.read()
    sfid.close()

    recs = fullstr.split('DATA FILE NAME')


    #initialize loadping.tmp
    print('writing %s\n' % (outfile))
    lfid = open(outfile,'w')


    print('checking for bad times: negative offsets will be noted\n')
    setback = -30
    setfwd  =  30
    for pingrec in recs:
        if len(pingrec) < 10 :
            continue
        # identify file
        matchobj = re.findall(filepat, pingrec)
        if len(matchobj) >0:
            print('../ping/%s\n' % (matchobj[0],))
            lines = pingrec.split("\n")
            for line in lines:
                matchobj = re.findall(timepat, line)
                if len(matchobj) > 0:
                    ts = line.split(":")
                    dt_min = int(ts[0].split()[-1])
                    dt_sec = int(ts[1].split()[0])
                    secs = dt_min*60 + dt_sec
                    if secs < setback:
                        print('time change\n')
                        print(line)
                        lfid.write('/*  %s */\n' % (line))


    lfid.write('\n'.join(['DATABASE_NAME:            ../adcpdb/%s' % (dbname),
                            'DEFINITION_FILE:          ../adcpdb/adcp1920.def',
                            'OUTPUT_FILE:              ../adcpdb/%s.lod' % dbname,
                            'MAX_BLOCK_PROFILES:       400',
                            'NEW_BLOCK_AT_FILE?        yes',
                            'NEW_BLOCK_AT_HEADER?      no',
                            'NEW_BLOCK_TIME_GAP(min):  32767',
                            '',
                            'PINGDATA_FILES:',
                            '']))

    for pingrec in recs:
        if len(pingrec) < 10 :
            continue
        # identify file
        matchobj = re.findall(filepat, pingrec)
        if len(matchobj) >0:
            print(matchobj[0])
            lfid.write('../ping/%s\n' % (matchobj[0]))

            skipproflist = []
            skiphdrlist = []
            # if it has a time, look for bad headers
            lines = pingrec.split("\n")
            for line in lines:
                matchobj = re.findall(timepat, line)
                if len(matchobj) > 0:
                    parts = line.split()
                    pc_timediff = int(parts[-1])
                    hdr = int(parts[0])
                    prof = int(parts[1])
                    if (pc_timediff == 99999) or (pc_timediff < setback) or \
                           (pc_timediff > setfwd):

                        if (len(skiphdrlist) == 0):
                            skiphdrlist.append(hdr)
                            skipproflist.append(prof)
                        elif skiphdrlist[-1] != hdr:
                            skipproflist = [prof]
                            skiphdrlist = [hdr]
                        else:
                            skiphdrlist.append(hdr)
                            skipproflist.append(prof)

                    else:
                        if len(skiphdrlist) > 0:
                            lfid.write('       skip_profile_range:\n')
                            lfid.write('            hdr= %d\n' % skiphdrlist[0])
                            lfid.write('            prof= %d to %d\n' % \
                                       (skipproflist[0], skipproflist[-1]))
                            skipproflist = []
                            skiphdrlist = []


                matchobj = re.findall(r"Statistics", line)
                if len(matchobj) > 0:
                    if len(skiphdrlist) > 0:
                        lfid.write('       skip_profile_range:\n')
                        lfid.write('            hdr= %d\n' % skiphdrlist[0])
                        lfid.write('            prof= %d to %d\n' % \
                                   (skipproflist[0], skipproflist[-1]))
                        skipproflist = []
                        skiphdrlist = []

                    lfid.write('       end\n')


    lfid.close()


if __name__ == '__main__':
    write_info(scanfile, dbname)
