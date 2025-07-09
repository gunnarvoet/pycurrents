"""
This is used to generate uhdas_cfg and proc_cfg files.
"""
import re
import string


def str_repr(s):
    # Double quotes work for both py and toml.
    return repr(s).replace("'", '"')

def _str(s, filetype):
    if filetype == "toml":
        if isinstance(s, bool):
            return "true" if s else "false"
        if isinstance(s, tuple):
            return str(list(s))
        if s is None:
            return '"None"'  # Or some other string? or a number like -1?
    return str(s)

class PrettyDict(dict):
    """
    Class to make dictionaries that print nicely
    """
    def __init__(self, d, filetype="py"):
        self.filetype = filetype
        super().__init__(d)

    def _str_py(self):
        lines = ['dict(',]
        for kk,vv in self.items():
            if isinstance(vv, str):
                ll='%10s = %s,' % (str(kk), str_repr(vv))
            else:
                ll='%10s = %s,' % (str(kk), str(vv))
            lines.append(ll)
        lines.append(')')
        return '\n'.join(lines)

    def _str_toml(self):
        parts = []
        for kk, vv in self.items():
            if isinstance(vv, str):
                part = f"{kk} = {str_repr(vv)}"
            else:
                part = f"{kk} = {_str(vv, 'toml')}"
            parts.append(part)
        middle = ", ".join(parts)
        return f"{{ {middle} }}"  # toml likes the spaces

    def __str__(self):
        if self.filetype == "py":
            return self._str_py()
        else:
            return self._str_toml()


class PrettyList(list):
    """
    Class to make list that prints nicely
    """
    def __init__(self, iterable=(), filetype="py"):
        self.filetype = filetype
        super().__init__(iterable)

    def __str__(self):
        lines = ['[',]
        for kk in self:
            if isinstance(kk, str):
                lines.append('    %s,' % (str_repr(kk)))
            else:
                lines.append('    %s,' % (_str(kk, self.filetype)))

        lines.append(']')
        return '\n'.join(lines)

#-----------
# FIXME: It's not private; imported both in pycurrents and in uhdas.
def _initvar(varformat):
    if varformat == 'string':
        return ""
    elif varformat == 'list':
        return []
    elif varformat == 'num':
        return None
    elif varformat == 'bool':
        return False
    elif varformat[-4:] == 'dict':
        return dict()
    else:
        ValueError('variable type %s not available ' % (varformat))

#-----------


class Templater:
    def __init__(self, template_str, subdict, formats, filetype='py'):
        '''
        template_str: string with templates written as __name__
        subdict: keys are names in template_str, values are substituted
        formats: same keys as subdict, with values describing data type
             'num', 'list', 'dict', 'bool'


        change template_str from __name__ to ${name}
        substitute values into that template_str
        prettyprint version stored in 'pstr' attribute
        '''
        self.template_str = template_str
        self.pdict = subdict
        self.varformat = formats
        self.filetype = filetype

        self.make_template()
        self.make_strings()
        self.substitute()

    ##----
    def make_template(self):
        lines = self.template_str.split('\n')
        template_keys = []
        for line in lines:
            found=re.findall(r'__\w+__',line)
            for ff in found:
                template_keys.append(ff[2:-2])
        self.template_keys = template_keys
        self.lines=lines
        for kk in template_keys:
            newstr = re.sub('__%s__' % (kk), '%s = ${%s}' % (kk,kk), self.template_str)
            self.template_str = newstr

    def make_strings(self):
        sstrings = {}

        for kk in self.template_keys:
            if kk in self.pdict.keys():
                if self.varformat[kk][-4:] == 'dict':
                    sstrings[kk] = PrettyDict(self.pdict[kk], self.filetype)
                elif self.varformat[kk][-4:] == 'list':
                    sstrings[kk] = PrettyList(self.pdict[kk], self.filetype)
                elif self.varformat[kk] == 'string':
                    sstrings[kk] = str_repr(self.pdict[kk])
                else:
                    sstrings[kk] = _str(self.pdict[kk], self.filetype)
            else:
                print('template key "%s" missing from proc pdef.' % (kk))
                sstrings[kk] = 'None'
        self.sstrings = sstrings

    def substitute(self):
        s = string.Template(self.template_str)
        self.pstr = s.substitute(**self.sstrings)
