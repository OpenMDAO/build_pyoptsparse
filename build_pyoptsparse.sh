#!/usr/bin/env bash
# Finds/downloads and unpacks pyOptSparse, IPOPT, and deps source
# archives to current directory. Chdirs to each directory in turn
# to build and install each package (except for pyOptSparse if
# build is disabled by command line options).
#
# Default values:
PREFIX=$HOME/ipopt
LINEAR_SOLVER=MUMPS
BUILD_PYOPTSPARSE=1

METIS_BRANCH=stable/2.0
MUMPS_BRANCH=stable/2.0
IPOPT_BRANCH=stable/3.13
PYOPTSPARSE_BRANCH=v2.1.5

COMPILER_SUITE=GNU

INCLUDE_SNOPT=0
SNOPT_DIR=SNOPT

HSL_TAR_FILE=NOFILE
INCLUDE_PAROPT=0
KEEP_BUILD_DIR=0
CHECK_PY_INST_TYPE=1
CHECK_COMPILER_FUNCTION=1
BUILD_TIME=`date +%s`
LINE="-----------------------------------------------------------------------------"
CORES=`nproc 2>&1`||CORES=`sysctl -n hw.ncpu 2>&1`||CORES=1

# Use only half the available cores for building:
[ $CORES -gt 1 ] && CORES=$((CORES/2))

usage() {
cat <<USAGE
Download, configure, build, and install pyOptSparse with IPOPT
support and dependencies. A temporary working directory is created,
which is removed if the installation succeeds unless -d is used.

Usage:
$0 [-a] [-b branch] [-d] [-f] [-g] [-h] [-i] [-l linear_solver]
    [-n] [-p prefix] [-s snopt_dir] [-t hsl_tar_file]

    -a                Include ParOpt. Default: no ParOpt
    -b branch         pyOptSparse git branch. Default: ${PYOPTSPARSE_BRANCH}
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
      $0
      $0 -l pardiso
      $0 -l hsl -n -t ../../coinhsl-archive-2014.01.17.tar.gz
USAGE
    exit 3
}

while getopts ":ab:dfghil:np:s:t:" opt; do
    case ${opt} in
        a)
            INCLUDE_PAROPT=1 ;;
        b)
            PYOPTSPARSE_BRANCH="$OPTARG" ;;
        d)
            KEEP_BUILD_DIR=1 ;;
        f)
            CHECK_PY_INST_TYPE=0 ;;
        g)
            CHECK_COMPILER_FUNCTION=0 ;;
        h)
            usage ;;
        i)
            COMPILER_SUITE=Intel ;;
        l)
            LS_UP=`echo $OPTARG | tr [:lower:] [:upper:]`
            case $LS_UP in
                MUMPS|HSL)
                    LINEAR_SOLVER=$LS_UP
                    COMPILER_SUITE=GNU ;;
                PARDISO)
                    LINEAR_SOLVER=PARDISO
                    COMPILER_SUITE=Intel ;;
                *)
                    echo "Unrecognized linear solver specified."
                    usage ;;
            esac
            ;;
        n)
            BUILD_PYOPTSPARSE=0 ;;
        p)
            PREFIX="$OPTARG" ;;
        s)
            INCLUDE_SNOPT=1
            SNOPT_DIR=$OPTARG
            if [ ! -d "$SNOPT_DIR" ]; then
                echo "Specified SNOPT source dir $SNOPT_DIR doesn't exist relative to `pwd`."
                exit 1
            fi

            # Use snoptc.f to determine the exact folder to point to. This is the same
            # file the the pyOptSparse build looks for. If it's not found, the
            # pyOptSparse build will silently ignore SNOPT.
            snopt_file=$(find -L "$SNOPT_DIR" -name snoptc.f)
            if [ $snopt_file = '' ]; then
                echo "$SNOPT_DIR does not appear to be a proper SNOPT directory."
                exit 1
            fi

            # Make sure it's an absolute path instead of relative:
            SNOPT_DIR=$(cd `dirname "$snopt_file"`; pwd)
            echo "Using $SNOPT_DIR for SNOPT source."
            ;;
        t)
            tar_file=$OPTARG
            if [ ! -f "$tar_file" ]; then
                echo "Specified HSL tar file $tar_file doesn't exist relative to `pwd`."
                exit 1
            fi

            # Make sure it's an absolute path instead of relative:
            tar_dir=$(cd `dirname "$tar_file"`; pwd)
            bare_file=`basename $tar_file`
            HSL_TAR_FILE="${tar_dir}/${bare_file}"
            echo "Using $HSL_TAR_FILE for HSL source tar file."
            ;;
        \?)
            echo "Unrecognized option -${OPTARG} specified."
            usage ;;
        :)
            echo "Option -${OPTARG} requires an argument."
            usage ;;
    esac
