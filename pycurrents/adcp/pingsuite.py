import os
import logging
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

from pycurrents.adcp.qplot import qpc
from pycurrents.adcp.uhdasconfig import UhdasConfig
from pycurrents.adcp.adcp_specs import ping_editparams, Sonar
from pycurrents.system.misc import Cachefile, Bunch
import pycurrents.adcp.pingavg as pingavg
from pycurrents.adcp.pingavg import get_uvship
from pycurrents.data import navcalc
from pycurrents.adcp.transform import heading_rotate
from pycurrents.num.stats import Stats
from pycurrents.codas import to_date

##----
# (1) set up logger
_log = logging.getLogger(__name__)

### adcp raw data ========================

#------------------------------------------

class PingSuite:
    '''
    class for reading a snippet of RDI ADCP UHDAS raw data, with uhdas
        ancillary serial data attached

    provides methods to

        * (using Multiread) select a segment with one
             instrument configuration  or a chunk that
             guarantees monotonic m_dday
        * extract specified time range from raw data using specified
            time type

   example


      PS=PingSuite(cruisedir, 'os38bb')
      PS.pinger.get_pings(start_dday=157.0, nsecs=300)

      # sets attributes PS.pinger.ens
      #                 PS.pinger.avg
      # usually run from the root processing directory (with
      #     default config and edit params in ../config/ and load/
      #     respectivley)

      NOTE: - time variable is 'utc' (corresponds to dday in codasdb)
            - cannot cross chunk (configuration change) boundaries
            - heading variable is already corrected (value stored in 'dh')

    '''

    def __init__(self,
                 # for UhdasConfig
                 sonar,
                 cfgpath='../config',    # read this cruisename_proc.py
                 cruisename=None,        #...using this cruisename
                 uhdas_dir_override=None,# allows override of uhdas_dir
                 #
                 # or if it is specified, do not use above
                 uhdas_cfg=None,  # if specified, use this UhdasConfig
                                  # otherwise, get from here:
                 #
                 editparams_file = '../load/ping_editparams.txt',
                 editparams_override = None,
                 verbose=True,
                 ibadbeam=None,
                 beam_index=None,
                 **kw):
        '''
        defaults assume
          - calling from 'edit' directory
          - cruisename_proc.py file has all the right information
        '''

        self.conf_fmt = '%s:  %5d, %7.1f, %6.1f, %6.1f,'
        self.ymdhms_fmt = '%04d/%02d/%02d %02d:%02d:%02d'
        self.sonar = Sonar(sonar)

        print('other kwargs:', kw)

        if uhdas_cfg is None:
            self.uhdas_cfg = UhdasConfig(cfgpath=cfgpath,
                                    cruisename=cruisename,
                                    uhdas_dir=uhdas_dir_override,
                                    sonar=sonar, **kw)
        else:
            self.uhdas_cfg = uhdas_cfg

        if verbose:
            print('cfgpath = ', self.uhdas_cfg.cfgpath)
            print('cruisename = ', self.uhdas_cfg.cruisename)
            print('sonar', self.uhdas_cfg.sonar)
            print('ibadbeam', ibadbeam)


        ## add this: there were changes due to adding --pingpref
        pingtype =  self.sonar.pingtype
        pingavg_params = self.uhdas_cfg.get_pingavg_params(pingtype = pingtype)
        self.uhdas_cfg.pingavg_params = pingavg_params


        if hasattr(self.uhdas_cfg, 'hcorr'):
            self.uhdas_cfg.pingavg_params['hcorr'] = self.uhdas_cfg.hcorr
            # we want to use hcorr if we can
            self.uhdas_cfg.pingavg_params.apply_hcorr = True


        self.yearbase = self.uhdas_cfg.yearbase

        # initialize, then override editing parameters
        editparams=ping_editparams(self.sonar)
        # override from file
        try:
            cc = Cachefile(cachefile=editparams_file)
            cc.read()
            editparams.update_values(cc.cachedict)
        except OSError:
            msg = 'could not read singleping parameters in %s' % (
                editparams_file)
            _log.debug(msg)

        # override from kwargs
        if editparams_override:
            editparams.update_values(editparams_override)

        if verbose:
            _log.debug('singleping editing parameters:')
            for k in editparams.keys():
                if int(editparams[k]) == float(editparams[k]):
                    _log.debug('%20s : %d', k, editparams[k])
                else:
                    _log.debug('%20s : %f', k, editparams[k])

        if not os.path.exists(self.uhdas_cfg.rawsonar):
            raise IOError('cannot find raw data at %s' % (self.uhdas_cfg.rawsonar))
        if not os.path.exists(self.uhdas_cfg.gbinsonar):
            raise IOError('cannot find gbin data at %s' % (self.uhdas_cfg.gbinsonar))

        self.pinger = Pinger(datadir   = self.uhdas_cfg.rawsonar,
                       gbinsonar       = self.uhdas_cfg.gbinsonar,
                       sonar           = self.sonar,
                       edit_params     = editparams,
                       params          = self.uhdas_cfg.pingavg_params ,
                       yearbase        = self.uhdas_cfg.yearbase,
                       ibadbeam        = ibadbeam,
                       beam_index      = beam_index
                       )

        if verbose:
            self.list_chunks()

    #------------------------------------------

    def list_configs(self):
        #         self.pinger.mr.list_configs()
        print("# index (ping, NCells, CellSize, Blank, Pulse) nfiles")
        for confnum, conf in enumerate(self.pinger.mr.conflist):
            numconfs = len(self.pinger.mr.confdict[conf])
            print('%5d    ' % (confnum,), self.conf_fmt % (conf), ' n=%4d' % (numconfs,))


    #---------
    def list_chunks(self, dayfmt='decimal'):
        ''' similar to list_configs()
        pingtype comes from sonar
        dayfmt is 'decimal' (zero-based yearday) or 'ascii' (ymdhms)

        '''
        if dayfmt not in ('decimal', 'ascii'):
            raise ValueError('must specify "decimal" or "ascii" for dayfmt')

        pingtype = self.sonar.pingtype
        if self.sonar.model in ('wh', 'bb'):
            chunks = self.pinger.mr.chunks
        elif self.sonar.model == 'nb':
            chunks = self.pinger.mr.chunks
        else: # 'os'
            if pingtype == 'bb':
                chunks = self.pinger.mr.bbchunks
            elif pingtype == 'nb':
                chunks = self.pinger.mr.nbchunks
            else:
                _log.debug('problem with ping type')

        if hasattr(self.pinger.mr, 'bs'):
            ss= 'nfiles, [u_dday0,u_dday1] (reboot) '
            print('# index (ping, NCells, CellSize, Blank, Pulse) ' + ss)
            for chunknum, chunk in enumerate(chunks):
                confs = self.pinger.mr.confs[chunk][0]  #??
                if pingtype in confs[0]:
                    conf = confs[0]
                elif len(confs) == 2 and pingtype in confs[1]:
                    conf = confs[1]
                else:
                    conf = []

                if len(conf) > 0:
                    startdd = self.pinger.mr.bs.starts[chunk]['u_dday'][0]
                    enddd = self.pinger.mr.bs.ends[chunk]['u_dday'][-1]
                    if dayfmt == 'decimal':
                        ddstr = ' [%5.3f, %5.3f]' % (startdd, enddd)
                    else:
                        y,m,d,hh,mm,ss =  to_date(self.yearbase, startdd)
                        start_ymdhms = self.ymdhms_fmt % (y,m,d,hh,mm,ss)
                        y,m,d,hh,mm,ss = to_date(self.yearbase, enddd)
                        end_ymdhms =  self.ymdhms_fmt % (y,m,d,hh,mm,ss)
                        ddstr = ' [%s to %s]' % (start_ymdhms, end_ymdhms)

                    if len(np.diff(
                        self.pinger.mr.bs.starts[chunk]['m_dday'])) > 0:
                        reboot = ''
                    else:
                        reboot = ' * '
                    nchks = len(chunk)
                    print(chunknum, '      ', self.conf_fmt % (conf), '  n=%4d' % (nchks,),  ddstr, reboot)
                else:
                    print('(none)')

        else:
            print("# index (ping, NCells, CellSize, Blank, Pulse) nfiles")
            for chunknum, chunk in enumerate(self.pinger.mr.chunks):
                conf = self.pinger.mr.confs[chunknum][0]
                print(chunknum, '  ', self.conf_fmt % (conf), '  n=%4d' % (len(chunk)))




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



