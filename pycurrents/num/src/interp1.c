/*
    Old linear interpolation routine derived from my implementation
    for a table1 mex file.

    A nearest neighbor version has been cloned.  The two probably
    could be consolidated by using function pointers.

    Both also could be improved by using a binary search to find the
    starting point.
*/

#include <math.h>
#include "interp1.h"
void interpolate(int ip, arr1 *zold, arr2 *fold, int i, double z, arr2 *fnew,
                 double max_dz);
void nearest(int ip, arr1 *zold, arr2 *fold, int i, double z, arr2 *fnew,
             double max_dz);
void to_Bad(int i, arr2 *a);


void to_Bad(int i, arr2 *a)
{
    int j;

    for (j=0; j < a->nc; j++)
    {
        a->data[i*a->rstride + j*a->cstride] = BADVAL;
    }
}

/* Specialized function to linearly interpolate all columns of a
   given row:
*/
void interpolate(int ip, arr1 *zold, arr2 *fold, int i, double z, arr2 *fnew,
                 double max_dz)
    /* ip for i_plus: index of row past target */
    /* i is index of row in fnew */
{
   double    dz, dzratio, f0, f1;
   int j;
   int dz_OK;

   dz = (zold->data[ip*zold->stride] - zold->data[(ip-1)*zold->stride]);
   dz_OK = 1;
   if (max_dz > 0 && fabs(dz) > max_dz)
   {
      dz_OK = 0;
   }

   dzratio =   (z - zold->data[(ip-1)*zold->stride]) / dz;

   for (j=0; j < fnew->nc; j++)
   {
      f0 = fold->data[(ip-1)*fold->rstride + j*fold->cstride];
      f1 = fold->data[ip*fold->rstride + j*fold->cstride];
      if (dz_OK && f0 < TEST_BV && f1 < TEST_BV)  /* also false for NaN */
         fnew->data[i*fnew->rstride + j*fnew->cstride] =
                                            f0 + dzratio * (f1 - f0);
      else
         fnew->data[i*fnew->rstride + j*fnew->cstride] = BADVAL;
   }

}

/* Specialized function to interpolate all columns of a
   given row via nearest-neighbor selection:
*/
void nearest(int ip, arr1 *zold, arr2 *fold, int i, double z, arr2 *fnew,
             double max_dz)
    /* ip for i_plus: index of row past target */
    /* i is index of row in fnew */
{
   double dz, dzleft, dzright;
   double f[2];
   int j, iwhich;
   int dz_OK;

   dz_OK = 1;
   if (max_dz > 0)
   {
      dz = (zold->data[ip*zold->stride] - zold->data[(ip-1)*zold->stride]);
      if (fabs(dz) > max_dz)
      {
         dz_OK = 0;
      }
   }

   dzleft =   (z - zold->data[(ip-1)*zold->stride]);
   dzright =   (zold->data[(ip)*zold->stride] - z);

   iwhich = 0;
   if (dzleft >  dzright)
   {
      iwhich = 1;
   }

   for (j=0; j < fnew->nc; j++)
   {
      f[0] = fold->data[(ip-1)*fold->rstride + j*fold->cstride];
      f[1] = fold->data[ip*fold->rstride + j*fold->cstride];
      if (dz_OK && f[0] < TEST_BV && f[1] < TEST_BV)  /* also false for NaN */
         fnew->data[i*fnew->rstride + j*fnew->cstride] = f[iwhich];
      else
         fnew->data[i*fnew->rstride + j*fnew->cstride] = BADVAL;
   }

}


/************      regridli     *****************************/

