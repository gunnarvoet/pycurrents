import numpy as np
from numpy.testing import assert_equal, assert_allclose

import pytest

from pycurrents.data.timetools import dt64_to_day
from pycurrents.file.matfile import (
    datenum_to_dt64,
    dt64_to_datenum,
    datenum_to_day,
    day_to_datenum,
    datenum_to_mpl,  # to be deprecated...
)


@pytest.mark.parametrize("units", ["s", "ms"])
def test_datetime64(units):
    # Test with octave, a Matlab clone.
    # octave:5> datenum(2022, 1, 2, 3, 4, 5)
    # ans = 738523.1278356481
    # octave:6> datenum(2022, 5, 4, 3, 2, 1)
    # ans = 738645.1264004629
    dnums = [738523.1278356481, 738645.1264004629]
    dts_expected = np.array(["2022-01-02T03:04:05", "2022-05-04T03:02:01"]).astype(
        f"datetime64[{units}]"
    )
    assert_equal(datenum_to_dt64(dnums, units), dts_expected)
    assert_equal(dt64_to_datenum(dts_expected), dnums)


@pytest.mark.parametrize("yearbase", [1960, 1970, 2000, 2025])
def test_dday(yearbase):
    dnums = [738523.1278356481, 738645.1264004629]
    dts = datenum_to_dt64(dnums)
    day_expected = dt64_to_day(yearbase, dts)
    day = datenum_to_day(dnums, yearbase)
    assert_allclose(day, day_expected)
    assert_equal(day_to_datenum(day, yearbase), dnums)


def test_datenum_to_mpl():
    # We are assuming the current mpl default epoch: the unix epoch.
    dnums = [738523.1278356481, 738645.1264004629]
    dn_mpl = datenum_to_mpl(dnums)
    assert_allclose(dn_mpl, datenum_to_dt64(dnums, units="s").astype(float) / 86400)
