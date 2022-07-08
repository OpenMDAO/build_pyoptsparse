#!/usr/bin/env python
import argparse
import os
import sys
import subprocess
from pathlib import Path, PurePath
import tempfile
from colors import *
from shutil import which

# Default options that the user can change with command line switches
opts = {
    'prefix': str(Path(Path.home() / 'ipopt')),
    'linear_solver': 'mumps',
    'build_pyoptsparse': True,
    'intel_compiler_suite': False,
    'snopt_dir': None,
    'hsl_tar_file': None,
    'include_paropt': False,
    'keep_build_dir': False,
    'check_sanity': True,
    'conda_cmd': 'conda',
    'force_rebuild': False,
    'ignore_conda': False,
    'verbose': False
}

# Information about the host, status, and constants
sys_info = {
    'gcc_major_ver': -1,
    'line_color': 'white',
    'msg_color': 'gray',
    'gnu_sanity_check_done': False,
    'python_sanity_check_done': False,
    'compile_cores': int(os.cpu_count()/2),
}

# Where to find each package, which branch to use if obtained by git,
# and which include file to test to see if it's already installed
build_info = {
    'metis': {
        'branch': 'stable/2.0',
        'url': 'https://github.com/coin-or-tools/ThirdParty-Metis.git',
        'include_check': PurePath('metis', 'metis.h')
    },
    'mumps': {
        'branch': 'stable/3.0',
        'url': 'https://github.com/coin-or-tools/ThirdParty-Mumps.git',
        'include_check': PurePath('mumps', 'mumps_c_types.h')
    },
    'ipopt': {
        'branch': 'stable/3.14',
        'url': 'https://github.com/coin-or/Ipopt.git',
        'include_check': PurePath('IpoptConfig.h')
    },
    'pyoptsparse': {
        'branch': 'v2.8.3',
        'url': 'https://github.com/mdolab/pyoptsparse.git',
    },
    'hsl': {
        'branch': 'stable/2.2',
        'url': 'https://github.com/coin-or-tools/ThirdParty-HSL',
    }
}

def announce(msg):
    print("%s\n%s\n%s" %(LINE, color(msg, sys_info['msg_color']), LINE))

def note(msg):
    if opts['verbose'] is False:
        print(msg, end="... ")
        sys.stdout.flush()
    else:
        print(msg)

def note_ok():
    if opts['verbose'] is False:
        print(green('OK'))

def initialize():
    """ Perform a collection of setup tasks """
    global dir_stack
    dir_stack = []

    if conda_is_active():
        opts['prefix']=os.environ['CONDA_PREFIX']
    elif venv_is_active():
        opts['prefix']=os.environ['VIRTUAL_ENV']

    global LINE
    LINE = color('=' * 78, fg=sys_info['line_color'])

def conda_is_active():
    return ('CONDA_PREFIX' in os.environ)

def allow_install_with_conda():
    return conda_is_active() and not opts['ignore_conda']

def venv_is_active():
    return ('VIRTUAL_ENV' in os.environ)

def run_cmd(cmd_list):
    """ Run a command with provided arguments. Hide output unless there's an error. """
    if opts['verbose'] is False:
        subprocess.run(cmd_list, check=True, capture_output=True)
    else:
        subprocess.run(cmd_list, check=True)

def make_install(parallel_procs:int=sys_info['compile_cores']):
    note('Building')
    os.environ['MAKEFLAGS'] = f'-j {str(parallel_procs)}'
    run_cmd(cmd_list=['make'])
    note_ok()

    note('Installing')
    run_cmd(cmd_list=['make','install'])
    note_ok()

def run_conda_cmd(cmd_args):
    cmd_list = [opts['conda_cmd']]
    cmd_list.extend(cmd_args)
    run_cmd(cmd_list)

def pip_install(pip_install_args):
    cmd_list = ['python', '-m', 'pip', 'install', '-q']
    cmd_list.extend(pip_install_args)
    note('Installing packages with pip')
    run_cmd(cmd_list)
    note_ok()

