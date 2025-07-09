'''
   asc2bin.py: parse nmea messages logged by UHDAS.
   Does NOT parse ascii files from other logging systems: Use serasc2bin.py

   Usage: asc2bin.py [<options>] [-y 2001] ...
                   [-o outputdirectory] file1 [file2 ...]

      Reads ascii files written by  UHDAS and writes corresponding
      files in binary double precision.  Output file name is the
      input file name base with the message name and '.rbin' appended.
      By default,
      if a file of that name already exists, the corresponding
      input file will not be processed.  Use '--redo' option
      to reprocess in this case.  Use '--update' to append to
      an rbin file if it already exists.  This can be used to
      continually update an rbin file as the source file is
      being written.

      Gzipped input files are handled transparently, without
      being explicitly gunzipped; the '.gz' extension is ignored
      when generating the output filename

      -h or --help:     print this message and exit
      -r or --redo:     process all input files, regardless of
                           whether an output file already exists
      -u or --update:   process incrementally
      -s or --seconds:  with -u, timeout in seconds (floating point)
      -o or --outdir:   directory for output files
      -m or --message:  desired output file type (without the dot)
      -y or --yearbase: 4-digit yearbase
      -l or --log_yearbase" 4-digit yearbase (yearbase used for $UNIXD
                            during logging). defaults to same as
                            yearbase if unspecified
      -v or --verbose:  print short diagnostics
      -V or --Verbose:  echo line number and line, so we can see
                           where it chokes
      -S or --showbad:  echo line number and line when they are
                           rejected, so we can see what junk is in the
                           file

      NOTE: the first entry, 'u_dday', is the time of the PC doing the logging.


      File or message types:


      binfile | (serial  |  NMEA    | fields in binary output file
       suffix |  source) |  string  |
     ---------+----------+----------+----------------------------------

         gps  (various)   $xxGGA    logger decimal day,
                                    GGA decimal day, lon degrees,
                                    lat degrees, quality indicator, HDOP
                                    ??GGA message (e.g., INGGA or GPGGA)
                                    # Quality indicator:
                                    0 = Fix not available or invalid <== bad
                                    1 = CIA standard GPS; fix valid.
                                    2 = DGS mode; fix valid.        <== typical
                                    3 = PPP mode; fix valid.
                                    4 = RTK fixed
                                    5 = RTK float
                                    6 = free inertial  <== eg. posmv, seapath (bad)



         gga  same as gps           deprecated

         ggn  (gps, no checksum)    $xxGGA without a checksum.

         gns              $xxGNS    logger decimal day, GGA decimal day,
                                    lon degrees, lat degrees
                                    number of svs, HDPO, Orthometric height (m),
                                    geoidal separation (m)
                                    (not returning mode, reference station ID, or age)
                                    This seems to be a Trimble message.

         rmc  same as gps $xxRMC    logger decimal day,
                                    fix decimal day, lon degrees,
                                    lat degrees, 1 if valid

         hdg  (gyro)      $xxHDx    logger decimal day, heading in degrees.
                          $xxHRC    examples:HEHDT, HEHDG, INHDT
                                    There is no error checking.

         gph  (gps-derived heading) logger decimal day, heading in degrees.
                          $xxHRC    examples: GPHDT. NOTE: This should be used for
                                    devices that DO NOT have an inertial component,
                                    such as Japan Radio Corp or 2-antenna Trimbles.

         ths  (Furuno)    $xxTHS    logger decimal day, heading in degrees,
                                    status (0=autonnmous, 1=estimated (dead
                                    reckoning), 2=manual, 3=simulator mode,
                                    4=invalid (includes 'standby')

         hnc  (same as gyro heading, but NO CHECKSUM) .hnc.bin

         adu  (Ashtech) $PASHR,ATT  logger decimal day,
                                    ATT decimal day (GPS days in week),
                                    heading, pitch, roll, mrms, brms,
                                    reacq flag.

         at2  (Ashtech) $PASHR,AT2  logger decimal day,
                                    ATT decimal day (GPS days in week),
                                    heading, pitch, roll, mrms, brms,
                                    reacq flag, last state, double
                                    differences (v12, v13, v14),  pdop.

         pat  (Ashtech) $PASHR,PAT  logger decimal day, hrminsec in the day,
                                    latitude degrees, longitude degrees,
                                    altitude(m), heading, pitch, roll,
                                    mrms, brms
                                    There is no error checking.

         paq  (Ashtech) $GPPAT      logger decimal day, hrminsec in the day,
                                    latitude degrees, longitude degrees,
                                    altitude(m), heading, pitch, roll,
                                    mrms, brms

         pmv  (POS/MV) $PASHR       logger decimal day,
                                    GGA decimal day, heading, roll,
                                    pitch, heave, accuracy of roll,
                                    of pitch, of heading, heading flag,
                                    IMU flag.
                                    GAMS flag: (0=no aiding, 1=GPS
                                       aiding, 2 = GAMS aiding)
                                    IMU flag: (0 = no IMU; 1 = using IMU )

         pvec  (Vector VS330) $PASHR       logger decimal day,
                                    GGA decimal day, heading, roll,
                                    pitch, heave, accuracy of roll,
                                    of pitch, of heading, heading flag,
                                    # no GAMS here
                                    IMU flag: (0 = no IMU; 1 = using IMU )

         rdi (various) $PRDID       logger decimal day,
                                    pitch, roll, heading.
                                    There is no error checking.

         rnh (various) $PRDID       logger decimal day,
                                    pitch, roll (but without heading)
                                    There is no error checking.

         psxn20 (Seapath) $PSXN,20  logger decimal day,
                                    quality for:  horizontal, height,
                                    heading, roll&pitch.

         psxn23 (Seapath) $PSXN,23  logger decimal day,
                                    roll, pitch, heading, heave

         psathpr (CSI) $PSAT,HPR    logger decimal day, GPS decimal day,
                                    heading, pitch, roll,
                                    flag (1 for GPS, 0 for gyro)


         tss1 (MAHRS) :             TSS MAHRS tss1 message:
                                    logger decimal day, status
                                    (settling: 0, unaided; 1, gps-aided;
                                    2, heading aided; 3, fully aided.
                                    settled: 4, unaided; 5, gps-aided;
                                    6, heading aided; 7, fully aided.)
                                    H accel, V accel, heave, roll, pitch

         ixrp  (Phins) $PIXSE,ATITUD   logger decimal day, roll, pitch

         ixgps (Phins) $PIXSE,POSITI   logger decimal day, lon, lat, altitude

         ixsspd (Phins) $PIXSE,SPEED_  logger decimal day, east, north, up

         ixalg  (Phins) $PIXSE,ALGSTS  logger decimal day, 64-bit-list

         hpr  (ABX-TWO) $PASHR,HPR  u_dday: logger decimal day.
                                    dday: UTC time of attitude (hhmmss.ss)
                                    heading: True heading angle in deg.
                                    pitch: Pitch angle in deg.
                                    roll: Roll angle in deg.
                                    mrms: Carrier measurement RMS error in m.
                                    brms: Baseline RMS error in m. (= 0 if not
                                          constrained)
                                    ia: Integer ambiguity (0: Fixed,> 0: Float)
                                        (This appears to be identical in
                                        practice to $PASHR,ATT reacq flag)
                                    bm: Baseline mode status (0: operation with
                                        fixed baseline length, 1: calibration
                                        in progress, 2: flexible baseline mode
                                        on)
                                    y: "antenna setup" where
                                       y=0: no length constraint,
                                       y=1: heading mode,
                                       y=2 or 3: attitude mode;
                                    xi: "number of double differences per
                                        vector", one per vector hence i=1, 2 or
                                        3, value from 0 to 9
                                        It is then returned by the parser as
                                        4 distinct values, x1, x2 and x3.
                                    pdop: PDOP corresponding to vector V12
                                    *cc: Checksum


                     #=== combined messages ===

         sea                       logger decimal day,
                                   roll, pitch, heading, heave,
                                   quality for:  height,
                                   heading, roll&pitch.  (The psxn23
                                   fields preceed the psxn20 fields.)

         gps_sea                   same as 'gps', but with horizontal quality
                                   column from psxn20 appended


         hnc_tss1 MAHRS            hnc message with all but the time from
                                   tss1 appended.

         hdg_tss1 MAHRS            hdg message with all but the time from
                                   tss1 appended.


                      #=== other messages ===


         spd  (floating point)     .spd.bin fields are logger decimal day,
                                   soundspeed in m/s.

         raw_spd  (integer)        .raw_spd.bin fields are logger decimal day,
                                   uncalibrated soundspeed.

         vbw     UHDAS $xxVBW      ship speed (kts) over water/ground
                                   fwd_w, stbd_w, flag_w (we only return water)
                                   (fwd: negative means ship moving astern)
                                   (stbd: negative means ship moving to port)
                                   (flag: 0=no problem, 1=invalid)

         vtg      $xxVTG           course over ground (degrees), T (deg T),
                                   course over ground (degrees), M (magnetic),
                                   speed (knots), N (knots),
                                   speed (km/hr), K (kilometers per hour),
                                   FAA mode (NMEA 2.3 and later), Checksum

         gpgst (BX392)  $GPGST     logger decimal day, UTC time status of
                                   position (hhmmss.ss), RMS value of the
                                   standard deviation of the range inputs to
                                   the navigation process, Standard deviation
                                   of semi-major axis of error ellipse (m),
                                   Standard deviation of semi-minor axis of
                                   error ellipse (m),  Orientation of
                                   semi-major axis of error ellipse
                                   (degrees from true north), Standard
                                   deviation of latitude error (m), Standard
                                   deviation of longitude error (m), Standard
                                   deviation of altitude error (m)
                    see https://docs.novatel.com/OEM7/Content/Logs/GPGST.htm

        ptnlvhd (Trimble) $PTNL,VHD decimal day from UTC of position fix,
                                    UTC of position in hhmmss.ss format,
                                    Date in mmddyy format,
                                    Azimuth, Azimuth/Time, Vertical Angle,
                                    Vertical/Time, Range, Range/Time,
                                    GPS Quality indicator:
                                        0: Fix not available or invalid
                                        1: Autonomous GPS fix
                                        2: RTK float solution
                                        3: RTK fix solution
                                        4: Differential, code phase only
                                           solution (DGPS)
                                        5: SBAS solution – WAAS/EGNOS/MSAS
                                        6: RTK Float 3D network solution
                                        7: RTK Fixed 3D network solution
                                        8: RTK Float 2D network solution
                                        9: RTK Fixed 2D network solution
                                        10: OmniSTAR HP/XP solution
                                        11: OmniSTAR VBS solution
                                        12: Location RTK
                                        13: Beacon DGPS
                                    Number of satellites used in solution,
                                    PDOP = Position Dillution Of Precision
                    see https://www.trimble.com/OEM_ReceiverHelp/V4.44/en/...
                        ...NMEA-0183messages_PTNL_VHD.html

        jratt (JLR-21 v.2.1) $PFEC,GPatt   yaw (0.0 - 359.9 deg.),
                                           pitch (-90.0 - 90.0  deg.)
                                           roll (-90.0 - 90.0  deg.)
                    Version with check sum
                    see http://www.echomastermarine.co.uk/assets/manuals/JRC...
                        .../JLR-21%20JLR-31%20Instruction%20Manual.pdf

        jrattn (JLR-21 v.1.5) $PFEC,GPatt   yaw (0.0 - 359.9 deg.),
                                            pitch (-90.0 - 90.0  deg.)
                                            nroll (-90.0 - 90.0  deg.)
                    Version without check sum
                    see http://www.echomastermarine.co.uk/assets/manuals/JRC...
                        .../JLR-21%20JLR-31%20Instruction%20Manual.pdf

        jrhve (JLR-21 v.2.1) $PFEC,GPatt    heaving (-99.999m - 99.999m)
                                            QC value: 0 = valid, 1 = invalid
                    Version with check sum
                    see http://www.echomastermarine.co.uk/assets/manuals/JRC...
                        .../JLR-21%20JLR-31%20Instruction%20Manual.pdf

        jrhven (JLR-21 v.1.5) $PFEC,GPatt   heaving (-99.999m - 99.999m)
                                            QC value: 0 = valid, 1 = invalid
                    Version without check sum
                    see http://www.echomastermarine.co.uk/assets/manuals/JRC...
                        .../JLR-21%20JLR-31%20Instruction%20Manual.pdf

   Note: there is a slight difference in the logger decimal day for the
   Seapath gga file versus the gps_sea.  In the latter, the time stamp
   is the one from the psxn20 message, which arrives immediately after
   the gga.  Fixing this would be more trouble than it is worth.

'''

