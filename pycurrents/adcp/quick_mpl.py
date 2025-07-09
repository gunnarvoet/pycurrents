'''
This file contains methods used in the q_mpl processor inside quick_adcp.py
Methods with Numpy only are in quick_npy.py
'''

# for debugging
#from IPython.Shell import IPShellEmbed
#ipshell = IPShellEmbed()
##            ipshell()

import os
import time
import logging
import numpy as np
from numpy import ma
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter, MaxNLocator

from pycurrents.num import stats, grid
from pycurrents.plot.mpltools import shorten_ax
from pycurrents.plot.maptools import LatFormatter, LonFormatter
from pycurrents.data.navcalc import unwrap_lon, wrap
from pycurrents.num.nptools import rangeslice
from pycurrents.num.nptools import loadtxt_
from pycurrents.system.misc import ScripterBase
from pycurrents.system.misc import guess_comment
from pycurrents.adcp.plot_uvship import plot_uvship


# Standard logging
_log = logging.getLogger(__name__)

_pre3_9 = matplotlib.__version_info__ < (3, 9)

def _close(fig):
    _log.debug(f"matplot lib version is {matplotlib.__version_info__}")
    if  not _pre3_9 and matplotlib.get_backend() not in matplotlib.backends.backend_registry.list_builtin(matplotlib.backends.BackendFilter.INTERACTIVE):
        plt.close(fig)
        _log.debug(f'closing {fig.number}')
    elif _pre3_9 and matplotlib.get_backend() not in matplotlib.rcsetup.interactive_bk:
        plt.close(fig)
        _log.debug(f'closing {fig.number}')
    else:
        _log.debug(f'not closing {fig.number}')

#############################################################################

_runstr = '''
#!/usr/bin/env python

## written by quick_mplplots.py -- edit as needed:

## cruiseid      is '${cruiseid}'
## dbname        is '${dbname}'
## proc_yearbase is ${proc_yearbase}
## printformats   is '${printformats}'

import matplotlib.pyplot as plt


'''

class Scripter(ScripterBase):
    script_head = _runstr
    script_tail = "plt.show()"


#============= define classes =====================
##  (a)  Tempplot
##  (b)  Navplot
##  (c)  Refplot
##  (d)  Hcorrplot
##  (e)  Btplot
##  (f)  Wtplot



##  (a)  ====================   Tempplot =======================


_tempstr = '''
from pycurrents.adcp.quick_mpl import Tempplot

PT = Tempplot()
PT(temp_filename='${temp_filename}',
   titlestr = '${cruiseid}: Transducer Temperature',
   proc_yearbase = ${proc_yearbase},
   printformats = '${printformats}',
   ddrange = None)
'''


class Tempplot(Scripter):
    """
    Mandatory kwargs (supply when initializing):
        temp_filename or dbname
        cruiseid
        proc_yearbase

    Optional kwargs (supply when initializing or when calling):
        titlestr
        outfilebase
        printformats
        dpi
        ddrange

    """
    script_body = _tempstr

    defaultparams = {'temp_filename': None,
                     'proc_yearbase': None,
                     'titlestr': None,
                     'dbname': None,
                     'cruiseid': 'ADCP',
                     'outfilebase': 'temp_plot',
                     'printformats': 'pdf',
                     'dpi': 100,
                     'ddrange': None}

    def process_params(self):
        p = self.params
        if p['proc_yearbase'] is None:
            raise ValueError('proc_yearbase must be set')
        if p['temp_filename'] is None:
            try:
                p['temp_filename'] = p['dbname'] + '.tem'
            except KeyError:
                raise ValueError('either temp_filename or dbname is required')
        fn = p['temp_filename']
        if fn is None or not os.path.exists(fn):
            _log.warning("Temperature file named %s does not exist."%(fn,))
        # could do additional validation here, but may not need to.
        if p['titlestr'] is None:
            p['titlestr'] = '%(cruiseid)s transducer temperature' % p

    def __call__(self, **kw):
        """
        See defaultparams for kwargs.
        """
        Scripter.__call__(self, **kw)

        self.get_data()
        if len(self.data) == 0:
            _log.warning('No temperature data found')
            return
        fig = self.plot_temp()
        if self.printformats:
            for pf in self.printformats.split(':'):
                fig.savefig(self.outfilebase+'.'+pf, dpi=self.dpi)
        _close(fig)


    def get_data(self):

        if self.temp_filename is None or not os.path.exists(self.temp_filename):
            self.data = []
        else:
            names = ['dday', 'mean_temp', 'last_temp', 'mean_sspd']
            dtype = np.dtype({'names':names, 'formats': [np.float64]*4})
            comment = guess_comment(self.temp_filename)
            tempdat = loadtxt_(self.temp_filename, comments=comment, dtype=dtype, ndmin=1)
            sl = rangeslice(tempdat['dday'], self.ddrange)
            self.data = tempdat[sl]

    def plot_temp(self):

        xlabelstr = 'Decimal Day, %d' % (self.proc_yearbase)

        _log.debug('plotting %d points\n', len(self.data['dday']))

        fig = plt.figure()

        # subplot 1
        self.ax1 = fig.add_subplot(211)
        self.ax2 = fig.add_subplot(212, sharex=self.ax1)

        dday = self.data['dday']
        self.ax1.plot(dday, self.data['mean_temp'], 'g.')
        self.ax1.set_title(self.titlestr)

        self.ax1.set_ylabel(u'Mean T (\N{DEGREE Sign}C)')

        # subplot 2
        delT = self.data['mean_temp'] - self.data['last_temp']
        self.ax2.plot(dday, delT, 'r.')

        self.ax2.text(.03, 0.94, 'mean T - last T',
                       verticalalignment='top',
                       horizontalalignment='left',
                       transform = self.ax2.transAxes)
        self.ax2.set_ylabel(u'T diff (\N{DEGREE Sign}C)')

        self.ax2.set_xlabel(xlabelstr)

        self.ax1.set_xlim(dday[0], dday[-1])

        for tl in self.ax1.get_xticklabels():
            tl.set_visible(False)

        return fig




##  (a)  ====================   uvship  =======================


_uvshipstr = '''
from pycurrents.adcp.quick_mpl import UVShipPlot

PUV = UVShipPlot()
PUV(uvshipfile='${uvshipfile}',
   titlestr = '${cruiseid}: uvship diffs',
   proc_yearbase = ${proc_yearbase},
   printformats = '${printformats}',
   ddrange = None)
'''


class UVShipPlot(Scripter):
    """
    Mandatory kwargs (supply when initializing):
        uvshipfile
        cruiseid
        proc_yearbase

    Optional kwargs (supply when initializing or when calling):
        titlestr
        outfilebase
        printformats
        dpi


    """
    script_body = _uvshipstr

    defaultparams = {'dbname': None,
                     'uvshipfile':None,
                     'proc_yearbase': None,
                     'titlestr': None,
                     'cruiseid': 'ADCP',
                     'outfilebase': 'uvship_plot',
                     'printformats': 'pdf',
                     'dpi': 100,
                     'ddrange': None}

    def process_params(self):
        p = self.params
        if p['proc_yearbase'] is None:
            raise ValueError('proc_yearbase must be set')

        if p['uvshipfile'] is None:
            try:
                p['uvshipfile'] = '%s.uvship' % (p['dbname'])
            except KeyError:
                raise ValueError('either uvshipfile or dbname is required')
        fn = p['uvshipfile']
        if fn is None or not os.path.exists(fn):
            _log.info('uvship file does not exist')
        # could do additional validation here, but may not need to.
        if p['titlestr'] is None:
            p['titlestr'] = '%(cruiseid)s ship speed diffs' % p

    def __call__(self, **kw):
        """
        See defaultparams for kwargs.
        """
        Scripter.__call__(self, **kw)

        if os.path.exists(self.uvshipfile):
            try:
                fig = plot_uvship(self.uvshipfile)
                if self.printformats:
                    for pf in self.printformats.split(':'):
                        fig.savefig(self.outfilebase+'.'+pf, dpi=self.dpi)
                    _close(fig)
            except Exception as exception:
                _log.debug(f"could not make uvplot with exception : {exception}")