int regridli(arr1* zo, arr2* fo, arr1* zn, arr2* fn, double max_dz)
/*        zo[],           input array of m depths: "z_old"
          fo[],           input array of m; f(z_old)
          zn[],           input array of n depths: "z_new".
          fn[],           output array of n; f(z_new)
          max_dz          if dz is larger, yield BADVAL
*/
{
   int  i;
   int  jhigh;
   int  increasing;    /* 1 if zo increases, 0 if it decreases */
   int       jmax;
   double    zz, z0, z1;
   int nold, nnew;
   int count;

   nnew = zn->n;
   nold = zo->n;
   if (nold < 2)
   {
      return 1; //mexErrMsgTxt("Need more than one row in the table.");
   }
   count = 0;
   for (i = 1; i < nold; i++)
   {
      z0 = zo->data[(i-1)*zo->stride];
      z1 = zo->data[i*zo->stride];
      if (z1 > z0) count++;
      else if (z1 < z0) count--;
      else if (z1 == z0) return 3; // duplicate.
      else return 4; // NaN
   }
   if (count == nold-1) increasing = 1;
   else if (count == -nold+1) increasing = 0;
   else  return 2; //mexErrMsgTxt("Table is not monotonic.");

   /* Interpolate each row: */
   jmax = nold - 1;
   if (increasing)
   {
      jhigh = 1;
      for (i=0; i<nnew; i++)
      {
         zz = zn->data[i*zn->stride];
         while (zo->data[jhigh*zo->stride] < zz && jhigh < jmax)
            jhigh++;
         while (zo->data[(jhigh-1)*zo->stride] > zz && jhigh > 1)
            jhigh--;
         if ( zo->data[jhigh*zo->stride] < zz ||
              zo->data[(jhigh-1)*zo->stride] > zz )
         {
            to_Bad(i, fn);
         }
         else
         {
            interpolate(jhigh, zo, fo, i, zz, fn, max_dz);
         }
      }
   }
   else /* decreasing */
   {
      jhigh = jmax;
      for (i=0; i<nnew; i++)
      {
         zz = zn->data[i*zn->stride];
         while (zo->data[jhigh*zo->stride] > zz && jhigh < jmax)
            jhigh++;
         while (zo->data[(jhigh-1)*zo->stride] < zz && jhigh > 1)
            jhigh--;
         if ( zo->data[jhigh*zo->stride] > zz ||
              zo->data[(jhigh-1)*zo->stride] < zz )
         {
            to_Bad(i, fn);
         }
         else
         {
            interpolate(jhigh, zo, fo, i, zz, fn, max_dz);
         }
      }
   }
   return 0;
}
/**************** end of regridli()  ************************************/


/************      regridnear     *****************************/
/* identical to regridli, substituting nearest for interpolate */

int regridnear(arr1* zo, arr2* fo, arr1* zn, arr2* fn, double max_dz)
/*        zo[],           input array of m depths: "z_old"
          fo[],           input array of m; f(z_old)
          zn[],           input array of n depths: "z_new".
          fn[],           output array of n; f(z_new)
          max_dz          if dz is larger, yield BADVAL
*/
{
   int  i;
   int  jhigh;
   int  increasing;    /* 1 if zo increases, 0 if it decreases */
   int       jmax;
   double    zz, z0, z1;
   int nold, nnew;
   int count;

   nnew = zn->n;
   nold = zo->n;
   if (nold < 2)
   {
      return 1; //mexErrMsgTxt("Need more than one row in the table.");
   }
   count = 0;
   for (i = 1; i < nold; i++)
   {
      z0 = zo->data[(i-1)*zo->stride];
      z1 = zo->data[i*zo->stride];
      if (z1 > z0) count++;
      else if (z1 < z0) count--;
      else if (z1 == z0) return 3; // duplicate.
      else return 4; // NaN
   }
   if (count == nold-1) increasing = 1;
   else if (count == -nold+1) increasing = 0;
   else  return 2; //mexErrMsgTxt("Table is not monotonic.");

   /* Interpolate each row: */
   jmax = nold - 1;
   if (increasing)
   {
      jhigh = 1;
      for (i=0; i<nnew; i++)
      {
         zz = zn->data[i*zn->stride];
         while (zo->data[jhigh*zo->stride] < zz && jhigh < jmax)
            jhigh++;
         while (zo->data[(jhigh-1)*zo->stride] > zz && jhigh > 1)
            jhigh--;
         if ( zo->data[jhigh*zo->stride] < zz ||
              zo->data[(jhigh-1)*zo->stride] > zz )
         {
            to_Bad(i, fn);
         }
         else
         {
            nearest(jhigh, zo, fo, i, zz, fn, max_dz);
         }
      }
   }
   else /* decreasing */
   {
      jhigh = jmax;
      for (i=0; i<nnew; i++)
      {
         zz = zn->data[i*zn->stride];
         while (zo->data[jhigh*zo->stride] > zz && jhigh < jmax)
            jhigh++;
         while (zo->data[(jhigh-1)*zo->stride] < zz && jhigh > 1)
            jhigh--;
         if ( zo->data[jhigh*zo->stride] > zz ||
              zo->data[(jhigh-1)*zo->stride] < zz )
         {
            to_Bad(i, fn);
         }
         else
         {
            nearest(jhigh, zo, fo, i, zz, fn, max_dz);
         }
      }
   }
   return 0;
}
/**************** end of regridnear()  ************************************/




