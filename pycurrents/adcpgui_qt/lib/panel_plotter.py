# FIXME - TR: this script is based on adcpgui/cplotter.py and very similar to it.
#             perhaps it should be moved into a common lib
# BREADCRUMB: common lib.
import copy
import logging
import numpy as np
import matplotlib.patheffects as PathEffects
from matplotlib.ticker import FuncFormatter, MaxNLocator
from matplotlib.dates import AutoDateLocator

from pycurrents.adcpgui_qt.lib.miscellaneous import (
    reset_artist, is_in_data_range, utc_formatting)
from pycurrents.adcpgui_qt.lib.plotting_parameters import (PITCH_ALIAS, CLIMS,
    COMPARE_PREFIX, alias_to_name, COLOR_PLOT_LIST, TWIN_DATA_NAME, CMAPDICT,
    CMAPDICT_CBLIND, UNITS, TITLES, FORMATTER, PLOT_PARAM, LINE_SIZE,
    MARKER_SIZE, YLIMS, TWIN_DATA_RANGE, FLAG_COLOR_PLOT_LIST, STAGED_EDITS_ALPHA,
    OVERPLOT_ALPHA)
# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

# Standard logging
_log = logging.getLogger(__name__)

### Global Parameters ###
X0 = 0.07
TOTAL_HEIGHT = 0.8
START_Y = 0.1
PAX_WIDTH = 0.8
PAD = TOTAL_HEIGHT * .01
C_AX_PAD = .05
C_AX_WIDTH = .009

DISPLAY_FEAT = DisplayFeaturesSingleton()


