#!/bin/env python
"""
This is a special-purpose "fixit" script for expert use only.
Use it when you have a cruise that crosses the year boundary,
and that was split such that legs were recorded with different
yearbases.  To glue the legs together, the .bin.log files and
the .rbin files from one or more legs need to be re-written
such that their decimal day columns are adjusted for a different
yearbase; for processing, all such files must be relative to the
same yearbase.

This script changes the files **in place**.  When assembling a
collection of cruise legs, first rsync to the new destination
the raw and rbin directories from the leg(s) you want to alter.
Then run this script on these files in the new location.
Last, rsync the files from the remaining legs.

The .log.bin files have a yearbase column.  The script checks
that the first entry in this column matches the original yearbase
argument given to the script, and raises an exception if they
don't match.

There is no such protection for the .rbin files, so it is up to
the user to ensure that the script is run only once and only with
the appropriate set of files.
"""

import argparse
import datetime
from pathlib import Path
import sys

from pycurrents.file.binfile_n import binfile_n

dday_names = ["unix_dday", "u_dday", "instrument_dday", "dday"]


def change_yearbase(fname, old_year, new_year):
    add_days = (datetime.date(old_year, 1, 1) - datetime.date(new_year, 1, 1)).days
    oldfile = binfile_n(fname)
    columns = oldfile.columns
    data = oldfile.read_n()[0]
    oldfile.close()
    if "yearbase" in columns:
        i_year = columns.index("yearbase")
        if (data[:, i_year] != old_year).any():
            raise RuntimeError(f"yearbase mismatch in {str(fname)}")
        data[:, i_year] = new_year
    for dday_name in dday_names:
        if dday_name in columns:
            icol = columns.index(dday_name)
            data[:, icol] += add_days
    newfile = binfile_n(fname, mode="w", name=oldfile.name, columns=columns)
    newfile.write(data)
    newfile.close()


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Change in place the yearbase in UHDAS .log.bin and .rbin files",
        epilog=__doc__,
    )
    parser.add_argument(
        "original_yearbase",
        metavar="Y_orig",
        type=int,
        help="original yearbase for data acquisition",
    )
    parser.add_argument(
        "new_yearbase",
        metavar="Y_new",
        type=int,
        help="new yearbase, after conversion",
    )
    parser.add_argument(
        "--dry-run",
        dest="no_go",
        action="store_true",
        help="print files that would be converted, and exit.",
    )
    parser.add_argument(
        "--globstr",
        type=str,
        help=(
            "Pathlib glob expression; you probably don't need to use this."
            " The default starts in the CWD and walks the tree,"
            " finding all .log.bin and .rbin files"
        ),
    )
    args = parser.parse_args()
    if args.globstr is None:
        paths = list(Path("./").glob("**/*.log.bin"))
        paths.extend(list(Path("./").glob("**/*.rbin")))
    else:
        paths = list(Path("./").glob(args.globstr))
    paths.sort()
    if args.no_go:
        for p in paths:
            print(str(p))
        print(f"Would change {args.original_yearbase} to {args.new_yearbase}")
        sys.exit()
    for p in paths:
        change_yearbase(p, args.original_yearbase, args.new_yearbase)
        print(f"converted: {str(p)}")


if __name__ == "__main__":
    main()
