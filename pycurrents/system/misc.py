"""
Miscellaneous things that are too small to warrant a module.
"""

from string import Template

import time
import os
import errno

# originally based on Robert Kern's Bunch; now modified to avoid
# the circular reference:
class Bunch(dict):
    """
    A dictionary that also provides access via attributes.

    Additional methods update_values and update_None provide
    control over whether new keys are added to the dictionary
    when updating, and whether an attempt to add a new key is
    ignored or raises a KeyError.

    The Bunch also prints differently than a normal
    dictionary, using str() instead of repr() for its
    keys and values, and in key-sorted order.  The printing
    format can be customized by subclassing with a different
    str_ftm class attribute.  Do not assign directly to this
    class attribute, because that would substitute an instance
    attribute which would then become part of the Bunch, and
    would be reported as such by the keys() method.

    To output a string representation with
    a particular format, without subclassing, use the
    formatted() method.
    """

    str_fmt = "{0!s:<{klen}} : {1!s:>{vlen}}\n"

    def __init__(self, *args, **kwargs):
        """
        *args* can be dictionaries, bunches, or sequences of
        key,value tuples.  *kwargs* can be used to initialize
        or add key, value pairs.
        """
        dict.__init__(self)
        for arg in args:
            self.update(arg)
        self.update(kwargs)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError("'Bunch' object has no attribute '%s'" % name)

    def __setattr__(self, name, value):
        self[name] = value

    def __str__(self):
        return self.formatted()

    def formatted(self, fmt=None, types=False):
        """
        Return a string with keys and/or values or types.

        *fmt* is a format string as used in the str.format() method.

        The str.format() method is called with key, value as positional
        arguments, and klen, vlen as kwargs.  The latter are the maxima
        of the string lengths for the keys and values, respectively,
        up to respective maxima of 20 and 40.
        """
        if fmt is None:
            fmt = self.str_fmt

        items = list(self.items())
        items.sort()

        klens = []
        vlens = []
        for i, (k, v) in enumerate(items):
            lenk = len(str(k))
            if types:
                v = type(v).__name__
            lenv = len(str(v))
            items[i] = (k, v)
            klens.append(lenk)
            vlens.append(lenv)

        klen = min(20, max(klens))
        vlen = min(40, max(vlens))
        slist = [fmt.format(k, v, klen=klen, vlen=vlen) for k, v in items]
        return ''.join(slist)

    def _from_pylines(self, pylines):
        # We can't simply exec the code directly, because in
        # Python 3 the scoping for list comprehensions would
        # lead to a NameError.  Wrapping the code in a function
        # fixes this.
        d = dict()
        lines = ["def _temp_func():\n"]
        lines.extend([f"    {line.rstrip()}\n" for line in pylines])
        lines.extend(["\n    return(locals())\n",
                      "_temp_out = _temp_func()\n",
                      "del(_temp_func)\n"])
        codetext = "".join(lines)
        code = compile(codetext, '<string>', 'exec')
        exec(code, globals(), d)
        self.update(d["_temp_out"])
        return self

    # If I were starting again, I would probably make the following two
    # functions class methods instead of instance methods, so they would
    # follow the factory pattern.  Too late now.

    def from_pyfile(self, filename):
        """
        Read in variables from a python code file.
        """
        with open(filename) as f:
            pylines = f.readlines()
        return self._from_pylines(pylines)

    def from_pystring(self, pystr):
        """
        Read in variables from a python code string.
        """
        pylines = pystr.split('\n')
        return self._from_pylines(pylines)

    def update_values(self, *args, **kw):
        """
        arguments are dictionary-like; if present, they act as
        additional sources of kwargs, with the actual kwargs
        taking precedence.

        One reserved optional kwarg is "strict".  If present and
        True, then any attempt to update with keys that are not
        already in the Bunch instance will raise a KeyError.
        """
        strict = kw.pop("strict", False)
        newkw = dict()
        for d in args:
            newkw.update(d)
        newkw.update(kw)
        self._check_strict(strict, newkw)
        dsub = dict([(k, v) for (k, v) in newkw.items() if k in self])
        self.update(dsub)

    def update_None(self, *args, **kw):
        """
        Similar to update_values, except that an existing value
        will be updated only if it is None.
        """
        strict = kw.pop("strict", False)
        newkw = dict()
        for d in args:
            newkw.update(d)
        newkw.update(kw)
        self._check_strict(strict, newkw)
        dsub = dict([(k, v) for (k, v) in newkw.items()
                                if k in self and self[k] is None])
        self.update(dsub)

    def _check_strict(self, strict, kw):
        if strict:
            bad = set(kw.keys()) - set(self.keys())
            if bad:
                bk = list(bad)
                bk.sort()
                ek = list(self.keys())
                ek.sort()
                raise KeyError(
                    "Update keys %s don't match existing keys %s" % (bk, ek))


