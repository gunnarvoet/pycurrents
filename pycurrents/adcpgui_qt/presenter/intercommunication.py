# Notes: This script gathers functions and tools enabling the communication
#        between the modules composing the present MVP code architecture
#        It is articulated around 8 main categories:
#         - comm. with the codas data base
#         - comm. with the control window IOs
#         - comm. between controlwindow and thresholds container/model
#         - comm. between parameter containers and CODAS model
#         - compatibility between user's options and parameter containers
#         - comm. between txycursors, views and models
#         - comm. between user and model
#         - comm. between ascii and CODAS models

import sys
import os
import logging
from numpy import ceil

# BREADCRUMB: common library...
from pycurrents.codas import to_datestring
from pycurrents.adcp.quick_adcp import Processor
from pycurrents.adcp.pingedit import write_badbins, write_badprf, write_mab
from pycurrents.adcp.uhdasfile import guess_dbname
from pycurrents.plot.mpltools import nowstr
from pycurrents.num.nptools import Flags
from pycurrents.system.misc import Bunch, Cachefile
from pycurrents.system.logutils import unexpected_error_msg
# BREADCRUMB: ...end of common library
from pycurrents.adcpgui_qt.lib.miscellaneous import (
    backward_compatibility_quick_fix, dict_diff_to_str)
from pycurrents.adcpgui_qt.lib.plotting_parameters import CLIMS, COMPARE_PREFIX
from pycurrents.adcpgui_qt.lib.mpl_widgets import TXYCursors
from pycurrents.adcpgui_qt.lib.qtpy_widgets import CustomDialogBox
from pycurrents.adcpgui_qt.model.display_features_models import displayFeaturesEdit

# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

# Standard logging
_log = logging.getLogger(__name__)


DISPLAY_FEAT = DisplayFeaturesSingleton()

global DEFAULT_VALUES
DEFAULT_VALUES = displayFeaturesEdit()


### Tools for communication with the codas data base ###
def get_dbparam(path, options):
    """
    For given *path* returns Bunch with database parameters:
        * sonar, crisename, beamangle, configtype, dbpathname

    Args:
        path: path to database, str.
        options: options object from the OptionParser

    Returns: Bunch
    """
    _log.debug("In get_dbparam - Inputs:"
              + "\n- path: " + path
              + "\n- options: " + options.__str__())
    db_param = Bunch(yearbase=None, beamangle=None, badbeam=None)

    dbinfo = get_dbinfo(path)
    if dbinfo is not None:
        for name in ('beamangle', 'configtype', 'cruisename',
                     'sonar', 'badbeam'):
            if name in dbinfo.cachedict:
                db_param[name] = dbinfo.cachedict[name]
    else:
        db_param.cruisename, db_param.sonar = get_sonar(path)

    db_param.update({k: v for (k, v) in
                    vars(options).items() if v is not None})
    db_param.dbpathname = path

    if db_param.beamangle is not None:
        db_param.beamangle = int(db_param.beamangle)

    return db_param


def get_sonar(path):
    """ For a given path returns cruisename and full sonar path """
    _log.debug("In get_sonar - Inputs: \n"
              + "- path: " + path)
    sonar_path = os.path.split(path)
    if sonar_path[1] == 'edit':
        sonar = os.path.split(sonar_path[0])
    else:
        sonar = sonar_path
    cruisename = os.path.split(sonar[0])[1]
    return cruisename, sonar_path[1]


def get_dbpath(path):
    """ For a given path returns database path """
    _log.debug("In get_dbpath - Inputs: \n"
              + "- path: " + path)
    try:
        dbpath = guess_dbname(path)
    except (Exception, IOError) as err:
        _log.error(unexpected_error_msg(err))
        sys.exit(1)
    return dbpath


def get_dbinfo(dbpath):
    """ For a given database path if exist reads dbinfo.txt and returns """
    _log.debug("In get_dbinfo - Inputs: \n"
              + "- dbpath: " + dbpath)
    dbinfo = os.path.join(os.path.split(os.path.split(dbpath)[0])[0],
                      'dbinfo.txt')
    if os.path.exists(dbinfo):
        dbinfo = Cachefile(dbinfo)
        dbinfo.read()
    else:
        dbinfo = None
        _log.debug('dbinfo.txt does not exist. Old version Database')
    return dbinfo


### Tools for communication with the control window IOs ###
# N.B.: some functions will be subject to changes if the structure or
#       or underlying library (qtpy here) of the guiApp changes

#  - Time Navigator IOs
def get_start_day(controlWindow):
    """
    Get start day from control window's widget

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: start decimal day, float.
    """
    _log.debug("In get_start_day")
    try:
        string = controlWindow.timeNavigationBar.entryStart.text()
        return float(string)
    except ValueError:  # blank entry
        _log.debug("blank entry")
        return 0.0


def get_day_step(controlWindow):
    """
    Get day step from control window's widget

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: decimal day step, float.
    """
    _log.debug("In get_day_step")
    try:
        string = controlWindow.timeNavigationBar.entryStep.text()
        return float(string)
    except ValueError:  # blank entry
        _log.debug("blank entry")
        return DEFAULT_VALUES['day_step']


def set_start_day(controlWindow, float_value):
    """
    Set value of the start day in the control window's widget

    Args:
        controlWindow: control window, view, qtpy widget
        float_value: user input, str.
    """
    _log.debug("In set_start_day - Inputs:"
              + "\n- float_value: " + str(float_value))
    controlWindow.timeNavigationBar.entryStart.setText("%.2f" % float_value)


