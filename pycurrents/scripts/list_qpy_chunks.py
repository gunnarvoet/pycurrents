#!/usr/bin/env python

'''
list ocean surveyor 'first' pingtype and time ranges for chunks
'''
# FIXME: Does the docstring match what the script does?
# FIXME: Clean up the usage (no Windows) and use the script docstring.
# FIXME: Is this script even used?  If so, add EC support.  Otherwise, delete.

from optparse import OptionParser
import sys

from pycurrents.system import pathops
from pycurrents.adcp.raw_multi import Multiread   # singleping ADCP

def usage():
    print('create a list of calls to quick_adcp.py to process data with')
    print('       chunks of bb and chunks of nb pings.  Ocean Surveyor only')
    print('')
    print('usage: ')
    print('list_qpy_chunks.py filelist')
    print('')
    print('examples for Windows:')
    print('list_qpy_chunks.py  os75 ps0918\*.LTA')
    print('')
    print('unix (linux, osx) example:')
    print('list_qpy_chunks.py  os75 ps0918/*.LTA')
    sys.exit()



if __name__ == '__main__':

    if len(sys.argv) == 1:
        usage()

    parser = OptionParser()
    parser.add_option("--verbose", dest="verbose",
                      action="store_true",
                      default=False,
                      help="print additional information")

    parser.add_option("--pingpref", dest="pingpref",
                      default = None,
                      help="if interleaved, process these pings ")

    (options, args) = parser.parse_args()

    instrument = args[0]
    if instrument[:2] not in ('os', 'pn'):
        usage()

    filelist=pathops.make_filelist(args[1:])

    m=Multiread(filelist, instrument[:2])

    sfmt='quick_adcp.py --cntfile q_py.cnt --sonar %s%s --incremental  --dday_bailout %8.5f --auto'


print('')

for ichunk in range(len(m.chunks)):
    # first pingtypes in chunk, first pingtype
    chunk = m.chunks[ichunk]
    nfiles = len(chunk)
    pingtypes = m.pingtypes[chunk[0]] # pingtypes don't change in a chunk
    pingnames = list(pingtypes.keys())
    if len(pingnames) == 1:
        pingtype = pingnames[0]
    else:
        if options.pingpref is None:
            print('interleaved pings found.  Must select with option "--pingpref"')
            sys.exit()
        pingtype = options.pingpref
    #
    pingstr = ''
    if 'bb' in pingnames:
        pingstr+='bb '
    else:
        pingstr+='   '
    if 'nb' in pingnames:
        pingstr+='nb '
    else:
        pingstr+='   '
    pingstr+='(%s) ' % (pingtype)
    #
    m.select_chunk(ichunk=ichunk)
    dd=m.read(ends=1)
    if options.verbose:
        print('\n#', ichunk, pingstr, 'nfiles=%3d' % (nfiles), dd.dday)
    print(sfmt % (instrument, pingtype, dd.dday[-1]))

print('')