class Cachefile:
    """
    class for cache file manilulation: init, read, write
    file is key, value; anything after a '#' is ignored
    """

    def __init__(self, cachefile=None, contents='parameters'):
        if cachefile is None:
            raise IOError('no file specified')

        self.cachefile = cachefile
        self.contents = contents
        self.comments = []

    #-------
    def init(self, *args, **kw):
        '''
        start the file, eg metafile with information to cache,
                           or which is not in the database
        initialize file with *args (dict, bunch, tuples) and **kw
        '''
        # only init if empty or nonexistent
        if os.path.exists(self.cachefile):
            # This late and local initialization is needed; otherwise
            # a root logger is created when logutils itself is
            # imported, which defeats its functionality.
            # FIXME - not consistent with new logging scheme
            import logging
            _log = logging.getLogger(__file__)
            _log.warning('file %s exists.  not initializing' %
                          (self.cachefile))
        self.cachedict=Bunch({})
        self.cachedict.update(*args, **kw)

        # initialize the comments here
        self.comments = ['#this file was automatically generated. DO NOT EDIT',
               '#\n'
               '# written %s\n' % (nowstr()),
               '# this file contains ' + self.contents + '\n',
               '#name, value pairs',
               '#--------------------',
              ]

        self.write()
    #-------
    def _strip_comments(self, lines):
        '''
        strip comments, return a dictionary
        comment protocol: put "#" at the front of line or whitespace split chunk
        '''
        cache_dict = {}
        comments = []
        for line in lines:
            line.rstrip()
            parts = line.split()
            for ipp in range(len(parts)):
                if parts[ipp][0] == '#':   #simple comment strip
                    comments.append(' '.join(parts[ipp:]))
                    parts=parts[:ipp]
                    break
            if len(parts) == 2:
                cache_dict[parts[0]] = parts[1]


        return cache_dict, comments

    #-------
    def add_comments(self, lines):
        '''
        add comments
        '''
        comments = []
        for line in self.comments:
            if line not in comments:
                comments.append(line)

        for line in lines:
            if line not in self.comments:
                self.comments.append(line)

    #------
    @staticmethod
    def _parse(arg):
        try:
            ret = float(arg)
            if int(ret) == ret:
                return int(ret)
            return ret
        except ValueError:
            if arg.lower() == 'none':
                return None
            return arg

    #----
    def _translate(self):
        '''
        translate  'None' into None, read numbers as float or int
        '''
        for key, val in self.cachedict.items():
            self.cachedict[key] = self._parse(val)

    #-------
    def read(self):
        '''
        metafile with information to cache, or which is not in the database
        read; sets attribute "cache" (Bunch, from file contents)

        '''
        ## This needs help ("intnames" is clunky)

        # read if present
        if os.path.exists(self.cachefile) is False or (
                             os.path.exists(self.cachefile) is True and
                             os.path.getsize(self.cachefile)==0):
            raise IOError('cannot read cachefile %s' % self.cachefile)

        with open(self.cachefile,'r') as newreadf:
            lines = newreadf.readlines()
        cdict, self.comments = self._strip_comments(lines)
        self.cachedict = Bunch(cdict)
        self._translate()

    #-------
    def write(self, *args, **kw):
        '''
        update variables in self.cachedict from *args and  kw.keys
        key must exist in cache *before* calling write method
        then write to cachefile

        '''

        # read anyway, initialize it if necessary

        self.cachedict.update_values(*args, **kw)

        llist=[]
        kk= list(self.cachedict.keys())
        kk.sort()
        for k in kk:
            llist.append('%20s   %s' %(k,self.cachedict[k]))
        cf = open(self.cachefile,'w')
        cf.write('\n'.join(self.comments))
        cf.write('\n')
        cf.write('\n'.join(llist))
        cf.write('\n')
        cf.close()


