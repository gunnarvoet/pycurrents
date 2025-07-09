'''
Tools for reading adcp data in various formats.

Modified from py_utils/uhdastools/readtools.
'''

import os
import glob
import time
import sys
import logging
import warnings
import numpy as np
from numpy import ma

from pycurrents.codas import get_profiles
from pycurrents.codas import masked_codas
from pycurrents.file.binfile_n import binfile_n
from pycurrents.data.navcalc import unwrap_lon
from pycurrents.adcp.transform import heading_rotate
from pycurrents.data import navcalc
from pycurrents.adcp.raw_multi import Multiread
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.system.misc import Bunch
from pycurrents.system import pathops
from pycurrents.num import regrid
from pycurrents.num import interp1

import scipy.io as spio



# Standard logging
_log = logging.getLogger(__name__)

# suppress these warnings:
##  warnings.warn("All-NaN slice encountered", RuntimeWarning)
warnings.filterwarnings('ignore', r'All-NaN (slice|axis) encountered')


class Binsuite:

    '''
    Methods to read a suite of bin files written by matlab
    "write_binsuite"; store data in a dictionary, and as
    attributes.
    No scale factors (eg. velocities are cm/s)

    Usage:

        bs = Binsuite('somedir', 'someprefix')
        print bs.filelist # to see the file names
        print bs        # to see the variables
        data = bs.data  # to get the dictionary
        bs.remove()     # to delete all the files
        v = bs.vabs     # access arrays as attributes
                        # (equivalent to bs.data['vabs']

    Note: Binsuite is being replaced by npz_lastens in
    ensplot, as of 2010/12/21.

    '''

    def __init__(self, path='.', prefix='suite', masked=True):
        self.path = path
        self.prefix = prefix
        self.masked = masked

        globstr = os.path.join(path, '%s_*.sbin' % (prefix,))
        self.filelist = glob.glob(globstr)
        if not self.filelist:
            raise ValueError('no files found')
        self._read()
        self._infostr = ''
        self._file_age_secs()

    def __str__(self):
        if not self._infostr:
            ss = ['         variable       nbins           nprofs',
                  '      ------------       -----           ------']
            for vname in self.data.keys():
                ss.append('%15s   %10d    %10d' % \
                       (vname, self.nbins[vname], self.nprofs[vname]))
            self._infostr = '\n'.join(ss)
        return self._infostr

    def __repr__(self):
        return self.__str__()

    def _file_age_secs(self):
        secs = 0
        now_epoch = time.time()
        for filename in self.filelist:
            secs = max(secs, now_epoch - os.path.getmtime(filename))
        self.age_secs = secs


    def _read(self):
        data={}
        self.nprofs = {}     ## These are used but not essential.
        self.nbins = {}

        for filename in self.filelist:
            filebase = os.path.basename(filename)
            varname = filebase.split('.')[0][len(self.prefix)+1:]

            b = binfile_n(filename)

            mat = b.read()

            if varname == 't':
                for icolumn in range(b.ncolumns):
                    vname = b.columns[icolumn]
                    data[vname] = mat[:,icolumn]
                    self.nprofs[vname] = mat.shape[0]
                    self.nbins[vname] = 1

            elif varname =='z':
                for icolumn in range(b.ncolumns):
                    vname = b.columns[icolumn]
                    data[vname] = mat[:, icolumn]
                    self.nprofs[vname] = 1
                    self.nbins[vname] = mat.shape[0]

            else:
                vname = b.columns[0][:-3]
                data[vname]=mat
                self.nprofs[vname], self.nbins[vname]= data[vname].shape

            b.close()


        ## maybe we should delete the original?
        # New standard 1D depth array name is "dep".
        if 'depth' in data and 'dep' not in data:
            data['dep']   = data['depth']
            self.nbins['dep']  = self.nbins['depth']
            self.nprofs['dep'] = self.nprofs['depth']
        # New standard 1D depth array name is "dep".
        if 'z' in data and 'dep' not in data:
            data['dep']   = data['depth']
            self.nbins['dep']  = self.nbins['z']
            self.nprofs['dep'] = self.nprofs['z']

        # Something looks wrong above--aren't the 'dep'
        # variables supposed to be 1-D?  It doesn't look
        # like they are.

        if 'uabs' in data:
            data['u'] = data['uabs']
            data['v'] = data['vabs']

            self.nbins['u']  = self.nbins['uabs']
            self.nbins['v']  = self.nbins['vabs']

            self.nprofs['u']  = self.nprofs['uabs']
            self.nprofs['v']  = self.nprofs['vabs']


        for k in ['u', 'v', 'heading', 'heading_used', 'lon', 'lat']:
            if k in data:
                data[k] = masked_codas(data[k], nancheck=True).astype(float)
            if k in ['u','v']:
                data[k] = data[k]/100.0

        if 'lon' in data:
            data['lon'] = unwrap_lon(data['lon'])

        self.__dict__.update(data)
        self.data = data

    def remove(self):
        for filename in self.filelist:
            os.remove(filename)
        self.filelist = []

                                    # DO NOT DELETE. used to make shoreside
