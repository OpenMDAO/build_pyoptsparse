#!/usr/bin/env python
"""
Build SNOPT extension module for use with conda-installed pyoptsparse.

This script builds the SNOPT Python extension module from SNOPT Fortran source code
using meson as the build system. This allows you to use SNOPT with a conda-installed
pyoptsparse without recompiling the entire package.

By default, the module is installed directly into the pyoptsparse package directory,
so no environment variable configuration is needed. SNOPT will be automatically
detected when you import pyoptsparse.

Requirements:
    - meson (pip install meson)
    - ninja (pip install ninja)
    - numpy
    - A Fortran compiler (gfortran, ifort, etc.)

Usage:
    python -m build_pyoptsparse.snopt_module /path/to/snopt/src [options]

Example:
    python -m build_pyoptsparse.snopt_module ~/Downloads/snopt-7.7/src
    python -m build_pyoptsparse.snopt_module ~/Downloads/snopt-7.7/src --output ~/my-snopt
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .build_pyoptsparse import announce


def find_pyoptsparse():
    """Find the pyoptsparse installation directory."""
    import pyoptsparse

    return Path(pyoptsparse.__file__).parent


def check_snopt_source(source_dir):
    """Check if the provided directory contains SNOPT source files."""
    source_path = Path(source_dir)

    if not source_path.exists():
        print(f"Error: Directory {source_dir} does not exist")
        return False

    if not source_path.is_dir():
        print(f"Error: {source_dir} is not a directory")
        return False

    # Check for key SNOPT file
    key_file = source_path / "snoptc.f"
    if not key_file.exists():
        print(f"Error: {source_dir} does not appear to contain SNOPT source code")
        print("       Expected to find snoptc.f in this directory")
        return False

    # Count .f files
    f_files = list(source_path.glob("*.f"))
    if len(f_files) < 10:
        print(f"Warning: Only found {len(f_files)} .f files in {source_dir}")
        print("         Expected to find more SNOPT source files")

    return True


def copy_snopt_source(source_dir, dest_dir):
    """Copy SNOPT source files to destination, excluding certain files."""
    source_path = Path(source_dir)
    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)

    EXCLUDE_FILES = ["snopth.f"]

    f_files = list(source_path.glob("*.f"))
    f_file_names = [f.name for f in f_files]

    if "sn27lu.f" in f_file_names:
        EXCLUDE_FILES.extend(["sn27lu77.f", "sn27lu90.f"])
    elif "sn27lu90.f" in f_file_names:
        EXCLUDE_FILES.extend(["sn27lu.f", "sn27lu77.f"])

    copied_files = []
    skipped_files = []

    for f_file in source_path.glob("*.f"):
        if f_file.name in EXCLUDE_FILES:
            skipped_files.append(f_file.name)
            continue

        shutil.copy2(f_file, dest_path / f_file.name)
        copied_files.append(f_file.name)

    print(f"Copied {len(copied_files)} SNOPT source files")
    if skipped_files:
        print(f"Skipped {len(skipped_files)} files: {', '.join(skipped_files)}")

    return copied_files


def download_file_from_github(url, dest_path):
    """Download a file from GitHub."""
    try:
        import urllib.request
        print(f"  Downloading {dest_path.name}...")
        urllib.request.urlretrieve(url, dest_path)
        return True
    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        return False


def copy_pyoptsparse_files(build_dir):
    """Copy necessary files from pyoptsparse installation to build directory."""
    this_dir = Path(__file__).parent
    pyopt_dir = find_pyoptsparse()
    snopt_dir = pyopt_dir / "pySNOPT"
    source_dir = snopt_dir / "source"

    build_path = Path(build_dir)

    # Create source subdirectory structure
    source_build_dir = build_path / "source" / "f2py"
    source_build_dir.mkdir(parents=True, exist_ok=True)

    # Files to copy/download
    files_needed = {
        "f2py/snopt.pyf": "https://raw.githubusercontent.com/mdolab/pyoptsparse/main/pyoptsparse/pySNOPT/source/f2py/snopt.pyf",
        "openunit.f": "https://raw.githubusercontent.com/mdolab/pyoptsparse/main/pyoptsparse/pySNOPT/source/openunit.f",
        "closeunit.f": "https://raw.githubusercontent.com/mdolab/pyoptsparse/main/pyoptsparse/pySNOPT/source/closeunit.f",
    }

    for file_path, url in files_needed.items():
        dest = build_path / "source" / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        if not dest.exists():
            if not download_file_from_github(url, dest):
                print(f"\nError: Failed to download {file_path}")
                print("Please check your internet connection or download manually from:")
                print("  https://github.com/mdolab/pyoptsparse/tree/main/pyoptsparse/pySNOPT/source")
                sys.exit(1)

    # else:
    #     # Copy files from installation
    #     print("Copying SNOPT build files from installation...")

    #     # Copy f2py interface file
    #     f2py_file = source_dir / "f2py" / "snopt.pyf"
    #     if not f2py_file.exists():
    #         print(f"Error: Cannot find {f2py_file}")
    #         sys.exit(1)
    #     shutil.copy2(f2py_file, source_build_dir / "snopt.pyf")

    #     # Copy helper Fortran files to source directory
    #     for helper_file in ["openunit.f", "closeunit.f"]:
    #         helper_path = source_dir / helper_file
    #         if helper_path.exists():
    #             shutil.copy2(helper_path, build_path / "source" / helper_file)

    #     print("Copied pyoptsparse build files")

    # Copy grab-all-fortran-files.py script
    grab_script = this_dir / "grab-all-fortran-files.py"
    if not grab_script.exists():
        print(f"Error: Cannot find {grab_script}")
        sys.exit(1)
    shutil.copy2(grab_script, build_path / "source" / "grab-all-fortran-files.py")
    # Make it executable
    (build_path / "source" / "grab-all-fortran-files.py").chmod(0o755)
    print("Copied pyoptsparse build assist script")


def create_meson_build_file(build_dir: Path | str,
                            snopt_src_files: list[str] | None=None,
                            snopt_lib_path: Path | str | None=None):
    """Create a standalone meson.build file for SNOPT.

    User must provide either snopt_src_files or snopt_lib_path

    Parameters
    ----------
    build_dir: Path or str
        Build directory path
    snopt_src_files : list[str]
        Optional path to snopt source files.
    snopt_lib_path
        Optional path to precompiled libsnopt7.so/dylib. If provided, link against this library
        instead of compiling from source.
    """
    build_path = Path(build_dir)

    if snopt_lib_path:
        # Link against precompiled library
        lib_dir = Path(snopt_lib_path).parent
        lib_name = Path(snopt_lib_path).name
        # Remove 'lib' prefix (Linux/macOS) and extension to get library name for -l flag
        if lib_name.startswith('lib'):
            lib_name = lib_name[3:]
        # Remove extensions (cross-platform)
        lib_name = lib_name.replace('.so', '').replace('.dylib', '').replace('.dll', '').replace('.a', '')

        meson_content = f"""project(
  'snopt-module',
  'c',
  meson_version: '>= 0.60',
  default_options: [
    'buildtype=debugoptimized',
    'c_std=c99',
  ],
)

