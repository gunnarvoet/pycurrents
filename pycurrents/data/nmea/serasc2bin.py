'''

   Usage: serasc2bin.py [<options>] [-y 2001] ...
                   [-o outputdirectory] file1 [file2 ...]

      Reads ascii files written by:
          VmDAS (RDI OS acquisition) or
          RVDAS (Palmer and Gould)
          SCS   (NOAA)

      and writes corresponding files
      in binary double precision.  Output file name is the
      input file name with mesage name and '.rbin' appended
      (except for uhdas files, where logging message is replaced
      with extracted message)

      Does not support newer UHDAS files with monotonic time field;
          use "asc2bin.py" for UHDAS files.

      By default,
      if a file of that name already exists, the corresponding
      input file will not be processed.  Use '--redo' option
      to reprocess in this case.

      Gzipped input files are handled transparently, without
      being explicitly gunzipped; the '.gz' extension is ignored
      when generating the output filename.

      -h or --help:     print this message and exit
      -r or --redo:     process all input files, regardless of
                           whether an output file already exists
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
      -s or --skip_bad   : proceed with available good lines

      -t or --type:     'rvdas', 'uh', 'vmdas', 'scs', 'lds', 'vids', 'rsmas',
                           ('vmdas' is the default)
                          'uh' is {'u_dday',......'m_dday'}
                          'olduh' is {'u_dday',......}  #does not include m_dday

      -c or --count:   for vmdas only:
                       VmDAS may have more than one serial message per
                       timestamp (PADCP); the timestamp comes at the
                       end of a group.  Use "--count" to specify which
                       messages to store.  The field "count" starts with
                       zero just prior to the PADCP message and decreases
                       backwards in time.
                       count switch:     outputs
                         first         (output the serial message at
                                            the beginning of the collection
                                            for the ensemble;
                                            corresponds to raw data
                                            structure nav.txy1)
                         last           (output the serial message at the
                                            end (nav.txy2)).  DEFAULT
                         all            (output all serial messages)


      NOTE: the first entry, 'u_dday', is the time of the PC doing the logging.
      For UHDAS, this is the linux clock time
      For rvdas, it is a GGA timestamp
      For scs, it is the SCS clock
      For vids, it is the VIDS clock
      For VmDAS, it is the PC clock time.
      for whoi_sdlog, it is PC clock time
      For samos_xml, it is the logger clock (could be PC or single board)


      File or message types:

         gps  GGA messages.  .gps.bin fields are logger decimal day,
                                    GGA decimal day, lon degrees,
                                    lat degrees.
                                    ??GGA message (e.g., INGGA or GPGGA)
         gga  same as gps

         ggn  (gps, no checksum)

         rmc  same as gps    .rmc.bin fields are logger decimal day,
                                    fix decimal day, lon degrees,
                                    lat degrees, 1 if valid

         spd  soundspeed     .spd.bin fields are logger decimal day,
                                    soundspeed in m/s.

         ssv  temp,soundspeed   .ssv.bin fields are logger decimal day,
                                    temperature deg C, soundspeed m/s

         hdg  gyro heading   .hdg.bin fields are logger decimal day,
                                    heading in degrees.
                                    HEHRC or xxHDT messages are read.

         hnc  gyro heading   (same as hdg, but without a checksum)

         gph  heading from 2 GPS   (same as hdg, but without a checksum)

         adu  Ashtech $PASHR,ATT    .adu.bin fields are logger decimal day,
                                    ATT decimal day (GPS days in week),
                                    heading, pitch, roll, mrms, brms,
                                    reacq flag.

         pat  Ashtech $PASHR,PAT    .pat.bin fields are logger decimal day,
                                    PAT decimal day (hours in the day)
                                    latitude degrees, longitude degrees,
                                    altitude(m), heading, pitch, roll, mrms,
                                    brms
                                    (These messages have no reacquisition flag)

         paq  Ashtech $GPPAT       .paq.bin fields are logger decimal day,
                                    (same contents as .pat but *with* reacq flag


         pmv  (POS/MV) $PASHR  .pmv.bin fields are logger decimal day,
                                    GGA decimal day, heading, roll,
                                    pitch, heave, accuracy of roll,
                                    of pitch, of heading, heading flag,
                                    IMU flag.
                                    GAMS flag: (0=no aiding, 1=GPS
                                       aiding, 2 = GAMS aiding)
                                    IMU flag: (0 = no IMU; 1 = using IMU )

         rdi (various) $PRDID  .rdi.bin fields are logger decimal day,
                                    pitch, roll, heading.
                                    There is no error checking.

         rdinc (various) $PRDID  (same as 'rdi', but no checksum)

         psxn20 Seapath $PSXN,20   logger decimal day,
                                    quality for:  horizontal, height,
                                    heading, roll&pitch.

         psxn23 Seapath $PSXN,23   logger decimal day,
                                    roll, pitch, heading, heave

         sea                       logger decimal day,
                                    roll, pitch, heading, heave,
                                    quality for:  height,
                                    heading, roll&pitch.  (The psxn23
                                    fields preceed the psxn20 fields.)

         gps_sea                   same as gga, but with horizontal quality
                                   column from psxn20 appended

         uvh     UHDAS $PUHAW,UVH  ocean u,v,heading (speedlog output)
         vbw     UHDAS $xxVBW      ship speed (kts) over water/ground
                                   fwd_w, stbd_w, flag_w (we only return water)
                                   (fwd: negative means ship moving astern)
                                   (stbd: negative means ship moving to port)
                                   (flag: 0=no problem, 1=invalid)


   Note: there is a slight difference in the logger decimal day for the
   Seapath gga file versus the gps_sea.  In the latter, the time stamp
   is the one from the psxn20 message, which arrives immediately after
   the gga.  Fixing this would be more trouble than it is worth.


'''
# 2011/11/06 JH: taking out "add_extension" -- always append msg + '.rbin'
# 2010/04/25 JH: adding LDS, taking out 'incremental'
# 2008/07/09 JH: making serasc2bin.py still work with uhdas (with
#    or without m_dday) and not require compiled python extensions

