#!/usr/bin/env python
import argparse
import os
import platform
import re
import shutil
import sys
import subprocess
import tarfile
from pathlib import Path, PurePath
import tempfile
from colors import *
from shutil import which
from packaging.version import parse
import numpy


# Default options that the user can change with command line switches
opts = {
    'prefix': str(Path(Path.home() / 'pyoptsparse')),
    'linear_solver': 'mumps',
    'build_pyoptsparse': True,
    'intel_compiler_suite': False,
    'snopt_dir': None,
    'hsl_tar_file': None,
    'include_paropt': False,
    'include_ipopt': True,
    'keep_build_dir': False,
    'check_sanity': True,
    'conda_cmd': 'conda',
    'force_build': False,
    'ignore_conda': False,
    'ignore_mamba': False,
    'verbose': False,
    'compile_required': True, # Not set directly by the user, but determined from other options
    'uninstall': False,
    'pyoptsparse_version': None, # Parsed pyOptSparse version, set by finish_setup()
    'make_name': 'make',
    'fall_back': False,
    'pip_cmd': 'pip'
}

# Information about the host, status, and constants
sys_info = {
    'gcc_major_ver': -1,
    'gcc_is_apple_clang': False,
    'line_color': 'white',
    'msg_color': 'gray',
    'gnu_sanity_check_done': False,
    'python_sanity_check_done': False,
    'compile_cores': int(os.cpu_count()/2),
    'sys_name': platform.system(),
    'conda_activate_dir': None,
    'conda_deactivate_dir': None,
    'conda_env_script': 'pyoptsparse_lib.sh',
    'conda_forge_available': False
}

# Where to find each package, which branch to use if obtained by git,
# and which include file to test to see if it's already installed
build_info = {
    'metis': {
        'branch': 'releases/2.0.0',
        'url': 'https://github.com/coin-or-tools/ThirdParty-Metis.git',
        'src_lib_glob': 'libcoinmetis*',
        'include_subdir': 'metis',
        'include_file': 'metis.h'
    },
    'mumps': {
        'branch': 'releases/3.0.2',
        'url': 'https://github.com/coin-or-tools/ThirdParty-Mumps.git',
        'src_lib_glob': 'libcoinmumps*',
        'include_subdir': 'mumps',
        'include_file': 'mumps_c_types.h'
    },
    'ipopt': {
        'branch': 'releases/3.14.7',
        'url': 'https://github.com/coin-or/Ipopt.git',
        'src_lib_glob': 'lib*ipopt*',
        'include_subdir': '.',
        'include_glob_list': ['Ip*.hpp', 'Sens*.hpp', 'Ip*.h', 'Ip*.inc'],
        'include_file': 'IpoptConfig.h'
    },
    'pyoptsparse': {
        'branch': 'v2.10.1' if parse(numpy.__version__) < parse('2.0') else 'v2.13.1',
        'url': 'https://github.com/mdolab/pyoptsparse.git',
    },
    'hsl': {
        'branch': 'releases/2.2.1',
        'url': 'https://github.com/coin-or-tools/ThirdParty-HSL',
        'src_lib_glob': 'libcoinhsl*',
        'include_subdir': 'hsl',
        'include_file': 'CoinHslConfig.h'
    },
    'paropt': {
        'branch': 'v2.1.4',
        'url': 'https://github.com/smdogroup/paropt.git',
        'src_lib_glob': 'libparopt*',
    }
}

