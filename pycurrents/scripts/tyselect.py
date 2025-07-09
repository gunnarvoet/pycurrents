#!/usr/bin/env python

"""
    Time range selector widget for picking time ranges corresponding
    to latitude or longitude sections, etc.

    This module includes a class that can be used with or without
    subclassing in a gui-independent fashion, or that can be
    subclassed to be embedded in a specific gui application.

    Data and selections are managed with an instance of the
    RangeSet class that is independent of the TxySelector widget.

    This can be run as a script on the command line for demonstration
    and testing.

"""

from pycurrents.plot.tyselect import test

if __name__ == '__main__':
    rs = test()
    print('final selections as time ranges:', rs.ranges)
    print('final selections as slices:', rs.slices)