def set_day_step(controlWindow, float_value):
    """
    Set value of the day step in the control window's widget

    Args:
        controlWindow: control window, view, qtpy widget
        float_value: user input, str.
    """
    _log.debug("In set_day_step - Inputs:"
              + "\n- float_value: " + str(float_value))
    controlWindow.timeNavigationBar.entryStep.setText("%.2f" % float_value)


#  - "Panels" inputs in plot tab
def get_num_axes(controlWindow):
    """
    Get the number of figures in the control window's widget

    Args:
        controlWindow: control window, view, qtpy widget
    """
    _log.debug("In get_num_axes")
    return controlWindow.tabsContainer.plotTab.counterFigures


def get_axes(controlWindow):
    """
    Get the names of the quantities to plot from the "Plot" tab.

    Args:
        plotTab: plot tab, control window's widget

    Returns: list of quantity names
    """
    _log.debug("In get_axes")
    axes_variables = []
    plotTab = controlWindow.tabsContainer.plotTab
    for ii in range(plotTab.counterFigures):
        if controlWindow.mode == 'compare':
            dropD = getattr(plotTab, "button" + str(ii))
            variable = str(dropD.variables.currentText())
        else:
            variable = str(getattr(plotTab, "button" + str(ii)).currentText())
        axes_variables.append(variable)
    return axes_variables


def get_axes_indexes(controlWindow):
    """
    Get the indexes of the quantities to plot from the "Plot" tab.
    Mostly use to save display features in config files.

    Args:
        plotTab: plot tab, control window's widget

    Returns: list of quantity indexes
    """
    _log.debug("In get_axes_indexes")
    axes_indexes = []
    plotTab = controlWindow.tabsContainer.plotTab
    for ii in range(plotTab.counterFigures):
        if controlWindow.mode == 'compare':
            dropD = getattr(plotTab, "button" + str(ii))
            index = dropD.variables.currentIndex()
        else:
            index = getattr(plotTab, "button" + str(ii)).currentIndex()
        axes_indexes.append(index)
    return axes_indexes


def get_sonars(controlWindow):
    """
    Get the names of the chosen sonars from the "Plot" tab's drop-downs.
    Args:
        controlWindow: control window, view, qtpy widget

    Returns: list of sonar names, [str., str.,...]
    """
    _log.debug("In get_sonars")
    axes_sonars = []
    plotTab = controlWindow.tabsContainer.plotTab
    for ii in range(plotTab.counterFigures):
        dropD = getattr(plotTab, "button" + str(ii))
        variable = str(dropD.sonars.currentText())
        axes_sonars.append(variable)
    return axes_sonars


def get_sonars_indexes(controlWindow):
    """
    Get the indexes  of the chosen sonars from the "Plot" tab's drop-downs.
    Mostly use to save display features in config files.

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: list of sonar indexes, [int., int.,...]
    """
    _log.debug("In get_sonars_indexes")
    axes_sonars_indexes = []
    plotTab = controlWindow.tabsContainer.plotTab
    for ii in range(plotTab.counterFigures):
        dropD = getattr(plotTab, "button" + str(ii))
        index = dropD.sonars.currentIndex()
        axes_sonars_indexes.append(index)
    return axes_sonars_indexes


# FIXME: are the is_*WHATEVER* function type really necessary? Look a little over-kill
#  - "Show staged edits" tick boxes in plot tab
def is_show_zapper(controlWindow):
    """
    Check if "show staged zapper edits" is toggled

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: flag, bool.
    """
    _log.debug("In is_show_zapper")
    checkBox = controlWindow.tabsContainer.plotTab.checkboxShowZapperEdit
    return checkBox.isChecked()


def is_show_bottom(controlWindow):
    """
    Check if "show staged bottom edits" is toggled

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: flag, bool.
    """
    _log.debug("In is_show_bottom")
    checkBox = controlWindow.tabsContainer.plotTab.checkboxShowBottomEdit
    return checkBox.isChecked()


def is_show_threshold(controlWindow):
    """
    Check if "show staged zapper edits" is toggled

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: flag, bool.
    """
    _log.debug("In is_show_threshold")
    checkBox = controlWindow.tabsContainer.plotTab.checkboxShowThresholdEdit
    return checkBox.isChecked()


#  - "Toggles" tick boxes in plot tab
def is_show_spd(controlWindow):
    """
    Check if "show speed" is toggled

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: flag, bool.
    """
    _log.debug("In is_show_spd")
    check_box = controlWindow.tabsContainer.plotTab.checkboxShowSpeed
    return check_box.isChecked()


def is_show_heading(controlWindow):
    """
    Check if "show heading" is toggled

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: flag, bool.
    """
    _log.debug("In is_show_heading")
    check_box = controlWindow.tabsContainer.plotTab.checkboxShowHeading
    return check_box.isChecked()


def is_show_mcursor(controlWindow):
    """
    Check if "show multi-cursor" is toggled

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: flag, bool.
    """
    _log.debug("In is_show_mcursor")
    check_box = controlWindow.tabsContainer.plotTab.checkboxShowMCursor
    return check_box.isChecked()


