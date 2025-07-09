#!/usr/bin/env python


'''
Fix a problem that is found in some old CODAS databases,
in which RAW_SPECTRAL_WIDTH and ADCP_CTD were specified as
structures, but the structure definitions were absent. This
caused a failure when trying to run mkblkdir to change to
a different machine type.

Run this in the directory with the block files (with or
without the block directory file) and it will fix the files
in place.

2006/05/02 EF

Original matlab documentation:
function fix_sw_struct
% This function looks for all the codas blockfiles in
% the current directory; for all but the block directory,
% it then changes the RAW_SPECTRAL_WIDTH from STRUCT to
% UBYTE.
% I wrote a cruder version called "fixit.m" for Pat Caldwell
% a year or two ago.
% If we keep running into related, but not identical,
% problems needing this sort of fix, then this can be
% generalized more.
%
% EF 2001/12/14
'''

import glob
import struct

files = [f for f in glob.glob('*.blk') if not f.endswith('dir.blk')]

of1 = 160 + 56 * 66 + 32  # sz_blk_hdr + sz_data_dir_entry * data_id + ofs
                           # 66 is RAW_SPECTRAL_WIDTH
                           # Pat also needed this applied to 76 on occasion

of2 = 160 + 56 * 76 + 32

for fname in files:
    print(fname, end=' ')
    f = open(fname, 'r+')
    cc = f.read(5)
    if cc[4] == 'P':
        fmt = '<h'
    else:
        fmt = '>h'
    for offset in (of1, of2):
        f.seek(offset)
        dtype = struct.unpack(fmt, f.read(2))[0]
        if dtype == 11:
            f.seek(offset)
            f.write(struct.pack(fmt, 1))
            print(offset, end=' ')
    f.close()
    print()