def process_command_line():
    """ Validate command line arguments and update options, or print usage and exit. """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='''
    Download, configure, build, and/or install pyOptSparse with dependencies.
    Temporary working directories are created, which are removed after
    installation unless -d is used.

    When running with a conda environment active, all packages that can be installed
    with conda will be, except when command line arguments modify this behavior. If
    found, mamba will be used to install/uninstall unless -m is invoked.
            ''',
        epilog='''
    NOTES:
    When using HSL as the linear solver, the source code tar file can be obtained
    from http://www.hsl.rl.ac.uk/ipopt/
    If PARDISO is selected as the linear solver, the Intel compiler suite with MKL
    must be available.

    Examples:
    build_pyoptsparse
    build_pyoptsparse --intel --linear-solver=pardiso
    build_pyoptsparse -l hsl -n -t ../../coinhsl-archive-2014.01.17.tar.gz
    '''
    )
    parser.add_argument("-a", "--paropt",
                        help="Add ParOpt support. Default: no ParOpt",
                        action="store_true",
                        default=opts['include_paropt'])
    parser.add_argument("-b", "--branch",
                        help=f"pyOptSparse release. \
                        Default: {build_info['pyoptsparse']['branch']}",
                        default=build_info['pyoptsparse']['branch'])
    parser.add_argument("-c", "--conda-cmd",
                        help=f"Command to install packages with if conda is used. \
                               Default: {opts['conda_cmd']}")
    parser.add_argument("-d", "--no-delete",
                        help="Do not erase the build directories after completion.",
                        action="store_true",
                        default=opts['keep_build_dir'])
    parser.add_argument("-e", "--ignore-conda",
                        help="Do not install conda packages, install under conda environment, \
                              or uninstall from the conda environment.",
                        action="store_true",
                        default=opts['ignore_conda'])
    parser.add_argument("-f", "--force-build",
                        help="Build/rebuild packages even if found to be installed or \
                              can be installed with conda.",
                        action="store_true",
                        default=opts['force_build'])
    parser.add_argument("-g", "--fall-back",
                        help="If a conda package fails to install, fall back to \
                              building from source. If selected, the build environment is \
                              tested in case it is needed.",
                        action="store_true",
                        default=opts['fall_back'])
    parser.add_argument("-k", "--no-sanity-check",
                        help="Skip the sanity checks.",
                        action="store_true",
                        default=not opts['check_sanity'])
    parser.add_argument("-i", "--intel",
                        help="Build with the Intel compiler suite instead of GNU.",
                        action="store_true",
                        default=opts['intel_compiler_suite'])
    parser.add_argument("-l", "--linear-solver",
                        help="Which linear solver to use with IPOPT. Default: mumps",
                        choices=['mumps', 'hsl', 'pardiso'],
                        default=opts['linear_solver'])
    parser.add_argument("-m", "--ignore-mamba",
                        help="Do not use mamba to install conda packages. \
                              Default: Use mamba if found",
                        action="store_true",
                        default=opts['ignore_mamba'])
    parser.add_argument("-n", "--no-install",
                        help=f"Prepare, but do {yellow('not')} build/install pyOptSparse itself. \
                               Default: install",
                        action="store_true",
                        default=not opts['build_pyoptsparse'])
    parser.add_argument("-o", "--no-ipopt",
                        help="Do not install IPOPT. Default: install IPOPT",
                        action="store_true",
                        default=not opts['include_ipopt']),
    parser.add_argument("-p", "--prefix",
                        help=f"Where to install if not a conda/venv environment. Default: {opts['prefix']}",
                        default=opts['prefix'])
    parser.add_argument("--pip-cmd",
                    help=f"pip command to use. Set to to --pip-cmd=='uv pip' if using uv. Default: {opts['pip_cmd']}",
                    default=opts['pip_cmd'])
    parser.add_argument("-s", "--snopt-dir",
                        help="Include SNOPT from SNOPT-DIR. Default: no SNOPT",
                        default=opts['snopt_dir'])
    parser.add_argument("-t", "--hsl-tar-file",
                        help="If HSL is the linear solver, use this as the path \
                        to the tar file of the HSL source. \
                        E.g. -t ../../coinhsl-archive-2014.01.17.tar.gz",
                        default=opts['hsl_tar_file'])
    parser.add_argument("-u", "--uninstall",
                        help="Attempt to remove include/lib files previously built from source \
                              (using the same --prefix) and/or installed with conda in the same \
                              environment, then exit. Default: Do not uninstall",
                        action="store_true",
                        default=opts['uninstall'])
    parser.add_argument("-v", "--verbose",
                        help="Show output from git, configure, make, conda, etc. and expand \
                              all environment variables.",
                        action="store_true",
                        default=opts['verbose'])

    args = parser.parse_args()

    # Update options with user selections
    opts['include_paropt'] = args.paropt
    opts['include_ipopt'] = not args.no_ipopt
    build_info['pyoptsparse']['branch'] = args.branch

    # Determine conda settings
    opts['ignore_conda'] = args.ignore_conda
    opts['ignore_mamba'] = args.ignore_mamba

    if opts['ignore_conda'] is False and conda_is_active():
        if args.conda_cmd is not None:
            opts['conda_cmd'] = args.conda_cmd
        else:
            if opts['ignore_mamba'] is True or which('mamba') is None:
                opts['conda_cmd'] = 'conda'
            else:
                opts['conda_cmd'] = 'mamba'

        # Make sure conda forge channel is available
        if args.uninstall is False:
            note('Checking for conda-forge')
            cmd_list=['info','--unsafe-channels']
            result = run_conda_cmd(cmd_list)

            if re.search(r'conda.*forge', result.stdout) is not None:
                sys_info['conda_forge_available'] = True
                note_ok()
            else:
                print(f'{yellow("WARNING")}: The conda-forge channel is not configured, cannot \
                        install conda packages. Falling back to building from source.')
                opts['compile_required'] = True

    opts['keep_build_dir'] = args.no_delete
    opts['force_build'] = args.force_build
    opts['fall_back'] = args.fall_back
    opts['check_sanity'] = not args.no_sanity_check
    opts['linear_solver'] = args.linear_solver
    if opts['linear_solver'] == 'pardiso':
        opts['intel_compiler_suite'] = True
    else:
        opts['intel_compiler_suite'] = args.intel

    opts['prefix'] = args.prefix
    opts['build_pyoptsparse'] = not args.no_install
    opts['pip_cmd'] = args.pip_cmd
    opts['snopt_dir'] = args.snopt_dir
    opts['hsl_tar_file'] = args.hsl_tar_file
    opts['verbose'] = args.verbose
    opts['uninstall'] = args.uninstall

def announce(msg:str):
    """
    Print an important message in color with a line above and below.

    Parameters
    ----------
    msg : str
        The information to be printed.
    """
    print(color(f' {msg} '.center(79, '-'), '#d0d0d0', 'blue'))

def note(msg:str):
    """
    Print a quick status message. If not in verbose mode, do not terminate with
    a newline because the result of the operation will print after.

    Parameters
    ----------
    msg : str
        The information to be printed.
    """
    if opts['verbose'] is False:
        print(msg, end="... ")
        sys.stdout.flush()
    else:
        print(msg + '...')

def note_ok():
    """ Print a green OK message to follow up a note() with. """
    if opts['verbose'] is False:
        print(green('OK'))

def note_failed():
    """ Print a red failure message to follow up a note() with. """
    if opts['verbose'] is False:
        print(red('failed'))

def code(msg:str)->str:
    """
    Create a message with "code" hilighting.

    Parameters
    ----------
    msg : str
        The information to be printed.
    """
    return color(msg, 'orange', style='underline')

def try_fallback(pkg:str, e:Exception):
    """
    When a conda package installation fails, this is called to print status info
    and determine whether it's possible to try building from source.

    Parameters
    ----------
    pkg : str
        The name of the package that failed to install.
    e : Exception
        That exception that was caught when the failure occurred.
    """

    note_failed()
    if opts['fall_back'] is True:
        print(yellow(f'Installing {pkg} with conda failed, falling back to source build.'))
    else:
        print(yellow('Use the --fall-back switch to build source on failed conda installs.'))
        raise e

def initialize():
    """ Perform a collection of setup tasks """
    global dir_stack
    dir_stack = []

    if conda_is_active() and (opts['ignore_conda'] is False):
        opts['prefix']=os.environ['CONDA_PREFIX']
        sys_info['conda_activate_dir'] = Path(opts['prefix']) / 'etc' / 'conda' / 'activate.d'
        sys_info['conda_deactivate_dir'] = Path(opts['prefix']) / 'etc' / 'conda' / 'deactivate.d'
    elif venv_is_active():
        opts['prefix']=os.environ['VIRTUAL_ENV']

