''' This was an attempt to make automated at-sea diagnostic
plots that would help identify electrical noise.  Didn't really
work that well.  Might be broken.  See 2014/07/29 changeset
in this directory for missing pieces, if there is an interest
in resurrecting it, and if it is broken.
'''

import time
import os

import logging
import numpy as np
#matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import Ellipse

from pycurrents.codas import to_day, to_date
from pycurrents.adcp.qplot import  qpc
from pycurrents.adcp.adcp_specs import cor_clim, amp_clim, vel_clim
from pycurrents.adcp.raw_multi import Multiread
from pycurrents.num import Stats
from pycurrents.adcp.qplot import textfig

# Standard logging
_log = logging.getLogger(__name__)


def beam_prof(data, yearbase, new_enough=2, titlestr=None, plot_bincol=False,
              climdict=None, ellinfo=None, experimental=True):
    '''
    plot profiles of  amp, cor, vel for each beam

      * recommend only 5-10 profles
      * used by uhdas.scripts.plot_beamdiagnostics

    **call signature**

    ``beam_prof(data, yearbase, new_enough=2, titlestr=None, plot_bincol=False, climdict=None, ellinfo=None)``

    *args*

       * *data* : from Multiread
       * *yearbase* : yearbase (for correct time on title)

    *kwargs*

       * *new_enough* : do not plot if end of data is older than this (hrs)
       * *plot_bincol* : plot horizontal lines at specific bins
                (meant to match bins used in beam_bints)
       * *climdict* : dictionary of plot limits for 'amp', 'cor', 'vel'
       * *ellinfo* = [x,y,width,height] to show high deep correlation (bad)

    *returns*

       * age of most recent data, in hours

    '''

    #dictionary of [binnum, color] for amp, cor, vel (marker)
    # presently hardwired to match defaults for beam_bints
    bincol = (
        (10, 'magenta'),
        (-10, 'darkblue')
        )

    proceed = True
    retval = None
    if climdict is None:
        climdict = {}

    if data is None or len(data) == 0 :
        proceed = False
        message = 'no data found'

    if proceed is True:
       #sstr = 'plot generated at %s' %(time.asctime(time.gmtime()),)
        dd=to_date(yearbase, data.dday[-1])

        ymdhms_str = '%4d/%02d/%02d %02d:%02d:%02d' % (
            dd[0],dd[1],dd[2],dd[3],dd[4],dd[5])
        data_sec = (np.datetime64(str(yearbase), "Y") +
                        np.timedelta64(int(data.dday[-1] * 86400), "s"))
        now_sec = np.datetime64(int(time.time()), "s")
        age_hours = (now_sec - data_sec).astype(float)/3600.
        retval = age_hours

        _log.debug('age_hours = %2.1f' % (age_hours))
        if age_hours < new_enough:
            proceed = True

            tstr = 'ADCP end dday, date: %s, %2.2f, (%2.1f hrs ago)' % (
                ymdhms_str, data.dday[-1], age_hours)
        else:
            proceed = False
            message = 'no recent data found\nage = %2.1f hours'%(age_hours,)
    if proceed is False:
        fig = textfig(message)
        if titlestr is not None:
            ax=fig.add_subplot(111)
            ax.set_title(titlestr)
        return retval

    # proceeding
    fig=plt.figure(figsize=(6,9))
    fig.text(.5,.05, tstr, ha='center', va='top')

    colors = ['r','g','b','k']
    variables = {'amp': 'amplitude',
                 'cor': 'correlation',
                 'vel': 'beam \nvelocity'}
    varspecs =  {'amp': (.9, .15, 'right'),
                 'cor': (.05, .9, 'left'),
                 'vel': (.02, .5, 'left')}
    plotvars = []
    for var in ['amp', 'cor', 'vel']:  #keep this order;
        if hasattr(data, var):
            plotvars.append(var)

    #-----  plots -----
    numplots = len(plotvars)

    for plotnum in np.arange(numplots):
        var = plotvars[plotnum]
        ax=fig.add_subplot(numplots, 1, plotnum+1)
        if var == 'cor' and ellinfo is not None:
            elx, ely, width, height = ellinfo
            ell = Ellipse(xy=(elx,ely), width=width, height=height,angle=0)
            ell.set_clip_box(ax.bbox)
            ell.set_alpha(0.4)
            ell.set_color('r')
            ax.add_artist(ell)
            ax.text(elx, .95*data.dep[-1],
                    'BAD CORR', color='r', ha='center', va='center', size=14)

        for bnum in range(4):
            aa = getattr(data, var)
            ax.plot(aa[:,:,bnum].T, data.dep, color=colors[bnum])
        ax.set_ylim(ax.get_ylim()[-1::-1])
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=7))
        if var in list(climdict.keys()):
            xlim = climdict[var]
        else:
            xlim = ax.get_xlim()
        ax.set_xlim(xlim)
        if plotnum == 0 and titlestr is not None:
            ax.set_title(titlestr)
        if var == 'vel':
            ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(
                           nbins=7, symmetric=True))
        if plot_bincol:
            xlim = ax.get_xlim()
            for ibin in np.arange(len(bincol)):
                binnum, cval = bincol[ibin]
                plt.plot(xlim, [data.dep[binnum],data.dep[binnum]], color=cval,
                         linewidth=2)
        ax.set_xlim(xlim)
        ax.set_ylabel('depth, meters')
        ax.set_ylim(max(data.dep),0)
        xtext, ytext, align = varspecs[var]
        ax.text(xtext, ytext, variables[var], transform = ax.transAxes,
                 ha=align, size=20)

        if experimental is True:
            fig.text(.5,.5,'EXPERIMENTAL',ha='center',va='center',
                  alpha=0.05,color='k',fontsize=60,rotation=50)

    plt.draw()
    return retval