# Get Python
py_mod = import('python')
py3 = py_mod.find_installation()
py3_dep = py3.dependency()

# Get NumPy include directory
incdir_numpy = run_command(py3,
  ['-c', 'import numpy; print(numpy.get_include())'],
  check: true
).stdout().strip()
inc_np = include_directories(incdir_numpy)

# Get f2py include directory
incdir_f2py = run_command(py3,
  ['-c', 'import os; import numpy; print(os.path.join(numpy.get_include(), "..", "..", "f2py", "src"))'],
  check: true
).stdout().strip()
inc_f2py = include_directories(incdir_f2py)

# Copy fortranobject.c locally
run_command(py3,
  ['-c', 'import os, shutil, numpy; shutil.copy(os.path.join(numpy.get_include(), "..", "..", "f2py", "src", "fortranobject.c"), ".")'],
  check: true
)
fortranobject_c = 'fortranobject.c'

# Find precompiled SNOPT library
cc = meson.get_compiler('c')
snopt_lib = cc.find_library('{lib_name}', dirs: ['{lib_dir}'], required: true)

# Generate C wrapper from f2py interface
snopt_source = custom_target('snoptmodule.c',
  input: ['source/f2py/snopt.pyf'],
  output: ['snoptmodule.c'],
  command: [py3, '-m', 'numpy.f2py', '@INPUT@', '--lower', '--build-dir', '.']
)

