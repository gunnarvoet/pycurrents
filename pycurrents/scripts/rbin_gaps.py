#!/usr/bin/env python
'''
rbin_gaps.py [options] uhdas_dir

--help             : print help and exit

--prefix prefix    : save files using this prefix (default is basename)

# statistics to calculate :
--all              : do all of these

--between          : time between file end and subsequent file start
                   :    - printed in seconds
                   :    - one file per instrument_message found

--rbintimes        : print statistics of time gaps within files

--clock            : print statistics of m_dday times

'''

# rbin_gaps.py (stub to access components from pycurrents.adcp.rbin_stats)

import sys
from optparse import OptionParser

import pycurrents.adcp.rbin_stats as rbs

if __name__ == '__main__':

    if len(sys.argv) == 1 or '-h' in sys.argv or '--help' in sys.argv:
        print(__doc__)
        sys.exit()

    parser = OptionParser(__doc__)

    parser.add_option("-a", "--all", dest="all", action="store_true",
                      default=False,
                      help="print all statistics")
    parser.add_option("-b", "--between", dest="between", action="store_true",
                      default=False,
                      help="print file with seconds-between-files")
    parser.add_option("-r", "--rbintimes", dest="rbintimes", action="store_true",
                      default=False,
                      help="print rbin statistics")
    parser.add_option("-c", "--clocks", dest="clocks", action="store_true",
                      default=False,
                      help="print file with anomalous clock times")
    parser.add_option("-p", "--prefix", dest="prefix",
                      default = None,
       help="prefix for filenames (default is crusieid)")

    (options, args) = parser.parse_args()

    uhdas_dir = args[0]
    if uhdas_dir[-1] == '/':
        uhdas_dir=uhdas_dir[:-1]
    print('getting rbin stats from %s' % (uhdas_dir))

    prefix = options.prefix

    rbindirs = rbs.find_rbindirs(uhdas_dir)
    print(rbindirs)
    for rbindir in rbindirs:
        msgs = rbs.find_msgs(rbindir, uhdas_dir, verbose=True)


    if options.all:
        options.between = True
        options.rbintimes = True
        options.clocks = True


    if options.between:
        for rbindir in rbindirs:
            msgs = rbs.find_msgs(rbindir, uhdas_dir)
            for msg in msgs:
                slist = rbs.get_slist(rbindir, msg, uhdas_dir)
                RS = rbs.RbinSegments(slist)
                if prefix:
                    outfile = '_'.join((prefix, 'rbin_gaps.txt'))
                else:
                    outfile = 'rbin_gaps.txt'
                RS.print_gaps_between(outfile=outfile)

    if options.rbintimes:
        wlist = []
        slist = ['        ' + rbs.Diffstats.labels]
        for rbindir in rbindirs:
            msgs = rbs.find_msgs(rbindir, uhdas_dir)
            for msg in msgs:
                s, w = rbs.check_rbintimes(rbindir, uhdas_dir, msg)
                wlist.append(w)
                slist.append(s)
            slist.append('\n')
        if prefix:
            outfile = '_'.join((prefix, 'rbintimes.txt'))
        else:
            outfile = 'rbintimes.txt'
        F = open(outfile,'w')
        F.write("======= rbintimes =========\n")
        F.write('\n'.join(slist) + '\n')
        if len(''.join(wlist)) > 0:
            # trim out empty lines
            wstr = '\n'.join(wlist)
            short_wlist = []
            for w in wstr.split('\n'):
                if len(w) > 0:
                    short_wlist.append(w)
            numwarn = len(short_wlist)
            if numwarn>0:
                F.write("====== rbintimes (%d warnings) =====\n" % (numwarn))
                header = '%20s'%(' ')+'dday ' + rbs.Diffstats.labels + '\n'
                F.write(header + '\n'.join(short_wlist) + '\n')
        F.close()


    if options.clocks:
        wlist = [''] #warnings
        slist=['']
        for rbindir in rbindirs:
            msgs = rbs.find_msgs(rbindir, uhdas_dir)
            for msg in msgs:
                s, w = rbs.check_clock(rbindir, uhdas_dir, msg)
                wlist.append(w)
                slist.append(s)
            slist.append('\n')
        if prefix:
            outfile = '_'.join((prefix, 'clock.txt'))
        else:
            outfile = 'clock.txt'
        F = open(outfile,'w')
        F.write("======= clocks =========\n")
        F.write('\n'.join(slist) + '\n')
        if len(''.join(wlist)) > 0:
            F.write("======= clocks (warnings) =========\n")
            F.write('\n'.join(wlist) + '\n')
        F.close()
