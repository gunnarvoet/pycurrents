'''
Routines for manipulating numbers and arrays; statistics, gridding, filters.

Useful classes and functions from submodules are usually
imported into this namespace, and should be imported
from here rather than from their submodules.

Imported classes include:

- :class:`~pycurrents.num.stats.Stats`
- :class:`~pycurrents.num.runstats.Runstats`

Imported functions include:

- :func:`~pycurrents.num.binstats.binstats`
- :func:`~pycurrents.num.bl_filt.bl_filt`
- :func:`~pycurrents.num.bl_filt.Blackman_filter`
- :func:`~pycurrents.num.nptools.loadtxt`
- :func:`~pycurrents.num.nptools.rangeslice`
- :func:`~pycurrents.num.nptools.lon_rangeslices`
- :func:`~pycurrents.num.nptools.lonslice_array`
- :func:`~pycurrents.num.nptools.lonslice_arrays`
- :func:`~pycurrents.num.grid.interp1`
- :func:`~pycurrents.num.grid.regrid`
- :func:`~pycurrents.num.utility.neighbor_count`
- :func:`~pycurrents.num.utility.neighbor_span`
- :func:`~pycurrents.num.utility.expand_mask`
- :func:`~pycurrents.num.utility.mask_nonincreasing`
- :func:`~pycurrents.num.utility.segments`
- :func:`~pycurrents.num.utility.segment_lengths`
- :func:`~pycurrents.num.utility.points_inside_poly`
- :func:`~pycurrents.num._median.median`
'''

from pycurrents.num.stats import Stats
from pycurrents.num.runstats import Runstats
from pycurrents.num.binstats import binstats
from pycurrents.num.bl_filt import bl_filt, Blackman_filter
from pycurrents.num.nptools import loadtxt_ as loadtxt
from pycurrents.num.nptools import rangeslice
from pycurrents.num.nptools import (lon_rangeslices, lonslice_array,
                                    lonslice_arrays)
from pycurrents.num.grid import interp1
from pycurrents.num.grid import regrid  # needs work to generalize blank,
                                        # allow different array orientation
                     # maybe later import blank, mask_from_poly, zgrid,
                     # and/or alternative wrapper for zgrid.

# add cleaner when api decision (function or class) is made

from pycurrents.num.utility import neighbor_count
from pycurrents.num.utility import neighbor_span
from pycurrents.num.utility import expand_mask
from pycurrents.num.utility import mask_nonincreasing
from pycurrents.num.utility import segments
from pycurrents.num.utility import segment_lengths
from pycurrents.num.utility import points_inside_poly
from pycurrents.num._median import median

# Silence pyflakes:
(Stats, Runstats, binstats, bl_filt, Blackman_filter, loadtxt, rangeslice,
    lon_rangeslices, lonslice_array, lonslice_arrays,
    interp1, regrid, neighbor_count, neighbor_span, expand_mask,
    mask_nonincreasing, segments, points_inside_poly, median)
