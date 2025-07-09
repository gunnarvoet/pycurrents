
#define BADVAL 1e100
#define TEST_BV 0.999e100

typedef struct {double *data;
                    int n;
                    int stride;
                    } arr1;
typedef struct {double *data;
                int nr;
                int nc;
                int rstride;
                int cstride;
                } arr2;
    /* rstride is number of doubles to next row;
       cstride is number of doubles to next column.
    */
int regridli(arr1* zo, arr2* fo, arr1* zn, arr2* fn, double max_dz);
int regridnear(arr1* zo, arr2* fo, arr1* zn, arr2* fn, double max_dz);