def beam_bints(data, yearbase, bins=[5, -5], new_enough=2, titlestr=None,
               climdict=None, experimental=True):
    '''
    plot amp, cor, vel for each beam as a timeseries

        * best for up to several hundred timestamps, 1-3 specific bins.
        * used by uhdas.scripts.plot_beamdiagnostics

    **call signature**

    ``beam_bints(data, yearbase, bins=[5, -5], new_enough=2, titlestr=None,climdict=None)``


    *args*

       * *data* : from Multiread
       * *yearbase* : yearbase (for correct time on title)

    *kwargs*

       * *bins* : list of (presently two) shallow and deep bins to plot
       * *new_enough*:  do not plot if end of data is older than this (hrs)
       * *titlestr* : title for plot
       * *climdict* : dictionary of plot limits for 'amp', 'cor', 'vel'


    *returns*

       * age of most recent data, in hours

    '''

    proceed = True
    retval = None

    if climdict is None:
        climdict = {}


    if data is None or len(data) == 0 :
        proceed = False
        message = 'no data found'

    if proceed is True:
       #sstr = 'plot generated at %s' %(time.asctime(time.gmtime()),)
        dd=to_date(yearbase, data.dday[-1])
        ymdhms_str = '%4d/%02d/%02d %02d:%02d:%02d' % (
            dd[0],dd[1],dd[2],dd[3],dd[4],dd[5])
        data_sec = (np.datetime64(str(yearbase), "Y") +
                        np.timedelta64(int(data.dday[-1] * 86400), "s"))
        now_sec = np.datetime64(int(time.time()), "s")
        age_hours = (now_sec - data_sec).astype(float)/3600.

        retval = age_hours

        _log.debug('age_hours = %2.1f' % (age_hours))
        if age_hours < new_enough:
            proceed = True

            tstr = 'ADCP end dday, date: %s, %2.2f, (%2.1f hrs ago)' % (
                ymdhms_str, data.dday[-1], age_hours)
        else:
            proceed = False
            message = 'no recent data found\nage = %2.1f hours'%(age_hours,)
    if proceed is False:
        fig = textfig(message)
        if titlestr is not None:
            ax=fig.add_subplot(111)
            ax.set_title(titlestr)
        return retval

    # proceeding
    mins  = (data.dday[-1] - data.dday) * 60 * 24
    xlim = (mins[0], mins[-1])
    depths = []
    for binnum in bins:
        depths.append(data.dep[binnum])

    #should make a colormap based on bins and choose using binnums
    # colors = ('magenta', 'darkblue', 'brown') color by bin
    colors = ['r','g','b','k'] #color by beam

    beamsymbols = (
        ('|','2','3','4'),
        ('o','d','p', 'h'),
        ('v','<','>','^'),
        )
    fig=plt.figure(figsize=(6,9))
    fig.text(.5,.05, tstr, ha='center', va='top')

    #-----  correlation -----
    ax1=fig.add_subplot(211)
    if 'cor' in data:
        for ibin in range(len(bins)):
            bbsymbols = beamsymbols[ibin]
            for ibeam in range(4):
                ax1.plot(mins, data.cor[:, bins[ibin], ibeam],
                         bbsymbols[ibeam], color=colors[ibeam])
    if 'cor' in list(climdict.keys()):
        ylim = climdict['cor']
    else:
        ylim = ax1.get_ylim()
    ax1.set_ylim(ylim)

    ax1.set_xticklabels([])
    ax1.set_xlim(xlim)
    ax1.text(.9, .7, 'correlation', transform=ax1.transAxes,
              size=20, ha='right', color='m')
    ax1.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=7))
    ax1.set_ylabel('COR units')
    ax1.grid(True)

    #-----  velocity -----
    ax2=fig.add_subplot(212, sharex=ax1)
    for ibin in range(len(bins)):
        bbsymbols = beamsymbols[ibin]
        for ibeam in range(4):
            ax2.plot(mins, data.vel[:, bins[ibin], ibeam],
                     bbsymbols[ibeam], color=colors[ibeam])

    if 'cor' in list(climdict.keys()):
        ylim = climdict['cor']
    else:
        ylim = ax2.get_ylim()
    ax2.set_xlim(ylim)

    ax2.set_ylim(-5,5)
    ax2.set_xlim(xlim)
    ax2.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=7))
    ax2.set_xlabel('minutes before data end')
    ax2.text(.9, .9, 'beam velocity', transform=ax2.transAxes,
              size=20, ha='right',  color='m')
    ax2.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=5))
    ax2.set_ylabel('m/sec')
    ax2.grid(True)


    if titlestr is not None:
        fig.text(.5,.95, titlestr, ha='center', va='top')

    if experimental is True:
        fig.text(.5,.5,'EXPERIMENTAL',ha='center',va='center',
             alpha=0.05,color='k',fontsize=60,rotation=50)

    plt.draw()
    return retval


