/* stripped down version of unistat from codas3 vstat */

typedef struct {
   int     n,        /* number of elements in each vector */
           n_increments;  /* incremented with each call to update_unistat */
   double *sum,      /* accumulate sums */
          *sumsq;    /* accumulate sums of squares */
   double *min;      /* minimum found */
   double *max;      /* maximum found */
   int    *npts,     /* count points accumulated */
          *imin,     /* index of minimum (start from zero) */
          *imax;     /* index of maximum */
   char   *name;
} UNISTAT_TYPE;


void zero_unistat(UNISTAT_TYPE *s);
int index_less(double d, double dstart, double dz);
int index_more(double d, double dstart, double dz);
int index_closest(double d, double dstart, double dz);
void update_unistat_piece(UNISTAT_TYPE *s,
                            double *array,
                            unsigned char *mask,
                            int i0,  /* starting index into unistat arrays */
                            int na);  /* number of points in the array */
void update_unistat_nomask(UNISTAT_TYPE *s,
                            double *array,
                            int i0,  /* starting index into unistat arrays */
                            int na);  /* number of points in the array */
void regrid(double zo[], double fo[], double zn[], double fn[],
            int m, int n, int *n0_ptr, int *nout_ptr);





