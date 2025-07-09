from datetime import datetime
import pytest
import numpy as np
from numpy.testing import assert_array_equal
from pycurrents.data.timetools import to_date, to_day, ddtime
from pycurrents.data.timetools import dt64_to_ymdhms, day_to_dt64
from pycurrents.data.timetools import dt64_to_day

# Only the first 4 test values may be used in the ddtime test
# because it needs to test 2-digit year formats.
dtlist = [(2010, 1, 2, 3, 4, 5),
          (2011, 2, 3, 4, 5, 6),
          (2012, 3, 4, 5, 6, 59),
          (2040, 4, 5, 6, 7, 30),
          (1450, 5, 6, 7, 8, 15),
         ]

datetimes = [datetime(*x) for x in dtlist]
dt64array = np.array(datetimes, dtype='M8[s]')
yearbase = 2011
epoch = datetime(yearbase, 1, 1, 0, 0, 0)

ddaylist = []
for dt in datetimes:
    diff = dt - epoch
    dday = diff.days + diff.seconds / 86400
    ddaylist.append(dday)

def test_to_date_scalar():
    ymdhms = to_date(yearbase, ddaylist[0])
    assert_array_equal(ymdhms, np.array(dtlist[0]))

def test_to_date_array():
    ymdhms = to_date(yearbase, ddaylist)
    assert_array_equal(ymdhms, np.array(dtlist))

def test_to_day_scalar():
    dday = to_day(yearbase, *dtlist[0])
    assert dday == ddaylist[0]

def test_to_day_array():
    dday = to_day(yearbase, np.array(dtlist))
    assert_array_equal(dday, ddaylist)

def test_dt64_to_ymdhms_scalar():
    ymdhms = dt64_to_ymdhms(dt64array[0])
    assert_array_equal(ymdhms, np.array(dtlist[0], dtype=ymdhms.dtype))

def test_dt64_to_ymdhms_array():
    ymdhms = dt64_to_ymdhms(dt64array)
    assert_array_equal(ymdhms, np.array(dtlist, dtype=ymdhms.dtype))

def test_day_to_dt64_scalar():
    dt = day_to_dt64(yearbase, ddaylist[0])
    assert dt == dt64array[0]

def test_day_to_dt64_array():
    dt = day_to_dt64(yearbase, ddaylist)
    assert_array_equal(dt, dt64array)

def test_dt64_to_day_scalar():
    day = dt64_to_day(yearbase, dt64array[0])
    assert day == ddaylist[0]

def test_dt64_to_day_array():
    day = dt64_to_day(yearbase, dt64array)
    assert_array_equal(day, ddaylist)

fmt1 = "%Y/%m/%d %H:%M:%S"
fmt2 = "%y/%m/%d %H:%M:%S"

@pytest.mark.parametrize('fmt', [fmt1, fmt2])
@pytest.mark.parametrize('dt,expected',
                          zip(datetimes[:4], ddaylist[:4]))
def test_ddtime(fmt, dt, expected):
    dtstring = dt.strftime(fmt)
    dday = ddtime(yearbase, dtstring)
    assert dday == expected