def install_conda_pkg(pkg_name:str):
    announce(f'Installing {pkg_name.upper()} with conda')
    install_args = ['install', '-y', pkg_name]
    run_conda_cmd(cmd_args=install_args)
    print("Done!")

def bkp_dir(dirname):
    if Path(dirname).is_dir():
        new_dirname = f"{dirname}.bkp.{sys_info['time']}"
        print(f"Renaming {dirname} to {new_dirname}")
        Path(dirname).rename(new_dirname)

def pushd(dirname):
    dir_stack.append(str(Path.cwd()))
    os.chdir(dirname)
    print(f'Changed directory to {str(blue(Path.cwd()))}')

def popd():
    dirname = dir_stack.pop()
    os.chdir(dirname)
    print(f'Changed directory back to {blue(dirname)}')

def get_coin_inc_dir()->str:
    coin_inc_dirs = ['coin-or', 'coin']
    for coin_dir in coin_inc_dirs:
        coin_path = Path(opts["prefix"]) / 'include' / coin_dir
        if coin_path.is_dir():
            return str(coin_path)

    return None

def git_clone(build_key:str):
    d = build_info[build_key]
    announce(f'Building {build_key.upper()} from source code')
    if opts['keep_build_dir'] is True:
        build_dir = tempfile.mkdtemp()
        dir_name = build_dir
        print(f"Remember to delete {blue(dir_name)} afterwards.")
    else:
        build_dir = tempfile.TemporaryDirectory()
        dir_name = build_dir.name

    note(f'Cloning {d["url"]}')
    run_cmd(cmd_list=['git', 'clone', '-q', d['url'], dir_name])
    note_ok()
    pushd(dir_name)

    # We don't care about the "detached HEAD" warning:
    run_cmd(cmd_list=['git', 'config', '--local', 'advice.detachedHead', 'false'])
    run_cmd(cmd_list=['git', 'checkout', '-q', d['branch']])
    return build_dir

def allow_build(build_key:str) -> bool:
    coin_dir = get_coin_inc_dir()
    if coin_dir is None:
        build_ok = True
    else:
        include_file = Path(PurePath(coin_dir, build_info[build_key]['include_check']))
        build_ok = opts['force_rebuild'] or not include_file.is_file()

    if build_ok is False:
        print(f"{build_key.upper()} is already installed under {opts['prefix']}, {yellow('skipping build')}.")

    return build_ok

def install_metis_from_src():
    if not allow_build('metis'):
        return

    build_dir = git_clone('metis')
    run_cmd(['./get.Metis'])
    os.environ['CFLAGS'] = '-Wno-implicit-function-declaration'
    note("Running configure")
    run_cmd(cmd_list=['./configure', f'--prefix={opts["prefix"]}'])
    note_ok()
    make_install()
    popd()

def install_metis():
    if allow_install_with_conda():
        install_conda_pkg('metis')
    else:
        install_metis_from_src()

def install_mumps_from_src():
    if not allow_build('mumps'):
        return

    build_dir = git_clone('mumps')
    run_cmd(['./get.Mumps'])
    coin_dir = get_coin_inc_dir()
    cflags = f'-w -I{opts["prefix"]}/include -I{coin_dir} -I{coin_dir}/metis'
    fcflags = cflags
    if sys_info['gcc_major_ver'] >= 10:
        fcflags = '-fallow-argument-mismatch ' + fcflags

    config_opts = [
        '--with-metis',
        f'--with-metis-lflags=-L{opts["prefix"]}/lib -lcoinmetis',
        f'--with-metis-cflags={cflags}',
        f'--prefix={opts["prefix"]}',
        f'CFLAGS={cflags}',
        f'FCFLAGS={fcflags}'
    ]
    cnf_cmd_list = ['./configure']
    cnf_cmd_list.extend(config_opts)

    note("Running configure")
    run_cmd(cmd_list=cnf_cmd_list)
    note_ok()
    make_install(1)
    popd()

def install_ipopt_from_src(config_opts):
    if not allow_build('ipopt'):
        return

    build_dir = git_clone('ipopt')
    cnf_cmd_list = ['./configure', f'--prefix={opts["prefix"]}', '--disable-java']
    cnf_cmd_list.extend(config_opts)
    note("Running configure")
    run_cmd(cmd_list=cnf_cmd_list)
    note_ok()
    make_install()
    popd()

