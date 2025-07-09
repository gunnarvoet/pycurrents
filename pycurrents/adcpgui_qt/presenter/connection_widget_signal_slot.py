# This GUI is built around a MVP design pattern:
#   - See pycurrents/adcpgui_qt/lib/images/Model_View_presenter_GUI_Design_Pattern.png
#   - See https://www.codeproject.com/Articles/228214/...
#         ...Understanding-Basics-of-UI-Design-Pattern-MVC-MVP
import logging

from pycurrents.adcpgui_qt.presenter.slots import (OnTimeStartChange,
    OnTimeStepChange, OnToggleChange, OnRefreshPanel, OnRefCDChange,
    OnMaskChange, OnVelRangeChange, OnBinRangeChange, OnVectScaleChange,
    OnShow, OnNext, OnPrev, OnZoomTopo, OnVectAveragingChange,
    OnSaturate, OnShowStagedEdit, OnThresholdChange, OnThresholdTick,
    OnZappers, OnBottomSelector, OnResetSelector, OnReturnInThresholdEntry,
    OnResetThresholds, OnResetEditing, OnApplyEditingCompareMode,
    OnDepthRangeChange, OnDiffRangeChange, OnAutoscale, OnApplyEditing,
    OnPingStartChange, OnPingStepChange, OnPlotRaw, OnNextRaw, OnPreviousRaw,
    OnPickPingStart, OnPercentGoodCutoffSave, refresh_topo_map,
    refresh_color_plot)

# Singletons
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton

# Standard logging
_log = logging.getLogger(__name__)


DISPLAY_FEAT = DisplayFeaturesSingleton()


