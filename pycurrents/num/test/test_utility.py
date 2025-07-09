import pytest

import numpy as np
from numpy.testing import assert_array_equal

from pycurrents.num import segments
from pycurrents.num import mask_nonincreasing

masks = [[0, 0, 0, 1, 1, 1],
          [1, 1, 1, 0, 0, 0],
          [0, 1, 0, 1, 0, 1],
          [1, 0, 1, 0, 1, 0],
          [0, 1, 0, 1, 0, 1, 0],
          [1, 0, 1, 0, 1, 0, 1],
          [0, 0, 0, 0, 0, 0],
          [1, 1, 1, 1, 1, 1],
          ]
expecteds1 = [[[0, 3]],
              [[3, 6]],
              [[0, 1], [2, 3], [4, 5]],
              [[1, 2], [3, 4], [5, 6]],
              [[0, 1], [2, 3], [4, 5], [6, 7]],
              [[1, 2], [3, 4], [5, 6]],
              [[0, 6]],
              np.empty((0, 2), dtype=int),
              ]

expecteds2 = expecteds1.copy()
expecteds2[0] = [[0, 2], [2, 3]]
expecteds2[1] = [[3, 5], [5, 6]]
expecteds2[6] = [[0, 2], [2, 4], [4, 6]]

@pytest.mark.parametrize('ar', zip(masks, expecteds1))
def test_segments_basic(ar):
    mask, expected = [np.array(x) for x in ar]
    found = segments(mask)
    assert_array_equal(found, expected)

@pytest.mark.parametrize('ar', zip(masks, expecteds2))
def test_segments_n(ar):
    mask, expected = [np.array(x) for x in ar]
    found = segments(mask, n=2)
    assert_array_equal(found, expected)

def test_mask_nonincreasing():
    # Test array with optional mask:
    x = [0, 1, -1, 2, 2, 3, 4, 5]
    xm = [0] * len(x)
    xm[-2] = 1
    # Manually make expected results, without and with the optional mask:
    y = np.array(x, dtype=float)
    expected = np.ma.array(y, mask=[0, 0, 1, 0, 1, 0, 0, 0])
    expected_m = expected.copy()
    expected_m[-2] = np.ma.masked

    found = mask_nonincreasing(x)
    found_m = mask_nonincreasing(np.ma.array(x, mask=xm))
    assert_array_equal(found, expected)
    assert_array_equal(found_m, expected_m)