# 2005/01/30 JH: change documentation to redirect UHDAS user to
#    asc2bin.py; changed default type to 'vmdas' (not 'uh')
#    (serasc2bin.py works for old UHDAS data, prior to m_dday)

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
import gzip
import copy
import logging


from pycurrents.data.nmea import msg as msg

def usage(msg=''):
    print(__doc__)
    print(msg)
    sys.exit()

def write_header(src, rows):
    h = []
    nrows = len(rows)
    nlines = nrows + 2   # could change if we put in more info
    nlines  # placate pyflakes
    h.append('%(nrows)d %(nlines)d %(src)s' % vars())
    for r in rows:
        h.append(r)
    h.append(sys.byteorder)
    return ('\n'.join(h) + '\n').encode('ascii')

# Following are three dictionaries, each of which has the
# output file types as keys.
from pycurrents.data.nmea.msg import function_dict
from pycurrents.data.nmea.msg import field_dict1


# For VMDAS include three extra pieces of information from the $PADCP string.
# 'count' is message index relative to the $PADCP, such that 0 means
# the message immediately before the string, -1 means the message before
# that, etc.  Which message or messages is/are provided depends on the
# 'count' argument to the asc2bin initializer, which is used only when
# parsing VMDAS data.

field_dictN = copy.deepcopy(field_dict1)
for value in field_dictN.values():
    value += ['count', 'ens_num']


haltflag = 0  # for interrupting the incremental conversion

# TODO: same name as asc2bin in msg.py...why?
class asc2bin(msg.Asc2binBase):
    def __init__(self, yearbase = None,
                   log_yearbase = None,
                   outfiledir = './',
                   message = None,
                   redo = 0,
                   skip_bad = 0,
                   showbad = 0,
                   verbose = 0,
                   count = 'last',
                   optdict = {},
                   logname = 'asc2bin'
                   ):
        logging.basicConfig()
