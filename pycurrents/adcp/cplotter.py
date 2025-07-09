"""
This was originally in adcpgui/cplotter.py and included CData and subclasses.
With the move to adcpgui_qt, everything but the CPlotter class became no longer
needed here.  This version of CPlotter is still used outside adcpgui_qt.
"""
import logging
import numpy as np
import matplotlib as mpl
import matplotlib.patheffects as PathEffects
from matplotlib.ticker import ScalarFormatter

from pycurrents.adcp._plot_tools import clims, jet_cmapdict, alt_cmapdict, titles

# Standard logging
_log = logging.getLogger(__name__)

#names of panels variables and their output to the screen
heading = 'heading, spd'
jitter  = 'jitter, spd'
numpings  = 'numpings, spd'
tr_temp = 'tr_temp, spd'

formatter = ScalarFormatter(useOffset = False)


class CPlotter:
    def __init__(self, fig=None, axdict=None):

        self.clims = clims.copy()
        self.fig = fig
        self.axdict = axdict

    def draw_ax(self, CDdata, axnum, name,
                      speed=False, jittercutoff=None,
                      annotation='',
                      use_cbarjet=False, sonar='', set_bad='w'):
        '''
        pcolor + colorbar, with speed on it also (if True)
        '''
        pax=self.axdict['pcolor'][axnum]
        cax=self.axdict['cbar'][axnum]
        tax=self.axdict['twinx'][axnum]

        pax.cla()
        cax.cla()
        tax.cla()
        cax.set_visible(False)

        if name == 'clear':
            self.clear_ax(pax, tax)
        elif name == jitter:
            self.draw_jitter(pax, CDdata, axnum, jittercutoff)
        elif name in (heading, numpings, tr_temp):
            self.draw_misc(pax, CDdata, axnum, name)
        else:
            data = getattr(CDdata.data, name)
            if use_cbarjet:
                cmapdict = jet_cmapdict
            else:
                cmapdict = alt_cmapdict

            if sonar =='diff':
                clim = self.clims['diff']
                cmap = cmapdict['diff']
                cmap.set_bad(set_bad)   #test cmap masking

            else:
                clim = self.clims[name]
                if use_cbarjet:
                    cmap=jet_cmapdict[name]
                else:
                    cmap=alt_cmapdict[name]
                cmap.set_bad(set_bad)   #test cmap masking


