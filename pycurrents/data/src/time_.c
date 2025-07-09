#include "time_.h"
/*****************************************************************************
*                                                                            *
*      COMMON OCEANOGRAPHIC DATA ACCESS SYSTEM (CODAS)                       *
*                                                                            *
*      WRITTEN BY:  RAMON CABRERA, ERIC FIRING, and JULIE RANADA             *
*                   JOINT INSTITUTE FOR MARINE AND ATMOSPHERIC RESEARCH      *
*                   1000 POPE ROAD  MSB 404                                  *
*                   HONOLULU, HI 96822                                       *
*                                                                            *
*      VERSION:     3.00                                                     *
*                                                                            *
*      DATE:        APRIL 1989                                               *
*                                                                            *
*****************************************************************************/
/*-----------------------------------------------------------------------------

       FILE:  time_.c

       TIME CONVERSION & PRINTING FUNCTIONS

       This is a modified version of a subset of the routines
       from CODAS3.

*/

int CUM_MONTH_DAYS[] =
   {0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365};

/*-----------------------------------------------------------------------------

   FUNCTION:  invalid_time

      It checks a YMDHMS_TIME_TYPE structure for valid ranges.

   PARAMETER:

      t = pointer to YMDHMS_TIME_TYPE structure

   RETURNS:  0 if time is okay
             1 otherwise

   CALLED FROM:  C

*/
int invalid_time(YMDHMS_TIME_TYPE *t)
{
   if ((t->year < 1) || (t->year > 4095) ||
      (t->month < 1) || (t->month > 12) ||
      (t->day < 1) || (t->day > 31) ||
      (t->hour > 23) ||
      (t->minute > 59) ||
      (to_hundredths_sec_s(t->second) > 5999))
      return(1);
   return(0);
}

/*-----------------------------------------------------------------------------

   FUNCTION:  TIMMIN

      Given a pointer to a ymdhms_time structure it returns the time
      in minutes since "JANUARY 1, 1  at 00:00"

      Note:  no validity check is done on t

   PARAMETER:

      t = pointer to struct/array of type YMDHMS_TIME_TYPE

   RETURNS:  minutes from "JAN 1, 1 at 00:00"

   CALLED FROM:  C, FORTRAN

*/
unsigned int TIMMIN(YMDHMS_TIME_TYPE *t)
{
   unsigned int l_1440 = 1440, l_365 = 365;
   unsigned int m, y;

   m = l_1440 * (CUM_MONTH_DAYS[t->month] + t->day - 1)
      + 60 * t->hour + t->minute;
   if ((y = t->year - 1) > 0)
      m += l_1440 * (l_365 * y + y / 4 - y / 100 + y / 400);
   if (!(t->year % 4) && ((t->year % 100) ||
      !(t->year % 400)) && t->month > 2)
   m += l_1440;
   return(m);
}

/*-----------------------------------------------------------------------------

   FUNCTION:  MINTIM

      Given time in minutes since Jan 1, 1 at 00:00, it calculates the
      YMDHMS_TIME_TYPE equivalent.

   PARAMETERS:

      t = pointer to YMDHMS_TIME_TYPE struct/array

      m = pointer to int variable where the minutes are stored

   RETURNS:  VOID

   CALLED FROM:  C, FORTRAN

*/
void MINTIM(YMDHMS_TIME_TYPE *t, int *m)
{
   int d, y, y1, im, d1, l_1440 = 1440, l_365 = 365;

   t->second = 0;
   t->minute = *m % 60;
   t->hour = (*m / 60) % 24;
   d = *m / l_1440;
   y = d / 365.2425;
   d1 = y * l_365 + y / 4 - y / 100 + y / 400;
   if (d > d1)
   {
      d -= (d1 - 1);
      y++;
   }
   else
   {
       y1 = y - 1;
       d -= (y1 * l_365 + y1 / 4 - y / 100 + y / 400 - 1);
   }
   if (d > l_365)
   {
      if ((y % 4) || (!(y % 100) && (y % 400)))
      {
         d -= l_365;
         y++;
      }
      else if (d > 366)
      {
         d -= 366;
         y++;
      }
   }
   if (!(y % 4) && ((y % 100) || !(y % 400)))
      if (d <= 60)
      {
         if (d > 31)
         {
            im = 2;
            d -= 31;
         }
         else im = 1;
      }
      else
      {
         im = (--d) / 29;
         if (d > CUM_MONTH_DAYS[im + 1]) im++;
         d -= CUM_MONTH_DAYS[im];
      }
   else
   {
      im = d / 29;
      if (d > CUM_MONTH_DAYS[im + 1]) im++;
      d -= CUM_MONTH_DAYS[im];
   }
   t->year = y;
   t->month = im;
   t->day = d;
   return;
}