def plot_pings(ens, flags, figs=None):
    '''
    ens comes from Pinger or Pingavg
    '''
    #-------------------
    # plot masks

    if figs is None:
        fig1=plt.figure()
        fig2=plt.figure()
        fig3=plt.figure()
    else:
        fig1, fig2, fig3 = figs
        plt.figure(num=fig1.number); plt.clf()
        plt.figure(num=fig2.number); plt.clf()
        plt.figure(num=fig3.number); plt.clf()


    plotnums = np.arange(8)
    ax1 = []
    ax1.append(fig1.add_subplot(421))
    for pp in 1+plotnums[1:]:
        num = int('42'+str(pp))
        ax1.append(fig1.add_subplot(num, sharex=ax1[0]))

    plotnum = 0
    for name in flags.names:
        aa=ax1[plotnum]
        qpc(flags.tomask(names=[name]), ax=aa)
        if plotnum < 6:
            aa.xaxis.set_visible(False)
            aa.text(.1,.1, name, transform=aa.transAxes, color='w')
        plotnum+=1


    aa=ax1[plotnum]
    aa.plot(ens.best.heading,'o-')
    aa.text(.1,.1, 'heading', transform=aa.transAxes, color='k')
    plt.draw()

    bboxf = ax1[0].get_position()
    bboxh = ax1[-1].get_position()
    ax1[-1].set_position([bboxh.x0, bboxh.y0, bboxf.width, bboxf.height])

    #-------------------
    # plot values

    plotnums = np.arange(6)
    ax2 = []
    ax2.append(fig2.add_subplot(321))
    for pp in 1+plotnums[1:]:
        num = int('32'+str(pp))
        ax2.append(fig2.add_subplot(num, sharex=ax2[0]))


    plotnum=0
    for name in ['amp1_orig','amp1']:
        aa=ax2[plotnum]
        qpc(getattr(ens, name), ax=aa, clim=[20,250])
        aa.xaxis.set_visible(False)
        aa.text(.1,.1, name, transform=aa.transAxes, color='w')
        plotnum+=1


    for name in ['u','v']:
        aa=ax2[plotnum]
        qpc(getattr(ens, name), ax=aa)
        aa.xaxis.set_visible(False)
        aa.text(.1,.1, name, transform=aa.transAxes, color='k')
        plotnum+=1


    for name in ['w','e']:
        aa=ax2[plotnum]
        qpc(1000*getattr(ens, name), ax=aa, clim=[-1000,1000])
        aa.text(.1,.1, name, transform=aa.transAxes, color='k')
        plotnum+=1

    #-------------------
    # plot time series


    ax3 = []
    ax3.append(fig3.add_subplot(141))
    ax3.append(fig3.add_subplot(142))
    ax3.append(fig3.add_subplot(122))

    plotnum=0
    for name in ['cor1', 'amp1']:
        aa=ax3[plotnum]
        aa.plot(getattr(ens, name).T, np.arange(ens.nbins))
        aa.set_ylim(aa.get_ylim()[-1::-1])
        aa.text(.05,.95, name, transform=aa.transAxes, color='k')
        plotnum+=1

    aa=ax3[plotnum]
    aa.plot(ens.best.lon, ens.best.lat,'.-')
    aa.plot(ens.best.lon[:2], ens.best.lat[:2],'go')
    aa.plot(ens.best.lon[-2:], ens.best.lat[-2:],'r.')
    aa.plot(ens.best.lon[-2:], ens.best.lat[-2:],'rx')
    aa.text(.1,.1, 'position', transform=aa.transAxes, color='k')
    aa.set_xlabel('lon')
    aa.set_ylabel('lat')
    aa.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    aa.yaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    plt.draw()
    plotnum+=1

    return fig1, fig2, fig3

