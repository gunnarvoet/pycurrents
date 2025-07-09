# This GUI is built around a MVP design pattern:
#   - See pycurrents/adcpgui_qt/lib/images/Model_View_presenter_GUI_Design_Pattern.png
#   - See https://www.codeproject.com/Articles/228214/...
#         ...Understanding-Basics-of-UI-Design-Pattern-MVC-MVP

# FIXME: search for common patterns shared between slots and refactor

import sys
import logging

from numpy import bitwise_or
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (
    waitingNinactive_cursor, waiting_cursor)
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt
from pycurrents.adcpgui_qt.lib.plotting_parameters import CLIMS
from pycurrents.adcpgui_qt.lib.miscellaneous import dict_diff_to_str
from pycurrents.adcpgui_qt.lib.panel_plotter import draw_vline_on_pcolor
from pycurrents.adcpgui_qt.presenter.intercommunication import (
    get_start_day, get_day_step, get_axes, get_num_axes, get_mask,
    get_vel_range, get_ref_bins, get_vect_scale, get_vect_averaging,
    get_thresholds, get_sonars, get_depth_range, get_axes_indexes,
    get_sonars_indexes, get_diff_range,
    is_saturate, is_show_heading, is_show_spd, is_show_mcursor, is_use_bins,
    is_autoscale, is_use_utc_date, is_show_bottom, is_show_threshold,
    is_show_zapper, set_start_day, set_day_step, reset_thresholds,
    refresh_cdata, refresh_topo_txycursors, refresh_colorplot_txycursors,
    shall_the_masks_be_reset, write_edits_to_tmp_ascii,
    apply_edits_to_CODAS_database, log_applied_edits,
    reset_edits_in_CODAS_database, get_ping_start, get_ping_step,
    set_ping_start,
)
from pycurrents.codas import DB
# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

# Standard logging
_log = logging.getLogger(__name__)


DISPLAY_FEAT = DisplayFeaturesSingleton()

# Global variables
CURRENT_START = None
CURRENT_STEP = None


