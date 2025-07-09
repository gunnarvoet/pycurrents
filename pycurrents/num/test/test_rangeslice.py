import pytest

import numpy as np

from pycurrents.num import rangeslice

intarray = np.arange(10)
floatarray = 0.5 * intarray
dtarray = np.arange(np.datetime64('2010-02-01'), np.datetime64('2010-02-11'))

arrays = [intarray, floatarray, dtarray]
ranges = [(3, 8), (3*0.5, 8*0.5),
          (np.datetime64('2010-02-04'), np.datetime64('2010-02-09'))]
deltas = [3, 3*0.5, np.timedelta64(3, 'D')]


@pytest.mark.parametrize('ar', zip(arrays, ranges))
def test_forward(ar):
    arr, ran = ar
    rs = rangeslice(arr, ran)
    lims = rs.start, rs.stop
    assert lims == (3, 8)

@pytest.mark.parametrize('ar', zip(arrays, ranges))
def test_backward(ar):
    arr, ran = ar
    rs = rangeslice(arr[::-1], ran)
    lims = rs.start, rs.stop
    assert lims == (2, 7)

@pytest.mark.parametrize('ar', zip(arrays, deltas))
def test_first(ar):
    arr, ran = ar
    rs = rangeslice(arr, ran)
    lims = rs.start, rs.stop
    assert lims == (0, 3)

@pytest.mark.parametrize('ar', zip(arrays, deltas))
def test_last(ar):
    arr, ran = ar
    rs = rangeslice(arr, -ran)
    lims = rs.start, rs.stop
    assert lims == (7, 10)

