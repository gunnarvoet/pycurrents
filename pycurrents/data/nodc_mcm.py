#!/usr/bin/env python

'''
   This is a quick and dirty script to read an NODC current meter
   file (file name given on the command line) with format F015 and to
   write out the records of type 4 to a flat ascii file.
   The output filename is the input filename with
   '.asc' appended.

    The fields are:
        year
        month
        day
        hour
        minutes
        seconds
        U (m/s)
        V
        T (degrees)
        P (decibars)
        S (PSU)

    Fields are delimited by spaces.
    Missing T, P, S are nan.
    If anything else is missing, this script will not do the right thing.

    If we end up doing anything serious with NODC MCM files, this will
    most likely be rewritten as a function or class to yield a nice
    numpy recarray.

    For one source of these files, see
    http://gcmd.nasa.gov/records/GCMD_FW00061.html

    Example of the top of one such file:

015TV499110000   ORIGINATORS METER NUMBER=  C31            0
015TV499110000 GULF OF GUINEA CURRENT METER DATA           1
015TV499120001 000200S0031200W 4996 6490       0    C3  4740
015TV499140001 1976 7 8220000  -204   309 5229               1
015TV499140001 1976 7 8230000  -389   176 5209               2
015TV499140001 1976 7 9     0  -692   103 5226               3
015TV499140001 1976 7 9 10000  -658   306 5185               4
015TV499140001 1976 7 9 20000  -837   395 5224               5
015TV499140001 1976 7 9 30000  -969   403 5242               6
015TV499140001 1976 7 9 40000  -987   411 5480               7
015TV499140001 1976 7 9 50000  -906   446 5547               8
015TV499140001 1976 7 9 60000 -1030   454 5556               9
015TV499140001 1976 7 9 70000 -1220   238 5408              10
015TV499140001 1976 7 9 80000  -738   317 5158              11
015TV499140001 1976 7 9 90000  -544   216 5143              12
015TV499140001 1976 7 9100000  -446   138 5145              13
015TV499140001 1976 7 9110000  -359   345 5143              14
015TV499140001 1976 7 9120000  -394   628 5141              15
015TV499140001 1976 7 9130000  -527   826 5141              16
015TV499140001 1976 7 9140000  -744   913 5145              17
015TV499140001 1976 7 9150000  -797   969 5143              18



'''

import sys

def hms_from_HHMMHH(arg):
    i = int(arg)
    hh = i // 10000
    i -= hh * 10000
    mm = i // 100
    ss = (i % 100)/60
    return hh, mm, ss

nan = float('nan')

fname = sys.argv[1]
outfname = fname + '.asc'
outf = open(outfname, 'w')

with open(fname) as newreadf:
    lines = newreadf.readlines()
for line in lines:
    if line[9] != '4':
        continue
    YYYY = int(line[15:19])
    MM = int(line[19:21])
    DD = int(line[21:23])
    HHMMHH = line[23:29]
    hh, mm, ss = hms_from_HHMMHH(HHMMHH)
    U = float(line[29:35]) / 10000
    V = float(line[35:41]) / 10000
    try:
        T = float(line[41:46]) / 1000
    except ValueError:
        T = nan
    try:
        P = float(line[46:51]) / 10
    except ValueError:
        P = nan
    try:
        S = float(line[51:56]) / 1000
    except ValueError:
        S = nan

    outf.write('%(YYYY)4d %(MM)2d %(DD)2d %(hh)2d %(mm)2d %(ss)2d %(U)7.3f %(V)7.3f %(T)7.3f %(P)6.1f %(S)6.3f\n' % vars())

outf.close()
