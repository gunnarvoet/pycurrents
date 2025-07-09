
"""
Access drifter data from the GDP Drifter DAC.

http://www.aoml.noaa.gov/phod/dac/dacdata.html

ftp://ftp.aoml.noaa.gov/phod/pub/buoydata/

The data typically come as two or more gzipped ascii files:

buoydata_1_5000.dat-gz
buoydata_5001_sep09.dat-gz

The first of these is not expected to change, since all the drifters
in the first group are dead.  The second is updated periodically,
with corresponding changes to the filename segment before the extension.


These files are unwieldy, so we first read them and reformat them
into a binary file (e.g., sep09.bdat) and a directory file (sep09.dir).
See :func:`reformat`; example usage is::

    infiles = ['buoydata_1_5000.dat-gz', 'buoydata_5001_sep09.dat-gz']
    reformat(infiles, 'sep09')

where "sep09" will be changed to whatever version you have downloaded.

Once this has been done, we can work with the data using
:class:`Drifters`.


"""

import gzip
import pickle
import struct
import os
import string  # for digits
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.collections import LineCollection, CircleCollection

from matplotlib.dates import date2num
from pycurrents.codas import to_date


# dtype for the reformatted drifter data
dt_dat = np.dtype([('ID', 'i4'), ('d2000', 'f4'),
                   ('x', 'f4'), ('y', 'f4'),
                   ('u', 'f4'), ('v', 'f4'),
                   #('spd', 'f4'),  # instead, calculate
                   ('T', 'f4'),
                   ('varx', 'f4'), ('vary', 'f4'),
                   ('varT', 'f4')])

# dtype for the directory
dt_dir = np.dtype([('ID', 'i4'),
                  ('i0', 'i4'), ('i1', 'i4'),
                  ('start', 'f4'), ('end', 'f4'),
                  ('W', 'f4'), ('E', 'f4'),
                  ('S', 'f4'), ('N', 'f4')])



t2000 = date2num(datetime(2000, 1, 1))

def daynum(y, m, d):
    """
    Convert the year, month, and day fields in the *.dat file
    to decimal day with yearbase 2000.
    """
    di = int(d)
    h = int(round((d - di)*24))
    t = date2num(datetime(y, m, di, h))
    return t - t2000

def reformat(infilelist, outfilebase):
    """
    Reformat as a binary array a set of compressed ascii
    drifter data files from the drifter DAC.
    Three additional results are saved as pickle files, the
    most important being *ID_indices.pkl.

    outfilebase is a name prepended to the output file names.

    Example:

        infiles = ['buoydata_1_5000.dat-gz', 'buoydata_5001_sep09.dat-gz']
        reformat(infiles, 'sep09')

    Note: instead of making an ndarray and saving it, we are
    making a binary file corresponding to the data of an ndarray,
    which will be accessed in Drifters using an mmap.  This is
    efficient for generating the file--only a single pass is
    required, with minimal memory--and for accessing
    the contents of the file.

    """
    binaryname = outfilebase + '.bdat'
    bf = open(binaryname, 'wb')
    old_id = 0
    ids = {}
    measurements = {}
    index_list = []
    chunks = 0
    iline = 0
    df = None
    while True:  #chunks < 100:
        if df is None:
            if not infilelist:
                break    # Finished with the whole loop.
            df = gzip.open(infilelist[0])
            del(infilelist[0])
        # Recently, AOML added some header lines...
        while True:
            line = df.readline().decode('ascii')  # EOF is empty string
            if not line:
                df.close()
                df = None  # flag: try the next file
                break
            line = line.lstrip()
            if line and line[0] in string.digits:
                break

        if df is None:
            continue   # Try the next file

        (ID, MM, DD, YY, LAT, LON, TEMP, VE, VN, SPD,
                            VARLAT, VARLON, VARTEMP) = line.split()

        if ID != old_id:
            chunks += 1
            print(chunks, ID)
            count = ids.get(ID, 0)
            ids[ID] = count + 1
            old_id = ID
            index_list.append((int(ID), iline))
        else:
            count = measurements.get(ID, 1)
            measurements[ID] = count + 1
        s = struct.pack('=i9f', int(ID), daynum(int(YY), int(MM), float(DD)),
                                 float(LON), float(LAT),
                                 float(VE)/100.0, float(VN)/100.0,
                                 float(TEMP),
                                 float(VARLON), float(VARLAT),
                                 float(VARTEMP))
        bf.write(s)
        iline += 1

    bf.close()

    for key, value in ids.items():
        print(key, value)

    pickle.dump(ids, open(outfilebase + 'ids.pkl', 'wb'))
    pickle.dump(measurements, open(outfilebase + 'measurements.pkl', 'wb'))
    pickle.dump(index_list, open(outfilebase + 'ID_indices.pkl', 'wb'))

    make_directory(outfilebase)