# 2006/05/18 EF: added CSI psathpr message
# 2005/03/28 EF: Reworked for UHDAS; new elapsed time fields;
#    logging module.

# 2004/09/30 EF: added sys.byteorder to binfile header,
#    to match binfile.py, write_bin.m, and read_bin.m,
#    all of which were modified to handle non-native order

# 2004/09/24 EF: switched from dday_frac to dday;
#   eliminate duplicate times; added dday to sea record

# 2004/09/18 EF: cleanup, documentation tweaks;
#   transparent handling of gzipped input files;
#   changed order of columns in vmdas output;
#   combined handling of psxn20 and psxn23.
#   Added hdop field to gga.
#   Added log_yearbase option from JH version;
#   fixed yearbase bug in get_vmdas_dday.
#   Added gps_sea combined message.


# 2003/11/01 JH: added vmdas

# 2003/06/25 EF: merged changes from rvdas; the implementation
# of the different file reading functions might be improved
# to reduce duplication of code, but we have a working framework
# for reading any files of this sort, e.g. SCS files as well
# as rvdas.

# 2003/06/23 EF: rvdas version working.
#  profiling shows that the checksum routine is the biggest
#  single time sink.
#  Added the Pyrex version of the checksum routines; ~20% speedup.
#
#  Changed variable name "str" to "str_" to avoid conflict
#  with built-in.


