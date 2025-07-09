
typedef struct {
    int N;
    int i_oldest;
    int i_next;
    int bad_line;
    int fd;
    int owned_file;
    off_t position;
    char *filename;
    char *buf;
    char *outbuf;
    struct stat st;
    } filetail;

void print_filetail(filetail *ft);
filetail *new_filetail(int N);
void dealloc_filetail(filetail *ft);
int open_filetail(filetail *ft, char *fname);
int connect_filetail(filetail *ft, int fd);
void close_filetail(filetail *ft);
long bytes_available(filetail *ft);
int fill_buf(filetail *ft);
int line_from_buf(filetail *ft);
char *read_line(filetail *ft);
int bytes_from_buf(filetail *ft, int n);
int read_bytes(filetail *ft, int n);
char *get_outbuf(filetail *ft);
int get_N(filetail *ft);