#----------------------------------------


class Pinger(pingavg.Pingavg):

    def __init__(self, pgcutoff=30, **kw):
        pingavg.Pingavg.__init__(self, update=False, dryrun=True, **kw)
        # This does some unnecessary things for present purposes,
        # but they don't hurt anything.  update=False is
        # presently the default, but we are making it
        # explicit here for safety.
        self.read_inputs()
        s, e = self.mr.chunk_ranges()
        self.dday_start = s[0]
        self.dday_end = e[-1]
        self.dday_starts = s
        self.dday_ends = e
        self._dday0 = self.dday_start
        self._nseconds = 120
        self._profs = None
        self.pgcutoff = pgcutoff

    def get_profs(self):
        if self._profs is None:
            p = self.get_pings()
            self._profs = p
        return self._profs

    profs = property(get_profs)

    def set_dday0(self, val):
        self._dday0 = max(self.dday_start, val)
        self._profs = None

    def get_dday0(self):
        return self._dday0

    dday0 = property(get_dday0, set_dday0)

    def set_nseconds(self, val):
        self._nseconds = val
        self._profs = None

    def get_nseconds(self):
        return self._nseconds

    nseconds = property(get_nseconds, set_nseconds)

    def set_ndays(self, val):
        self.set_nseconds(val/86400.0)

    def get_ndays(self):
        return self.nseconds / 86400.0

    ndays = property(get_ndays, set_ndays)

    def forward(self):
        self.dday0 += self.ndays
        self.dday0 = min(self.dday0, self.dday_end - self.ndays)
                        # This may need options for how to handle
                        # running off the end.

    def back(self):
        self.dday0 -= self.ndays

    def amp_mask(self, amp):

        """
        amp = Nprofs x Nbins x Nbeams
        inst is 'os', 'bb', 'wh', 'nb'

        returns (cleaned_amp, mask)
        # mask is same shape as amp and includes vertical slide for velocity
        """
        # don't change the original
        a = amp.copy()
        athresh = self.edit_params.ampfilt
        if self.sonar.isa("os"):
            a[:,-1] = a[:,-2]  # Old OS bug...
        amask = np.zeros(a.shape, bool)
        if a.shape[0] > 2:
            aa = a.astype(np.int16)
            amed = np.empty(a.shape, dtype=np.int16)
            amed[1:-1] = (aa[:-2] + aa[2:])//2
            amed[0] = (aa[1] + aa[2])//2
            amed[-1] =  (aa[-2] + aa[-3])//2
            amask = (aa - amed) > athresh
            # now clean amp
            np.putmask(a, amask, amed.astype(np.uint8))
            # vertical slide for velocity masking
            amask[:,1:-1] |= (amask[:,:-2] | amask[:,2:])
            amask[:,0] |= amask[:,1]
        return a, amask


    def get_pings(self, start_dday=None, nsecs=None):
        """
        Returns [ens, avg],
        ens is an augmented version of the ensemble
                for the present time range.
        avg is an augmented version of result of averaging)
        if nsecs>0, default to starting at dday[0], going forward
        if nsecs<0, default to starting at dday[-], going backward
        """
        ddrange=[0,0]
        if start_dday is None:
            if nsecs > 0:
                ddrange[0] = self.dday0
            else:
                ddrange[1] = self.dday_end
        else:
            if nsecs > 0:
                ddrange[0] = start_dday # go forward
            else:
                ddrange[1] = start_dday # go backward
        if nsecs > 0:
            ddrange[1] = ddrange[0] + nsecs/86400.
        else:
            ddrange[0] = ddrange[1] + nsecs/86400.    #nsecs < 0


        # overwrite variables:
        start_dday, stop_dday = ddrange
        print('Pinger.get_pings: start_dday=%f, stop_dday=%f' % (start_dday, stop_dday))

        self.ens_secs = np.abs(nsecs)
        ich = np.searchsorted(self.dday_ends, start_dday)
        ich = max(0, ich)
        ich = min(ich, len(self.mr.chunks) - 1)
        self.mr.select_chunk(ich)
        chunk = self.mr
        self.have_bt = chunk.bt[0]
        tr = [start_dday, stop_dday]
        chunk.set_range(tr)

        ppd = chunk.read()
        if ppd is None:
            _log.debug("Empty segment: %f %f, chunk %d", tr[0], tr[1], ich)
            return None

        self.ens = ppd
        self.ens.dep += self.params.tr_depth
        avg = Bunch() # We need this near for hcorr and edit.
                      # Otherwise, it would be at the start of average().
        self.avg = avg
        self.average_scalars() # HPR; heading is needed by hcorr
                               # for ens_hcorr_asc
        self.rotate()


        self.ens.umeas_orig = self.ens.u.copy()
        self.ens.vmeas_orig = self.ens.v.copy()
        self.ens.amp_orig = self.ens.amp.copy()

        self.edit()
        self.average()

        ## augment, and give different names; easier to remember
        self.ens.amp1_orig = self.ens.amp1_orig.copy()
        self.ens.utc = self.ens.times.dday
        self.ens.umeas = self.ens.vs['u']
        self.ens.vmeas = self.ens.vs['v']
        self.ens.w = self.ens.vs['w']
        self.ens.e = self.ens.vs['e']

        self.ens.lon   = self.ens.best.lon
        self.ens.lat   = self.ens.best.lat
        ## overwrite heading with 'best'.  This is a data product
        self.ens.heading = self.ens.best.heading
        self.ens.heading_corrected = self.ens.heading - self.dh
        self.ens.uship, self.ens.vship = get_uvship(self.ens.utc,
                                          self.ens.lon,
                                          self.ens.lat,
                                          method='centered')
        self.ens.uvel = self.ens.umeas + self.ens.uship[:, np.newaxis]
        self.ens.vvel = self.ens.vmeas + self.ens.vship[:, np.newaxis]
        self.ens.spd, self.ens.cog = navcalc.spd_cog_from_uv(self.ens.uship,
                                                             self.ens.vship)
        self.ens.bt_umeas=self.ens.bt_uv[:,0]
        self.ens.bt_vmeas=self.ens.bt_uv[:,1]
        self.ens.fmeas, self.ens.pmeas = calculate_fp(self.ens.umeas,
                                      self.ens.vmeas, self.ens.heading)
        self.ens.fvel, self.ens.pvel = calculate_fp(self.ens.uvel,
                                                    self.ens.vvel,
                                                    self.ens.heading)

        # more are available

        avg = Bunch()
        self.avg.utc = self.ens.utc[-1]
        amp = Stats(self.ens.amp,axis=0).mean
        self.avg.amp1 = amp[:,0]
        self.avg.amp2 = amp[:,1]
        self.avg.amp3 = amp[:,2]
        self.avg.amp4 = amp[:,3]

        # u,v at this stage are measured
        self.avg.umeas = self.avg.u.copy()
        self.avg.vmeas = self.avg.v.copy()
        ## check about xducerxy here...
        self.avg.uship = Stats(self.ens.uship).mean
        self.avg.vship = Stats(self.ens.vship).mean
        # use these names for ocean velocities; overwrite u,v
        self.avg.u = self.avg.umeas + self.avg.uship
        self.avg.v = self.avg.vmeas + self.avg.vship
        self.avg.u.mask |= (self.avg.pg < self.pgcutoff)
        self.avg.v.mask |= (self.avg.pg < self.pgcutoff)
        self.avg.lon = self.ens.lon[-1]
        self.avg.lat = self.ens.lat[-1]
        self.avg.dep = self.ens.dep
        self.avg.last_heading = self.ens.heading[-1]
        self.avg.last_heading_corrected = self.ens.heading_corrected[-1]
        self.avg.fmeas, self.avg.pmeas = calculate_fp(self.avg.umeas,
                                            self.avg.vmeas,
                                            self.avg.last_heading_corrected)
        self.avg.fvel, self.avg.pvel = calculate_fp(self.avg.u, self.avg.v,
                                             self.avg.last_heading_corrected)

        ## BREAKING API; I don't think this is being used.
        #return ens, avg

    def delete_oldfiles(self):
        """
        Override pingavg method with a dummy so we don't need to have
        a loaddir.
        """
        pass
