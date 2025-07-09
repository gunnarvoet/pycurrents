#!/usr/bin/env python
"""
Use the files from raw EC playback to make equivalent Seapath position and
heading files, roughly simulating what we would have gotten with UHDAS as
the original acquisition system.

This rewrites the *.log.bin files to substitute the EC time for the computer
and monotonic times.  It extracts the Seapath data from the *.raw files and
writes them out as *.gps.rbin and *.sea.rbin files, again with all times
coming from the EC.
"""

import argparse

from pathlib import Path
from shutil import copyfile

import numpy as np

from pycurrents.adcp.raw_multi import Multiread
from pycurrents.file.binfile_n import binfile_n

gps_columns = "u_dday dday lon lat quality hdop m_dday".split()
sea_columns = ("u_dday dday roll pitch heading heave"
               " height_qual head_qual rp_qual m_dday").split()

def write_seapath_rbins(ec_fname, dest_dir, yearbase=None):
    source = Path(ec_fname)
    gps_path = Path(dest_dir).joinpath(source.stem).with_suffix('.gps.rbin')
    sea_path = Path(dest_dir).joinpath(source.stem).with_suffix('.sea.rbin')
    log_path = source.with_suffix('.raw.log.bin')
    log_backup = source.with_suffix('.raw.log.bin.orig')

    bf_log = binfile_n(str(log_path))
    logrecords = bf_log.records
    logcolumns = bf_log.columns
    bf_log.close()

    if logrecords[0].unix_dday != logrecords[0].instrument_dday:
        if not log_backup.exists():
            copyfile(log_path, log_backup)
        logrecords.unix_dday = logrecords.monotonic_dday = logrecords.instrument_dday
        if yearbase is not None:
            logrecords.yearbase = yearbase
        bf_log = binfile_n(str(log_path), columns=logcolumns, mode='w',
                           name='ser_bin_log')
        bf_log.write(logrecords.view(dtype=np.float64))
        bf_log.close()

    # print(gps_path, sea_path)
    m = Multiread(str(source), 'ec', yearbase=yearbase)
    d = m.read()
    a_gps = np.zeros((m.nprofs, len(gps_columns)), dtype=np.float64)
    a_sea = np.zeros((m.nprofs, len(sea_columns)), dtype=np.float64)
    a_gps[:, 0] = a_sea[:, 0] = d.times['u_dday']
    a_gps[:, 1] = a_sea[:, 1] = d.dday
    a_gps[:, -1] = a_sea[:, -1] = d.times['m_dday']

    a_gps[:, 2] = d.VL['longitude']
    a_gps[:, 3] = d.VL['latitude']
    a_gps[:, 4] = 2  # quality
    a_gps[:, 5] = 1  # hdop
    missing = (a_gps[:, 2:4] == 0).all(axis=1)
    a_gps[missing, 2:4] = np.nan

    a_sea[:, 2] = d.VL['roll']
    a_sea[:, 3] = d.VL['pitch']
    a_sea[:, 4] = d.VL['heading']
    a_sea[:, 5] = d.VL['heave']
    a_sea[:, 6:-1] = 0  # height, head, rp quality
    missing = (a_sea[:, 2:6] == 0).all(axis=1)
    a_sea[missing, 2:6] = np.nan

    bf_gps = binfile_n(str(gps_path), columns=gps_columns, mode='w', name='gps')
    bf_gps.write(a_gps)
    bf_gps.close()

    bf_sea = binfile_n(str(sea_path), columns=sea_columns, mode='w', name='sea')
    bf_sea.write(a_sea)
    bf_sea.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
        #description='Fix binfiles from EC playback.')
    parser.add_argument('rawdir', help='Directory with *.raw files')
    parser.add_argument('rbindir', help='Directory where *.rbin will go')
    args = parser.parse_args()

    rawfiles = Path(args.rawdir).glob('*.raw')
    for rf in rawfiles:
        write_seapath_rbins(rf, args.rbindir)
        print(rf)