# Collection of "OnEvent" type functions
# - On input change
def OnTimeStartChange(controlWindow):
    """
    Actions when start time is changed through the GUI:
      - update 'start_day' in DISPLAY_FEAT model

    Args:
        controlWindow: control window, view, qtpy widget
    """
    # Logging
    _log.debug('OnTimeStartChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    start_time = get_start_day(controlWindow)
    if start_time:
        # Propagate to model
        DISPLAY_FEAT.start_day = start_time
        # - update time range
        time_step = get_day_step(controlWindow)
        DISPLAY_FEAT.time_range[0] = start_time
        DISPLAY_FEAT.time_range[1] = start_time + time_step

    # Logging diffirence in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug(' - Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


def OnTimeStepChange(controlWindow):
    """
    Actions when time step is changed through the GUI:
      - update 'step_day' and 'time_range' in DISPLAY_FEAT model

    Args:
        controlWindow: control window, view, qtpy widget
    """
    # Logging
    _log.debug('OnTimeStepChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    time_step = get_day_step(controlWindow)
    if time_step:
        # Propagate to model
        # - update time step
        DISPLAY_FEAT.day_step = time_step
        # - update time range
        start_time = get_start_day(controlWindow)
        DISPLAY_FEAT.time_range[0] = start_time
        DISPLAY_FEAT.time_range[1] = start_time + time_step

    # Logging diffirence in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


@waitingNinactive_cursor
def OnToggleChange(controlWindow, colorPlotWindow, txyCursors, CD):
    """
    Actions when toggles are changed through the GUI:
      - update DISPLAY_FEAT model
      - refresh color plot
      - switch on/off multicursors
      - log it in tab

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
        thresholds: editing thresholds container, model, Bunch
        CD: codas database, model, CData class
    """
    # logging
    _log.debug('OnToggleChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    # update 'show_spd', 'show_heading' and 'use_bins' in DISPLAY_FEAT
    DISPLAY_FEAT.show_spd = is_show_spd(controlWindow)
    DISPLAY_FEAT.show_heading = is_show_heading(controlWindow)
    DISPLAY_FEAT.multicursor = is_show_mcursor(controlWindow)
    old_flag_bin = DISPLAY_FEAT.use_bins
    DISPLAY_FEAT.use_bins = is_use_bins(controlWindow)
    old_flag_tick = DISPLAY_FEAT.utc_date
    DISPLAY_FEAT.utc_date = is_use_utc_date(controlWindow)
    # callback/refresh color plot
    if (old_flag_bin != DISPLAY_FEAT.use_bins) or\
       (old_flag_tick != DISPLAY_FEAT.utc_date):
        if old_flag_bin != DISPLAY_FEAT.use_bins:
            # refresh grid
            CD.set_grid(DISPLAY_FEAT.depth_range, DISPLAY_FEAT.use_bins)
            # refresh plots
            colorPlotWindow.draw_color_plot()
        if old_flag_tick != DISPLAY_FEAT.utc_date:
            colorPlotWindow.utc_date_format()
        colorPlotWindow.canvas.draw()
    else:
        colorPlotWindow.draw_over_layer()
        colorPlotWindow.canvas.draw()
    # switch on/off cursors
    txyCursors.set_visible(DISPLAY_FEAT.multicursor)
    if DISPLAY_FEAT.mode == 'single ping':
        # refresh by proxy
        controlWindow.tabsContainer.plotTab.buttonPlot.clicked.emit()
    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


def OnThresholdChange(controlWindow, thresholds, CD):
    """
    Actions when thresholds' values change through the GUI:
      - read thresholds' values from GUI table
      - update current values in thresholds container
      - update staged edits' mask

    Args:
        controlWindow: control window, view, qtpy widget
        thresholds: editing thresholds container, model, Bunch
        CD: codas database, model, CData class
    """
    # logging
    _log.debug('OnThresholdChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = thresholds.copy()

    # Read thresholds' values from GUI table
    currentThresholds = get_thresholds(controlWindow, thresholds)
    # Update current values in thresholds container
    entriesDict = controlWindow.tabsContainer.thresholdsTab.checkboxEntryLabels
    for edit_name in entriesDict.keys():
        if entriesDict[edit_name].checkbox.isChecked():
            if edit_name in currentThresholds.keys():
                thresholds.current_values[edit_name] =\
                    currentThresholds[edit_name]
            else:
                thresholds.current_values[edit_name] =\
                    thresholds.default_values[edit_name]
        else:
            thresholds.current_values[edit_name] =\
                thresholds.default_disabled_values[edit_name]
    # update thresholdMask
    CD.update_thresholds_mask()

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in thresholds: '
                  + dict_diff_to_str(ini_dict, thresholds))


@waitingNinactive_cursor
def OnThresholdTick(controlWindow, colorPlotWindow, thresholds, CD):
    """
    Actions when threshold's check box is ticked
     - call OnThresholdChange
     - refresh color plot
     - restore zoom
    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        thresholds: editing thresholds container, model, Bunch
        CD: codas database, model, CData class
    """
    # logging
    _log.debug('OnThresholdTick')
    OnThresholdChange(controlWindow, thresholds, CD)
    refresh_color_plot(controlWindow, colorPlotWindow,
                       restore_previous_zoom=True)


@waitingNinactive_cursor
def OnShowStagedEdit(controlWindow, colorPlotWindow):
    """
    Actions when "show staged *** edits" boxes are ticked:
      - update show_bottom, show_threshold, show_zapper in DISPLAY_FEAT
      - refresh color

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
    """
    # Logging
    _log.debug('OnShowStagedEdit')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    # update show_bottom, show_threshold, show_zapper in DISPLAY_FEAT
    DISPLAY_FEAT.show_zapper = is_show_zapper(controlWindow)
    if DISPLAY_FEAT.mode == 'edit':
        DISPLAY_FEAT.show_threshold = is_show_threshold(controlWindow)
        DISPLAY_FEAT.show_bottom = is_show_bottom(controlWindow)
    # refresh color
    colorPlotWindow.draw_color_plot(restore_previous_zoom=True)
    colorPlotWindow.canvas.draw()

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


@waitingNinactive_cursor
def OnSaturate(controlWindow, colorPlotWindow):
    """
    Actions when "saturate vel. plots# box is ticked:
      - Change color bar boundaries accordingly with box state
      - refresh pcolor plots

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
    """
    # Logging
    _log.debug('OnSaturate')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    # Change color bar boundaries if box check
    plotTab = controlWindow.tabsContainer.plotTab
    # Update DISPLAY_FEAT
    DISPLAY_FEAT.saturate = is_saturate(controlWindow)
    if DISPLAY_FEAT.saturate:
        plotTab.entryVelMin.setText('0')
        plotTab.entryVelMax.setText('100')
    # Back to default boundaries if box check
    else:
        plotTab.entryVelMin.setText(str(CLIMS['u'][0]))
        plotTab.entryVelMax.setText(str(CLIMS['u'][1]))
    # Refresh pcolor plots
    colorPlotWindow.draw_color_plot(restore_previous_zoom=True)
    colorPlotWindow.canvas.draw()

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))



@waitingNinactive_cursor
def OnReturnInThresholdEntry(colorPlotWindow):
    """
    Call back "refresh pcolor plots" when enter is pressed in threshold's entry

    Args:
        colorPlotWindow: control window, view, qtpy widget
    """
    # Logging
    _log.debug('OnReturnInThresholdEntry')
    # Refresh pcolor plots
    colorPlotWindow.draw_color_plot(restore_previous_zoom=True)
    colorPlotWindow.canvas.draw()


@waitingNinactive_cursor
def OnMaskChange(controlWindow, colorPlotWindow, thresholds, CD, pg_cutoff=None):
    """
    Actions when mask toggles are changed through the GUI:
      - update DISPLAY_FEAT model
      - refresh color plot and topo. map
      - log it in both tab and ascii file

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        thresholds: editing thresholds container, model, Bunch
        CD: codas database, model, CData class
        pg_cutoff: percent good cutoff, int 0-100
    """
    # Logging
    _log.debug('OnMaskChange')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()
        ini_thresholds = thresholds.copy()

    # update 'mask' in DISPLAY_FEAT accordingly
    DISPLAY_FEAT.mask = get_mask(controlWindow)
    # check mask, disable PG slider if not in low pg mode
    plotTab = controlWindow.tabsContainer.plotTab
    if DISPLAY_FEAT.mode == 'edit':
        if DISPLAY_FEAT.mask == 'low pg':
            if not plotTab.panelPlotting.panelCutoff.isEnabled():
                plotTab.panelPlotting.panelCutoff.setEnabled(True)
        else:
            plotTab.panelPlotting.panelCutoff.setEnabled(False)
    # callback/refresh color plot and topo map
    if DISPLAY_FEAT.mode == 'edit':
        CD.fix_flags(DISPLAY_FEAT.mask, thresholds=thresholds.current_values, pg_cutoff=pg_cutoff)
    else:
        CD.fix_flags(DISPLAY_FEAT.mask, thresholds=thresholds.current_values)
    colorPlotWindow.draw_color_plot(restore_previous_zoom=True)
    colorPlotWindow.canvas.draw()

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))
        _log.debug('- Changes in thresholds: '
                  + dict_diff_to_str(ini_thresholds, thresholds))