def beam_pcolor(data, name, yearbase, new_enough=2, titlestr=None,
                clim=None):
    '''
    make a 4-panel pcolor plot of correlation, amplitude, beam velocity

      * recommend not more than 200 profiles, (all depths used)
      * used by uhdas.scripts.plot_beamdiagnostics

   **call signature**

    ``beam_pcolor(data, name, yearbase, new_enough=2, titlestr=None, clim=None)``

    *args*

       * *data* : from Multiread
       * *name* : 'amp', 'cor', 'vel' -- field to plot
       * *yearbase* : yearbase (for correct time on title)

    *kwargs*

       * *new_enough*:  do not plot if end of data is older than this (hrs)
       * *titlestr* : title for plot
       * *clim* : color limits for the variable being plotted

    *returns*

       * age of most recent data, in hours

    '''

    proceed = True
    retval = None

    if data is None or len(data) == 0 :
        proceed = False
        message = 'no data found'


    if proceed is True:
       #sstr = 'plot generated at %s' %(time.asctime(time.gmtime()),)
        dd=to_date(yearbase, data.dday[-1])
        ymdhms_str = '%4d/%02d/%02d %02d:%02d:%02d' % (
            dd[0],dd[1],dd[2],dd[3],dd[4],dd[5])
        data_sec = (np.datetime64(str(yearbase), "Y") +
                        np.timedelta64(int(data.dday[-1] * 86400), "s"))
        now_sec = np.datetime64(int(time.time()), "s")
        age_hours = (now_sec - data_sec).astype(float)/3600.
        retval = age_hours

        _log.debug('age_hours = %2.1f' % (age_hours))
        if age_hours < new_enough:
            proceed = True

            tstr = 'ADCP end dday, date: %s, %2.2f, (%2.1f hrs ago)' % (
                ymdhms_str, data.dday[-1], age_hours)
        else:
            proceed = False
            message = 'no recent data found\nage = %2.1f hours'%(age_hours,)
    if proceed is False:
        fig = textfig(message)
        if titlestr is not None:
            ax=fig.add_subplot(111)
            ax.set_title(titlestr)
        return retval

    #proceeding

    ylim = [len(data.dep), 0]
    fig=plt.figure(figsize=(6,9))
    fig.text(.5,.05, tstr, ha='center', va='top')

    mins  = (data.dday[-1] - data.dday) * 60 * 24
    xlim = (mins[0], mins[-1])

    var = data.get(name[:3])  #amp, cor, vel
    if var is None:
        _log.warning('field %s not in data' % (name,))


    axes_list=[]
    for count in range(4):
        axes_list.append(fig.add_subplot(4,1,count+1))

    for count in range(4):
        beamnum = count+1
        ax=axes_list[count]
        plt.sca(ax)
        qpc(var[:,:,count], profs=mins, clim=clim, ax=ax)
        ax.set_ylim(ylim)
        ax.set_xlim(xlim)
        ax.set_title('beam %d' % (beamnum,))
        if beamnum <= 3:
            ax.set_xticklabels([])
        ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=5))
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=7))


    if titlestr is not None:
        fig.text(.5,.95, titlestr, ha='center', va='top', size=14)

    plt.draw()