#        L.setLevel(logging.INFO)
        self.yearbase = yearbase
        self.log_yearbase = log_yearbase
        self.verbose = verbose
        self.showbad = showbad
        self.outfiledir = outfiledir
        self.redo = redo
        self.skip_bad = skip_bad
        self.message = message
        self.last_dday = -100000
        self.timer = time.sleep  # default; override comes in via optdict
        self.type = 'vmdas'
        self.count = count
        self.last_psxn20 = None
        self.last_gga = None
        self.function_dict = function_dict.copy()
        self.function_dict['sea'] = self.get_sea
        self.function_dict['gps_sea'] = self.get_gps_sea
        for k, v in optdict.items():
            setattr(self, k, v)
        if self.log_yearbase is None: #it was unset
            self.log_yearbase = self.yearbase
        if self.message in ['gps','gga','ggn', 'rmc', 'pmv','pat','sea', 'gps_sea']:
            self.check_dday = self.check_gga_dday
        elif self.message == 'adu':
            self.check_dday = self.check_adu_dday
        else:
            self.check_dday = lambda x: x

        if not os.access(self.outfiledir, os.F_OK):
            os.makedirs(self.outfiledir, 0o775)
        self.epoch_t = time.mktime((self.yearbase, 1, 1, 0, 0, 0, 0, 0, 0))
        epoch_tlog = time.mktime((self.log_yearbase, 1, 1, 0, 0, 0, 0, 0, 0))
        self.yearbase_dif_days = round((epoch_tlog - self.epoch_t) / 86400.0)

        if self.type[-2:] == 'uh': #'uh' 'olduh'
            self.translate_file = self.translate_file2
            self.get_dday = self.get_UNIX_dday
        elif self.type == 'rvdas':
            self.translate_file = self.translate_file1
            self.split_line = msg.split_rvdas
            self.get_dday = msg.get_rvdas_dday
        elif self.type == 'whoi_dslog':
            self.translate_file = self.translate_file1
            self.split_line = msg.split_dslog
            self.get_dday = msg.get_dslog_dday
        elif self.type == 'scs':
            self.translate_file = self.translate_file1
            self.split_line = msg.split_scs
            self.get_dday = msg.get_scs_dday
        elif self.type == 'vids':
            self.translate_file = self.translate_file1
            self.split_line = msg.split_vids
            self.get_dday = msg.get_vids_dday
        elif self.type == 'samos_xml':
            self.translate_file = self.translate_file1
            self.split_line = msg.split_samosxml
            self.get_dday = msg.get_samosxml_dday
        elif self.type == 'osu_csv':
            self.translate_file = self.translate_file1
            self.split_line = msg.split_osucsv
            self.get_dday = msg.get_samosxml_dday
        elif self.type == 'lds':
            self.translate_file = self.translate_file1
            self.split_line = msg.split_lds
            self.get_dday = msg.get_lds_dday
        elif self.type.startswith('vmdas'):
            self.translate_file = self.translate_file3
            self.get_dday = msg.get_vmdas_dday
        elif self.type.startswith('rsmas'):
            self.split_line = msg.split_rsmas
            self.translate_file = self.translate_file1
            self.get_dday = msg.get_rsmas_dday
        else:
            raise NameError(self.type)


    def translate_file1(self, filename, outfilename):
        '''The time tag and the message are on a single line. eg. RVDAS
        '''
        # redo RVDAS
        ext = outfilename.split('.')[-2]
        field_dict = field_dict1
        try:
            get_field = self.function_dict[ext]
            header = write_header(ext, field_dict[ext])
            nfields = len(field_dict[ext])
        except KeyError:
            print('filename <%s> has unrecognized extension <%s>\n' % (
                outfilename, ext))
            return -1
        split_line = self.split_line
        get_dday = self.get_dday
        a = array.array('d')
        i = 0
        for line in self.open(filename, 'rb'):
            i += 1
            if self.verbose > 1:
                print('%d %s' % (i, line), end=' ')
            try:
                timetag, nmea = split_line(line)
                fieldlist = get_field(nmea)
                if fieldlist:
                    newtime = get_dday(timetag,self.yearbase,self.epoch_t)
                    fieldlist.insert(0, newtime)
                    fieldlist = self.check_dday(fieldlist)
                    a.fromlist(fieldlist)
            except:
                if self.showbad:
                    print('%s: BAD: %d %s' % (ext, i, line), end=' ')
                    raise
                if self.skip_bad is False:
                    raise ValueError
                else:
                    print('continuing anyway...')

        fo = open(outfilename, 'wb')
        fo.write(header)
        a.tofile(fo)
        fo.close()
        return len(a) // nfields

        # Pre-allocating the full size of the array and then using
        # the insert method is slower, not faster, than using the
        # append method.


    def translate_file2(self, filename, outfilename):
        '''The time tag is on the line preceeding the message.  eg. uhdas
        '''
        # redo UH
        field_dict = copy.deepcopy(field_dict1)
        if self.type in ('uh', 'olduh'):
            for key, value in field_dict.items():
                value.append('m_dday')
        ext = outfilename.split('.')[-2]
        try:
            get_field = self.function_dict[ext]
            header = write_header(ext, field_dict[ext])
            nfields = len(field_dict[ext])
        except KeyError:
            print('filename <%s> has unrecognized extension <%s>\n' % (outfilename, ext))
            return -1
        get_dday = self.get_dday  # returns a list with [u_dday,m_dday] or [u_dday,]
        f = self.open(filename, 'rb')
        lines = f.readlines()
        f.close()
        a = array.array('d')
        for i in range(0, len(lines)-1, 2):
            if self.verbose > 1:
                print('linenum=%d: %s\n' % (i, lines[i]))
                print('linenum=%d: %s\n' % (i+1, lines[i+1]))
            try:
                fieldlist = get_field(lines[i+1].rstrip())
                ddaylist = get_dday(lines[i])
                Uparts = lines[i].split(b',')[1:] # just the numbers
                if fieldlist:
                    # add u_dday to the beginning
                    fieldlist.insert(0, ddaylist[0])
                    # add m_dday to the end if appropriate
                    if self.type == 'uh':
                        if len(Uparts) == 1:
                            print('expecting m_dday on $UNIXD line.  ')
                            print('maybe use "--type olduh"??')
                            sys.exit()
                    elif self.type == 'olduh':
                        if len(Uparts) == 2:
                            print('too many elements on UNIXD line.  ')
                            print('maybe use "--type uh"??')
                            sys.exit()
                        else:
                            fieldlist.append(ddaylist[0]) #add fake m_dday
                    fieldlist = self.check_dday(fieldlist)
                    a.fromlist(fieldlist)
            except:
                if self.showbad:
                    print('%s: BAD: %d %s' % (ext, i, lines[i]), end=' ')
                    print('%s: BAD: %d %s' % (ext, i+1, lines[i+1]), end=' ')
                if self.skip_bad:
                    raise ValueError


        fo = open(outfilename, 'wb')
        fo.write(header)
        a.tofile(fo)
        fo.close()
        return len(a) // nfields

        # Pre-allocating the full size of the array and then using
        # the insert method is slower, not faster, than using the
        # append method.


    def translate_file3(self, filename, outfilename):
        '''A series of message lines preceed a time stamp line.
        This is presently specific to VMDAS data, but could be
        generalized.
        '''
        field_dict = field_dictN
        ext = outfilename.split('.')[-2]
        try:
            get_field = self.function_dict[ext]
            header = write_header(ext, field_dict[ext])
            nfields = len(field_dict[ext])
        except KeyError:
            print('filename <%s> has unrecognized extension <%s>\n' % (outfilename, ext))
            return -1
        get_dday = self.get_dday
        f = self.open(filename, 'rb')
        lines = f.readlines()
        f.close()
        a = array.array('d')

        # Undo the PADCP nonsense: when $PADCP record ends a line,
        # move it to the next position, and tack what was the next
        # line onto the end of the first.
        for i, line in enumerate(lines[:-1]):
            ind = line.find(b"$PADCP")
            if ind > 0:
                line0 = line[:ind]
                linep = line[ind:]
                line1 = lines[i+1]
                lines[i] = line0 + line1
                lines[i+1] = linep

        # for each field that occurs BEFORE the next time stamp,
        # store the entries in a list and
        # then print all messages with the timestamp


        msglist = []  ## accrete messages here

        for i, line in enumerate(lines):
            try:
                # Is it the message? If so, append it to msglist.
                fieldlist = get_field(line.rstrip())
                if fieldlist is not None:
                    msglist.append(fieldlist)
                    continue   # Get another line.

                # It's not the message, so look for a $PADCP timestamp.
                lst =  get_dday(line, self.yearbase, self.epoch_t)
                if lst != None and msglist != []:
                    # Now we have at least one message followed by
                    # a timestamp, so assemble the message(s) and
                    # timestamp.
                    dday = lst[0]
                    ens_num = lst[1]
                    mlistlen = len(msglist)
                    if self.count == 'first':
                        numrange = (0,)
                    elif self.count == 'last':
                        numrange = (mlistlen - 1,)
                    else:
                        numrange = list(range(mlistlen))
                    for num in numrange:
                        r = [dday] + msglist[num]
                        r += [ float(num - mlistlen + 1),   # 'count'
                               float(ens_num)]
                        r = self.check_dday(r)
                        a.fromlist(r)
                    msglist = []  #reinitialize msglist
            except:
                if self.showbad:
                    print('%s: BAD: %d %s' % (ext, i, line), end=' ')
                if self.skip_bad is False:
                    raise ValueError

        #now write it all out to disk

        fo = open(outfilename, 'wb')
        fo.write(header)
        a.tofile(fo)
        fo.close()
        return len(a) // nfields


    def translate_files(self, filenames, **kw):
        self.__dict__.update(kw)
        #for k in kw.keys():
        #   setattr(self, k, kw[k])
        n = 0
        try:
            for filename in filenames:
                if self.verbose:
                    print(filename)
                fpath, fname = os.path.split(filename)
                fname_base, log_ext = os.path.splitext(fname)
                if log_ext == '.gz':
                    fname_base, log_ext = os.path.splitext(fname_base)
                    self.open = gzip.open
                else:
                    self.open = open
                out_ext = self.message or log_ext[1:]
                # if UH, replace msg; else add message; always add '.rbin'

                if self.type in ('uh', 'olduh'):
                    ofbase=fname_base
                else:
                    ofbase=fname
                outfilename = os.path.join(self.outfiledir,'%s.%s.rbin' %(
                                 (ofbase, out_ext)))
                if self.redo or not os.access(outfilename, os.F_OK):
                    n = self.translate_file(filename, outfilename)
                else:
                    if self.verbose: print('no action')
        except KeyboardInterrupt:
            raise
        except:
            raise
        return n  # number of records written to the last file

