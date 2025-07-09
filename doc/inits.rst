Module Descriptions
===================

All packages should be imported starting with "pycurrents"


**adcp**  (``pycyrrents.adcp``)

     * quick_adcp.py and shipboard processing-specific tools


**adcpgui** (``pycurrents.adcpgui``)

     * ADCP CODAS data viewer

**codas** (``pycurrents.codas``)

      * Module for accessing codas databases in python
      * It is numpy-specific.

**data** (``pycurrents.data``)

      * parse data from specific sources


          - adcp
          - nmea
          - other (seabird, soundspeed, topography)
          - navigation tools

**data.adcp** (``pycurrents.data.adcp``)

      * narrowband datafile reader, sound speed

**data.nmea** (``pycurrents.nmea.adcp``)

      * tools to parse nmea messages, binfile generation from nmea files


**file** (``pycurrents.file``)

      * Specialized file handling

         - binfiles
         - file globbing for live directories

**num**  (``pycurrents.num``)

      * Manipulate numbers and arrays; statistics, gridding, filters


**plot** (``pycurrents.num``)

      * Plotting (contour, vector, topography)
      * postscript conversion
      * plotting convenience


**py_utils/uhdastools**  (``pycurrents.py_utils.uhdastools``)

      * transitional; deprecated - mostly related to rbin file handling


**system**  (``pycurrents.system``)

      *  timers, threading, tee, tail
      *  zip, hgsummary


**text**  (``pycurrents.text``)

      *  code for handling text files, rst documents, web generation