def install_with_mumps():
    install_metis()
    if allow_install_with_conda():
        install_conda_pkg('mumps')
        install_conda_pkg('ipopt')
    else:
        install_mumps_from_src()
        coin_dir = get_coin_inc_dir()
        ipopt_opts = [
            '--with-mumps',
            f'--with-mumps-lflags=-L{opts["prefix"]}/lib -lcoinmumps',
            f'--with-mumps-cflags=-I{coin_dir}/mumps',
            '--without-asl',
            '--without-hsl'
        ]
        install_ipopt_from_src(config_opts=ipopt_opts)

def install_pyoptsparse_from_src():
    pip_install(pip_install_args=['numpy','sqlitedict'])
    build_dir = git_clone('pyoptsparse')

    os.environ['IPOPT_INC'] = get_coin_inc_dir()
    os.environ['IPOPT_LIB'] = f'{opts["prefix"]}/lib'
    os.environ['CFLAGS'] = '-Wno-implicit-function-declaration -std=c99'
    pip_install(pip_install_args=['--no-cache-dir', './'])
    popd()

def install_pyoptsparse():
    if allow_install_with_conda() and opts['snopt_dir'] is None:
        install_conda_pkg('pyoptsparse')
    else:
        install_pyoptsparse_from_src()

def check_compiler_sanity():
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

    note(f'Testing {os.environ["FC"]}')
    with open('hello.f90', 'w', encoding="utf-8") as f:
        f.write("program hello\n  print *, 'fortran works!'\nend program hello")

    run_cmd(cmd_list=[os.environ['FC'], '-o', 'hello_f', 'hello.f90'])
    run_cmd(cmd_list=['./hello_f'])
    note_ok()

    popd()

def check_sanity():
    announce("Testing build environment functionality. Can be skipped with -k.")

    errors = []

    required_cmds=[
        'make',
        os.environ['CC'],
        os.environ['CXX'],
        os.environ['FC'],
        'git'
    ]

    if opts['build_pyoptsparse'] is True:
        required_cmds.extend(['pip', 'swig'])

    if opts['hsl_tar_file'] is not None:
        required_cmds.append('tar')
        if not Path(opts['hsl_tar_file']).is_file():
            errors.append(f"{red('ERROR')}: HSL tar file {yellow(opts['hsl_tar_file'])} does not exist.")

    if opts['include_paropt'] is True:
        required_cmds.append('mpicxx')

    if opts['snopt_dir'] is not None:
        if not Path(opts['snopt_dir']).is_dir():
            errors.append(f"{red('ERROR')}: SNOPT folder {yellow(opts['snopt_dir'])} does not exist.")

    for cmd in required_cmds:
        cmd_path = which(cmd)
        if cmd_path is None:
            errors.append(f"{red('ERROR')}: Required command {yellow(cmd)} not found.")
        elif opts['verbose'] is True:
            print(f"{green('FOUND')}: {cmd} is {cmd_path}")

    check_compiler_sanity()

    if len(errors) > 0:
        for err in errors:
            print(err)

        exit(1)