def is_use_bins(controlWindow):
    """
    Check if "z = bins" is toggled

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: flag, bool.
    """
    _log.debug("In is_use_bins")
    checkboxZBins = controlWindow.tabsContainer.plotTab.checkboxZBins
    return checkboxZBins.isChecked()


def is_use_utc_date(controlWindow):
    """
    Check if "x = UTC dates" is toggled

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: flag, bool.
    """
    _log.debug("In is_use_utc_date")
    checkboxXTicks = controlWindow.tabsContainer.plotTab.checkboxXTicks
    return checkboxXTicks.isChecked()


def is_saturate(controlWindow):
    """
    Check if "saturate vel. plots" is toggled

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: flag, bool.

    """
    _log.debug("In is_saturate")
    checkboxSaturate = controlWindow.tabsContainer.plotTab.checkboxSaturate
    return checkboxSaturate.isChecked()


def get_mask(controlWindow):
    """
    Get the name of the mask to apply from the control window's radio button

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: mask name, str.
    """
    _log.debug("In get_mask")
    if controlWindow.tabsContainer.plotTab.radiobuttonNoFlags.isChecked():
        mask = "no flags"
    if controlWindow.tabsContainer.plotTab.radiobuttonCodas.isChecked():
        mask = "codas"
    if controlWindow.mode == "edit":
        if controlWindow.tabsContainer.plotTab.radiobuttonAll.isChecked():
            mask = "all"
        if controlWindow.tabsContainer.plotTab.radiobuttonLowPG.isChecked():
            mask = "low pg"
    return mask


#  - "Plotting" inputs in plot tab
def get_vel_range(controlWindow):
    """
    Get the velocity range from the control window's entries

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: [min., max], list of floats
    """
    _log.debug("In get_vel_range")
    vel_range = [None, None]
    try:
        vel_range[0] = float(
            controlWindow.tabsContainer.plotTab.entryVelMin.text())
    except ValueError:  # blank entry
        vel_range[0] = DEFAULT_VALUES['vel_range'][0]
    try:
        vel_range[1] = float(
            controlWindow.tabsContainer.plotTab.entryVelMax.text())
    except ValueError:  # blank entry
        vel_range[1] = DEFAULT_VALUES['vel_range'][1]
    return vel_range


def get_diff_range(controlWindow):
    """
    Get the velocity range from the control window's entries

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: [min., max], list of floats
    """
    _log.debug("In get_diff_range")
    diff_range = [None, None]
    try:
        diff_range[0] = float(
            controlWindow.tabsContainer.plotTab.entryDiffMin.text())
    except ValueError:  # blank entry
        diff_range[0] = CLIMS[COMPARE_PREFIX][0]
    try:
        diff_range[1] = float(
            controlWindow.tabsContainer.plotTab.entryDiffMax.text())
    except ValueError:  # blank entry
        diff_range[1] = CLIMS[COMPARE_PREFIX][1]
    return diff_range


def get_depth_range(controlWindow):
    """
    Get the depth range from the control window's entries

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: [min., max], list of floats
    """
    _log.debug("In get_depth_range")
    depth_range = [None, None]
    try:
        depth_range[1] = float(
            controlWindow.tabsContainer.plotTab.depthRange.entryMin.text())
    except ValueError:  # blank entry
        depth_range[1] = DEFAULT_VALUES['user_depth_range'][1]
    try:
        depth_range[0] = float(
            controlWindow.tabsContainer.plotTab.depthRange.entryMax.text())
    except ValueError:  # blank entry
        depth_range[0] = DEFAULT_VALUES['user_depth_range'][1]
    return depth_range


def is_autoscale(controlWindow):
    """
    Get flag for auto-scale from the control window's check box

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: bool.
    """
    _log.debug("In get_autoscale")
    checkBox = controlWindow.tabsContainer.plotTab.depthRange.checkboxAutoscale
    return checkBox.isChecked()


#  - Single Ping mode inputs in polt tab
def get_ping_start(controlWindow):
    """
    Get the "ping start" from the control window's entry

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: decimal day, float
    """
    _log.debug("In get_ping_start")
    try:
        return float(controlWindow.tabsContainer.plotTab.entryStartPing.text())
    except ValueError:
        return None


def get_ping_step(controlWindow):
    """
    Get the "ping step" from the control window's entry

    Args:
        controlWindow: control window, view, qtpy widget

    Returns: time step in seconds, float
    """
    _log.debug("In get_ping_step")
    try:
        return float(controlWindow.tabsContainer.plotTab.entryStepPing.text())
    except ValueError:
        return None


def set_ping_start(controlWindow, float_value):
    """
    Set the "ping start" in the control window's entry

    Args:
        controlWindow: control window, view, qtpy widget
        float_value: decimal day, float
    """
    _log.debug("In set_ping_start")
    value_str = str(round(float_value, 2))
    controlWindow.tabsContainer.plotTab.entryStartPing.setText(value_str)


def set_ping_step(controlWindow, float_value):
    """
    Set the "ping step" in the control window's entry

    Args:
        controlWindow: control window, view, qtpy widget
        float_value: time step in seconds, float
    """
    _log.debug("In set_ping_step")
    value_str = str(round(float_value, 2))
    controlWindow.tabsContainer.plotTab.entryStepPing.setText(value_str)