def lonrange(x):
    """
    Given a set of longitudes, return the west and east limits.

    Inputs and outputs are given in the 0-360 range.

    This will fail for drifters that cross both 0 and 180, which
    may be a problem in the Southern Ocean.
    """
    xmin = x.min()
    xmax = x.max()
    if xmin >= 180 or xmax < 180:
        # simplest case: all points are 180 to 360, or 0-180
        return xmin, xmax

    # More complex: points on both sides of dateline.
    x0 = np.compress(x < 180, x)    # East longitudes.
    x1 = np.compress(x >= 180, x)   # West longitudes
    x00 = x0.min()
    x01 = x0.max()
    x10 = x1.min()
    x11 = x1.max()
    if (x10 - x01) < (x00 + 360 - x11):
        # Crossing the Dateline:
        return x00, x11
    else:
        # Crossing the Prime Meridian:
        return x10, x01

def make_directory(outfilebase):
    """
    Write a binary file serving as a directory to the drifters.

    This is called by reformat(), so normally it will not need
    to be called manually.

    This should be changed to save the array directly using np.save.

    """
    binaryname = outfilebase + '.bdat'
    dirname = outfilebase + '.dir'
    drift = np.memmap(binaryname, dtype=dt_dat, mode='r')
    indices = pickle.load(open(outfilebase + 'ID_indices.pkl', 'rb'))

    ID_ii = np.array(indices)
    i0a = ID_ii[:,1]
    i1a = np.array(i0a, copy=True)
    i1a[:-1] = i0a[1:]
    i1a[-1] = -1

    adir = np.memmap(dirname, dtype=dt_dir, mode='w+',
                        shape=i0a.shape)
    adir['ID'] = ID_ii[:,0]
    adir['i0'] = i0a
    adir['i1'] = i1a


    for i, i0 in enumerate(i0a):
        d = drift[i0:i1a[i]]
        adir['start'][i] = d['d2000'][0]
        adir['end'][i] = d['d2000'][-1]
        x = np.compress(d['x'] < 360, d['x'])
        y = np.compress(d['y'] < 90, d['y'])
        adir['S'][i] = y.min()
        adir['N'][i] = y.max()
        adir['W'][i], adir['E'][i] = lonrange(x)

# Temporary location:
# from custom_cmap.py example, slightly modified:
cdict3 = {'red':  ((0.0, 0.0, 0.0),
                   (0.25,0.0, 0.0),
                   (0.5, 0.85, 1.0),
                   (0.75,1.0, 1.0),
                   (1.0, 0.4, 1.0)),

         'green': ((0.0, 0.0, 0.0),
                   (0.25,0.0, 0.0),
                   (0.5, 0.95, 0.95),
                   (0.75,0.0, 0.0),
                   (1.0, 0.0, 0.0)),

         'blue':  ((0.0, 0.0, 0.4),
                   (0.25,1.0, 1.0),
                   (0.5, 1.0, 0.85),
                   (0.75,0.0, 0.0),
                   (1.0, 0.0, 0.0))
        }

plt.register_cmap(name='BlueRed3', data=cdict3)



