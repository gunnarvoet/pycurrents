"""
Animation-related routines.

ffmpeg: wrapper for ffmpeg, to make a movie from a sequence of
png files.

"""

import glob
import tempfile
import os
import subprocess
import shutil


def ffmpeg(fileglob, outfile, fps=5, bitrate=1800, exe="ffmpeg"):
    """
    Use ffmpeg or avconv to generate a movie file.

    *fileglob* is a glob expression that generates an
    ascii-sortable list of png files.

    *outfile* is an output file name, e.g. 'movie.mp4' or 'movie.webm'

    This is linux-specific and requires ffmpeg or avconv with suitable
    codecs.  It may be modified to handle more options.
    """
    files = glob.glob(fileglob)
    files.sort()
    tdir = tempfile.mkdtemp()
    temp_pat = os.path.join(tdir, "_movie_temp_%05d.png")
    for i, fn in enumerate(files):
        fnpath = os.path.abspath(fn)
        os.symlink(fnpath, temp_pat % (i+1))
    cmd = [exe, "-y", "-r", str(fps),
           "-i", temp_pat, '-pix_fmt', 'yuv420p', "-b", f"{bitrate}k", outfile]
    print("\n".join(["", "Running:", " ".join(cmd), "", ""]))
    retcode = subprocess.call(cmd)
    if retcode == 0:
        print("\nSuccess.\nRemoving temporary directory.")
        shutil.rmtree(tdir)
    else:
        print("temporary directory is ", tdir)
        print("remove it manually after debugging")