##  (a)  ====================   Npings  =======================


_npingstr = '''
from pycurrents.adcp.quick_mpl import NPingplot

PT = NPingplot()
PT(nping_filename='${nping_filename}',
   titlestr = '${cruiseid}: Pings Per Ensemble',
   proc_yearbase = ${proc_yearbase},
   printformats = '${printformats}',
   ddrange = None)
'''


class NPingplot(Scripter):
    """
    Mandatory kwargs (supply when initializing):
        nping_filename or dbname
        cruiseid
        proc_yearbase

    Optional kwargs (supply when initializing or when calling):
        titlestr
        outfilebase
        printformats
        dpi
        ddrange

    """
    script_body = _npingstr

    defaultparams = {'nping_filename': None,
                     'proc_yearbase': None,
                     'titlestr': None,
                     'dbname': None,
                     'cruiseid': 'ADCP',
                     'outfilebase': 'nping_plot',
                     'printformats': 'pdf',
                     'dpi': 100,
                     'ddrange': None}

    def process_params(self):
        p = self.params
        if p['proc_yearbase'] is None:
            raise ValueError('proc_yearbase must be set')
        if p['nping_filename'] is None:
            try:
                p['nping_filename'] = p['dbname'] + '_npings.txt'
            except KeyError:
                raise ValueError('either nping_filename or dbname is required')
        self.fn = p['nping_filename']
        if not os.path.exists(self.fn):
            self.fn = None
        if self.fn is None :
            _log.info("not making plot: NPings")
        # could do additional validation here, but may not need to.
        if p['titlestr'] is None:
            p['titlestr'] = '%(cruiseid)s  ping statistics' % p

    def __call__(self, **kw):
        """
        See defaultparams for kwargs.
        """
        Scripter.__call__(self, **kw)

        self.get_data()
        if len(self.data) == 0:
            _log.info('no NPing data')
            return
        fig = self.plot_nping()
        if self.printformats:
            for pf in self.printformats.split(':'):
                fig.savefig(self.outfilebase+'.'+pf, dpi=self.dpi)
        _close(fig)


    def get_data(self):
        if self.fn is None:
            self.data = []
        else:
            names = ['dday', 'npings', 'seconds']
            dtype = np.dtype({'names':names, 'formats': [np.float64]*4})
            comment = guess_comment(self.nping_filename)
            npingdat = loadtxt_(self.nping_filename, comments=comment, dtype=dtype, ndmin=1)
            sl = rangeslice(npingdat['dday'], self.ddrange)
            self.data = npingdat[sl]

    def plot_nping(self):

        xlabelstr = 'Decimal Day, %d' % (self.proc_yearbase)

        _log.debug('plotting %d points\n', len(self.data['dday']))

        fig = plt.figure()

        # subplot 1
        self.ax1 = fig.add_subplot(111)

        dday = self.data['dday']
        self.ax1.plot(dday, self.data['npings'], 'b.')

        self.ax1.set_title(self.titlestr)
        self.ax1.set_xlabel(xlabelstr)

        # subplot 2
        self.ax1.plot(dday, self.data['seconds'], 'k.')

        self.ax1.text(.03, 0.94, 'seconds per ensemble',
                       verticalalignment='top',
                       horizontalalignment='left',
                       transform = self.ax1.transAxes)
        self.ax1.text(.03, 0.80, 'pings per ensemble',
                       verticalalignment='top',
                       horizontalalignment='left',
                       transform = self.ax1.transAxes,
                       color='blue')

        self.ax1.set_xlim(dday[0], dday[-1])
        yl = self.ax1.get_ylim()
        self.ax1.set_ylim([0.0, 1.05*yl[1]])

        return fig


##  (b)  ====================   Navplot =======================

_navstr = '''

from pycurrents.adcp.quick_mpl import Navplot

PN = Navplot()
PN(dbname = '${dbname}',
   titlestr = '${cruiseid}: Ship Positions',
   proc_yearbase = ${proc_yearbase},
   fixfile = '${fixfile}',
   printformats = '${printformats}',
   ddrange = None)
'''

class Navplot(Scripter):
    """
    Mandatory kwargs:
        dbname
        cruiseid
        proc_yearbase
        fixfile
    Optional kwargs:
        titlestr
        printformats
        dpi
        ddrange

    """
    script_body = _navstr

    defaultparams = {'dbname' : None,
                     'proc_yearbase': None,
                     'titlestr': None,
                     'cruiseid': 'ADCP',
                     'fixfile' : None,
                     'outfilebase': 'nav_plot',
                     'printformats': 'pdf',
                     'dpi': 100,
                     'ddrange': None}

    def process_params(self):
        p = self.params
        if p['proc_yearbase'] is None:
            raise ValueError('proc_yearbase must be set')
        if p['fixfile'] is None:
            try:
                p['fixfile'] = p['dbname'] + '.gps'
            except KeyError:
                raise ValueError('either fixfile or dbname is required')
        fn = p['fixfile']
        if fn is None or not os.path.exists(fn):
            raise ValueError("GPS file named %s does not exist."%(fn,))
        if p['titlestr'] is None:
            p['titlestr'] = '%(cruiseid)s cruise track' % p

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)

        self.get_data()
        if len(self.data) == 0:
            _log.warning('No nav plot data found')
            return
        fig = self.plot_nav()

        if self.printformats:
            for pf in self.printformats.split(':'):
                fig.savefig(self.outfilebase+'.'+pf, dpi=self.dpi)
        _close(fig)


    def get_data(self):

        names = ['dday', 'lon', 'lat']
        dtype = np.dtype({'names':names, 'formats': [np.float64]*3})
        comment = guess_comment(self.fixfile)
        nav = loadtxt_(self.fixfile, comments=comment, dtype=dtype, ndmin=1)

        sl = rangeslice(nav['dday'], self.ddrange)
        self.data = nav[sl]

    def plot_nav(self):
        fig = plt.figure()

        # subplot 1
        ax1 = fig.add_subplot(211)
        ax2 = ax1.twinx()
        ax3 = fig.add_subplot(212)

        dday = self.data['dday']
        lon = unwrap_lon(self.data['lon'])
        lat = self.data['lat']

        ax1.plot(dday, lon, 'b.')
        ax2.plot(dday, lat, 'g.')
        ax1.yaxis.set_major_formatter(LonFormatter())
        ax2.yaxis.set_major_formatter(LatFormatter())

        ax1.set_xlim(dday[0], dday[-1])
        ax1.set_title(self.titlestr)
        ax1.grid(True)
        for tl in ax1.yaxis.get_ticklabels():
            tl.set_color('b')
        for tl in ax2.yaxis.get_ticklabels():
            tl.set_color('g')


        ## subplot 2

        ax3.plot(self.data['lon'], self.data['lat'],'.')
        ax3.xaxis.set_major_formatter(LonFormatter())
        ax3.yaxis.set_major_formatter(LatFormatter())
        ax3.grid(True)
        ax3.set_aspect('equal', adjustable='datalim') # mercatorize later
        # Or use a real map.
        # Add symbols for start and end.
        return fig

##  (c)  ====================   Refplot =======================

_reflstr = '''
from pycurrents.adcp.quick_mpl import Refplot

## other parameters that can be chosen
## name         default
## ----         -------
## outfilebase  'reflayer',
## printformats 'pdf',
## dpi           100,
## days_per_page 2.0,
## ddrange       [min, max]
## max_gap_ratio 0.05,
## min_speed     1.0,
## max_speed     5.0,
## ylim          [-1., 1.]


PT = Refplot()
PT(sm_filename='${dbname}.sm',
   ref_filename='${dbname}.ref',
    cruiseid = '${cruiseid}',
    proc_yearbase = ${proc_yearbase},
    printformats = '${printformats}',
    ddrange = 'all')
'''