def connect_control_panels_topo(mode,
        controlWindow, colorPlotWindow, topoMapWindow, txyCursors,  # Views
        thresholds, asciiNpaths_container, CD):  # Models
    """
    Set the connection between widgets, signals and slots (aka functions)
    in particular between the control, panels and topographic windows (views)
    and CODAS Database and display features containers (models)

    Args:
        mode: GUI mode, str.
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        topoMapWindow: topo. map's window, view, qtpy widget
        txyCursors: multi window cursor, Custom Matplotlib Multicursor
        thresholds: editing thresholds container, model, Bunch
        asciiNpaths_container: container of ascii files & system paths, model
        CD: codas database, model, CData class
    """
    # N.B.: some functions will be subject to changes if the structure or
    #       or underlying library (qtpy here) of the guiApp changes
    timeNav = controlWindow.timeNavigationBar
    plotTab = controlWindow.tabsContainer.plotTab
    if mode == 'edit':
        thresholdsTab = controlWindow.tabsContainer.thresholdsTab
    # FIXME: rather than having if statement per mode, dev. sub-function per class
    # Time navigation
    timeNav.entryStart.textChanged.connect(
        lambda: OnTimeStartChange(controlWindow))
    timeNav.entryStep.textChanged.connect(
        lambda: OnTimeStepChange(controlWindow))
    timeNav.buttonShow.clicked.connect(
        lambda: OnShow(controlWindow, colorPlotWindow, topoMapWindow,
                       txyCursors, thresholds,
                       asciiNpaths_container, CD))
    timeNav.buttonNext.clicked.connect(
        lambda: OnNext(controlWindow, colorPlotWindow, topoMapWindow,
                       txyCursors, thresholds,
                       asciiNpaths_container, CD))
    timeNav.buttonPrev.clicked.connect(
        lambda: OnPrev(controlWindow, colorPlotWindow, topoMapWindow,
                       txyCursors, thresholds,
                       asciiNpaths_container, CD))
    # Plot tab
    # - Manual editing
    if mode in ['edit', 'compare']:
        plotTab.checkboxShowZapperEdit.clicked.connect(
            lambda: OnShowStagedEdit(controlWindow, colorPlotWindow))
        if mode == 'edit':
            plotTab.checkboxShowBottomEdit.clicked.connect(
                lambda: OnShowStagedEdit(controlWindow, colorPlotWindow))
            plotTab.checkboxShowThresholdEdit.clicked.connect(
                lambda: OnShowStagedEdit(controlWindow, colorPlotWindow))
    # - Panels
    plotTab.refreshPanelsButton.clicked.connect(
        lambda: OnRefreshPanel(
            controlWindow, colorPlotWindow, topoMapWindow, txyCursors,
            thresholds, asciiNpaths_container, CD))
    # - Toggles
    plotTab.checkboxShowHeading.clicked.connect(
        lambda: OnToggleChange(controlWindow, colorPlotWindow, txyCursors, CD))
    plotTab.checkboxShowSpeed.clicked.connect(
        lambda: OnToggleChange(controlWindow, colorPlotWindow, txyCursors, CD))
    plotTab.checkboxShowMCursor.clicked.connect(
        lambda: OnToggleChange(controlWindow, colorPlotWindow, txyCursors, CD))
    plotTab.checkboxZBins.clicked.connect(
        lambda: OnToggleChange(controlWindow, colorPlotWindow, txyCursors, CD))
    plotTab.checkboxXTicks.clicked.connect(
        lambda: OnToggleChange(controlWindow, colorPlotWindow, txyCursors, CD))
    if mode in ['edit', 'compare']:
        plotTab.checkboxSaturate.clicked.connect(
        lambda: OnSaturate(controlWindow, colorPlotWindow))
    #  * masking
    plotTab.radiobuttonNoFlags.clicked.connect(
        lambda: OnMaskChange(controlWindow, colorPlotWindow, thresholds, CD))
    plotTab.radiobuttonCodas.clicked.connect(
        lambda: OnMaskChange(controlWindow, colorPlotWindow, thresholds, CD))
    if mode == 'edit':
        plotTab.radiobuttonAll.clicked.connect(
            lambda: OnMaskChange(controlWindow, colorPlotWindow,
                                 thresholds, CD))
        plotTab.radiobuttonLowPG.clicked.connect(
            lambda: OnMaskChange(controlWindow, colorPlotWindow,
                                 thresholds, CD, plotTab.entryPGCutoff.value()))
    # - Plotting
    #  * velocity range
    plotTab.entryVelMin.textChanged.connect(
        lambda: OnVelRangeChange(controlWindow))
    plotTab.entryVelMax.textChanged.connect(
        lambda: OnVelRangeChange(controlWindow))
    #  * velocity diff range
    if mode == 'compare':
        plotTab.entryDiffMin.textChanged.connect(
            lambda: OnDiffRangeChange(controlWindow))
        plotTab.entryDiffMax.textChanged.connect(
            lambda: OnDiffRangeChange(controlWindow))
    #  * depth range
    if mode in ['edit', 'compare']:
        plotTab.depthRange.entryMin.textChanged.connect(
            lambda: OnDepthRangeChange(controlWindow))
        plotTab.depthRange.entryMax.textChanged.connect(
            lambda: OnDepthRangeChange(controlWindow))
        plotTab.depthRange.checkboxAutoscale.clicked.connect(
            lambda: OnAutoscale(controlWindow, colorPlotWindow))
    #  * percent good cutoff
    if mode == 'edit':
        def slider_released():
            plotTab.entryPGCutoffText.setText(str(plotTab.entryPGCutoff.value()))
            OnMaskChange(controlWindow, colorPlotWindow,
                         thresholds, CD, plotTab.entryPGCutoff.value())

        def text_edited():
            plotTab.entryPGCutoff.setValue(int(plotTab.entryPGCutoffText.text()))
            OnMaskChange(controlWindow, colorPlotWindow, thresholds, CD, plotTab.entryPGCutoff.value())

        def threshold_saved():
            whole_file = plotTab.checkboxPGCBehavior.checkState()
            plotTab.checkboxPGCBehavior.setChecked(False)
            OnPercentGoodCutoffSave(CD, plotTab.entryPGCutoff.value(), whole_file)

        plotTab.entryPGCutoff.sliderReleased.connect(slider_released)
        #plotTab.entryPGCutoffText.returnPressed.connect(text_edited)
        plotTab.entryPGCutoffText.editingFinished.connect(text_edited)
        plotTab.entryPGCSave.clicked.connect(threshold_saved)
    # Thresholds Tab
    if mode == 'edit':
        checkBoxDict = thresholdsTab.checkboxEntryLabels
        for edit_name in thresholds.widget_features.edit_names:
            #  - Threshold entry
            checkBoxDict[edit_name].entry.textChanged.connect(
                lambda: OnThresholdChange(controlWindow, thresholds, CD))
            # - Threshold checkbox
            checkBoxDict[edit_name].checkbox.stateChanged.connect(
                lambda: OnThresholdTick(controlWindow, colorPlotWindow,
                                        thresholds, CD))
            # - Connect return in entry to update_masks and re-draw masks
            checkBoxDict[edit_name].entry.returnPressed.connect(
                lambda: OnReturnInThresholdEntry(colorPlotWindow))
        # - Reset thresholds
        thresholdsTab.buttonResetThreshold.clicked.connect(
            lambda: OnResetThresholds(controlWindow, colorPlotWindow,
                                      thresholds))
    # Topo. window's controllers
    #  * bin range
    topoMapWindow.entryBinLower.textChanged.connect(
        lambda: OnBinRangeChange(topoMapWindow))
    topoMapWindow.entryBinUpper.textChanged.connect(
        lambda: OnBinRangeChange(topoMapWindow))
    #  * vector scale
    topoMapWindow.entryVectScale.textChanged.connect(
        lambda: OnVectScaleChange(topoMapWindow))
    #  * vector averaging
    topoMapWindow.entryVectAveraging.textChanged.connect(
        lambda: OnVectAveragingChange(topoMapWindow))
    #  * Ref. CD change
    if mode == 'compare':
        topoMapWindow.refSonarDropdown.currentIndexChanged.connect(
        lambda: OnRefCDChange(topoMapWindow, txyCursors, CD))

    # Mouse & keyboard events
    # - Return
    timeNav.entryStart.returnPressed.connect(
        # lambda: OnReturn(controlWindow, colorPlotWindow, topoMapWindow,
        #                  txyCursors, thresholds,
        #                  asciiNpaths_container, CD))
        # More drastic refresh
        lambda: OnShow(controlWindow, colorPlotWindow, topoMapWindow,
                       txyCursors, thresholds,
                       asciiNpaths_container, CD))

    timeNav.entryStep.returnPressed.connect(
        # lambda: OnReturn(controlWindow, colorPlotWindow, topoMapWindow,
        #                  txyCursors, thresholds,
        #                  asciiNpaths_container, CD))
        # More drastic refresh
        lambda: OnShow(controlWindow, colorPlotWindow, topoMapWindow,
                       txyCursors, thresholds,
                       asciiNpaths_container, CD))
    plotTab.entryVelMin.returnPressed.connect(
        lambda: refresh_color_plot(controlWindow, colorPlotWindow))
    plotTab.entryVelMax.returnPressed.connect(
        lambda: refresh_color_plot(controlWindow, colorPlotWindow))
    if mode == 'compare':
        plotTab.entryDiffMin.returnPressed.connect(
            lambda: refresh_color_plot(controlWindow, colorPlotWindow))
        plotTab.entryDiffMax.returnPressed.connect(
            lambda: refresh_color_plot(controlWindow, colorPlotWindow))
    if mode in ['edit', 'compare']:
        plotTab.depthRange.entryMin.returnPressed.connect(
            lambda: refresh_color_plot(controlWindow, colorPlotWindow))
        plotTab.depthRange.entryMax.returnPressed.connect(
            lambda: refresh_color_plot(controlWindow, colorPlotWindow))
    topoMapWindow.entryBinUpper.returnPressed.connect(
        lambda: refresh_topo_map(controlWindow, topoMapWindow, txyCursors))
    topoMapWindow.entryBinLower.returnPressed.connect(
        lambda: refresh_topo_map(controlWindow, topoMapWindow, txyCursors))
    topoMapWindow.entryVectScale.returnPressed.connect(
        lambda: refresh_topo_map(controlWindow, topoMapWindow, txyCursors))
    topoMapWindow.entryVectAveraging.returnPressed.connect(
        lambda: refresh_topo_map(controlWindow, topoMapWindow, txyCursors))
    # - Zoom
    topoMapWindow.toolbar.maptoolbarsignal.connect(
        lambda: OnZoomTopo(topoMapWindow, txyCursors))
    # - hover
    # - drag
    # - close