def get_uvztbin(prefix, path='./'): # plots (in process_tarballs.py )
    '''
    read txy,uv,[amp] output, saved as binfiles or bin and npy

    This is for files written by UHDAS and emailed in the daily tarball.
    for u and v.
    '''
    basename = os.path.join(path, prefix)
    ufile = '%s_u.npy' % (basename,)
    _int = False
    if os.path.exists(ufile):
        u = np.load(ufile)
        v = np.load('%s_v.npy' % (basename,))
        _int = True
        _npy = True
        ampfile = '%s_amp.npy' % (basename,)
        if os.path.exists(ampfile):
            amp = np.load('%s_amp.npy' % (basename,))
        else:
            amp = None
    else: # written by matlab. no amp
        ufile = '%s_u.bin' % (basename,)
        u = binfile_n(ufile).read()
        vfile = '%s_v.bin' % (basename,)
        v = binfile_n(vfile).read()
        if u.dtype.char in np.typecodes['Integer']:
            _int = True
        _npy = False
    xfile = '%s_xytT.bin' % (basename,)
    X = binfile_n(xfile)
    xyt = X.read()
    lon = xyt[:, X.columns.index('lon')]
    lat = xyt[:, X.columns.index('lat')]
    T = None
    if 'T' in X.columns:
        T = xyt[:, X.columns.index('T')]

    dday = xyt[:, X.columns.index('dday')]

    zfile = '%s_zYR.bin' % (basename,)
    Z = binfile_n(zfile)
    zyr = Z.read()
    z = zyr[:, Z.columns.index('zc')]
    if _npy:
        zc = z
    else:
        zc = (z[1:] + z[:-1])/2  # looks like a bug in generation of
                                  # zYR.bin by matlab

    yearbase =  int(zyr[0, Z.columns.index('yearbase')])

    nr, nc = u.shape
    if nr == len(zc) and nc == len(lon) and nr != nc:
        u = u.T
        v = v.T

    if amp is None:
        data = {'u'       :    u,
                'v'       :    v,
                'lon'     :    lon,
                'lat'     :    lat,
                'dday'    :    dday,
                'T'       :    T,
                'dep'     :    zc,
                'yearbase': yearbase}
    else:
        data = {'u'       :    u,
                'v'       :    v,
                'amp'     :    amp,
                'lon'     :    lon,
                'lat'     :    lat,
                'dday'    :    dday,
                'T'       :    T,
                'dep'     :    zc,
                'yearbase': yearbase}

    ## return masked data
    for k in ['u', 'v', 'lon', 'lat', 'T']:
        val = data[k]
        if val is not None:
            data[k] = masked_codas(val, nancheck=True)
            if k == 'lon':
                data[k] = unwrap_lon(data[k])

    if 'amp' in data.keys():  # amp is not masked, but there might be gaps
        val = data['amp']
        if val is not None:
            data['amp'] = masked_codas(val, nancheck=True)


    if _int:   # it is integer cm/s
        for k in ['u', 'v']:
            data[k] = data[k] / 100.0
        if 'amp' in data.keys():
            data['amp'] = data['amp'] / 100.0

    return data

#---------------