class Refplot(Scripter):
    """
    Mandatory kwargs:
        sm_filename or dbname
        ref_filename or dbname
        cruiseid
        proc_yearbase

    Optional kwargs
        outfilebase='reflayer',
        printformats='pdf',
        dpi=100,
        days_per_page = 2.0,
        ddrange = None,
        max_gap_ratio = 0.05,
        min_speed = 1.0,
        max_speed = 5.0,
        ylim = [-1., 1.]

    """
    script_body = _reflstr

    defaultparams = dict(sm_filename=None,
                         ref_filename=None,
                         dbname=None,
                         incremental=False,
                         proc_yearbase = None,
                         titlestr=None,
                         cruiseid='ADCP',
                         outfilebase='reflayer',
                         printformats='pdf',
                         dpi=100,
                         days_per_page = 2.0,
                         ddrange = None,
                         max_gap_ratio = 0.05,
                         min_speed = 1.0,
                         max_speed = 5.0,
                         ylim = [-1., 1.])

    def process_params(self):
        p = self.params
        if p['proc_yearbase'] is None:
            raise ValueError('proc_yearbase must be set')
        if p['sm_filename'] is None:
            try:
                p['sm_filename'] = p['dbname'] + '.sm'
            except KeyError:
                raise ValueError('either sm_filename or dbname is required')
        fn = p['sm_filename']
        if fn is None or not os.path.exists(fn):
            raise ValueError("smoothr file named %s does not exist."%(fn,))
        if p['ref_filename'] is None:
            try:
                p['ref_filename'] = p['dbname'] + '.ref'
            except KeyError:
                raise ValueError('either ref_filename or dbname is required')
        fn = p['ref_filename']
        if fn is None or not os.path.exists(fn):
            raise ValueError("refabs file named %s does not exist."%(fn,))
        if p['titlestr'] is None:
            p['titlestr'] = '%(cruiseid)s absolute reference layer velocity' % p

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''

        Scripter.__call__(self, **kw)

        self.get_data()
        if len(self.refdat) == 0:
            _log.warning("No refabs data found")
            return
        if len(self.smdat) == 0:
            _log.warning("No smoothr data found")
            return

        if not self.edit_points():
            _log.warning("No valid reference layer data after editing")
            return

        dday = self.refdat['reftime']
        startdd = np.floor(dday[0])
        minspan = dday[-1] - startdd
        dt =  self.days_per_page
        numpages = int(np.ceil(minspan/dt))

        _log.debug('found %f days of data', dday[-1] - dday[0])
        _log.debug('start day is %f', startdd)
        _log.debug('figures with  %f days per page', self.days_per_page)
        _log.debug('printing %d pages', numpages)
        _log.debug('yrange will be [%f, %f]',
                                    -self.ylim[0], self.ylim[1])

        pages = list(range(numpages))
        if self.incremental:
            pages = pages[-2:]
        for pagenum in pages:
            fig = self.plot_refnav(startdd + pagenum*dt)
            if fig is None: # no data in that time range, so None is returned
                continue
            if self.printformats:
                for pf in self.printformats.split(':'):
                    fname = '%s_%03d.%s' % (self.outfilebase,
                               int(np.floor(startdd+pagenum*dt)), pf)
                    fig.savefig(fname,  dpi=self.dpi)
            _close(fig)


    #---------

    def get_data(self):

        ## load the data
        names = ['reftime', 'lon', 'lat', 'absu', 'absv', 'dfixtime',
                 'gapu', 'gapv', 'gaptime']
        dtype = np.dtype({'names':names, 'formats': [np.float64]*9})
        comment = guess_comment(self.ref_filename)
        if os.path.getsize(self.ref_filename)==0:
            self.refdat = []
        else:
            refdat = loadtxt_(self.ref_filename, comments=comment, dtype=dtype, ndmin=1)
            try:
                sl = rangeslice(refdat['reftime'], self.ddrange)
                self.refdat = refdat[sl]
            except:
                self.refdat = []


        names = ['smtime', 'sm_u', 'sm_v',
                    'uship', 'vship', 'smlon', 'smlat', 'frac']
        dtype = np.dtype({'names': names, 'formats': [np.float64]*8})
        comment = guess_comment(self.sm_filename)
        smdat = loadtxt_(self.sm_filename, comments=comment, dtype=dtype, ndmin=1)
        sl = rangeslice(smdat['smtime'], self.ddrange)
        self.smdat = smdat[sl]


    def edit_points(self):
        """Returns True if successful."""
        gapu, gapv = self.refdat['gapu'], self.refdat['gapv']
        speed = np.maximum(np.sqrt(gapu**2 + gapv**2), self.min_speed)

        # ratio = (gap velocity * gaptime) /
        #      (maximum velocity * interval of fix );
        gaptime = self.refdat['gaptime']
        dfixtime = self.refdat['dfixtime']
        ratio=(speed * gaptime) / (self.max_speed * dfixtime)

        # EDITING

        # find data within max_gap ratio range
        irange_in = (ratio <  self.max_gap_ratio)

        # assign those data that lie within max_gap ratio range
        if not irange_in.any():
            _log.warning("No good reference layer velocities available.")
            return False

        ref = self.refdat[irange_in]
        self.abs_u = ref['absu']
        self.abs_v = ref['absv']
        self.dt= ref['dfixtime']
        self.t = ref['reftime']


        # make abs_u and abs_v "bar-shaped"
        n = len(self.t)
        self.tt = np.zeros(2*n-1,float)
        self.uu = np.zeros(2*n-1,float)
        self.vv = np.zeros(2*n-1,float)


        self.tt[0::2] = self.t
        # make sure tt will be non-decreasing.
        dt0 = np.diff(self.t) - (1.0/86400)
        dt = np.minimum(dt0, self.dt[:-1]/(60*24)) # [:-1] or [1:]?
        self.tt[1:(2*n-2):2] = self.t[:-1] + dt
        self.uu[0::2] = self.abs_u
        self.uu[1:(2*n-2):2] = self.abs_u[:-1]
        self.vv[0::2] = self.abs_v
        self.vv[1:(2*n-2):2] = self.abs_v[:-1]


        # save times that are outside max_gap ratio range
        irange_out = ~irange_in
        self.notime = self.refdat[irange_out]['reftime'] # fix time
        # (may have length 0)

        self.nodat_y = np.empty_like(self.notime)
        filler=0.1*np.diff(self.ylim)+self.ylim[0]
        self.nodat_y.fill(filler[0])

        return True

    #----------

    def plot_refnav(self, startdd):


        #---------

        ddmin = startdd
        ddmax = ddmin + self.days_per_page

        i_smdday = rangeslice(self.smdat['smtime'], [ddmin, ddmax])
        i_refdday = rangeslice(self.refdat['reftime'], [ddmin, ddmax])
        i_ttdday = rangeslice(self.tt, [ddmin, ddmax])

        smt = self.smdat['smtime'][i_smdday]
        reft = self.refdat['reftime'][i_refdday]
        if len(smt) + len(reft) == 0:
            return None

        fig = plt.figure()
        ax1 = fig.add_subplot(311)
        ax2 = fig.add_subplot(312, sharex=ax1, sharey=ax1)
        ax3 = fig.add_subplot(313, sharex=ax1)
        ax4 = ax3.twinx()

        for ax in [ax1, ax2, ax3, ax4]:
            ax.yaxis.set_major_locator(MaxNLocator(5, prune='lower'))
            ax.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))

        for ax in [ax1, ax2, ax3]:
            ax.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))

        ax1.plot(self.tt[i_ttdday], self.uu[i_ttdday], '.r')
        ax1.plot(self.notime, self.nodat_y, 'm+')
        smu = ma.masked_equal(self.smdat['sm_u'][i_smdday], 1e38)
        smv = ma.masked_equal(self.smdat['sm_v'][i_smdday], 1e38)
        ax1.plot(smt, smu, '-b')
        ax1.set_ylabel('U (m/s)'),
        ax1.set_title(self.titlestr)
        ax1.set_ylim(self.ylim)
        ax1.grid(True)


        ax2.plot(self.tt[i_ttdday], self.vv[i_ttdday], '.r')
        ax2.plot(self.notime, self.nodat_y, 'm+')
        ax2.plot(smt, smv, '-b')
        ax2.set_ylabel('V (m/s)'),
        ax2.set_ylim(self.ylim)
        ax2.grid(True)

       #----------------------------

        dday = self.smdat['smtime']
        lon = ma.masked_equal(self.smdat['smlon'], 1e38)
        lat = ma.masked_equal(self.smdat['smlat'], 1e38)
        lon = unwrap_lon(lon)

        ax3.plot(dday, lon, 'b.')
        ax4.plot(dday, lat, 'g.')

        ax3.yaxis.set_major_formatter(LonFormatter())
        ax4.yaxis.set_major_formatter(LatFormatter())

        ax3.grid(True)
        for tl in ax3.yaxis.get_ticklabels():
            tl.set_color('b')
        for tl in ax4.yaxis.get_ticklabels():
            tl.set_color('g')

        ax1.set_xlim(ddmin,ddmax)
        for ax in [ax1, ax2]:
            for tl in ax.xaxis.get_ticklabels():
                tl.set_visible(False)
        ax3.set_xlabel('%(proc_yearbase)s decimal day' % self.params)
        return fig