# Build extension module linked against precompiled library
py3.extension_module('snopt',
  snopt_source,
  fortranobject_c,
  include_directories: [inc_np, inc_f2py],
  dependencies: [py3_dep, snopt_lib],
  install: false
)

message('Building SNOPT module linked against precompiled library: {snopt_lib_path}')
"""
    else:
        # Compile from source
        meson_content = f"""project(
  'snopt-module',
  'c', 'fortran',
  meson_version: '>= 0.60',
  default_options: [
    'buildtype=debugoptimized',
    'c_std=c99',
  ],
)

# Get Python
py_mod = import('python')
py3 = py_mod.find_installation()
py3_dep = py3.dependency()

# Get NumPy include directory
incdir_numpy = run_command(py3,
  ['-c', 'import numpy; print(numpy.get_include())'],
  check: true
).stdout().strip()
inc_np = include_directories(incdir_numpy)

# Get f2py include directory
incdir_f2py = run_command(py3,
  ['-c', 'import os; import numpy; print(os.path.join(numpy.get_include(), "..", "..", "f2py", "src"))'],
  check: true
).stdout().strip()
inc_f2py = include_directories(incdir_f2py)

# Copy fortranobject.c locally
run_command(py3,
  ['-c', 'import os, shutil, numpy; shutil.copy(os.path.join(numpy.get_include(), "..", "..", "f2py", "src", "fortranobject.c"), ".")'],
  check: true
)
fortranobject_c = 'fortranobject.c'

# Get list of all Fortran files
snopt_source_files = [{', '.join(snopt_src_files)}]

# Generate C wrapper from f2py interface
snopt_source = custom_target('snoptmodule.c',
  input: ['source/f2py/snopt.pyf'],
  output: ['snoptmodule.c'],
  command: [py3, '-m', 'numpy.f2py', '@INPUT@', '--lower', '--build-dir', '.']
)

# Build extension module
py3.extension_module('snopt',
  snopt_source,
  fortranobject_c,
  snopt_source_files,
  include_directories: [inc_np, inc_f2py],
  dependencies: py3_dep,
  install: false,
  fortran_args: '-ffixed-line-length-80'
)

message('SNOPT module will be built')
"""

    meson_file = build_path / "meson.build"
    meson_file.write_text(meson_content)
    print("Created meson.build file")


def build_with_meson(build_dir):
    """Build SNOPT module using meson."""
    build_path = Path(build_dir)

    print("\nBuilding SNOPT module with meson...")
    print("This may take several minutes...\n")

    # Check if meson is available
    meson_path = shutil.which("meson")
    if not meson_path:
        print("Error: meson not found")
        print("Please install meson: pip install meson ninja")
        return False

    try:
        # Setup meson build
        print("Running meson setup...")
        result = subprocess.run(
            [meson_path, "setup", "builddir"],
            cwd=build_path,
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        # Compile
        print("\nCompiling...")
        result = subprocess.run(
            [meson_path, "compile", "-C", "builddir"],
            cwd=build_path,
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        print("\nBuild completed successfully!")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        print("\nStdout:")
        print(e.stdout)
        print("\nStderr:")
        print(e.stderr)
        return False
    except FileNotFoundError:
        print("Error: Could not find meson")
        print("Make sure meson is installed: pip install meson ninja")
        return False


def find_built_module(build_dir):
    """Find the built SNOPT extension module."""
    build_path = Path(build_dir)

    # Look in builddir for meson output
    builddir = build_path / "builddir"

    # Look for snopt*.so, snopt*.pyd, snopt*.dylib files (cross-platform)
    patterns = ["snopt*.so", "snopt*.pyd", "snopt*.dylib", "snopt*.dll"]

    for pattern in patterns:
        files = list(builddir.glob(pattern))
        if files:
            return files[0]

    return None


def install_module(module_path, output_dir):
    """Copy the built module to the output directory."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    dest_file = output_path / module_path.name
    shutil.copy2(module_path, dest_file)

    print(f"\nInstalled SNOPT module to: {dest_file}")
    return dest_file


