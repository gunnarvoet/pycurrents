
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include "msgmaker.h"

/* The following switches from plain printf to the msgmaker
   library which can write to stderr and to a buffer, from which
   pyrex or python can read.
*/
#define printf sprintf_msg

#define dmax(x,y) ((x)>(y)?(x):(y))
#define FLAGVAL     1e100
#define FLAGTHRESH  9e99

int zgrid_(int nx, int ny, double *z_out,
            double x1, double y1,
            double dx, double dy,
            int n, double *x_in, double *y_in, double *z_in,
            double del, double cay, int nrng,
            int idbug)
{
    /* Initialized data */
    double eps = 0.001;
    int itmax = 100;
    int nopt = 30;

    /* Local variables */
    int *jmnew;
    double zadd;
    int iter, nnew;
    double zijn, zimm, zmin, zjmm, zmax, zipp, zjpp, zsum, zul200;
    int i, j, k, idivg;
    double zbase, pcent, relax;
    int imnew;
    double dzmax, dzrms, rtrms, caysd4;
    int im, jm;
    double z00, dz;
    int nblank;
    double cayscl, corect, zrange, epslon;
    int ngrpts;
    double dzrmsp, zulovf, den, abz;
    int nij, npg;
    double zij, zim, zjm, wgt;
    double zpk, zip, zjp, zul, del2, del4;

    reset_msg();

/* **********************************************************************
*/

/*                           PGM = ZGRID */

/*                           ROGER B. LUKAS */
/*                           DEPT. OF OCEANOGRAPHY */
/*                           UNIV. OF HAWAII */

/*                           12/2/80 */

/* **********************************************************************
*/

/*     ZGRID interpolates irregularly distributed data to a */
/*     rectangular grid. The interpolation is controlled by */
/*     variation of the grid mesh and the parameters CAY and DEL. */

/*     The method used is to first assign each data point to */
/*     the closest grid point. If more than one data point is */
/*     assigned to a grid point, the data are averaged at that */
/*     grid point. Presently, ZGRID can handle up to 200 data */
/*     points at one grid point. Any data points after 200 have */
/*     been assigned to a grid point are ignored for that grid */
/*     point. A grid point can be "blanked out" by */
/*     assigning a value of 1.0E35 or greater to it prior to */
/*     entry to ZGRID. */

/*     All unblanked, unfilled grid points are interpolated */
/*     from the filled grid points as the solution to the */
/*     partial differential equation */

/*         (D2Z/DX2) + (D2Z/DY2) - K ( (D4Z/DX4) + (D4Z/DY4) ) = 0. */

/*     The solution to this equation is found by using the */
/*     method of successive over-relaxation (See Numerical */
/*     Methods for Partial Differential Equations by William */
/*     Ames). */

/*     An initial estimate of the solution is made by assigning */
/*     each unfilled grid point the value of the closest */
/*     filled grid point, as long as there is no more than */
/*     NRNG grid points between them (measured along the axes */
/*     directions only, no diagonal distances). If a grid */
/*     point is still unfilled after this process, it is set */
/*     to 1.0E35 and blanked out. */

/*     initially, Gauss-Seidel iteration is carried out */
/*     until enough information about the rate of convergence */
/*     to a solution can be obtained. Then an attempt is */
/*     made to estimate the optimum relaxation parameter */
/*     to the convergence. The process of refining */
/*     the estimate  the optimum relaxation parameter */
/*     is continued every NOPT iterations. */

/*     If the solution does not converge within ITMAX iterations, */
/*     the user is warned, and the most recent grid is */
/*     returned. This can happen because either */

/*           1) there are large areas of the grid */
/*              without any data, */
/*           2) the regions without data are not */
/*              "simply" connected, or */
/*           3) or the boundary conditions are inconsistent. */

/*     There are two types of boundaries: those where the */
/*     points outside the boundary are undefined (the edges */
/*     of the grid and interior blanked regions), and those */
/*     where the points on and outside the boundary are filled */
/*     with data. For the first type, the boundary conditions */
/*     are that DZ/DN = D2Z/DN2 = 0. For the second type, */
/*     the boundary conditions are Z = ZB and D2Z/DN2 = 0. */
/*     here D/DN is the partial derivative normal to the */
/*     boundary. */

/*     Subroutine arguments are: */

/*        Z     The grid to which the data is to interpolated. */

/*        NX    The number of grid points along the abcissa. */

/*        NY    The number of grid points along the ordinate. */

/*        X1    The abcissa value of Z(1,1) in data units */

/*        Y1    The ordinate value of Z(1,1) in data units */

/*        DX,DY The length of the sides of the grid cells */
/*              IN DATA UNITS */

/*        N     The number of data points to be gridded. */

/*        CAY   The parameter controlling how much the */
/*              fourth order part of the differential equation */
/*              is to be used in the interpolation. */

/*        DEL   The parameter controlling the aspect ratio of */
/*              the interpolation. DEL is defined as DX/DY */
/*              strictly, but has been made a parameter to */
/*              allow the user to exercise more control over */
/*              the interpolation. */

/*        NRNG  The maximum distance in grid points which will be */
/*              used to search for valid data as a first estimate to */
/*              the solution. */

/*        IDBUG Controls the level of debugging information */
/*              that is printed out. 0 gives none, 1 records */
/*              entry and exit from the subroutine, and 2 records */
/*              the iteration process and lists the final grid */
/*              values. */


/*     JMNEW should be dimensioned the same as the row dimension */
/*     of Z. */
/* ***********************************************************************
 */
    if (idbug > 0) {
    printf("nx %d, ny %d, n %d, cay %f, nrng %d\n",
            nx, ny, n, cay, nrng);
    }
/*     CHECK FOR EXISTENCE OF DATA */
/*     IF NO DATA, ISSUE ERROR MESSAGE AND TERMINATE */

    if (n == 0) {
      printf("zgrid: No data\n");
      return(-1);
    }

/*           COMPUTE LOCAL CONSTANTS FROM GLOBAL ARGUMENTS */

    del2 = del * del;
    del4 = del2 * del2;
    cayscl = cay / (dx * dx);
    caysd4 = cayscl * del4;

/*     Set non-zero grid points to the flag value. */

    ngrpts = nx * ny;
    nblank = 0;
    for (j = 0; j < ngrpts; ++j) {
        if (z_out[j] != 0.0) {
            z_out[j] = FLAGVAL;
            ++nblank;
        }
    }
    if (idbug > 0) {
        printf("nblank: %d\n", nblank);
    }

/*     CHECK TO SEE IF THE WHOLE GRID IS BLANKED OUT */

    if (nblank == ngrpts) {
      printf("zgrid: Everything is blanked out.\n");
      return(-1);
    }

/*     GET ZBASE WHICH WILL MAKE ALL ZP VALUES POSITIVE BY AT LEAST */
/*     .25(ZMAX-ZMIN) AND FILL IN GRID WITH ZEROS. */
/* ***********************************************************************
 */

/*        FIND MAXIMUM AND MINIMUM FOR Z */

    zmin = FLAGTHRESH;
    zmax = -FLAGTHRESH;
    for (k = 0; k < n; ++k) {
        zpk = z_in[k];
        if (zpk > zmax) {
            zmax = zpk;
        }
        if (zpk < zmin) {
            zmin = zpk;
        }
    }


/*        DETERMINE RANGE OF Z VALUES */
/*        SET UP METHOD TO SET RANGES */

    zrange = zmax - zmin;

/*        ABEND IF ZRANGE IS NOT POSITIVE */

    if (zrange <= 0.0) {
    printf("zgrid: Range of input values = 0; check input.\n");
    return(-1);
    }
    zbase = -zmin + zrange * 0.25;
    zul = zbase + zmax;                 /* zrange * 1.25  */
    zul200 = zul * 200.0;               /* zrange * 250   */
    zulovf = zul200 * 200.0;            /* zrange * 50000 */


/*     AFFIX EACH POINT ZP TO NEAREST GRID PT. TAKE AVG IF MORE THAN */
/*     ONE NEAR PT.  ADD ZBASE PLUS 10*ZRANGE AND MAKE NEGATIVE. */
/*     INITIALLY SET EACH UNSET GRID PT TO VALUE OF NEAREST KNOWN PT */

/*     ZUL200 IS USED TO KEEP TRACK OF # OF POINTS ASSIGNED TO EACH */
/*     GRID POINT. ZULOVF CHECKS TO MAKE SURE AVERAGE WILL BE CORRECT */
/*     BY REJECTING ANY NEW POINTS. PRESENTLY SET UP SO THAT NO MORE */
/*     THAN 200 POINTS CAN BE ASSIGNED TO ONE GRID POINT. */

/* ***********************************************************************
 */
    zadd = zbase + zul200;              /* -zmin + zrange * 250.25 */

    for (k = 0; k < n; ++k) {
        i = (x_in[k] - x1) / dx + 0.5;
        if (i < 0 || i >= nx) {
            continue;
        }
        j = (y_in[k] - y1) / dy + 0.5;
        if (j < 0 || j >= ny) {
            continue;
        }
        if (z_out[i + j * nx] >= zulovf) {
            continue;
        }
        z_out[i + j * nx] += (z_in[k] + zadd);
    }


/*      AVERAGE DATA ASSIGNED TO EACH GRID POINT. */
/*      ALSO, SEARCH GRID FOR GRID POINTS WITH NO DATA. */
/*      NPG AT END OF SEARCH IS THE NUMBER OF GRID POINTS */
/*      WITHOUT DATA. */

    npg = 0;
    zadd = zrange * 10.0 - zul200;
    for (j = 0; j < ny; ++j) {
        for (i = 0; i < nx; ++i) {
            zij = z_out[i + j * nx];

/*           SKIP BLANKED POINTS */

            if (zij >= FLAGTHRESH) {
                continue;
            }
            nij = zij / zul200;
            if (nij <= 0) {
/*           NO DATA AT THIS GRID POINT, FLAG IT. */
                z_out[i + j * nx] = -FLAGVAL;
                ++npg;
            }
            else {
                z_out[i + j * nx] = -(zij / nij + zadd);
            }

        }
    }

/*      IF EVERY GRID POINT HAS AT LEAST ONE DATA POINT */
/*      ASSIGNED TO IT, THEN THERE IS NO NEED TO DO ANY */
/*      INTERPOLATION, SO RETURN. */

    if (npg == 0) {
      if (idbug > 0) {
      printf("zgrid: Every grid point has a data point; no interpolation needed.\n");
      }
      goto L2120;
    }

/*     IF 5% OR LESS OF THE UNBLANKED GRID POINTS HAVE VALID DATA, THEN
*/
/*     TERMINATE EXECUTION SINCE THE INTERPOLATION WILL TAKE A LONG TIME
*/
/*     TO CONVERGE TO A SOLUTION, IF AT ALL. */

    pcent = (double) (npg / (ngrpts - nblank));
    if (pcent >= 0.98) {
        printf("zgrid: Less than 2%% of the grid has data; quitting.\n");
        return(-1);
    }

/*           FOR EACH GRID POINT WITHOUT DATA, ASSIGN IT THE */
/*           VALUE OF THE NEAREST GRID POINT AS A FIRST */
/*           APPROXIMATION TO THE SOLUTION, BUT DON'T EXTRAPOLATE MORE */
/*           THAN NRNG GRID CELLS. ANY GRID POINTS STILL UNASSIGNED */
/*           AFTER EXTRAPOLATION WILL BE BLANKED OUT. */

/*        IMNEW AND JMNEW KEEP TRACK OF EXTRAPOLATED POINTS */
/*  jmnew is indexed by i, the row-dimension index, so its
      length is nx, or nx.
*/
    if (nrng <= 0) {
        goto L200;   /* Skip this step entirely. */
    }
    jmnew = calloc(nx,sizeof(int));
    if (jmnew == NULL)
    {
        printf("zgrid: Failed to allocate memory for jmnew.\n");
        return (-1);
    }

    for (iter = 0; iter < nrng; ++iter) {
        nnew = 0;
        for (j = 0; j < ny; ++j) {
            imnew = 0;
            for (i = 0; i < nx; ++i) {
                if (z_out[i + j * nx] > -FLAGTHRESH) {
                    jmnew[i] = 0;
                    imnew = 0;
                    continue;
                }

/*              UNFILLED GRID POINT, GET VALUE FROM NEAREST GRID POINT */
/*              WITH DATA */

                if (!(i == 0 || imnew > 0)) {
                    zijn = fabs(z_out[i - 1 + j * nx]);
                    if (zijn < FLAGTHRESH) {
                        goto L195;
                    }
                }

                if (!(j == 0 || jmnew[i] > 0)) {
                    zijn = fabs(z_out[i + (j - 1) * nx]);
                    if (zijn < FLAGTHRESH) {
                        goto L195;
                    }
                }

                if (!(i == nx-1)) {
                    zijn = fabs(z_out[i + 1 + j * nx]);
                    if (zijn < FLAGTHRESH) {
                        goto L195;
                    }
                }

                if (!(j == ny-1)) {
                    zijn = fabs(z_out[i + (j + 1) * nx]);
                    if (zijn < FLAGTHRESH) {
                        goto L195;
                    }
                }
                jmnew[i] = 0;
                imnew = 0;
                continue;

L195:
                jmnew[i] = 1;
                imnew = 1;
                z_out[i + j * nx] = zijn;
                ++nnew;
            }  /* end of loop through rows: i */
        }  /* end of column loop: j */

/*        IF NO NEW GRID POINTS HAVE BEEN FILLED, FINISHED */

        if (nnew <= 0) {
             break;
        }
    }  /* end of iteration loop: iter */

    free(jmnew);
L200:

/*     BLANK ANY GRID POINTS STILL UNFILLED */

    for (j = 0; j < nx*ny; ++j) {
        abz = fabs(z_out[j]);
        if (abz >= FLAGTHRESH) {
            z_out[j] = abz;
        }
    }

/* Now, original gridded data points (based on binning)
   are negative, and points estimated from neighbors via nrng>0
   are positive;
   only the latter will be adjusted by the following procedure.
   Points that will not be valid are now all "FLAGTHRESH" (not -FLAGTHRESH).
*/

/*     IMPROVE THE NON-DATA POINTS BY APPLYING POINT OVER-RELAXATION */
/*     USING THE LAPLACE-SPLINE EQUATION  (CARRE'S METHOD IS USED) */
/*     EVERY NOPT ITERATIONS, ESTIMATE THE OPTIMUM RELAXATION */
/*     PARAMETER. */

/* ***********************************************************************
 */
    epslon = eps * zrange;
    dzrmsp = zrange * 0.1;
    relax = 1.0;
    idivg = 0;
    for (iter = 0; iter < itmax; ++iter) {
        dzrms = 0.0;
        dzmax = 0.0;
        for (j = 0; j < ny; ++j) {
            for (i = 0; i < nx; ++i) {
                z00 = z_out[i + j * nx];

/*              IF BLANKED OR FILLED, SKIP THIS GRID POINT */

                if (z00 >= FLAGTHRESH || z00 < 0.0) {
                    continue;
                }
                wgt = 0.0;
                zsum = 0.0;

                im = 0;
                if (i == 0) {
                    goto L570;
                }
                zim = fabs(z_out[i - 1 + j * nx]);
                if (zim >= FLAGTHRESH) {
                    goto L570;
                }
                im = 1;
                wgt += 1.0;
                zsum += zim;
                if (i == 1) {
                    goto L570;
                }
                zimm = fabs(z_out[i - 2 + j * nx]);
                if (zimm >= FLAGTHRESH) {
                    goto L570;
                }
                wgt += cayscl;
                zsum -= cayscl * (zimm - zim * 2.0);

L570:
                if (i == nx-1) {
                    goto L700;
                }
                zip = fabs(z_out[i + 1 + j * nx]);
                if (zip >= FLAGTHRESH) {
                    goto L700;
                }
                wgt += 1.0;
                zsum += zip;
                if (im == 0) {
                    goto L620;
                }
                wgt += cayscl * 4.0;
                zsum += cayscl * 2.0 * (zim + zip);


L620:
                if (i == nx-2) {
                    goto L700;
                }
                  zipp = fabs(z_out[i + 2 + j * nx]);
                if (zipp >= FLAGTHRESH) {
                    goto L700;
                }
                wgt += cayscl;
                zsum -= cayscl * (zipp - zip * 2.0);


L700:

                jm = 0;
                if (j == 0) {
                    goto L1570;
                }
                zjm = fabs(z_out[i + (j - 1) * nx]);
                if (zjm >= FLAGTHRESH) {
                    goto L1570;
                }
                jm = 1;
                wgt += del2;
                zsum += zjm * del2;
                if (j == 1) {
                    goto L1570;
                }
                  zjmm = fabs(z_out[i + (j - 2) * nx]);

                if (zjmm >= FLAGTHRESH) {
                    goto L1570;
                }
                wgt += caysd4;
                zsum -= caysd4 * (zjmm - zjm * 2.0);


L1570:
                if (j == ny-1) {
                    goto L1700;
                }
                zjp = fabs(z_out[i + (j + 1) * nx]);
                if (zjp >= FLAGTHRESH) {
                    goto L1700;
                }
                wgt += del2;
                zsum += zjp * del2;
                if (jm == 0) {
                    goto L1620;
                }
                wgt += caysd4 * 4.0;
                zsum += caysd4 * 2.0 * (zjm + zjp);


L1620:
                if (j == ny-2) {
                    goto L1700;
                }
                  zjpp = fabs(z_out[i + (j + 2) * nx]);

                if (zjpp >= FLAGTHRESH) {
                    goto L1700;
                }
                wgt += caysd4;
                zsum -= caysd4 * (zjpp - zjp * 2.0);


L1700:

                dz = (zsum / wgt - z00) * relax;
                dzrms += dz * dz;
/* Computing MAX */
                dzmax = dmax(fabs(dz),dzmax);
                z_out[i + j * nx] = z00 + dz;
            }   /* end of i loop */
        }   /* end of j loop */

        dzrms = sqrt(dzrms / npg);
        rtrms = dzrms / dzrmsp;
        dzrmsp = dzrms;
         if (rtrms >= 1.0) {
            ++idivg;
        }
         if (rtrms < 1.0) {
            idivg = 0;
        }
         if (idivg >= 10) {
             printf("zgrid: Fails to converge: idivg >= 10\n");
             return(-1);
        }

/*        TEST STOPPING CRITERION */

        if (dzmax < epslon) {
            break;
        }
        if (iter == nopt) {
/*              RECOMPUTE THE RELAXATION PARAMETER IN HOPES */
/*              OF SPEEDING UP THE CONVERGENCE */
            idivg = 0;
            den = sqrt(1.0 - rtrms * rtrms) + 1.0;
            relax = 2.0 / den;
        }
    }

/*          SOLUTION HASN'T CONVERGED IN ITMAX ITERATIONS, SO */
/*          WRITE OUT APPROPRIATE WARNING MESSAGE AND CONTINUE */
/*          EXECUTION. */
    if (dzmax >= epslon)
        printf("zgrid: Warning: solution did not converge.\n");
L2120:

/*          ALL FINISHED WITH INTERPOLATION. CORRECT ALL GRID POINTS */
/*          FOR THE DISPLACEMENT MADE IN GRIDDING THE DATA. */

/* ***********************************************************************
 */
    corect = zbase + zrange * 10.0;
    for (j = 0; j < nx*ny; ++j) {
        if (z_out[j] < FLAGTHRESH) {
            z_out[j] = fabs(z_out[j]) - corect;
        }
    }
    return 0;


} /* zgrid_ */