def connect_popup_control(
        pop_up_dict,  # Dict of Pop-up windows/Views
        controlWindow):  # Display container/Models
    """
    Set the connection between widgets, signals and slots (aka functions) in
    particular between the zapper, panels and topographic windows (view) and
    the CODAS Database (model)

    Args:
        pop_up_dict: dict. of panels' windows, view, {'name': qtpy widget,...}
        controlWindow: control window, view, qtpy widget
    """

    # Plot tab
    # - Manual Editing
    plotTab = controlWindow.tabsContainer.plotTab
    editBar = controlWindow.editBar
    plotTab.buttonZapper.clicked.connect(
        lambda: OnZappers(controlWindow, pop_up_dict['zap']))
    editBar.buttonResetEditing.clicked.connect(
        lambda: OnResetSelector(controlWindow, pop_up_dict['reset']))
    if DISPLAY_FEAT.mode == 'edit':
        plotTab.buttonBottom.clicked.connect(
            lambda: OnBottomSelector(controlWindow, pop_up_dict['bottom']))


def connect_ascii_models(
        controlWindow, resetWindow,  # Views
        thresholds, asciiNpaths_container, CD):  # Models
    """
    Set the connection between widgets, signals and slots (aka functions) in
    particular between the control window, reset pop-up window and (views)
    thresholds, ascii and CODAS Database containers (models)

    Args:
        controlWindow: control window, view, qtpy widget
        resetWindow: reset editing pop-up window, qtpy widget
        thresholds: editing thresholds container, model, Bunch
        asciiNpaths_container: container of ascii files & system paths, model
        CD: codas database, model, CData class
    """
    # Apply edits
    apply = OnApplyEditingCompareMode if CD.mode == 'compare' else OnApplyEditing
    controlWindow.editBar.buttonApplyEditing.clicked.connect(
        lambda: apply(controlWindow, asciiNpaths_container, thresholds, CD)
    )
    # Reset edits
    resetWindow.buttonResetEdits.clicked.connect(
        lambda: OnResetEditing(resetWindow, asciiNpaths_container, CD)
    )