##  (d)  ====================   Hcorrplot =======================

_hcorrstr = '''


from pycurrents.adcp.quick_mpl import Hcorrplot

PH = Hcorrplot()
PH(hcorr_filename= 'ens_hcorr.asc',
   titlestr = '${cruiseid}: Heading Correction',
   outfilebase = 'ens_hcorr_mpl',
   printformats = '${printformats}',
   proc_yearbase = ${proc_yearbase},
   ddrange = 'all')



'''


class Hcorrplot(Scripter):
    """
    Mandatory kwargs (supply when initializing):
        hcorr_filename or dbname
        [cruiseid (or titlestr), for reasonable titles]

    Optional kwargs (supply when initializing or when calling):
        titlestr
        cruiseid
        proc_yearbase
        outfilebase
        printformats
        dpi
        ddrange
        days_per_panel

        panels_per_page

    """
    script_body = _hcorrstr

    defaultparams = dict(hcorr_filename='ens_hcorr.asc',
                         proc_yearbase = None,
                         dbname=None,
                         titlestr=None,
                         cruiseid='ADCP',
                         incremental=False,
                         printformats = 'pdf',
                         dpi=100,
                         ddrange = 'all',
                         days_per_panel = 1,
                         panels_per_page = 4,
                         max_yscale = 10,
                         outfilebase='ens_hcorr_mpl')

    def process_params(self):
        p = self.params
        if p['hcorr_filename'] is None:
            raise ValueError('hcorr_filename must be set')
        if p['outfilebase'] is None:
            raise ValueError('outfilebase must be set')
        fn = p['hcorr_filename']
        if  not os.path.exists(fn):
            _log.warning("hcorr file named %s does not exist."%(fn,))
            return
        if p['titlestr'] is None:
            p['titlestr'] = '%(cruiseid)s heading correction' % p



    def __call__(self, **kw):
        '''
        See defaultparams.
        '''
        Scripter.__call__(self, **kw)

        self.get_data()
        if len(self.data) < 2:
            _log.warning('Not enough hcorr data available')
            return

        ymin = self.data['dh_mean'].min()
        ymax = self.data['dh_mean'].max()
        ymin = max(ymin, -self.max_yscale)
        ymax = min(ymax, self.max_yscale)
        self.yrange = [ymin, ymax]

        dday = self.data['dday']
        startdd = np.floor(dday[0])
        minspan = dday[-1] - startdd
        dt = self.panels_per_page * self.days_per_panel
        numpages = int(np.ceil((minspan)/dt))

        _log.debug('found %f days of data',
                    self.data['dday'][-1] - self.data['dday'][0])
        _log.debug('figures with %d panels per page, %f days per panel',
                                self.panels_per_page, self.days_per_panel)
        _log.debug('printing %d pages', numpages)


        pages = list(range(numpages))
        if self.incremental:
            pages = pages[-2:]
        for pagenum in pages:
            fig = self.plot_hcorr(startdd + pagenum*dt)
            if self.printformats:
                for pf in self.printformats.split(':'):
                    fname = '%s_%03d.%s' % (self.outfilebase,
                                         startdd+pagenum*dt, pf)
                    fig.savefig(fname,  dpi=self.dpi)

            _close(fig)


    def get_data(self):
        names = ['dday', 'hd_mean', 'hd_last', 'dh_mean', 'dh_std',
                 'n_used', 'badmask', 'Npersist']
        dtype = np.dtype({'names': names, 'formats': [np.float64]*8})
        comment = guess_comment(self.hcorr_filename)
        _hcorr = loadtxt_(self.hcorr_filename, comments=comment, ndmin=2)
        nr, nc = _hcorr.shape
        if nc == 7:
            hcorr = np.zeros((nr, 8), dtype=np.float64)
            hcorr[:,:7] = _hcorr
        else:
            hcorr = _hcorr

        hcorr = hcorr.view(dtype).ravel()

        sl = rangeslice(hcorr['dday'], self.ddrange)
        self.data = hcorr[sl]


    def plot_hcorr(self, startdd):
        fig = plt.figure(figsize=(8, 6), dpi=self.dpi)
        dday = self.data['dday']
        mask = self.data['badmask'].astype(bool)
        dh_mean = ma.array(self.data['dh_mean'], mask=mask)
        dh_mean_bad = ma.array(self.data['dh_mean'], mask=~mask)
        for plotnum in range(self.panels_per_page):
            ax = fig.add_subplot(self.panels_per_page, 1, plotnum+1)
            ddmin = startdd + plotnum*self.days_per_panel
            ddmax = ddmin + self.days_per_panel
            ii = rangeslice(dday, [ddmin, ddmax])
            ax.plot(dday[ii], dh_mean[ii], 'g.', label='heading correction')
            ax.plot(dday[ii], dh_mean_bad[ii], 'r+', label='placeholder (bad value)')
            ax.set_ylabel('deg')
            ax.set_xlim([ddmin, ddmax])
            ax.yaxis.set_major_locator(MaxNLocator(5, prune='both'))
            ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
            ax.set_ylim(self.yrange)
            ax.tick_params(direction='in')
            if plotnum == 0:
                ax.legend(bbox_to_anchor=(1.011, 1.55)) #values hand-tuned
        if self.params['proc_yearbase'] is None:
            ax.set_xlabel('decimal day')
        else:
            ax.set_xlabel('decimal day, year=%d' % (self.proc_yearbase,))
        fig.suptitle(self.titlestr)
        return fig

##  (e)  ====================   Btplot =======================

_btcalstr = '''

from pycurrents.adcp.quick_mpl import Btplot

## other parameters that can be chosen:
## These lines are formatted so you can just remove the '##' and they will
## just work; no additional formatting.

##   name                      default
##   ------                   --------------
##   dbname        = '../../adcpdb/aship' , # use the real name
##   titlestr      =   ' ${cruiseid}'     ,
##   load_only     =      False           , # if True; no graphical or text output
##   printformats  =      'pdf'           ,
##   dpi           =      100             ,
##   outfilebase   =     'btcal'          ,
##   ddrange       =      'all'           ,
##   step          =      1               ,
##   min_speed     =      2               ,
##   max_sig       =      2.5             ,
##   max_gap       =      0.1             ,
##   tol_dt        =      0.02            ,
##   min_depth     =      25              ,  #shallower for high freq
##   max_depth     =      1500            ,
##

BT = Btplot()
BT(btm_filename='${dbname}.btm',
   ref_filename='${dbname}.ref',
   cruiseid = '${cruiseid}',
   min_depth = ${min_depth},
   max_depth = ${max_depth},
   printformats = '${printformats}',
   proc_yearbase='${proc_yearbase}')
'''

