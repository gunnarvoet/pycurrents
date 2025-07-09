# N.B.: Based on legacy code pplotter.py
import numpy as np
from matplotlib.ticker import MaxNLocator
import matplotlib.patheffects as PathEffects
import matplotlib.artist as martist
from pycurrents.adcpgui_qt.lib.plotting_parameters import (CMAPDICT,
    CMAPDICT_CBLIND, LINE_SIZE, MARKER_SIZE, ScalarFormatter)


# FIXME - clean up this code...loads of redundant lines, params could be more global
def plot_pings(ens, flags,
               pingFlagFig, pingVelFig, pingProFig, beamVelFig,
               bad_color, bin=False, colorblind=False):
    """
    Set-up and draw single-ping plots

    Args:
        ens: ensemble from Pinger Object
        flags: flags from Pinger Object
        pingFlagFig: Matplotlib figure associated with "Ping Flags"
        pingVelFig: Matplotlib figure associated with "Ping Velocities"
        pingProFig: Matplotlib figure associated with "Ping Profiles"
        beamVelFig: Matplotlib figure associated with "Beam Velocities"
        bad_color: RGB color associated with bad values, tuple
                   ex.: (0.8, 0.8, 0.8)
        bin: boolean switch for Y-axis in bins or meters
        colorblind: boolean switch for colorblind friendly color scheme
    """
    # Clear figs
    pingFlagFig.clf()
    pingVelFig.clf()
    pingProFig.clf()
    beamVelFig.clf()
    # Plotting params
    # - Color maps
    # Set-up colorbar
    if colorblind:
        cmapdict = CMAPDICT_CBLIND
    else:
        cmapdict = CMAPDICT
    for cmap in cmapdict.values():
        cmap.set_bad(bad_color)   #test cmap masking
    cbarloc = MaxNLocator(nbins=5, steps=[1, 2, 4, 5, 10])
    # - Formatter
    formatter = ScalarFormatter(useOffset=False)
    # bin or depth on y axis
    if not bin:
        x = np.arange(ens.nprofs)
        y = ens.dep
        ylims = [ens.dep.max(), ens.dep.min()]
    else:
        y = np.arange(ens.nbins)
        ylims = [ens.nbins, 0]
    xlims = [0, ens.nprofs]

    # Ping flags
    # - orig., e., cor., amp., be., wp. and ra.
    ax1 = []
    ax1.append(pingFlagFig.add_subplot(5, 2, 1))
    # - sharing axis
    for ii, pp in enumerate(range(2, 11)):
        if ii == 6:  # heading's axis
            ax1.append(pingFlagFig.add_subplot(
                5, 2, pp, sharex=ax1[2]))
        else:  # others
            ax1.append(pingFlagFig.add_subplot(
                5, 2, pp, sharex=ax1[0], sharey=ax1[0]))
    for plotnum, name in enumerate(flags.names):
        aa = ax1[plotnum]
        oneflag = flags.tomask(names=[name])
        vals = np.unique(oneflag)
        if len(vals) == 1:
            aa.plot(oneflag[:, 0], '.',
                    ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
            aa.set_ylim([-1, 2])
            aa.set_xlim(xlims)
            title = aa.text(.5, .6, 'No Data', transform=aa.transAxes, ha='center',
                            color='r')
            title.set_path_effects(
                [PathEffects.withStroke(linewidth=3, foreground="w")])
        else:
            data = oneflag.T
            # Cannot deal with bool array anymore...makes figure.colorbar crash
            if 'bool' in str(data.dtype):
                data = data.astype(int)
            if not bin:
                pp = aa.pcolorfast(x, y, data, cmap=cmapdict['ping flag'])
            else:
                pp = aa.pcolorfast(data, cmap=cmapdict['ping flag'])
        title = aa.text(.1, .1, name, transform=aa.transAxes)
        title.set_path_effects(
            [PathEffects.withStroke(linewidth=3, foreground="w")])
        if plotnum < 6:
            aa.xaxis.set_visible(False)
            aa.set_ylabel('Depth', fontsize='small')
            aa.set_ylim(ylims)
            aa.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
        aa.set_xlim(xlims)
        if name == 'ra':
            aa.set_xlabel('Profile from "Ping start"')
            aa.xaxis.set_major_locator(MaxNLocator(integer=True))
    # - heading
    aa = ax1[7]
    aa.plot(ens.best.heading, 'o-', ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
    title = aa.text(.1, .1, 'heading', transform=aa.transAxes)
    title.set_path_effects(
        [PathEffects.withStroke(linewidth=3, foreground="w")])
    aa.set_xlabel('Profile from "Ping start"')
    aa.xaxis.set_major_locator(MaxNLocator(integer=True))
    aa.set_ylabel('deg.', fontsize='small')
    aa.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
    aa.grid()
    bboxf = ax1[0].get_position()
    bboxh = ax1[-1].get_position()
    ax1[-1].set_position([bboxh.x0, bboxh.y0, bboxf.width, bboxf.height])
    # - colorbar
    cb_ax = pingFlagFig.add_axes([0.95, 0.3, 0.02, 0.4])
    cbar = pingFlagFig.colorbar(pp, cax=cb_ax)
    cbar.set_ticks([0.25, 0.75])
    cbar.set_ticklabels(['0', '1'])
    title = cb_ax.set_title('flag number', fontsize='small', rotation=90,
                            x=0.5, y=0.6)
    title.set_path_effects(
        [PathEffects.withStroke(linewidth=3, foreground="w")])

    # Ping Velocities
    ax2 = []
    # shared axis with Ping flag
    ax2.append(pingVelFig.add_subplot(5, 2, 1, sharex=ax1[0], sharey=ax1[0]))
    for pp in range(2, 11):
        ax2.append(pingVelFig.add_subplot(5, 2, pp, sharex=ax2[0],
                                          sharey=ax2[0]))
    plotnum=0
    for name in ['amp1_orig', 'amp1']:
        aa = ax2[plotnum]
        if not bin:
            pp = aa.pcolorfast(x, y, getattr(ens, name).T,
                               cmap=cmapdict['amp'], vmin=20,  vmax=250)
        else:
            pp = aa.pcolorfast(getattr(ens, name).T,
                               cmap=cmapdict['amp'], vmin=20,  vmax=250)
        cbar = pingVelFig.colorbar(pp, ax=aa, extend='both', # aspect=30,
                                   shrink=0.8, ticks=cbarloc)
        cbar.outline.set_linewidth(0)
        aa.xaxis.set_visible(False)
        title = aa.text(.1, .1, name, transform=aa.transAxes)
        title.set_path_effects(
            [PathEffects.withStroke(linewidth=3, foreground="w")])
        aa.set_ylim(ylims)
        aa.set_xlim(xlims)
        aa.set_ylabel('Depth', fontsize='small')
        aa.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
        plotnum += 1
    for name in ['u', 'v', 'fvel']:  ## these are ocean velocities
        val=getattr(ens, name)
        orig = np.ma.masked_array(val.data, mask=flags.tomask(names=['orig']))
        aa = ax2[plotnum]
        if not bin:
            pp = aa.pcolorfast(x, y, orig.T,
                               cmap=cmapdict[name], vmin=-1, vmax=1)
        else:
            pp = aa.pcolorfast(orig.T, cmap=cmapdict[name], vmin=-1, vmax=1)
        cbar = pingVelFig.colorbar(pp, ax=aa, extend='both', # aspect=30,
                                   shrink=0.8, ticks=cbarloc)
        cbar.outline.set_linewidth(0)
        aa.xaxis.set_visible(False)
        title = aa.text(.1, .1, name + '(not flagged)', transform=aa.transAxes)
        title.set_path_effects(
            [PathEffects.withStroke(linewidth=3, foreground="w")])
        aa.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
        aa.set_ylim(ylims)
        aa.set_xlim(xlims)
        aa.set_ylabel('Depth', fontsize='small')
        plotnum += 1
        # now do masked
        aa = ax2[plotnum]
        if not bin:
            pp = aa.pcolorfast(x, y, getattr(ens, name).T,
                               cmap=cmapdict[name], vmin=-1, vmax=1)
        else:
            pp = aa.pcolorfast(getattr(ens, name).T,
                               cmap=cmapdict[name], vmin=-1, vmax=1)
        cbar = pingVelFig.colorbar(pp, ax=aa, extend='both', # aspect=30,
                                   shrink=0.8, ticks=cbarloc)
        cbar.outline.set_linewidth(0)
        aa.xaxis.set_visible(False)
        title = aa.text(.1,.1, name + '(flagged)', transform=aa.transAxes)
        title.set_path_effects(
            [PathEffects.withStroke(linewidth=3, foreground="w")])
        aa.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
        aa.set_ylim(ylims)
        aa.set_xlim(xlims)
        aa.set_ylabel('Depth', fontsize='small')
        plotnum += 1
    # - masked
    for name in ['w', 'e']:
        aa = ax2[plotnum]
        if not bin:
            pp = aa.pcolorfast(x, y, 1000 * getattr(ens, name).T,
                               cmap=cmapdict[name], vmin=-1000, vmax=1000)
        else:
            pp = aa.pcolorfast(1000*getattr(ens, name).T,
                               cmap=cmapdict[name], vmin=-1000,  vmax=1000)
        cbar = pingVelFig.colorbar(pp, ax=aa, extend='both', # aspect=30,
                                   shrink=0.8, ticks=cbarloc)
        cbar.outline.set_linewidth(0)
        title = aa.text(.1, .1, name, transform=aa.transAxes)
        title.set_path_effects(
            [PathEffects.withStroke(linewidth=3, foreground="w")])
        aa.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
        aa.set_ylim(ylims)
        aa.set_xlim(xlims)
        aa.set_xlabel('Profile from "Ping start"')
        aa.set_ylabel('Depth', fontsize='small')
        plotnum += 1

    # Ping Profiles
    a31 = pingProFig.add_subplot(141)
    a32 = pingProFig.add_subplot(142, sharey=a31)
    a33 = pingProFig.add_subplot(122)
    ax3 = [a31, a32, a33]

    plotnum=0
    name = 'amp1'
    aa = ax3[plotnum]
    aa.plot(getattr(ens, name).T, y, ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
    aa.grid()
    # aa.set_ylim(aa.get_ylim()[-1::-1])
    # aa.text(.05,.95, name, transform=aa.transAxes, color='k')
    aa.set_title(name)
    aa.xaxis.set_major_locator(MaxNLocator(4, prune='both'))
    aa.set_ylabel('Depth', fontsize='small', labelpad=-4)

    plotnum = 1
    name = 'pgood'
    aa = ax3[plotnum]
    aa.plot(
        np.round(100-100*np.sum(flags.tomask(names='all'), axis=0)/ens.nprofs),
        y, 'k.-', ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
    aa.set_ylim(aa.get_ylim()[-1::-1])
    aa.set_xlim([-1, 101])
    martist.setp(aa.get_yticklabels(), visible=False)
    aa.set_title(name)
    aa.xaxis.set_major_locator(MaxNLocator(3, prune='both'))
    aa.grid()

    aa = ax3[2]
    name = 'position'
    aa.plot(ens.best.lon, ens.best.lat, '.-',
            ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
    aa.plot(ens.best.lon[:2], ens.best.lat[:2], 'go',
            ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
    aa.plot(ens.best.lon[-2:], ens.best.lat[-2:], 'r.',
            ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
    aa.plot(ens.best.lon[-2:], ens.best.lat[-2:], 'rx',
            ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
    aa.grid()
    aa.set_title(name)
    aa.tick_params(axis="y", direction="in", pad=-50)
    aa.set_xlabel('lon')
    aa.xaxis.set_major_locator(MaxNLocator(3, prune='both'))
    aa.xaxis.set_major_formatter(ScalarFormatter())
    aa.set_ylabel('lat')
    aa.yaxis.tick_right()
    aa.yaxis.set_label_position("right")
    aa.yaxis.set_major_formatter(formatter)

    # Beam Velocities
    a1 = beamVelFig.add_subplot(121)
    a2 = beamVelFig.add_subplot(122, sharex=a1, sharey=a1)
    cc = ['r', 'g', 'b', 'k']
    for beam in [1, 2, 3, 4]:
        name = 'vel%d' % (beam)
        beamvel = getattr(ens, name)
        a1.plot(beamvel.T, y, '.-',
                color=cc[beam-1], ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
        a1.text(.05, .05 + .07*(beam-1), name, transform=a1.transAxes,
                color=cc[beam-1])

        beamvel_ma = np.ma.masked_array(beamvel, ens.vs['u'].mask)
        a2.plot(beamvel_ma.T, y, '.-',
                color=cc[beam-1], ms=MARKER_SIZE, lw=LINE_SIZE, alpha=0.5)
        a2.text(.05, .05+.07*(beam-1), name, transform=a2.transAxes,
                color=cc[beam-1])

    ylims = a1.get_ylim()
    a1.set_ylim(ylims[-1::-1])
    a2.set_ylim(ylims[-1::-1])
    a1.grid()
    a2.grid()
    martist.setp(a2.get_yticklabels(), visible=False)
    a1.xaxis.set_major_locator(MaxNLocator(4, prune='both'))
    a2.xaxis.set_major_locator(MaxNLocator(4, prune='both'))
    a1.set_title('unedited')
    a2.set_title('edited')
    a1.set_ylabel('Depth', fontsize='small', labelpad=-4)
    a1.set_xlabel('m/s', fontsize='small')
    a2.set_xlabel('m/s', fontsize='small')