def process_command_line():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='''
    Download, configure, build, and/or install pyOptSparse with IPOPT support and
    dependencies. Temporary working directories are created, which are removed
    after installation unless -d is used.
            ''',
        epilog='''
    NOTES:
    When using HSL as the linear solver, the source code tar file can be obtained
    from http://www.hsl.rl.ac.uk/ipopt/
    If PARDISO is selected as the linear solver, the Intel compiler suite with MKL
    must be available.

    Examples:
    build_pyoptsparse.py
    build_pyoptsparse.py -l pardiso
    build_pyoptsparse.py -l hsl -n -t ../../coinhsl-archive-2014.01.17.tar.gz
    '''
    )
    parser.add_argument("-a", "--paropt",
                        help="Add ParOpt support. Default: no ParOpt",
                        action="store_true",
                        default=opts['include_paropt'])
    parser.add_argument("-b", "--branch",
                        help=f"pyOptSparse git branch. \
                        Default: {build_info['pyoptsparse']['branch']}",
                        default=build_info['pyoptsparse']['branch'])
    parser.add_argument("-c", "--conda-cmd",
                        help=f"Command to install packages with if conda is used. \
                            Default: {opts['conda_cmd']}",
                        default=opts['conda_cmd'])
    parser.add_argument("-d", "--no-delete",
                        help="Do not erase the build directories after completion.",
                        action="store_true",
                        default=opts['keep_build_dir'])
    parser.add_argument("-e", "--ignore-conda",
                        help="Build from source even if conda is found.",
                        action="store_true",
                        default=opts['ignore_conda'])
    parser.add_argument("-f", "--force-rebuild",
                        help="If building a package from source, \
                              rebuild even if it's found to be installed.",
                        action="store_true",
                        default=opts['force_rebuild'])
    parser.add_argument("-k", "--no-sanity-check",
                        help="Skip the sanity checks.",
                        action="store_true",
                        default=not opts['check_sanity'])
    parser.add_argument("-i", "--intel",
                        help="Use the Intel compiler suite instead of GNU.",
                        action="store_true",
                        default=opts['intel_compiler_suite'])
    parser.add_argument("-l", "--linear-solver",
                        help="Which linear solver to expect. Default: mumps",
                        choices=['mumps', 'hsl', 'pardiso'],
                        default=opts['linear_solver'])
    parser.add_argument("-n", "--no-install",
                        help="Prepare, but do NOT build/install pyOptSparse itself. \
                              Default: install",
                        action="store_true",
                        default=not opts['build_pyoptsparse'])
    parser.add_argument("-p", "--prefix",
                        help=f"Where to install. Default: {opts['prefix']}",
                        default=opts['prefix'])
    parser.add_argument("-s", "--snopt-dir",
                        help="Include SNOPT from SNOPT-DIR. Default: no SNOPT",
                        default=opts['snopt_dir'])
    parser.add_argument("-t", "--hsl-tar-file",
                        help="If HSL is the linear solver, use this as the path \
                        to the tar file of the HSL source. \
                        E.g. -t ../../coinhsl-archive-2014.01.17.tar.gz",
                        default=opts['hsl_tar_file'])
    parser.add_argument("-v", "--verbose",
                        help="Show output from git, configure, make, etc.",
                        action="store_true",
                        default=opts['verbose'])

    args = parser.parse_args()

    # Update options with user selections
    opts['include_paropt'] = args.paropt
    build_info['pyoptsparse']['branch'] = args.branch
    opts['conda_cmd'] = args.conda_cmd
    opts['keep_build_dir'] = args.no_delete
    opts['ignore_conda'] = args.ignore_conda
    opts['force_rebuild'] = args.force_rebuild
    opts['check_sanity'] = not args.no_sanity_check
    opts['linear_solver'] = args.linear_solver
    if opts['linear_solver'] == 'pardiso':
        opts['intel_compiler_suite'] = True
    else:
        opts['intel_compiler_suite'] = args.intel

    opts['prefix'] = args.prefix
    opts['build_pyoptsparse'] = not args.no_install
    opts['snopt_dir'] = args.snopt_dir
    opts['hsl_tar_file'] = args.hsl_tar_file
    opts['verbose'] = args.verbose

def finish_setup():
    if opts['intel_compiler_suite'] is True:
        os.environ['CC'] = 'icc'
        os.environ['CXX'] = 'icpc'
        os.environ['FC'] = 'ifort'
    else:
        os.environ['CC'] = 'gcc'
        os.environ['CXX'] = 'g++'
        os.environ['FC'] = 'gfortran'
        gcc_ver = subprocess.run(['gcc', '-dumpversion'], capture_output=True)
        sys_info['gcc_major_ver'] = int(gcc_ver.stdout.decode('UTF-8').split('.')[0])

    if opts['check_sanity']:
        check_sanity()

initialize()
process_command_line()
finish_setup()

# install_with_mumps()
# install_pyoptsparse()
