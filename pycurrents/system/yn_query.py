"""
Function used in quick_adcp for terminal-based user interaction.
"""
import os
import sys

def yn_query(query, optionstr, **choices):
    ## yn_query usage:
    #    yn_query('perform this action?', 'y', 'n', 'q', default='n', auto=0)
    #    yn_query('perform this action?', 'yq', default='y', auto=0)

    r'''
    python usage: yn_query(query, optionstr, **choices)
    shell usage: "yn_query"  (query is "perform this action?")

    This function poses the question in "query" and returns
    1 if  answer  is yes
    0 if  answer  is no
    changes directories (if specified) and quits (if 'q')

    - query is a string
    - options is one string with 'y', 'n', or 'q', (as 'ynq')
    - choices can be any or all of several name=value pairs:
                       default='n'      (or some other member of \*options)
                       auto=0
                       auto=1
                       backtodir='somedirectory'

    including auto=1 does not ask, but returns as if the default were chosen

    '''

    default = ''
    auto = 0
    backtodir = os.getcwd()

    for kw in choices.keys():
        if kw == 'default':
            default = choices[kw]
        elif kw == 'auto':
            auto = int(choices[kw])
        elif kw == 'backtodir':
            backtodir = choices[kw]

    olist = []
    for count in range(0, len(optionstr)):
        olist.append(optionstr[count])
    optionstr = '/'.join(olist)
    prompt = query + ' [' +optionstr+ ']'+' [' +default+ '] '

    ## now adapt from perl query
    if auto:
        if ((default == 'n') or (default == 'y')):
            retval = (default == 'y')
            #print 'yn_query automatically returning, with ', retval
            return retval
        if (default == 'q'):
            os.chdir(backtodir)
            sys.exit(1)

    ok = ''

    while ok not in olist:
        ok = input(prompt)

        #print 'DEBUG (yn_query): "ok" is <%s>' %ok

        if not ok:
            #print 'accepting default'
            ok = default
            if not default:
                print('no default available')

    if ((ok == 'q') or (ok == 'quit')):
        print('changing directory to ...\n', backtodir, '\n... and quitting')
        os.chdir(backtodir)
        sys.exit(1)

    retval =  (ok == 'y')
    return retval

