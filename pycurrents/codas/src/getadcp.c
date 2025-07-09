#include "getadcp.h"


#define MAX_RA 2048

int get_data(ADCP_PROFILE_SET *aps, int nprofs, int nbin, int txy_only)
{
    int i, j, k;
    int i0;
    int res;
    unsigned int n, navail;
    NAVIGATION_TYPE nav;
    BOTTOM_TRACK_TYPE bt;
    ACCESS_VARIABLES_TYPE acc;
    ANCILLARY_2_TYPE ancil2;
    ANCILLARY_1_TYPE ancil1;
    CONFIGURATION_1_TYPE config1;
    DMSH_LL_TYPE pos_dmsh;
    DOUBLE_LL_TYPE pos_ll;

    static UBYTE rabuf[MAX_RA];

    for (i=0; i<nprofs; i++)
    {
        if (i>0)
        {
            res = dbmove_cnf(1);
            if (res) break;
        }
        n = 2 * sizeof(int);
        /*printf("pointer: %p\n", aps->blkprf+i*2);   */
        if (dbget_cnf(BLOCK_PROFILE_INDEX, (char *) (aps->blkprf+i*2), &n,
           "getting block-profile index")) return(-1);
        /*printf("after block profile index: n= %d\n", n);  */
        n = sizeof(YMDHMS_TIME_TYPE);
        if (dbget_cnf(TIME, (char *) (aps->time+i*6), &n, "getting time"))
            return(-2);
        aps->dday[i] = year_day((YMDHMS_TIME_TYPE *) (aps->time+i*6),
                                                            aps->year_base);
        /* We would use use_db.c get_latlon() except that it exits
           on error instead of returning a non-zero value.
        */
        n = sizeof(DMSH_LL_TYPE);
        if (dbget_cnf(POSITION, (char *)&pos_dmsh, &n, "getting position"))
            return(-3);
        if (pos_dmsh.lon.degree == BADSHORT)
        {
            pos_ll.lon = pos_ll.lat = BADFLOAT;
        }
        else
        {
            pos_ll.lat = POSHUN(&(pos_dmsh.lat)) / 360000.0;
            pos_ll.lon = POSHUN(&(pos_dmsh.lon)) / 360000.0;
        }
        aps->lon_dir[i] = pos_ll.lon;
        aps->lat_dir[i] = pos_ll.lat;

        if (txy_only) continue;

        n = sizeof(NAVIGATION_TYPE);
        if (dbget_cnf(NAVIGATION, (char *) &nav, &n, "getting navigation"))
        {
           nav.longitude = 0.0;   /* Change by EF, 93/02/10, to work with LADCP data. */
           nav.latitude  = 0.0;
        }
        if (nav.longitude == 0.0 && nav.latitude == 0.0)
            aps->lon[i] = aps->lat[i] = 1e38;
        else
        {
            aps->lon[i] = (nav.longitude < ADJ_BADFLOAT) ? nav.longitude : 1e38;
            aps->lat[i] = (nav.latitude  < ADJ_BADFLOAT) ? nav.latitude  : 1e38;
        }
        n = sizeof(BOTTOM_TRACK_TYPE);
        if (dbget_cnf(BOTTOM_TRACK, (char *)&bt, &n, "getting bt"))
        {
           aps->U_bt[i] = aps->V_bt[i] = aps->D_bt[i] = 1e38;
        }
        else
        {
           aps->U_bt[i] = bt.u;
           aps->V_bt[i] = bt.v;
           aps->D_bt[i] = bt.depth;
        }

        n = sizeof(ACCESS_VARIABLES_TYPE);
        if (dbget_cnf(ACCESS_VARIABLES, (char *) &acc, &n,
                                     "getting access variables")) return(-4);
        aps->lgb[i] = acc.last_good_bin;
        aps->U_ship[i] = acc.U_ship_absolute;
        aps->V_ship[i] = acc.V_ship_absolute;

        n = sizeof(ANCILLARY_2_TYPE);
        if (dbget_cnf(ANCILLARY_2, (char *) &ancil2, &n,
                                         "getting ancillary_2")) // return(-5);
        {
           /* LADCP does not have ANCILLARY_2 */
           aps->mab[i] = BADSHORT;
           aps->watrk_hd_misalign[i] = BADFLOAT;
           aps->watrk_scale_factor[i] = BADFLOAT;
           aps->botrk_hd_misalign[i] = BADFLOAT;
           aps->botrk_scale_factor[i] = BADFLOAT;
           aps->last_temp[i] = BADFLOAT;
           aps->last_heading[i] = BADFLOAT;
           aps->mn_pitch[i] = BADFLOAT;
           aps->mn_roll[i] = BADFLOAT;
           aps->std_pitch[i] = BADFLOAT;
           aps->std_roll[i] = BADFLOAT;

        }
        else
        {
           aps->mab[i] = ancil2.max_amp_bin;
           aps->watrk_hd_misalign[i] = ancil2.watrk_hd_misalign;
           aps->watrk_scale_factor[i] = ancil2.watrk_scale_factor;
           aps->botrk_hd_misalign[i] = ancil2.botrk_hd_misalign;
           aps->botrk_scale_factor[i] = ancil2.botrk_scale_factor;
           aps->last_temp[i] = ancil2.last_temp;
           aps->last_heading[i] = ancil2.last_heading;
           aps->mn_pitch[i] = ancil2.mn_pitch;
           aps->mn_roll[i] = ancil2.mn_roll;
           aps->std_pitch[i] = ancil2.std_pitch;
           aps->std_roll[i] = ancil2.std_roll;

        }

        n = sizeof(ANCILLARY_1_TYPE);
        if (dbget_cnf(ANCILLARY_1, (char *) &ancil1, &n, "getting ancillary_1"))
            return(-6);
        aps->heading[i] = ancil1.mn_heading;
        aps->tr_temp[i] = ancil1.tr_temp;
        aps->snd_spd_used[i] = ancil1.snd_spd_used;
        aps->best_snd_spd[i] = ancil1.best_snd_spd;
        aps->pgs_sample[i] = ancil1.pgs_sample;

        n = sizeof(CONFIGURATION_1_TYPE);
        if (dbget_cnf(CONFIGURATION_1, (char *) &config1, &n,
                                                "getting configuration_1"))
            return(-6);
        aps->num_bins[i] = config1.num_bins;


        i0 = i*nbin;
        for (j = 0; j < nbin; j++) aps->pf[i0+j] = BADUBYTE;
        n = nbin;

        /* some early databases don't have profile_flags */
        if (dbget_cnf(PROFILE_FLAGS, (char *) aps->pf+i0, &n,
           "getting profile flags"))
        {
            for (j = 0; j < nbin; j++) aps->pf[i0+j] = 0;
        }

        for (j = 0; j < nbin; j++) aps->d[i0+j] = BADFLOAT;
        n = nbin;
        if (dbget_f_cnf(DEPTH, aps->d+i0, &n, "getting depth"))
            return(-8);

        for (j = 0; j < nbin; j++) aps->u[i0+j] = BADFLOAT;
        n = nbin;
        if (dbget_f_cnf(U, aps->u+i0, &n, "getting U velocity"))
            return(-9);

        for (j = 0; j < nbin; j++) aps->v[i0+j] = BADFLOAT;
        n = nbin;
        if (dbget_f_cnf(V, aps->v+i0, &n, "getting V velocity"))
            return(-10);

        for (j = 0; j < nbin; j++) aps->w[i0+j] = BADFLOAT;
        n = nbin;
        if (dbget_f_cnf(W, aps->w+i0, &n, "getting W velocity"))
            return(-11);

        for (j = 0; j < nbin; j++) aps->e[i0+j] = BADFLOAT;
        n = nbin;
        if (dbget_f_cnf(ERROR_VEL, aps->e+i0, &n, "getting error velocity"))
            return(-12);

        for (j = 0; j < nbin; j++) aps->pg[i0+j] = BADUBYTE;
        n = nbin;
        if (dbget_cnf(PERCENT_GOOD, (char *)aps->pg+i0, &n, "getting percent good"))
            return(-13);

        for (j = 0; j < nbin; j++) aps->a[i0+j] = BADUBYTE;
        n = nbin;
        if (dbget_cnf(AMP_SOUND_SCAT, (char *)aps->a+i0, &n, "getting amplitude"))
            return(-14);

        /* We do not check for success on SW and RA; they are optional. */
        for (j = 0; j < nbin; j++) aps->sw[i0+j] = BADUBYTE;
        n = nbin;
        dbget_cnf(SPECTRAL_WIDTH, (char *)aps->sw+i0, &n, "getting spectral width");

        for (j = 0; j < 4*nbin; j++) aps->ra[4*i0+j] = BADUBYTE;
        n = MAX_RA;
        dbget_cnf(RAW_AMP, (char *)rabuf, &n, "getting raw amplitude");
        navail = n/4;
        for (j = 0; j < nbin; j++)
        {
            for (k=0; k < 4; k++)
            {
                aps->ra[4*i0+j*4+k] = rabuf[j+k*navail];
            }
        }

        /* resid_stats, tseries_stats, tseries_diffstats, ev_std_dev may not be present,
             so don't fail */
        for (j=0; j < 6*nbin; j++) aps->resid_stats[6*i0+j] = BADFLOAT;
        n = 6 * nbin * sizeof(float);
        dbget_cnf(RESID_STATS, (char *)&(aps->resid_stats[6*i0]), &n,
                                    "getting residual stats");

        for (j=0; j < 7; j++) aps->tseries_stats[7*i+j] = BADFLOAT;
        n = 7 * sizeof(float);
        dbget_cnf(TSERIES_STATS, (char *)&(aps->tseries_stats[7*i]), &n,
                                    "getting tseries stats");

        for (j=0; j < 4; j++) aps->tseries_diffstats[4*i+j] = BADFLOAT;
        n = 4 * sizeof(float);
        dbget_cnf(TSERIES_DIFFSTATS, (char *)&(aps->tseries_diffstats[4*i]), &n,
                                    "getting tseries diffstats");

        /* As of 2021-07-05 we have been saving only error vel std, not
        u, v, or w std, in our codas database.
        */
        for (j = 0; j < nbin; j++) aps->e_std[i0+j] = BADFLOAT;
        n = nbin;
        dbget_f_cnf(EV_STD_DEV, aps->e_std+i0, &n, "getting E std");

    }
    return(i);
}
