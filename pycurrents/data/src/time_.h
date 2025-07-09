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

       FILE:  time_.h

              TIME CONVERSION FUNCTIONS

*/
#include <math.h>
#ifndef time__included
#define time__included

#define to_hundredths_sec_s(x) ((x)&0x8000?(x)^0x8000:(x)*100)
#define div_pr(n,d)          ((n)%(d)<0?(n)/(d)-1:(n)/(d))
#define mod_pr(n,d)          ((n)%(d)<0?(n)%(d)+(d):(n)%(d))
#define round_val(x)       ((long) round(x))

typedef struct
{
   unsigned short year, month, day, hour, minute, second;
} YMDHMS_TIME_TYPE;

int invalid_time(YMDHMS_TIME_TYPE *t);
unsigned int TIMMIN(YMDHMS_TIME_TYPE *t);
void MINTIM(YMDHMS_TIME_TYPE *t, int *m);
int TIMDIF(YMDHMS_TIME_TYPE *t1, YMDHMS_TIME_TYPE *t2);
void DIFTIM(YMDHMS_TIME_TYPE *t1, YMDHMS_TIME_TYPE *t2, int *s);
int TIMCMP(YMDHMS_TIME_TYPE *t1, YMDHMS_TIME_TYPE *t2);
double year_day(YMDHMS_TIME_TYPE *t, int year_base);
void yd_to_ymdhms_time(double yd, int year_base, YMDHMS_TIME_TYPE *t);

#endif /* ifndef time__included */
