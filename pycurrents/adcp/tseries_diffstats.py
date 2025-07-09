'''
Tools to assemble and plot timeseries statistics, stored in CODAS database
    as TSERIES_DIFFSTATS:

Background:

Each ensemble average profile is generated using refavg, which returns
- a profile (goes into CODAS as u or v)
- a timeseries ("u_ts", "v_ts" ;zero mean) of offsets for the profiles
- an error matrix (minimized residual from creation of profile and timeseries)

TSERIES_DIFFSTATS is the variance of diff(u_ts) , i.e. (diff(u_ts)**2).mean()
for each ensemble

This program plots standard error of the mean for these timeseries diffs,
as well as error velocity (similarly scaled),  ship speed, and number of pings
per ensemble.  There is also a method to print summary statistics.

'''

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import logging

from pycurrents.codas import DB, get_profiles
from pycurrents.codas import to_datestring
from pycurrents.system.misc import Bunch
from pycurrents.num.nptools import rangeslice     # subsampling (slice)
from pycurrents.num import Stats            # mean,std,med (masked)
from pycurrents.data import navcalc  # uv_from_txy, unwrap_lon, unwrap ...

# Standard logging
_log = logging.getLogger(__name__)


def get_data(dbname, ndays=None, startdd=None):
    alldata=get_profiles(dbname)
    #
    data = Bunch()
    if startdd is None:
        rs=rangeslice(alldata.dday, ndays)
    else:
        if ndays is None:
            ndays = alldata.dday[-1] - alldata.dday[0] + 1 #get the rest
        rs=rangeslice(alldata.dday, startdd, startdd+ndays)
    #
    db = DB(dbname)

    # If this variable doesn't exist, let the exception be caught and handled
    # by the calling code.
    tsds =  db.get_variable('TSERIES_DIFFSTATS')

    data.tsds_uu = tsds[rs,0]  ## (diff(u_ts)**2).mean()
    data.tsds_uv = tsds[rs,1]  ## (diff(u_ts)*diff(v_ts)).mean()
    data.tsds_vv = tsds[rs,2]  ## (diff(v_ts)**2).mean()
    data.tsds_N  = tsds[rs,3]  ## diff(u_ts).count()

    data.dday = alldata.dday[rs]
    data.yearbase = alldata.yearbase
    data.pg = alldata.pg[rs,:]
    ulon = navcalc.unwrap(alldata.lon)
    uship, vship = navcalc.uv_from_txy(alldata.dday,
                                       ulon, alldata.lat, pad=True)
    spd = np.ma.hypot(uship, vship)
    data.spd = spd[rs]
    #
    ancil1 = db.get_variable('ANCILLARY_1')
    data.npings = ancil1['pgs_sample'][rs]
    estd = db.get_variable('EV_STD_DEV')
    data.estd=estd[rs]
    ## timeseries stats (variance if diff(u_ts))
    #
    return data


def get_stats(data):
    sd=Bunch()    # stats of data
    sd.dday = data.dday
    sd.yearbase=data.yearbase
    sd.Sn = Stats(data.npings)
    sd.Snts = Stats(data.tsds_N)
    ### Standard Error sqrt(var)/sqrt(N) scaled by sqrt(2) because of the "diff"
    sd.SEM_u = np.sqrt(data.tsds_uu)/np.sqrt(2*data.tsds_N)
    sd.SEM_v = np.sqrt(data.tsds_vv)/np.sqrt(2*data.tsds_N)
    sd.Sju = Stats(sd.SEM_u)
    sd.Sjv = Stats(sd.SEM_v)
    #
    estdma = np.ma.masked_where(data.estd==0, data.estd)
    sd.estd_mean = Stats(estdma,axis=1).mean/np.sqrt(data.tsds_N) # SEM=same scaling?
    sd.Se = Stats(sd.estd_mean)
    return sd