done

# Choose compiler and make settings:
case $COMPILER_SUITE in
    GNU)
        CC=gcc
        CXX=g++
        FC=gfortran
        ;;
    Intel)
        CC=icc
        CXX=icpc
        FC=ifort
        ;;
    *)
        echo "Unknown compiler suite specified."
        exit 2
        ;;
esac

MAKEFLAGS='-j 6'
export CC CXX FC MAKEFLAGS

REQUIRED_CMDS="make $CC $CXX $FC sed git curl tar awk"
if [ $BUILD_PYOPTSPARSE = 1 ]; then
    REQUIRED_CMDS="$REQUIRED_CMDS pip swig"
fi

if [ $INCLUDE_PAROPT = 1 ]; then
    REQUIRED_CMDS="$REQUIRED_CMDS mpicxx"
fi

####################################################################

set -e
trap 'cmd_failed $?' EXIT

cmd_failed() {
	if [ "$1" != "0" -a "$1" != "100" ]; then
        echo $LINE
		echo "FATAL ERROR: The command failed with error $1."
        echo $LINE
		exit 1
	fi
}

##### Special checks for Python #####
# Find the nearest 
PY=`which python3` || PY=`which python` || {
    echo "Python executable cannot be found, please install it or add it to PATH."
    exit 1
}

# Make sure it's the right version
PYver=`$PY --version 2>&1`
[ "${PYver:0:8}" = 'Python 3' ] || {
    echo "Python version 3.x is required, cannot continue with $PYver."
    exit 1
}

# If it's not writable, it's probably the system version.
# Don't bother checking if it's on Travis.
[ -z "$TRAVIS" ] && [ $CHECK_PY_INST_TYPE = 1 -a ! -w $PY ] && {
    cat<<EOD1
$LINE
The $PY binary is not writable and is probably the
system version instead of a personal installation/virtual environment.
Continuing MAY result in permissions errors or dependency conflicts
(this check can be skipped with the -f switch).

To create a virtual Python environment, run:

$PY -m venv path/to/new_env
source path/to/new_env/bin/activate
$LINE
Attempt installation with $PY anyway?
EOD1
    select yn in "Yes" "No"; do
        case $yn in
            Yes ) break;;
            No ) echo "Exiting as requested."; exit 0;;
        esac
    done
    echo ""
    echo "Continuing as requested..."
}

missing_cmds=''
for c in $REQUIRED_CMDS; do
	type -p $c > /dev/null || missing_cmds="$missing_cmds $c"
done

[ -z "$missing_cmds" ] || {
	echo "Missing required commands:$missing_cmds"
	exit 1
}

# Check for compiler functionality
[ $CHECK_COMPILER_FUNCTION = 1 ] && {
    echo $LINE
    echo "Testing basic compiler functionality. Can be skipped with -g."
    echo $LINE
    printf '#include <stdio.h>\nint main() {\nprintf("test");\nreturn 0;\n}\n' > hello.c
    $CC -o hello_c hello.c
    ./hello_c > /dev/null
    rm hello_c hello.c

    printf '#include <iostream>\nint main() {\nstd::cout << "test";\nreturn 0;\n}\n' > hello.cc
    $CXX -o hello_cxx hello.cc
    ./hello_cxx > /dev/null
    rm hello_cxx hello.cc

    printf "program hello\n  print *, 'test'\nend program hello" > hello.f90
    $FC -o hello_f hello.f90
    ./hello_f > /dev/null
    rm hello_f hello.f90
}

echo $LINE
echo "Will run make with $CORES cores where possible."
echo $LINE