class Drifters:
    """
    Access and plot a drifter database that has been reformatted
    using :func:`format`.

    Use :meth:`select` after initializing to set *xlim* and *ylim*.

    Attributes *map_kw*, *topo_kw*, and *grid_kw* are dictionaries
    that may be modified to provide keyword arguments to the call
    to :func:`pycurrents.plot.maptools.mapper`, and to
    :meth:`pycurrents.plot.maptools.grid` and
    :meth:`pycurrents.plot.maptools.topo`.
    The first is initialized to enable caching in the current directory;
    the other two are initially empty.
    """
    def __init__(self, filebase):
        """
        Initialize a memory map for the reformatted binary drifter data.
        *filebase* is reformatted filename base, e.g. 'sep09'.
        If necessary, include the directory.
        """
        self.filebase = filebase
        dirname = filebase + '.dir'
        datname = filebase + '.bdat'
        self.dir = np.fromfile(dirname, dtype=dt_dir)
        self.dat = np.memmap(datname, dt_dat )
        self._iselect = None
        self.xlim = None
        self.ylim = None
        self.map_kw = dict(cache='./')
        self.topo_kw = {}
        self.grid_kw = {}

    def select(self, xlim, ylim, tlim=None):
        """
        Select a subset of the data based on *xlim*, *ylim*, and *tlim*.
        All times are handled as decimal days relative to yearbase 2000.
        *xlim* and *ylim* must be specified; *tlim* is optional.
        Most subsequent data extraction methods also include a *tlim*
        kwarg.
        """
        self.ylim = ylim
        ddir = self.dir
        ys, yn = ylim
        iselect = (ddir['S'] < yn) & (ddir['N'] > ys)
        if tlim is not None:
            tfirst, tlast = tlim
            iselect &= (ddir['start'] < tlast) & (ddir['end'] > tfirst)
        # Southern Ocean: use a latitude criterion only
        if ys < -40:
            self._iselect = iselect
            return

        xw, xe = xlim
        if xw < 0:
            xw += 360
            xe += 360
        if xe < xw:
            xe += 360
        self.xlim = xw, xe

        dxw = ddir['W'].copy()
        dxe = ddir['E'].copy()
        dxe[dxe < dxw] += 360
        iselect &= ((dxe > xw) & (dxw < xe))
        self._iselect = iselect

    def tracks(self):
        """
        Returns a generator of data slices, one per selected track.

        Normally, select() will have been called first.

        """
        if self._iselect is None:
            ddir = self.dir
        else:
            ddir = self.dir[self._iselect]
        for line in ddir:
            yield self.dat[line['i0']:line['i1']]

    def subtracks(self, tlim=None, mask_end=False):
        """
        Returns a list of track subsections based on tlim.
        Each is a masked array, masked where latitude is invalid.
        (Actual flag value is 999.99.)
        """
        _tracks = []
        if tlim is None:
            tlim = -10000, 10000
        for tr in self.tracks():
            mask = (tr['d2000'] >= tlim[0]) & (tr['d2000'] < tlim[1])
            tr = tr[mask]
            # It looks like there is no point in masking out-of-range
            # values, since subsequent steps (plotting, etc.) can
            # often handle that more efficiently.
            #mask &= (tr['y'] >= self.ylim[0]) & (tr['y'] <= self.ylim[1])
            #if self.xlim[1] > 360:
            #    tr['x'][tr['x'] < self.xlim[0]] += 360
            #mask = (tr['x'] >= self.xlim[0]) & (tr['x'] <= self.xlim[1])
            #_tracks.append(np.ma.array(tr, mask=~mask))
            mbad = tr['y'] > 90
            if len(mbad) < 2:
                continue
            if mask_end:
                mbad[-1] = True
            _tracks.append(np.ma.array(tr, mask=mbad))
        return _tracks

    def basemap(self, **kw):
        from pycurrents.plot.maptools import mapper
        kw.update(self.map_kw)
        return mapper(self.xlim, self.ylim, **kw)

    def spag_lines(self, tlim=None, ax=None,
                   map=None,
                   marker_kw=None,
                   colors=None,
                   **kw):
        """
        Spaghetti plot all tracks (possibly subsetted by *tlim*),
        cycling through primary and secondary colors by default.
        *colors* may also be a colorspec or sequence of them.
        """
        if ax is None:
            ax = plt.gca()
        if colors is None:
            colors=['r','g','b','c','y','m','k']
        if map is None:
            m = self.basemap(resolution='i', ax=ax)
        else:
            m = map
        segs = []
        for i, tr in enumerate(self.subtracks(tlim)):
            xym = np.ma.zeros((len(tr), 2))
            xym[:,0], xym[:,1] = m(tr['x'], tr['y'])
            segs.append(xym)
            color = colors[i % len(colors)]
            if marker_kw is not None:
                ax.plot(*xym[-1], mfc=color, mec=color, **marker_kw)
        ax.add_collection(LineCollection(segs,
                                colors=colors, **kw))
        if map is None:
            m.topo(**self.topo_kw)
            m.grid(**self.grid_kw)
        return m

    def spag_dots(self, tlim=None, months=None, ax=None,
                    cmap=None, clim=None, c='u', size=10,
                    age=None, t0=None):
        """
        plot tracks as dots, colored based on the value of *c*.

        *c* can be: 'u', 'v', 'spd', 'T'
        *tlim* is used to subset by time.
        *months* is a list of 1-based month numbers; e.g. [1,2,3]
                restricts the plot to data from Jan, Feb, Mar.

        """
        if c == 'T':
            if clim is None:
                clim = [0, 30]
            if cmap is None:
                cmap = plt.get_cmap('jet')
        elif c == 'spd':
            if clim is None:
                clim = [0, 1]
            if cmap is None:
                cmap = plt.get_cmap('YlOrRd')
        else:
            if clim is None:
                clim = [-1, 1]
            if cmap is None:
                cmap = plt.get_cmap('BlueRed3')
        norm = mcolors.Normalize(*clim)
        if ax is None:
            ax = plt.gca()
        m = self.basemap(resolution='i', ax=ax)
        tracks = self.subtracks(tlim, mask_end=True)
        if len(tracks) == 0:
            points = np.ma.array([], dtype=dt_dat)
        else:
            points = np.ma.concatenate(tracks)
        if months is not None:
            ymds = to_date(2000, points['d2000'])
            mselect = np.zeros((len(points),), bool)
            for mon in months:
                mselect |= (ymds[:,1] == mon)
            points = points[mselect]
            # Here we have thrown away masked points, so we are
            # committed to plotting points, not lines.
        xym = np.ma.zeros((len(points), 2))
        xym[:,0], xym[:,1] = m(points['x'], points['y'])
        if age is None:
            sz = [size]
        else:
            dday = points['d2000']
            sz = size * ((dday - t0 + age)/age)**2
        col = CircleCollection(sz, offsets=xym,
                    edgecolors='none',
                    norm=norm,
                    cmap=cmap,
                    transOffset=ax.transData,
                    zorder=2.5)
        if c == 'spd':
            carray = np.ma.abs(points['u'] + 1j*points['v'])
        else:
            carray = points[c]
        if c == 'T':
            carray = np.ma.masked_greater(carray, 900)
            cmap.set_bad('w')
        else:
            carray = np.ma.masked_greater(carray, 9)
        col.set_array(carray)
        ax.add_collection(col)

        if c == 'spd':
            extend = 'max'
        else:
            extend = 'both'
        cbar = ax.figure.colorbar(col, ax=ax, orientation='horizontal',
                                       shrink=0.8,
                                       pad=0.02,
                                       fraction=0.03,
                                       aspect=30,
                                       extend=extend)
        ld = dict(u='U (m/s)', v='V (m/s)', spd='Spd (m/s)',
                  T='Temperature')
        cbar.set_label(ld[c])
        m.topo(**self.topo_kw)
        bbax = ax.get_position()
        bbcb = cbar.ax.get_position()
        xshift = np.mean(bbax.intervalx - bbcb.intervalx)
        cbar.ax.set_position(bbcb.translated(xshift, 0))

        m.grid(**self.grid_kw)
        return m, cbar



    def spag_seasons(self, tlim=None):
        from matplotlib.pyplot import subplots
        from pycurrents.codas import to_date
        tracks = self.subtracks(tlim)
        ymds = []
        for track in tracks:
            ymds.append(to_date(2000, track['d2000']))

        fig, ax = subplots(2,2)
        for i, a in enumerate(ax.flat):
            m = self.basemap(ax=a, resolution='i')
            m0 = 1 + 3*i
            m1 = m0 + 2
            segs = []
            for tr, ymd in zip(tracks, ymds):
                goodmask = (ymd[:,1] >= m0) & (ymd[:,1] <= m1)
                if goodmask.any():
                    x = np.ma.array(tr['x'], mask=~goodmask)
                    y = np.ma.array(tr['y'], mask=~goodmask)
                    xym = np.ma.zeros((len(tr), 2))
                    xym[:,0], xym[:,1] = m(x, y)
                    segs.append(xym)
                    #a.plot(*m(x,y))
            a.add_collection(LineCollection(segs,
                                    colors=['r','g','b','c','y','m','k']))
            a.set_title('Months %d-%d' % (m0, m1))
            m.topo(**self.topo_kw)
            m.grid(**self.grid_kw)
        return fig

