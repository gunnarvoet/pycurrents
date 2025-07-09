#!/usr/bin/env python3

import os

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from optparse import OptionParser

from pycurrents.get_test_data import get_test_data_path
from pycurrents.adcpgui_qt.model.codas_data_models import CDataEdit
from pycurrents.adcpgui_qt.model.thresholds_models import Thresholds
from pycurrents.adcpgui_qt.model.display_features_models import (
    displayFeaturesEdit, DisplayFeaturesSingleton)
from pycurrents.adcpgui_qt.presenter.intercommunication import get_dbpath

from pycurrents.adcpgui_qt.lib.zappers import (
    _test_decorator, ZapperMaker, TOOL_NAMES)
from pycurrents.adcpgui_qt.lib.panel_plotter import make_axes, CPlotter
from pycurrents.adcpgui_qt.lib.plotting_parameters import COLOR_PLOT_LIST

# TODO: dev tests for write_dict2config_file and get_dict_from_config_file


def test_zappers():
    # FIXME: use qtbots to really test the interaction
    test_data_path = get_test_data_path()
    path2data = os.path.join(test_data_path + '/uhdas_data/proc/os150bb')
    dbpath = get_dbpath(path2data)
    (options, args) = OptionParser().parse_args([''])
    thresholds = Thresholds()
    options.mode = 'edit'
    options.netcdf = False

    CD = CDataEdit(thresholds, dbpath, options)
    CD.ddstep = 0.8
    CD.get_data(newdata=True)
    CD.set_grid()
    for zapper_name in TOOL_NAMES:
        figure = plt.Figure()
        canvas = FigureCanvas(figure)
        ax = figure.subplots()
        ax.plot(CD.Xc, CD.Yc, 'k.', ms=2, alpha=0.5)
        def decorator(x, y):
            return _test_decorator(x, y, ax, canvas, CD)
        zapMaker = ZapperMaker(zapper_name, decorator, ax, figure.canvas,
                               CD)
        zapMaker.get_zapper()
        # Avoid showing windows hence commenting
        # canvas.show()
        plt.close(figure)


def test_make_axes():
    figure = plt.Figure()
    axes = make_axes(figure, ['test'])
    assert(list(axes.keys()) == ['pcolor', 'cbar', 'twinx', 'triplex', 'edit'])
    plt.close(figure)


def test_cplotter():
    test_data_path = get_test_data_path()
    path2data = os.path.join(test_data_path + '/uhdas_data/proc/os75nb')
    dbpath = get_dbpath(path2data)
    (options, args) = OptionParser().parse_args([''])
    thresholds = Thresholds()
    options.mode = 'edit'
    options.netcdf = False

    CD = CDataEdit(thresholds, dbpath, options)
    CD.ddstep = 0.8
    CD.get_data(newdata=True)
    CD.set_grid()

    display_dict = displayFeaturesEdit()
    DisplayFeaturesSingleton(display_dict)

    figure = plt.Figure()
    ax_dict = make_axes(figure, ['test'])
    CP = CPlotter(figure, ax_dict)
    CP.draw(CD, 0, COLOR_PLOT_LIST[0])
    plt.close(figure)








