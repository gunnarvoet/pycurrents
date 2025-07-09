

cdef extern from "dbext.h":
    ctypedef struct YMDHMS_TIME_TYPE:
        unsigned short year, month, day, hour, minute, second

    ctypedef struct DMSH_POSITION_TYPE:
        short degree, minute, second, hundredth

    ctypedef short SHORT
    ctypedef unsigned short USHORT
    ctypedef char CHAR
    ctypedef char BYTE
    ctypedef unsigned char UBYTE
    ctypedef int LONG
    ctypedef unsigned int ULONG
    ctypedef float FLOAT
    ctypedef double DOUBLE
    ctypedef struct COMPLEX:
        FLOAT RE, IM

    # With cython >=24, the following enum doesn't work unless it
    # is anonymous.  I don't understand this.
    cdef enum:
        BYTE_VALUE_CODE    = 0
        UBYTE_VALUE_CODE   = 1
        CHAR_VALUE_CODE    = 2
        SHORT_VALUE_CODE   = 3
        USHORT_VALUE_CODE  = 4
        LONG_VALUE_CODE    = 5
        ULONG_VALUE_CODE   = 6
        FLOAT_VALUE_CODE   = 7
        DOUBLE_VALUE_CODE  = 8
        COMPLEX_VALUE_CODE = 9
        TEXT_VALUE_CODE    =10
        STRUCT_VALUE_CODE  =11

    ctypedef struct STRUCT_DEF_ELEM_TYPE:
        CHAR      name[20]
        CHAR      units[12]
        SHORT     value_type
        SHORT     count
        CHAR      format_ptr[4]

    ctypedef struct STRUCT_DEF_HDR_TYPE:
        CHAR      name[20]
        LONG      nelem
        CHAR      padding[16]

    ctypedef union STRUCT_DEF_ENTRY_TYPE:
        STRUCT_DEF_HDR_TYPE  hdr
        STRUCT_DEF_ELEM_TYPE elem

    cdef enum SEARCH_CODES:
        TIME_SEARCH          = 1
        BLOCK_PROFILE_SEARCH = 2

    # This one causes compilation errors, so we use the numbers
    # directly in _codas.pyx.
    #cdef enum DATABASE_ACCESS_MODES:
    #    READ_ONLY        = 0
    #    READ_WRITE       = 1

    cdef enum DATA_TYPES_IN_DATA_BASE:
        DATASET_ID            =  100
        PRODUCER_ID           =  101
        TIME                  =  102
        POSITION              =  103
        DATA_MASK             =  104
        DATA_PROC_MASK        =  105
        DEPTH_RANGE           =  106

        DATABASE_VERSION      =  200
        PRODUCER_HOST         =  201
        DATABASE_NUMBER       =  202
        BLOCK_PROFILE_INDEX   =  203

        BLOCK_DIR_FILE        =  300
        BLOCK_FILE            =  301
        PRODUCER_DEF_FILE     =  302
        TEMP_DATA_FILE        =  303
        BLOCK_DIR_HDR         =  304
        BLOCK_DIR             =  305
        BLOCK_HDR             =  306
        DATA_LIST             =  307
        PROFILE_DIR           =  308
        DATA_DIR              =  309
        PROFILE_DATA          =  310
        PRODUCER_DEF          =  311
        STRUCTURE_DEF         =  312
        STRUCTURE_FORMATS     =  313
        BLOCK_FTR             =  314
        DATA_LIST_ENTRY       =  315

        DATA_LIST_NAMES       =  401
        NAMES_WITH_DATA       =  402