### Panel's axis marker
# FIXME: perhaps turn make_axes into a factory rather than a simple function
def make_axes(fig, ax_list=[]):
    """
    Returns a custom dictionary of Matplotlib Axes objects.
    These axes are organised along 5 layers (from foreground to background):
    edit, triplex, twinx, cbar, pcolor

    Args:
        fig: Matplotlib Figure object
        ax_list: list of variables aliases, list of str.

    Returns: axdict, dict.
    """
    ### Parameters ###
    numax = len(ax_list)
    ax_height = TOTAL_HEIGHT/float(numax)
    refPcolorAx = None

    ### Defining layers ###
    # N.B.: all layers share x axis by default
    axdict = dict(pcolor=[], cbar=[], twinx=[], triplex=[], edit=[])
    # Pcolor layer:
    # - plot pcolor on
    # - solid background
    # - defined as navigation layer (zoom, pan, etc) if
    #   alias in COLOR_PLOT_LIST
    # - Foreground (z order = 0)
    # - share x & y axis with all pcolor panels
    for alias, plotnum in zip(ax_list, range(numax)):
        left = X0
        bottom = START_Y + plotnum*(ax_height+PAD)
        width = PAX_WIDTH
        height = ax_height
        if not refPcolorAx:
            refPcolorAx = fig.add_axes([left, bottom, width, height])
            ax = refPcolorAx
        else:
            ax = fig.add_axes([left, bottom, width, height],
                              sharex=refPcolorAx, sharey=refPcolorAx)
        ax.set_frame_on(False)
        ax.xaxis.set_visible(False)
        ax.set_zorder(0)
        ax.grid(False)
        # Additional attribute to store artist
        setattr(ax, "pcolorArtist", None)
        setattr(ax, "figTitleArtist", None)
        # Add to dict
        axdict['pcolor'].append(ax)

    # Colorbar layer:
    # - contains color bars on the side
    # - visible is alias in COLOR_PLOT_LIST
    # z order = 10
    for alias, plotnum in zip(ax_list, range(numax)):
        left = X0 + PAX_WIDTH + C_AX_PAD
        bottom = START_Y + 0.1 * ax_height + plotnum*(ax_height + PAD)
        width = C_AX_WIDTH
        height = 0.8 * ax_height
        cax = fig.add_axes([left, bottom, width, height])
        cax.set_zorder(0)
        cax.set_navigate(False)
        # Additional attribute to store artist (return from "colorbar()")
        setattr(cax, "colorbarArtist", None)
        axdict['cbar'].append(cax)
        # cax is handled differently because we can't easily reuse
        # the Axes passed in to a colorbar via cax; we need to remove the old
        # colorbar, including its Axes, and make a new Axes.
        cax.remove()  # Because it is just a template and data structure.

    # Twinx layer:
    # - overplot layer with yaxis on the left if alias not in COLOR_PLOT_LIST
    # - overplot layer with yaxis on the right if alias in COLOR_PLOT_LIST
    # - transparent background
    # - defined as navigation layer (zoom, pan, etc) if
    #   alias not in COLOR_PLOT_LIST
    # - z order = 15
    for alias, plotnum in zip(ax_list, range(numax)):
        left = X0
        bottom = START_Y + plotnum*(ax_height+PAD)
        width = PAX_WIDTH
        height = ax_height
        tax = fig.add_axes([left, bottom, width, height],
                           sharex=refPcolorAx)
        tax.set_frame_on(False)
        tax.xaxis.set_visible(False)
        tax.set_zorder(2)
        tax.patch.set_alpha(0.0)  # transparent background
        # Additional attribute to store artist
        setattr(tax, "plotArtist", None)
        setattr(tax, "figTitleArtist", None)
        # Add to dict
        axdict['twinx'].append(tax)

    # Triplex layer:
    # - overplot layer with yaxis on the right
    # - transparent background
    # - z order = 20
    for alias, plotnum in zip(ax_list, range(numax)):
        trax = axdict['twinx'][plotnum].twinx()
        trax.grid(False)
        trax.set_frame_on(False)
        trax.xaxis.set_visible(False)
        trax.set_zorder(4)
        trax.patch.set_alpha(0.0)  # background
        trax.set_navigate(False)
        # Additional attribute to store artist
        setattr(trax, "plotArtist", None)
        # Add to dict
        axdict['triplex'].append(trax)

    # Edit layer:
    # - catches all mouse events because created last (see ./zappers.py)
    # - plots editing points if alias in alias in flagPlotList
    # - holds x axis formatter
    # - transparent background yet visible frame
    # - foreground (z order = 25)
    # - share x & y axis with pcolor layer
    for alias, plotnum in zip(ax_list, range(numax)):
        left = X0
        bottom = START_Y + plotnum*(ax_height+PAD)
        width = PAX_WIDTH
        height = ax_height
        ax = axdict['pcolor'][plotnum]
        eax = fig.add_axes([left, bottom, width, height], sharex=ax, sharey=ax)
        eax.grid(False)
        eax.set_frame_on(True)
        eax.xaxis.set_visible(True)
        eax.yaxis.set_visible(False)
        eax.patch.set_alpha(0.0)  # background
        eax.set_zorder(6)
        # add attributes to axis for staged edits artists
        setattr(eax, 'zapperArtist', None)
        setattr(eax, 'thresholdArtist', None)
        setattr(eax, 'bottomArtist', None)
        axdict['edit'].append(eax)

    ### Customization ###
    # reverse the order so 0,1,2,3 starts at the top
    for name, arr in axdict.items():
        axdict[name] = arr[::-1]
    # X axis ticks only on bottom panel
    for eax in axdict['edit'][:-1]:
        # turn off x axis
        eax.xaxis.set_visible(False)
    # Share y for pitch and roll
    for alias, triplex, twinx in zip(ax_list, axdict['triplex'], axdict['twinx']):
        if alias == PITCH_ALIAS:
            triplex.get_shared_y_axes().join(triplex, twinx)

    return axdict