def matread_adcpsect(prefix, path='./',  ndays = None, masked=False):
    '''
    read specified *_uv.mat and *_xy.mat files; return a dictionary
        with dday, lon, lat, u, v, z; u and v are in m/s

        ndays : take up to this number of days from the end,
                    or it can be a sequence of two numbers
                    giving the dday limits.

        masked : False (default) for no masking, so bad data
                    will be nan; if True, then all arrays except
                    dday and z will be converted to masked arrays
    '''

    basename = os.path.join(path, prefix)


    veldata = spio.loadmat('%s_uv.mat' % (basename,))
    u = veldata['uv'][:,::2]
    v = veldata['uv'][:,1::2]
    odata = spio.loadmat('%s_xy.mat' % (basename,))
    dday = odata['xyt'][2,:]
    jgood = np.nonzero(~np.isnan(dday))[0]
    nprofs = len(jgood)
    if nprofs < len(dday):
        odata['xyt'] = odata['xyt'].take(jgood, axis=1)
        dday = dday.take(jgood)
        u = u.take(jgood, axis=1)
        v = v.take(jgood, axis=1)

    if nprofs:
        try:
            len(ndays)
        except TypeError:
            ndays = [ndays]
        if ndays[0] is None:
            jj = slice(nprofs)
        elif len(ndays) == 1:
            ndays = ndays[0]
            if ndays > 0:
                jj = (dday - dday[0]) < ndays
            elif ndays < 0:
                jj = dday > (dday[-1] + ndays)
            else:
                #print 'warning zero duration chosen for adcpsect data\n'
                return {} # probably not what we want in this case
        else: #assume 2-d
            jj = (dday >= ndays[0]) & (dday <= ndays[1])
    else:
        jj = []

    data = {}
    data['u'] = u[:,jj].T
    data['v'] = v[:,jj].T
    # others
    data['lon']  = odata['xyt'][0,jj]
    data['lat']  = odata['xyt'][1,jj]
    data['dday'] = dday[jj]
    data['dep']    = odata['zc'].flatten() # unnecessary copy, but easy
                                           # way to make it 1-D
    if masked:
        for k, val in data.items():
            if k not in ['dep', 'dday']:
                data[k] = ma.masked_invalid(val)
    data['yearbase'] = int(odata['year_base'])

    data['lon'] = unwrap_lon(data['lon'])

    return data


#exceptions
class DataGetError(Exception):
    ''' exception for get_adata
    '''
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr('could not get data using %s' % (self.value,))

#--------------
def get_adata(prefix, path= './', read_fcn = None,
              ndays = None,   yearbase = None):
    '''
    standardized scheme to get data from various processed adcp sources
    output: a dictionary of fields incuding u,v,dep,dday,lon,lat

    -------------
    ## read from a database directly (return unflagged)

    codasdb(dbname,                         # dbname includes path
            ndays=None,                     # float or [start, end]
            yearbase = None)

    -------------
    ## read files written by matlab using (written by write_bin)

    get_uvztbin(prefix,                     # prefix without ".bin"
             path = somepath                # path to files
    binsuite(prefix,                        # prefix without ".sbin"
             path = somepath                # path to files

    -------------
    ## read files using scipy.io.mio.readmat (read_fcn = 'adcpsect_mat'):
    matread_adcpsect(prefix,                # adcpsect (do not include _uv.mat)
                     path=somepath)         # path to files

    '''

    _log.debug( 'path+prefix is %s' % (os.path.join(path, prefix),) )

    allowed_readfcns = ['codasdb',
                        'uvztbin',
                        'binsuite',
                        'adcpsect_mat',
                        ]

    if read_fcn not in allowed_readfcns:
        raise ValueError('read function %s not recognized', read_fcn)
    elif read_fcn == 'codasdb':
        try:
            data = get_profiles(os.path.join(path,prefix), yearbase=yearbase,
                                    ndays=ndays)
        except Exception:
            _log.exception("codasdb")
            raise DataGetError(read_fcn)

    elif read_fcn == 'uvztbin':    # This is the format of uhdas tarballs.
        try:
            data = get_uvztbin(prefix, path=path)   #includes yearbase
            #  consistency: (u,v,lon,lat,temperature)
            data['tr_temp'] = data['T']
        except Exception:
            _log.exception("uvztbin")
            raise DataGetError(read_fcn)
    elif read_fcn == 'binsuite':
        try:
            b = Binsuite(prefix=prefix, path=path)
            data = b.data                           # *lacks* yearbase
        except Exception:                                     # therefore *broken*
            _log.exception("binsuite")
            raise DataGetError(read_fcn)
    elif read_fcn == 'adcpsect_mat':
        try:
            data = matread_adcpsect(prefix, path=path)  #includes yearbase
        except Exception:
            _log.exception('adcp_mat')
            raise DataGetError(read_fcn)

    return data



### ============================================


def regrid_zonly(t, field, Z, z):
    '''
    t is (nprofs x 1)
    Z is (nprofs x Nbins) usually from get_profiles with bin,ncell varying
    field is (nprofs x Nbins) , eg amp, u, errvel
    z is a specific collection of output levels, (1 x M)
    '''
    new_field = np.ma.zeros((len(t), len(z)),float)
    for iprof in range(len(t)):
        new_field[iprof,:] = interp1(Z[iprof,:], field[iprof,:], z)
    #
    return new_field

