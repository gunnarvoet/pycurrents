#!/usr/bin/env python

"""
Parse PMEL ascii CTD data files with multiple profiles per file.

This is the format in which the TAO CTD data have been given to us;
we don't know how standard or widely used the format is.

If run as a script, with a list of such files on the command line,
this program will write a separate bin file for each profile, and
will write a *.table file with selected header data for each input file.
Binfiles will be written in the current working directory; the *.table
file will be written in the same directory as the corresponding original
ascii file.

The header variables are:
    cast name, which is also the base of the binfile name
    year
    month
    day
    hour
    minute
    longitude
    latitude
    ocean depth  (-1 if not available)
    max cast pressure

The binfiles have only pressure, temperature, and salinity.  They use
float32, which should provide adequate accuracy.

This module is a bare-minimum version with no attempt at refinements
such as command-line switches to control data output.  It has been
used on very few files; for wider use it might require additional
code to handle special cases or variations in the file format.

"""
import re
import time
import sys
import numpy

from pycurrents.file.binfile_n import binfile_n

class ctdfile:
    h1 = re.compile('CAST\W*(.*?)\W*DATE\W*(.*?)\W*TIME\W*(\d{4})\W*GMT .*')
    h2 = re.compile('LAT\W*(.*?)\W*LONG\W*(.*?)\W*WEATHER .*')
    h4 = re.compile('DEPTH\W*(\d+)\W*M')

    def __init__(self, fname):
        self.filename = fname
        self.file = open(fname)
        self.currentline = None
        self.eof = False
        self.dtype = numpy.dtype(numpy.float32)

    @staticmethod
    def convert_date_time(tdate, ttime):
        st = time.strptime(' '.join([tdate, ttime]), '%d %b %y %H%M')
        return st[:5]

    @staticmethod
    def convert_lat(tlat):
        deg, minNS = tlat.split()
        min = minNS[:-1]
        if minNS[-1] == 'N':
            return float(deg) + float(min)/60.0
        else:
            return -(float(deg) + float(min)/60.0)

    @staticmethod
    def convert_lon(tlon):
        deg, minEW = tlon.split()
        min = minEW[:-1]
        if minEW[-1] == 'E':
            return float(deg) + float(min)/60.0
        else:
            return -(float(deg) + float(min)/60.0)

    def read_header(self):
        if self.currentline is None:
            line = self.file.readline()
        else:
            line = self.currentline
        cast, date, time = self.h1.match(line).groups()
        line = self.file.readline()
        lat, lon = self.h2.match(line).groups()
        self.file.readline()
        line = self.file.readline()
        try:
            depth = self.h4.search(line).groups()[0]
        except AttributeError:
            depth = -1
        for i in range(4):
            self.file.readline()
        ret = [cast]
        ret.extend(list(self.convert_date_time(date, time)))
        ret.append(self.convert_lon(lon))
        ret.append(self.convert_lat(lat))
        ret.append(float(depth))
        return ret

    def read_cast_data(self):
        reclist = []
        while True:
            line = self.file.readline()
            if not line:
                self.eof = True
                break
            if line.startswith('CAST'):
                self.currentline = line
                break
            reclist.append(numpy.fromstring(line, count=3,
                                            dtype=self.dtype, sep=' '))
        return numpy.array(reclist)

    def read_cast(self):
        header = self.read_header()
        data = self.read_cast_data()
        return header, data

    def extract_casts(self):
        hfile = open(self.filename+'.table', 'w')
        fmt = "%20s %4d %2d %3d %2d %2d %10.5f %10.5f %4d %4d\n"
        while not self.eof:
            header, data = self.read_cast()
            header.append(data[:,0].max())
            hfile.write(fmt % tuple(header))
            bf = binfile_n(header[0] + '.bin', 'w',
                        type='f4',
                        columns=['P', 'T', 'S'],
                        name='TAO_CTD')
            bf.write(data)
            bf.close()
        hfile.close()


if __name__ == '__main__':
    for fname in sys.argv[1:]:
        ctdfile(fname).extract_casts()


