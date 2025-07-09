
''' checksums.pyx Pyrex checksum routines '''


# 2003/06/23 EF First try at a Pyrex module, prompted
# by a python profiler run that showed the checksum
# routine to be a major time sink in rtdas2bin.py.
# To compile:
#     pyrexc checksums.pyx
#     gcc -c -fPIC -I/usr/include/python2.3 checksums.c
#     gcc -shared checksums.o -o checksums.so
#
# Modified 2005/03/27 to perform an rstrip, and return
# the string without the checksum.


def NMEA(str_):
   cdef int i, bcs, nb, cs
   cdef int n
   cdef char *buf
   n = len(str_)
   buf = str_
   # Do a fast rstrip:
   while buf[n-1] < 48 and n > 10:
      n = n - 1
   if n <= 10:
      raise ValueError("too short")
   cs = int(str_[(n-2):n], 16)
   nb = n - 3
   buf[nb] = 0
   bcs = buf[1]       # Don't include the $
   for i from 2 <= i < nb:
      bcs = bcs ^ buf[i]
   #print cs, bcs, nb
   if cs != bcs:
      raise ValueError("Checksum mismatch")
   return buf

def HERC(str_):
   cdef int i, bcs, nb
   cdef int n
   cdef char *buf
   n = len(str_)
   buf = str_
   # Do a fast rstrip:
   while buf[n-1] < 48 and n > 10:
      n = n - 1
   if n <= 10:
      raise ValueError("too short")
   cs = int(str_[(n-2):n], 16)
   nb = n - 3
   buf[nb] = 0
   bcs = buf[0]       # Include the $
   for i from 1 <= i < nb:
      bcs = bcs ^ buf[i]
   if cs != bcs:
      raise ValueError("Checksum mismatch")
   return buf



