# build_pyoptsparse
This script was written to overcome the complexities of building pyOptSparse and IPOPT. It can download and install IPOPT and other dependencies and pyOptSparse itself. This behavior can be adjusted with various command-line switches.

Support for **conda** and will be used if either has been activated, unless disabled by command line arguments. In both cases, software will be installed under the virtual environment folder. If a conda environment is active and **mamba** is available, it will be used to install/uninstall to improve performance.

Alternatively, if a **venv** environement is active, the script will install to that virtual environment's folder.

For dependencies that require building, temporary directories are used then removed by default after the item has been installed.

By default, MUMPS is used as the linear solver, but if HSL or PARDISO are available, one of those can be selected instead.

The script performs checks the environment by testing for commands that are required to build or install pyOptSparse and it dependencies.

If you have a previous installation of pyOptSparse and its dependencies and are encountering errors when running this script, try using the --uninstall switch first to remove old include/library files.

To install:
1. Activate your virtual environment
2. Git clone the repository
3. Run `python -m pip install ./build_pyoptsparse`.
If ParOpt support is desired, run `python -m pip install './build_pyoptsparse[paropt]'`

## Usage
```
usage: build_pyoptsparse [-h] [-a] [-b BRANCH] [-c CONDA_CMD] [-d] [-e] [-f] [-k] [-i]
                         [-l {mumps,hsl,pardiso}] [-m] [-n] [-o] [-p PREFIX] [-s SNOPT_DIR]
                         [-t HSL_TAR_FILE] [-u] [-v]

    Download, configure, build, and/or install pyOptSparse with dependencies.
    Temporary working directories are created, which are removed after
    installation unless -d is used.

    When running with a conda environment active, all packages that can be installed
    with conda will be, except when command line arguments modify this behavior. If
    found, mamba will be used to install/uninstall unless -m is invoked.


options:
  -h, --help            show this help message and exit
  -a, --paropt          Add ParOpt support. Default: no ParOpt
  -b BRANCH, --branch BRANCH
                        pyOptSparse git branch. Default: v2.9.2
  -c CONDA_CMD, --conda-cmd CONDA_CMD
                        Command to install packages with if conda is used. Default: conda
  -d, --no-delete       Do not erase the build directories after completion.
  -e, --ignore-conda    Do not install conda packages, install under conda environment, or
                        uninstall from the conda environment.
  -f, --force-build     Build/rebuild packages even if found to be installed or can be installed
                        with conda.
  -k, --no-sanity-check
                        Skip the sanity checks.
  -i, --intel           Build with the Intel compiler suite instead of GNU.
  -l {mumps,hsl,pardiso}, --linear-solver {mumps,hsl,pardiso}
                        Which linear solver to use with IPOPT. Default: mumps
  -m, --ignore-mamba    Do not use mamba to install conda packages. Default: Use mamba if found
  -n, --no-install      Prepare, but do not build/install pyOptSparse itself. Default:
                        install
  -o, --no-ipopt        Do not install IPOPT. Default: install IPOPT
  -p PREFIX, --prefix PREFIX
                        Where to install if not a conda/venv environment. Default:
                        $HOME/pyoptsparse
  -s SNOPT_DIR, --snopt-dir SNOPT_DIR
                        Include SNOPT from SNOPT-DIR. Default: no SNOPT
  -t HSL_TAR_FILE, --hsl-tar-file HSL_TAR_FILE
                        If HSL is the linear solver, use this as the path to the tar file of the
                        HSL source. E.g. -t ../../coinhsl-archive-2014.01.17.tar.gz
  -u, --uninstall       Attempt to remove an installation previously built from source (using the
                        same --prefix) and/or installed with conda in the same environment, then
                        exit. Default: Do not uninstall
  -v, --verbose         Show output from git, configure, make, conda, etc. and expand all
                        environment variables.

    NOTES:
    When using HSL as the linear solver, the source code tar file can be obtained
    from http://www.hsl.rl.ac.uk/ipopt/
    If PARDISO is selected as the linear solver, the Intel compiler suite with MKL
    must be available.

    Examples:
    build_pyoptsparse
    build_pyoptsparse --intel --linear-solver=pardiso
    build_pyoptsparse -l hsl -n -t ../../coinhsl-archive-2014.01.17.tar.gz
 ```