#--------------

#--------------

def timegrid_cdb(data, deltat=.02, startz=None, deltaz=10, outbin=None):
    '''
    ##
    regrids adcp data from CODAS DB on a uniform t-z grid

        data is a ProcEns most easily returned by this:

            data = get_profiles(dbname, ndays = ndays)

        deltat is timestep in days (.02 days is about 30 minutes),
        deltaz is vertical step
        outbin = None returns all output (for contour)
        outbin = int returns a single bin (for vector)

        returns dictionary with keys dday, lon, lat, dep, u, v, temp
    '''

    # input arguments are in 't-z' (time, vertical) coordinates
    # in the code below, 'x-y' refers to the same (abcissa, ordinal)

    if 'amp' in data.keys():
        has_amp=True
    else:
        has_amp=False


    # inputs
    xin = data['dday']  # Must not have masked or bad points.

    if 'dep' in data:          # data snippets sent to shore
        temp_u=data['u']
        temp_v=data['v']
        if has_amp:
            temp_a = data['amp']
        temp_y = data['dep']
    else:
        if (np.diff(data['depth'],axis=1) == 0).all():
            temp_u=data['u']
            temp_v=data['v']
            if has_amp:
                temp_a=data['amp']
            temp_y = data['depth'][0,:]
        else:
            #regrid u and v by profile to be on the finest grid in the data
            temp_y = np.arange(data['depth'].min(), data['depth'].max() + 0.01,
                               np.diff(data['depth']).min())
            temp_u = np.ma.zeros((len(xin), len(temp_y)),float)
            temp_v = np.ma.zeros((len(xin), len(temp_y)),float)
            if has_amp:
                temp_a = np.ma.zeros((len(xin), len(temp_y)),float)
            for iprof in range(len(xin)):
                temp_u[iprof,:] = interp1(data['depth'][iprof,:],
                                      data['u'][iprof,:], temp_y)
                temp_v[iprof,:] = interp1(data['depth'][iprof,:],
                                      data['v'][iprof,:], temp_y)
                if has_amp:
                    temp_a[iprof,:] = interp1(data['depth'][iprof,:],
                                      data['amp'][iprof,:], temp_y)

    yin = data['dep']
    data['lon'] = unwrap_lon(data['lon'])

    # outputs

    gdata = Bunch()
    xout = np.arange(xin[0], xin[-1], deltat)
    gdata['dday'] = xout
    gdata['lon']  = interp1(data['dday'], data['lon'], xout)
    gdata['lat']  = interp1(data['dday'], data['lat'], xout)
    gdata['tr_temp'] = interp1(data['dday'], data['tr_temp'], xout)

    if startz is None:
        starty = yin.min()
    else:
        starty = startz

    if deltaz > 0:
        yout = np.arange(starty, yin.max(), deltaz)
    else:
        yout = np.arange(starty, yin.min(), deltaz)
    gdata['dep']  = yout
    if 'yearbase' in data:
        gdata['yearbase'] = data['yearbase']


    gdata['u'] = regrid(temp_y, xin, temp_u, yout, xout)
    gdata['v'] = regrid(temp_y, xin, temp_v, yout, xout)
    if has_amp:
        gdata['amp'] = regrid(temp_y, xin, temp_a, yout, xout)

    if outbin is not None:
        gdata['u'] = gdata['u'][:,outbin]
        gdata['v'] = gdata['v'][:,outbin]
        if has_amp:
            gdata['amp'] = gdata['amp'][:,outbin]

    return gdata

#--------------