def beam_stats_byfile(filelist, inst, pingtype, yearbase=None, maxnum=24):
    '''
    get historical statistics for correlation and velocity by file

    **call signature**

    ``beam_stats_byfile(filelist, inst, pingtype, yearbase=None, maxnum=24)``

    *args*

      * *filelist* :



    return statistics (mean, stddev, num) in a dictionary, for: amp, vel, cor
    '''

    #deal with this
    if yearbase is None:
        logging.debug("Yearbase in plotraw.py was None")
        dd=time.gmtime()
        nowdday = int(to_day(dd[0],dd[0],dd[1],dd[2],0,0,0))
        yearbase=int(dd[0])
        logging.debug(f"nowdday = {nowdday} and yearbase = {yearbase}")


    shortlist=[]
    numbins = 0


    for ifile in np.arange(len(filelist)):
        fname = filelist[-ifile-1]
        _log.debug('%s, size=%d' % (fname, os.path.getsize(fname)))

        if os.path.getsize(fname) > 0:
            m=Multiread(fname, inst[:2])
            if inst[:2] in ('os', 'pn', 'ec'):
                pingtypes = m.pingtypes[0] #one file in list
                if pingtype in list(pingtypes.keys()):
                    m.select(pingtypes[pingtype])
            else:
                m.select(0)

            data=m.read(ends=1)

            numbins = max(numbins, len(data.dep))
            shortlist.append(fname) # newest is first


    # 3-d
    if len(shortlist) == 0:
        raise IOError('no data found')

    ampmean = np.ma.zeros((len(shortlist), numbins, 4), float)
    cormean = np.ma.zeros((len(shortlist), numbins, 4), float)
    velmean = np.ma.zeros((len(shortlist), numbins, 4), float)

    ampstd = np.ma.zeros((len(shortlist), numbins, 4), float)
    corstd = np.ma.zeros((len(shortlist), numbins, 4), float)
    velstd = np.ma.zeros((len(shortlist), numbins, 4), float)

    ampnum = np.ma.zeros((len(shortlist), numbins, 4), float)
    velnum = np.ma.zeros((len(shortlist), numbins, 4), float)
    cornum = np.ma.zeros((len(shortlist), numbins, 4), float)

    enddd =  np.zeros((len(shortlist)), float)
    numbins =  np.zeros((len(shortlist)), int)

    _log.info('found %d files' % (len(shortlist)))

    for ff in shortlist:
        print(os.path.split(ff)[-1])

    for ifile in np.arange(len(shortlist)):
        fname = shortlist[-ifile-1] #read in reverse
        m=Multiread(fname, inst[:2])
        if inst[:2] in ('os', 'pn', 'ec'):
            pingtypes = m.pingtypes[0] #one file in list
            if pingtype in list(pingtypes.keys()):
                m.select(pingtypes[pingtype])
        else:
            m.select(0)

        try:
            data=m.read()
        except:
            print('failed %s' % (fname))
            continue

        nprofs, ndepth, nbeams = data.amp.shape
        enddd[ifile] = data.dday[-1]
        numbins[ifile]=ndepth

        S = Stats(data.amp, axis=0)
        ampmean[ifile, :ndepth, :nbeams] = S.mean
        ampstd[ifile, :ndepth, :nbeams] = S.std
        ampnum[ifile, :ndepth, :nbeams] = S.N
        S = Stats(data.cor, axis=0)
        cormean[ifile, :ndepth, :nbeams] = S.mean
        corstd[ifile, :ndepth, :nbeams] = S.std
        cornum[ifile, :ndepth, :nbeams] = S.N
        S = Stats(data.vel, axis=0)
        velmean[ifile, :ndepth, :nbeams] = S.mean
        velstd[ifile, :ndepth, :nbeams] = S.std
        velnum[ifile, :ndepth, :nbeams] = S.N

    # nfiles x nbins x nbeams
    stats_dict = {'ampmean' : ampmean,
                  'ampstd'  : ampstd,
                  'ampnum'  : ampnum,
                  'cormean' : cormean,
                  'corstd'  : corstd,
                  'cornum'  : cornum,
                  'velmean' : velmean,
                  'velstd'  : velstd,
                  'velnum'  : velnum,
                  'numbins' : numbins,
                  'enddd'   : enddd}

    return stats_dict

