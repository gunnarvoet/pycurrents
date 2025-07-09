import datetime
import os
import numpy as np
from numpy.testing import assert_allclose
from pycurrents.get_test_data import get_test_data_path
from pycurrents.adcp.transform import heading_rotate
from pycurrents.adcp.raw_multi import Multiread
from pycurrents.adcp.raw_simrad import wintime_to_datetime, wintime_to_dday
from pycurrents.codas import to_day


def test_beam_order():
    fpath = os.path.join(
        get_test_data_path(), "uhdas_data/raw/os150/hly2018_149_64800.raw"
    )
    m1 = Multiread(fpath, "os")
    data1 = m1.read(stop=1)
    uv = heading_rotate(data1.xyze[:, :, :2], 0)

    m2 = Multiread(fpath, "os", beam_index=[1, 0, 3, 2])  # [2,1,4,3]
    data2 = m2.read(stop=1)
    uvrot = heading_rotate(data2.xyze[:, :, :2], 180)

    assert_allclose(uv, uvrot)


def test_wintime_to_datetime():
    wt_int = 125000000000000000
    wt_np = np.uint64(wt_int)
    target_dt = datetime.datetime(1997, 2, 9, 22, 13, 20)
    assert wintime_to_datetime(wt_int) == target_dt
    assert wintime_to_datetime(wt_np) == target_dt


def test_wintime_to_dday():
    target_dday = to_day(2025, 2025, 4, 19, 9, 43)
    unix_seconds = to_day(1970, 2025, 4, 19, 9, 43) * 86400
    win = unix_seconds * 10000000 + 116444736000000000
    win_np = np.array([win], dtype=np.uint64)
    assert_allclose(wintime_to_dday(win, 2025), target_dday, rtol=1e-12)
    assert_allclose(wintime_to_dday(win_np, 2025)[0], target_dday, rtol=1e-12)