# Surely we should be importing this from somewhere...
monthnames = ['January', 'February', 'March', 'April', 'May',
               'June', 'July', 'August', 'September', 'October',
               'November', 'December']

def monthly_summary(filebase, outdir, xlim, ylim, T_clim,
                    max_spd=1,
                    size=5,
                    format='png'):
    """
    Quick plot of monthly tracks colored by u, v, spd, T.

    Each plot is saved to a file; a single figure is created
    at the start and closed at the end.

    This may be used as-is, or it may be copied and modified
    as needed.
    """
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    D = Drifters(filebase)
    D.select(xlim, ylim)
    fig = plt.figure()
    fig.subplots_adjust(top=0.97, bottom=0.085, left=0.09, right=0.92)
    for mon in range(1,13):
        for c in ['u', 'v', 'spd', 'T']:
            if c == 'T':
                clim = T_clim
            elif c == 'spd':
                clim = [0, max_spd]
            else:
                clim = [-max_spd, max_spd]
            ax = fig.add_subplot(1, 1, 1)
            m, cbar = D.spag_dots(months=[mon], ax=ax, c=c, clim=clim,
                                  size=size)
            ax.set_title(monthnames[mon-1])
            outfile = 'monthly_%s_m%02d.%s' % (c, mon, format)
            fig.savefig(os.path.join(outdir, outfile))
            # Using bbox_inches='tight' doesn't work here at present;
            # it chops off the latitude tick labels.
            print("saved %s" % outfile)
            fig.clf()
    plt.close(fig)