### Tools for comm. between topowindow I/Os ###
def get_ref_bins(topoWindow):
    """
    Get the bin range from the control window's entries

    Args:
        topoWindow: topographic map window, view, qtpy widget

    Returns: [min., max], list of floats
    """
    _log.debug("In get_ref_bins")
    ref_bins = [None, None]
    try:
        ref_bins[0] = int(
            topoWindow.entryBinUpper.text())
    except ValueError:  # blank entry
        ref_bins[0] = DEFAULT_VALUES['ref_bins'][0]
    try:
        ref_bins[1] = int(
            topoWindow.entryBinLower.text())
    except ValueError:  # blank entry
        ref_bins[1] = DEFAULT_VALUES['ref_bins'][1]
    return ref_bins


def get_vect_scale(topoWindow):
    """
    Get vector scale factor from the control window's entry
    Args:
        topoWindow: topographic map window, view, qtpy widget

    Returns: vector scale, float
    """
    _log.debug("In get_vect_scale")
    try:
        vect_scale = 1. / float(
            topoWindow.entryVectScale.text())
    except (ValueError, ZeroDivisionError):  # blank entry
        vect_scale = DEFAULT_VALUES['vec_scale']
    return vect_scale


def get_vect_averaging(topoWindow):
    """
    Get vector averaging rate (minutes) from the control window's entry
    Args:
        topoWindow: topographic map window, view, qtpy widget

    Returns: vector scale, float
    """
    _log.debug("In get_vect_averaging")
    try:
        vect_averaging = int(
            topoWindow.entryVectAveraging.text())
    except ValueError:  # blank entry
        vect_averaging = DEFAULT_VALUES['delta_t']
    return vect_averaging


### Tools for comm. between controlwindow and thresholds container/model ###
def get_thresholds(controlWindow, thresholds):
    """
    Get the current values of the thresholds

    Args:
        controlWindow: control window, view, qtpy widget
        thresholds: editing thresholds container, model, Bunch

    Returns: dictionary of thresholds current values
    """
    _log.debug("In get_thresholds")
    ini_dict = thresholds.current_values.copy()

    currentThresholds = thresholds.current_values
    entriesDict = controlWindow.tabsContainer.thresholdsTab.checkboxEntryLabels
    for name in entriesDict.keys():
        if entriesDict[name].checkbox.isChecked():
            try:
                currentThresholds[name] = int(entriesDict[name].entry.text())
            except ValueError:  # blank entry
                continue
        else:
            currentThresholds[name] = int(
                thresholds.default_values[name])

    # Logging differences in models
    _log.debug('- Changes in thresholds.current_values: '
              + dict_diff_to_str(ini_dict, thresholds.current_values))

    return currentThresholds


def reset_thresholds(controlWindow, thresholds):
    """
    Reset threshold tab and bunch singleton to defaults values

    Args:
        controlWindow: control window, view, qtpy widget
        thresholds: editing thresholds container, model, Bunch
    """
    _log.debug("In reset_thresholds")
    ini_dict = thresholds.copy()

    checkBoxDict = controlWindow.tabsContainer.thresholdsTab.checkboxEntryLabels
    enabled_thresholds = thresholds.widget_features.enabled_thresholds
    names = thresholds.widget_features.edit_names
    for name in names:
        e = name not in enabled_thresholds
        v = thresholds.default_values[name]
        checkBox = checkBoxDict[name]
        checkBox.entry.setText(str(v))
        checkBox.check_state(e)
        checkBox.checkbox.setChecked(e)
    # Emit event so that associated slots are triggered
    checkBox.entry.textChanged.emit("hello world!")

    # Logging differences in models
    _log.debug('- Changes in thresholds: '
              + dict_diff_to_str(ini_dict, thresholds))


def log_applied_edits(editsMask, profileMask, bottomIndexes,
                      controlWindow, thresholds, ascii_container):
    """
    Log in *MODE*.log file the edits applied to the database

    Args:
        editsMask: bin wise mask, 2D numpy array
        profileMask: profile wise mask, 1D numpy array
        bottomIndexes: list of bottom indexes, 1D numpy masked array
        controlWindow: control window, view, qtpy widget
        thresholds: editing thresholds container, model, Bunch
        ascii_container: container of ascii files & system paths, model
    """
    # Logging
    _log.debug("In log_applied_edits")
    _log.debug('- thresholds: \n' + thresholds.__str__())
    _log.debug('- ascii_container: \n' + ascii_container.__str__())

    #  Append ascii log files - Legacy code
    # FIXME: perhaps move this block to miscellaneous or ascii_model?
    #   - applied thershold
    if controlWindow.mode != 'compare':
        ss = []
        keys = thresholds.widget_features.edit_names
        entriesDict = controlWindow.tabsContainer.thresholdsTab.checkboxEntryLabels
        # Time range
        startdd = DISPLAY_FEAT.start_day
        ddstep = DISPLAY_FEAT.day_step
        timeMargin = ddstep * DISPLAY_FEAT.time_margin
        startddMinusMargin = startdd - timeMargin
        ddstepPlusMargins = ddstep + 2.0 * timeMargin
        msg = '  The following thresholds were applied at %s from %s to %s decimal days:'
        ss.append(msg % (
            nowstr(),
            round(startddMinusMargin, 2),
            round(startddMinusMargin + ddstepPlusMargins)))
        ss.append('  ================================')
        for k in keys:
            v = thresholds.current_values[k]
            if entriesDict[k].checkbox.isChecked():
                ss.append('  %20s : %5d' % (k, v))
            else:
                ss.append('  %20s :    --' %k)
        ss.append('  ================================')
        ascii_container.write_to_log('\n'.join(ss))
    #   - applied bad bin
    ascii_container.write_to_log("\n  %s bad bins were masked" %
                                 editsMask.sum())
    #   - applied profiles
    ascii_container.write_to_log("\n  %s bad profiles were masked" %
                                 profileMask.sum())
    #   - identified bottom points
    ascii_container.write_to_log("\n  %s bottom points were identified" %
                                 bottomIndexes.count())


