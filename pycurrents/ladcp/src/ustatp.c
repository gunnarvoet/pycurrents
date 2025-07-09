#include <math.h>
#include <stdio.h>

#include "ustatp.h"
/* stripped down version of unistat from codas3 vstat */

void zero_unistat(UNISTAT_TYPE *s)
{
   int i;

   s->n_increments = 0;
   for (i=0; i<s->n; i++)
   {
      (s->sum)[i] = 0.0;
      (s->npts)[i] = 0;
      (s->sumsq)[i] = 0.0;
      (s->min)[i] = 1e100;
      (s->max)[i] = -1e100;
      (s->imin)[i] = 0;
      (s->imax)[i] = 0;
   }
}                       /* zero_unistat */


/* Return the index of the first depth shallower than or equal
   to d, in a uniform depth array starting at dstart and with an
   increment of dz.
*/
int index_less(double d, double dstart, double dz)
{
   int i;
   i = (int)  ((d - dstart)/dz);
   if (i >= 0) return (i);
   else        return (0);
}

/* Return the index of the first depth deeper than or equal
   to d, in a uniform depth array starting at dstart and with an
   increment of dz.
*/
int index_more(double d, double dstart, double dz)
{
   double di;
   int i;
   di = ((d - dstart)/dz);
   i = (int) di ;
   if ( ((double) i) < di ) i++;
   if (i >= 0) return (i);
   else        return (0);
}
/* Return the index of the depth closest
   to d, in a uniform depth array starting at dstart and with an
   increment of dz.
*/
int index_closest(double d, double dstart, double dz)
{
   int i;
   i = lround((d - dstart) / dz);
   return (i);
}

void update_unistat_piece(UNISTAT_TYPE *s,
                            double *array,
                            unsigned char *mask,
                            int i0,  /* starting index into unistat arrays */
                            int na)  /* number of points in the array */
{
   double f;
   int i, ii;
   int is_min, is_max;
   //printf("in update_unistat_piece\n");
   na = na < s->n ? na : s->n;   // min_val(na, s->n);
   //printf("na is %d\n", na);
   for (ii=0; ii<na; ii++)
   {
      //printf("%d %lf %d\n", ii, array[ii], mask[ii]);
      if (mask[ii]) continue;

      i = ii + i0;
      f = array[ii];
      is_min = 0;
      is_max = 0;
      ((s->npts)[i])++;
      (s->sum)[i] += f;
      (s->sumsq)[i] += (f*f);
      if (f < (s->min)[i])
      {
         (s->min)[i] = f;
         is_min = 1;
      }
      if (f > (s->max)[i])
      {
         (s->max)[i] = f;
         is_max = 1;
      }
      if (is_min)
         (s->imin)[i] = s->n_increments;
      if (is_max)
         (s->imax)[i] = s->n_increments;
   }
   //printf("End of loop.\n");
   //printf("s->n_increments before incrementing is: %d\n", s->n_increments);
   (s->n_increments)++ ;
   //printf("s->n_increments after incrementing is: %d\n", s->n_increments);
}                       /* update_unistat_piece */

/* version with no masking or bad-checking */
void update_unistat_nomask(UNISTAT_TYPE *s,
                            double *array,
                            int i0,  /* starting index into unistat arrays */
                            int na)  /* number of points in the array */
{
   double f;
   int i, ii;
   int is_min, is_max;
   //printf("in update_unistat_piece\n");
   na = na < s->n ? na : s->n;   // min_val(na, s->n);
   //printf("na is %d\n", na);
   for (ii=0; ii<na; ii++)
   {
      //printf("%d %lf\n", ii, array[ii]);

      i = ii + i0;
      f = array[ii];
      is_min = 0;
      is_max = 0;
      ((s->npts)[i])++;
      (s->sum)[i] += f;
      (s->sumsq)[i] += (f*f);
      if (f < (s->min)[i])
      {
         (s->min)[i] = f;
         is_min = 1;
      }
      if (f > (s->max)[i])
      {
         (s->max)[i] = f;
         is_max = 1;
      }
      if (is_min)
         (s->imin)[i] = s->n_increments;
      if (is_max)
         (s->imax)[i] = s->n_increments;
   }
   //printf("End of loop.\n");
   //printf("s->n_increments before incrementing is: %d\n", s->n_increments);
   (s->n_increments)++ ;
   //printf("s->n_increments after incrementing is: %d\n", s->n_increments);
}                       /* update_unistat_piece */


