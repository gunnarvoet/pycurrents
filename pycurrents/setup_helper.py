"""
Helper functions for use in setup.py and runsetup.py:

write_hg_status() records hg status at the time of installation
in a module, hg_status.py, which can then be imported.

find_codasbase() returns the prefix to which codas was installed.
The codas binaries must be on your path.
"""

import platform
import subprocess
from subprocess import check_output, CalledProcessError
import sys
import os
import glob
import logging

_log = logging.getLogger(__file__)

if sys.platform == "win32":
    print('Windows is not supported')
    sys.exit(-1)


def find_executable(names):
    for _name in names:
        res = subprocess.run(['which', _name], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        if res.returncode == 0 and res.stdout.decode('ascii').startswith(sys.prefix):
            return _name
    return None


pip_cmd = find_executable(['pip3', 'pip'])
if pip_cmd is None:
    raise RuntimeError("Cannot find a 'pip' co-located with the running python.")
_pip_ver_str = check_output([pip_cmd, "--version"], text=True)
# pip 22.3.1 from /Users/efiring/miniconda3/envs/pycodas/lib/python3.10/site-packages/pip (python 3.10)
pip_major = int(_pip_ver_str.split()[1].split('.')[0])


def write_file_as_user(fpath, contents):
    with open(fpath, "wt") as f:
        f.write(contents)
    # It seems that when xrdp is used to open a graphics connection, the user
    # of that connection ends up with SUDO_USER=root, etc.
    if 'SUDO_USER' in os.environ and os.environ['SUDO_USER'] != 'root':
        try:
            os.chown(fpath, int(os.environ['SUDO_UID']),
                    int(os.environ['SUDO_GID']))
        except:
            print(f"chown on {fpath} with {os.environ['SUDO_USER']} failed")

def write_hg_status(dest=None):
    if dest is None:
        fpath = "hg_status.py"
    else:
        fpath = os.path.join(dest, "hg_status.py")
    commentstr = '\n'.join([
        '# this program is created during the install process.',
        '# DO NOT edit by hand.',
        '# Instead, import hg_status and use its attributes.\n\n'])
    defline = "installed = '''\n"
    endline = "'''\n"
    try:
        summary = check_output(["hg", "summary"]).decode('ascii', 'ignore')
        rev = summary.split(' ', 2)[1]
        log = check_output(["hg", "log", "-r", rev]).decode('ascii', 'ignore')
        status = check_output(["hg", "status"]).decode('ascii', 'ignore')
        lines = ''.join([commentstr, defline, summary,
                         '---\n', log, '---\n', status,  endline])
    except OSError:
        lines = defline + 'no hg found; continuing\n' + endline
    except CalledProcessError:
        lines = defline + 'Error calling hg; continuing\n' + endline

    write_file_as_user(fpath, lines)

get_test_data_template = """
# this program is created during the install process.
# DO NOT edit by hand.

import os

error_msg = '''
-Test data could not be found-
PYCURRENTS_TEST_DATA environment variable is not defined.
DOWNLOAD the pycurrents test data set,
EXPORT its path as PYCURRENTS_TEST_DATA env. var. and
TRY AGAIN
'''

def get_test_data_path():
    if 'PYCURRENTS_TEST_DATA' in os.environ:
        test_data_path = os.environ['PYCURRENTS_TEST_DATA']
    else:
        test_data_path = '%s'

    if not os.path.isdir(test_data_path):
        raise RuntimeError(error_msg)
    return test_data_path
"""


def write_get_test_data(dest=None):
    here = os.path.abspath(os.curdir)
    test_data_path = os.path.normpath(os.path.join(here, '../pycurrents_test_data'))
    if dest is None:
        fpath = "get_test_data.py"
    else:
        fpath = os.path.join(dest, "get_test_data.py")
    write_file_as_user(fpath, get_test_data_template % test_data_path)


def _read_codasbase(prefix=None):
    if prefix is None:
        cmd = 'codas_prefix'
    else:
        cmd = os.path.join(prefix, 'bin', 'codas_prefix')
    codas_prefix = check_output(cmd)
    codas_prefix = str(codas_prefix.decode().strip())
    return codas_prefix


def find_codasbase():
    """
    Locate the prefix to which CODAS was installed.

    """
    fpath = 'codas_prefix.cache'
    try:
        codas_prefix = _read_codasbase()
    except OSError:
        if not os.path.isfile(fpath):
            raise RuntimeError(
                    'CODAS executables installed by waf must be on your path\n'
                    'or the codas prefix must be in "codas_prefix.cache"')

        with open(fpath) as f:
            prefix = f.read()
        try:
            codas_prefix = _read_codasbase(prefix)
        except OSError:
            raise RuntimeError(
                    'CODAS executables installed by waf must be on your path')
    write_file_as_user(fpath, codas_prefix)
    return codas_prefix


def show_installed(package):
    res = subprocess.run([pip_cmd, 'list', '-e', '--format', 'freeze', '-v'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in res.stdout.decode('ascii').split('\n'):
        if line.startswith(package):
            print('Installed as editable:\n%s\n' % line)
            return True, 'editable'
    res = subprocess.run([pip_cmd, 'list', '--format', 'freeze', '-v'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in res.stdout.decode('ascii').split('\n'):
        if line.startswith(package):
            print('Installed normally:\n%s\n' % line)
            return True, 'normal'
    print('Not installed')
    return False, 'uninstalled'

def uninstall(package, options):
    cmdlist = ['sudo'] if options.sudo else []
    cmdlist.extend([pip_cmd, 'uninstall'])
    if options.yes:
        cmdlist.append('-y')
    if hasattr(options, 'Break_system_packages') and options.Break_system_packages is True:
        cmdlist.append('--break-system-packages')
    cmdlist.append(package)
    print("running '%s'" % ' '.join(cmdlist))
    subprocess.run(cmdlist, cwd='/tmp')

def build(package, options):
    wheels = glob.glob(f"{package}*.whl")
    if len(wheels) > 0:
        print(f"Found existing wheel(s): {wheels}; deleting them.")
        for fname in wheels:
            os.remove(fname)

    with open("runsetup.log", "w") as f:
        f.write("Pip output via --log option\n------------------\n\n")
    try:
        _all = options.all
    except AttributeError:
        _all = False
    if _all:
        if pip_major < 23:
            # ubuntu 22.04, python 3.10, pip major is 22.0.2
            opt_all = ' --global-option=--all '
        else:
            # python >= 3.11 includes pip major >= 23
            # config-settings was added in pip 22.1; is required in 23
            opt_all = ' --config-settings global-option=--all '
    else:
        opt_all = ''

    opts = f" --log=runsetup.log --no-cache-dir --no-index --no-build-isolation {opt_all} "

    if hasattr(options, 'Break_system_packages') and options.Break_system_packages is True:
            if 'noble' not in platform.freedesktop_os_release().get("VERSION_CODENAME"):
                _log.warning('Break_system_packages has only been tested in Ubuntu noble')
            opts += ' --break-system-packages '
    opts += " --no-build-isolation "
    _log.info(f"pip opts are {opts}")

    if options.develop:
        cmd = f"{pip_cmd} install -e {opts} ."
        errmsg = "editable installation failed"
    else:
        _sudo = "sudo " if options.sudo else ""
        cmd = f"{_sudo}{pip_cmd} install {opts} ."
        errmsg = "normal (non-editable) installation failed"
    print('running command:')
    print(cmd)
    cmd_obj = subprocess.run(cmd.split(), text=True, capture_output=True)
    if cmd_obj.returncode:
        print(errmsg)
        print("stdout:\n{cmd_obj.stdout}\n--------------\n")
        print("stderr:\n{cmd_obj.stderr}\n--------------\n")
        sys.exit(cmd_obj.returncode)
    if options.develop:
        print("{package} installed as editable.")
        sys.exit(0)

    res = subprocess.run([pip_cmd, 'show', package], text=True,
                         capture_output=True)
    for line in res.stdout.split('\n'):
        if line.startswith("Location"):
            print(line)
            sys.exit(0)


def clean(options):
    try:
        cmd = 'sudo ' if options.sudo else ''
        cmd += 'hg purge --all'
        subprocess.run(cmd.split(), check=True)
        print("ran '%s'" % cmd)
    except subprocess.CalledProcessError:
        print('Could not run "hg purge --all";'
              ' is Mercurial installed and is the purge extension activated?'
              ' You need a line, "purge=", in the "[extensions]" section'
              ' of your "~/.hgrc" file.')

