# build_pyoptsparse

This script package is intended to help get pyoptsparse working more easily with the optional SNOPT dependency.

Originally, this script was written to overcome the complexities of building pyOptSparse and IPOPT, but improvements to pyoptsparse and the reliance on cyipopt eliminated this need.

As a result, this package no longer supports full compilation of pyoptsparse. Instead, users should install pyoptsparse and cyipopt from conda-forge, which will provide a working implementation of IPOPT.

Users who still need SNOPT integration should take the following steps:

1. Activate your virtual environment.
2. Install pyoptsparse and cyipopt from conda-forge. 
3. Install this package. It currently must be installed directly from github:

```bash
python -m pip install git+https://github.com/OpenMDAO/build_pyoptsparse.git
```

4. Build and install the SNOPT module for pyoptsparse using your licensed SNOPT source files or dynamic library.

```bash
python -m build_pyoptsparse.snopt_module /path/to/snopt/fortran/src
```

or 

```bash
python -m build_pyoptsparse.snopt_module --snopt-lib /path/to/libsnopt7.so
```

For now, the existing `python -m build_pyoptsparse` command remains but issues a noisy deprecation warning by default, with an option to bypass it using `python -m build_pyoptsparse --ignore-dep`.