/*****************************************************************

    Things from codas/vector, switched to double precision

and maybe use a mask instead of BADFLOAT?


*****************************************************************/



static double interpolate(double *z, double *f, double zi)
{
     double     del_f, del_z, dz, fi;
     del_f = f[1] - f[0];
     del_z = z[1] - z[0];
     dz    = zi - z[0];
     fi    = f[0] + dz * del_f / del_z;
     return( fi );
}


/****************************************************************
                     87-30-87

FUNCTION:  REGRID
Interpolate an array f(zo) onto a new grid, f(zn).  Instead of
simple linear interpolation, this routine approximates the function
as a set of line segments connecting the input data points.
Now, consider the output grid, and a grid of midpoints between
the output grid points.  The function at an output gridpoint is
then approximated as the average of the function (line-segment
approx. on the old grid) from one midpoint to the next (new grid).

regrid does not check for monotonically increasing grids or for
bad input array values; these are left as the responsibility of
the calling routine.

regrid alters only those elements in the output array for which
new values are calculated.   Therefore it can be used repeatedly
with different sections of the grid.  For example, if there are bad
data values, a function might scan f(zo) and call regrid once for
each section of contiguous good values.  If the output array had
been first initialized to all bad values, then the result of this
process would be an output array with interpolated data wherever
there were no gaps in the input array, and bad value flags elsewhere.

MODIFIED: Tue  09-27-1988
   Removed a bug causing extrapolation when the function is
   called with no overlap between the new and old grids.
   Changed the location of initialization of imin, imax,
   for readability.

***************************************************************/

#define min_val(x, y)        ((x)<(y)?(x):(y))
#define max_val(x, y)        ((x)>(y)?(x):(y))
#define average(x, y)        (0.5 * ((x) + (y)))

/************      regrid     *****************************/

void regrid(double zo[], double fo[], double zn[], double fn[],
            int m, int n, int *n0_ptr, int *nout_ptr)
{
     int  imin,          /* first new gridpoint index for fn  */
          imax;          /* last new gridpoint index for fn   */
     int  i, j;          /* index counters; i:new; j:old      */
     int  jlow, jhigh;
     double     zlow,     /* midway between zn(i) and zn(i-1)  */
               zhigh,    /* midway between zn(i) and zn(i+1)  */
               flow,     /* f(zlow)  (interpolated)           */
               fhigh;    /* f(zhigh) (interpolated)           */
     double     integral;

/****************************************************************
                 zo(jlow)              zo(jhigh)
         ----------|--------------------|-------------       zo
        ----|--------|--------|--------|---------|------   zn
          zn(i-1)   zlow    zn(i)     zhigh    zn(i+1)
******************************************************************/

/****Find limits of gridpoint index for new grid. *****************

           |-----------------------------------------|        zn (case a)
        -----------------------------------------------       zo
     ---|---------------------------------------------|------ zn (case b)
       imin                                         imax

     There can be no extrapolation in this version of regrid;
     data on the old grid must match or overhang the part of the
     new grid for which interpolation will be done.
*********************************************************************/

     imin = 0;
     imax = n-1;

     while( (zn[imin] < zo[0]) && (imin < n-1) ) imin++;
     while( (zn[imax] > zo[m-1]) && (imax > 0) )  imax--;

     /*** If there is no overlap between the old and
          new grids, there can be no interpolation.
          Set number of points regridded to zero, and
          quit.  If this occurs, then either imin = n-1
          or imax = 0; the converse is NOT true.
     ***/
     if ( (zn[imin] < zo[0]) || (zn[imax] > zo[m-1]) )
     {
          *nout_ptr = 0;
          return;
     }

     /*** Otherwise, the first interpolated point will be
          at index imin, and the last will be at imax.
     ***/
     *n0_ptr = imin;
     *nout_ptr = imax - imin + 1;


     /*** Initialize ?high to start the loop.
          In the loop ?high is immediately replaced by ?low,
          and a new ?high is calculated.
     ***/
     if (imin==0) zhigh = zn[imin];
     else
     {
          zhigh = average( zn[imin], zn[imin+1] );
          zhigh = max_val( zhigh, zo[0] );
     }
     jhigh = 1;
     while( (zo[jhigh] < zhigh) && (jhigh < m-1) ) jhigh++;
     /* This is one past initial jlow.  */
     fhigh = interpolate( zo+jhigh-1, fo+jhigh-1, zhigh);

     for ( i=imin; i<=imax; i++)
     {          /* I think this could be rearranged for compactness */
          zlow = zhigh;
          if ( i == imax)
          {
               if (imax==n-1)  zhigh = zn[imax];
               else
               {
                    zhigh = average(zn[i], zn[i+1]);
                    zhigh = min_val( zhigh, zo[m-1] );
               }
          }
          else  zhigh = average( zn[i], zn[i+1] );

          jlow = jhigh-1;      /* new jlow is 1 to left of old jhigh */
          while ( (zo[jhigh] < zhigh) && (jhigh < m-1) ) jhigh++;
          flow = fhigh;
          fhigh = interpolate(zo+jhigh-1, fo+jhigh-1, zhigh);
          if ( jhigh == (jlow+1) )
               fn[i] = interpolate(zo+jlow, fo+jlow, zn[i]);
          else                               /* all other cases       */
          {
               /** end pieces are needed first **/
               integral = average(flow,fo[jlow+1]) * (zo[jlow+1]-zlow)
                        + average(fhigh,fo[jhigh-1]) * (zhigh-zo[jhigh-1]);
               /** now the middle sections  **/
               for (j=jlow+1; j<jhigh-1; j++)
                    integral += average(fo[j], fo[j+1]) * (zo[j+1]-zo[j]);
               fn[i] = integral / (zhigh - zlow);
          }
     }
     return;
}
/**************** end of regrid()  ************************************/