### Tools for communication between parameter containers and CODAS model ###
def refresh_cdata(thresholds, ascii_container, CD,
                  new_data=False):
    """
    Refresh codas model (i.e. CD) based on the current display features
    container model (i.e. DISPLAY_FEAT)

    Args:
        thresholds: editing thresholds container, model, Bunch
        ascii_container: container of ascii files & system paths, model
        CD: codas database, model, CData class
        new_data: if True, forces to CD to fetch data within requested
                  time range contained in DISPLAY_FEAT
    """
    # Logging
    _log.debug("In refresh_cdata")
    _log.debug('- DISPLAY_FEAT: \n' + DISPLAY_FEAT.__str__())
    _log.debug('- thresholds: \n' + thresholds.__str__())
    _log.debug('- ascii_container: \n' + ascii_container.__str__())

    # Propagate potential change in DISPLAY_FEAT
    startdd = DISPLAY_FEAT.start_day
    ddstep = DISPLAY_FEAT.day_step
    timeMargin = ddstep * DISPLAY_FEAT.time_margin
    startddMinusMargin = startdd - timeMargin
    ddstepPlusMargins = ddstep + 2.0 * timeMargin
    if ((CD.startdd != startddMinusMargin) or (CD.ddstep != ddstepPlusMargins)
        or new_data):
        ascii_container.write_to_log(
            "\n\n Extracting data from %7.2f to %7.2f decimal days" %
            (startddMinusMargin, startddMinusMargin + ddstepPlusMargins))
        ascii_container.write_to_log(
            "\n ================================")
        # FIXME: find the nearest timestamp to the left of startddMinusMargin
        CD.startdd = startddMinusMargin
        # FIXME: find the nearest timestamp to the right of startddMinusMargin + ddstepPlusMargins
        CD.ddstep = ddstepPlusMargins
        CD.get_data(new_data)
    # TICKET 626
    if CD.data is not None or CD.mode == 'compare':
        CD.set_grid(DISPLAY_FEAT.depth_range, DISPLAY_FEAT.use_bins)
        if DISPLAY_FEAT.mode in ["edit", "compare"]:
            if new_data:
                CD.reset_masks(force_reset=True)
            CD.update_thresholds_mask()  # FIXME - this line resets BE, TE, PE as well - due to legacy code
            CD.fix_flags(DISPLAY_FEAT.mask, thresholds.current_values)
        else:
            CD.fix_flags(DISPLAY_FEAT.mask)


### Tools for compatibility between user's options and parameter containers ###
def initialize_display_feat(thresholds,
                            asciiNpaths_container, CD, options):
    """
    Initialize the current display features container, override its default
    values with user inputs and refresh codas model accordingly

    Args:
        thresholds: editing thresholds container, model, Bunch
        asciiNpaths_container: ascii file names & path container, model, Bunch
        CD: codas database, model, CData class
        options: set of options, ArgumentParser object
    """
    _log.debug("In initialize_display_feat")
    ini_display = DISPLAY_FEAT.__dict__.copy()
    ini_thresholds = thresholds.copy()
    # - Override display features with user's options
    for key in DISPLAY_FEAT.__dict__:
        try:
            user_value = getattr(options, key)
            if user_value is not None:
                DISPLAY_FEAT.__dict__[key] = user_value
        except (AttributeError, KeyError):
            continue
    # - Initialize DISPLAY_FEATures for color plots
    DISPLAY_FEAT.start_day = CD.startdd_all
    DISPLAY_FEAT.day_range = [CD.startdd_all, CD.enddd_all]
    DISPLAY_FEAT.year_base = CD.yearbase
    if DISPLAY_FEAT.mode == 'single ping':
        DISPLAY_FEAT.ping_start = round(
            CD.startdd_all + 0.05 * (CD.enddd_all - CD.startdd_all), 2)
    CD.ddstep = DISPLAY_FEAT.day_step
    # - At this point if CD.data == None,
    #   something's wrong with the requested time range
    if not CD.data:
        # - loop though ddstep until CD.data is or ddstep + startdd_all > startdd_all
        #       if latter raise error
        stop = False
        ddstep = CD.ddstep
        while not stop:
            CD.ddstep = ddstep
            if ddstep + CD.startdd_all > CD.enddd_all:
                _log.error('There is no data in %s' % CD.dbpathname)
                sys.exit(1)
            if not CD.data:
                ddstep *= 2.0
                _log.debug("No data found in %s. Increasing initial step to %s",
                      CD.dbpathname, ddstep)
            else:
                _log.debug("Finally found data in %s for ddstep = %s",
                          CD.dbpathname, ddstep)
                DISPLAY_FEAT.day_step = ddstep
                stop = True
    # - Finish initialize DISPLAY_FEATURES for color plots
    DISPLAY_FEAT.time_range = [DISPLAY_FEAT.start_day,
                               DISPLAY_FEAT.start_day + DISPLAY_FEAT.day_step]
    # - Initialize data features
    DISPLAY_FEAT.num_bins = CD.data.nbins
    minDepth = int(CD.data.depth.min())
    maxDepth = ceil(CD.data.depth.max())
    if minDepth > 0.0:
        minDepth = 0.0
    DISPLAY_FEAT.depth_range = [maxDepth, minDepth]
    DISPLAY_FEAT.axes = DISPLAY_FEAT.axes_choices[:DISPLAY_FEAT.num_axes]
    # - Define sonar name if not provided yet
    # FIXME - ultimately, all the database discovery and container sync should
    #         be done in one location
    if hasattr(CD.dbparam, "sonar") and not DISPLAY_FEAT.sonar:
        DISPLAY_FEAT.sonar = CD.dbparam.sonar
    # - Override display features with user's configuration
    if options.setting:
        for key in DISPLAY_FEAT.__dict__:
            try:
                setting_value = options.setting[key]
                if setting_value is not None:
                    DISPLAY_FEAT.__dict__[key] = setting_value
            except (AttributeError, KeyError):
                continue
    # - Refresh Codas Data
    refresh_cdata(thresholds, asciiNpaths_container, CD,
                  new_data=True)
    # Logging differences in models
    _log.debug('- Changes in DISPLAY_FEAT: '
              + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))
    _log.debug('- Changes in thresholds: '
              + dict_diff_to_str(ini_thresholds, thresholds))
    _log.debug('- ascii_container: ' + asciiNpaths_container.__str__())