def timegrid_amp(data, deltat=0.01):
    '''
    regrids amp onto a uniform t-z grid   (default=15min)
        data is a ProcEns most easily returned by this:

            data = get_profiles(dbname, ndays = ndays)

        returns dictionary with keys dday, lon, lat, dep, amp
    '''

    # input arguments are in 't-z' (time, vertical) coordinates
    # in the code below, 'x-y' refers to the same (abcissa, ordinal)


    # inputs
    xin = data['dday']  # Must not have masked or bad points.

    if 'amp' not in data.keys():
        return None

    if (np.diff(data['depth'],axis=1) == 0).all():
        temp_a=data['amp']
        temp_y = data['depth'][0,:]
    else:
        #regrid amp by profile to be on the finest grid in the data
        temp_y = np.arange(data['depth'].min(), data['depth'].max() + 0.01,
                           np.diff(data['depth']).min())
        temp_a = np.ma.zeros((len(xin), len(temp_y)),float)
        for iprof in range(len(xin)):
            temp_a[iprof,:] = interp1(data['depth'][iprof,:],
                                      data['amp'][iprof,:], temp_y)

    data['lon'] = unwrap_lon(data['lon'])

    # outputs

    gdata = Bunch()
    if deltat < 1:
        xout = np.arange(xin[0], xin[-1], deltat)
        gdata['dday'] = xout
        gdata['lon']  = interp1(data['dday'], data['lon'], xout)
        gdata['lat']  = interp1(data['dday'], data['lat'], xout)
    else:
        step = int(deltat)
        xout = data['dday'][::step]
        gdata['dday'] = xout
        gdata['lon']  = data['lon'][::step]
        gdata['lat']  = data['lat'][::step]


    gdata['dep']  = temp_y  #uniform in the vertical

    if 'yearbase' in data:
        gdata['yearbase'] = data['yearbase']

    gdata['amp'] = np.ma.zeros((len(xout), len(temp_y)),float)

    for bin in np.arange(len(temp_y)):
        gdata['amp'][:,bin] = interp1(data.dday, temp_a[:,bin], xout)

    return gdata


#--------------


def get_dbname(dbname=None):
    """
    Return dbname of an existing CODAS database.

    If input arg dbname is None (default), look for a db,
    assuming the current working directory is the base of
    a processing tree.

    If a valid dbname cannot be returned, raise ValueError.
    """
    if dbname is not None:
        if os.path.exists(os.path.join(dbname, 'dir.blk')):
            return dbname

        raise ValueError('dbname is not found')


    dirlistfiles = glob.glob('adcpdb/*dir.blk')
    if len(dirlistfiles) == 0:
        raise ValueError('could not guess dbname from "adcpdb/*dir.blk"')
    if len(dirlistfiles) > 1:
        raise ValueError('more than one database in directory "adcpdb"')

    dbname = dirlistfiles[0][:-7]

    fulldbpath = os.path.realpath(os.path.split(dbname)[0])
    fulldbname = os.path.join(fulldbpath, os.path.basename(dbname))
    blkfile = '%sdir.blk' % (os.path.basename(dbname))

    if not os.path.exists(os.path.join(fulldbpath, blkfile)):
        raise ValueError('full path to database has no "dir.blk" file')

    return fulldbname

#----------------------


## Should this be in navcalc? (after editing; see also ProcEns)
def calculate_fp(u,v,heading):
    '''
    calculate forward and port components of velocity
    f,p = calculate_fp(u,v,heading)
    '''
    if len(u.shape) == 1:
        u=u[:,np.newaxis]
        v=v[:,np.newaxis]
    nprofs, nbins = u.shape
    vv = np.ma.empty((nprofs, nbins, 2), dtype=float)
    vv[:,:,0] = u
    vv[:,:,1] = v
    uvr = heading_rotate(vv,90 -heading)
    p = uvr[:,:,1].squeeze()
    f = uvr[:,:,0].squeeze()
    return f, p

#--------------------------

