#!/usr/bin/env python
'''
quick syntax-checker for python files
(these are typically files with 'data', used with UHDAS)
'''


import sys
import os
from pycurrents.system.misc import Bunch

if "--help" in sys.argv or "-h" in sys.argv or len(sys.argv)==1:
    print('usage: check_syntax.py file1.py [file2.py...]')
    sys.exit()


for fname in sys.argv[1:]:
    if not os.path.exists(fname):
        print('ERROR: filename %s does not exist' % (fname))
    else:
        print("--------------- %s ----------------" % (fname))
        x = Bunch().from_pyfile(fname)
        print(x)
        print("\n")
