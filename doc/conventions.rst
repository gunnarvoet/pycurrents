Conventions
============

::
  
  import numpy as np
  from numpy import ma
  
  
**shortcuts**

::

  import matplotlib.pyplot as plt
  import matplotlib.mpl    as mpl
  import matplotlib.mlab   as mlab 
  
  import scipy as sp # if you have it; we do not depend on it.


**the big shortcut**

::
  
  from pycurrents.imports import *


**instead of "print"** for debugging statements


::

  import logging
  L = logging.getLogger(__file__)            # or new file name

  

**deprecated**

::


  from matplotlib import pylab 
  from matplotlib import *
  