def conda_is_active() -> bool:
    """ Determine if a conda environment is active. """
    return ('CONDA_PREFIX' in os.environ)

def allow_install_with_conda() -> bool:
    """ Determine if we can install with conda. """
    return conda_is_active() and (opts['ignore_conda'] is False) and \
           (sys_info['conda_forge_available'] is True)

def venv_is_active() -> bool:
    """ Determine if a Python virtual environment is active. """
    return ('VIRTUAL_ENV' in os.environ)

def subst_env_for_path(path:str)->str:
    """
    If a well-known env var is the initial part of the path, substitute the name
    of that var to make it easier to read.

    Parameters
    ----------
    path : str
        The path to check for environment variables.

    Returns
    -------
    str
        The possibly updated path.
    """

    if opts['verbose'] is True: return path

    for testvar in ['TMPDIR', 'TMP_DIR', 'TEMP_DIR', 'CONDA_PREFIX', 'VIRTUAL_ENV']:
        if testvar in os.environ and re.match(os.environ[testvar], path) is not None:
            new_path = PurePath(re.sub(os.environ[testvar], f'${testvar}/', path))
            return str(new_path)

    return path

def run_cmd(cmd_list, do_check=True, raise_error=True)->bool:
    """
    Run a command with provided arguments. Hide output unless there's an error
    or verbose mode is enabled.

    Parameters
    ----------
    cmd_list : list
        Each token of the command line is a separate member of the list.

    do_check : bool
        If true, test whether the process returns a non-zero status.

    raise_error: bool
        Only matters if do_check is true. If false, raise an exception
        if the process returns a non-zero status. If true, do not raise
        an exception, but have the function return False.

    Returns
    -------
    subprocess.CompletedProcess
        The result of the finished command.
    """
    result = None

    try:
        result = subprocess.run(cmd_list, check=do_check, capture_output=True, text=True)
    except subprocess.CalledProcessError as inst:
        if opts['verbose'] is True:
            print(inst.stdout, inst.stderr)
        if raise_error is True:
            raise inst

    if opts['verbose'] is True and result is not None:
        print(result.stdout, result.stderr)

    return result

def check_make(errors:list):
    """
    Find the best make command and test its viability.

    Parameters
    ----------
    errors : list
        Accumulated pre-check error messages.
    """

    if 'MAKE' in os.environ:
        opts['make_name'] = os.environ['MAKE']
    elif which('gmake') is not None:
        opts['make_name'] = 'gmake'

    if find_required_command(opts['make_name'], errors):
        # If the make command is found, test whether it's GNU make
        cmd_list=[opts['make_name'], '--version']
        result = subprocess.run(cmd_list, check=False, capture_output=True, text=True)

        if str(result.stdout).find('GNU Make') == -1:
            print(f'{yellow("WARNING")}: {opts["make_name"]} is not GNU Make. '
                  'Source code builds may fail.')

def make_install(parallel_procs:int=sys_info['compile_cores'], make_args = None, do_install=True):
    """
    Run 'make' followed by 'make install' in the current directory.

    Parameters
    ----------
    parallel_procs : int
        Start this many parallel make processes. Defaults to half of the system cores.
        Some packages fail when built in parallel, so 1 should be used in those cases.
    """
    note('Building')
    os.environ['MAKEFLAGS'] = f'-j {str(parallel_procs)}'
    make_cmd=[opts['make_name']]
    if make_args is not None:
        make_cmd.extend(make_args)
    run_cmd(cmd_list=make_cmd)
    note_ok()

    if do_install is True:
        note('Installing')
        run_cmd(cmd_list=[opts['make_name'],'install'])
        note_ok()

def run_conda_cmd(cmd_args):
    """
    Shorthand for performing a conda operation.

    Parameters
    ----------
    cmd_list : list
        Each token of the command line is a separate member of the list. The conda
        executable name is prepended, so should not be included in the list.

    Returns
    -------
    subprocess.CompletedProcess
        The result of the finished command.
    """
    cmd_list = [opts['conda_cmd']]
    cmd_list.extend(cmd_args)
    return run_cmd(cmd_list)

def pip_install(pip_install_args, pkg_desc='packages'):
    """
    Shorthand for performing a 'pip install' operation.

    Parameters
    ----------
    pip_install_args : list
        Each token of the command line is a separate member of the list. The
        is prepended with 'python -m pip install'; '-q' is added when not verbose.
    """
    cmd_list = opts['pip_cmd'].split() + ['install']
    if opts['verbose'] is False:
        cmd_list.append('-q')
    cmd_list.extend(pip_install_args)
    note(f'Installing {pkg_desc} with {opts["pip_cmd"]}')
    run_cmd(cmd_list)
    note_ok()

def install_conda_pkg(pkg_name:str):
    """
    Shorthand for performing a 'conda install' operation for a single package.

    Parameters
    ----------
    pkg_name : str
        The name of the package to install.
    """
    note(f'Installing {pkg_name.upper()} with conda')
    install_args = ['install', '-q', '-y', pkg_name]
    run_conda_cmd(cmd_args=install_args)
    note_ok()

def pushd(dirname):
    """
    Preserve the current directory name in a stack, then change to the specified directory.

    Parameters
    ----------
    dirname : str
        The absolute or relative name of the folder to change to.
    """
    dir_stack.append(str(Path.cwd()))
    os.chdir(dirname)
    print(f'Changed directory to {code(str(subst_env_for_path(dirname)))}')

def popd():
    """ Change to the top directory name on the stack of names. """
    dirname = dir_stack.pop()
    os.chdir(dirname)
    print(f'Changed directory back to {code(subst_env_for_path(dirname))}')