def OnPercentGoodCutoffSave(CD, pg_cutoff, whole_file):
    """
    Update the PROFILE_FLAGS in the CODAS database to mask profiles
    where PERCENT_GOOD is below the cutoff. If the chosen cutoff is
    lower than 50% the previously masked profiles will be unmasked.
    These changes are currently only applied over the timespan that
    is currently displayed in the plotting windows.

    Args:
        CD: codas database, model, CData class
        pg_cutoff: percent good cutoff, int 0-99
    """
    _log.debug('OnPercentGoodCutoffSave')

    db_path = CD.dbpathname

    if whole_file == Qt.Checked:
        start_dd, end_dd = DISPLAY_FEAT.day_range
    else:
        # calculate the start and end dd currently displayed
        start_dd = CD.get_startdd()
        dd_step = CD.get_ddstep()
        # I'm not sure how this margin was derived, but we essentially add 5% of the
        # timestep to either end, this appears consistent with the display
        timeMargin = dd_step * DISPLAY_FEAT.time_margin
        startddMinusMargin = start_dd - timeMargin
        ddstepPlusMargins = dd_step + 2.0 * timeMargin
        end_dd = startddMinusMargin + ddstepPlusMargins

    db = DB(db_path, read_only=False)
    _log.debug(f'setting PG cutoff to {pg_cutoff}% for day range {start_dd}-{end_dd}')
    if "PROFILE_FLAGS" in db.get_variable_names():
        displayed_range = db.get_range(ddrange=(start_dd, end_dd))
        flags = db.get_variable("PROFILE_FLAGS", r=displayed_range)
        pg = db.get_variable("PERCENT_GOOD", r=displayed_range)

        flags = bitwise_or(flags, (pg < pg_cutoff) * 2)  # Set bit 1 where pg < pg_cutoff
        flags &= ~((pg > pg_cutoff) * 2) # Unset bit 1 where pg > pg_cutoff


        db.put_array("PROFILE_FLAGS", flags, r=displayed_range)
    del db # For arcane reasons, this is the way to close the db.
    CD.reset_masks(force_reset=True)
    CD.update_thresholds_mask()
    CD.get_data(newdata=True)