### Panel plotting engines
class CPlotter(object):
    def __init__(self, fig, axdict):
        """
        This class contains the tools to generates all the color plots

        Args:
            fig: Matplotlib Figure object
            axdict: dictionary of Matplotlib Axes objects
                    (see ./plotting_parameters.py)
        """
        self.fig = fig
        self.axdict = axdict
        self.clims = CLIMS.copy()
        self.text_left = None
        self.text_right = None

    ### Plotting functions
    def draw(self, CDdata, axnum, alias,
             draw_on_all_pcolor=False):
        """
        Plot panels in GUI's panels window

        Args:
            CDdata: codas database, CD object (see codas_data_models.py)
            axnum: panel's axis index, int
            alias: panel's quantity alias, str
            draw_on_all_pcolor: if True, draw staged edits on all pcolor layers

        """
        ### Calling Layers (see ./plotting_parameters.py)
        pax = self.axdict['pcolor'][axnum]
        cax = self.axdict['cbar'][axnum]  # template and data structure...
        tax = self.axdict['twinx'][axnum]
        trax = self.axdict['triplex'][axnum]
        eax = self.axdict['edit'][axnum]
        ### Clear up All Artists and Y axis
        # - listing & removing artists (see ./plotting_parameters.py)
        artists = [pax.pcolorArtist, tax.plotArtist, trax.plotArtist,
                   cax.colorbarArtist, # The return from fig.colorbar().
                   pax.figTitleArtist, tax.figTitleArtist,
                   eax.zapperArtist, eax.thresholdArtist, eax.bottomArtist]
        for artist in artists:
            reset_artist(artist)
        # It's not needed now, but for consistency it would be better if
        # reset_artist took a list of (Axes, attribute) so it could
        # reset the attribute to None.
        # - turning off all y axis; colorbar is already removed by reset_artist
        pax.yaxis.set_visible(False)
        tax.yaxis.set_visible(False)
        trax.yaxis.set_visible(False)
        # - turning off navigation
        pax.set_navigate(False)
        tax.set_navigate(False)
        trax.set_navigate(False)
        eax.set_navigate(False)
        ### Plot panel
        # - parse alias
        diff_flag = COMPARE_PREFIX in alias.lower()
        name = alias_to_name(alias)
        # - plotting data
        if alias == 'clear':
            self._clear_pcolor(pax, tax, trax)
        # In case varialble not in the database (ex. netcdf database)
        elif name not in CDdata.data.keys():
            self._clear_pcolor(
                pax, tax, trax,
                msg='"%s" not available in current database' % alias)
        elif alias in COLOR_PLOT_LIST or diff_flag:
            # Ticket 626
            # Sanity check - in case of comparison between non-overlapping
            #                datasets
            if diff_flag and CDdata.data[name] is None:
                self._clear_pcolor(pax, tax, trax,
                                   msg='No over-lapping data')
            else:
                pax.set_navigate(True)
                self.draw_pcolor(name, pax, cax, CDdata,
                                 diff=diff_flag)
        else:
            tax.set_navigate(True)
            self.draw_plot(name, tax, CDdata)
            self.draw_plot(TWIN_DATA_NAME[name], trax, CDdata, y_left=False)
        # - over-plotting data
        self.draw_over_layer(alias, tax, trax, CDdata)
        # - formatting xaxis
        self._format_xaxis(DISPLAY_FEAT.utc_date, CDdata.xlim, CDdata.yearbase)
        # - plotting edits
        if DISPLAY_FEAT.mode in ['edit', 'compare']:
            self.draw_staged_edits(name, eax, CDdata,
                                   show_bottom=DISPLAY_FEAT.show_bottom,
                                   show_threshold=DISPLAY_FEAT.show_threshold,
                                   show_zapper=DISPLAY_FEAT.show_zapper,
                                   draw_on_all_pcolor=draw_on_all_pcolor)

    def draw_pcolor(self, dataName, pax, cax, CDdata,
                    diff=False):
        """
        draw color plot

        Args:
            dataName: name of the 2D data field, str
            pax: pcolor's axes, Matplotlib Axes
            cax: colorbar's axes template, Matplotlib Axes
            CDdata: codas database, CD object (see codas_data_models.py)
            diff: bool. flag enables special plotting features for comparison
        """
        # Retrieve data
        data = CDdata.data[dataName]
        # Set-up colorbar
        if DISPLAY_FEAT.colorblind:
            cmapdict = CMAPDICT_CBLIND
        else:
            cmapdict = CMAPDICT
        # Def. display features
        #  - double check
        if COMPARE_PREFIX in dataName.lower():
            diff = True
        if diff:
            clim = self.clims[COMPARE_PREFIX]
            cmap = cmapdict[COMPARE_PREFIX]
            units = UNITS[dataName.split()[-2]]
            wrd_list = dataName.split()
            ref_sonar = CDdata.sonar
            comp_sonar = wrd_list[-1]
            qty = wrd_list[1] + ' ' + wrd_list[0]
            title = qty + ': ' + ref_sonar + ' - ' + comp_sonar
        else:
            clim = self.clims[dataName]
            cmap = cmapdict[dataName]
            units = UNITS[dataName]
            title = TITLES[dataName]
            if CDdata.mode == 'compare':
                title = CDdata.sonar + ': ' + title
        cmap = copy.copy(cmap)
        cmap.set_bad(DISPLAY_FEAT.background)
        # Set-up artists on pcolor layer
        # - pcolor
        pax.pcolorArtist = pax.pcolorfast(
            CDdata.Xe, CDdata.Ye, data,
            cmap=cmap, vmin=clim[0], vmax=clim[1], zorder=pax.zorder)
        # - colorbar
        cbarloc = MaxNLocator(nbins=self.nbins)
        cax_pos = cax.get_position(original=True)
        real_cax = self.fig.add_axes(cax_pos)
        cbar = self.fig.colorbar(
            pax.pcolorArtist, cax=real_cax, extend='both', ticks=cbarloc)
        cbar.ax.set_ylabel(units, fontsize='10',
                           style='normal', color='k')
        cbar.ax.yaxis.set_label_position('right')
        cax.colorbarArtist = cbar  # So it can be removed.
        real_cax.set_zorder(0)
        real_cax.set_navigate(False)
        # Set-up y axis
        pax.yaxis.set_visible(True)
        pax.set_ylabel(CDdata.yname, style='oblique', color='k')
        pax.yaxis.set_label_coords(-0.05, 0.5)
        pax.tick_params(axis='y', colors='k')
        pax.yaxis.set_major_formatter(FORMATTER)
        pax.yaxis.set_major_locator(
            MaxNLocator(nbins=6, prune='both', integer=True))
        if DISPLAY_FEAT.autoscale:
            CDdata.set_grid()
            pax.set_ylim(CDdata.ylim)
        else:
            pax.set_ylim(DISPLAY_FEAT.user_depth_range)
        # Write sonar name in compare mode
        self._add_title_in_fig(pax, title)

    def draw_plot(self, name, ax, CDdata,
                  y_left=True, show_label=True, alpha=1.0,
                  transparent_background=False,
                  opt=None):
        """
        Draw time series
        Args:
            name: name of the 1D data field, str
            ax: plot's axis, Matplotlib Axis
            CDdata: codas database, CD object (see codas_data_models.py)
            y_left: if True, Y axis ticks on the left, else on the right, bool.
            show_label: if True, show Y axis label
            transparent_background: if True, plot has a transparent background,
                                    else white background
            opt: set of plotting options (see PLOT_PARAM in
                 plotting_parameters.py), dictionary/Bunch
        """
        data = CDdata.data[name]
        dday = CDdata.data.dday
        if not opt:
            opt = PLOT_PARAM[name]
        # Y axis visible
        ax.yaxis.set_visible(True)
        if type(data) in [np.ma.core.MaskedArray, np.ndarray]:
            # Define artist
            color = opt[1]
            ax.plotArtist = ax.plot(dday, data, opt[2], color=color,
                                    lw=LINE_SIZE, ms=MARKER_SIZE, alpha=alpha)
            # set-up Axis
            ax.tick_params(axis='y', colors=opt[1])
            ax.yaxis.grid(linestyle='dashed')
            if show_label:
                ax.set_ylabel(opt[0], color=opt[1])
            if y_left:
                ax.yaxis.set_ticks_position('left')
                ax.yaxis.set_label_position('left')
            else:
                ax.yaxis.set_ticks_position('right')
                ax.yaxis.set_label_position('right')
            ax.yaxis.set_major_locator(opt[3])
            # Special treatment for heading since we impose cardinal points
            if name == 'heading':
                ax.set_yticklabels(opt[4])
                ax.set_ylim(YLIMS[name])
            else:
                ax.set_ylim(DISPLAY_FEAT.__dict__[TWIN_DATA_RANGE[name]])
            if not transparent_background:
                # Background color
                ax.set_frame_on(True)
                ax.patch.set_alpha(1.0)
                ax.set_facecolor('w')
                # ax.set_axis_bgcolor('w')
        else:  # in case 1D data does not exist
            self._clear_plot(ax)
            pass
        # Write sonar name in compare mode
        if not transparent_background:
            title = TITLES[name]
            if CDdata.mode == 'compare':
                title = CDdata.sonar + ': ' + title
            self._add_title_in_fig(ax, title)

    @staticmethod
    def draw_staged_edits(alias, eax, CDdata,
                          show_bottom=False,
                          show_threshold=False,
                          show_zapper=False,
                          draw_on_all_pcolor=False,
                          specific_mask=None):
        """
        Plot staged edits' points over pcolor panels

        Args:
            alias: panel's quantity alias, str
            eax: edit layer axis, Matplotlib Axis
            CDdata: codas database, CD object (see codas_data_models.py)
            show_bottom: show bottom edits if True, bool.
            show_threshold: show thresholds edits if True, bool.
            show_zapper: show manual edits if True, bool.
            draw_on_all_pcolor: if True, draw staged edits on all pcolor layers
            specific_mask: plot given mask instead if provided
        """
        # Clean artist
        eax.zapperArtist = reset_artist(eax.zapperArtist)
        # Consolidate staged edits
        name = alias_to_name(alias)
        # Fix for Ticket 626 (non-overlapping datasets)
        # Sanity check
        if not CDdata.data:
            return
        if (name in FLAG_COLOR_PLOT_LIST or draw_on_all_pcolor
            or COMPARE_PREFIX in name):
            mask = np.zeros(CDdata.Xc.shape, dtype=bool)
            if show_zapper:
                mask = np.ma.mask_or(mask, CDdata.zapperMask, shrink=False)
            if show_bottom:
                mask = np.ma.mask_or(mask, CDdata.bottomMask, shrink=False)
            if show_threshold:
                mask = np.ma.mask_or(mask, CDdata.thresholdsMask, shrink=False)
            if specific_mask is not None:
                if (isinstance(specific_mask, np.ndarray)
                        and specific_mask.shape == CDdata.Xc.shape):
                    mask = specific_mask
                # specific_mask can be initialized to array(False), in which
                # case we ignore it.
            # Plot staged points
            eax.zapperArtist = eax.plot(
                CDdata.Xc[mask], CDdata.Yc[mask],
                # FIXME - move to plotting_parameters.py
                'o', ms=2, alpha=STAGED_EDITS_ALPHA, color='white',
                fillstyle='full', markeredgecolor='black', markeredgewidth=0.5)

    def draw_over_layer(self, alias, tax, trax, CDdata):
        """
        Draw heading and/or speeding over pcolor panels included in
        COLOR_PLOT_LIST (see plotting_parameters.py)

        Args:
            alias: panel's quantity alias, str
            tax: twinx layer axis, Matplotlib Axis
            trax: triplex layer axis, Matplotlib Axis
            CDdata: codas database, CD object (see codas_data_models.py)
        """
        diff_flag = COMPARE_PREFIX in alias
        if alias in COLOR_PLOT_LIST or diff_flag:
            # Clean artist & co.
            self._del_text_over_layer()
            tax.plotArtist = reset_artist(tax.plotArtist)
            trax.plotArtist = reset_artist(trax.plotArtist)
            tax.yaxis.set_visible(False)
            trax.yaxis.set_visible(False)
            # over-plot
            if DISPLAY_FEAT.show_spd:
                opt = PLOT_PARAM['spd_right']
                self._add_speed_text()
                self.draw_plot('spd', tax, CDdata,
                               y_left=False, show_label=False,
                               alpha=OVERPLOT_ALPHA,
                               transparent_background=True, opt=opt)
                tax.yaxis.grid(False)
            if DISPLAY_FEAT.show_heading:
                self._add_heading_text()
                self.draw_plot('heading', trax, CDdata,
                               y_left=False, show_label=False,
                               alpha=OVERPLOT_ALPHA,
                               transparent_background=True)
                trax.yaxis.grid(False)

    ### Local Lib
    @staticmethod
    def _add_title_in_fig(ax, title):
        """
        Writes title in the plot panel (top left corner)

        Args:
            ax: Matplotlib's Axis object
            title: string
        """
        # FIXME - text overlapped by speed/heading over-plot (due to zorder of the axis the text is attached to)
        if hasattr(ax, 'figTitleArtist'):
            reset_artist(ax.figTitleArtist)
            ax.figTitleArtist = ax.text(0.005, 0.03, '%s' % title,
                                        horizontalalignment='left',
                                        verticalalignment='bottom',
                                        transform=ax.transAxes)
            ax.figTitleArtist.set_path_effects([PathEffects.withStroke(
                linewidth=3, foreground="w")])

    def _add_text_over_layer(self, position, text, color):
        """
        Add text related to heading & speeding over layers in figure's corners

        Args:
            position: 'left' or 'right', str.
            text: given text to be displayed, str.
            color: Matplotlib compatible color string, ex. 'g', 'w', etc., str.
        """
        # axes coordinates are 0,0 is bottom left and 1,1 is upper right
        left, right = .01, .99
        bottom = .01
        if 'right' in position:
            self.text_right = self.fig.text(
                right, bottom, text,
                horizontalalignment='right',
                verticalalignment='bottom',
                color=color, fontweight='bold')
        if 'left' in position:
            self.text_left = self.fig.text(
                left, bottom, text,
                horizontalalignment='left',
                verticalalignment='bottom',
                color=color, fontweight='bold')

    def _add_speed_text(self):
        self._add_text_over_layer('left', 'Ship Speed in m/s',
                                  PLOT_PARAM['spd'][1])

    def _add_heading_text(self):
        self._add_text_over_layer('right', 'Ship Heading in cardinal dir.',
                                  PLOT_PARAM['heading'][1])

    def _del_text_over_layer(self):
        try:
            self.text_left.remove()
            self.text_left = None
        except (AttributeError, ValueError):
            pass
        try:
            self.text_right.remove()
            self.text_right = None
        except (AttributeError, ValueError):
            pass

    def _clear_pcolor(self, pax, tax, trax, msg=''):
        """
        Plot "no data found" text in pcolor layers

        Args:
            pax: pcolor's axis, Matplotlib Axis
            tax: twin's axis, Matplotlib Axis
            trax: triplex's axis, Matplotlib Axis
        """
        tax.yaxis.set_visible(False)
        trax.yaxis.set_visible(False)
        tax.set_frame_on(False)
        if not msg:
            if is_in_data_range(DISPLAY_FEAT):
                msg = 'No data found in requested time range'
            else:
                msg = 'Outside of data range'
        pax.pcolorArtist = pax.text(.5, .5, msg,
                                    color='r', size=12,
                                    transform=pax.transAxes, ha='center')

    def _clear_plot(self, ax):
        """
        Plot "no data found" text in twinx or triplex layer

        Args:
            ax: twin's or triplex' axis, Matplotlib Axis
        """
        ax.set_frame_on(False)
        ax.patch.set_alpha(1.0)
        msg = 'this variable has not been found'
        ax.plotArtist = ax.text(.5, .5, msg, color='r', size=12,
                                transform=ax.transAxes, ha='center')

    def _format_xaxis(self, utc_date, xlim, yearbase):
        """
        Format X axis ticks
        Args:
            utc_date: if True, date in UTC format, else in decimal days
            xlim: time range, [min., max.], list
            xlim: year base, int.
        """
        # FIXME - really close to _format_axis in generic_app_components.py
        #         make static and move to lib
        ax = self.axdict['edit'][-1]
        # set new ticks
        if not utc_date:
            ax.xaxis.set_major_locator(MaxNLocator(nbins=9, prune='both'))
            ax.xaxis.set_major_formatter(FORMATTER)
            xtext_rotation = 0
            fontsize = 10
            alignment = 'center'
        else:
            # Fix for Ticket 685
            ax.xaxis.set_major_locator(AutoDateLocator())
            utc_formatter = FuncFormatter(
                lambda x, pos: utc_formatting(x, pos, yearbase))
            ax.xaxis.set_major_formatter(utc_formatter)
            fontsize = 9
            xtext_rotation = 20
            alignment = 'right'
        try:
            for label in ax.get_xticklabels():
                label.set_fontsize(fontsize)
                label.set_ha(alignment)
                label.set_rotation(xtext_rotation)
            # self.fig.tight_layout()  # FIXME - apparently needs to use add_subplot (instead of axes)
            # self.fig.autofmt_xdate() # Not helping with pop-up windows either
        except ValueError:
            _log.debug("""
            ---panel_plotter.py known bug---
            ValueError: ordinal must be >= 1. For more details see
            https://github.com/matplotlib/matplotlib/issues/6023
            """)
            pass
        ax.set_xlim(xlim)

    # Dynamic attributes
    def _get_nbins(self):
        """Dynamically defines the number of bins in colorbars"""
        numax = len(self.axdict['pcolor'])
        # nbins = number of bins in color bars
        if numax >= 8:
            return 2
        elif 8 > numax >= 6:
            return 3
        elif 6 > numax >= 4:
            return 4
        else:
            return 5

    nbins = property(_get_nbins)


### Plotting lib
def draw_vline_on_pcolor(axdict, value):
    """
    Draw a vertical line at the location of the "ping start"
    Args:
        axdict: dictionary of axis (see make_axes)
        value: ping start value

    Returns:

    """
    for ax in axdict['edit']:
        if hasattr(ax, 'pingStartVline'):
            reset_artist(ax.pingStartVline)
        pingStartVline = ax.axvline(
            value, color='k', linewidth=1, label='Ping Start')
        setattr(ax, 'pingStartVline', pingStartVline)