def get_coin_inc_dir()->str:
    """
    Determine what the path to the MUMPS/METIS/IPOPT include directory is, if it exists.

    Returns
    -------
    str
        The absolute path to the correct existing directory, or None if not found.
    """
    coin_inc_dirs = ['coin-or', 'coin']
    for coin_dir in coin_inc_dirs:
        coin_path = Path(opts["prefix"]) / 'include' / coin_dir
        if coin_path.is_dir():
            return str(coin_path)

    return None

def get_coin_lib_name(pkg:str)->str:
    """
    Determine whether the required lib starts with 'lib' or 'libcoin'.

    Parameters
    ----------
    pkg : str
        The name of the library to test.

    Returns
    -------
    str
        The pkg parameter prefaced with either 'coin' or nothing.
    """
    lib_vars = ['coin', '']

    for lv in lib_vars:
        lib_glob = f"lib{lv}{pkg}*"
        found_libs = sorted(Path(f"{opts['prefix']}/lib").glob(lib_glob))
        if len(found_libs) > 0:
            return f'{lv}{pkg}'

    return None

def git_clone(build_key:str, auto_delete:bool=True):
    """
    Create a temporary directory, change to it, and clone the repository associated
    with the specified package key.

    Parameters
    ----------
    build_key : str
        A key in the build_info dict with info about the selected package.
    auto_delete : bool
        Override the 'keep_build_dir' setting. Auto-delete if true, leave if false.

    Returns
    -------
    context manager OR str
        When the 'keep_build_dir' option is False, an object with info about the directory,
        which causes the directory to be cleaned up and removed when it goes out of scope.
        When the 'keep_build_dir' option is True, returns a str with the name of the folder.
    """
    d = build_info[build_key]
    announce(f'Building {build_key.upper()} from source code')
    if opts['keep_build_dir'] is True or auto_delete is False:
        build_dir = tempfile.mkdtemp()
        dir_name = build_dir
        print(f"Remember to delete {code(subst_env_for_path(dir_name))} afterwards.")
    else:
        build_dir = tempfile.TemporaryDirectory()
        dir_name = build_dir.name

    note(f'Cloning {d["url"]}')
    run_cmd(cmd_list=['git', 'clone', '-q', d['url'], dir_name])
    note_ok()
    pushd(dir_name)

    if d["branch"]:
        # We don't care about the "detached HEAD" warning:
        run_cmd(cmd_list=['git', 'config', '--local', 'advice.detachedHead', 'false'])
        note(f'Checking out branch {d["branch"]}')
        run_cmd(cmd_list=['git', 'checkout', '-q', d['branch']])

    return build_dir

def allow_build(build_key:str) -> bool:
    """
    Determine whether the specified package should be built from source.

    Parameters
    ----------
    build_key : str
        A key in the build_info dict with info about the selected package.

    Returns
    -------
    bool
        True if the package is not yet installed or force_build is true, false if already built.
    """
    coin_dir = get_coin_inc_dir()
    if coin_dir is None:
        build_ok = True
    else:
        d = build_info[build_key]
        include_file = Path(coin_dir) / d['include_subdir'] / d['include_file']
        build_ok = opts['force_build'] or not include_file.is_file()

    if build_ok is False:
        print(f"{build_key.upper()} is already installed under {opts['prefix']}, {yellow('skipping build')}.")

    return build_ok

def install_metis_from_src():
    """ Git clone the METIS repo, build the library, and install it and the include files. """
    if not allow_build('metis'):
        return

    metis_dir = git_clone('metis')
    os.environ['METIS_DIR'] = metis_dir if isinstance(metis_dir, str) else metis_dir.name

    run_cmd(['./get.Metis'])
    os.environ['CFLAGS'] = '-Wno-implicit-function-declaration'
    note("Running configure")
    run_cmd(cmd_list=['./configure', f'--prefix={opts["prefix"]}'])
    note_ok()
    make_install()
    popd()

def install_metis():
    """ Install METIS either through conda or building. """
    if allow_install_with_conda() and opts['force_build'] is False:
        try:
            install_conda_pkg('metis')
            os.environ['METIS_DIR'] = os.environ['CONDA_PREFIX']
            return
        except Exception as e:
            try_fallback('METIS', e)

    install_metis_from_src()

def get_common_solver_config_cmd():
    """ Gets common configuration options for Mumps and HSL solvers. """

    coin_dir = get_coin_inc_dir()
    cflags = f'-w -I{opts["prefix"]}/include -I{coin_dir} -I{coin_dir}/metis'
    fcflags = cflags
    if sys_info['gcc_major_ver'] >= 10:
        fcflags = '-fallow-argument-mismatch ' + fcflags

    metis_lib = get_coin_lib_name('metis')
    metis_lflags = f'-L{opts["prefix"]}/lib -l{metis_lib}'
    if platform.system() == "Linux":
        metis_lflags += ' -lm'

    config_opts = [
        '--with-metis',
        f'--with-metis-lflags={metis_lflags}',
        f'--with-metis-cflags={cflags}',
        f'--prefix={opts["prefix"]}',
        f'CFLAGS={cflags}',
        f'FCFLAGS={fcflags}'
    ]

    # Disable OpenMP support if we are on macOS building with Apple Clang.
    if sys_info['gcc_is_apple_clang']:
        config_opts.append('--disable-openmp')

    cnf_cmd_list = ['./configure']
    cnf_cmd_list.extend(config_opts)
    return cnf_cmd_list

def install_mumps_from_src():
    """ Git clone the MUMPS repo, build the library, and install it and the include files. """
    if not allow_build('mumps'):
        return

    build_dir = git_clone('mumps')
    run_cmd(['./get.Mumps'])

    cnf_cmd_list = get_common_solver_config_cmd()

    note("Running configure")
    run_cmd(cmd_list=cnf_cmd_list)
    note_ok()

    make_install(1) # MUMPS build can fail with parallel make
    popd()

