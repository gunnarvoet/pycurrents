'''
Class to average reference layer velocities for plotting
'''

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

from pycurrents.codas import get_profiles         # general codasdb reader
from pycurrents.num import Stats            # mean,std,med (masked)
from pycurrents.num import Runstats               # running statistics
from pycurrents.num import rangeslice     # subsampling (slice)
from pycurrents.num import interp1           # interpolation
from pycurrents.system import Bunch          # handling dictionaries


class Refl:
    def __init__(self, dbpath, varnames, zrange=None, ddrange=None):
        '''
        get data from dbpath (guess_db); kwargs passed to get_profiles)
        '''
        if zrange is None:
            zrange = [50,130]
        self.zrange = zrange
        self.data = get_profiles(dbpath, diagnostics=True, ddrange=ddrange)
        self.dday = self.data.dday
        self._izsl = rangeslice(self.data.dep, zrange[0], zrange[1])
        self.ref = Bunch()
        for var in varnames:
            self.ref[var] = self.get_ref(var)
    #
    def get_ref(self,varname):
        S=Stats(getattr(self.data, varname)[:,self._izsl], axis=1)
        return S.mean


def get_refdiff(ref1, ref2, varnames, onstation=2):
    '''
    return ref2-ref1 difference for varnames
    '''
    rdiff = Bunch()
    rdiff.dday = ref1.dday
    for var in varnames:
        ref1_ = ref1.ref[var]
        ref2_ = interp1(ref2.dday, ref2.ref[var], rdiff.dday)
        rdiff[var] = ref2_ - ref1_
    rdiff['mask'] = ref1.data.spd < onstation  #True when on station
    return rdiff

def get_refangle(ref1, ref2, onstation=2):
    '''
    return difference in measured velocities (angle)
    '''
    rdiff_angle = Bunch()
    rdiff_angle.dday = ref1.dday
    rangle1 = 90-180*np.angle(ref1.ref['umeas'] + 1j*ref1.ref['vmeas'])/np.pi
    rangle2 = 90-180*np.angle(ref2.ref['umeas'] + 1j*ref2.ref['vmeas'])/np.pi
    #
    rangle1_ = rangle1
    rangle2_ = interp1(ref2.dday, rangle2, rdiff_angle.dday)
    rdiff_angle.diff = np.ma.masked_where(ref1.data.spd < onstation, rangle2_ - rangle1_)
    nani=np.where(np.isnan(rdiff_angle.diff))[0]
    rdiff_angle.diff.mask[nani] = True
    return rdiff_angle

def get_refrat(ref1, ref2, onstation=2):
    '''
    return ref2/ref1 ratio for fmeas
    '''
    refrat = Bunch()
    refrat.dday = ref1.dday
    ref1_ = ref1.ref['fmeas']
    ref2_ = interp1(ref2.dday, ref2.ref['fmeas'], refrat.dday)
    refrat.fmeas = np.ma.masked_array(ref2_/ref1_, mask=ref1.data.spd < onstation)
    return refrat

def mtext(x,y,tstr, ax=None, **kwargs):
    '''
    text in [0,1,0,1] coordinates)
    '''
    if ax is None:
        ax = plt.gca()
    ax.text(x,y,tstr, transform = ax.transAxes, **kwargs)

colors=Bunch(u='r',
             v='b',
             fvel='m',
             pvel='c')

def mid(x):
    return (x[0:-1]+x[1:])/2

#===================================