os.environ['TZ'] = 'UTC'


def main():
    import getopt

    try:
        options, args = getopt.getopt(sys.argv[1:], 'SvVhrbo:y:l:m:ac:t:',
                              ['showbad', 'verbose', 'Verbose', 'help',
                               'redo', 'skip_bad', 'outdir=', 'yearbase=',
                               'log_yearbase=',
                               'message=', 'count=',
                               'type='])
    except getopt.GetoptError:  # Before Python 2.x this was getopt.error
        usage('error in argument list')

    if len(args) == 0:
        print(options)
        usage()

    opts = {}

    for o, a in options:
        if o in ('-h', '--help'):
            usage()
        elif o in ('-r', '--redo'):
            opts['redo'] = 1
        elif o in ('-b', '--skip_bad'):
            opts['skip_bad'] = 1
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
        elif o in ('-m', '--message'):
            opts['message'] = a
        elif o in ('-c', '--count'):
            opts['count'] = a
        elif o in ('-t', '--type'):
            opts['type'] = a


    t0 = time.process_time()

    if 'type' in list(opts.keys()):
        if opts['type'] == 'vmdas':
            if opts['count'] not in ('first', 'last', 'all'):
                print("option 'count' must be 'first', 'last', or 'all'")
                print("you chose '%s'" % opts['count'])
                sys.exit()

    import glob
    filenames = []
    for arg in args:
        filenames += glob.glob(arg)

    asc2bin(optdict = opts).translate_files(filenames)

    t1 = time.process_time()
    print('Elapsed cpu time:   %.1f s' % (t1 - t0))


if __name__ == '__main__':
    main()
