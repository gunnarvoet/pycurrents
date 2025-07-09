#!/usr/bin/env python
"""
Create a short-form netcdf file from a CODAS shipboard ADCP
database.

usage: adcp_nc.py dbpath outfilebase cruisetitle sonar
"""

from pycurrents.adcp.adcp_nc import main

main()