def plot_uv2(R1, R2, rdiff, vars, names=None, title=None, nwin=33):
    f,ax=plt.subplots(figsize=(8,10),nrows=4, sharex=True)
    v0=vars[0] #name
    v1=vars[1] #name
    c0=colors[v0]
    c1=colors[v1]
    if names is None:
        name1 = 'data1'
        name2= 'data2'
    else:
        name1, name2 = names
    zrange = R1.zrange
    #
    ax[0].plot(R1.dday, R1.ref[v0], color=c0, alpha=0.5, mec='none')
    ax[0].plot(R2.dday, R2.ref[v0], 'k.', ms=2)
    ax[0].hlines(0, rdiff.dday[0], rdiff.dday[-1], 'k', lw=2)
    ax[0].grid(True)
    ax[0].set_ylim([-.5,.5])
    ax[0].set_xlabel('decimal day')
    #
    ax[1].plot(R1.dday, R1.ref[v1], c1, alpha=0.5, mec='none')
    ax[1].plot(R2.dday, R2.ref[v1], 'k.', ms=2)
    ax[1].hlines(0, rdiff.dday[0], rdiff.dday[-1], 'k', lw=2)
    ax[1].grid(True)
    ax[1].set_ylim([-.5,.5])
    ax[1].set_xlabel('decimal day')
    #
    ax[2].plot(rdiff.dday, rdiff[v0], '.', color=c0, ms=1)
    ax[2].plot(rdiff.dday, rdiff[v1], '.', color=c1, ms=1)
    #
    ax[2].plot(rdiff.dday, Runstats(rdiff[v0],nwin=nwin).median, c0)
    ax[2].plot(rdiff.dday, Runstats(rdiff[v1],nwin=nwin).median, c1)
    ax[2].hlines(0, rdiff.dday[0], rdiff.dday[-1], 'k', lw=1)
    ax[2].grid(True)
    ax[2].set_ylim([-.1,.1])
    ax[2].set_xlabel('decimal day')
    #
    ax[3].plot(rdiff.dday, R1.data.heading, 'g.', ms=2)
    ax[3].set_xlabel('decimal day')
    ax[3].grid(True)
    mtext(.95,.9,'HEADING',ax=ax[3], ha='right',size='small',color='g')
    #
    ax[3].set_xlim(rdiff.dday[0], rdiff.dday[-1])
    ax2=plt.twinx(ax=ax[3])
    ax2.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax2.plot(rdiff.dday, R1.data.uship, 'r')
    ax2.plot(rdiff.dday, R1.data.vship, 'b')
    ax2.set_ylim(-7,7)
    # add ship speed
    for aa in ax[:-1]:
        ax2=plt.twinx(ax=aa)
        ax2.plot(rdiff.dday, R1.data.spd, 'y.', ms=2)
        ax2.set_ylim(0,7)
        ax2.set_xlim(rdiff.dday[0], rdiff.dday[-1])
    #
    mtext(.01,.9,'ocean %s (%s)' % (v0, name1), ax=ax[0], color=c0, weight='bold')
    mtext(.01,.05,'ocean %s (%s)' % (v0, name2), ax=ax[0], color='k', weight='bold')
    mtext(.01,.9,'ocean %s (%s)' % (v1, name1), ax=ax[1], color=c1, weight='bold')
    mtext(.01,.05,'ocean %s (%s)' % (v1, name2), ax=ax[1], color='k', weight='bold')
    mtext(.01,.9,' ocean %s diff (%s-%s)' % (v0, name2, name1), ax=ax[2], color=c0, weight='bold')
    mtext(.01,.05,' ocean %s diff (%s-%s)' % (v1, name2, name1), ax=ax[2], color=c1, weight='bold')
    mtext(.01,.9, 'uship', ax=ax[3], color='r', weight='bold')
    mtext(.01,.05,'vship', ax=ax[3], color='b', weight='bold')
    mtext(.99,.9, 'ship speed', ax=ax[0], color='y', ha='right', weight='bold')
    mtext(.99,.9, 'ship speed', ax=ax[1], color='y', ha='right', weight='bold')
    mtext(.99,.9, 'ship speed', ax=ax[2], color='y', ha='right', weight='bold')
    if title is not None:
        f.text(.5,.95,title, ha='center')
    f.text(.1,.02,'nwin=%d' % (nwin))
    f.text(.1,.04,'zrange=%d-%d' % (zrange[0], zrange[1]))
    ax[0].xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax2.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    plt.draw()
    return f

