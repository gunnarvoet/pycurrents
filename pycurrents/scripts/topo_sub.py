#! /usr/bin/env python
'''
We use two topography products, ETOPO and Smith-Sandwell.
Present versions we can parse are


(1) ETOPO:

go to http://www.ngdc.noaa.gov/mgg/global/global.html

      ETOPO1 Ice Surface

get this file: etopo1_ice_g_i2.zip


direct link:

http://www.ngdc.noaa.gov/mgg/global/relief/ETOPO1/data/ice_surface/grid_registered/binary/etopo1_ice_g_i2.zip

(2) Smith Sandwell:

go to   http://topex.ucsd.edu/WWW_html/mar_topo.html)

        "Global Topography V14.1"

get this file: topo_18.1.img

direct link:


ftp://topex.ucsd.edu/pub/global_topo_1min/topo_18.1.img


---------------------

Installation:

(1)

    - make a directory adjacent to the UH programs directory,
    - it must be called "topog"
    - inside "topog" make two directories
                   "etopo"
                   "sstopo"


    - ETOPO:
      - move the ETOPO file (etopo1_ice_g_i2.zip) into the etopo directory:
      - unzip there (etopo1_ice_g_i2.bin,etopo1_ice_g_i2.hdr)


    - Smith Sandwell:
      - move the Smith-Sandwell file (topo_18.1.img) to the sstopo directory

(2)

    - in a shell window, with all environment variables set correctly,
      change directories to uh_programs/pycurrents/data
      (if the UH programs directory is 'uh_programs')

      run:

            python topo_sub.py

    - this should generate 2 more files for each type of topography.
      (it takes a long time). Then you should have:


      (new)

          topog/sstopo/topo_18.1.img
          topog/sstopo/topo_18.1s3.img
          topog/sstopo/topo_18.1s9.img

          topog/etopo/etopo1_ice_g_i2.bin
          topog/etopo/etopo1_ice_g_i2_s3.bin
          topog/etopo/etopo1_ice_g_i2_s9.bin

      (alongside these)

          uh_programs/adcp_templates/[etc]
          uh_programs/codas3/[etc]
          uh_programs/pycurrents/[etc]

'''

from pycurrents.data.topo import Etopo_file, SS_file, MissingDataFileError

try:
    E = Etopo_file()
    print("Found %s" % E.fname)
    for n in E.nsubs[1:]:
        try:
            e = Etopo_file(nsub=n)
            print("Found %s" % e.fname)
        except MissingDataFileError:
            print("Making subset with %dx%d medians" % (n,n))
            E.make_subsets(nsubs=[n], verbose=True)
except MissingDataFileError:
    print("No Etopo files found")

try:
    E = SS_file()
    print("Found %s" % E.fname)
    for n in E.nsubs[1:]:
        try:
            e = SS_file(nsub=n)
            print("Found %s" % e.fname)
        except MissingDataFileError:
            print("Making subset with %dx%d medians" % (n,n))
            E.make_subsets(nsubs=[n], verbose=True)
except MissingDataFileError:
    print("No Smith-Sandwell files found")



print('finished')
