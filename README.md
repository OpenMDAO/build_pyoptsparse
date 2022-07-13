# build_pyoptsparse
This is a script that was written to overcome the complexities of building pyOptSparse with IPOPT. It downloads and installs dependencies, IPOPT itself, and pyOptSparse. It was designed with support for OpenMDAO in mind. The behavior of the script can be adjusted with various command-line switches.

Support for **conda** and **venv** is included and will be used if either has been activated. In both cases, software will be installed under the virtual environment folder. If a conda environment is active and **mamba** is available, it will be used to install/uninstall to improve performance.

For dependencies that require building, temporary directories are used and removed by default after the item has been installed.

By default, MUMPS is used as the linear solver, but if HSL or PARDISO are available, one of those can be selected instead.

The script performs sanity checking on the environment by testing for commands that are required to build or install pyOptSparse and it dependencies.

## Usage
```
usage: build_pyoptsparse [-h] [-a] [-b BRANCH] [-c CONDA_CMD] [-d] [-e] [-f] [-k] [-i]
                         [-l {mumps,hsl,pardiso}] [-m] [-n] [-p PREFIX] [-s SNOPT_DIR]
                         [-t HSL_TAR_FILE] [-u] [-v]

    Download, configure, build, and/or install pyOptSparse with IPOPT support and
    dependencies. Temporary working directories are created, which are removed
    after installation unless -d is used.

    When running under conda, all packages that can be installed with conda will
    be, except when command line arguments modify this behavior. If found, mamba
    will be used to install/uninstall unless -m is used.


options:
  -h, --help            show this help message and exit
  -a, --paropt          Add ParOpt support. Default: no ParOpt
  -b BRANCH, --branch BRANCH
                        pyOptSparse git branch. Default: v2.8.3
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
  -p PREFIX, --prefix PREFIX
                        Where to install if not a conda/venv environment. Default:
                        /Users/tkollar/ipopt
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
    build_pyoptsparse.py
    build_pyoptsparse.py --intel --linear-solver=pardiso
    build_pyoptsparse.py -l hsl -n -t ../../coinhsl-archive-2014.01.17.tar.gz
 ```