def connect_control_panels_pingplots(
        controlWindow, colorPlotWindow, pingPlotsWindows):
    """
    Set the connection between widgets, signals and slots (aka functions) in
    particular between the control window, the plotting panel, the single-ping
    plotting windows (views) and the display features' container (model)
    Args:
        controlWindow: control window, view, qtpy widget
        colorPlotWindow: color plot panels' window, view, qtpy widget
        pingPlotsWindows: single-ping plots' windows, view,
                          class containing qtpy widgets
    """
    plotTab = controlWindow.tabsContainer.plotTab
    # Inputs changes
    plotTab.entryStartPing.textChanged.connect(
        lambda: OnPingStartChange(controlWindow, colorPlotWindow))
    plotTab.entryStepPing.textChanged.connect(
        lambda: OnPingStepChange(controlWindow))
    # Button clicked
    plotTab.buttonPlot.clicked.connect(
        lambda: OnPlotRaw(colorPlotWindow, pingPlotsWindows))
    plotTab.buttonNextPing.clicked.connect(
        lambda: OnNextRaw(controlWindow, colorPlotWindow, pingPlotsWindows))
    plotTab.buttonPrevPing.clicked.connect(
        lambda: OnPreviousRaw(controlWindow, colorPlotWindow, pingPlotsWindows))
    # On return hit
    plotTab.entryStartPing.returnPressed.connect(
        lambda: OnPlotRaw(colorPlotWindow, pingPlotsWindows))
    plotTab.entryStepPing.returnPressed.connect(
        lambda: OnPlotRaw(colorPlotWindow, pingPlotsWindows))
    # On "pick" event
    #   (see https://matplotlib.org/users/event_handling.html)
    colorPlotWindow.canvas.mpl_connect(
        'button_press_event',   # 'pick_event',
        lambda event: OnPickPingStart(
            controlWindow,  colorPlotWindow, pingPlotsWindows, event))

