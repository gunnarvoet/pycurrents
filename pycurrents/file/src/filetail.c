/*
    File reading object optimized for tailing a growing
    file.

    2006/01/14 EF
*/

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <string.h>
#include "filetail.h"



static char empty_line[] = "";

void print_filetail(filetail *ft)
{
    printf("%d %d %d %lld\n", ft->N, ft->i_oldest, ft->i_next, (long long) ft->position);
}

filetail *new_filetail(int N)
{
    filetail *ft;

    ft = calloc(1, sizeof(filetail));
    if (ft == NULL) {
        return NULL;
    }
    ft->buf = calloc(N, sizeof(char));
    ft->outbuf = calloc(N, sizeof(char));
    ft->fd = -1;
    ft->N = N;
    return ft;
}

void dealloc_filetail(filetail *ft)
{
    close_filetail(ft);
    if (ft != NULL) {
        if (ft->buf != NULL) free(ft->buf);
        if (ft->outbuf != NULL) free(ft->outbuf);
        free(ft);
    }
    ft = NULL;
}

int open_filetail(filetail *ft, char *fname)
{
    close_filetail(ft);
    ft->fd = open(fname, O_RDONLY);
    if (ft->fd == -1) return -1;
    ft->filename = calloc(1, strlen(fname)+1);
    if (ft->filename == NULL) return -1;
    strcpy(ft->filename, fname);
    /* printf("in open_filetail: %s\n", ft->filename); */
    ft->i_oldest = 0;
    ft->i_next = 0;
    ft->position = 0;
    ft->bad_line = 0;
    ft->owned_file = 1;
    return 0;
}

int connect_filetail(filetail *ft, int fd)
{
    char fname[] = "anonymous_file";
    off_t ret;
    close_filetail(ft);
    ret = lseek(fd, 0, SEEK_SET);
    if (ret != 0) return -1;
    ft->fd = fd;
    ft->filename = calloc(1, strlen(fname)+1);
    if (ft->filename == NULL) return -1;
    strcpy(ft->filename, fname);
    /* printf("in open_filetail: %s\n", ft->filename); */
    ft->i_oldest = 0;
    ft->i_next = 0;
    ft->position = 0;
    ft->bad_line = 0;
    ft->owned_file = 0;
    return 0;
}


void close_filetail(filetail *ft)
{
    if (ft == NULL) return;
    if (ft->fd == -1) return;
    if (ft->owned_file) close(ft->fd);
    ft->fd = -1;
    free(ft->filename);
    ft->filename = NULL;
}

long bytes_available(filetail *ft)
{
    long n_avail;
    off_t filelength;

    if (ft->fd == -1) return 0;
    fstat(ft->fd, &(ft->st));
    filelength = ft->st.st_size;
    /* We are not checking to make sure this has not decreased. */
    n_avail = filelength - ft->position;
    return n_avail;
}

int fill_buf(filetail *ft)
{
    long n_avail;
    int n_space;
    int n_to_read;
    int n_read;
    int n, nr;
    int n_ahead;
    int i_read = 0;

    n_avail = bytes_available(ft);
    if (n_avail == 0) return 0;
    n_space = ft->N - (ft->i_next - ft->i_oldest + ft->N) % ft->N - 1;
    if (n_space == 0) return 0;
    n_to_read = n_space < n_avail ? n_space : n_avail;
    n_read = 0;
    /*printf("fill_buf %d %d %d\n", n_avail, n_space, n_to_read);*/
    while (n_read < n_to_read && i_read < 4) {
        if (ft->i_next < ft->i_oldest) {
            n = n_space < n_avail ? n_space : n_avail;
        } else {
            n_ahead = ft->N - ft->i_next;
            if (ft->i_oldest == 0) n_ahead--;
            n = n_ahead < n_avail ? n_ahead : n_avail;
        }
        if (n == 0) break;
        nr = read(ft->fd, ft->buf + ft->i_next, n);
        if (nr == -1) return -1;
        ft->position += nr;
        ft->i_next += nr;
        ft->i_next %= ft->N;
        n_read += nr;
        n_avail -= nr;
        n_space -= nr;
        i_read++;
        /*printf("   %d %d %d %d\n", i_read, n, nr, n_read);*/
    }
    return n_read;
}

int line_from_buf(filetail *ft)
{
    /* modulo division of a negative number seems to be compiler-dependent;
       gcc on i86 does not give the same result as python, so we
       have to add ft->N first, to make the number positive.
    */
    int i, iwrap = 0;
    int n_buf = ((ft->i_next - ft->i_oldest) + ft->N) % ft->N;

    if (n_buf == 0) return 0;
    /* printf("line_from_buf n_buf %d\n", n_buf);
       printf("   %d\n", ft->i_next - ft->i_oldest);
    */
    for (i = 0; i < n_buf; i++) {
        iwrap = (ft->i_oldest + i) % ft->N;
        ft->outbuf[i] = ft->buf[iwrap];
        if (ft->buf[iwrap] == '\n') {
            i++;
            ft->outbuf[i] = '\0';
            ft->i_oldest = (iwrap + 1) % ft->N;
            ft->bad_line = 0;
            return i; /* length of line excluding nul termination */
        }
    }
    /* printf("n_buf = %d, ft->N = %d\n", n_buf, ft->N); */
    if (n_buf == ft->N - 1)
    {
        ft->i_oldest = (iwrap + 1) % ft->N;
        ft->bad_line = 1;
        return -1; /* Discarding byte string with no newline. */
    }
    return 0; /* No full line found. */
}


char *read_line(filetail *ft)
{
    int ret;
    int last_was_bad = ft->bad_line;

    if (ft->fd == -1) return empty_line; /* maybe should be error condition */
    ret = line_from_buf(ft);
    if (ret > 0 && !ft->bad_line && !last_was_bad) return ft->outbuf;
    // ret = fill_buf(ft);
    while (fill_buf(ft) > 0) {
        last_was_bad = ft->bad_line;
        ret = line_from_buf(ft);
        if (ret > 0 && !ft->bad_line && !last_was_bad) return ft->outbuf;
    }
    return empty_line;
}

int bytes_from_buf(filetail *ft, int n)
{
    int i, iwrap = 0;
    int n_buf = ((ft->i_next - ft->i_oldest) + ft->N) % ft->N;

    if (n > n_buf) return 0;
    if (n == 0) return 0;
    for (i = 0; i < n; i++) {
        iwrap = (ft->i_oldest + i) % ft->N;
        ft->outbuf[i] = ft->buf[iwrap];
    }
    ft->i_oldest = (iwrap + 1) % ft->N;
    return n;
}

int read_bytes(filetail *ft, int n)
{
    int ret;

    if (ft->fd == -1) return -1;
    if (n >= ft->N) return -2;
    ret = bytes_from_buf(ft, n);
    if (ret > 0) return ret;
    ret = fill_buf(ft);
    if (ret > 0) {
        ret = bytes_from_buf(ft, n);
        if (ret > 0) return ret;
    }
    return 0;
}

char *get_outbuf(filetail *ft)
{
    return ft->outbuf;
}

int get_N(filetail *ft)
{
    return ft->N;
}

#if 0
int main(int argc, char **argv)
{
    filetail *ft;
    int ret;
    char *line;

    ft = new_filetail(1024);
    ret = open_filetail(ft, argv[1]);
    if (ret != 0) {
        printf("Can't open file %s\n", argv[1]);
        exit(-1);
    }
    while (1) {
        line = read_line(ft);
        if (line == empty_line) sleep(1); /* testing; too long in general */
        else {
            fputs(line, stdout);
            fflush(stdout);
        }
    }
}
#endif

