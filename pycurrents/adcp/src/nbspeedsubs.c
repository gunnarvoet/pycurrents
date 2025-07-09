/* Routines for quickly implementing a minimal speedlog
   capability for the NB-150 instrument.

*/

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "nbspeedsubs.h"

#ifndef M_PI
#define M_PI		3.14159265358979323846
#endif

#define NB_MAX_NBINS 128
#define NB_MAX_ARRAY (128*4)
static short int intvel[NB_MAX_ARRAY];
static double X[NB_MAX_NBINS];
static double Y[NB_MAX_NBINS];
static double U[NB_MAX_NBINS];
static double V[NB_MAX_NBINS];
static double W[NB_MAX_NBINS];
static double E[NB_MAX_NBINS];

double NaN = 0.0/0.0;

void unpack_velocity(unsigned char *buf, short int *v, int n)
{
   /* n is the number of bins to unpack, starting from 0;
      we need 6 bytes per bin.
   */
   int i, j;

   for (i = 0, j = 0; i < n; i++, j+= 6)
   {
      v[i*4] = buf[j] * 16 + (buf[j+1] >> 4);
      v[i*4 + 1] = (buf[j+1] & 0xf) * 256 + buf[j+2];
      v[i*4 + 2] = buf[j + 3] * 16 + (buf[j+4] >> 4);
      v[i*4 + 3] = (buf[j+4] & 0xf) * 256 + buf[j+5];
   }
   for (i = 0; i < n*4; i++)
   {
      if (v[i] > 2048)
      {
         v[i] -= 4096;
      }
   }
}


void beam_xyze(short int *v, double *U, double *V, double *W, double *E, int n)
{
   int i, j;
   double s30 = sin(M_PI/6.0);
   double c30 = cos(M_PI/6.0);
   double scale = 0.25 * 0.01;  /* to give nominal m/s */
   double a, b, d;

   a = scale/(2*s30);
   b = scale/(4*c30);
   d = a/sqrt(2);



   for (i = 0, j=0; i < n; i++, j+=4)
   {
      if (v[i] == 2048 || v[i+1] == 2048 || v[i+2] == 2048 || v[i+3] == 2048)
      {
         U[i] = NaN; V[i] = NaN; W[i] = NaN; E[i] = NaN;
      }
      else
      {
         U[i] = a * (v[j] - v[j+1]);
         V[i] = a * (-v[j+2] + v[j+3]);
         W[i] = b * (v[j] + v[j+1] + v[j+2] + v[j+3]);
         E[i] = d * (v[j] + v[j+1] - v[j+2] - v[j+3]);
      }
   }
}


void rotate_uv(double Head, double *X, double *Y, double *U, double *V, int n)
{
   int i;
   double ch = cos(Head * M_PI/180);
   double sh = sin(Head * M_PI/180);

   for (i = 0; i < n; i++)
   {
      U[i] = X[i] * ch + Y[i] * sh;
      V[i] = -X[i] * sh + Y[i] * ch;
   }
}

int z_average(double *U, double *Uav, int n)
{
   int i, count;
   double sum = 0.0;

   count = 0;
   for (i = 0; i < n; i++)
   {
      if (!isnan(U[i]))
      {
         sum += U[i];
         count++;
      }
   }
   if (count > 0) *Uav = sum/count;
   else           *Uav = NaN;
   return count;
}

int avg_uv(unsigned char *s, int n, int i0, int i1, double Head,
               double *Uav, double *Vav)
{
   int n_used;
   int n_bins_avail;
   int n_bins_to_use;
   /* i0 and i1 are Python-style loop indices; i0 is the starting
      index, i1 is the ending index plus 1. (Negative indexing is not
      supported here.)

      n is the number of bytes in the buffer s, which contains
      the packed velocity data from the ping data structure.
      There are 6 bytes per bin (12 bits per velocity number).
   */
   n_bins_avail = n/6;
   if (i1 > n_bins_avail) i1 = n_bins_avail;
   n_bins_to_use = i1 - i0;
   unpack_velocity(s, intvel, i1);
   /*printf("%hd %hd %hd %hd\n", intvel[i0], intvel[i0+1],
                               intvel[i0+2], intvel[i0+3]);*/
   beam_xyze(intvel+4*i0, X, Y, W, E, n_bins_to_use);
   /*printf("%6.2f %6.2f %6.2f %6.2f\n", X[0], Y[0], W[0], E[0]);*/
   rotate_uv(Head, X, Y, U, V, n_bins_to_use);
   /*printf("%5.1f %6.2f %6.2f\n", Head, U[0], V[0]);*/
   n_used = z_average(U, Uav, n_bins_to_use);
   z_average(V, Vav, n_bins_to_use);
   /*printf("%6.2f %6.2f\n", *Uav, *Vav);*/
   return n_used;
}
