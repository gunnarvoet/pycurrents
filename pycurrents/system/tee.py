"""
tee.py: defines class tee which creates a file-like object
that can write to more than one location (file or gui
object), applying filters to determine which strings go to
which locations.

See tkMessageFile.py for more examples of writeable gui objects.

See demo() for an example and test.

"""

# 2002/08/27 EF

# This could be reimplemented using dictionaries and named
# destinations, so that one could remove a destination by
# name instead of having to know the index. **IMPORTANT**

# 2003/12/14 EF added case_sensitive option and
# documentation.
# 2004/07/09 EF added time_tag option.
#  possibly something still needs to be done to ensure
#  line buffering of all streams; as it is, it seems that
#  what should be a single line can get split, thereby
#  ending up with two time tags.

import re
import time

def _simple(file, string, ifunc, xfunc):
    file.write(string)

def _include(file, string, ifunc, xfunc):
    if ifunc(string):
        file.write(string)

def _exclude(file, string, ifunc, xfunc):
    if not xfunc(string):
        file.write(string)

def _include_exclude(file, string, ifunc, xfunc):
    if ifunc(string) and not xfunc(string):
        file.write(string)

_funcs = [_simple, _include, _exclude, _include_exclude]


class tee:
    ''' Arguments to class constructor and add method are:
        to:       any object with a write method that takes a
                  string argument.

        include, exclude: a string that can be interpreted as
                  a regular expression, or a callable object
                  taking a string as an argument and
                  returning True or False.

        case_sensitive: 1 or True if case-sensitive
                  (default), 0 or False otherwise;
                  specifying this in the constructor sets the
                  default, which can be overridden for a
                  particular location when it is added with
                  the add method.

        time_tag: 1 or True to prepend a time stamp to each
                  message; default is 0 or False.

    '''


    def __init__(self, to = None, include = None,
                      exclude = None, case_sensitive = 1,
                      time_tag = 0):
        self.to = []
        self.include = []
        self.exclude = []
        self.write_func = []
        self.n = 0
        self.case_sensitive = case_sensitive
        self.time_tag = time_tag
        if to:
            self.add(to, include, exclude)

    def add(self, to, include = None, exclude = None,
                case_sensitive = None):
        if case_sensitive is None:
            case_sensitive = self.case_sensitive
        if case_sensitive:
            re_flag = 0
        else:
            re_flag = re.I
        self.to.append(to)
        ii = 0
        if include is None:
            self.include.append(None)
        else:
            ii = ii + 1
            if callable(include):
                self.include.append(include)
            else:
                self.include.append(re.compile(include, re_flag).search)
        if exclude is None:
            self.exclude.append(None)
        else:
            ii = ii + 2
            if callable(exclude):
                self.exclude.append(exclude)
            else:
                self.exclude.append(re.compile(exclude, re_flag).search)
        self.write_func.append(_funcs[ii])
        self.n += 1

    def write(self, str_):
        str_ = str_.rstrip() + '\n'   # In case Pmw strips off the newline.
        if len(str_.strip()) < 1:     # Eliminate blank lines.
            return                     # Maybe Pmw is adding them.
        if self.time_tag:
            s = time.strftime('%Y/%m/%d %H:%M:%S - ', time.gmtime()) + str_
        for ii in range(self.n):
            self.write_func[ii](self.to[ii], s, self.include[ii], self.exclude[ii])

    def flush(self):
        for fobj in self.to:
            if hasattr(fobj, "flush"):
                fobj.flush()

    def remove(self, index):
        if index >= self.n:
            return              # silently refuse; Q&D
        self.n -= 1
        del(self.to[index])
        del(self.include[index])
        del(self.exclude[index])
        del(self.write_func[index])

def demo():
    import sys
    from tkinter.messagebox import showerror

    class test_writer:

        def write(self, msg):
            showerror('Tee demo', msg)

    tw = test_writer()

    # Start with stdout; exclude strings with 'Error' in them:
    T = tee(sys.stdout, exclude = 'error',
                      case_sensitive = False,
                      time_tag = 1)

    # Error messages go to a Tk box: (We don't really need to
    # use re.search here; it is included just to demonstrate
    # how a callable can be used in place of a regular expression.
    T.add(tw, (lambda x: re.search('error', x, re.I)), 'No Error')

    if len(sys.argv) < 2:
        print(__doc__)
    else:
        for arg in sys.argv[1:]:
            T.write(arg)

if __name__ == "__main__":
    demo()