class Btplot(Scripter):
    """
    Mandatory kwargs:
        btm_filename or dbname
        ref_filename or dbname
        cruiseid
        proc_yearbase
    Optional kwargs:
        load_only     = False,
        printformats  = 'pdf',
        dpi           = 100,
        outfilebase   ='btcal',
        ddrange       = 'all',
        step          = 1,
        min_speed     = 2,
        max_sig       = 2.5,
        max_gap       = 0.1,
        tol_dt        = 0.02,
        min_depth     = 25,
        max_depth     = 1500)
    """


    script_body = _btcalstr

    defaultparams = dict(btm_filename=None,
                         ref_filename=None,
                         dbname=None,
                         titlestr=None,
                         cruiseid='ADCP',
                         proc_yearbase = None,
                         load_only     = False,
                         printformats  = 'pdf',
                         dpi           = 100,
                         outfilebase   ='btcal',
                         ddrange       = 'all',
                         step          = 1,
                         min_speed     = 2,
                         max_sig       = 2.5,
                         max_gap       = 0.1,
                         tol_dt        = 0.02,
                         min_depth     = 25,
                         max_depth     = 1000)

    def process_params(self):
        p = self.params
        if p['proc_yearbase'] is None:
            raise ValueError('proc_yearbase must be set')
        for ext in ['btm', 'ref']:
            if p[ext+'_filename'] is None:
                try:
                    p[ext+'_filename'] = p['dbname'] + '.' + ext
                except KeyError:
                    raise ValueError(
                            'either %s_filename or dbname is required'%(ext,))
            fn = p[ext+'_filename']
            if fn is None or not os.path.exists(fn):
                raise ValueError("Input file named %s does not exist."%(fn,))
        if p['titlestr'] is None:
            p['titlestr'] = '%(cruiseid)s bottomtrack calibration' % p

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''
        Scripter.__call__(self, **kw)

        if not self.get_data():
            _log.debug("Returning from Btplot with no output")
            return

        if not self.edit_points():
            _log.debug("Returning from Btplot with no output")
            return

        self.grid_bt()

        if self.load_only is False:

            if self.outfilebase is not None:
                self.print_stats()

            if self.printformats:
                fig = self.plot_caldots()
                for pf in self.printformats.split(':'):
                    fig.savefig(self.outfilebase+'.'+pf, dpi=self.dpi)
                _close(fig)

        self.write_caldat()


    def get_data(self):
        comment = guess_comment(self.btm_filename)
        btdat = loadtxt_(self.btm_filename, comments=comment, ndmin=2)
        if len(btdat) == 0:
            _log.debug("No data in %s", self.btm_filename)
            return 0
        if len(btdat.shape) == 1:
            _log.debug("insufficient data in %s", self.btm_filename)
            return 0
        comment = guess_comment(self.ref_filename)
        refdat = loadtxt_(self.ref_filename, comments=comment, ndmin=2)
        if len(refdat) == 0:
            _log.debug("No data in %s", self.ref_filename)
            return 0
        if len(refdat.shape) == 1:
            _log.debug("Insufficient data in %s", self.ref_filename)
            return 0

        bti = rangeslice(btdat[:,0], self.ddrange)
        refi = rangeslice(refdat[:,0], self.ddrange)

        self.refdat = refdat[refi,:]
        self.day_bt   = btdat[bti,0]

        if len(self.refdat) == 0 or len(self.day_bt) == 0:
            _log.debug('No BT data in time range %s', self.ddrange)
            return 0

        self.u_bt     = btdat[bti,1]
        self.v_bt     = btdat[bti,2]
        self.depth_bt = btdat[bti,3]

        self.speed_bt = np.sqrt(self.u_bt**2 + self.v_bt**2)
        course_bt = 90 - (np.arctan2(self.v_bt, self.u_bt)*180/np.pi)
        self.heading_bt = np.remainder(course_bt+360+180, 360.0)-180

        self.ddrange = [self.day_bt[0], self.day_bt[-1]]
        return 1

    def edit_points(self):
        """Return True if more than one point survives."""
        refdat = self.refdat
        # At the outset, eliminate any points with big gaps in the BT:
        # self.refdat is called "cal" in matlab
        refdat = refdat.compress(refdat[:,7] <= self.max_gap, axis=0)

        # make sure we have data
        refi = rangeslice(refdat[:,0], self.ddrange) # ddrange was updated above
        refdat = refdat[refi,:]
        refdday = refdat[:,0]


        # Eliminate any points outside the desired depth range:
        # Estimate the depths etc at the fix times from the lst_btrk depths.
        # Normally, the fix times will nearly, but not perfectly, coincide
        # with the BT times.  Hence the interpolation step is required, but
        # will not greatly change the depth estimates.

        cal_depth = np.interp(refdday, self.day_bt, self.depth_bt)

        igoodref = (cal_depth >= self.min_depth) & (cal_depth <= self.max_depth)

        #### Eliminate points with bad BT values: TESTING
        speedcutoff = 10000 #  cm/s (100m/s, i.e. 25m/s for each component)

        # some VmDAS data has nans as well.
        xx=np.sum(np.absolute(refdat[:,1:5]), axis=1)
        bad_speed = (np.isnan(xx) | (xx >= speedcutoff))

        nbad = bad_speed.sum()
        if nbad:
            F = open('btcal_errs.log','a')
            F.write('BAD SPEEDS DETECTED: (due to a bad raw BT value?)\n')
            for ii in np.nonzero(bad_speed)[0]:
                F.write('BAD LINE (line number %d):\n' % (ii,))
            F.close()

        mask = ~bad_speed & igoodref

        self.okrefdat = refdat.compress(mask, axis=0)
        return self.okrefdat.shape[0] > 1

    def grid_bt(self):

        nfix = self.okrefdat.shape[0]
        i0 = np.arange(nfix - self.step, dtype=int)
        i1 = i0 + self.step

        day = self.okrefdat[:,0] # fix times
        self.dayuv = 0.5 * (day[i0] + day[i1])  # times of velocities

        regrid_refu     = grid.interp1(self.day_bt, self.u_bt, self.dayuv)
        regrid_refv     = grid.interp1(self.day_bt, self.v_bt, self.dayuv)
        ## FIXME: use or delete regrid_refdepth and regrid_refspeed
        #regrid_refdepth = grid.interp1(self.day_bt, self.depth_bt,
        #                                                       self.dayuv);


        #regrid_refspeed = np.sqrt(regrid_refu**2 + regrid_refv**2)
        regrid_refhead  = 90 - (np.arctan2(regrid_refv,
                                           regrid_refu)*180/np.pi)
        regrid_refhead  = np.remainder(regrid_refhead+360+180,360.)-180

        # cal(:,2) and cal(:,3) are the differences in meters
        # between successive fixes in the x and y directions,
        # respectively.  Row 1 is zero, row 2 is the displacement
        # from time 1 to time 2, etc.  cal(:,4) and cal(:,5)
        #   are similar, but determined from ADCP bottom track.


        refdatsum = self.okrefdat.cumsum(axis=0)
        xnav = refdatsum[:,1]
        ynav = refdatsum[:,2]

        xbt  = refdatsum[:,3]
        ybt  = refdatsum[:,4]


        dt = (day[i1] - day[i0]) * 86400
        unav = (xnav[i1] - xnav[i0]) / dt
        vnav = (ynav[i1] - ynav[i0]) / dt

        ubt  = (xbt[i1]  - xbt[i0])  / dt
        vbt  = (ybt[i1]  - ybt[i0])  / dt

        med_dt = np.median(dt)

        self.speed_nav = np.sqrt(unav**2 + vnav**2)
        self.speed_btgrid  = np.sqrt(ubt**2 + vbt**2)

        self.dt = dt
        self.med_dt = med_dt

        self.a = self.speed_nav/self.speed_btgrid

        ph = (np.arctan2(vnav,unav) - np.arctan2(vbt,ubt))*(180/np.pi)
        self.ph = wrap(ph, min=-180)

        badmask = (self.speed_nav < self.min_speed )
        badmask |= (np.absolute(self.dt - self.med_dt)/self.med_dt
                                                        >= self.tol_dt)

        self.a_ma = ma.masked_array(self.a, mask=badmask)
        self.ph_ma = ma.masked_array(self.ph, mask=badmask)

        for ii in [0,1]:  #iterate
            a_mn = self.a_ma.mean()
            a_std = self.a_ma.std()
            a_dev = np.abs(self.a_ma - a_mn)/a_std
            self.a_ma[a_dev > self.max_sig] = ma.masked

            ph_mn = self.ph_ma.mean()
            ph_std = self.ph_ma.std()
            ph_dev = np.abs(self.ph_ma - ph_mn)/ph_std

            badmask = (a_dev > self.max_sig) | (ph_dev > self.max_sig)
            self.a_ma[badmask] = ma.masked
            self.ph_ma[badmask] = ma.masked


    def print_stats(self):
        #---------------------------------------------------------
        # Write the results out to a file named "btcaluv.out".
        a_mn_e, a_std_e, a_num_e, a_med_e = stats.Stats(
            self.a_ma, axis=0, masked=False)(median=True)

        ph_mn_e, ph_std_e, ph_num_e, ph_med_e = stats.Stats(
            self.ph_ma, axis=0, masked=False)(median=True)

        f = open('btcaluv.out', 'a')
        f.write( '%s\n' % (self.titlestr,))
        f.write( '\nTime range %6.2f to %6.2f' % tuple(self.ddrange))
        f.write( '\n   Calculation done at %s'  % (time.asctime(),))
        f.write( '\n    step: %d' % (self.step,))
        f.write( '\n    min_depth: %3.0f   max_depth: %3.0f' %
                                  (self.min_depth, self.max_depth))
        f.write( '\n    min_speed: %4.1f m/s   max_sig: %4.1f std devs' %
                                  (self.min_speed, self.max_sig))
        f.write( '\n    max_gap: %5.2f minutes   tol_dt: %4.2f (fraction)'%
                                 (self.max_gap, self.tol_dt))
        f.write( '\nunedited: %d points' % (len(self.ph,)))
        f.write( '\nedited:   %d points, %3.1f min speed, %3.1f max dev' %
                       (self.ph_ma.count(), self.min_speed, self.max_sig))
        f.write( '\n            median     mean      std')
        f.write( '\namplitude  %7.4f  %7.4f  %7.4f' %
                         (a_med_e, a_mn_e, a_std_e))
        f.write( '\nphase      %7.4f  %7.4f  %7.4f' %
                            (ph_med_e, ph_mn_e, ph_std_e))
        f.write( '\n\n')
        f.close()


    #----------
    def plot_caldots(self):

        # prep the figure
        fig = plt.figure(figsize=(6,8))

        #---------
        ax1 = fig.add_subplot(511)
        ax2 = fig.add_subplot(512, sharex=ax1)
        ax3 = fig.add_subplot(513, sharex=ax1)
        ax4 = fig.add_subplot(514, sharex=ax1)
        ax5 = fig.add_subplot(515, sharex=ax1)

        shorten_ax(ax1, -.1)
        shorten_ax(ax3, -.3)
        shorten_ax(ax4, -.1)
        shorten_ax(ax5, .1)

        for ax in [ax1, ax2, ax3, ax4, ax5]:
            ax.yaxis.set_major_locator(MaxNLocator(5, prune='lower'))
            ax.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
            ax.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
            ax.grid(True)


        ax1.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax1.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax2.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax2.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))

        ax3.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax3.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax4.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax4.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))

        ax5.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax5.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))

        # -------amplitude and phase ----------

        xlim = [self.day_bt[0], self.day_bt[-1]]
        xx=np.array([xlim[0], xlim[1], xlim[1], xlim[0], xlim[0]])
        yy=np.array([-1,      -1,      1,       1,       -1])

        left_kwargs = dict(fontsize=14, weight='bold', color='0.5')
        #------ phase

        ax1.fill(xx,0.1*yy,color='0.80')
        ax1.plot(xlim, [0,0],'k')
        ax1.plot(self.dayuv,   self.ph_ma, '.')
        ax1.set_ylabel('degrees'),
        ax1.text(.05, 0.8, 'Phase', transform = ax1.transAxes,
                  **left_kwargs)
        ax1.set_title(self.titlestr)
        # ----- amp
        ss=stats.Stats(self.a_ma, axis=0, masked=False)
        yrange=np.max([.005, 2*ss.std])+.002
        yrect = 1 + 0.002*yy
        ax2.fill(xx,yrect,color='0.80')
        ax2.plot(xlim, [1, 1],'k')
        ax2.plot(self.dayuv, self.a_ma, '.')
        ax2.set_xlim(xlim)
        ylow = np.min([ss.mean-yrange, 1-yrange, .99])
        yhigh = np.max([ss.mean+yrange, 1+yrange, 1.01])

        try:
            ax2.set_ylim([ylow, yhigh])
        except:
            _log.debug('cannot set ylim in plot_caldots -- bad data?')
        ax2.text(.05, 0.8, 'Amplitude', transform = ax2.transAxes,
                  **left_kwargs)
        ax2.set_ylabel('scale factor')
        ax2.set_xlabel('Decimal Day')

        #------- bottom track --------------

        ax3.plot(self.day_bt, self.speed_bt, '.')
        ax3.set_ylabel('m/s'),
        ax3.text(.05, 0.8, 'Speed', transform = ax3.transAxes,
                  **left_kwargs)

        #------ course

        ax4.plot(self.day_bt, self.heading_bt, '.')
        ax4.set_ylabel('degrees'),
        ax4.text(.05, 0.8, 'Heading', transform = ax4.transAxes,
                  **left_kwargs)

        #------- speed

        ax5.plot(self.day_bt, self.depth_bt, '.')
        ax5.set_ylabel('meters'),
        ax5.text(.05, 0.8, 'Depth', transform = ax5.transAxes,
                  **left_kwargs)
        ax5.set_xlabel('Decimal Day')
        ax5.set_ylim(ax5.get_ylim()[::-1])


        for ax in [ax1, ax3, ax4]:
            for tl in ax.xaxis.get_ticklabels():
                tl.set_visible(False)

        return fig

    #----------
    def write_caldat(self):
        with open(self.outfilebase+'_edited.txt','w') as F:
            F.write('#decimal_day   amplitude     phase\n')
            aaa = np.ma.filled(self.a_ma.astype(float), np.nan)
            ph = np.ma.filled(self.ph_ma.astype(float), np.nan)

            for tup in zip(self.dayuv, aaa, ph):
                F.write('%10.4f  %10.3f   %10.3f\n' % tup)



