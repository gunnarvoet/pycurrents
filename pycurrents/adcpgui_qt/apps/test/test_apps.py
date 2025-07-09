#!/usr/bin/env python3

# FIXME: use pytest-qt and qtbot to really test the GUI/Qt related parts
#        see: http://pytest-qt.readthedocs.io/en/latest/intro.html
# FIXME: use image comparison or pytest-mpl for the Matplotlib related parts
#        see: https://github.com/matplotlib/pytest-mpl?files=1
#        see: https://matplotlib.org/1.3.0/devel/testing.html

from pytestqt import qtbot

from pycurrents.get_test_data import get_test_data_path  # BREADCRUMB: common library

from pycurrents.adcpgui_qt.apps.figview_qt import MyMainWindow
from pycurrents.adcpgui_qt.apps.patch_hcorr_app import PatchHcorrApp
from pycurrents.adcpgui_qt.apps.plot_rbins_app import PlotRbinApp

assert qtbot


def test_figview_app(qtbot):
    test_folder_path = get_test_data_path()
    test_path = test_folder_path + '/uhdas_data/proc/os75bb/'
    figview = MyMainWindow(dirpath=test_path)
    figview.show()
    qtbot.addWidget(figview)


def test_patch_hcorr_app(qtbot):
    test_folder_path = get_test_data_path()
    test_path = test_folder_path + '/uhdas_data/proc/os150nb/'
    PatchHcorrApp(working_dir=test_path, test=qtbot)


def test_plot_rbin_app(qtbot):
    test_folder_path = get_test_data_path()
    test_path = test_folder_path + '/uhdas_data/'

    PlotRbinApp(uhdas_dir=test_path,
                rname1="posmv:pmv",
                rname2="gyro27:hdg", test=qtbot)