def initialize_display_feat_compare_mode(
        sonars, thresholds, asciiNpaths, CD_compare, options):
    """
    Wrapping function initializing the current display features container,
    override its default values with user inputs and refresh codas model
    accordingly.

    Args:
        thresholds: editing thresholds container, model, dict. of Bunch
        asciiNpaths: ascii file names & path container, model, dict. of Bunch
        CD_compare: codas database, model, CDataCompare class
        options: set of options, ArgumentParser object
    """
    _log.debug("In initialize_display_feat")
    ini_display = DISPLAY_FEAT.__dict__.copy()
    # - Override display features with user's options
    for key in DISPLAY_FEAT.__dict__:
        try:
            user_value = getattr(options, key)
            if user_value is not None:
                DISPLAY_FEAT.__dict__[key] = user_value
        except (AttributeError, KeyError):
            continue
    # - Initialize display_features for color plots
    # FIXME: in compare mode startdd_all, enddd_all are actually different between CDs
    DISPLAY_FEAT.start_day = CD_compare.startdd_all
    DISPLAY_FEAT.day_range = [CD_compare.startdd_all, CD_compare.enddd_all]
    DISPLAY_FEAT.year_base = CD_compare.yearbase
    CD_compare.ddstep = DISPLAY_FEAT.day_step
    # Ticket 626
    # - Force same startdd for all datasets
    CD_compare.startdd = CD_compare.startdd_all
    # - At this point if CD.data == None, something's wrong with the requested time range
    CD_compare.get_data()
    if None in [CD_compare[sonar].data for sonar in CD_compare.sonars]:
        # - loop though ddstep until CD.data is or ddstep + startdd_all > startdd_all
        #       if latter raise error
        stop = False
        ddstep = CD_compare.ddstep
        while not stop:
            CD_compare.ddstep = ddstep
            if ddstep + CD_compare.startdd_all > CD_compare.enddd_all:
                _log.error('There is no data in %s' % CD_compare.sonars)
                sys.exit(1)
            if None in [CD_compare[sonar].data for sonar in CD_compare.sonars]:
                ddstep *= 2.0
                _log.debug(
                    "No data found in %s. Increasing initial time step to %s",
                    CD_compare.sonars, ddstep)
            else:
                _log.debug("Finally found data in %s for ddstep = %s",
                          CD_compare.sonars, ddstep)
                DISPLAY_FEAT.day_step = ddstep
                stop = True
    # - Finish initialize DISPLAY_FEATURES for color plots
    DISPLAY_FEAT.time_range = [DISPLAY_FEAT.start_day,
                               DISPLAY_FEAT.start_day + DISPLAY_FEAT.day_step]
    # - Override display features with user's configuration
    if options.setting:
        for key in DISPLAY_FEAT.__dict__:
            try:
                setting_value = options.setting[key]
                if setting_value is not None:
                    DISPLAY_FEAT.__dict__[key] = setting_value
            except (AttributeError, KeyError):
                continue
    # - Mine data from CD s
    nb_bins_list = []
    min_depth_list = []
    max_depth_list = []
    for sonar_name in sonars:
        t = thresholds[sonar_name]
        ini_thresholds = t.copy()
        a = asciiNpaths[sonar_name]
        CD = CD_compare[sonar_name]
        if CD.data is not None:
            nb_bins_list.append(CD.data.nbins)
            min_depth_list.append(int(CD.data.depth.min()))
            max_depth_list.append(ceil(CD.data.depth.max()))
            # - Refresh Codas Data
            refresh_cdata(t, a, CD, new_data=True)
            # Logging differences in models
            _log.debug('- Changes in thresholds: '
                      + dict_diff_to_str(ini_thresholds, t))
            _log.debug('- ascii_container: ' + a.__str__())
        # - Redefine default panels
        # FIXME - this is going to break when num_axes > 14
        DISPLAY_FEAT.axes_choices[CD.sonar].extend(CD.diff_aliases)
        DISPLAY_FEAT.axes = DISPLAY_FEAT.axes_choices[CD.sonar][
                            :DISPLAY_FEAT.num_axes]
        DISPLAY_FEAT.sonars = DISPLAY_FEAT.sonar_choices[:]
    # - Propagate in display_container
    DISPLAY_FEAT.num_bins = max(nb_bins_list)
    minDepth = min(min_depth_list)
    if minDepth > 0.0:  # sanity check
        minDepth = 0.0
    DISPLAY_FEAT.depth_range = [max(max_depth_list), minDepth]
    # - Extending DISPLAY_FEAT.sonars until it matches len(DISPLAY_FEAT.axes_choices)
    len_diff = DISPLAY_FEAT.num_axes - len(DISPLAY_FEAT.sonars)
    if len_diff > 0:
        for ii in range(len_diff):
            DISPLAY_FEAT.sonars.insert(-1, DISPLAY_FEAT.sonar_choices[-1])
    elif len_diff < 0:
        DISPLAY_FEAT.sonars = DISPLAY_FEAT.sonar_choices[:len_diff]

    # Logging differences in models
    _log.debug('- Changes in DISPLAY_FEAT: '
              + dict_diff_to_str(ini_display, DISPLAY_FEAT.__dict__))


