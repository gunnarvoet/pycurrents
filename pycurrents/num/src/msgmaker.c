/*

    msgmaker.c: derived mainly from codas3/ioserv/rept_msg;
    provides functions for propagating messages out to cython
    extension code.

*/
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include "msgmaker.h"

/* Note: if this code is changed so that instead of being
   static arrays, the buffers are dynamically allocated, then
   their size will need to be specified differently in the calls
   to vsnprintf and strncat below.
*/
static char buf[1024];
static char bigbuf[10000];

static int to_stderr = 0;
static int to_bigbuf = 1;


void set_msg_stderr(int tf)
{
    to_stderr = tf;
}

void set_msg_bigbuf(int tf)
{
    to_bigbuf = tf;
    bigbuf[0] = '\0';
}

void reset_msg(void)
{
    bigbuf[0] = '\0';
}

char *get_msg_buf(void)
{
    return bigbuf;
}

int get_msg(char *msg_ptr, int n)
/* n is the number of bytes available in msg_ptr, not including the null */
/* copy bigbuf contents into msg_ptr, and reset bigbuf */
/* This can be called twice, once with a NULL first argument
   to return the length of bigbuf, and then a second time
   after allocating sufficient memory, pointed to by non-NULL
   msg_ptr.

    This may not actually be needed.
*/
{
    int nbuf;
    nbuf = strlen(bigbuf);
    if (msg_ptr == NULL)
    {
        return nbuf;
    }
    if (nbuf <= n)   /* msg_ptr must be of length n+1 */
    {
        strcpy(msg_ptr, bigbuf);
    }
    else
    {
        nbuf = -1; /* error return */
    }
    bigbuf[0] = '\0';
    return nbuf;
}



void report_msg(char *msg)  /* original api, wrapped by sprintf_msg */
{
   if (to_stderr)
   {
      fprintf(stderr, "%s", msg);               /* print to screen */
   }
   if (to_bigbuf)
   {
      strncat(bigbuf, msg, sizeof(bigbuf) - strlen(bigbuf) - 1);
   }
}

/* Newer API used by zgrid so that printf calls can be redirected
   to the msg bigbuf.
*/
void sprintf_msg(char *fmt, ...)
{
   va_list args;
   va_start(args, fmt);
   vsnprintf(buf, sizeof(buf), fmt, args);
   va_end(args);
   report_msg(buf);
}


