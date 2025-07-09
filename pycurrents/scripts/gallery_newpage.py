#!/usr/bin/env python

import sys

from pycurrents.adcp.gallery import Gallery

G = Gallery()

if "-h" in sys.argv:
    print(G.__doc__)
else:
    G.make_all()