def plot_cor_byfile(stats_dict, procdirname):
    '''
    plot correlation history (statistics) by file
    stats_dict comes from  beam_stats_byfile
    '''

    ampmean = stats_dict['ampmean']
    #ampstd = stats_dict['ampstd']
    #ampnum  = stats_dict['ampnum']
    cormean = stats_dict['cormean']
    #corstd  = stats_dict['corstd']
    #cornum  = stats_dict['cornum']
    #velmean = stats_dict['velmean']
    #velstd  = stats_dict['velstd']
    velnum  = stats_dict['velnum']
    enddd   = stats_dict['enddd']



    ff=plt.figure()
    ff.add_subplot(321)
    qpc(ampmean[:,:60,2],profs=enddd,
        clim=amp_clim[procdirname[:2]])
    ax=plt.gca()
    ax.text(.05,.05,'AMP3',color='w',transform=ax.transAxes,)

    ff.add_subplot(322)
    qpc(velnum[:,:60,2],profs=enddd)
    ax=plt.gca()
    ax.text(.05,.05,'NUMpts',color='w',transform=ax.transAxes,)

    ##--- correlation -----
    ff.add_subplot(323)
    qpc(cormean[:,:60,0],profs=enddd,
        clim=cor_clim[procdirname])
    ax=plt.gca()
    ax.text(.05,.05,'COR1mean',color='w',transform=ax.transAxes,)


    ff.add_subplot(324)
    qpc(cormean[:,:60,1],profs=enddd,
        clim=cor_clim[procdirname])
    ax=plt.gca()
    ax.text(.05,.05,'COR2std',color='w',transform=ax.transAxes,)


    ff.add_subplot(325)
    qpc(cormean[:,:60,2],profs=enddd,
        clim=cor_clim[procdirname])
    ax=plt.gca()
    ax.text(.05,.05,'COR3mean',color='w',transform=ax.transAxes,)


    ff.add_subplot(326)
    qpc(cormean[:,:60,3],profs=enddd,
        clim=cor_clim[procdirname])
    ax=plt.gca()
    ax.text(.05,.05,'COR4std',color='w',transform=ax.transAxes,)


    plt.draw()

    #------

