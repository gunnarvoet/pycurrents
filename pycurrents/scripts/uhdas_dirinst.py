#!/usr/bin/env python

'''

usage:
    uhdas_instname.py shipletters  [-d dirname]

returns:
    printed table with columns [dirname, instrument name, messages parsed]

if "-d" is specified, only output the "instrument name"
   (no messages)

eg.

   uhdas_instname.py en

## returns

              subdir       instrument name              messages
          ----------          ----------------    ------------

             gpsnav1           Norstar GPS              ('gps',)
                gyro                  Gyro              ('hdg',)
              gpsnav            Furuno GPS              ('gps',)
             dualref               DualRef              ('pmv',)



   uhdas_instname.py en -d gpsnav

## returns

Furuno GPS

'''

import sys
from optparse import OptionParser
from importlib import import_module
from pycurrents.system.misc import Bunch
from  onship import shipnames

# keys are the same 2-letter abbreviation, eg. 'kk'

if ('--help' in sys.argv) or (len(sys.argv) == 1):
    print(__doc__)
    sys.exit()


if __name__ == "__main__":
    qsletters=[]
    for k in shipnames.shipletters:
        qsletters.append("'%s'" % k)
    shipletters=','.join(qsletters)

    usage = '\n'.join(["\n\nusage for UH-managed ships:",
         "    uhdas_instname.py XX ",
         "   choose one ship abbreviation (XX) from:",
         shipletters,
         "",
         "",
         ])

    if len(sys.argv) == 1:
        print(usage)
        sys.exit()

    parser = OptionParser(usage)

    parser.add_option("-d",  "--dirname", dest="dirname",
                      default=None,
                      help="if specified, only output the corresponding instrument")

    (options, args) = parser.parse_args()


    if len(args) > 1:
        print(usage)
        raise IOError('must specify ship letters for one ship')

    shipkey = args[0]
    if shipkey not in shipnames.shipletters:
        print(usage)
        raise IOError('must specify CORRECT ship letters')

    sensor_cfg = import_module('onship.sensor_cfgs.%s_sensor_cfg' % (shipkey))

    sebunch = Bunch()
    for sdict in sensor_cfg.sensors:  # list of dictionaries
        if 'messages' in sdict.keys(): # ADCPS do not have 'messages'
            sebunch[sdict['subdir']] = (sdict['instrument'],  sdict['messages'])


    if options.dirname is None:
        print('\n%20s  %20s  %20s' % ('subdir', 'instrument name', 'messages'))
        print('          ----------          ----------------    ------------\n')
    for key in sebunch.keys():
        instrument, messages = (sebunch[key][0], sebunch[key][1])

        if options.dirname is None:
            print('%20s  %20s  %20s' % (key, instrument, messages))
        else:
            if options.dirname == key:
                print(instrument)