def OnVelRangeChange(controlWindow):
    """
    Actions when velocity range changed through the GUI:
      - update DISPLAY_FEAT model

    Args:
        controlWindow: control window, view, qtpy widget
    """
    # Logging
    _log.debug('OnVelRangeChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    DISPLAY_FEAT.vel_range = get_vel_range(controlWindow)

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


def OnDiffRangeChange(controlWindow):
    """
    Actions when velocity difference range changed through the GUI:
      - update DISPLAY_FEAT model

    Args:
        controlWindow: control window, view, qtpy widget
    """
    # Logging
    _log.debug('OnDiffRangeChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    DISPLAY_FEAT.diff_range = get_diff_range(controlWindow)

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


def OnDepthRangeChange(controlWindow):
    """
    Actions when depth range changed through the GUI:
      - update DISPLAY_FEAT model

    Args:
        controlWindow: control window, view, qtpy widget
    """
    # Logging
    _log.debug('OnDepthRangeChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    DISPLAY_FEAT.user_depth_range = get_depth_range(controlWindow)

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


def OnBinRangeChange(topoWindow):
    """
    Actions when bin range changed through the GUI:
      - update DISPLAY_FEAT model

    Args:
        topoWindow: topographic map window, view, qtpy widget
    """
    # Logging
    _log.debug('OnBinRangeChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    DISPLAY_FEAT.ref_bins = get_ref_bins(topoWindow)

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


def OnVectScaleChange(topoWindow):
    """
    Actions when vector scale is changed through the GUI:
      - update DISPLAY_FEAT model

    Args:
        topoWindow: topographic map window, view, qtpy widget
    """
    # Logging
    _log.debug('OnVectChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    DISPLAY_FEAT.vec_scale = get_vect_scale(topoWindow)

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


def OnVectAveragingChange(topoWindow):
    """
    Actions when vector averaging is changed through the GUI:
      - update DISPLAY_FEAT model

    Args:
        topoWindow: topographic map window, view, qtpy widget
    """
    # Logging
    _log.debug('OnVectAveragingChange')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    DISPLAY_FEAT.delta_t = get_vect_averaging(topoWindow)

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


def OnRefCDChange(topoWindow, txyCursors, CDcompare):
    """
    Actions when changing reference codas database model:
      - retrieve user inputs from control panel
      - change CD accordingly
      - refresh plots

    Args:
        topoWindow: topographic map window, view, qtpy widget
        txyCursors:
        CDcompare: custom class containing CData objects

    """
    # Logging
    _log.debug('OnRefCDChange')
    # FIXME - Not quite complying to architecture.
    #         Next line should be in intercommunication
    # FIXME - add entry in DISPLAY_FEAT
    ref_sonar = topoWindow.refSonarDropdown.currentText()
    topoWindow.ref_sonar = ref_sonar
    CD = CDcompare[ref_sonar]
    topoWindow._change_ref_CD(CD)
    refresh_topo_txycursors(topoWindow, txyCursors)
    # callback/refresh color topo.
    topoWindow.draw_topo_map()
    refresh_topo_txycursors(topoWindow, txyCursors)
    topoWindow.canvas.draw()


@waitingNinactive_cursor
def OnAutoscale(controlWindow, colorPlotWindow):
    """
    Actions when "auto-scale" box is ticked:
      - update DISPLAY_FEAT
      - refresh pcolor plots

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
    """
    # Logging
    _log.debug('OnAutoscale')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    # Update DISPLAY_FEAT
    DISPLAY_FEAT.autoscale = is_autoscale(controlWindow)
    # Refresh pcolor plots
    colorPlotWindow.draw_color_plot()
    colorPlotWindow.canvas.draw()

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


#  * Single Ping mode
def OnPingStartChange(controlWindow, colorPlotWindow):
    """
    Actions when "ping start" changes:
      - update DISPLAY_FEAT container
      - update "info ping" on control panel
      - draw plots and horizontal line
    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
    """
    # Logging
    _log.debug('OnPingStartChange')
    # update DISPLAY_FEAT container
    new_ping_start = get_ping_start(controlWindow)
    if new_ping_start is not None:
        DISPLAY_FEAT.ping_start = new_ping_start
        # update "info ping" on control panel
        controlWindow.tabsContainer.plotTab.set_info_ping()
        # draw plots and horizontal line
        draw_vline_on_pcolor(colorPlotWindow.axdict, new_ping_start)
        colorPlotWindow.canvas.draw()


def OnPingStepChange(controlWindow):
    """
    Actions when ping step changes:
      - update DISPLAY_FEAT
    Args:
        controlWindow: control window, view, qtpy widget
    """
    # Logging
    _log.debug('OnPingStepChange')
    new_ping_step = get_ping_step(controlWindow)
    if new_ping_step is not None:
        DISPLAY_FEAT.ping_step = new_ping_step


@waitingNinactive_cursor
def OnPlotRaw(colorPlotWindow, pingPlotsWindows):
    """
    Actions when "Plot Raw" button is hit
      - Gathers control entries & widgets' states
      - refresh single ping plots & info text
      - draw vertical line
    Args:
        colorPlotWindow: control window, view, qtpy widget
        pingPlotsWindows: single-ping plotting windows,
                          container of qtpy widgets
    """
    # N.B.: controlWindow is added so that @waitingNinactive_cursor works
    # Logging
    _log.debug('OnPlotRaw')
    # Gathers control entries & widgets' states
    ping_start = DISPLAY_FEAT.ping_start
    ping_step = DISPLAY_FEAT.ping_step
    bin_flag = DISPLAY_FEAT.use_bins
    colorblind_flag = DISPLAY_FEAT.colorblind
    # refresh single ping plots & info text
    pingPlotsWindows.group_refresh(ping_start, ping_step, bin_flag,
                                   colorblind_flag)
    # draw vertical line
    draw_vline_on_pcolor(colorPlotWindow.axdict, DISPLAY_FEAT.ping_start)
    colorPlotWindow.canvas.draw()


@waitingNinactive_cursor
def OnNextRaw(controlWindow, colorPlotWindow, pingPlotsWindows):
    """
    Actions when "right arrow" button is hit
      - Increment time range
      - update DISPLAY_FEAT
      - refresh single ping plots & info text
      - draw vertical line
    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        pingPlotsWindows: single-ping plotting windows,
                          container of qtpy widgets
    """
    # Logging
    _log.debug('OnNextRaw')
    # Increment time range
    day_in_sec = 24.0 * 60.0 * 60.0
    increment = DISPLAY_FEAT.ping_start / day_in_sec
    new_ping_start = DISPLAY_FEAT.ping_start + increment
    # propagate
    DISPLAY_FEAT.ping_start = new_ping_start
    set_ping_start(controlWindow, new_ping_start)
    # refresh single ping plots & info text
    pingPlotsWindows.group_refresh(DISPLAY_FEAT.ping_start,
                                   DISPLAY_FEAT.ping_step,
                                   DISPLAY_FEAT.use_bins,
                                   DISPLAY_FEAT.colorblind)
    controlWindow.tabsContainer.plotTab.set_info_ping()
    # draw vertical line
    draw_vline_on_pcolor(colorPlotWindow.axdict, DISPLAY_FEAT.ping_start)
    colorPlotWindow.canvas.draw()


@waitingNinactive_cursor
def OnPreviousRaw(controlWindow, colorPlotWindow, pingPlotsWindows):
    """
    Actions when "left arrow" button is hit
      - Increment time range
      - update DISPLAY_FEAT
      - refresh single ping plots & info text
      - draw vertical line
    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        pingPlotsWindows: single-ping plotting windows,
                          container of qtpy widgets
    """
    # Logging
    _log.debug('OnPreviousRaw')
    # Increment time range
    day_in_sec = 24.0 * 60.0 * 60.0
    increment = DISPLAY_FEAT.ping_start / day_in_sec
    new_ping_start = DISPLAY_FEAT.ping_start - increment
    # propagate
    DISPLAY_FEAT.ping_start = new_ping_start
    set_ping_start(controlWindow, new_ping_start)
    # refresh single ping plots & info text
    pingPlotsWindows.group_refresh(DISPLAY_FEAT.ping_start,
                                   DISPLAY_FEAT.ping_step,
                                   DISPLAY_FEAT.use_bins,
                                   DISPLAY_FEAT.colorblind)
    controlWindow.tabsContainer.plotTab.set_info_ping()
    # draw vertical line
    draw_vline_on_pcolor(colorPlotWindow.axdict, DISPLAY_FEAT.ping_start)
    colorPlotWindow.canvas.draw()


@waitingNinactive_cursor
def OnPickPingStart(controlWindow, colorPlotWindow, pingPlotsWindows,
                    event):
    """
    Actions when "ping start" picked with mouse's click:
      - retrieve ping start from mouse event
      - update DISPLAY_FEAT
      - refresh single ping plots, vertical line & info text
    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        pingPlotsWindows: single-ping plotting windows,
                          container of qtpy widgets
        event: Matplotlib's mouse event
    """
    # N.B.: controlWindow is added so that @waitingNinactive_cursor works
    # Logging
    _log.debug('OnPickPingStart')
    if not colorPlotWindow.toolbar.mode:
        if event.xdata:
            # propagate
            DISPLAY_FEAT.ping_start = event.xdata
            set_ping_start(controlWindow, event.xdata)
            # refresh single ping plots & info text
            pingPlotsWindows.group_refresh(DISPLAY_FEAT.ping_start,
                                           DISPLAY_FEAT.ping_step,
                                           DISPLAY_FEAT.use_bins,
                                           DISPLAY_FEAT.colorblind)
            controlWindow.tabsContainer.plotTab.set_info_ping()
            # draw vertical line
            draw_vline_on_pcolor(colorPlotWindow.axdict, event.xdata)
            colorPlotWindow.canvas.draw()

# - On events
@waitingNinactive_cursor
def OnZoomTopo(topoMapWindow, txyCursors):
    """
    Actions when user zooms on topo. map:
      - refresh multicursor
      - refresh topo. map

    Args:
        topoMapWindow: topo. map's window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug('OnZoomTopo')
    if _log.getEffectiveLevel() <= 10:
        ini_dict = DISPLAY_FEAT.__dict__.copy()

    refresh_topo_txycursors(topoMapWindow, txyCursors)
    topoMapWindow.canvas.draw()

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_dict, DISPLAY_FEAT.__dict__))


@waitingNinactive_cursor
def OnShow(controlWindow, colorPlotWindow, topoMapWindow, txyCursors,
           thresholds, asciiNpaths_container, CD):
    """
    Actions when user clicks "show" button -> global refresh:
      - focus on show button
      - update start entry in Time Nav. and DISPLAY_FEAT
      - refresh codas database
      - refresh multicursor, color plots and topo. map
      - log it in both tab and ascii file

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        topoMapWindow: topo. map's window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
        thresholds: editing thresholds container, model, Bunch
        asciiNpaths_container: container of ascii files & system paths, model
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug('OnShow')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()
        ini_thresholds = thresholds.copy()

    global CURRENT_STEP, CURRENT_START
    # update axes features in DISPLAY_FEAT accordingly
    if DISPLAY_FEAT.mode == 'compare':
        sonars = get_sonars(controlWindow)
        sonars_indexes = get_sonars_indexes(controlWindow)
        if sonars != DISPLAY_FEAT.sonars:
            DISPLAY_FEAT.sonars = sonars
        if sonars_indexes != DISPLAY_FEAT.sonars_indexes:
            DISPLAY_FEAT.sonars_indexes = sonars_indexes
        depth_range = get_depth_range(controlWindow)
        if depth_range != DISPLAY_FEAT.user_depth_range:
            DISPLAY_FEAT.user_depth_range = depth_range
    axes = get_axes(controlWindow)
    if axes != DISPLAY_FEAT.axes:
        DISPLAY_FEAT.axes = axes
    axes_indexes = get_axes_indexes(controlWindow)
    if axes_indexes != DISPLAY_FEAT.axes_indexes:
        DISPLAY_FEAT.axes_indexes = axes_indexes
    numax = get_num_axes(controlWindow)
    if numax != DISPLAY_FEAT.num_axes:
        DISPLAY_FEAT.num_axes = numax
        #  callback/refresh color plot, topo map and color plots' multi-cursors
        colorPlotWindow.remake_axes()
        refresh_colorplot_txycursors(
            colorPlotWindow, topoMapWindow, txyCursors)
    # focus out of time entries and other widget connect to return key/onshow
    controlWindow.timeNavigationBar.buttonShow.setFocus()
    # update start entry in Time Nav.
    time_step = get_day_step(controlWindow)
    start_time = get_start_day(controlWindow)
    _log.debug("time_step: " + str(time_step))
    _log.debug("DISPLAY_FEAT.day_step: " + str(DISPLAY_FEAT.day_step))
    _log.debug("start_time: " + str(start_time))
    _log.debug("DISPLAY_FEAT.start_day: " + str(DISPLAY_FEAT.start_day))
    test1 = round(time_step, 2) != round(DISPLAY_FEAT.day_step, 2)
    test2 = round(start_time) != round(DISPLAY_FEAT.start_day)
    if test1 or test2:
        new_data = True
    else:
        new_data = False
    # check if masks need resetting
    if _pop_up_question_wrapper(start_time, time_step, CD) is False:
        return
    else:
        if DISPLAY_FEAT.mode in ['edit', 'compare'] and new_data:
            CD.reset_masks(force_reset=True)
    # reformat Time Nav.'s entries
    set_start_day(controlWindow, start_time)
    set_day_step(controlWindow, time_step)
    # update global vars
    CURRENT_START = get_start_day(controlWindow)
    CURRENT_STEP = get_day_step(controlWindow)
    # refresh cdata and both colorPlotWindow's and topoMapWindow's attributes
    topoMapWindow.reset_xy_lims()
    refresh_cdata(thresholds, asciiNpaths_container, CD,
                  new_data=new_data)
    # callback/refresh color plot and topo.
    _refresh_colorplot_topo(colorPlotWindow, topoMapWindow, txyCursors)
    # callbacks for single ping mode
    if DISPLAY_FEAT.mode == 'single ping':
        # Update ping start
        if test2:
            new_ping_start = start_time + 0.05 * time_step
            controlWindow.tabsContainer.plotTab.entryStartPing.setText(
                str(new_ping_start))
        # refresh by proxy
        controlWindow.tabsContainer.plotTab.entryStartPing.returnPressed.emit()
    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))
        _log.debug('- Changes in thresholds: '
                  + dict_diff_to_str(ini_thresholds, thresholds))
        _log.debug('- ascii_container: ' + asciiNpaths_container.__str__())


@waitingNinactive_cursor
def OnNext(controlWindow, colorPlotWindow, topoMapWindow, txyCursors,
           thresholds, asciiNpaths_container, CD):
    """
    Actions when user clicks Next "->" button:
      - update values in Time Nav. and DISPLAY_FEAT
      - refresh codas database
      - refresh multicursor, color plots and topo. map
      - log it in both tab and ascii file

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        topoMapWindow: topo. map's window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
        thresholds: editing thresholds container, model, Bunch
        asciiNpaths_container: container of ascii files & system paths, model
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug('OnNext')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()
        ini_thresholds = thresholds.copy()

    global CURRENT_STEP, CURRENT_START
    # Create pop-up message if edit masks aren't empty and reset them if needed
    if DISPLAY_FEAT.mode in ['edit', 'compare']:
        if not shall_the_masks_be_reset(CD).answer:
            return
    # update 'timerange',
    time_step = get_day_step(controlWindow)
    start_time = get_start_day(controlWindow) + time_step
    DISPLAY_FEAT.time_range[0] = start_time
    DISPLAY_FEAT.time_range[1] = start_time + time_step
    # update start entry in Time Nav.
    set_start_day(controlWindow, start_time)
    set_day_step(controlWindow, time_step)
    # update global vars
    CURRENT_START = get_start_day(controlWindow)
    CURRENT_STEP = get_day_step(controlWindow)
    if DISPLAY_FEAT.mode == 'edit':
        # show thresholds edits
        controlWindow.tabsContainer.plotTab.checkboxShowThresholdEdit.click()
    # callback/refresh color plot, topo map and update txyCursors data
    refresh_cdata(thresholds, asciiNpaths_container, CD,
                  new_data=True)
    topoMapWindow.reset_xy_lims()
    # callback/refresh color plot and topo.
    _refresh_colorplot_topo(colorPlotWindow, topoMapWindow, txyCursors)
    # callbacks for single ping mode
    if DISPLAY_FEAT.mode == 'single ping':
        # Update ping start
        new_ping_start = start_time + 0.05 * time_step
        controlWindow.tabsContainer.plotTab.entryStartPing.setText(
            str(round(new_ping_start, 2)))
        # refresh by proxy
        controlWindow.tabsContainer.plotTab.entryStartPing.returnPressed.emit()
    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))
        _log.debug('- Changes in thresholds: '
                  + dict_diff_to_str(ini_thresholds, thresholds))
        _log.debug('- ascii_container: ' + asciiNpaths_container.__str__())


@waitingNinactive_cursor
def OnPrev(controlWindow, colorPlotWindow, topoMapWindow, txyCursors,
           thresholds, asciiNpaths_container, CD):
    """
    Actions when user clicks Previous "<-" button:
      - update values in Time Nav. and DISPLAY_FEAT
      - refresh codas database
      - refresh multicursor, color plots and topo. map
      - log it in both tab and ascii file

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        topoMapWindow: topo. map's window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
        thresholds: editing thresholds container, model, Bunch
        asciiNpaths_container: container of ascii files & system paths, model
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug('OnPrev')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()
        ini_thresholds = thresholds.copy()

    global CURRENT_STEP, CURRENT_START
    # Create pop-up message if edit masks aren't empty and reset them if needed
    if DISPLAY_FEAT.mode in ['edit', 'compare']:
        if not shall_the_masks_be_reset(CD).answer:
            return
    # update 'timerange'
    time_step = get_day_step(controlWindow)
    start_time = get_start_day(controlWindow) - time_step
    DISPLAY_FEAT.time_range[0] = start_time
    DISPLAY_FEAT.time_range[1] = start_time + time_step
    # update start entry in Time Nav.
    set_start_day(controlWindow, start_time)
    set_day_step(controlWindow, time_step)
    # update global vars
    CURRENT_START = get_start_day(controlWindow)
    CURRENT_STEP = get_day_step(controlWindow)
    if DISPLAY_FEAT.mode == 'edit':
        # show thresholds edits
        controlWindow.tabsContainer.plotTab.checkboxShowThresholdEdit.click()
    # callback/refresh color plot, topo map and multicursor
    topoMapWindow.reset_xy_lims()
    refresh_cdata(thresholds, asciiNpaths_container, CD,
                  new_data=True)
    # callback/refresh color plot and topo.
    _refresh_colorplot_topo(colorPlotWindow, topoMapWindow, txyCursors)
    # callbacks for single ping mode
    if DISPLAY_FEAT.mode == 'single ping':
        # Update ping start
        new_ping_start = start_time + 0.05 * time_step
        controlWindow.tabsContainer.plotTab.entryStartPing.setText(
            str(round(new_ping_start, 2)))
        # refresh by proxy
        controlWindow.tabsContainer.plotTab.entryStartPing.returnPressed.emit()
    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))
        _log.debug('- Changes in thresholds: '
                  + dict_diff_to_str(ini_thresholds, thresholds))
        _log.debug('- ascii_container: ' + asciiNpaths_container.__str__())


@waitingNinactive_cursor
def OnRefreshPanel(controlWindow, colorPlotWindow, topoMapWindow, txyCursors,
                   thresholds, asciiNpaths_container, CD):
    """
    Actions when "Refresh Panel(s)" button is hit:
      - update 'num_axes' and 'axes' in DISPLAY_FEAT model
      - refresh color plot, topo. map and multi-cursors
      - log it in tab

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        topoMapWindow: topo. map's window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
        thresholds: editing thresholds container, model, Bunch
        asciiNpaths_container: container of ascii files & system paths, model
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug('OnRefreshPanel')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()
        ini_thresholds = thresholds.copy()

    # update 'num_axes' and 'axes' in DISPLAY_FEAT accordingly
    DISPLAY_FEAT.num_axes = get_num_axes(controlWindow)
    DISPLAY_FEAT.axes = get_axes(controlWindow)
    DISPLAY_FEAT.axes_indexes = get_axes_indexes(controlWindow)
    if DISPLAY_FEAT.mode == 'compare':
        DISPLAY_FEAT.sonars = get_sonars(controlWindow)
        DISPLAY_FEAT.sonars_indexes = get_sonars_indexes(controlWindow)
    # refresh data
    refresh_cdata(thresholds, asciiNpaths_container, CD)
    #  callback/refresh color plot, topo map and color plots' multi-cursors
    colorPlotWindow.remake_axes()
    refresh_colorplot_txycursors(
        colorPlotWindow, topoMapWindow, txyCursors)
    colorPlotWindow.draw_color_plot()
    # refresh ping start veritcal line
    if DISPLAY_FEAT.mode == 'single ping':
        draw_vline_on_pcolor(colorPlotWindow.axdict, DISPLAY_FEAT.ping_start)
        controlWindow.tabsContainer.plotTab.set_info_ping()
    # draw/refresh
    topoMapWindow.canvas.draw()
    colorPlotWindow.canvas.draw()

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))
        _log.debug('- Changes in thresholds: '
                  + dict_diff_to_str(ini_thresholds, thresholds))
        _log.debug('- ascii_container: ' + asciiNpaths_container.__str__())


@waiting_cursor
def OnZappers(controlWindow, zapperPlotWindow):
    """
    Actions when "zappers" button is hit:
      - make control window inactive
      - make Pop-up zapper window visible
      - toggle "show bottom edits" accordingly

    Args:
        controlWindow: control window, view, qtpy widget
        zapperPlotWindow: zapper pop-up window, view, qtpy widget
    """
    # Logging
    _log.debug('OnZappers')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()

    # Make control window (only) inactive
    controlWindow.setEnabled(False)
    for child in controlWindow.children():
        child.setEnabled(True)
    # Make Pop-up zapper window visible
    zapperPlotWindow.setVisible(True)
    # Toggle "show zapper edits"
    _toggle_staged_edits(zapperPlotWindow, zapper="zapper")

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))


@waiting_cursor
def OnBottomSelector(controlWindow, bottomPlotWindow):
    """
    Actions when "Seabed selector" button is hit:
      - make control window inactive
      - make Pop-up zapper window visible
      - toggle "show bottom edits" accordingly

    Args:
        controlWindow: control window, view, qtpy widget
        bottomPlotWindow: seabed selector pop-up window, view, qtpy widget
    """
    # Logging
    _log.debug('OnBottomSelector')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()

    # Make control window (only) inactive
    controlWindow.setEnabled(False)
    for child in controlWindow.children():
        child.setEnabled(True)
    # Make Pop-up zapper window visible
    bottomPlotWindow.setVisible(True)
    # Toggle "show bottom edits"
    _toggle_staged_edits(bottomPlotWindow, zapper="bottom")

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))


# FIXME: def OnThresholdSelector similarly to above and connect it to
#       controlWindow.buttonThreshold.clicked.connect(self.on_click_threshold)
#       in connection_widget_signal_slot.py...see control_window.py


@waiting_cursor
def OnResetSelector(controlWindow, resetPlotWindow):
    """
    Actions when "Reset Editing" button is hit:
      - make control window inactive
      - make Pop-up zapper window visible
      - make sure checkboxes and plot are consistent with DISPLAY_FEAT and data

    Args:
        controlWindow: control window, view, qtpy widget
        resetPlotWindow: reset editing pop-up window, view, qtpy widget
    """
    # Logging
    _log.debug('OnResetSelector')

    # # Make control window (only) inactive
    controlWindow.setEnabled(False)
    for child in controlWindow.children():
        child.setEnabled(True)
    # Make Pop-up reset window visible
    resetPlotWindow.setVisible(True)
    # Make sure checkboxes and plot are consistent with DISPLAY_FEAT and data
    resetPlotWindow._reset_edits()
    resetPlotWindow._checkbox_refresh()
    resetPlotWindow._panel_refresh()


@waiting_cursor
def OnResetThresholds(controlWindow, colorPlotWindow, thresholds):
    """
    Callback when "Reset Thresholds" button is hit

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        thresholds: editing thresholds container, model, Bunch
    """
    # Logging
    _log.debug('OnResetThresholds:')
    if _log.getEffectiveLevel() <= 10:
        ini_thresholds = thresholds.copy()

    # Callback
    reset_thresholds(controlWindow, thresholds)
    OnReturnInThresholdEntry(colorPlotWindow)

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in thresholds: '
                  + dict_diff_to_str(ini_thresholds, thresholds))


@waitingNinactive_cursor
def OnApplyEditing(controlWindow, ascii_container, thresholds, CD,
                   refresh=True):
    """
    Actions when "Apply Editing" button is hit":
      - Define masks
      - Write temporary ascii files
      - Apply edits to database
      - Clean-up
      - Refresh plots

    Args:
        controlWindow: control window, view, qtpy widget
        ascii_container: container of ascii files & system paths , model, Bunch
        thresholds: editing thresholds container, model, Bunch
        CD: codas database, model, CData class
        refresh: switch for refreshing plots
    """
    # Logging
    _log.debug('OnApplyEditing')
    if _log.getEffectiveLevel() <= 10:
        ini_thresholds = thresholds.copy()

    # Steps:
    # 1. Define masks:
    editsMask, profileMask, bottomIndexes = CD.get_masks()
    # 2. Write temporary ascii files: Legacy code
    write_edits_to_tmp_ascii(editsMask, profileMask, bottomIndexes,
                             ascii_container, CD)
    # 3. Apply edits as follows
    apply_edits_to_CODAS_database(thresholds, ascii_container, CD)
    # 4. Log applied edits
    log_applied_edits(editsMask, profileMask, bottomIndexes,
                      controlWindow, thresholds, ascii_container)
    # 5. Clean-up
    #  a. append to asclog files
    ascii_container.update_asclog_files()
    #  b. delete so-created ascii files
    ascii_container.remove_tmp_files()
    #  c. reset masks
    CD.reset_masks(force_reset=True)
    CD.update_thresholds_mask()  # FIXME - this line resets BE, TE, PE as well - due to legacy code
    # 6. Refresh plots...by proxy
    CD.get_data(newdata=True)
    if refresh:
        controlWindow.timeNavigationBar.buttonShow.clicked.emit()

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in thresholds: '
                  + dict_diff_to_str(ini_thresholds, thresholds))
        _log.debug('- ascii_container: ' + ascii_container.__str__())


@waitingNinactive_cursor
def OnApplyEditingCompareMode(controlWindow, ascii_container, thresholds, CD):
    """
    Actions when "Apply Editing" button is hit":
      - Define masks
      - Write temporary ascii files
      - Apply edits to database
      - Clean-up
      - Refresh plots
    FOR USE IN COMPARE MODE ONLY !!!

    Args:
        controlWindow: control window, view, qtpy widget
        ascii_container: container of ascii files & system paths , model, Bunch
        thresholds: editing thresholds container, model, Bunch
        CD: codas database, model, CData class
    """
    # Wrap OnApplyEditing slot
    for sonar in CD.sonars:
        a = ascii_container[sonar]
        t = thresholds[sonar]
        c = CD[sonar]
        # Fix for Ticket 626
        if c.data:
            OnApplyEditing(controlWindow, a, t, c, refresh=False)
    # Refresh plots...by proxy
    controlWindow.timeNavigationBar.buttonShow.clicked.emit()


@waitingNinactive_cursor
def OnResetEditing(resetWindow, ascii_container, CD):
    """
    Actions when "Reset Editing" button is hit":
      - Reset database in given time ranges
      - Reset masks
      - Refresh plot

    Args:
        resetWindow: reset editing pop-up window, view, qtpy widget
        ascii_container: container of ascii files & system paths , model, Bunch
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug('OnResetEditing')
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- ascii_container: ' + ascii_container.__str__())

    # Special treatment for compare mode
    if CD.mode == 'compare':
        cd = CD[resetWindow.chosenSonar]
        ascii = ascii_container[resetWindow.chosenSonar]
    else:
        cd = CD
        ascii = ascii_container
    # Reset database in given time ranges
    for ddrange in resetWindow.clear_edit_ranges:
        reset_edits_in_CODAS_database(ddrange, ascii, cd)
    # Reset masks
    resetWindow._reset_edits()
    # Refresh plot
    CD.get_data(newdata=True)
    resetWindow.draw_color_plot()
    resetWindow.canvas.draw()


def OnClose(controlWindow, CD):
    # Logging
    _log.debug('OnClose')
    if shall_the_masks_be_reset(CD).answer:
        controlWindow.close()
        sys.exit(0)


### Local lib - Collection of "refresh" type functions
def refresh_topo_map(controlWindow, topoMapWindow, txyCursors):
    """
    Custom "refresh" function for the topo. map

    Args:
        colorPlotWindow: color plot panels' window, view, qtpy widget
        topoMapWindow: topo. map's window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug('In refresh_topo_map')

    controlWindow.timeNavigationBar.buttonShow.setFocus()
    xlims = topoMapWindow.topax.get_xlim()
    ylims = topoMapWindow.topax.get_ylim()
    topoMapWindow.draw_topo_map(xlims=xlims, ylims=ylims)
    refresh_topo_txycursors(topoMapWindow, txyCursors)
    # flush old artist and draw new plot
    topoMapWindow.canvas.draw()


def refresh_color_plot(controlWindow, colorPlotWindow,
                       restore_previous_zoom=False):
    """
    Custom "refresh" function for the color plots

    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
    """
    # Logging
    _log.debug('In refresh_color_plot')

    controlWindow.timeNavigationBar.buttonShow.setFocus()
    colorPlotWindow.draw_color_plot(restore_previous_zoom)
    colorPlotWindow.canvas.draw()


def _pop_up_question_wrapper(start_time, time_step, CD):
    """
    Display a pop-up message if edit masks aren't empty
    and reset them if needed

    Args:
        start_time: float
        time_step: float
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug('In _pop_up_question_wrapper')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()

    flag = (start_time != CURRENT_START) or (time_step != CURRENT_STEP)
    if CURRENT_STEP and CURRENT_START:  # due to kick start where they both=None
        if flag and DISPLAY_FEAT.mode in ['edit', 'compare']:
            question = shall_the_masks_be_reset(CD)
            return question.answer
    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))
    return True