def plot_data(data, titlestr=None):
    sd = get_stats(data)
    #
    f,ax=plt.subplots(figsize=(7,9), nrows=3, ncols=1, sharex=True)
    #
    ax[0].plot(data.dday, data.tsds_N, 'k.', ms=3)
    ax[0].plot(data.dday, data.npings, 'g.')
    ax[0].set_ylim([0, np.max(data.npings)+5])
    ax[0].xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
    ax[0].text(.5, 1.03, 'num pings per ensemble ', ha='right', color='g',
               size=14, transform = ax[0].transAxes)
    ax[0].text(.5, 1.03, ' (num pings per ts_stats)', ha='left', color='k',
               size=14, transform = ax[0].transAxes)
    #
    ax2=plt.twinx(ax[0])
    yellow = np.array([0.5, 0.4, 0])
    ax2.plot(data.dday, data.spd, '.',color=yellow, ms=2)
    ax2.set_ylabel('ship speed, m/s', color=yellow)
    ax2.tick_params('y', colors=yellow)
    #
    #
    ax[1].plot(data.dday, sd.estd_mean, 'k.')
    ax[1].set_ylim([0, .16])
    ax[1].grid(True)
    ax[1].text(.95,.90,'std(errvel)/sqrt(N)', ha='right',
               transform = ax[1].transAxes, color='k')
    #
    gray=.8*np.array([1,1,1])
    ax[2].plot(data.dday, sd.estd_mean, '.', color=gray)
    ax[2].plot(data.dday, sd.SEM_u, 'm.', ms=4)
    ax[2].plot(data.dday, sd.SEM_v, 'c+', ms=4)
    ax[2].set_ylim([0, .16])
    ax[2].grid(True)
    # #mean(diff(uts)^2)/sqrt(2*N)
    ax[2].text(.05,.90,'u timeseries SEM', transform = ax[2].transAxes, color='m')
    ax[2].text(.05,.80,'v timeseries SEM', transform = ax[2].transAxes, color='c')
    ax[2].text(.95,.90,'std(errvel)/sqrt(N)', ha='right',
               transform = ax[2].transAxes, color=gray)
    if titlestr is not None:
        f.text(.5, .95, titlestr, ha='center')
    #
    ax[0].set_xlim(data.dday[0], data.dday[-1])
    ax[-1].set_xlabel('decimal day')
    return f, ax, sd


def stats_str(sd):
    s = []
    s.append('time range: %s to %s (%7.3f to %7.3f)' % (to_datestring(sd.yearbase, sd.dday[0]),
                                                        to_datestring(sd.yearbase, sd.dday[-1]),
                                                        sd.dday[0], sd.dday[-1]))
    s.append('')
    s.append('                              mean      stddev  ')
    s.append('u timeseries SEM)         :   %4.3f     %4.3f   ' % (sd.Sju.mean, sd.Sju.std))
    s.append('v timeseries SEM)         :   %4.3f     %4.3f   ' % (sd.Sjv.mean, sd.Sjv.std))
    s.append('std(errvel)/sqrt(N)       :   %4.3f     %4.3f   ' % (sd.Se.mean,  sd.Se.std))
    s.append('')
    s.append('pings per ensemble        :  %4.0f       %4.0f  ' % (sd.Sn.mean,  sd.Sn.std))
    s.append('number of good in tseries :  %4.0f       %4.0f  ' % (sd.Snts.mean,  sd.Snts.std))
    s.append('')
    return '\n'.join(s)


def hplot(ax, xlow, xhigh, m, s, **kw):
    '''
    ax.hlines(m, xlow, xhigh,   lw=2, color=color)
    ax.hlines(m+s, xlow, xhigh, lw=1, color=color)
    ax.hlines(m-s, xlow, xhigh, lw=1, color=color)
    '''
    ax.hlines(m, xlow, xhigh,    lw=2, **kw)
    ax.hlines(m+s, xlow, xhigh,  lw=2, linestyles='dotted', **kw)
    ax.hlines(m-s, xlow, xhigh,  lw=2, linestyles='dotted', **kw)


### see pycurrents.scripts for calling