##  (f)  ====================   Wtplot =======================


_wtcalstr = '''

from pycurrents.adcp.quick_mpl import Wtplot

## other options that can be chosen
## These lines are formatted so you can just remove the '##' and they will
## just work; no additional formatting.

##
##       name                    value
##      -------------          -----------
##        cruiseid          =   '${cruiseid}',
##        printformats      =   'pdf'        ,
##        dpi               =    100         ,
##        outfilebase       =   'wtcal'      ,
##        statsfile         =   'adcpcal.out',
##        load_only         =   False        ,    #if True: no plots, no output
##        comment           =   '#'          ,
##        ddrange           =   'all'        ,
##        clip_ph           =    3,          ,
##        clip_amp          =    0.04        ,
##        clip_var          =    0.05        ,
##        clip_dt           =    60          ,
##        clip_u            =    [-100,100]  ,
##        clip_v            =    [-100,100]  ,



WT = Wtplot()
WT(cal_filename = '${cal_filename}',
  printformats = '${printformats}',
  cruiseid = '${cruiseid}',
  proc_yearbase = '${proc_yearbase}')
'''



class Wtplot(Scripter):
    """
    Mandatory kwargs:
        cal_filename or dbname
        proc_yearbase

    Optional kwargs:         default
      -------------          -----------
        cruiseid             'ADCP
        printformats         'pdf'
        load_only             False
        dpi                   100
        outfilebase          'wtcal'
        statsfile            'adcpcal.out'
        comment              '#'
        ddrange              'all'
        clip_ph               3,
        clip_amp              0.04
        clip_var              0.05
        clip_dt               60
        clip_u                [-100,100]
        clip_v                [-100,100]

    """
    script_body = _wtcalstr

    defaultparams = dict(cal_filename=None,
                         dbname=None,
                         titlestr=None,
                         proc_yearbase=None,
                         cruiseid='ADCP',
                         load_only=False,
                         printformats = 'pdf',
                         dpi=100,
                         outfilebase='wtcal',
                         statsfile = 'adcpcal.out',
                         comment= '#',
                         ddrange = 'all',
                         clip_ph  = 3,
                         clip_amp = 0.04,
                         clip_var = 0.05,
                         clip_dt  = 60,
                         clip_u   = [-100,100],
                         clip_v   = [-100,100])

    def process_params(self):
        p = self.params
        if p['proc_yearbase'] is None:
            raise ValueError('proc_yearbase must be set')
        if p['cal_filename'] is None:
            try:
                p['cal_filename'] = p['dbname'] + '_7.cal'
            except KeyError:
                raise ValueError('either cal_filename or dbname is required')
        fn = p['cal_filename']
        if fn is None or not os.path.exists(fn):
            raise ValueError("Calib file named %s does not exist."%(fn,))
        if p['titlestr'] is None:
            p['titlestr'] = '%(cruiseid)s watertrack calibration' % p

    def __call__(self, **kw):
        '''
        See defaultparams.
        '''
        Scripter.__call__(self, **kw)

        try:
            self.get_data()
        except:
            _log.debug('No watertrack calibration data')
            return

        _log.debug('Found %d calibration points', len(self.caldat))

        if not self.edit_points():
            _log.debug('Fewer than 2 edited points found. No WT plot made.')
            return


        if self.load_only is False:
            statstr = self.get_stats()
            self.print_stats(statstr)

            fig = self.plot_caldots()
            if self.printformats:
                for pf in self.printformats.split(':'):
                    fig.savefig(self.outfilebase+'1.'+pf, dpi=self.dpi)
            _close(fig)

            fig = self.plot_calhist()
            if self.printformats:
                for pf in self.printformats.split(':'):
                    fig.savefig(self.outfilebase+'2.'+pf, dpi=self.dpi)
            _close(fig)

            self.write_caldat()


    def get_data(self):

        names = ['updn', 't', 'nabs', 'nfix', 'du', 'dv', 'var', 'mvar',
                  'dt', 'amp', 'ph']
        formats = [np.int8, np.float64, np.int64, np.int64, np.float64, np.float64,
                   np.float64, np.float64, np.float64, np.float64, np.float64]
        dtype = np.dtype({'names':names, 'formats':formats})
        comment = guess_comment(self.cal_filename)
        caldat = loadtxt_(self.cal_filename, comments=comment, dtype=dtype, ndmin=1)

        ii = rangeslice(caldat['t'], self.ddrange)
        self.caldat = caldat[ii]

        dday = caldat['t'][ii]
        if len(dday):
            self.ddrange = [dday[0], dday[-1]]


    #----------

    def edit_points(self):

        cd = self.caldat

        if np.isnan(np.sum(cd['du'] + cd['dv'] + cd['amp'] + cd['ph'])):
            badvals = (np.isnan(cd['du']) | np.isnan(cd['dv']) |
                       np.isnan(cd['amp']) | np.isnan(cd['ph']))
            mask = ~badvals
            F = open('wtcal_errs.log','a')
            F.write('BAD SPEEDS DETECTED: (due to a bad navigation?)\n')
            for ii in np.nonzero(badvals)[0]:
                F.write('BAD LINE (line number %d):\n' % (ii,))
            F.close()
            caldat = cd.compress(mask)

        else:
            caldat = self.caldat

        if caldat.size < 2:
            return False

        rmed_ph  = np.median(caldat['ph'])
        rmed_amp = np.median(caldat['amp'])
        rmed_dt  = np.median(caldat['dt'])

        # --> Find indices with good amp, phase, vel, and variance

        a_good1  = (caldat['amp'] - rmed_amp < self.clip_amp)
        a_good2  = (caldat['amp'] - rmed_amp > -self.clip_amp)

        p_good1  = (caldat['ph'] - rmed_ph < self.clip_ph)
        p_good2  = (caldat['ph'] - rmed_ph > -self.clip_ph)

        dt_good1 = (caldat['dt'] - rmed_dt < self.clip_dt)
        dt_good2 = (caldat['dt'] - rmed_dt > -self.clip_dt)

        var_good = (caldat['mvar'] < self.clip_var)

        du_good1 = (caldat['du']  > self.clip_u[0])
        du_good2 = (caldat['du']  < self.clip_u[1])
        dv_good1 = (caldat['dv']  > self.clip_v[0])
        dv_good2 = (caldat['dv']  < self.clip_v[1])

        goodmask = ( p_good1  & p_good2 & a_good1 & a_good2 &
                             dt_good1 & dt_good2 &  var_good &
                             du_good1 & du_good2 &  dv_good1 &
                             dv_good2)

        caldat_ma = caldat[goodmask]

        self.caldat_ma = caldat_ma
        self.goodmask = goodmask

        return True


    #----------


    def get_stats(self):
        '''
        return string to print into adcpcal.out
        '''

        varlist = ['amp', 'ph', 'dt', 'var', 'mvar', 'du', 'dv']
        lablist = ['amplitude', 'phase', 'nav - pc',
                      'var', 'min var', 'delta-u', 'delta-v']
        labels = dict(zip(varlist, lablist))

        mr = len(self.caldat['t'])
        n_edit = len(self.caldat_ma)

        tmean = self.caldat_ma['t'].mean() if n_edit > 0 else np.nan
        if n_edit > 1:
            t_centered = self.caldat_ma['t'] - tmean
            ph_coef = np.polyfit(t_centered, self.caldat_ma['ph'],  1)
            pa_coef = np.polyfit(t_centered, self.caldat_ma['amp'], 1)
        elif n_edit == 1:
            ph_coef = [0, self.caldat_ma['ph'][0]]
            pa_coef = [0, self.caldat_ma['amp'][0]]
        else:
            ph_coef = [np.nan, np.nan]
            pa_coef = [np.nan, np.nan]

        outlist = []

        outlist.append(' %s\n' % self.titlestr)

        outlist.append('#%s\n' % (self.comment)) # new

        outlist.append(' Time range %6.2f to %6.2f' % tuple(self.ddrange))
        outlist.append( '\n   Calculation done at %s' % (time.asctime(),))
        outlist.append( '\n   delta-u min = %6.2f, max = %6.2f' %
                                                    tuple(self.clip_u))
        outlist.append( '\n   delta-v min = %6.2f, max = %6.2f' %
                                                    tuple(self.clip_v))
        outlist.append( '\n   clip_amp = %4.2f,  clip_ph = %4.1f' %
                                            (self.clip_amp, self.clip_ph))
        outlist.append( '\n   clip_dt = %4.0f,  clip_var = %5.3f' %
                                            (self.clip_dt, self.clip_var))
        outlist.append( '\nNumber of edited points: %3.0f out of %3.0f' %
                                                               (n_edit, mr))
        outlist.append( '\n   amp   = %6.4f  + %6.4f (t - %5.1f)' %
                                            (pa_coef[1], pa_coef[0], tmean))
        outlist.append( '\n   phase = %6.2f  + %6.4f (t - %5.1f)' %
                                            (ph_coef[1], ph_coef[0], tmean))

        outlist.append( '\n            median     mean      std')
        for var in varlist:
            s = stats.Stats(self.caldat_ma[var], axis=0, masked=False)
            outlist.append('\n%-10s %7.4f  %7.4f  %7.4f' % (labels[var],
                         s.median, s.mean, s.std))

        return ''.join(outlist)


    def print_stats(self, statstr):
        '''
        append string to adcpcal.out
        '''
        outfile = open(self.statsfile,'a') #was 'adcpcal.out
        outfile.write(statstr)
        outfile.write('\n\n')
        outfile.close()


    #----------
    def plot_caldots(self):

        fig = plt.figure(figsize=(6,8))
        fig.subplots_adjust(left=0.15, right=0.95,
                            bottom=0.07, top=0.93, hspace=0.05)
        fig.suptitle(self.titlestr)

        ax1 = fig.add_subplot(411)
        ax2 = fig.add_subplot(412, sharex=ax1)
        ax3 = fig.add_subplot(413, sharex=ax1)
        ax4 = fig.add_subplot(414, sharex=ax1)

        for ax in [ax1, ax2, ax3, ax4]:
            ax.yaxis.set_major_locator(MaxNLocator(5, prune='lower'))
            ax.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
            ax.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
            ax.grid(True)

        xlim=self.caldat['t'][0],self.caldat['t'][-1]
        xx=np.array([xlim[0], xlim[1], xlim[1], xlim[0], xlim[0]])
        yy=np.array([-1,      -1,      1,       1,       -1])

        left_kwargs = dict(fontsize=14, weight='bold', color='0.5')

        # ----- phase (unedited)
        ax1.fill(xx,0.1*yy,color='0.80')
        ax1.plot(xlim, np.array([0,0]),'k')
        ax1.plot(self.caldat['t'], self.caldat['ph'],'bo')
        ax1.set_xlim(xlim)
        ax1.set_ylabel('degrees'),
        ax1.text(.05, 0.8, 'phase (unedited)', transform = ax1.transAxes,
                  **left_kwargs)

        # ----- amp (unedited)
        yrect = 1 + 0.002*yy
        ax2.fill(xx, yrect,color='0.80')
        ax2.plot(xlim, np.array([0,0]),'k')
        ax2.plot(self.caldat['t'], self.caldat['amp'],'co')
        ax2.set_ylabel('scale factor'),
        ax2.text(.05, 0.8, 'amp (unedited)', transform = ax2.transAxes,
                  **left_kwargs)


        # ----- phase (edited)
        ax3.fill(xx,0.1*yy,color='0.80')
        ax3.plot(xlim, np.array([0,0]),'k')
        ax3.plot(self.caldat_ma['t'], self.caldat_ma['ph'],'bo')
        ax3.set_ylabel('degrees'),
        ax3.text(.05, 0.8, 'phase (edited)',  transform = ax3.transAxes,
                  **left_kwargs)

        # ----- amp (edited)
        yrect = 1 + 0.002*yy
        ax4.fill(xx, yrect,color='0.80')
        ax4.plot(xlim, np.array([1,1]),'k')
        ax4.plot(self.caldat_ma['t'], self.caldat_ma['amp'],'co')
        ax4.set_ylabel('scale factor')

        ss=stats.Stats(self.caldat_ma['amp'], masked=False)
        yrange=np.max([.005, 2*ss.std])+.002
        ylow = np.min([ss.mean-yrange, 1-yrange, .99])
        yhigh = np.max([ss.mean+yrange, 1+yrange, 1.01])
        try:
            ax4.set_ylim([ylow, yhigh])
        except:
            _log.debug('cannot set ylim in plot_caldots -- bad data?')

        ax4.text(.05, 0.8, 'amp (edited)', transform = ax4.transAxes,
                  **left_kwargs)

        ax4.set_xlabel('%(proc_yearbase)s decimal days' % self.params)

        for ax in [ax1, ax2, ax3]:
            for tl in ax.xaxis.get_ticklabels():
                tl.set_visible(False)

        return fig


    #----------
    def write_caldat(self):
        with open(self.outfilebase+'_edited.txt','w') as F:
            F.write('#decimal_day   amplitude     phase\n')
            for tup in zip(self.caldat['t'],
                           self.caldat['amp'],
                           self.caldat['ph']):
                F.write('%10.4f  %10.3f   %10.3f\n' % tup)