#            p = pax.pcolorfast(CDdata.xb, CDdata.yb, data.T,
            p = pax.pcolorfast(CDdata.Xirreg, CDdata.Yirreg, data.T,
                              cmap=cmap,
                              vmin=clim[0], vmax=clim[1])

            pax.set_ylabel(CDdata.yname, style='oblique', color='k')

            cbarloc = mpl.ticker.MaxNLocator(nbins=6, steps=[1, 2, 4, 5, 10])
            cbar = self.fig.colorbar(p, cax=cax, extend='both', ticks=cbarloc)
            cbar.ax.set_ylabel(titles[name], fontsize='10',
                               style='normal', color='k')
            cbar.ax.yaxis.set_label_position('left')

            if hasattr(CDdata, 'manual_mask'):
                # numpy bug - TODO
                pax.plot(CDdata.X[:-1, :-1][CDdata.manual_mask],
                         CDdata.Y[:-1, :-1][CDdata.manual_mask], 'k.', ms=2)

            pax.tick_params(axis='y', colors='k')
            pax.xaxis.set_major_formatter(formatter)
            tax.xaxis.set_major_formatter(formatter)
            pax.yaxis.set_major_formatter(formatter)
            pax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=9))
            pax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=6))
            #cax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=7))

            tax.yaxis.set_visible(False)
            cax.set_visible(True)

            pax.set_ylim(CDdata.ylim)
            pax.set_xlim(CDdata.xlim)
            # for "show next"
            self.show_spd(CDdata, axnum, name, speed)

        if axnum == len(self.axdict['pcolor'])-1:
            pax.xaxis.set_visible(True)
        else:
            pax.xaxis.set_visible(False)

        txt = pax.text(0.02, 0.03, '%s %s' % (sonar, annotation),
                       transform = pax.transAxes)
        txt.set_path_effects([PathEffects.withStroke(linewidth=3,
                              foreground="w")])

    def clear_ax(self, pax, tax):
        tax.yaxis.set_visible(False)
        pax.text(.5, .5, 'no data found', color='r', size=12,
                 transform=pax.transAxes, ha='center')

    def show_spd(self, CDdata, axnum, name, speed=False):
        tax=self.axdict['twinx'][axnum]
        if speed:
            if name in ['u','v','fvel','pvel', heading, jitter, numpings, tr_temp]:
                tax.plot(CDdata.data.dday,
                         CDdata.data.spd, 'g-')
                tax.yaxis.set_major_locator(
                    mpl.ticker.MaxNLocator(nbins=5, prune='upper'))
                if name not in  ['u','v','fvel','pvel']: #avoid collisions with colorbar
                    tax.set_ylabel('shipspd, m/s', color='g')
                tax.tick_params(axis='y', colors='g')
                tax.set_xlim(CDdata.xlim)
                tax.set_ylim(0,8)
                tax.yaxis.set_visible(True)
                tax.set_visible(True)
        else:
            if name in ['u','v','fvel','pvel']:
                tax.cla()
                tax.ticklabel_format(useOffset=False)
                #tax.xaxis.set_major_formatter(formatter)
                tax.yaxis.set_visible(False)


    def draw_misc(self, pax, CDdata, axnum, name):

        hmin = -180
        hrange = (hmin-10, hmin+360+10)
        npingrange = (0,320)
        tr_temp_range = None # temperature should autoscale

        if name == numpings:  #might not always have this?
            npingrange = (0, 1.1*np.max(CDdata.data.pgs_sample))  #better to have whole range
                     #             label         color style  pos     y_lim
        plt_param = {'shipspeed':('shipspd, m/s', 'g',  '-', 'right', (0, 8)),
                     heading :('heading',    'b',  '.', 'left',  hrange),
                     numpings :('NumPings',  'k',  '.', 'left',  npingrange),
                     tr_temp :('temperature', 'b',  '.', 'left',  tr_temp_range),
                     }

        opt = plt_param[name]
        pax.set_ylabel(opt[0], color=opt[1])
        pax.tick_params(axis='y', colors=opt[1])
        pax.yaxis.set_ticks_position(opt[3])
        pax.yaxis.set_label_position(opt[3])
        pax.set_xlim(CDdata.xlim)
        if opt[4]:
            pax.set_ylim(opt[4])
        pax.ticklabel_format(useOffset=False)

        if name == heading:
            self.show_spd(CDdata, axnum, name, speed=True)
#            data = wrap(CDdata.data.heading, min = 45)
            data = ((CDdata.data.heading - hmin+360) % 360) + hmin
        elif name == numpings:
            self.show_spd(CDdata, axnum, name, speed=True)
            data = CDdata.data.pgs_sample
        elif name == tr_temp:
            self.show_spd(CDdata, axnum, name, speed=True)
            data = CDdata.data.tr_temp
        else:
            data = CDdata.data.spd

        pax.plot(CDdata.data.dday, data, opt[1]+opt[2])


    def update_dday_marker(self, dday):
        """
        Mark start of single-ping data on pcolor plots.
        Set dday to None to remove the markers
        """
        if dday is None:
            for ax in self.axdict['pcolor']:
                for line in ax.lines:
                    if line.get_label() == "dday_marker":
                        line.remove()
            return

        x = np.array([dday, dday])
        for ax in self.axdict['pcolor']:
            have_markers = False
            for line in ax.lines:
                if line.get_label() == "dday_marker":
                    line.set_xdata(x)
                    have_markers = True

            if not have_markers:
                ax.axvline(x=dday, color='k', label="dday_marker")
