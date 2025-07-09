#include "geninc.h"
#include "adcp.h"                   /* NAVIGATION_TYPE                       */
#include "data_id.h"                /* CODAS variable names and IDs          */
#include "use_db.h"                 /* db*_cnf()                             */
typedef struct
{
    int *blkprf;
    SHORT *time, *lgb, *mab;
    unsigned char *pf, *pg, *a, *sw, *ra;
    float *d, *u, *v, *w, *e;
    float *U_ship, *V_ship, *heading;
    float *tr_temp, *snd_spd_used, *best_snd_spd;
    float *watrk_hd_misalign, *watrk_scale_factor,
          *botrk_hd_misalign, *botrk_scale_factor,
          *last_temp, *last_heading;
    float *mn_pitch, *mn_roll, *std_pitch, *std_roll;
    float *U_bt, *V_bt, *D_bt;
    double *dday, *lon, *lat;
    double *lon_dir, *lat_dir;
    float *resid_stats;
    float *tseries_stats;
    float *tseries_diffstats;
    SHORT *pgs_sample;
    SHORT *num_bins;
    float *e_std;  // u_std etc. are not available
    int year_base;
} ADCP_PROFILE_SET;

typedef union
{
    ADCP_PROFILE_SET aps;
    void *ptrs[44];
} ADCP_PROFILE_SET_UNION;

int get_data(ADCP_PROFILE_SET *aps, int nprofs, int nbin, int txy_only);