def plot_fpstats(R1, R2, refdiff, refrat, rdiff_angle, names=None, title=None,
                 nwin=33, rscale=4, zrange=None):
    '''
    ratio only makes sense with fmeas
    plot refl2/refl1 fmeas, and refl2-refl1 pabs
    '''
    if zrange is None:
        zrange = [50,130]

    print('======> NOTE ABOUT CALIBRATIONS <=======')
    print('\nIf there was a reason to apply a calibration ')
    print('to %s for it to better match  %s, ' % (names[1], names[0]))
    print('these are APPROXIMATE values to use.')
    print('Use these as if they came from cal/watertrk or cal/botmtrk.')


    ylimrat=(-rscale*.002, rscale*.002)
    ylimdiff=(-rscale*.05, rscale*.05) #center it later
    ylimangle=(-rscale*.5, rscale*.5) #center it later
    f=plt.figure(figsize=(11,7))
    ax=[]
    ax.append(f.add_subplot(4,1,1))
    ax.append(f.add_subplot(4,1,2))
    ax.append(f.add_subplot(2,3,4))
    ax.append(f.add_subplot(2,3,5))
    ax.append(f.add_subplot(2,3,6))

    #underway fwd ratio
    medscale = Stats(refrat.fmeas.compressed()).median
    ax[0].plot(refrat.dday, refrat.fmeas, 'm.', ms=1)
    ax[0].hlines(1, refrat.dday[0], refrat.dday[-1], 'k', lw=2)
    ax[0].grid(True)
    ax[0].set_ylim(ylimrat+medscale)
    ax[0].set_xlim(refrat.dday[0], refrat.dday[-1])

    # underway port diff
    refdiffpma = np.ma.masked_array(refdiff.pvel, refdiff.mask)
    refdiff_median = Stats(refdiffpma).median
    ax[1].plot(refdiff.dday, refdiffpma, 'c.', ms=1)
    ax[1].hlines(0, refdiff.dday[0], refdiff.dday[-1], 'k', lw=2)
    ax[1].grid(True)
    ax[1].set_ylim(refdiff_median + np.array(ylimdiff))
    ax[1].set_xlim(refrat.dday[0], refrat.dday[-1])

    # histogram of ratio
    medscale = Stats(refrat.fmeas.compressed()).median
    h,b = np.histogram(refrat.fmeas.compressed(), bins=40,range=ylimrat+medscale)
    xx=np.array([.99, 1.01, 1.01, .99, .99])
    maxh = max(h)
    yy=np.array([0,      0,      maxh,       maxh,       0])
    yrect = 1.1*yy
    ax[2].fill(xx, yrect,color='0.95')
    ax[2].plot(np.array([1,1]), np.array([0,1.1*maxh]),'k')
    ax[2].plot(mid(b), h, 'm.-')
    ax[2].grid(True)
    ax[2].set_xlabel('scale factor')
    print('\n     scale factor:f    %5.3f     to  %s ' % (1/medscale, names[1], )) ##!! reciprocal
    #

    # histogram of port diff
    medportdiff = Stats(refdiffpma.compressed()).median
    h,b = np.histogram(refdiffpma.compressed(), bins=40,range=ylimdiff+medportdiff)
    xx=np.array([-.05, .05, .05, -.05, -.05])
    maxh = max(h)
    yy=np.array([0, 0, maxh, maxh, 0])
    yrect = 1.1*yy
    ax[3].fill(xx, yrect,color='0.95')
    ax[3].plot(np.zeros((2)), np.array([0,1.1*maxh]),'k')
    ax[3].plot(mid(b), h, 'c.-')
    ax[3].grid(True)
    ax[3].set_xlabel('m/s difference')
    #
    # histogram of measured angle diff
    medangle = Stats(rdiff_angle.diff.compressed()).median
    h,b = np.histogram(rdiff_angle.diff.compressed(), bins=40, range=ylimangle+medangle)
    xx=np.array([-.5, .5, .5, -.5, -.5])
    maxh = max(h)
    yy=np.array([0, 0, maxh, maxh, 0])
    yrect = 1.1*yy
    ax[4].fill(xx, yrect,color='0.95')
    ax[4].plot(np.zeros((2)), np.array([0,1.1*maxh]),'k')
    ax[4].plot(mid(b), h, 'b.-')
    ax[4].grid(True)
    ax[4].set_xlabel('angle (degrees)')
    print('     rotation angle:  %4.2fdeg   to  %s ' % (medangle, names[1], ))
    print("================")

    #
    for num in [0,2]:
        mtext(.01,.9,'fmeas ratio ', ax=ax[num], color='m', weight='bold')
        if names is not None:
            mtext(.01, .75, '%s/%s' % (names[1], names[0]), ax=ax[num], color='m', weight='bold')

    for num in [1,3]:
        mtext(.01,.9,'pmeas diff ', ax=ax[num], color='c', weight='bold')
        if names is not None:
            mtext(.01, .75, '%s-%s' % (names[1], names[0]), ax=ax[num], color='c', weight='bold')

    for num in [4,]:
        mtext(.01,.9,'measured velocity angle diff ', ax=ax[num], color='b', weight='bold')
        if names is not None:
            mtext(.01, .75, '%s-%s' % (names[1], names[0]), ax=ax[num], color='b', weight='bold')

    f.text(.05,.02,'zrange=%d-%d' % (zrange[0], zrange[1]))
    if title is not None:
        f.text(.5,.95,title + ' (underway statistics)', ha='center')
    plt.draw()

    return f


def plot_angle(refdiff, rdiff_angle, names=None, title=None, nwin=33,):
    '''
    plot angle between measured velocities
    '''
    f,ax = plt.subplots(figsize=(12,5))
    #transducer angle
    ax.plot(rdiff_angle.dday, rdiff_angle.diff,'.')
    ax.grid(True)
    ax.set_ylim([-1.5,1.5])
    ax.set_xlim(rdiff_angle.dday[0], rdiff_angle.dday[-1])
    ax.set_title('transducer angle difference')
    ax.set_xlabel('dday')
    ax.set_ylabel('degrees')
    mtext(.01,.2,'measured velocity angle diff ', ax=ax,
          color='b', weight='bold')
    if names is not None:
        mtext(.01, .1, '%s-%s' % (names[1], names[0]), ax=ax,
              color='b', weight='bold')

    #
    if title is not None:
        f.text(.5,.95,title + ' (transducer angle difference)', ha='center')
    plt.draw()
    return f
