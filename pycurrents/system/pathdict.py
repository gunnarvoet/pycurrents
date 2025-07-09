''' Wrap a dictionary of paths into a class with several
    useful methods from os.path. More can be added.

    The constructor simply makes a dictionary and calls it
    "path".
    The "set" method takes a path name (the dictionary key)
    and a set of components as additional arguments; it
    builds the path, adds it to the dictionary, and returns
    it.

'''
# 2002/08/31 EF

import os.path

class PathDict:
    def __init__(self):
        self.path = self.__dict__

    def set(self, key, *components):
        if not components or components[0] == None:
            pk = None
        else:
            pk = os.path.join(*components)
        self.path[key] = pk
        return pk

    def get(self, key):
        return self.path[key]

    def delete(self, key):
        del self.path[key]

    def basename(self, key):
        return os.path.basename(self.path[key])

    def dirname(self, key):
        return os.path.dirname(self.path[key])

    def exists(self, key):
        return os.path.exists(self.path[key])

    def isfile(self, key):
        return os.path.isfile(self.path[key])

    def isdir(self, key):
        return os.path.isdir(self.path[key])

    def normpath(self, key, set = 0):
        p = os.path.normpath(self.path[key])
        if set:
            self.path[key] = p
        return p

    def abspath(self, key, set = 0):
        p = os.path.abspath(self.path[key])
        if set:
            self.path[key] = p
        return p

    def split(self, key):
        return os.path.split(self.path[key])

    def splitext(self, key):
        return os.path.splitext(self.path[key])

