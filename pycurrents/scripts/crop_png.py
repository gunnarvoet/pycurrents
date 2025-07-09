#!/usr/bin/env python

import os
import subprocess
import argparse

parser = argparse.ArgumentParser(
                  description='Crop (and optionally quantize) png files.')
parser.add_argument('fnames', metavar='filename', type=str, nargs='+',
                    help='paths of files to crop')
parser.add_argument('-q', '--quantize', action='store_true',
                    help='quantize (use a 256-color palette)')
group = parser.add_mutually_exclusive_group()
group.add_argument('--inplace', action='store_true',
                   help='modify the source file in place')
group.add_argument('--outdir', default='./',
                    help='output directory')
parser.add_argument('--clobber', action='store_true',
                    help='allow destination to be overwritten')
parser.add_argument('-m', '--margin', type=int, default=0,
                    help='white margin in pixels')
parser.add_argument('-v', '--verbose', action='store_true',
                    help='print the source and target')
parser.add_argument('--dry_run', action='store_true',
                    help="print but don't execute the command pipeline")
args = parser.parse_args()

for fname in args.fnames:
    fname = os.path.expanduser(fname)
    if args.inplace:
        outname = fname
    else:
        outname = os.path.join(args.outdir, os.path.basename(fname))
        outname = os.path.expanduser(outname)
    outname_tmp = outname + ".tmp"
    if not (args.clobber or args.inplace) and os.path.exists(outname):
        print(f"Skipping; source {fname} which would clobber {outname}.")
        continue
    parts = [f'pngtopnm {fname}']
    parts.append('pnmcrop')
    # The -margin option to pnmcrop is missing in the ancient libpbm still
    # being shipped by Ubuntu, so we use the pnmpad command instead.
    if args.margin:
        m = args.margin
        parts.append(f'pnmpad -left={m} -right={m} -top={m} -bottom={m} -white')
    parts.append('pnmtopng')
    if args.quantize:
        parts.append('pngquant -')
    cmd = ' | '.join(parts) + f' >{outname_tmp}; mv {outname_tmp} {outname}'
    if args.dry_run:
        print(cmd)
    else:
        output = subprocess.check_output(cmd, shell=True)
    if args.verbose:
        print(f"{fname} -> {outname}")
