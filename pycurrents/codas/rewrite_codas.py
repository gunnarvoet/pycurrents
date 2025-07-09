"""
Functions for reading an early ADCP CODAS database and regenerating it.

This is motivated by early HOT cruises.  Some of the databases lack
PROFILE_FLAGS and/or some structure definitions.

Transferring information from ACCESS_VARIABLES and applying a percent good
cutoff to PROFILE_FLAGS is performed on the newly written database.

The structure definition file might need to be edited to include an additional
structure definition, and to include a line for the PROFILE_FLAGS.  Make sure
that line is:

PROFILE_VAR   34  UBYTE     PROFILE_FLAGS        0       1       none

Example script using these functions:
#####################################

from pathlib import Path
from pycurrents.codas.rewrite_codas import dump_codas, run_ldcodas, update_profile_flags

cruise_dirname = "hot16"
dbname = "ah16"

source_tree = Path("original") / cruise_dirname
dest_tree = Path("fixed") / cruise_dirname
dest_load = dest_tree / "load"
dest_load.mkdir(parents=True, exist_ok=True)
dest_dbpath = dest_tree / "adcpdb" / dbname

sdfilepath = source_tree / "adcpdb" / "nav.def"    # <-- structure def file
pdfilepath = dest_tree / "adcpdb" / "codas3wc.def" # <-- producer def file

source_dbpath = source_tree / "adcpdb" / dbname
dest_dbdir = dest_tree / "adcpdb"

dump_codas(source_dbpath, dest_load, sdfile=sdfilepath)
run_ldcodas(dest_load, dest_dbdir, dbname, pdfilepath)

update_profile_flags(dest_dbpath)

##########################################

"""

import os
from pathlib import Path
import subprocess

import numpy as np
from pycurrents.codas import DB


def dump_codas(dbname, destdir, sdfile=None):
    """
    Given a codas db, write a 'db.cmd' and 'db.bin' file pair for ldcodas.

    dbname is a Path or string ending with the db name (e.g., 'aship')
    destdir is the path in which the cmd and bin files will be written
    sdfile is the path to a Structure Definition File with any structure
    definitions that are missing from the original database.
    """
    destdir = Path(destdir)
    if sdfile is not None:
        sdfile = str(sdfile)  # DB doesn't handle Path
    db = DB(str(dbname), sdfile=sdfile)
    block_vars = db.get_variable_names(access="block")
    profile_vars = db.get_variable_names(access="profile")
    if "PERCENT_GOOD" not in profile_vars:
        raise RuntimeError("Assumed presence of PERCENT_GOOD is violated.")

    cmdfile = open(destdir / "db.cmd", "w")
    binfile = open(destdir / "db.bin", "wb")
    cmdfile.write("little_endian\nbinary_file: db.bin\n")
    last_block = -1
    count = 0
    while True:
        blk = db.block_profile[0]
        if last_block != blk:
            last_block = blk
            cmdfile.write("new_block\n")
            dpmask = db.get_numpy_bytes("DATA_PROC_MASK").view(np.uint32)[0]
            cmdfile.write(f"dp_mask: {dpmask:d}\n")
            for varname in block_vars:
                var = db.get_numpy_bytes(varname)
                nbytes = len(var)
                cmdfile.write(f"binary_data: {varname} UBYTE {nbytes:d} {count:d}\n")
                count += nbytes
                binfile.write(var.tobytes())

        t = db.get_ymdhms()
        time_string = f"{t[0]:d}/{t[1]:02d}/{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
        cmdfile.write(f"new_profile: {time_string}\n")
        dr = db.get_depth_range()
        cmdfile.write(f"depth_range: {dr[0]:d} {dr[1]:d}\n")
        pos = db.get_dmsh_position()
        cmdfile.write("position: ")
        for part in pos:
            cmdfile.write(f" {part:d}")
        cmdfile.write("\n")
        for varname in profile_vars:
            var = db.get_numpy_bytes(varname)
            nbytes = len(var)
            cmdfile.write(f"binary_data: {varname} UBYTE {nbytes:d} {count:d}\n")
            count += nbytes
            binfile.write(var.tobytes())
            if varname == "PERCENT_GOOD":
                ndepths = nbytes
        if "PROFILE_FLAGS" not in profile_vars:
            var = np.zeros((ndepths,), dtype=np.uint8)
            cmdfile.write(f"binary_data: PROFILE_FLAGS UBYTE {ndepths:d} {count:d}\n")
            count += ndepths
            binfile.write(var.tobytes())

        if db.move(1) != 0:
            break

    cmdfile.close()
    binfile.close()


def run_ldcodas(load_dir, dbdir, dbname, pdfile):
    """
    Using output from dump_codas, write a new database.

    load_dir is the location of db.cmd and db.bin
    dbdir is the location of the database to be written
    dbname is the database name, with no path
    pdfile is the path for the Producer Definition File

    Warning: any existing database files (*.blk) will be deleted.
    """
    dbpath = Path(dbdir) / dbname
    oldblocks = Path(dbdir).glob("*.blk")
    for blk in oldblocks:
        os.remove(blk)
    lines = [
        f"DATABASE_NAME:   {str(dbpath.resolve())}\n",
        f"DEFINITION_FILE: {str(pdfile.resolve())}\n",
        "cmd_file_list\n",
        "END\n",
        "db.cmd\n",
    ]


    wd = os.getcwd()
    os.chdir(load_dir)
    try:
        with open("ldcodas.cnt", "w") as f:
            f.writelines(lines)
        subprocess.run(["ldcodas", "ldcodas.cnt"])
    finally:
        os.chdir(wd)


def update_profile_flags(dbname, pgmin=50):
    """
    Update the profile_flags array based on ACCESS_VARIABLES and a pgmin.

    dbname is a string or pathlib.Path

    The update is done in place.
    """
    db = DB(str(dbname), read_only=False)
    if "PROFILE_FLAGS" not in db.get_variable_names():
        raise ValueError(f"Database {str(dbname)} has no PROFILE_FLAGS")
    nblocks = db.bp_end[0] + 1
    for iblock in range(nblocks):
        r = (iblock, iblock)  # One at a time; r is inclusive on both ends.
        flags = db.get_variable("PROFILE_FLAGS", r=r)
        pg = db.get_variable("PERCENT_GOOD", r=r)
        flags[pg < pgmin] |= 2
        access = db.get_variable("ACCESS_VARIABLES", r=r)
        fgb, lgb = access["first_good_bin"], access["last_good_bin"]
        # Bad profile:
        flags[lgb == -1, :] |= 4
        # Top and bottom bad ranges (one-based indexing):
        ind = np.arange(1, flags.shape[1] + 1)[np.newaxis, :]
        flags[ind < fgb[:, np.newaxis]] |= 4
        flags[ind > lgb[:, np.newaxis]] |= 4
        db.put_array("PROFILE_FLAGS", flags, r=r)

    del db  # For arcane reasons, this is the way to close the db.
