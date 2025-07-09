'''
mfile.py provides a function, m_to_dict, for parsing a string
consisting of lines from an m-file, each of which simply specifies
a string or numeric variable with its value.  This is not a
complete parser!

'''

## EF 2004/10/04: Added variable substitution, made the
## names arguments optional. Removed dictionary and
## "is_string" arguments.

## EF 2003/12/14: removed is_string argument, added documentation
## and demo.  Added comment removal and parsing of cell arrays
## containing lists of strings (without spaces).

## Original was written in August 2002, on KM cruise, Panama to Honolulu.

import re

class Bunch(dict):
    def __init__(self, *args, **kw):
        dict.__init__(self, *args, **kw)
        self.__dict__ = self

def mfile_to_bunch(fname, names=None):
    return mfile_to_dict(fname, names=None, bunch=True)

def mfile_to_dict(fname, names=None, bunch=False):
    """
    Like m_to_dict, but takes a filename instead of a string.
    """
    with open(fname) as newreadf:
        s = newreadf.read()
    return m_to_dict(s, names=names, bunch=bunch)

def m_to_dict(s, names = None, bunch=False):
    '''
    Try to fill a dictionary with variables from an m-file.

    s is a string from an m-file
    names is a sequence of variable names to find in the string.
    If names is None, it uses each string to the left of
    an '='.

    The function returns the dictionary, which it creates if
    it did not already exist.

    If a name in names is not found, no error is raised.

    If bunch is True, a Bunch is returned instead of a dict,
    and any dots in keys are replaced with underscores.

    '''

    # Clean out comments and join continued lines.

    lines = s.split('\n')
    cleanlines = []
    for line in lines:
        line = line.split('%', 2)[0]
        i_cont = line.find('...')
        if i_cont >= 0:
            line = line[:i_cont] + ' '
        else:
            line = line + '\n'
        line = line.lstrip()
        line = line.replace(';', '')
        if len(line) > 3:
            cleanlines.append(line)
    s = ''.join(cleanlines)
    if bunch:
        d = Bunch()
    else:
        d = dict()
    if names is None:
        names = []
        for line in cleanlines:
            fields = line.split('=')
            if len(fields) == 2:
                names.append(fields[0].strip())
    for name in names:
        if bunch:
            namekey = name.replace('.', '_')
        else:
            namekey = name
        # Check for a string first:
        pat = r"%s\s*=\s*'(.+)'" % name
        f = re.search(pat, s)
        if f:
            d[namekey] = f.group(1)
            continue
        # Is it a cell array, with a list of strings?
        pat = r"%s\s*=\s*(\{.*\})" % name
        f = re.search(pat, s)
        if f:
            g = f.group(1).replace('{', '[').replace('}', ']').replace(';', ',')
            d[namekey] = eval(g)
            continue
        # Is it a number or previously defined variable?
        pat = r"%s\s*=\s*(\S+)" % name
        f = re.search(pat, s)
        if f:
            num_s = f.group(1)
            try:
                n = int(num_s)
            except ValueError:
                try:
                    n = float(num_s)
                except ValueError:
                    try:
                        n = d[num_s]
                    except:
                        continue
            d[namekey] = n
    return d

if __name__ == "__main___":
    import sys
    with open(sys.argv[1]) as newreadf:
        s = newreadf.read()
    d =  m_to_dict(s)
    for key, item in d.items():
        print(key, '  :  ', item)
