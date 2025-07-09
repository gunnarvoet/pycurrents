#!/usr/bin/env  python
from optparse import OptionParser
import os
import sys

from onship import shipnames
from pycurrents.adcp.uhdasconfig import Proc_Gen

if __name__ == "__main__":

    shiplist = []
    shipkeys = shipnames.shipkeys
    shipkeys.sort()
    for k in shipkeys:
        shiplist.append('%10s -- %s' % (k, shipnames.shipnames[k]))

    usage = '\n'.join(["\n\nusage:",
             "  ",
             " generate a new proc_cfg.py file for a UHDAS ship:",
             "      uhdas_config_gen.py -s shipletters [outfile]",
             " eg.\nuhdas_config_gen.py -s kk kk1105",
             "      (default output file is 'SS_proc.py', ",
             "       where SS is the ship letters)",
             " \nchoose one ship abbreviation from:"] + shiplist)

    if len(sys.argv) == 1:
        print(usage)
        sys.exit()

    parser = OptionParser(usage)

    parser.add_option("-s",  "--shipkey", dest="shipkey",
       default=None,
       help="ship abbreviation")

    (options, args) = parser.parse_args()

    if not options.shipkey:
        raise IOError('MUST specify ship letters')


    if len(args) == 0:
        procfile = '%s_proc.py' %(options.shipkey)
        comment = 'Be sure to rename the "%s" to use specific cruise name' % (procfile)
    else:
        procfile = '%s_proc.py' % (args[0])
        comment = ''

    shipkey   = options.shipkey

    # make proc_cfg.py
    P=Proc_Gen(shipkey=shipkey, shipinfo=None)
    if os.path.exists(procfile):
        print('\n\nfile "%s" exists.  not overwriting\n\n' % (procfile))
        sys.exit()
    P.write(procfile)
    print('\n===> wrote processing configuration to "%s"' % (procfile))
    print('\n NOTE: you must still edit the top of the file and add:')
    print('yearbase')
    print('uhdas_dir')
    print('shipname')
    print('cruiseid')
    print('')
    print('see example in "%s" comments\n' % (procfile))
    print(comment)
    print('')