# 2002/08/18 EF: Added pmv support; generalized gga; --message option.
# bug in translate_file_incr fixed 2001/04/16


import sys
import os
import array
import time
import datetime
import logging

from pycurrents.file.binfile import binfile_a
from pycurrents.file.linefile_tail import linefile2s
import pycurrents.data.nmea.msg as msg
from pycurrents.data.nmea.msg import function_dict
from pycurrents.data.nmea.msg import field_dict1

# Standard logging
_log = logging.getLogger('asc2bin')


def usage():
    print(__doc__)
    sys.exit()
# Append the monotonic elapsed time field (2005/03/29)
for key, value in field_dict1.items():
    value.append('m_dday')  #used to exclude 'rdi' message -- why?

class asc2bin(msg.Asc2binBase):
    def __init__(self, yearbase = None,
                   log_yearbase = None,
                   outfiledir = './',
                   message = None,
                   redo = 0,
                   update = 0,
                   showbad = 0,
                   verbose = 0,
                   sleepseconds = 10,
                   keep_running = None,
                   logname = 'asc2bin'
                   ):
        logging.basicConfig()  # Only acts if a handler is not already present.
        _log.setLevel(logging.INFO)
        self.yearbase = yearbase
        self.log_yearbase = log_yearbase
        self.verbose = verbose
        self.showbad = showbad
        self.outfiledir = outfiledir
        self.redo = redo
        self.update = update
        if update:
            self.sleepseconds = sleepseconds
        else:
            self.sleepseconds = 0
        self.keep_running = keep_running
        self.message = message
        self.function_dict = function_dict.copy()
        self.function_dict['sea'] = self.get_sea
        self.function_dict['gps_sea'] = self.get_gps_sea
        self.function_dict['hnc_tss1'] = self.get_hnc_tss1
        self.function_dict['hdg_tss1'] = self.get_hdg_tss1

        self.get_field = self.function_dict[self.message]
        self.fields = field_dict1[self.message]
        self.recordlength = len(self.fields)
        if self.log_yearbase is None: #it was unset
            self.log_yearbase = self.yearbase
        if self.message in ['gps', 'gga', 'ggn', 'gns', 'rmc',
                            'pat', 'paq', 'pmv', 'pvec', 'sea',
                            'gps_sea', 'psathpr', 'gpgst', 'ptnlvhd', 'hpr']:
            self.check_dday = self.check_gga_dday
        elif self.message in ['adu', 'at2']:
            self.check_dday = self.check_adu_dday
        else:
            self.check_dday = lambda x: x
        if self.redo:
            self.mode = 'w'
        else:
            self.mode = 'a'
        # Information saved from message to message and across file boundaries:
        self.last_dday = -100000
        self.last_psxn20 = None
        self.last_gga = None
        self.last_hdg = None
        # Counters
        self.Nbad = 0
        self.Ngood = 0

        self.log = logging.getLogger(logname)  #gets root logger if empty

        if not os.access(self.outfiledir, os.F_OK):
            os.makedirs(self.outfiledir, 0o775)
        # epoch_t is used for old UNIXT timestamp
        self.epoch_t = time.mktime((self.yearbase, 1, 1, 0, 0, 0, 0, 0, 0))
        _dlog = datetime.date(self.log_yearbase, 1, 1).toordinal()
        _dproc = datetime.date(self.yearbase, 1, 1).toordinal()
        self.yearbase_dif_days = _dlog - _dproc
        self.yearbase_ordinal = _dproc  # saved for use in handling $PYRTM
        self.translate_file = self.translate_file_2
        self.translate_file_incr = self.translate_file_2
        self.get_dday = self.get_UNIX_dday

    # both of these use msg.get_tss1; must be here to access 'self'
    def get_hnc_tss1(self, str_):
        f = msg.get_degrees_nochecksum(str_)
        if f:
            self.last_hdg = f
            return None
        f = msg.get_tss1(str_)
        if f and self.last_hdg:
            return self.last_hdg + f

    def get_hdg_tss1(self, str_):
        f = msg.get_degrees(str_)
        if f:
            self.last_hdg = f
            return None
        f = msg.get_tss1(str_)
        if f and self.last_hdg:
            return self.last_hdg + f


    def make_record(self, timestring, datastring):
        rec = None
        try:
            timestring = timestring.strip()
            datastring = datastring.strip().split(b'_')[0]

            rec2 = self.get_field(datastring)
            if rec2:
                rec1 = self.get_dday(timestring)
                if rec1:
                    rec = self.check_dday(array.array('d', rec1[:1] + rec2 + rec1[1:]))
                    assert len(rec) == self.recordlength
                    self.Ngood += 1
        except:
            self.Nbad += 1
            if self.showbad and self.Nbad < 10:
                _log.exception('in make_record')
                _log.warning( 'Rejected %s %s\n   %s %s\n %s\n' % (self.filename,
                                                          self.message,
                                                          timestring,
                                                          datastring, str(rec)))
            rec = None

        return rec


    def translate_file_2(self, filename, outfilename):
        '''The time tag is on the line preceeding the message. (eg. UHDAS logging)
        '''
        self.filename = filename
        self.Ngood = 0
        self.Nbad = 0
        # append to UH
        f_in = linefile2s(filename, sync = ['$UNIXD', '$PYRTM'],
                          timeout = self.sleepseconds,
                          keep_running = self.keep_running)
        f_out = binfile_a(outfilename, mode=self.mode, name = self.message,
                         columns = self.fields)

        n_written = f_out.count()
        self.log.debug('filename: %s, outfilename: %s, n_written: %d' %
                        (filename, outfilename, n_written))
        if n_written > 0:    # appending to an existing binfile
            f_out.seek(-1, 2)
            last_written = f_out.read(1)
            self.log.debug('last_written: %s' % str(last_written))
            # Read n_written records to position the input file:
            # (this is the earliest possible location; it might need
            #  to be advanced much farther, if there is more than one
            #  message type in the file)
            t, d = f_in.read_records(n_written)[-2:]  # change if read_records changes
            rec = self.make_record(t, d)
            self.log.debug('rec: %s' % str(rec))
            # Because of the Python bug, a record might have been
            # missed, so we compare the monotonic time fields.
            while rec is None or rec[-1] < last_written[-1]:
                lines = f_in.read_record()
                if lines:
                    rec = self.make_record(*lines)
                    self.log.debug('searching, rec: %s' % str(rec))
                else:
                    self.log.debug('no more lines, and rec != last_written')
                    break

        if n_written == 0:    #New file: read as much as possible in one chunk.
            lines = f_in.read_records()
            n = len(lines)//2
            self.log.debug('New file, n = %d' % n)
            if n > 0:
                recs = array.array('d')
                j = 0
                for ii in range(0, 2*n, 2):
                    rec = self.make_record(lines[ii], lines[ii+1])
                    if rec:
                        recs += rec
                        j += 1
                if j > 0:
                    f_out.write(recs)
                    n_written += j

        # Incremental read
        self.log.debug('Starting incremental, n_written = %d' % n_written)
        for (timeline, dataline) in f_in:
            self.log.debug('%s %s' % (timeline, dataline))
            rec = self.make_record(timeline, dataline)
            if rec:
                self.log.debug('rec is %s' % str(rec))
                f_out.write(rec)
                n_written += 1

        f_in.close()
        f_out.close()
        self.log.debug('End translate_file_2, n_written = %d' % n_written)
        return n_written



    def translate_files(self, filenames):
        #self.__dict__.update(kw)
        n = 0
        try:
            for filename in filenames:
                if (not self.update) or self.verbose:
                    _log.info(filename)
                fpath, fname = os.path.split(filename)
                fname_base, log_ext = os.path.splitext(fname)
                if log_ext == '.gz':
                    fname_base, log_ext = os.path.splitext(fname_base)
                out_ext = self.message or log_ext[1:]

                outfilename = os.path.join(self.outfiledir,
                                     fname_base + '.' + out_ext + '.rbin')
                outfile_exists = os.access(outfilename, os.F_OK)
                if outfile_exists and os.stat(outfilename).st_size == 0:
                    outfile_exists = False # Bad file; force regeneration.
                needs_processing = self.redo or not outfile_exists
                if self.update and outfile_exists:
                    if os.path.getmtime(filename) > os.path.getmtime(outfilename):
                        needs_processing = True
                if needs_processing:
                    if self.verbose: _log.info( ' ---> %s' % outfilename)
                    n = self.translate_file(filename, outfilename)
                else:
                    if self.verbose:
                        _log.info('no action')
                if (not self.update) or self.verbose:
                    _log.info('Ngood = %d   Nbad = %d' % (self.Ngood, self.Nbad))
        except KeyboardInterrupt:
            raise
        except:
            _log.exception("filename is %s", filename)
        return n  # number of records written to the last file