def uhdasfile(arg1, inst=None,
                    h_align=None,
                    beamangle=None,
                    pingtype=None,
                    ibadbeam=None, # 0-based RDI beam number
                    beam_index=None, # list of 0-baed beams eg [0,1,3,2]
                    ):
    # this was written to replace get_xfraw.m
    ''' read a single raw file, find gbin data, create ocean velocities
    '''
    if inst is None:
        print('must set instrument, eg "os","nb","bb","wh"')
        sys.exit()
    if h_align is None:
        print('must set heading alignment')
        sys.exit()
    if inst=='nb' and (beamangle is None):
        print('must set beamangle')
        sys.exit()

    rawfiles=pathops.make_filelist(arg1)
    baselist = []
    for rawfile in rawfiles:
        parts = os.path.split(rawfile)
        basename = parts[-1].split('.')[0]
        baselist.append(basename)

    rawdir, instname = os.path.split(parts[0])
    uhdas_dir, junk = os.path.split(rawdir)
    gbindir = os.path.join(uhdas_dir, 'gbin', instname)

    bestlist = []
    timelist = []
    for b in baselist:
        bestlist.append(os.path.join(gbindir, 'time', '%s.best.gbin' % (b)))
        timelist.append(os.path.join(gbindir, 'time', '%s.tim.gbin' % (b)))

    best= BinfileSet(bestlist)
    tim = BinfileSet(timelist)

    ng = len(tim.dday)

    m=Multiread(rawfiles,inst, ibad=ibadbeam, beam_index=beam_index)
    if pingtype is not None:
        m.pingtype = pingtype

    data=m.read(start=-ng)
    if inst in ('bb', 'os', 'pn', 'wh'):
        beamangle = data.sysconfig['angle']

    Npings = min(len(tim.dday), len(data.dday))  ## length of gbin data
    data.utc = tim.dday[:Npings]
    data.lon = best.lon[:Npings]
    data.lat = best.lat[:Npings]
    data.heading = best.heading[:Npings]

    data.uship, data.vship = navcalc.uv_from_txy(data.utc,
                                                 data.lon, data.lat)
    dx, dy = navcalc.diffxy_from_lonlat(data.lon, data.lat)
    data.spd = np.ma.sqrt(data.uship**2 + data.vship**2)
    data.cog = np.ma.remainder(90-np.ma.arctan2(dy,dx)*180/np.pi + 360,360)

    data.beamangle = beamangle
    data.h_align = h_align

    hd = data.heading + data.h_align #- dh
    uv = heading_rotate(data.xyze[:Npings,:,:2], hd)
    bt_uv = heading_rotate(data.bt_xyze[:Npings,:2], hd)

    data.umeas = uv[:Npings,:,0]
    data.vmeas = uv[:Npings,:,1]
    data.wmeas = data.xyze[:Npings,:,2]
    data.emeas = data.xyze[:Npings,:,3]

    data.bt_umeas = bt_uv[:Npings,0]
    data.bt_vmeas = bt_uv[:Npings,0]

    data.u = data.uship[:, np.newaxis] + data.umeas
    data.v = data.vship[:, np.newaxis] + data.vmeas

    data.fmeas, data.pmeas = calculate_fp(data.umeas,
                                      data.vmeas, data.heading)

    data.fvel, data.pvel = calculate_fp(data.u, data.v, data.heading)

    return data


#---------------------------------
def vmdas(data, timefield='dday'):
    '''
        from  VmDAS data         provide variables
        ----------------        ------------------------
            ENR                  (do nothing)
            ENS                  (provide LON, LAT)
            ENX, LTA, STA,       match get_profiles(...diagnostics=True)
                                       i.e. umeas,vmeas,w,e
                                       u,v
                                       bt_u, bt_v
                                       uship, vship, cog
                                       fmeas, pmeas
                                       fvel, pvel

            **kwargs: 'timefield' -- use 'dday' or 'utc' (from nav field)
                                     ('utc' is not recommended)


     returns new "data"

    '''

    if hasattr(data, 'trans') is False:
        print('cannot determine coordinate system. returning None')
        return None

    if hasattr(data, 'nav_end_txy'):
        # add these:
        #   uship, vship, mps, cog
        #   utc, lon, lat
        if not hasattr(data, 'utc'):
            data.utc  = data.nav_end_txy[:,0]
            data.lon  = data.nav_end_txy[:,1]
            data.lat  = data.nav_end_txy[:,2]

        if not hasattr(data, 'uship'):
            if timefield == 'utc':
                dday = data.utc
            else:
                dday = data.dday

            data.uship, data.vship = navcalc.uv_from_txy(
                                          dday, data.lon, data.lat)
            dx, dy = navcalc.diffxy_from_lonlat(data.lon, data.lat)
            data.mps = np.ma.sqrt(data.uship**2 + data.vship**2)

            data.cog = np.ma.remainder(90-np.ma.arctan2(dy,dx)*180/np.pi +
                                   360,360)

        if data.trans.coordsystem == 'earth':
            # add these:
            #   umeas, vmeas, w, e
            #   fvel, pvel
            #   fmeas, pmeas

            if not hasattr(data, 'umeas'):
                data.umeas = data.vel1
                data.vmeas = data.vel2
                data.w = data.vel3
                data.e = data.vel4

            if hasattr(data, 'bt_vel') and not hasattr(data, 'bt_u'):

                data.bt_u = data.bt_vel[:,0]
                data.bt_v = data.bt_vel[:,1]


            data.u = data.uship[:, np.newaxis] + data.umeas
            data.v = data.vship[:, np.newaxis] + data.vmeas

            data.fmeas, data.pmeas = calculate_fp(data.umeas,
                                                  data.vmeas, data.heading)

            data.fvel, data.pvel = calculate_fp(data.u, data.v, data.heading)

    return data
