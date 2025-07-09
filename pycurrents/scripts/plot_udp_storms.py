#!/usr/bin/env python

'''
   plot_udp_storms.py: parse nmea messages logged by UHDAS.

   Usage: plot_udp_storms.py [<options>] [-y 2001] ... file1 [file2 ...]
'''

import sys
import os
import array
import logging
import numpy as np


from optparse import OptionParser
from pycurrents.system import pathops
from pycurrents.codas import to_datestring
from pycurrents.num.binstats import binstats
from pycurrents.adcp import uhdasfileparts
from pycurrents.num import rangeslice
from pycurrents.plot.mpltools import savepngs
from pycurrents.num import Stats
from pycurrents.data.nmea import asc2bin
from pycurrents.file.linefile_tail import linefile2s
from pycurrents.data.nmea.msg import frac_to_dday

# Standard logging
_log = logging.getLogger('udp_storms')

#
if ('--noshow' in sys.argv):
    import matplotlib
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib


# make the fonts bigger
font = {'weight' : 'bold',
        'size'   : 12}
matplotlib.rc('font', **font)

def trim_filelist(filelist, startdday=None, ndays=None, file_hours=2):
    '''
    return a subset of the filelist using file start times (from names)
    with startdday, through ndays (using file startime + 2 hours)

    new filelist replaces old filelist
    '''
    if not filelist:
        return
    file_dt = file_hours/24.  # typical duration of UHDAS files
    filelist.sort()
    if not startdday and not ndays:
        return filelist

    F = uhdasfileparts.FileParts(filelist)
    starts = F.dday
    maxends = starts + file_dt
    if startdday:
        if ndays:
            if ndays > 0:
                startdd = startdday
                enddd = startdday + ndays + file_dt
            else:
                startdd = startdday + ndays
                enddd = startdday
        else:
            startdd = startdday
            enddd = maxends[-1]
        sl = rangeslice(starts, startdd, enddd)
    else:
        sl = rangeslice(starts, ndays)

    return filelist[sl]

#----
# Subclass asc2bin

