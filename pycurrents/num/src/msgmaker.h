/* The following are added to support the python interface. */
void set_msg_stderr(int tf);
void set_msg_bigbuf(int tf);
void reset_msg(void);
char *get_msg_buf(void);

void report_msg(char *msg);
int get_msg(char *msg_ptr, int n);
void sprintf_msg(char *fmt, ...);

