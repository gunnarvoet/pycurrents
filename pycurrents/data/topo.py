'''
Access the etopo1, etopo2, and Smith Sandwell topography.

- :func:`best_topo`
- :func:`nearest_depth`


'''
import os
import pickle

import numpy as np

_found = dict(best=None, ss=None, etopo=None)

class MissingDataFileError(IOError):
    pass

class Topo_grid:
    def __init__(self, nlon, nlat, lon0, lat0):
        self.nlon = nlon
        self.nlat = nlat
        self.lon0 = lon0
        self.lat0 = lat0   # Not used for SS.

class Topo_file:

    def __init__(self, nsub=None, version=None, datadir=None):
        '''
        Memory-map a binary topography data file.

        nsub is 1, 3, or 9 to select the subsampling;

        This is a base class that must be subclassed. Subclasses
        must supply the class attributes:

            topogrids
            versions
            nsubs
            dtype
            subdir
            fname_template
            fname_template_sub

        Subclasses must also override the methods:

            index_to_lon
            index_to_lat
            lon_to_index
            lat_to_index

        The main user methods of this class are "extract" and "nearest".

        '''
        if datadir is None:
            datpath = self.find_directory()
        else:
            datpath = datadir
        self.datpath = datpath
        if nsub is None:
            nsub = 1
        category = {SS_file: 'ss', Etopo_file: 'etopo'}[self.__class__]
        if version is None:
            version = _found[category]
        if version is None:
            for v in self.versions:
                fname = self.fullpath(datpath, v, nsub)
                if os.path.exists(fname):
                    version = v
                    _found[category] = version
                    break
            if version is None:
                raise MissingDataFileError('Could not find topog data file')
        else:
            fname = self.fullpath(datpath, version, nsub)
            if not os.path.exists(fname):
                raise MissingDataFileError('Could not find file: %s' % fname)
        grid = self.topogrids[version]
        self.lon0 = grid.lon0
        self.lat0 = grid.lat0
        self.version = version
        self.nsub = nsub
        nlon = grid.nlon // nsub
        self.nlat = grid.nlat // nsub
        self.fname = fname
        z = np.memmap(fname, dtype=self.dtype, mode='r',
                                shape=(self.nlat, nlon))
        # We have to handle the etopo1 "grid-centered" case,
        # identified by an odd number of longitude points, in
        # which the first and last longitude are identical.
        if nsub == 1 and grid.nlon % 2 == 1:
            self.z = z[:, :-1]
            self.nlon = grid.nlon - 1
        else:
            self.z = z
            self.nlon = nlon

        self.pts_per_degree = self.nlon / 360.0
        self.ii0 = -self.lon0 * self.pts_per_degree


    def find_directory(self):
        """
        Look for the 'topog' directory by backing up from this file location.
        """
        head, tail = os.path.split(os.path.realpath(__file__))
        while 1:
            datpath = os.path.join(head, 'topog', self.subdir)
            if os.path.isdir(datpath):
                return datpath
            if not tail:
                raise MissingDataFileError('failed to find topog directory')
            head, tail = os.path.split(head)

    def fullpath(self, datpath, version, nsub):
        if nsub in self.nsubs[1:]:
            fname = os.path.join(datpath,
                                 self.fname_template_sub % (version, nsub))
        elif nsub == 1:
            fname = os.path.join(datpath, self.fname_template % (version,))
        else:
            raise ValueError('nsub must be in %s' % self.nsubs)
        return fname

    def extract(self, xr, yr, dtype='i2', grid='center'):
        '''
        Return x, y, z for given lon and lat ranges.

        x, y will be 1-D double arrays
        z will be int16 by default; use dtype kwarg for alternatives.

        if grid is 'center' (default), z.shape = (len(y), len(x));
        if grid is 'boundary', then x and y give the cell boundaries,
        and their dimensions are one greater than those of z.
        '''
        if grid not in ['center', 'boundary']:
            raise ValueError('grid must be "center" or "boundary"')
        xr = np.asarray(xr)
        yr = np.asarray(yr)
        # Ensure the left side of the lon range is inside the
        # lon range of the topo array:
        wrapped = int((xr[0] - self.lon0) // 360)
        xr -= (wrapped * 360)
        ii = self.lon_to_index(xr)
        jj = self.lat_to_index(yr[::-1])
        nlonz = np.diff(ii)[0]   # could check to make sure they are positive
        nlatz = np.diff(jj)[0]

        if grid == 'boundary':
            ii0 = np.arange(ii[0], ii[1]+1, dtype=np.int64)
            x = self.index_to_lon(ii0, 'W')
            jj0 = np.arange(jj[0], jj[1]+1, dtype=np.int64)
            y = self.index_to_lat(jj0, 'N')
        else:
            ii0 = np.arange(ii[0], ii[1], dtype=np.int64)
            x = self.index_to_lon(ii0, 'center')
            jj0 = np.arange(jj[0], jj[1], dtype=np.int64)
            y = self.index_to_lat(jj0, 'center')
        if wrapped:
            x += (wrapped * 360)
        y=np.ascontiguousarray(y[::-1])

        z = np.zeros((nlatz, nlonz), np.int16)
        # If the right side wraps past lon0 + 360 degrees,
        # break longitudes into
        # two pieces, the first (ii(0):ii(1)) going to the highest longitude,
        # and the second (ii(2):ii(3)) going from 0 to the right limit.
        if ii[1] > self.nlon:
            ii = np.array([ii[0], self.nlon, 0, ii[1] - self.nlon],
                               dtype=np.int64)
        ii0 = np.arange(ii[0], ii[1], dtype=np.int64)
        if len(ii) == 2:      # No crossing; single read.
            z = self.z[slice(*jj), slice(*ii)] # again, here it is (y,x)
        else:                  # Crosses lon0; 2 reads per latitude
            nlonz1 = ii[1] - ii[0]
            z[:, :nlonz1] = self.z[slice(*jj), slice(ii[0], ii[1])]
            z[:, nlonz1:] = self.z[slice(*jj), slice(ii[2], ii[3])]
        z=np.array(z[::-1, :], dtype=dtype, order='C', copy=True)
        return x, y, z

    def nearest(self, x, y):
        """
        Return elevations of nearest gridpoints.

        x, y can be scalars or sequences, but must not be masked,
        and must have the same number of elements.
        """
        x = np.ravel(x)
        y = np.ravel(y)
        if len(x) != len(y):
            raise ValueError("x, y must be the same length")
        ii = self.lon_to_index(x)
        jj = self.lat_to_index(y)
        return np.asarray(self.z[jj, ii % self.nlon])

    def lon_to_index(self, x, round='closest'):
        """
        Convert from degrees longitude to integer index,
        but without wrapping; that is, the index can be negative,
        or it can equal or exceed the number of longitudes.

        Mapping to the range 0 to (nlon-1) is deliberately left
        out of this method, consistent with the design of the
        rest of the class.

        round: ['closest' | 'W' | 'E']

        """
        x = np.asarray(x) - self.lon0
        x *= self.pts_per_degree
        offset = dict(W=-1.0, closest=-0.5, E=0)[round]
        ii = np.rint(x + offset).astype(np.int64)
        return ii

    def index_to_lon(self, ii, position='center'):
        """
        Convert from index (integer or floating point) to
        degrees longitude.

        position:
            center  center of cell ii to ii+1
            W       position of boundary ii
            E       position of boundary ii+1

        """
        ii = np.asarray(ii)  - self.ii0
        _offset = dict(W=0, center=0.5, E=1)[position]
        return (ii + _offset) / self.pts_per_degree

    def lat_to_index(self, y, round='closest'):
        raise NotImplementedError("subclass must implement this")

    def index_to_lat(self, jj, position='center'):
        raise NotImplementedError("subclass must implement this")


    def make_subsets(self, nsubs = None, verbose=False):
        '''
        Generate the subsampled files using a block-median.

        nsubs is a list of odd integer subsamplings; if None,
        it will use the class or instance attribute.

        This will only need to be run when we get a new data version,
        or if we decide to use other subsamplings.
        '''
        if self.nsub != 1:
            raise RuntimeError("Make subsets only from original file.")
        if nsubs is None:
            nsubs = self.nsubs[1:]
        for nsub in nsubs:
            fname_out = self.fullpath(self.datpath, self.version, nsub)
            fout = open(fname_out, 'wb')
            if verbose:
                print("Starting %s" % fname_out)
            # temporary array for each new row:
            znew = np.empty((self.nlon//nsub,), dtype=self.dtype)
            for i0 in range(0, self.nlat, nsub):
                ii = i0//nsub
                if verbose and ii%10 == 0:
                    print("row %d of %d" % (ii, self.nlat//nsub))
                for j0 in range(0, self.nlon, nsub):
                    jj = j0//nsub
                    z = self.z[i0:(i0+nsub),j0:(j0+nsub)]
                    znew[jj] = np.median(z, axis=None)
                znew.tofile(fout)
            fout.close()
            if verbose:
                print("Finished %s" % fname_out)
            # This is very slow; it might be faster to make a
            # normal array from each horizontal strip, and operate
            # on slices of that.


class Etopo_file(Topo_file):
    """
    """
    # Note etopo2 standard is cell-centered; etopo1 is grid-centered.
    # We are doing all calculations based on cell boundaries, so we
    # we need to adjust the grid specification for etopo1.
    # (etopo1 is available in both cell and grid centered versions,
    # but the latter is the master, so that is what we will use.)
    # Also, etopo1 has values for grid longitudes -180 and +180;
    # we use a view in __init__ to clip off the latter.
    topogrids = {'2v2c': Topo_grid(10800, 5400, -180.0, 90),
                 '1_ice_g': Topo_grid(21601, 10801, -180.0 - 1.0/120,
                                                90.0 + 1.0/120),
                 '1_ice_c': Topo_grid(21600, 10800, -180.0,
                                                90.0),
                 }
    versions = ['1_ice_g', '1_ice_c', '2v2c'] # highest priority first
    nsubs = [1, 3, 9]  # could go to 21 next
    dtype = np.dtype("<i2")
    subdir = 'etopo'

    def fullpath(self, datpath, version, nsub):
        if version.startswith('1'):
            self.fname_template = 'etopo%s_i2.bin'
            self.fname_template_sub = 'etopo%s_i2_s%d.bin'
        else:
            # original files were "ETOPO", we had renamed to "etopo"
            self.fname_template = 'etopo%s_i2_lsb.bin'
            self.fname_template_sub = 'etopo%s_i2_lsb_s%d.bin'
        return Topo_file.fullpath(self, datpath, version, nsub)


    def lat_to_index(self, y, round='closest'):
        """

        round: ['closest' | 'N' | 'S']

        """
        offset = dict(N=-1, closest=-0.5, S=0)[round]
        yy = self.lat0 - np.asarray(y)
        jj = np.rint(yy * self.pts_per_degree + offset).astype(np.int64)
        np.clip(jj, 0, self.nlat-1, out=jj)
        return jj

    def index_to_lat(self, jj, position='center'):
        """

        position:
            center  center of cell jj to jj+1
            N       position of boundary jj
            S       position of boundary jj+1

        """
        jj = np.asarray(jj)
        offset = dict(N=0, center=0.5, S=1)[position]
        y = self.lat0 - (jj + offset)/self.pts_per_degree
        return y


class SS_file(Topo_file):
    topogrids = {'8.2': Topo_grid(10800, 6336, 0.0, 0.0),
               '9.1b': Topo_grid(21600, 17280, 0.0, 0.0),
               '14.1': Topo_grid(21600, 17280, 0.0, 0.0),
               '15.1': Topo_grid(21600, 17280, 0.0, 0.0),
               '18.1': Topo_grid(21600, 17280, 0.0, 0.0),
               '19.1': Topo_grid(21600, 17280, 0.0, 0.0),
               '27.1': Topo_grid(21600, 17280, 0.0, 0.0),
                 }

    # for versions >= 9, the lat range (cell boundaries) is
    # +-80.7380086.
    # 0.0 is the longitude boundary.

    versions = ['27.1', '19.1', '18.1', '15.1', '14.1', '9.1b', '8.2'] # highest priority first
    nsubs = [1, 3, 9]  # could go to 21 next
    dtype = np.dtype(">i2")
    subdir = 'sstopo'
    fname_template = 'topo_%s.img'
    fname_template_sub = 'topo_%ss%d.img'

    def lat_to_index(self, y, round='closest'):
        """

        round: ['closest' | 'N' | 'S']

        """
        y = np.asarray(y)
        tanlat = np.tan(y*np.pi/360.0)
        jr = np.array(self.nlat/2 - self.pts_per_degree*180/np.pi *
             np.log( (1+tanlat)/(1-tanlat) ))
        offset = dict(N=-1, closest=-0.5, S=0)[round]
        jj = np.rint(jr + offset).astype(np.int64)
        np.clip(jj, 0, self.nlat-1, out=jj)
        return jj

    def index_to_lat(self, jj, position='center'):
        """

        position:
            center  center of cell jj to jj+1
            N       position of boundary jj
            S       position of boundary jj+1

        """
        jj = np.asarray(jj)
        offset = dict(N=0, center=0.5, S=1)[position]
        expy = np.exp((jj+offset-self.nlat/2)*np.pi/(self.pts_per_degree*180))
        y = -2*(180/np.pi)*np.arctan( (expy-1)/(expy+1) )
        return y

def _check_SS(latrange, datadir):
    try:
        topo = SS_file(datadir=datadir)
        maxlat = topo.index_to_lat(0)
        minlat = topo.index_to_lat(topo.nlat - 1)
        del topo # Free the address space.
        if latrange[0] > minlat and latrange[1] < maxlat:
            return True
    except IOError:
        return False

def _get_best(latrange, toposource=None, datadir=None, reset_source=False):

    if reset_source is True:  #dataviewer needs this option
        _found['best'] = None

    if toposource is None:
        toposource = _found['best']
    else:
        toposource = toposource.lower()  # explicitly requested

    if toposource == 'ss' and _check_SS(latrange, datadir):
        _found['best'] = 'ss'
        return 'ss'

    topo = Etopo_file(datadir=datadir)
    del topo # Free the address space.
    _found['best'] = 'etopo'
    return 'etopo'


def best_topo(lonrange, latrange,  toposource=None,
                        nsub=None,
                        datadir=None,
                        pad=True,
                        cache='',
                        reset_source=False):
    '''
    return x,y,topo from best source, or chosen source

    toposource may be 'SS' or 'etopo'; if it is 'SS' but
        the requested latrange, including 1/2 degree pad
        if requested, exceeds the SS range, then 'etopo'
        will be used.

    nsub must be None, 1, 3, or 9; if None, the default,
        the subsampling factor will be chosen based on
        the size of the domain

    datadir is the location of the topo file(s)

    pad is True (default) to provide data from a slightly
        larger region than specified by lonrange and latrange;
        this is useful for contouring in the lonrange, latrange
        domain.  Pad will be ignored if the result would yield
        a longitude span >= 360.

    cache is a string specifying a directory.  Default is '',
        which disables caching.  Caching is likely to be worthwhile
        only when many plots are made with exactly the same
        lon and lat ranges.  When caching is enabled, it is
        left to the user to clean up by deleting unneeded
        cache files, e.g. 'Topo*.cache'.

    reset_source tells best_topo to try from scratch to determine
        the best source (for interactive sessions with extreme
        latitudes

    '''
    lonrange = np.array(lonrange, dtype=float)
    latrange = np.array(latrange, dtype=float)
    if pad:
        p = np.array([-0.5, 0.5])
        if np.diff(lonrange)[0] < 359:
            lonrange += p
        latrange += p
        latrange.clip(-90, 90)

    toposource = _get_best(latrange,
                            toposource=toposource,
                            datadir=datadir,
                            reset_source=reset_source)
    _nsub_orig = nsub

    if toposource == 'ss':
        topo = SS_file(nsub=nsub, datadir=datadir)
    else:
        topo = Etopo_file(nsub=nsub, datadir=datadir)

    pts_per_degree = topo.pts_per_degree

    if nsub is None:
        nx = int((lonrange[1] - lonrange[0])* pts_per_degree)
        ny = int((latrange[1] - latrange[0])* pts_per_degree)
        n = max(nx, ny)
        if n < 900:
            nsub = 1
        elif n < 900*3:
            nsub = 3
        else:
            nsub = 9

    if bool(cache):
        params = (('lonrange', tuple(lonrange)),
                  ('latrange', tuple(latrange)),
                  ('toposource', toposource),
                  ('nsub', nsub))
        cachefname = os.path.join(cache, "Topo_%d.cache" % abs(hash(params)))
        try:
            params, x, y, z = pickle.load(open(cachefname, 'rb'))
            return x, y, z
        except (IOError, EOFError):
            pass

    if nsub != _nsub_orig:
        del topo  # workaround for Windows mmap bug
        if toposource == 'ss':
            topo = SS_file(nsub=nsub, datadir=datadir)
        else:
            topo = Etopo_file(nsub=nsub, datadir=datadir)

    x, y, z = topo.extract(lonrange, latrange)

    if bool(cache):
        vartup = (params, x, y, z)
        pickle.dump(vartup, open(cachefname, 'wb'), -1)

    return x, y, z


def nearest_depth(x, y, toposource=None, datadir=None):
    """
    Return nearest depth from etopo (default) or SS dataset.

    x, y must be scalars, or sequences of the same length.

    If any value of y is outside the SS range, then the etopo
    data will be used for all points regardless of the requested
    *toposource*.
    """
    x = np.asarray(x)
    y = np.asarray(y)

    toposource = _get_best([y.min(), y.max()],
                            toposource=toposource,
                            datadir=datadir)

    if toposource == 'ss':
        topo = SS_file(datadir=datadir)
    else:
        topo = Etopo_file(datadir=datadir)

    return topo.nearest(x, y)
