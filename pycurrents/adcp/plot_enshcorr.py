'''
plot ens_hcorr.asc for perusal, reports, or web site
'''

import logging

import numpy as np
import matplotlib.pyplot as plt

from pycurrents.system.misc import guess_comment

_log = logging.getLogger(__name__)

class HcorrPlotter:
    def __init__(self, medfilt_halfwin = 31):

        self.medfilt_win = 2*medfilt_halfwin + 1

    def get_data(self, hcorr_ascfile, skiplines=0):
        comment = guess_comment(hcorr_ascfile)
        self.hcorr = np.loadtxt(hcorr_ascfile,comments=comment, skiprows=skiplines)
        _log.info('found %d values' % (len(self.hcorr)))

        self.hdict = {
            'idday'    : 0,
            'ihead_m'  : 1,
            'ihead_l'  : 2,
            'idh'      : 3,
            'istd'     : 4,
            'indh'     : 5,
            'ibad'     : 6}

        ibad  = self.hdict['ibad']
        idh   = self.hdict['idh']
        istd   = self.hdict['istd']
        idday =  self.hdict['idday']
        self.dday = self.hcorr[:,idday]
        self.t = self.dday #for 'echo' callback
        self.dh = self.hcorr[:,idh]
        self.dhstd = self.hcorr[:,istd]
        self.dh_masked_original =  np.ma.masked_where(
            self.hcorr[:,ibad]==1, self.hcorr[:,idh])
        self.bad_ddranges = []

        #dh1 = np.ma.masked_where(self.hcorr[:,ibad]>0, self.hcorr[:,idh])
        self.dh_origmasked = np.ma.masked_where(self.hcorr[:,ibad]==1,
                                             self.hcorr[:,idh])


    def make_plots(self, titlestring=''):
        """ Redraws the figure
        """

        # clear the axes and redraw the plot anew
        #

        #idday    = self.hdict['idday']
        ihead_m  = self.hdict['ihead_m']
        #ihead_l  = self.hdict['ihead_l']
        idh      = self.hdict['idh']
        #istd     = self.hdict['istd']
        indh     = self.hdict['indh']
        #ibad     = self.hdict['ibad']

        self.fig, self.ax = plt.subplots(nrows=3, figsize=(10,10), sharex=True)
        self.xlim = [self.dday[0], self.dday[-1]]
        _log.info('dday range %f5.2 - %f5.2' % (self.dday[0], self.dday[-1]))

        ## heading
        self.ax[0].plot(self.dday,self.hcorr[:,indh],'m.')
        self.ax[0].text(.25,0.10, 'number good',
                              ha='right',color='m', size='large',
                              transform=self.ax[0].transAxes)
        self.ax[0].set_ylabel('number')
        self.ax[0].grid(True)
        num60 = np.max(np.floor(self.hcorr[:,indh]/60))+1
        self.ax[0].set_ylim(0,60*(num60+1))  # ymax is a multiple of 60
        ## number good
        self.ax[1].plot(self.dday,
                              np.remainder(self.hcorr[:,ihead_m], 360),'b.')
        self.ax[1].text(.25, 0.10, 'mean heading',
                              ha='right',color='b', size='large',
                              transform=self.ax[1].transAxes)
        self.ax[1].set_ylim(-5,365)
        self.ax[1].set_ylabel('degrees')
        self.ax[1].grid(True)
        ## heading correction
        self.ax[2].plot(self.dday, self.hcorr[:,idh], 'r.')
        self.ax[2].plot(self.dday, self.dh_origmasked, 'k.')
        self.ax[2].text(.5, 0.9, 'heading correction used in ADCP processing',
                              ha='center',color='k', size='large',
                              transform=self.ax[2].transAxes)

        self.ax[2].text(.25, 0.25, 'BAD', ha='right',color='r', size='large',
                              transform=self.ax[2].transAxes)
        self.ax[2].text(.25, 0.10, 'GOOD', ha='right',color='k', size='large',
                              transform=self.ax[2].transAxes)
        self.ax[2].set_ylabel('degrees')
        self.ax[2].grid(True)


        avglen = np.median(86400*np.diff(self.dday))/60.  # minutes
        cstr = '%2.1f' % (avglen)
        tstr = 'heading correction from processing\n (edited, %s minute chunks)' % (cstr)
        if titlestring != '':
            tstr = '%s\n%s' % (titlestring, tstr)
        self.fig.text(.5, 0.92, tstr, ha='center', size='large')
