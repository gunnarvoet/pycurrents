"""
Wrapper for qr_solve in csparse library.

Solves over and underdetermined linear systems with a sparse matrix.
"""

import numpy as np
#import scipy.sparse as sp  # This form fails.

from scipy import sparse as sp

cdef extern from "stdlib.h":
    ctypedef int size_t

from cpython cimport PyMem_Malloc
from cpython cimport PyMem_Free
from cpython cimport PyLong_AsVoidPtr

cdef extern from "suitesparse/cs.h":
    ctypedef struct cs:
        int nzmax  #    /* maximum number of entries */
        int m      #    /* number of rows */
        int n      #    /* number of columns */
        int *p     #    /* column pointers (size n+1) or col indices (size nzmax) */
        int *i     #    /* row indices, size nzmax */
        double *x  #    /* numerical values, size nzmax */
        int nz     #    /* # of entries in triplet matrix, -1 for compressed-col */

    int cs_qrsol (int order, cs *A, double *b)

def solve(A, B, order=1):
    """
    Return the X that solves AX = B in a least-squares sense.

    A must be a sparse matrix, or convertible to it with csc_matrix().
    B is an ndarray of 1 or 2 dimensions; if the latter, X has
    the same shape, and each column of X is the solution for the
    corresponding column of B.

    kwarg: order is 0 or 1; it affects the processing, but I don't know
    exactly how yet.

    """
    cdef cs * cs_ptr
    B = np.array(B, dtype=np.float64)
    if B.ndim > 2:
        raise ValueError("B can have at most 2 dimensions; B.shape = %s"
                                                            % (B.shape,))
    A = sp.csc_matrix(A)    # checks for max 2 dims; returns 2-D (matrix)
    if B.shape[0] != A.shape[1]:
        raise ValueError("A.shape = %s, B.shape = %s;\n"
                             % (A.shape, B.shape) +
                    "First dimension of B must match second dimension of A")
    #A.sort_indices()
    cs_ptr = <cs *> PyMem_Malloc(sizeof(cs))
    if cs_ptr == NULL:
        raise RuntimeError("Cannot allocate memory")
    cs_ptr.m, cs_ptr.n = A.shape
    cs_ptr.nzmax = A.data.size
    cs_ptr.nz = -1 # compressed column flag is -1
    cs_ptr.x = <double *>PyLong_AsVoidPtr(A.data.__array_interface__['data'][0])
    cs_ptr.p = <int *>PyLong_AsVoidPtr(A.indptr.__array_interface__['data'][0])
    cs_ptr.i = <int *>PyLong_AsVoidPtr(A.indices.__array_interface__['data'][0])
    try:
        if B.ndim == 1:
            ret = cs_qrsol(order, cs_ptr,           # first arg: order, 0 or 1?
                        <double *>PyLong_AsVoidPtr(B.__array_interface__['data'][0]))
            if ret == 0:
                raise RuntimeError("cs_qrsol failed")
        else:
            for j in range(B.shape[1]):
                Bc = np.array(B[:,j])
                ret = cs_qrsol(order, cs_ptr,
                        <double *>PyLong_AsVoidPtr(Bc.__array_interface__['data'][0]))
                if ret == 0:
                    raise RuntimeError("cs_qrsol failed at column %d" % j)
                B[:,j] = Bc
    finally:
        PyMem_Free(cs_ptr)
    return B