def install_paropt_from_src():
    """
    Git clone the PAROPT repo, build the library, and install it and the include files.
    """
    build_dir = git_clone('paropt')

    # Use build defaults as per ParOpt instructions:
    Path('Makefile.in.info').rename('Makefile.in')
    make_vars =  [f'PAROPT_DIR={Path.cwd()}']
    if sys_info['sys_name'] == 'Darwin':
        make_vars.extend(['SO_EXT=dylib', 'SO_LINK_FLAGS=-fPIC -dynamiclib -undefined dynamic_lookup',
                          f'METIS_INCLUDE=-I{os.environ["METIS_DIR"]}/include/',
                          f'METIS_LIB=-L{os.environ["METIS_DIR"]}/lib/',
                          '-lmetis'])
    else:
        make_vars.extend(['SO_EXT=so', 'SO_LINK_FLAGS=-fPIC -shared',
                          f'METIS_INCLUDE=-I{os.environ["METIS_DIR"]}/include/',
                          f'METIS_LIB=-L{os.environ["METIS_DIR"]}/lib/',
                          '-lmetis'])

    make_install(make_args=make_vars, do_install=False)
    pip_install(['./'], pkg_desc='paropt')

    lib_dest_dir = str(Path(opts['prefix']) / 'lib')
    note(f'Copying library files to {code(subst_env_for_path(lib_dest_dir))}')
    lib_files = sorted(Path('lib').glob('libparopt*'))
    for lib in lib_files:
        shutil.copy2(str(lib), lib_dest_dir)
    note_ok()

    popd()

def install_ipopt_from_src(config_opts:list=None):
    """
    Git clone the IPOPT repo, build the library, and install it and the include files.

    Parameters
    ----------
    config_opts : list
        Additional options to use with the IPOPT configure script.
    """
    if not allow_build('ipopt') or opts['include_ipopt'] is False:
        return

    build_dir = git_clone('ipopt')
    cnf_cmd_list = ['./configure', f'--prefix={opts["prefix"]}', '--disable-java']

    # Don't accidentally use PARDISO if it wasn't selected:
    if opts['linear_solver'] != 'pardiso': cnf_cmd_list.append('--disable-pardisomkl')

    if config_opts is not None: cnf_cmd_list.extend(config_opts)
    note("Running configure")
    run_cmd(cmd_list=cnf_cmd_list)
    note_ok()
    make_install()
    popd()

def install_ipopt(config_opts:list=None):
    """
    Install IPOPT either through conda or building.

    Parameters
    ----------
    config_opts : list
        Additional options to use with the IPOPT configure script if building.
    """
    if opts['pyoptsparse_version'] >= parse('2.14'):
        pkg_path = os.environ['PKG_CONFIG_PATH'] + ':' if 'PKG_CONFIG_PATH' in os.environ else ''
        pkg_dir = Path(opts['prefix']) / 'lib' / 'pkgconfig'
        os.environ['PKG_CONFIG_PATH'] = pkg_path + str(pkg_dir)

    if allow_install_with_conda() and opts['force_build'] is False:
        try:
            install_conda_pkg('ipopt')
            if opts['pyoptsparse_version'] >= parse('2.14'):
                install_conda_pkg('cyipopt')
            return
        except Exception as e:
            try_fallback('IPOPT', e)

    install_ipopt_from_src(config_opts=config_opts)
    if opts['pyoptsparse_version'] >= parse('2.14'):
        pip_install(['cyipopt', '--use-pep517'], pkg_desc='cyipopt')

def install_mumps():
    """ Install MUMPS either through conda or building. """
    if allow_install_with_conda() and opts['force_build'] is False:
        try:
            install_conda_pkg('mumps-include')
            install_conda_pkg('mumps-seq')
            install_conda_pkg('mumps-mpi')
            return
        except Exception as e:
            try_fallback('MUMPS', e)

    install_mumps_from_src()

def install_with_mumps():
    """ Install METIS, MUMPS, and IPOPT. """
    install_metis()
    install_mumps()

    if opts['include_ipopt'] is True:
        # Get this info in case we need to build IPOPT from source
        coin_dir = get_coin_inc_dir()

        mumps_lib = get_coin_lib_name('mumps')
        ipopt_opts = [
            '--with-mumps',
            f'--with-mumps-lflags=-L{opts["prefix"]}/lib -l{mumps_lib}',
            f'--with-mumps-cflags=-I{coin_dir}/mumps',
            '--without-asl',
            '--without-hsl'
        ]

        install_ipopt(config_opts=ipopt_opts)

def install_hsl_from_src():
    """ Build HSL from the user-supplied source tar file. """
    if not allow_build('hsl'):
        return

    build_dir = git_clone('hsl')

    # Extract the HSL tar file and rename the folder to 'coinhsl'
    # First, determine the name of the top-level folder:
    with tarfile.open(opts['hsl_tar_file'], 'r') as tf:
        hsl_dir_name = tf.getnames()[0]
    run_cmd(cmd_list=['tar', 'xf', opts['hsl_tar_file']]) # Extract
    Path(hsl_dir_name).rename('coinhsl') # Rename

    cnf_cmd_list = get_common_solver_config_cmd()

    note("Running configure")
    run_cmd(cmd_list=cnf_cmd_list)
    note_ok()
    make_install()
    popd()

def install_with_hsl():
    """ Install pyOptSparse using the HSL linear solver """
    install_metis()
    install_hsl_from_src()

    coin_dir = get_coin_inc_dir()
    metis_lib = get_coin_lib_name('metis')
    ipopt_opts = [
        '--with-hsl',
        f'--with-hsl-lflags=-L{opts["prefix"]}/lib -lcoinhsl -l{metis_lib}',
        f'--with-hsl-cflags=-I{coin_dir}/hsl',
        '--disable-linear-solver-loader'
    ]
    install_ipopt_from_src(config_opts=ipopt_opts)
    install_pyoptsparse_from_src()

def install_with_pardiso():
    """ Build IPOPT with the PARDISO linear solver. """
    # install_ipopt_from_src(config_opts=['--with-lapack=-mkl'])
    install_ipopt_from_src()

    # pyOptSparse doesn't do well with Intel compilers, so unset:
    # select_gnu_compiler()

    install_pyoptsparse_from_src()