def print_instructions(install_path, is_default_location):
    """Print instructions for using the built module."""
    install_dir = Path(install_path).parent

    print("\n" + "="*80)
    announce("SUCCESS! SNOPT module built and installed")
    print("="*80)

    if is_default_location:
        print("\nSNOPT has been installed to the pyoptsparse package directory.")
        print("It will be automatically detected - no configuration needed!")
        print("")
        print("To test your installation:")
        print("  python -c \"from pyoptsparse import SNOPT; print('SNOPT loaded successfully!')\"")
    else:
        print(f"\nSNOPT has been installed to: {install_dir}/")
        print("\nTo use SNOPT with pyoptsparse, set the following environment variable:\n")

        # Check the shell
        shell = os.environ.get("SHELL", "")

        print(f"  export PYOPTSPARSE_IMPORT_SNOPT_FROM={install_dir}/")
        print("")

        if "bash" in shell or "zsh" in shell:
            shell_rc = "~/.bashrc" if "bash" in shell else "~/.zshrc"
            print(f"To make this permanent, add the following to your {shell_rc}:")
            print(f"  echo 'export PYOPTSPARSE_IMPORT_SNOPT_FROM={install_dir}/' >> {shell_rc}")
            print("")

        print("You can also set it in your Python code before importing:")
        print("  import os")
        print("  os.environ['PYOPTSPARSE_IMPORT_SNOPT_FROM'] = '{install_dir}/'")
        print("  from pyoptsparse import SNOPT")
        print("")
        print("To test your installation:")
        print(f"  PYOPTSPARSE_IMPORT_SNOPT_FROM={install_dir}/ python -c \"from pyoptsparse import SNOPT; print('SNOPT loaded successfully!')\"")

    print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Build SNOPT extension module for conda-installed pyoptsparse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