def sleep(secs):
    '''
    This works just like time.sleep except that it traps an error.
    The IOError "unknown error 514" seems to be caused by a linux
    kernel bug.
    '''
    try:
        time.sleep(secs)
    except IOError:
        pass


def guess_comment(fname, cstr='%#', numlines=10):
    '''
    guess the comment character from a line of text
    (matlab processing uses '%', python processing uses '#')

    returns first comment character match, or None
    '''
    F = open(fname, 'r')
    for num in range(numlines):
        line = F.readline().strip()
        for cc in cstr:
            if line.startswith(cc):
                return cc

def nowstr():
    '''
    get utc time from computer clock, return string "yyyy/mm/dd hh:mm:ss"
    '''
    return time.strftime("%Y/%m/%d %H:%M:%S")


class ScripterBase:
    """
    Base class for classes that write standalone scripts.

    The script is left behind for later command-line use.
    The code in the script is run using exec.

    This is designed for quick_adcp.

    """

    script_head = ""
    script_body = ""
    script_tail = ""
    defaultparams = {}

    def __init__(self, *args, **kw):
        """
        The optional first argument is a dictionary of options.
        Additional options may be specified via keyword arguments.
        """
        if len(args):
            self.optdict = args[0]
        else:
            self.optdict = {}
        self.kw = kw
        fname = self.__class__.__name__ + '_script.py'
        self.script_filename = kw.get('script_filename', fname)
        self.params = self.defaultparams.copy()
        for k, v in self.optdict.items():
            if k in self.params:
                self.params[k] = v
        self.params.update(kw)

    def __call__(self, **kw):
        """
        Call can be used for stand-alone plotting, with any kw
        params supplied here overriding those from instantiation.

        Subclass should call this method at the start of its own
        __call__ method.
        """

        self.params.update(kw)
        self.process_params()
        # Turn all parameters into attributes, for convenience.
        for k, v in self.params.items():
            setattr(self, k, v)
        # Actual calculation or plotting code follows this in subclass.

    def process_params(self):
        """
        Subclass will use this for validation etc.
        """
        pass

    def fill_strings(self):
        self.head = Template(self.script_head).substitute(self.params)
        self.body = Template(self.script_body).substitute(self.params)
        self.tail = Template(self.script_tail).substitute(self.params)

    def write(self, filename=None):
        self.process_params()
        self.fill_strings()
        if filename is None:
            filename = self.script_filename
        script = '\n'.join([self.head, self.body, self.tail, ''])
        with open(filename, 'w') as file:
            file.write(script)

    def run(self):
        self.process_params()
        self.fill_strings()
        exec(self.body)

def safe_makedirs(*args, **kw):
    """
    Replacement for os.makedirs.

    os.makedirs raises an exception if the requested path
    already exists; safe_makedirs raises
    an exception only if the requested path cannot be made, or
    if it exists but is not a directory.
    """
    try:
        os.makedirs(*args, **kw)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(args[0]):
            raise