def _toggle_staged_edits(editPlotWindow, zapper="zapper"):
    # Logging
    _log.debug('In _toggle_staged_edits')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()

    # Toggle "show zapper edits"
    old_values = {
        "show_zapper": DISPLAY_FEAT.show_zapper,
        "show_bottom": DISPLAY_FEAT.show_bottom,
        "show_threshold": DISPLAY_FEAT.show_threshold,
                  }
    if zapper == 'zapper':
        DISPLAY_FEAT.show_zapper = True
        DISPLAY_FEAT.show_bottom = False
        # DISPLAY_FEAT.show_threshold = False
    elif zapper == 'bottom':
        DISPLAY_FEAT.show_zapper = False
        DISPLAY_FEAT.show_bottom = True
        DISPLAY_FEAT.show_threshold = False
    else:
        _log.debug("In toggle_staged_edits - unknown zapper mode")
        return
    # Make sure checkboxes and plot are consistent with DISPLAY_FEAT
    editPlotWindow._checkbox_refresh()
    editPlotWindow._panel_refresh()
    # Back to old display values
    DISPLAY_FEAT.show_zapper = old_values["show_zapper"]
    DISPLAY_FEAT.show_bottom = old_values["show_bottom"]
    DISPLAY_FEAT.show_threshold = old_values["show_threshold"]

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))


def _refresh_colorplot_topo(colorPlotWindow, topoMapWindow, txyCursors):
    # Logging
    _log.debug('In _refresh_colorplot_topo')
    if _log.getEffectiveLevel() <= 10:
        ini_display = DISPLAY_FEAT.__dict__.copy()

    colorPlotWindow.draw_color_plot()
    colorPlotWindow.canvas.draw()
    topoMapWindow.draw_topo_map()
    refresh_topo_txycursors(topoMapWindow, txyCursors)
    topoMapWindow.canvas.draw()

    # Logging differences in models
    if _log.getEffectiveLevel() <= 10:
        _log.debug('- Changes in DISPLAY_FEAT: '
                  + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))