build_dir=build_pyoptsparse.`printf "%x" $BUILD_TIME`
mkdir $build_dir
pushd $build_dir

bkp_dir() {
    check_dir=$1
    if [ -d "$check_dir" ]; then
        echo "Renaming $check_dir to ${check_dir}.bkp.${BUILD_TIME}"
        mv "$check_dir" "${check_dir}.bkp.${BUILD_TIME}"
    fi
}

install_metis() {
    echo "==========================="
    echo "INSTALL METIS $METIS_BRANCH"
    echo "==========================="
    bkp_dir ThirdParty-Metis

    # Install METIS
    git clone -b $METIS_BRANCH https://github.com/coin-or-tools/ThirdParty-Metis.git
    pushd ThirdParty-Metis
    ./get.Metis
    CFLAGS='-Wno-implicit-function-declaration' ./configure --prefix=$PREFIX
    make -j $CORE
    make install
    popd
}

install_ipopt() {
    echo "==========================="
    echo "INSTALL IPOPT $IPOPT_BRANCH"
    echo "==========================="
    bkp_dir Ipopt

    echo $CC $CXX $FC
    git clone -b $IPOPT_BRANCH https://github.com/coin-or/Ipopt.git

    pushd Ipopt
    ./configure --prefix=${PREFIX} --disable-java "$@"
    make -j $CORES
    make install
    popd
}

install_paropt() {
    echo "=============="
    echo "INSTALL PAROPT"
    echo "=============="
    bkp_dir paropt

    [ -n "$TRAVIS" ] && {
        #TODO: Remove this when the functionality is added to OM .travis.yml
        conda install -v -c conda-forge gxx_linux-64 --yes
        conda install -v -c conda-forge gfortran_linux-64 --yes
    }

    pip install Cython
    git clone https://github.com/gjkennedy/paropt
    pushd paropt
    cp Makefile.in.info Makefile.in
    make -j $CORES PAROPT_DIR=$PWD
    # In some cases needed to set this CFLAGS
    # CFLAGS='-stdlib=libc++' python setup.py install
    $PY setup.py install
    popd
 }

build_pyoptsparse() {
    echo "====================================="
    echo "BUILD PYOPTSPARSE $PYOPTSPARSE_BRANCH"
    echo "====================================="
    patch_type=$1

    pip install numpy
    bkp_dir pyoptsparse
    git clone -b "$PYOPTSPARSE_BRANCH" https://github.com/mdolab/pyoptsparse.git

    if [ "$PYOPTSPARSE_BRANCH" = "v1.2" ]; then
        case $patch_type in
            mumps)
                sed -i -e "s/coinhsl/coinmumps', 'coinmetis/" pyoptsparse/pyoptsparse/pyIPOPT/setup.py
                ;;
            pardiso)
                sed -i -e "s/'coinhsl', //;s/, 'blas', 'lapack'//" pyoptsparse/pyoptsparse/pyIPOPT/setup.py
                ;;
        esac
    elif [ "$PYOPTSPARSE_BRANCH" = "v2.1.5" ]; then
        case $patch_type in
            mumps)
                sed -i -e 's/coinhsl/coinmumps", "coinmetis/' pyoptsparse/pyoptsparse/pyIPOPT/setup.py
                ;;
            pardiso)
                sed -i -e 's/"coinhsl", //;s/, "blas", "lapack"//' pyoptsparse/pyoptsparse/pyIPOPT/setup.py
                ;;
        esac
    fi

    if [ $INCLUDE_SNOPT = 1 ]; then
        rsync -a --exclude snopth.f "${SNOPT_DIR}/" ./pyoptsparse/pyoptsparse/pySNOPT/source/
    fi

    if [ "$PYOPTSPARSE_BRANCH" = "v2.1.5" ] && [ $INCLUDE_PAROPT = 1 ] ; then
    echo ">>> Installing paropt";
      install_paropt
    fi

    if [ $BUILD_PYOPTSPARSE = 1 ]; then
        $PY -m pip install sqlitedict

        # Necessary for pyoptsparse to find IPOPT:
        export IPOPT_INC=$PREFIX/include/coin-or
        export IPOPT_LIB=$PREFIX/lib
        export CFLAGS='-Wno-implicit-function-declaration' 
        $PY -m pip install --no-cache-dir ./pyoptsparse
    else
	echo $LINE
	echo NOT building pyOptSparse by request. Make sure to set
	echo these variables before building it yourself:
	echo
	echo export IPOPT_INC=$PREFIX/include/coin-or
	echo export IPOPT_LIB=$PREFIX/lib
	echo $LINE
    fi
}

