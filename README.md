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

## Building the SNOPT module on Windows

Building the SNOPT module on Windows requires the Intel Fortran compiler (`ifx`) plus the MSVC linker (`link.exe`) from Visual Studio Build Tools. `ifx` needs the MSVC linker even though it doesn't need the MSVC compiler itself, so both must be available before running `build_pyoptsparse.snopt_module`.

### Using conda/pixi (recommended)

Visual Studio Build Tools (the "Desktop development with C++" workload) must still be installed separately, since Microsoft does not allow its linker to be redistributed. Once that's done, add the conda-forge `ifx_win-64` package to your environment:

```bash
conda install -c conda-forge ifx_win-64
```

or in a `pixi.toml`:

```toml
[target.win-64.dependencies]
ifx_win-64 = "*"
```

`ifx_win-64` pulls in the actual Intel Fortran compiler binaries and activates both `ifx` and the system Visual Studio linker automatically whenever the environment is activated (`conda activate` / `pixi run` / `pixi shell`) — no manual environment setup needed.

### Without conda/pixi

If you're not using conda or pixi, install both toolchains manually:

1. Install the [Intel oneAPI HPC Toolkit](https://www.intel.com/content/www/us/en/developer/tools/oneapi/hpc-toolkit-download.html) (provides `ifx`).
2. Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio) with the "Desktop development with C++" workload (provides `link.exe`/`cl.exe`).
3. Activate both environments in the same shell before building. The Intel installer creates a Start Menu shortcut named something like "Intel oneAPI command prompt for Intel 64 for Visual Studio 2022" if it detected Visual Studio at install time — use that, or manually run:

   ```cmd
   call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
   ```

   (adjust the Visual Studio version argument to match what you have installed).
4. From that same shell, run the build command as usual:

   ```cmd
   python -m build_pyoptsparse.snopt_module C:\path\to\snopt\fortran\src
   ```