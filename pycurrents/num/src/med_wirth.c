
/*
 * Algorithm from N. Wirth's book, implementation by N. Devillard.
 * This code in public domain.

    Modified slightly for use with cython wrapper.

 */




/*---------------------------------------------------------------------------
   Function :   kth_smallest()
   In       :   array of elements, # of elements in the array, rank k
   Out      :   one element
   Job      :   find the kth smallest element in the array
   Notice   :   use the median() macro defined below to get the median.

                Reference:

                  Author: Wirth, Niklaus
                   Title: Algorithms + data structures = programs
               Publisher: Englewood Cliffs: Prentice-Hall, 1976
    Physical description: 366 p.
                  Series: Prentice-Hall Series in Automatic Computation

 ---------------------------------------------------------------------------*/

#define ELEM_SWAP(a,b) { register int t=(a);(a)=(b);(b)=t; }

#include "med_wirth.h"

int kth_smallest_i(int a[], int n, int k)
{
    register int i,j,l,m ;
    register int x ;

    l=0 ; m=n-1 ;
    while (l<m) {
        x=a[k] ;
        i=l ;
        j=m ;
        do {
            while (a[i]<x) i++ ;
            while (x<a[j]) j-- ;
            if (i<=j) {
                ELEM_SWAP(a[i],a[j]) ;
                i++ ; j-- ;
            }
        } while (i<=j) ;
        if (j<k) l=i ;
        if (k<i) m=j ;
    }
    return a[k] ;
}

#undef ELEM_SWAP
#define ELEM_SWAP(a,b) { register long int t=(a);(a)=(b);(b)=t; }

int kth_smallest_l(long int a[], int n, int k)
{
    register int i,j,l,m ;
    register long int x ;

    l=0 ; m=n-1 ;
    while (l<m) {
        x=a[k] ;
        i=l ;
        j=m ;
        do {
            while (a[i]<x) i++ ;
            while (x<a[j]) j-- ;
            if (i<=j) {
                ELEM_SWAP(a[i],a[j]) ;
                i++ ; j-- ;
            }
        } while (i<=j) ;
        if (j<k) l=i ;
        if (k<i) m=j ;
    }
    return a[k] ;
}

#undef ELEM_SWAP



#define ELEM_SWAP(a,b) { register float t=(a);(a)=(b);(b)=t; }

float kth_smallest_f(float a[], int n, int k)
{
    register int i,j,l,m ;
    register float x ;

    l=0 ; m=n-1 ;
    while (l<m) {
        x=a[k] ;
        i=l ;
        j=m ;
        do {
            while (a[i]<x) i++ ;
            while (x<a[j]) j-- ;
            if (i<=j) {
                ELEM_SWAP(a[i],a[j]) ;
                i++ ; j-- ;
            }
        } while (i<=j) ;
        if (j<k) l=i ;
        if (k<i) m=j ;
    }
    return a[k] ;
}

#undef ELEM_SWAP
#define ELEM_SWAP(a,b) { register double t=(a);(a)=(b);(b)=t; }

double kth_smallest_d(double a[], int n, int k)
{
    register int i,j,l,m ;
    register double x ;

    l=0 ; m=n-1 ;
    while (l<m) {
        x=a[k] ;
        i=l ;
        j=m ;
        do {
            while (a[i]<x) i++ ;
            while (x<a[j]) j-- ;
            if (i<=j) {
                ELEM_SWAP(a[i],a[j]) ;
                i++ ; j-- ;
            }
        } while (i<=j) ;
        if (j<k) l=i ;
        if (k<i) m=j ;
    }
    return a[k] ;
}

#undef ELEM_SWAP

/* #define median(a,n) kth_smallest(a,n,(((n)&1)?((n)/2):(((n)/2)-1)))
*/


