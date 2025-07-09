void unpack_velocity(unsigned char *buf, short int *v, int n);
void beam_xyze(short int *v, double *U, double *V, double *W, double *E, int n);
void rotate_uv(double Head, double *X, double *Y, double *U, double *V, int n);
int z_average(double *U, double *Uav, int n);
int avg_uv(unsigned char *s, int n, int i0, int i1, double Head,
               double *Uav, double *Vav);