def plot_velPG_byfile(stats_dict, procdirname,experimental=True):
    '''
    plot velocity and correlation statistics in shallow and deep bins
    stats_dict comes from  beam_stats_byfile
    '''


    #ampmean = stats_dict['ampmean']
    ampnum  = stats_dict['ampnum']
    cormean = stats_dict['cormean']
    #corstd  = stats_dict['corstd']
    velmean = stats_dict['velmean']
    #velstd  = stats_dict['velstd']
    velnum  = stats_dict['velnum']
    enddd   = stats_dict['enddd']

    sbin = 5
    dbin = -5

    xlims=[enddd[0], enddd[-1]]

    ff=plt.figure(figsize=(6,8))
    ax1=ff.add_subplot(311)
    colors = ['r','g','b','k']
    for beam in np.arange(4):
        plt.plot(enddd, velmean[:,sbin,beam], '-', color=colors[beam])
        plt.plot(enddd, velmean[:,dbin,beam], '.', color=colors[beam])

    ax1.set_title('beam velocity')
    ax1.set_ylim(-4,4)
    ax1.set_ylabel('m/s')
    ax1.set_xticklabels([])
    ax1.set_xlim(xlims)

    ax2=ff.add_subplot(312)
    colors = ['r','g','b','k']
    for beam in np.arange(4):
        plt.plot(enddd, cormean[:,sbin,beam], '-', color=colors[beam])
        plt.plot(enddd, cormean[:,dbin,beam], '.', color=colors[beam])

    ax2.set_title('correlation')
    ax2.set_ylim(cor_clim[procdirname])
    ax2.set_ylabel('units')
    ax2.set_xticklabels([])
    ax1.set_xlim(xlims)


    ax3=ff.add_subplot(313)
    colors = ['r','g','b','k']
    for beam in np.arange(4):
        plt.plot(enddd, 100*velnum[:,sbin,beam]/ampnum[:,sbin,beam],
                 '-', color=colors[beam])
        plt.plot(enddd, 100*velnum[:,dbin,beam]/ampnum[:,dbin,beam],
                 '.', color=colors[beam])

    ax3.set_title('percent good samples per dataset')
    ax3.set_ylabel('percent')
    ax3.set_ylim(-1,101)
    ax1.set_xlim(xlims)


    ff.text(.5,.03,'solid = bin(5th from top)\n deep = bin(5th from bottom)',
             ha='center')

    if experimental is True:
        ff.text(.5,.5,'EXPERIMENTAL',ha='center',va='center',
             alpha=0.05,color='k',fontsize=60,rotation=50)


    plt.draw()



def statslist(stats_dict, beamnum=3, binnum=5):
    '''
    generate a summary list of strings suitable for printing

    *args*

      * *stats_dict* : comes from  beam_stats

    *kwargs* (for statistical summary)

      * *beamnum* : beam to use
      * *binnum* : deep bin number

    *returns*:

      * list of strings suitable for printing

    '''

    int_names = ( 'beamnum', 'binnum', 'velnum', 'ampnum')
    float_names = ('velmean', 'velstd', 'cormean', 'corstd')


    binstats = {}
    binstats['enddd'] = stats_dict['enddd']
    binstats['numbins'] = stats_dict['numbins']
    numfiles, numbins, numbeams = stats_dict['ampmean'].shape

    binstats['beamnum'] = np.zeros(numfiles, dtype=int)+beamnum
    if binnum >= 0:
        binstats['binnum'] = np.zeros(numfiles, dtype=int) + binnum
    else:
        binstats['binnum'] = binstats['numbins'] + binnum - 1


    for name in int_names[2:]:
        binstats[name] =  np.zeros(numfiles, dtype=int)
        for ii in np.arange(numfiles):
            binstats[name][ii] = stats_dict[
                name][ii,binstats['binnum'][ii],beamnum-1]

    for name in float_names:
        binstats[name] =  np.zeros(numfiles, dtype=float)
        for ii in np.arange(numfiles):
            binstats[name][ii] = stats_dict[
                name][ii,binstats['binnum'][ii],beamnum-1]

    ## now generate the info to be printed
    header = '%7s %7s %7s' % ('# enddd', 'beamnum', 'binnum')
    for name in int_names[2:]:
        header += '%8s' % (name,)

    for name in float_names:
        header += '%8s' % (name,)


    dlist = []
    for fnum in np.arange(numfiles):
        dstr = '%7.3f' % (binstats['enddd'][fnum],)
        for name in int_names:
            dstr =dstr + '%5d    ' % (binstats[name][fnum],)
        for name in float_names:
            dstr =dstr + ' %5.2f  ' % (binstats[name][fnum],)
        dlist.append(dstr)

    dlist.append('')

    return header, dlist



