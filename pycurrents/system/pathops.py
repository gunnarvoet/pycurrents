'''Pathname operations beyond os.path.
'''
import os.path

def filename_base(pathname):
    return os.path.split(pathname)[1].split('.')[0]

def basename(fname):
    """
    Strip directories and extensions from a path or sequence of paths.
    """
    if len(fname) == 0:    # presumably an empty list; return empty list
        return []
    if len(fname[0]) > 1:  # fname is a list, not a filename
        return [filename_base(f) for f in fname]
    return filename_base(fname)


def corresponding_pathname(pathname, dir, ext):
    '''Generate a new path preserving a base filename.

    The base filename is the filename up to the first dot.

       pathname: path containing the original filename
       dir: directory path of new file
       ext: new extension, including the leading dot

    Note that ext differs from the output of os.path.splitext;
    the latter never includes a dot other than the leading dot.

    If pathname is a sequence of paths, a corresponding list is returned.
    '''
    fnbase = basename(pathname)
    if len(fnbase) == 0:    # presumably an empty list; return empty list
        return []
    if len(fnbase[0]) > 1:  # fname is a list, not a filename
        return [os.path.join(dir, fnb + ext) for fnb in fnbase]
    return os.path.join(dir, fnbase + ext)


def get_common_filelist(*filelists):
    '''
    Generate a list of file base names common to a set of lists.
    The input lists are the arguments.
    The output list is sorted; any initial ordering is destroyed
    by the set intersection operation.
    '''
    flist = list(filelists[0])  # copy it so we don't alter the original
    for f in filelists[1:]:
        flist.extend(f)
    return sorted(set(basename(flist)))


def make_filelist(arg, base=None, abs=False, sorted=None, allow_empty=False):
    """
    return a list of filenames or paths

    arg can be a filename, a glob, or a sequence of paths
    base is a path to be prepended to all filenames; if
        arg is a glob, then base will be prepended prior to globbing.
    if abs is true, all paths will be made absolute
    if sorted is True, the paths will be sorted in lexical order;
                if False, no sorting will be done.  The default,
                None, sorts only if arg is a glob.
    If allow_empty is False (default) and a glob is supplied,
        ValueError will be raised if no files are found.

    """
    if hasattr(arg, "islower"):  # duck type test for string-like
        if '*' in arg or '?' in arg:
            import glob
            if base is not None:
                arg = os.path.join(base, arg)
                base = None
            fl = glob.glob(arg)
            if len(fl) < 1:
                if allow_empty:
                    return []
                raise ValueError("No files were found using glob: ", arg)
            if sorted is None:
                sorted = True
        else:
            fl = [arg]
    else:
        fl = list(arg)
    if sorted:
        fl.sort()
    if base is not None:
        fl = [os.path.join(base, fn) for fn in fl]
    if abs:
        fl = [os.path.abspath(fn) for fn in fl]
    return fl