cdef extern from "data_id.h":
    cdef enum DATA_ID:
        DEPTH                  =  0
        TEMPERATURE            =  1
        SALINITY               =  2
        OXYGEN                 =  3
        OPTICS                 =  6
        AMP_SOUND_SCAT         =  7
        U                      =  8
        V                      =  9
        P                      = 10
        TEMP_SAMPLE            = 11
        SALINITY_SAMPLE        = 12
        OXYGEN_SAMPLE          = 13
        NUTRIENT_SAMPLE        = 14
        TRACER_SAMPLE          = 15
        OCEAN_DEPTH            = 20
        WEATHER                = 21
        SEA_SURFACE            = 22
        PROFILE_COMMENTS       = 32
        BLOCK_COMMENTS         = 33
        PROFILE_FLAGS          = 34
        CONFIGURATION_1        = 35
        CONFIGURATION_2        = 36
        ANCILLARY_1            = 37
        ANCILLARY_2            = 38
        ACCESS_VARIABLES       = 39
        DEPTH_SAMPLE           = 40
        SIGMA_T                = 41
        SIGMA_THETA            = 42
        SIGMA_Z                = 43
        SIGMA_2                = 44
        SIGMA_4                = 45
        SPEC_VOL_ANOM          = 46
        THERMOSTERIC_ANOM      = 47
        DYNAMIC_HEIGHT         = 48
        BVF                    = 49
        SOUNDSPEED             = 50
        TIME_FROM_START        = 51
        POTENTIAL_TEMP         = 52
        CONDUCTIVITY           = 53
        W                      = 54
        ERROR_VEL              = 55
        PERCENT_GOOD           = 56
        PERCENT_3_BEAM         = 57
        SPECTRAL_WIDTH         = 58
        U_STD_DEV              = 59
        V_STD_DEV              = 60
        W_STD_DEV              = 61
        EV_STD_DEV             = 62
        AMP_STD_DEV            = 63
        RAW_DOPPLER            = 64
        RAW_AMP                = 65
        RAW_SPECTRAL_WIDTH     = 66
        BEAM_STATS             = 67
        NAVIGATION             = 68
        BOTTOM_TRACK           = 69
        U_LOG                  = 70
        V_LOG                  = 71
        USER_BUFFER            = 75
        ADCP_CTD               = 76
        CORRELATION_MAG        = 77

cdef extern from "dbinc.h":
    ctypedef struct DATA_LIST_ENTRY_TYPE:
        CHAR      name[20]
        CHAR      units[12]
        SHORT     value_type
        SHORT     access_type
        ULONG     access_0
        ULONG     access_1
        FLOAT     offset
        FLOAT     scale
        ULONG     index


cdef extern from "time_.h":
    void yd_to_ymdhms_time(double yd, int year_base, YMDHMS_TIME_TYPE *t)
    double year_day(YMDHMS_TIME_TYPE *t, int year_base)

cdef extern from "find_def.h":
    STRUCT_DEF_HDR_TYPE *find_def(char *struct_name,
                STRUCT_DEF_HDR_TYPE *linked_list)
    int find_elem(char *elem_name, char *struct_name,
              STRUCT_DEF_HDR_TYPE *linked_list,
              unsigned int *data_ofs, unsigned int *nb,
              STRUCT_DEF_ELEM_TYPE *store_def)

cdef extern from "ioserv.h":
    void set_msg_stdout(int tf)
    void set_msg_bigbuf(int tf)
    int get_msg(char *msg_ptr, int n)

cdef extern from "use_db.h":
    cdef enum RANGE_TYPE_NUMS:
        TIME_RANGE = 1
        DAY_RANGE
        BLOCK_RANGE
        BLKPRF_RANGE
    ctypedef struct TIME_RANGE_TYPE:
        YMDHMS_TIME_TYPE start, end
    ctypedef struct DAY_RANGE_TYPE:
        int yearbase
        double start
        double end
    ctypedef struct BLOCK_RANGE_TYPE:
        int start
        int end
    ctypedef struct BLKPRF_INDEX_TYPE:
        int block
        int profile
    ctypedef struct BLKPRF_RANGE_TYPE:
        BLKPRF_INDEX_TYPE start
        BLKPRF_INDEX_TYPE end
    ctypedef union RANGE_U:
        BLOCK_RANGE_TYPE block
        BLKPRF_RANGE_TYPE blkprf
        DAY_RANGE_TYPE day
        TIME_RANGE_TYPE time
    ctypedef struct RANGE_TYPE:
        unsigned char type
        RANGE_U ru

    int dbopen_cnf(int dbid, char *dbname, int accmode, int memmode)
    void dbclose_cnf()
    int dbget_cnf(int type, void *data, unsigned int *n, char *msg)
    int dbget_f_cnf(int type, float *data, unsigned int *n, char *msg)
    int dbput_cnf(int type, void *data, unsigned int *n, char *msg)
    int dbput_f_cnf(int type, float *data, unsigned int *n,
                    unsigned int *nbad, char *msg)
    int dbmove_cnf(int nsteps)
    int dbsrch_cnf(int search_type, void *search_param)
    int dbset_cnf(int id)
    int db_last(BLKPRF_INDEX_TYPE *last_blkprf)
    int count_range(RANGE_TYPE *range)
    int goto_start_of_range(RANGE_TYPE *range)
    int goto_end_of_range(RANGE_TYPE *range)

cdef extern from "dbdcl.h":
    void DBLOADSD(char *filename, int *ierr)

cdef extern from "misc.h":
    ctypedef struct NAME_LIST_ENTRY_TYPE:
        char *name
        int code