### Tools for communication between txycursors, views and models ###
def initialize_txycursors(colorPlotWindowList, topoMapWindow):
    """
    Initialize a custom multi-cursor
    Args:
        colorPlotWindow: color plot panels' window, view, qtpy widget
        topoMapWindow: topo. map's window, view, qtpy widget

    Returns: custom multi-cursor, TXYCursors
    """
    _log.debug("In initialize_txycursors")
    CD = topoMapWindow.CD
    # Ticket 626
    # Sanity check - due to non-overlapping datasets in compare mode
    if CD.data is not None and hasattr(topoMapWindow, 'bmap'):  # if no bmap == no data available:
        new_xmap, new_ymap = topoMapWindow.bmap.projtran(CD.data.lon, CD.data.lat)
        dday = CD.data.dday
    else:
        new_xmap, new_ymap = [], []
        dday = []
    canvasNaxes = []
    for colorPlotWindow in colorPlotWindowList:
        canvas = colorPlotWindow.canvas
        axlist = []
        for ax in colorPlotWindow.axdict['pcolor']:
            axlist.append(ax)
        canvasNaxes.append([canvas, axlist])

    txycursors = TXYCursors(dday, new_xmap, new_ymap,
                            topoMapWindow.canvas, canvasNaxes)
    txycursors.update_topocursor(topoMapWindow.topax)

    return txycursors


def refresh_topo_txycursors(topoMapWindow, txyCursors):
    """
    Refresh the given topo. map's custom multi-cursor

    Args:
        topoMapWindow: topo. map's window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
    """
    _log.debug("In refresh_topo_txycursors")
    _log.debug('- DISPLAY_FEAT: \n' + DISPLAY_FEAT.__str__())

    CD = topoMapWindow.CD
    if CD.data is not None:
        new_t = CD.data.dday
        txyCursors.update_topocursor(topoMapWindow.topax)
        if not hasattr(topoMapWindow, 'bmap'):  # if no bmap == no data available
            topoMapWindow.draw_topo_map()
        # if no bmap == still no data available...just bomb out cause there is no good data.
        if not hasattr(topoMapWindow, 'bmap'):
            #  Switch cursors
            txyCursors.set_visible(DISPLAY_FEAT.multicursor)
            return
        new_xmap, new_ymap = topoMapWindow.bmap.projtran(
            CD.data.lon, CD.data.lat)
        txyCursors.update_data(new_t, new_xmap, new_ymap)
    #  Switch cursors
    txyCursors.set_visible(DISPLAY_FEAT.multicursor)


def refresh_colorplot_txycursors(colorPlotWindow, topoMapWindow, txyCursors):
    """
    Refresh the given color plot's custom multi-cursor

    Args:
        colorPlotWindow: color plot panels' window, view, qtpy widget
        topoMapWindow: topo. map's window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
    """
    _log.debug("In refresh_colorplot_txycursors")
    _log.debug('- DISPLAY_FEAT: \n' + DISPLAY_FEAT.__str__())

    #       update txyCursors color plots' multi-cursors
    canvas = colorPlotWindow.canvas
    axlist = []
    for ax in colorPlotWindow.axdict['pcolor']:
        axlist.append(ax)
        ax.clear()
    canvasNaxes = [[canvas, axlist]]
    txyCursors.update_plotcursors(txyCursors, canvasNaxes)
    #  Switch cursors
    txyCursors.set_visible(DISPLAY_FEAT.multicursor)
    topoMapWindow.toolbar.home()


### Tools for communication between user and model ###
def shall_the_manual_masks_be_reset(CD):
    """
    Create a pop-up dialog box
    """
    _log.debug("In shall_the_manual_masks_be_reset")
    if CD.mode == 'compare':
        summation = 0
        for sonar in CD.sonars:
            summation += CD[sonar].zapperMask.sum()
        flag = summation == 0
    else:
        flag = (CD.zapperMask.sum() + CD.bottomMask.sum()) == 0
    if not flag:
        message = str("This operation will delete/reset the manual edits.\n" +
                      "        Are you sure you to continue?")
        return CustomDialogBox(message)
    else:
        # mimic CustomDialogBox structure
        return Bunch({'answer': True})