#------------------------------

    def plot_calhist(self):

        fig = plt.figure(figsize=(6,8))
        fig.subplots_adjust(left=0.15, right=0.95,
                            bottom=0.07, top=0.93)
        fig.suptitle(self.titlestr)

        ax1 = fig.add_subplot(411)
        ax2 = fig.add_subplot(412)
        ax3 = fig.add_subplot(413)
        ax4 = fig.add_subplot(414)
        for ax in [ax1, ax2, ax3, ax4]:
            ax.xaxis.set_major_locator(MaxNLocator(7, prune='lower'))
            ax.yaxis.set_major_locator(MaxNLocator(4, prune='lower'))

        # --- phase
        left_kwargs = dict(fontsize=14,
                          weight='bold',
                          color='0.5',
                          ha='left')
        right_kwargs = left_kwargs.copy()
        right_kwargs['ha'] ='right'

        ax1.hist(self.caldat_ma['ph'], bins=20, facecolor='b')
        ax1.text(.05, 0.8, 'phase (edited)', transform = ax1.transAxes, **left_kwargs)
        ax1.text(.95, 0.8, 'degrees',        transform = ax1.transAxes, **right_kwargs)
        # --- amp
        ax2.hist(100*(self.caldat_ma['amp']-1), bins=20, facecolor='c')
        ax2.text(.05, 0.8, 'amplitude (edited)', transform = ax2.transAxes, **left_kwargs)
        ax2.text(.95, 0.8, 'scale factor',       transform = ax2.transAxes, **right_kwargs)
        # --- PC time
        ax3.hist(self.caldat_ma['dt'], bins=20, facecolor='g')
        ax3.text(.05, 0.8, 'nav - pc', transform = ax3.transAxes, **left_kwargs)
        ax3.text(.95, 0.8, 'seconds',  transform = ax3.transAxes, **right_kwargs)

        ax4.plot(self.caldat_ma['t'], self.caldat_ma['dt'],'g.', ms=12)
        ax4.set_ylabel('seconds'),
        ax4.text(.05, 0.8, 'nav - pc', fontsize=14,
                       weight='bold',
                       color='0.5',
                       transform = ax4.transAxes)
        ax4.grid(True)

        return fig