install_with_mumps() {
    install_metis
    echo "================================"
    echo "INSTALL WITH MUMPS $MUMPS_BRANCH"
    echo "================================"
    bkp_dir ThirdParty-Mumps

    # Install MUMPS
    git clone -b $MUMPS_BRANCH https://github.com/coin-or-tools/ThirdParty-Mumps.git
    pushd ThirdParty-Mumps
    ./get.Mumps
    ./configure --with-metis --with-metis-lflags="-L${PREFIX}/lib -lcoinmetis" \
       --with-metis-cflags="-I${PREFIX}/include -I${PREFIX}/include/coin-or -I${PREFIX}/include/coin-or/metis" \
       --prefix=$PREFIX CFLAGS="-I${PREFIX}/include -I${PREFIX}/include/coin-or -I${PREFIX}/include/coin-or/metis" \
       FCFLAGS="-I${PREFIX}/include -I${PREFIX}/include/coin-or -I${PREFIX}/include/coin-or/metis"
    make -j $CORES
    make install
    popd

    install_ipopt --with-mumps --with-mumps-lflags="-L${PREFIX}/lib -lcoinmumps" \
        --with-mumps-cflags="-I${PREFIX}/include/coin-or/mumps"

    # Build and install pyoptsparse
    build_pyoptsparse mumps
}

install_with_hsl() {
    echo "================"
    echo "INSTALL WITH HSL"
    echo "================"
    install_metis
    bkp_dir ThirdParty-HSL

    # Unpack, build, and install HSL archive lib:
    git clone https://github.com/coin-or-tools/ThirdParty-HSL
    pushd ThirdParty-HSL
    hsl_top_dir=`tar vtf $HSL_TAR_FILE|head -1|awk '{print $9;}'`
    tar xf $HSL_TAR_FILE
    mv $hsl_top_dir coinhsl
    ./configure --prefix=$PREFIX --with-metis \
       --with-metis-lflags="-L${PREFIX}/lib -lcoinmetis" \
       --with-metis-cflags="-I${PREFIX}/include"
    make -j $CORES
    make install
    popd

    install_ipopt --with-hsl --with-hsl-lflags="-L${PREFIX}/lib -lcoinhsl -lcoinmetis" \
        --with-hsl-cflags="-I${PREFIX}/include/coin-or/hsl" --disable-linear-solver-loader

    build_pyoptsparse hsl
}

install_with_pardiso() {
    echo "====================="
    echo "INSTALL WITH PARADISO"
    echo "====================="
    install_ipopt --with-lapack="-mkl"

    # pyOptSparse doesn't do well with Intel compilers, so unset:
    unset CC CXX FC
    build_pyoptsparse pardiso
}

case $LINEAR_SOLVER in
    MUMPS)
        install_with_mumps ;;
    HSL)
        [ "$HSL_TAR_FILE" = "NOFILE" ] && {
            echo
            echo $LINE
            echo "ERROR: With hsl, use -t to point to the source tar file.";
            echo $LINE
            exit 100;
        }
        install_with_hsl ;;
    PARDISO)
        install_with_pardiso ;;
    *)
        echo "Unknown linear solver specified."
        exit 2
        ;;
esac

echo Done.
popd
if [ $KEEP_BUILD_DIR = 0 ]; then
    echo "Removing build directory '$build_dir'"
    rm -fr $build_dir
fi

ld_var=LD_LIBRARY_PATH
[ `uname -s` = 'Darwin' ] && ld_var=DYLD_LIBRARY_PATH
cat<<EOD2

$LINE
NOTE: Set the following environment variable before using this installation:

export ${ld_var}=${PREFIX}/lib:\$${ld_var}

Otherwise, you may encounter errors such as:
 "pyOptSparse Error: There was an error importing the compiled IPOPT module"
$LINE
Build succeeded!
EOD2
exit 0
