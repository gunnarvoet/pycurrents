#!/usr/bin/env python
'''
Specialized diagnostic plotting.

comparison plot of ship speeds calculated using two methods
 - codas fixes (first difference of the ensemble endpoints)
 - average of single-point ship speeds for 'good' profiles only

usage:

    plot_uvship.py filename

where the filename specifies a file used by the 'putnav'
program to add position and ship velocity data to a CODAS
database.
'''

from pycurrents.adcp.plot_uvship import main

main()