def plot_statsfile(procdirname, cruiseid='', experimental=True):
    '''
    read ascii stats file from beam_history ; plot

    *args*

      * *procdirname* : instrument+pingtype: 'wh300','os75bb',...

    *kwargs*

      * *cruiseid* : figure title is (cruiseid + procdirname)

    '''

    fname = '%s_stats.txt' % (procdirname,)


    (enddd, beamnum, binnum, velnum, ampnum, velmean, velstd,
     cormean, corstd) = np.loadtxt(fname, skiprows=2, unpack=True, comments='#')

    fig=plt.figure(figsize=(6,9))
    allpg = 100.*velnum/ampnum

    xlim = [min(enddd), max(enddd)]


    colors=['r','g','b','k']

    ax1=fig.add_subplot(311)
    for ii in [0,1,2,3]:
        ax1.plot(enddd[ii::8], velmean[ii::8], '.', color=colors[ii])
        #
        pg = allpg[(ii+4)::8]
        edd = enddd[(ii+4)::8]
        vm = velmean[(ii+4)::8]
        for jj in np.arange(len(pg)):
            if pg[jj] > 30:
                ax1.plot(edd[jj], vm[jj], 'o', color=colors[ii])
            else:
                ax1.plot(edd[jj], vm[jj], 'o', color=colors[ii],
                         markerfacecolor='none')

    ax1.set_ylim(vel_clim[procdirname[:2]])
    ax1.set_xlim(xlim)
    ax1.text(.05,.85,'beam velocity', transform=ax1.transAxes)


    ax2=fig.add_subplot(312)
    for ii in [0,1,2,3]:
        ax2.plot(enddd[ii::8], cormean[ii::8],'.'+colors[ii])
        ax2.plot([enddd[ii::8], enddd[ii::8]],
                  [cormean[ii::8]-corstd[ii::8], cormean[ii::8]+corstd[ii::8]],
                  colors[ii]+'.-')

        pg = allpg[(ii+4)::8]
        edd = enddd[(ii+4)::8]
        cm = cormean[(ii+4)::8]
        for jj in np.arange(len(pg)):
            if pg[jj] > 30:
                ax2.plot(edd[jj], cm[jj], 'o', color=colors[ii])
            else:
                ax2.plot(edd[jj], cm[jj], 'o', color=colors[ii],
                         markerfacecolor='none')

    ax2.set_ylim(cor_clim[procdirname])
    ax2.set_xlim(xlim)
    ax2.set_xticklabels([])
    ax2.text(.05,.5,'correlation', transform=ax2.transAxes)


    ax3=fig.add_subplot(313)
    for ii in [0,1,2,3]:
        ax3.plot(enddd[ii::8], allpg[ii::8], colors[ii]+'.')


        pg = allpg[(ii+4)::8]
        edd = enddd[(ii+4)::8]
        for jj in np.arange(len(pg)):
            if pg[jj] > 30:
                ax3.plot(edd[jj], pg[jj], 'o', color=colors[ii])
            else:
                ax3.plot(edd[jj], pg[jj], 'o', color=colors[ii],
                         markerfacecolor='none')

    ax3.set_ylim(-5,105)
    ax3.set_xlim(xlim)
    ax3.set_xlabel('decimal day, file end')
    ax3.text(.05,.5,'percent good (velocity)', transform=ax3.transAxes)

    fig.text(.5,.95, cruiseid+' '+procdirname, ha='center')
    if experimental is True:
        fig.text(.5,.5,'EXPERIMENTAL',ha='center',va='center',
             alpha=0.05,color='k',fontsize=60,rotation=50)

    plt.draw()