Examples:
  # Build from source and install to default location (pyoptsparse package directory)
  # No environment variable needed!
  python -m build_pyoptsparse.snopt_module ~/Downloads/snopt-7.7/src

  # Link against precompiled library (Linux/macOS/Windows)
  python -m build_pyoptsparse.snopt_module --snopt-lib /path/to/libsnopt7.so
  python -m build_pyoptsparse.snopt_module --snopt-lib C:\path\to\snopt7.dll

  # Build from source and install to custom location (requires setting PYOPTSPARSE_IMPORT_SNOPT_FROM)
  python -m build_pyoptsparse.snopt_module ~/Downloads/snopt-7.7/src --output ~/my-snopt

  # Keep build directory for debugging
  python -m build_pyoptsparse.snopt_module ~/Downloads/snopt-7.7/src --keep-build
        """
    )

    parser.add_argument(
        "snopt_source",
        nargs="?",
        default=None,
        help="Path to directory containing SNOPT source files (*.f). Not required if using --snopt-lib."
    )

    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for built module (default: pyoptsparse installation pySNOPT directory)"
    )

    parser.add_argument(
        "--snopt-lib",
        dest="snopt_lib",
        default=None,
        help="Path to precompiled SNOPT library (libsnopt7.so, libsnopt7.dylib, or snopt7.dll) to link against instead of compiling from source"
    )

    parser.add_argument(
        "--keep-build",
        action="store_true",
        help="Keep temporary build directory after building"
    )

    parser.add_argument(
        "--build-dir",
        default=None,
        help="Use specific build directory instead of temporary directory"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.snopt_source and not args.snopt_lib:
        parser.error("Either snopt_source or --snopt-lib must be provided")

    if args.snopt_source and args.snopt_lib:
        parser.error("Cannot specify both snopt_source and --snopt-lib. Choose one build method.")

    # Validate snopt_lib path if provided
    if args.snopt_lib:
        snopt_lib_path = Path(args.snopt_lib)
        if not snopt_lib_path.exists():
            print(f"Error: SNOPT library not found: {args.snopt_lib}")
            sys.exit(1)
        if not snopt_lib_path.is_file():
            print(f"Error: {args.snopt_lib} is not a file")
            sys.exit(1)
        # Expand to absolute path
        args.snopt_lib = str(snopt_lib_path.resolve())

    # Set default output directory to pyoptsparse pySNOPT directory
    is_default_location = args.output is None
    if args.output is None:
        pyopt_dir = find_pyoptsparse()
        args.output = pyopt_dir / "pySNOPT"

    print("="*70)
    print("pyoptsparse SNOPT Module Builder")
    print("="*70)
    if args.snopt_lib:
        print("Build mode: Link against precompiled library")
        print(f"SNOPT library: {args.snopt_lib}")
    else:
        print("Build mode: Compile from source")
        print(f"SNOPT source: {args.snopt_source}")
    print(f"Output directory: {args.output}")
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python: {sys.version.split()[0]}")
    print("="*70)
    print("")

    # Check SNOPT source directory (only if building from source)
    if args.snopt_source and not check_snopt_source(args.snopt_source):
        sys.exit(1)

    # Create or use build directory
    if args.build_dir:
        build_dir = Path(args.build_dir)
        build_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = None
        print(f"Using build directory: {build_dir}\n")
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="snopt-build-")
        build_dir = Path(temp_dir.name)
        print(f"Created temporary build directory: {build_dir}\n")

    try:
        # Copy files to build directory
        copy_pyoptsparse_files(build_dir)

        # Copy SNOPT source files if building from source
        if not args.snopt_lib:
            snopt_src_list = copy_snopt_source(args.snopt_source, build_dir / "source") if args.snopt_source else None
            # Prepend 'source/' to each filename since files are in source/ subdirectory
            if snopt_src_list:
                snopt_src_list.extend(["openunit.f", "closeunit.f"])
                snopt_src_list = [f"'source/{f}'" for f in snopt_src_list]
        else:
            snopt_src_list = None

        # Create meson.build file
        create_meson_build_file(build_dir, snopt_lib_path=args.snopt_lib, snopt_src_files=snopt_src_list)

        # Build the module with meson
        if not build_with_meson(build_dir):
            print("\nBuild failed. Exiting.")
            if args.keep_build or args.build_dir:
                print(f"Build directory preserved at: {build_dir}")
            sys.exit(1)

        # Find the built module
        module_path = find_built_module(build_dir)
        if not module_path:
            print("\nError: Could not find built SNOPT module")
            if args.keep_build or args.build_dir:
                print(f"Build directory preserved at: {build_dir}")
            sys.exit(1)

        print(f"Found built module: {module_path.name}")

        # Install the module
        installed_path = install_module(module_path, args.output)

        # Print instructions
        print_instructions(installed_path, is_default_location)

        # Keep or clean up build directory
        if args.keep_build and temp_dir:
            print(f"\nBuild directory preserved at: {build_dir}")
            temp_dir = None  # Prevent cleanup

    finally:
        # Clean up temporary directory if needed
        if temp_dir and not args.keep_build:
            temp_dir.cleanup()


if __name__ == "__main__":
    main()
