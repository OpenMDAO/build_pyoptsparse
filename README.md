# build_pyoptsparse
This is a bash script that was written to overcome the complexities of building pyOptSparse with IPOPT. It downloads and installs dependencies, IPOPT itself, and pyOptSparse. It was designed with support for OpenMDAO in mind. The variables at the beginning of the script can be adjusted to download different package versions.

By default, the script uses MUMPS, but if HSL or PARDISO are available, it can use those.

Depending on which options are chosen, it may perform some minor patching to allow the build to succeed.

The script expects gcc, g++, and gfortran to be available (unless -i is used). It also checks for python and pip, asking for confirmation if they appear to be a system installation rather than a personal one / virtual environment.

## Usage
```
./build_pyoptsparse.sh [-a] [-b branch] [-d] [-f] [-g] [-h] [-i] [-l linear_solver]
    [-n] [-p prefix] [-s snopt_dir] [-t hsl_tar_file]

    -a                Include ParOpt. Default: no ParOpt
    -b branch         pyOptSparse git branch. Default: v2.1.5
    -d                Do not erase the build directory after completion.
    -f                Skip Python system vs. personal installation check.
    -g                Skip compiler functionality check.
    -h                Display usage and exit.
    -i                Use Intel compiler suite instead of GNU.
    -l linear_solver  One of mumps, hsl (see -t), or pardiso. Default: mumps
    -n                Prepare, but do NOT build/install pyOptSparse.
                        Default: build & install
    -p prefix         Where to install. Default: ~/ipopt
                      Note: If older versions are already installed in
                      this dir, the build may fail. If it does, rename
                      the directory or remove the old versions.
    -s snopt_dir      Include SNOPT from snopt_dir. Default: no SNOPT
    -t hsl_tar_file   If hsl is specified with -l, use this as the path
                        to the tar file with the HSL source.
                        e.g. -t ../../coinhsl-archive-2014.01.17.tar.gz

NOTES:
    When using HSL as the linear solver, the source code tar file can
    be obtained from http://www.hsl.rl.ac.uk/ipopt/

    If PARDISO is selected as the linear solver, the Intel compiler suite
    with MKL must be available.

    Examples:
      ./build_pyoptsparse.sh
      ./build_pyoptsparse.sh -l pardiso
      ./build_pyoptsparse.sh -l hsl -t ../../coinhsl-archive-2014.01.17.tar.gz
 ```