def copy_snopt_files(build_dirname):
    """
    Copy SNOPT source files into the pyOptSparse build dir, excluding snopth.f.

    Parameters
    ----------
    build_dirname : str
        The directory where pyOptSparse is being built/installed from.
    """
    note('Copying SNOPT source files')
    snoptc_f_list = sorted(Path(opts['snopt_dir']).rglob('snoptc.f'))
    all_snopt_files = sorted(Path(snoptc_f_list[0]).parent.glob('*'))

    dest_dir = str(Path(build_dirname) / 'pyoptsparse' / 'pySNOPT' / 'source')

    exclude_snopth_f = re.compile('.*snopth.f')
    for sfile in all_snopt_files:
        src_file = str(sfile)
        # copy source files, exclude any directories (e.g. f2py/)
        if not exclude_snopth_f.match(src_file) and not sfile.is_dir():
            shutil.copy2(src_file, dest_dir)

    note_ok()

def patch_pyoptsparse_src():
    """ Some versions of pyOptSparse need to be modified slightly to build correctly. """

    if opts['pyoptsparse_version'] < parse('2.6.3'):
        pushd("pyoptsparse/pyIPOPT")
        note("Patching for versions < 2.6.3")

        setup_py_path = Path("setup.py")
        pos_setup_py = open(str(setup_py_path))
        data = pos_setup_py.read()
        pos_setup_py.close()
        setup_py_path.rename('setup.py.orig')

        new_data = re.sub(r'libraries=.+,', 'libraries=["ipopt"],', data)

        with open(str(setup_py_path), 'w') as setup_py_path:
            setup_py_path.write(new_data)

        note_ok()
        popd()

def install_pyoptsparse_from_src():
    """ Git clone the pyOptSparse repo and use pip to install it. """
    pip_install(['Cython'], pkg_desc='Cython')

    # First, build PAROPT if selected:
    if opts['include_paropt'] is True:
        install_paropt_from_src()

    build_dir = git_clone('pyoptsparse', opts['build_pyoptsparse'])

    if opts['include_ipopt'] is True:
        os.environ['IPOPT_INC'] = get_coin_inc_dir()
        os.environ['IPOPT_LIB'] = str(Path(opts["prefix"]) / 'lib')
        os.environ['IPOPT_DIR'] = str(Path(opts["prefix"]))
    os.environ['CFLAGS'] = '-Wno-implicit-function-declaration -std=c99'

    # Pull in SNOPT source:
    if opts['snopt_dir'] is not None:
        build_dir_str = build_dir if isinstance(build_dir, str) else build_dir.name
        copy_snopt_files(build_dir_str)

    if opts['build_pyoptsparse'] is True:
        patch_pyoptsparse_src()
        pip_install(pip_install_args=['--no-cache-dir', './'], pkg_desc='pyoptsparse')
    else:
        announce('Not building pyOptSparse by request')
        if opts['include_ipopt'] is True:
            print(f"""
Make sure to set these environment variables before building it yourself:

{code(f'export IPOPT_INC={subst_env_for_path(os.environ["IPOPT_INC"])}')}
{code(f'export IPOPT_LIB={subst_env_for_path(os.environ["IPOPT_LIB"])}')}
                   """)

    popd()

def uninstall_built_item(build_key:str):
    """ Uninstall a specific item that was previously built from source code. """
    d = build_info[build_key]

    if 'include_subdir' in d:
        inc_dir = Path(opts['prefix']) / 'include' / 'coin-or' / d['include_subdir']
        if 'include_glob_list' in d:
        # If there's a list of glob patterns, remove found files individually instead
        # of removing an entire include subdirectory:
            note(f'Removing {build_key.upper()} include files')

            for glob_item in d['include_glob_list']:
                for inc_file in sorted(Path(inc_dir).glob(glob_item)):
                    Path(inc_file).unlink()

            try:
                inc_dir.rmdir()
            except:
                pass

            note_ok()
        else:
        # If there's no chance that other include files will be installed in the same
        # folder, just remove the whole subdirectory.
            if inc_dir.is_dir():
                note(f'Removing {build_key.upper()} include directory')
                shutil.rmtree(inc_dir)
                note_ok()

    # Remove individual library files.
    if 'src_lib_glob' in d:
        lib_dir = Path(opts['prefix']) / 'lib'
        lib_file_list = sorted(lib_dir.glob(d['src_lib_glob']))
        if len(lib_file_list) > 0:
            note(f'Removing {build_key.upper()} library files')
            for lib_file in lib_file_list:
                Path(lib_file).unlink()
            note_ok()

def uninstall_paropt_and_pyoptsparse():
    """ Both ParOpt and pyOptSparse were installed with pip. """
    # Uninstall pyOptSparse
    note('Removing pyOptSparse')
    run_cmd(cmd_list=['pip','uninstall','-y','pyOptSparse'], do_check=False)
    note_ok()

    note('Removing PAROPT package')
    run_cmd(cmd_list=['pip','uninstall','-y','paropt'], do_check=False)
    note_ok()
    uninstall_built_item('paropt')

def remove_conda_scripts():
    """ Remove the conda activate/deactivate scripts if they exist. """
    if conda_is_active() and opts['ignore_conda'] is False:
        note("Removing conda activate/deactivate scripts")
        act_path = Path(sys_info['conda_activate_dir']) / sys_info['conda_env_script']
        if act_path.is_file(): act_path.unlink()

        deact_path = Path(sys_info['conda_deactivate_dir']) / sys_info['conda_env_script']
        if deact_path.is_file(): deact_path.unlink()
        note_ok()

def uninstall_built():
    """ Attempt to remove files that were previously installed when building from source. """
    uninstall_paropt_and_pyoptsparse()

    for build_key in ['ipopt', 'hsl', 'mumps', 'metis']:
        uninstall_built_item(build_key)

    if opts['ignore_conda'] is False: remove_conda_scripts()

