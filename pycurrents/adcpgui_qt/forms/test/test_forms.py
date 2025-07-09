#!/usr/bin/env python3

# FIXME: use pytest-qt and qtbot to really test the GUI/Qt related parts
#        see: http://pytest-qt.readthedocs.io/en/latest/intro.html
# FIXME: use image comparison or pytest-mpl for the Matplotlib related parts
#        see: https://github.com/matplotlib/pytest-mpl?files=1
#        see: https://matplotlib.org/1.3.0/devel/testing.html

import pytest

from pytestqt import qtbot

from pycurrents.get_test_data import get_test_data_path  # BREADCRUMB: common library
from pycurrents.adcpgui_qt.forms.adcp_tree_form import ADCPTreeForm
from pycurrents.adcpgui_qt.forms.uhdas_proc_gen_form import UHDASProcGenForm
from pycurrents.adcpgui_qt.forms.vmdas_converter_form import VmdasConversionForm
from pycurrents.adcpgui_qt.forms.reform_vmdas_form import ReformVMDASForm
from pycurrents.adcpgui_qt.forms.proc_starter_form import ProcStarterForm
from pycurrents.adcpgui_qt.forms.form_dispatcher import PickDirectoryPopUp

assert qtbot


def test_adcp_tree_form(qtbot):
    test_folder_path = get_test_data_path()
    cruise_dir_path = test_folder_path + '/uhdas_data/proc/os75nb/'
    adcp_tree_form = ADCPTreeForm(cruise_dir_path=cruise_dir_path)
    qtbot.addWidget(adcp_tree_form)


def test_uhdas_proc_gen_form(qtbot):
    _ = pytest.importorskip("onship")
    test_folder_path = get_test_data_path()
    uhdas_dir_path = test_folder_path + '/uhdas_data/'
    uhdas_proc_gen_form = UHDASProcGenForm(
        uhdas_dir=uhdas_dir_path, project_path=test_folder_path)
    qtbot.addWidget(uhdas_proc_gen_form)


def test_vmdas_converter_form(qtbot):
    test_folder_path = get_test_data_path()
    vmdas_dir_path = test_folder_path + '/vmdas_data/os75/'
    form = VmdasConversionForm(vmdas_dir_path)
    qtbot.addWidget(form)


def test_reform_vmdas_form(qtbot):
    form = ReformVMDASForm(proc_dir_path='test_dir', cruisename='test')
    qtbot.addWidget(form)


def test_proc_starter_form(qtbot):
    test_folder_path = get_test_data_path()
    reform_defs_path = test_folder_path
    reform_defs_path += '/uhdas_style_data/config/reform_defs_os75.py'
    form = ProcStarterForm(reform_defs_path=reform_defs_path)
    qtbot.addWidget(form)


def test_form_dispatcher(qtbot):
    form = PickDirectoryPopUp()
    qtbot.addWidget(form)



