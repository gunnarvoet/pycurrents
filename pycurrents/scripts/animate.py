#!/usr/bin/env python

import argparse
from pycurrents.plot.animation import ffmpeg

parser = argparse.ArgumentParser(
                description="Run ffmpeg on a set of plot pngfiles.")
parser.add_argument("fileglob",
                    help="input file glob pattern, e.g., 'fig*.png'")
parser.add_argument("outfile",
                    help="output file name, e.g., 'movie.mp4'")
parser.add_argument("--fps", type=int, default=4,
                    help="Frames per second (default is 4)")
parser.add_argument("--bitrate", type=int, default=1800,
                    help="bitrate (k, integer; default is 1800)")

args = parser.parse_args()

ffmpeg(args.fileglob, args.outfile, fps=args.fps, bitrate=args.bitrate)