// Maybe we can use straight regrid.
#if 0
/**************************************************************

   S_REGRID.C

   This function regrids an array with or without gaps,
   leaving BADFLOAT in the gaps.  It also checks to see
   that the new grid increases with index.  If not,
   then the two grids are negated before and after
   regridding, for no net change.  There is still no
   checking for monotonicity of either grid, or for
   the same sense of change in both.

   The function returns the number of good points in the new array.

   The function of changing decreasing into increasing
   grids could be done in a modified version of regrid()
   itself.

*/

/* Note: in the variables, a second character of 'o' means
   "old", and 'n' means "new", that is, the regridded version.
*/

int s_regrid(double *zo, double *fo, double *zn, double *fn, int no, int nn)
{
   int i;
   int in0 = 0, inm;
   int io0, io1;
   int n0, nout;
   int negate = 0;
   int ngood = 0;

/* Find the valid range of zn.  It is the first range with no gaps. */

   while ((in0 < nn) && !good_double(zn[in0]))   in0++;
   inm = in0;
   while ((inm < nn) && good_double(zn[inm]))   inm++;

/* Check for increasing zn; otherwise negate zn and zo. */

   if (zn[in0] > zn[inm-1])   negate = 1;

   if (negate)
      for (i=in0; i<inm; i++)
         zn[i] = -zn[i];

/* Initialize fn as bad everywhere. */

   for (i=0; i<nn; i++)  fn[i] = BADFLOAT;

/* Find each good range in fo, and regrid it.*/

   io0 = 0;
   while (io0 < no)
   {
      while ((io0 < no) && (!good_double(fo[io0]))) io0++;
      /* Now io0 is no or the beginning of a good section. */

      io1 = io0;
      while ((io1 < no) && (good_double(fo[io1]))) io1++;
      /* Now io1 is no or the beginning of a bad section. */
      /* If either is n, both should be n */

      if (negate)
         for (i=io0; i<io1; i++)
            zo[i] = -zo[i];

      if (io1-io0 > 1)
      {
         regrid(zo+io0, fo+io0, zn+in0, fn+in0, io1-io0, inm-in0, &n0, &nout);
         ngood += nout;
      }

      if (negate)
         for (i=io0; i<io1; i++)
            zo[i] = -zo[i];

      io0 = io1;
   }
   if (negate)
      for (i=in0; i<inm; i++)
         zn[i] = -zn[i];

   return (ngood);
}

#endif
// hide s_regrid