def uninstall_conda_pkgs():
    """ Attempt to remove packages previously installed by conda. """

    if conda_is_active():
        for pkg in ['ipopt','mumps','mumps-include','mumps-seq','mumps-mpi','metis']:
            note(f"Removing {pkg.upper()} conda package")
            run_cmd(cmd_list=[opts['conda_cmd'],'uninstall','-y',pkg], do_check=False)
            note_ok()

def display_environment():
    announce("Relevant environment variables")
    for ev in ['CONDA_PREFIX','VIRTUAL_ENV','TMPDIR','TMP_DIR','TEMP_DIR']:
        if ev in os.environ:
            print(f'{cyan(ev)}: {code(os.environ[ev])}')

def check_library(libname:str, raise_on_failure=True):
    """
    Determine whether the specified library is available for linking.

    Parameters
    ----------
    libname : str
        The name of the library without the preceding 'lib' or '.a/.so.*/.dll' extension.
    """

    build_dir = tempfile.TemporaryDirectory()
    pushd(build_dir.name)

    note(f'Checking for library: {libname}')
    with open('hello.c', 'w', encoding="utf-8") as f:
        f.write('#include <stdio.h>\nint main() {\nprintf("cc works!\\n");\nreturn 0;\n}\n')

    result = run_cmd(cmd_list=[os.environ['CC'], '-o', 'hello_c', 'hello.c', f'-l{libname}'],
                    raise_error=False)

    success = (result is not None and result.returncode == 0)
    if success is True:
        note_ok()
    else:
        print(red('not found'))
        if raise_on_failure is True:
            raise RuntimeError(f'Cannot continue without {libname} library.')

    popd()

    return success

def check_compiler_sanity():
    """ Build and run programs written in C, C++, and FORTRAN to test the compilers. """
    build_dir = tempfile.TemporaryDirectory()
    pushd(build_dir.name)

    note(f'Testing {os.environ["CC"]}')
    with open('hello.c', 'w', encoding="utf-8") as f:
        f.write('#include <stdio.h>\nint main() {\nprintf("cc works!\\n");\nreturn 0;\n}\n')

    run_cmd(cmd_list=[os.environ['CC'], '-o', 'hello_c', 'hello.c'])
    run_cmd(cmd_list=['./hello_c'])
    note_ok()

    note(f'Testing {os.environ["CXX"]}')
    with open('hello.cc', 'w', encoding="utf-8") as f:
        f.write('#include <iostream>\nint main() {\nstd::cout << "c++ works!" << std::endl;\nreturn 0;\n}\n')

    run_cmd(cmd_list=[os.environ['CXX'], '-o', 'hello_cxx', 'hello.cc'])
    run_cmd(cmd_list=['./hello_cxx'])
    note_ok()

    if opts['include_paropt']:
        note(f'Testing mpicxx')
        run_cmd(cmd_list=['mpicxx', '-o', 'hello_cxx_mpi', 'hello.cc'])
        run_cmd(cmd_list=['./hello_cxx_mpi'])
        note_ok()

    note(f'Testing {os.environ["FC"]}')
    with open('hello.f90', 'w', encoding="utf-8") as f:
        f.write("program hello\n  print *, 'fortran works!'\nend program hello")

    run_cmd(cmd_list=[os.environ['FC'], '-o', 'hello_f', 'hello.f90'])
    run_cmd(cmd_list=['./hello_f'])
    note_ok()

    popd()

def find_required_command(cmd:str, errors:list):
    """
    Determine if the command name is in the PATH.

    Parameters
    ----------
    cmd : str
        The name of the command to look for.
    errors : list
        Accumulated pre-check error messages.
    """
    cmd_path = which(cmd)
    if cmd_path is None:
        errors.append(f"{red('ERROR')}: Required command {yellow(cmd)} not found.")
        return False
    elif opts['verbose'] is True:
        print(f"{green('FOUND')}: {cmd} is {cmd_path}")

    return True

def check_sanity():
    """ Determine if all the required commands are there and can build if necessary. """
    announce("Testing build environment functionality. Can be skipped with -k.")

    errors = []
    required_cmds = []

    print(f'Using {code(subst_env_for_path(opts["prefix"]))} for install prefix')

    if conda_is_active() and (opts['ignore_conda'] is False):
        cpre = os.environ['CONDA_PREFIX']
        if re.search('intelpython', cpre) is not None:
            print(f"""
{yellow("WARNING")}: $CONDA_PREFIX points to:
{' ' * 9 + code(cpre)}
This is associated with Intel OneAPI and may cause the installation to fail.
If it does, set up Intel OneAPI {yellow('before')} activating your conda env.
"""[1:])

    if opts['compile_required'] is True or opts['fall_back'] is True:
        check_make(errors)
        required_cmds.extend(['git', os.environ['CC'], os.environ['CXX'], os.environ['FC']])
        if opts['build_pyoptsparse'] is True:
            required_cmds.extend(['swig'])

    if opts['compile_required'] is False:
        required_cmds.append(opts['conda_cmd'])

    if opts['hsl_tar_file'] is not None:
        required_cmds.append('tar')
        if not Path(opts['hsl_tar_file']).is_file():
            errors.append(f"{red('ERROR')}: HSL tar file {yellow(opts['hsl_tar_file'])} does not exist.")

    if opts['include_paropt'] is True:
        required_cmds.append('mpicxx')
        if opts['pyoptsparse_version'] < parse('2.1.2'):
            errors.append(f"{red('ERROR')}: PAROPT is only supported by pyOptSparse {yellow('v2.1.2')} or newer.")

    if opts['snopt_dir'] is not None:
        if not Path(opts['snopt_dir']).is_dir():
            errors.append(f"{red('ERROR')}: SNOPT folder {yellow(opts['snopt_dir'])} does not exist.")

    for cmd in required_cmds:
        find_required_command(cmd, errors)

    if len(errors) > 0:
        for err in errors:
            print(err)

        exit(1)

    if opts['compile_required'] is True or opts['fall_back'] is True:
        check_compiler_sanity()
        check_library('lapack')
        check_library('blas')

        if opts['build_pyoptsparse'] is True:
            if check_library('openblas', raise_on_failure=False) is False:
                print(f"{yellow('WARNING')}: openblas missing. Required to build scipy on uncommon platforms.")

