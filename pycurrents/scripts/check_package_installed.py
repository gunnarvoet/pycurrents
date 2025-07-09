#!/usr/bin/env python
import os
import glob
import sys
from importlib import import_module

usage = '''
This program tests whether there are multiple installations
of 'pycurrents and 'uhdas' installed on your system.

Action:

           Print the commands to use to clear out the old versions.
           (You must take that action)

Explanation:

Code installed prior to Jan 1 2020 used a python installation scheme
called "distutils".  After Jan 1, 2020, pycurrents and uhdas packages
are now installed using "setuptools".  There were good reasons for doing
this, but the "installed" locations are actually slightly different
and can live alongside each other, causing Python to be confused
about what it is using.

Details (example)

distutils:
/usr/local/lib/python3.6/dist-packages/pycurrents-0.0.0.egg-info   # a file
/usr/local/lib/python3.6/dist-packages/pycurrents                  # a directory

setuptools:
/usr/local/lib/python3.6/dist-packages/pycurrents-0.0.0-py3.6-linux-x86_64.egg

The appropriate solution is to delete all installed versions of pycurrents
and uhdas, and re-install.
'''




if '-h' in sys.argv:
    print(usage)
    sys.exit()


for modstr in ('pycurrents', 'uhdas'):
    installed_list = []
    try:
        mod = import_module(modstr)
        plist=mod.__path__[0].split(os.path.sep)
        if 'site-packages' in plist:
            index = plist.index('site-packages')
        elif 'dist-packages' in plist:
            index = plist.index('dist-packages')
        else:
            print('cannot find %s in site-packages or dist-packages' % (modstr))
            index=-1

        if index > 0:
            location = os.path.sep.join(plist[:index+1])
            names = sorted(glob.glob(os.path.join(location, '*'+modstr+'*')))
            installed_list.extend(names)

            print('# found %d installed items related to %s ' % (len(installed_list), modstr))
            print('# remove with:')
            for installed_thing in installed_list:
                print('    sudo rm -Rf %s' % (installed_thing))
        else:
            print("%s is not installed for this version of Python" % (modstr))
    except Exception as e:
        print(e)