def shall_the_masks_be_reset(CD):
    """
    Create a pop-up dialog box
    """
    _log.debug("In shall_the_masks_be_reset")
    if CD.mode == 'compare':
        summation = 0
        for sonar in CD.sonars:
            summation += CD[sonar].zapperMask.sum()
        flag = summation == 0
    else:
        flag = (CD.zapperMask.sum() + CD.bottomMask.sum()
                + CD.thresholdsMask.sum()) == 0
    if not flag:
        message = str("This operation will delete/reset the staged edits.\n" +
                      "        Are you sure you to continue?")
        return CustomDialogBox(message)
    else:
        # mimic CustomDialogBox structure
        return Bunch({'answer': True})


### Tools for comm. betwwen ascii and CODAS models ###
def write_edits_to_tmp_ascii(editsMask, profileMask, bottomIndexes,
                             ascii_container, CD):
    """
    Write staged edits to temporary ascii files

    Args:
        editsMask: bin wise mask, 2D numpy array
        profileMask: profile wise mask, 1D numpy array
        bottomIndexes: list of bottom indexes, 1D numpy masked array
        ascii_container: ascii file names & path container, model
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug("In write_edits_to_tmp_ascii")
    _log.debug('- ascii_container: \n' + ascii_container.__str__())

    ### Based on legacy code ###
    # Make sure to pass the original edges times (x) to be consistent
    # with legacy code. Hence, dday = CD.Xe[1:, 0].
    # Note that Xe = np.insert(x, 0, x[0] - dx)
    # (see codas_data_model.set_grid1D)
    dday = CD.Xe[1:, 0]
    year_base = CD.yearbase
    if editsMask.shape:
        flags = Flags(flags=editsMask, names=['bad'])  # FIXME Legacy code
        write_badbins(dday, year_base, ['bad'], flags,
                      outfile=ascii_container.tmp_edit_paths['badbin'],
                      openstyle='a')
    #  * bad profiles
    if profileMask.shape:
        flags = Flags(flags=profileMask, names=['bad'])  # FIXME Legacy code
        write_badprf(dday, year_base, flags,
                     outfile=ascii_container.tmp_edit_paths['badprf'],
                     openstyle='a')
    #  * seabed/bottom line
    if bottomIndexes.shape:
        write_mab(dday, year_base, bottomIndexes,
                  outfile=ascii_container.tmp_edit_paths['bottom'],
                  openstyle='a')


def apply_edits_to_CODAS_database(thresholds, ascii_container, CD):
    """
    Apply staged edits to CODAS database

    Args:
        thresholds: editing thresholds container, model, Bunch
        ascii_container: ascii file names & path container, model
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug("In apply_edits_to_CODAS_database")
    _log.debug('- thresholds: \n' + thresholds.__str__())
    _log.debug('- ascii_container: \n' + ascii_container.__str__())

    #  a. update DB
    ### Based on legacy code ###
    params = CD.dbparam.copy()
    params['auto'] = True
    params.update(thresholds.current_values)
    dbinfo_param = get_dbinfo(CD.dbpathname)
    if dbinfo_param:
        params.update(dbinfo_param.cachedict)
    # For retro compatibility purposes
    params = backward_compatibility_quick_fix(params, CD)
    # FIXME: strip down proc and use only run_applyedit
    proc = Processor(params)
    proc.run_applyedit(abs_db_path=CD.dbpathname,
                       workdir=ascii_container.edit_dir_path,
                       log_path=ascii_container.log_path,
                       verbose=False)


def reset_edits_in_CODAS_database(ddrange, ascii_container, CD):
    """
    Reset editing from CODAS database

    Args:
        ddrange: time range, list of decimal days (floats)
        ascii_container: ascii file names & path container, model
        CD: codas database, model, CData class
    """
    # Logging
    _log.debug("In reset_edits_in_CODAS_database")
    _log.debug('- ascii_container: \n' + ascii_container.__str__())

    ### Based on legacy code ###
    # Format time range
    startdd, enddd = ddrange
    t1 = to_datestring(CD.yearbase, startdd)
    t2 = to_datestring(CD.yearbase, enddd)
    # Get/set database parameters
    params = CD.dbparam.copy()
    params['auto'] = True
    dbinfo_param = get_dbinfo(CD.dbpathname)
    if dbinfo_param:
        params.update(dbinfo_param.cachedict)
    # For retro compatibility purposes
    params = backward_compatibility_quick_fix(params, CD)
    # FIXME: strip down proc and use only write/clear/run_clearflags
    # Reset edits in database and log in %MODE%.log
    proc = Processor(params)
    proc.write_clearflags(
        os.path.join(ascii_container.edit_dir_path, 'clearflags.tmp'),
        tr='%s to %s' % (t1, t2), db_dir=CD.dbpathname)
    # Logging in %MODE%.log
    proc.run_clearflags(workdir=ascii_container.edit_dir_path)
    ascii_container.write_to_log(
        '\n  Removed flags from ascii files in dday range %7.2f -%7.2f' %
        (startdd, enddd))
    # Clean up
    ascii_container.cull_asc_dates(CD.yearbase, ddrange=[startdd, enddd])
    ascii_container.remove_tmp_files()