#---------------------------

dirdict = {'temp': 'edit',
           'npings' : 'edit',
           'uvship' : 'nav',
           'nav': 'nav',
           'refl': 'nav',
           'hcorr': 'cal/rotate',
           'btcal': 'cal/botmtrk',
           'wtcal': 'cal/watertrk'}

classdict = {'temp': Tempplot,
             'npings' : NPingplot,
             'uvship' : UVShipPlot,
             'nav': Navplot,
             'refl': Refplot,
             'hcorr': Hcorrplot,
             'btcal': Btplot,
             'wtcal': Wtplot
             }

##     =======================================================

class Q_test:
    '''test import of classes'''

    def qtest(self):

        print('in test')

class Q_mpl:
    '''calls to plotting classes'''

    _log.debug('in Q_mpl')
    #---------

    def mpltest(self):
        import matplotlib
        print('MPL scalar formatter is ', matplotlib.ticker.ScalarFormatter)

    def run_plotter(self, plotname, **kw):
        _log.debug('Starting plot: %s', plotname)
        plotdir = dirdict[plotname]
        startdir = os.getcwd()
        os.chdir(plotdir)
        try:
            Plotter = classdict[plotname](self.opts, **kw)
            Plotter.write()
            Plotter()
        except:
            _log.exception('Failure in plot: %s', plotname)
        finally:
            os.chdir(startdir)
            _log.debug('Ending plot: %s', plotname)

    def plottemp_mpl(self, **kw):
        self.run_plotter('temp', **kw)

    def plotnpings_mpl(self, **kw):
        self.run_plotter('npings', **kw)

    def plotuvship_mpl(self, **kw):
        self.run_plotter('uvship', **kw)

    def plotnav_mpl(self, **kw):
        self.run_plotter('nav', **kw)

    def plotrefl_mpl(self, **kw):
        self.run_plotter('refl', **kw)

    def plothcorr_mpl(self, **kw):
        # FIXME: not the right place?  why is this needed?
        kw.setdefault('hcorr_filename', self.opts['time_angle_base']+'.asc')
        kw.setdefault('outfilebase', self.opts['time_angle_base'])
        kw.setdefault('time_angle_base', self.opts['time_angle_base'])
        self.run_plotter('hcorr', **kw)

    def plotbtcal_mpl(self, **kw):
        self.run_plotter('btcal', **kw)

    def plotwtcal_mpl(self, **kw):
        self.run_plotter('wtcal', **kw)
