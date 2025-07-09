cdef extern from "time_.h":
    ctypedef struct YMDHMS_TIME_TYPE:
        unsigned short year, month, day, hour, minute, second

    void yd_to_ymdhms_time(double yd, int year_base, YMDHMS_TIME_TYPE *t)
    double year_day(YMDHMS_TIME_TYPE *t, int year_base)