def animation_T(filebase, outdir, xlim, ylim, T_clim,
                tlim=None,
                cmap=None,
                line_kw=None,
                days=15,
                interval=2):
    """
    Quick animation, coloring by temperature.

    *days* is the worm length
    *interval* is the time in days between frames.

    """
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    D = Drifters(filebase)
    D.select(xlim, ylim, tlim)
    D.grid_kw['ny'] = 4  # nx, ny default is 6
    tracks = D.subtracks()
    points = np.ma.concatenate(tracks)
    if tlim is None:
        t0 = points['d2000'].min()
        t1 = points['d2000'].max()
    else:
        t0, t1 = tlim
    print("time range: %f to %f" % (t0, t1))
    fig = plt.figure(figsize=(8, 6))
    fig.subplots_adjust(top=0.97, bottom=0.1, left=0.09, right=0.92)
    for t in np.arange(t0, t1+0.3, interval):
        ymd = to_date(2000, t)
        tlim = [t - days - 0.1, t+0.1]
        ax = fig.add_subplot(1, 1, 1)
        c = 'T'
        m, cbar = D.spag_dots(tlim=tlim, ax=ax, c=c, clim=T_clim,
                                cmap=cmap,
                                size=20,
                                age=days*1.5,
                                t0=t)
        if line_kw is not None:
            D.spag_lines(tlim=tlim, ax=ax, map=m, **line_kw)

        ax.set_title("%4d %02d %02d  %02d" % tuple(ymd[:4]))
        ax.set_title(f"{days}-day tracks", loc='left')
        outfile = '%s_%04d%02d%02d_%02d.png' % (c, ymd[0], ymd[1],
                                                       ymd[2],
                                                       ymd[3])
        fig.savefig(os.path.join(outdir, outfile), dpi=100)
        # Using bbox_inches='tight' doesn't work here at present;
        # it chops off the latitude tick labels.
        print("saved %s" % outfile)
        fig.clf()
    plt.close(fig)