class PYRTM_Reader(asc2bin.asc2bin):
    ## new. -- override/add some methods

    def check_gga_dday_all(self, r, check_repeat=False):
        r[1] = frac_to_dday(r[0], r[1])
        if check_repeat:
            if abs(r[1] - self.last_dday) < 1e-9: # around 0.0001 s
                return []
        self.last_dday = r[1]
        return r

    def check_adu_dday_all(self, r, check_repeat=False):
        """
        ATT message uses GPS time.  Here we make a 14-s correction
        for dates up to 2009 (valid for 2006-2008), and 15-s
        correction for 2009 and later.  When another leap-second
        is announce, this routine will need to be updated accordingly.
        """
        dday_gps = frac_to_dday(r[0], r[1]) - 15.0/86400 #from 2009/01/01
        year = self.yearbase + int(dday_gps//365)
        if year < 2009:
            dday_gps += 1.0/86400
        r[1] = dday_gps
        if check_repeat:
            if abs(r[1] - self.last_dday) < 1e-7: # around 0.01 s
                return []
        self.last_dday = r[1]
        return r

    def translate_pyrtm_nowrite(self, filename):
        # was translate_file2; now stripped of 'writing'
        '''The time tag is on the line preceeding the message. (eg. UHDAS logging)
        '''
        self.filename = filename
        self.Ngood = 0
        self.Nbad = 0
        # append to UH
        f_in = linefile2s(filename, sync = ['$UNIXD', '$PYRTM'],
                          timeout = self.sleepseconds,
                          keep_running = self.keep_running)
        lines = f_in.read_records()
        n = len(lines)//2
        recs = array.array('d')
        if n > 0:
            for ii in range(0, 2*n, 2):
                rec = self.make_record(lines[ii], lines[ii+1])
                if rec:
                    recs += rec
        else:
            _log.warning(f'no lines in file {filename}')

        f_in.close()
        _log.debug('End translate_pyrtm_nowrite_')
        return recs

    def translate_pyrtm_files(self, filenames):
        #self.__dict__.update(kw)
        recs = array.array('d')
        try:
            for filename in filenames:
                if not self.verbose:
                    _log.info(filename)
                recs += self.translate_pyrtm_nowrite(filename)

        except KeyboardInterrupt:
            raise
        except Exception as e:
            _log.exception(f"An error occurred while processing the file {filename}:\n{e}")
        return recs

if __name__ == "__main__":

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(1)

    if '--help' in sys.argv:
        print(__doc__)

    parser = OptionParser()

    parser.add_option("-v", "--verbose", dest="verbose", action="store_true",
                      default = False,
                      help="print things")
    parser.add_option("-V", "--Verbose", dest="Verbose", action="store_true",
                      default = False,
                      help="print things")
    parser.add_option("--showbad", dest="showbad", action="store_true",
                      default = False,
                      help="show bad lines")

    parser.add_option("-y", "--yearbase", dest="yearbase", default = None,
               help="yearbase - required")
    parser.add_option("--message", dest="message", default = None,
               help="msg for parsing")

    parser.add_option("-n", "--ndays", dest="ndays", default = None, # i.e. all
               help="choose how many days to test; negative is from the end")

    parser.add_option("-T", "--title", dest="titlestr", default = "UDP storms",
               help="title string")

    parser.add_option("-s", "--startdday", dest="startdday",
                      default = None, # i.e. all
               help="when to start")

    parser.add_option("-o", "--outfile", dest="outfile", default=None,
                      help="save the text to this file")

    parser.add_option("-p", "--pngfile", dest="pngfile",
                      default = None,
                      help="save figure as PNGFILE.png")

    parser.add_option("-d", "--outdir", dest="outdir",
               default = './',  help="save files to this directory")

    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")

    (options, args) = parser.parse_args()

    if not options.show and options.pngfile is None:
        _log.error('not showing figure; select a PNGFILE file name for saving')

    if options.startdday:
        options.startdday= float(options.startdday)
    if options.ndays:
        options.ndays= float(options.ndays)
    verbose = 0
    if options.verbose:
        verbose = 1
    if options.Verbose:
        verbose = 2

    PYRTM_opts = dict()
    PYRTM_opts['yearbase']=int(options.yearbase)
    PYRTM_opts['verbose']=options.verbose
    PYRTM_opts['showbad']=options.showbad
    PYRTM_opts['message']=options.message

    '''
    # testing
    PYRTM_opts = dict()
    PYRTM_opts['yearbase']=2022
    PYRTM_opts['verbose']=1
    PYRTM_opts['showbad']=False
    PYRTM_opts['message']='gps'

    filelist=pathops.make_filelist('test_data/seapath_udp/*')
    newlist=filelist[:3]
    '''

    if len(args) > 0:
        filelist = pathops.make_filelist(args)
        if len(filelist) == 0:
            msg = 'no valid filenames found from args'
            _log.error(msg)
            raise IOError(msg)
        newlist = trim_filelist(filelist, startdday=options.startdday,
                                ndays=options.ndays)
    else:
        print(__doc__)
        sys.exit(1)

    ### Initialize PYRTM_Reader and override some methods+attributes
    PR = PYRTM_Reader(**PYRTM_opts)

    if PR.message in ['gps', 'gga', 'ggn', 'gns', 'rmc',
                    'pat', 'paq', 'pmv', 'pvec', 'sea',
                    'gps_sea', 'psathpr', 'gpgst', 'ptnlvhd', 'hpr']:
        PR.check_dday = PR.check_gga_dday_all
    elif PR.message in ['adu', 'at2']:
        PR.check_dday = PR.check_adu_dday_all
    else:
        PR.check_dday = lambda x: x

    # now use it.

    recs = PR.translate_pyrtm_files(newlist)
    numrecs = int(len(recs)/PR.recordlength)
    adata= np.array(recs.tolist()).reshape(numrecs, PR.recordlength)
    rdtype = np.dtype({'names':PR.fields,
                       'formats':['f8']*PR.recordlength})
    data = adata.view(type=np.recarray, dtype=rdtype).ravel()

    ###  get stats
    secs=86400*(data['u_dday']-data['u_dday'][0])
    dt = np.diff(secs)
    seglen=300
    segends=np.arange(secs[0], secs[-1]+seglen, seglen)
    binpt,binmean,binstd,binn=binstats(secs[:-1], dt, segends)

    # print before plotting
    outlist = ['%d files: %s through %s:' % (len(filelist),
                                             filelist[0],
                                             filelist[-1]),]
    bigcount=np.where(binn>1.05*Stats(binn).median)[0]
    for ibig in bigcount:
        u_dday = segends[ibig]/86400. + data['dday'][0]
        outlist.append('5 min starting at %s, count=%d' %
              (to_datestring(2022, u_dday), binn[ibig]))
    bigstring = '\n'.join(outlist) + '\n\n'
    if options.outfile:
        open(os.path.join(options.outdir, options.outfile),'w').write(bigstring)
    else:
        print(bigstring)

    # plot
    f,ax=plt.subplots(figsize=(9,10), nrows=4)

    ax[0].plot((binpt/86400.) + data['u_dday'][0], binn, 'r')
    ax[0].set_xlabel('decimal day')
    ax[0].set_ylabel('number of messages')
    ax[0].text(.95,.90,'number of messages in 5-minute chunks', ha='right',
          transform=ax[0].transAxes)

    ax[1].plot(data.u_dday[1:], dt)
    ax[1].set_ylabel('seconds')
    ax[1].text(.95,.90,'gap between message arrival times ', ha='right',
          transform=ax[1].transAxes)
    ax[1].set_title('')
    ax[1].set_xlabel('decimal day')

    ax[2].plot(data.u_dday[1:], dt)
    ax[2].set_ylim(-1,5)
    ax[2].set_ylabel('seconds')
    ax[2].text(.95,.90,'gap between message arrival times (zoom)', ha='right',
          transform=ax[2].transAxes)
    ax[2].set_xlabel('decimal day')

    ax[3].plot(data.dday,'y-')
    ax[3].plot(data.dday,'r.',ms=2)
    ax[3].set_ylabel('decimal day')
    ax[3].text(.1,.90,'GGA message decimal day',
          transform=ax[3].transAxes)
    ax[3].set_xlabel('index')

    f.text(.5,.95,options.titlestr,ha='center', fontsize="large")

    restore_ion = False
    if not options.show and plt.isinteractive():
        plt.ioff()
        restore_ion = True

    if options.pngfile is not None:
        savepngs(os.path.join(options.outdir, options.pngfile), dpi=110, fig=f)

    if options.show:
        plt.show()

    if restore_ion:
        plt.ion()