os.environ['TZ'] = 'UTC'


def main():
    import getopt

    try:
        options, args = getopt.getopt(sys.argv[1:], 'SvVhro:y:l:us:m:',
                             ['showbad', 'verbose', 'Verbose', 'help',
                              'redo', 'outdir=', 'yearbase=', 'log_yearbase=',
                              'update', 'seconds=',
                              'message',
                              ])
    except getopt.GetoptError:  # Before Python 2.x this was getopt.error
        usage()

    if len(args) == 0:
        usage()

    opts = {}

    for o, a in options:
        if o in ('-h', '--help'):
            usage()
        elif o in ('-r', '--redo'):
            opts['redo'] = 1
        elif o in ('-o', '--outdir'):
            opts['outfiledir'] = a
        elif o in ('-y', '--yearbase'):
            opts['yearbase'] = int(a)
        elif o in ('-l', '--log_yearbase'):
            opts['log_yearbase'] = int(a)
        elif o in ('-v', '--verbose'):
            opts['verbose'] = 1
        elif o in ('-V', '--Verbose'):
            opts['verbose'] = 2
        elif o in ('-S', '--showbad'):
            opts['showbad'] = 1
        elif o in ('-u', '--update'):
            opts['update'] = 1
        elif o in ('-s', '--seconds'):
            opts['sleepseconds'] = float(a)
        elif o in ('-m', '--message'):
            opts['message'] = a

    t0 = time.process_time()

    import glob
    filenames = []
    for arg in args:
        filenames += glob.glob(arg)

    asc2bin(**opts).translate_files(filenames)

    t1 = time.process_time()
    print('Elapsed cpu time:   %.1f s' % (t1 - t0))

if __name__ == "__main__":
    main()