/*-----------------------------------------------------------------------------

   FUNCTION:  TIMDIF

      Given pointers to two YMDHMS_TIME_TYPE structures, it returns the
      difference in seconds between the second and the first times.

      Note:  no validity check is done on t1 and t2

   PARAMETERS:

      t1 = pointer to first time

      t2 = pointer to second time

   RETURNS: (t2 - t1) in seconds

   CALLED FROM:  C, FORTRAN

*/
int TIMDIF(YMDHMS_TIME_TYPE *t1, YMDHMS_TIME_TYPE *t2)
{
   return((TIMMIN(t2) - TIMMIN(t1)) * 60 +
      ((int)t2->second - (int)t1->second));
}

/*-----------------------------------------------------------------------------

   FUNCTION:  DIFTIM

      Given a reference YMDHMS_TIME_TYPE t1 and a number of seconds s from
      that time, this function calculates the YMDHMS_TIME_TYPE t2 as t1 + s.

      Note:  no validity check is done on t1 and t2

   PARAMETERS:

      t1 = pointer to reference YMDHMS_TIME_TYPE

      t2 = pointer to resulting YMDHMS_TIM_TYPE

      s = pointer to number of seconds from reference time t1

   RETURNS:  VOID

   CALLED FROM:  C, FORTRAN

*/
void DIFTIM(YMDHMS_TIME_TYPE *t1, YMDHMS_TIME_TYPE *t2, int *s)
{
   int m, ss;

   ss = to_hundredths_sec_s(t1->second) / 100 + (*s);
   m = TIMMIN(t1) + div_pr(ss,60);
   MINTIM(t2, &m);
   t2->second = mod_pr(ss,60);
}

/*-----------------------------------------------------------------------------

   FUNCTION: TIMCMP

      It compares two YMDHMS_TIME_TYPE structures/arrays.

      Note:  no validity check is done on t1 and t2

   PARAMETERS:

      t1 = pointer to first time

      t2 = pointer to second time

   RETURNS:  0 if t1 = t2
             1 if t1 < t2
             2 if t2 < t1

   CALLED FROM:  C, FORTRAN

*/
int TIMCMP(YMDHMS_TIME_TYPE *t1, YMDHMS_TIME_TYPE *t2)
{
   short int t1_hs, t2_hs;

   if (t1->year < t2->year)     return(1);
   if (t1->year > t2->year)     return(2);
   if (t1->month < t2->month)   return(1);
   if (t1->month > t2->month)   return(2);
   if (t1->day < t2->day)       return(1);
   if (t1->day > t2->day)       return(2);
   if (t1->hour < t2->hour)     return(1);
   if (t1->hour > t2->hour)     return(2);
   if (t1->minute < t2->minute) return(1);
   if (t1->minute > t2->minute) return(2);
   t1_hs = to_hundredths_sec_s(t1->second);
   t2_hs = to_hundredths_sec_s(t2->second);
   if (t1_hs < t2_hs) return(1);
   if (t1_hs > t2_hs) return(2);
   return(0);
}

/*-----------------------------------------------------------------------------

   FUNCTION:  year_day

      It converts a YMDHMS_TIME_TYPE into a double-precision number of
      days from the beginning of a base year.

      NOTE: If this number is given with seven digits after the decimal,
      there is no loss of accuracy.  Therefore a double precision number
      is adequate for a period of many years from the base time.

   PARAMETERS:

      ymdhms_time = time to be converted
      year_base   = year to use

   RETURNS:  time in decimal days

*/
double year_day(YMDHMS_TIME_TYPE *time, int year_base)
#define hundredths_seconds_per_minute 6000.0
#define hundredths_seconds_per_day 8640000.0
{
   YMDHMS_TIME_TYPE base;

   base.year = year_base;
   base.month = base.day = 1;   /* January 1 */
   base.hour = base.minute = base.second = 0;
   return( ((int) (TIMMIN(time) - TIMMIN(&base))) * hundredths_seconds_per_minute
      + to_hundredths_sec_s(time->second)) / hundredths_seconds_per_day;
}

#define minutes_per_day 1440.0
#define seconds_per_day 86400.0

/*-----------------------------------------------------------------------------

   FUNCTION:  yd_to_ymdhms_time

      It converts time expressed in decimal days to a YMDHMS_TIME_TYPE
      structure.

   PARAMETERS:

      yd = time to be converted (double-precision decimal days)
      year_base = year to use

      time_ptr = ptr to YMDHMS_TIME_TYPE result

   RETURNS:  void
*/


void yd_to_ymdhms_time(double yd, int year_base, YMDHMS_TIME_TYPE *time_ptr)
{
   YMDHMS_TIME_TYPE base, base_min;
   double dsec;
   int sec;
   int yd_min, y;

   base.year = year_base;
   base.month = base.day = 1;
   base.hour = base.minute = base.second = 0;
   yd_min = (int)(yd * minutes_per_day);
   y = yd_min + TIMMIN(&base);
   MINTIM(&base_min, &y);
   dsec = (yd * minutes_per_day - yd_min) * 60.0;
   sec = (int) round_val(dsec);
   DIFTIM(&base_min, time_ptr, &sec);
   return;
}