def select_intel_compilers():
    """ Set environment variables to use Intel compilers. """
    os.environ['CC'] = os.environ.get('CC', 'icc')
    os.environ['CXX'] = os.environ.get('CXX', 'icpc')
    os.environ['FC'] = os.environ.get('FC', 'ifort')
    sys_info['gcc_major_ver'] = -1
    sys_info['gcc_is_apple_clang'] = False

def select_gnu_compilers():
    """ Set environment variables to use GNU compilers. """
    os.environ['CC'] = os.environ.get('CC', 'gcc')
    os.environ['CXX'] = os.environ.get('CXX', 'g++')
    os.environ['FC'] = os.environ.get('FC', 'gfortran')
    gcc_ver = subprocess.run(['gcc', '-dumpversion'], capture_output=True)
    sys_info['gcc_major_ver'] = int(gcc_ver.stdout.decode('UTF-8').split('.')[0])
    gcc_version = subprocess.run(['gcc', '--version'], capture_output=True)
    sys_info['gcc_is_apple_clang'] = 'Apple clang' in gcc_version.stdout.decode('UTF-8')

def finish_setup():
    """ Finalize settings based on provided options and environment state. """
    if opts['intel_compiler_suite'] is True:
        select_intel_compilers()
    else:
        select_gnu_compilers()

    # Determine whether any compiling will actually be performed
    opts['compile_required'] = opts['build_pyoptsparse'] is True or \
                not (allow_install_with_conda() and opts['snopt_dir'] is None and \
                opts['include_paropt'] is False and opts['hsl_tar_file'] is None)

    # Set an option with the parsed pyOptSparse version
    pos_ver_str = build_info['pyoptsparse']['branch']
    if pos_ver_str[:1] == 'v': pos_ver_str = pos_ver_str[1:] # Drop the initial v
    opts['pyoptsparse_version'] = parse(pos_ver_str)

    # Change snopt_dir to an absolute path
    if opts['snopt_dir'] is not None:
        opts['snopt_dir'] = str(Path(opts['snopt_dir']).resolve())

    if opts['hsl_tar_file'] is not None:
        opts['hsl_tar_file'] = str(Path(opts['hsl_tar_file']).resolve())

    display_environment()

    if opts['check_sanity']:
        check_sanity()

def install_conda_scripts(var_name:str, lib_dir:Path):
    """
    Create conda activate/deactivate scripts to set dynamic linker search path.

    Parameters
    ----------
    var_name : str
        The name of the dynamic linker environment variable.
    lib_dir : Path
        The location of the shared library files.
    """
    bash_path = which('bash')

    sys_info['conda_activate_dir'].mkdir(parents=True, exist_ok=True)
    act_file_name = str(sys_info['conda_activate_dir'] / sys_info['conda_env_script'])
    with open(act_file_name, 'w', encoding="utf-8") as f:
        f.write(
f"""#!{bash_path}
if [ -z "${var_name}" ]; then
    export {var_name}="{str(lib_dir)}"
else
    # Preserve previous settings
    export OLD_{var_name}="${var_name}"
    export {var_name}="{str(lib_dir)}:${var_name}"
fi
""")

    sys_info['conda_deactivate_dir'].mkdir(parents=True, exist_ok=True)
    deact_file_name = str(sys_info['conda_deactivate_dir'] / sys_info['conda_env_script'])
    with open(deact_file_name, 'w', encoding="utf-8") as f:
        f.write(
f"""#!{bash_path}
if [ -z "$OLD_{var_name}" ]; then
    unset {var_name}
else
    # Restore previous setting
    {var_name}="$OLD_{var_name}"
    unset OLD_{var_name}
fi
""")

    print(
f"""Your {cyan(os.environ['CONDA_DEFAULT_ENV'])} conda environment has been updated to automatically
set the {yellow(var_name)} environment variable when activated.

This setting is found in the following files:
{code(subst_env_for_path(act_file_name))}
{code(subst_env_for_path(deact_file_name))}

Run {code(f'source {subst_env_for_path(act_file_name)}')} to set it now.
""")

def post_build_success():
    """ Announce successful build and print some instructions. """
    announce("The pyOptSparse build is complete")

    lib_dir = Path(opts['prefix']) / 'lib'
    if sys_info['sys_name'] == 'Darwin':
        var_name = 'DYLD_LIBRARY_PATH'
    else:
        var_name = 'LD_LIBRARY_PATH'

    if allow_install_with_conda():
        install_conda_scripts(var_name, lib_dir)
    else:
        if opts['include_ipopt'] is True:
            print(
f"""{yellow('NOTE')}: Set the following environment variable before using this installation:

{code(f'export {var_name}={subst_env_for_path(str(lib_dir))}')}

Otherwise, you may encounter errors such as:
 "pyOptSparse Error: There was an error importing the compiled IPOPT module"
""")

    announce('SUCCESS!')
    exit(0)

def perform_install():
    """ Initiate all the required actions in the script. """
    process_command_line()
    initialize()

    if opts['uninstall']:
        announce('Uninstalling pyOptSparse and related packages')
        print(f'{yellow("NOTE:")} Some items may be listed even if not installed.')
        if opts['ignore_conda'] is False: uninstall_conda_pkgs()
        uninstall_built()
        exit(0)

    finish_setup()

    announce('Beginning installation')

    if opts['linear_solver'] == 'mumps':
        install_with_mumps()
        install_pyoptsparse_from_src()
    elif opts['linear_solver'] == 'pardiso':
        install_with_pardiso()
    elif opts['linear_solver'] == 'hsl':
        install_with_hsl()

    post_build_success()

if __name__ == "__main__":
    perform_install()
