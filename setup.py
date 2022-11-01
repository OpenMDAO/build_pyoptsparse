from distutils.core import setup
from setuptools import find_packages
import re

__version__ = re.findall(
    r"""__version__ = ["']+([0-9\.]*)["']+""",
    open('__init__.py').read(),
)[0]

optional_dependencies = {
    'paropt': [
        'cython',
        'mpi4py'
    ]
}

setup(name='build_pyoptsparse',
    version=__version__,
    license='Apache License',
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        'ansicolors',
        'numpy',
        'sqlitedict',
        'packaging'
    ],
    description="Automated installer for pyOptSparse",
    long_description="""pyOptSparse has several dependencies which can be tricky
    to build. This script attempts to automate the process as much as possible
    with command line arguments to customize the functionality.
    """,
    author='OpenMDAO Team',
    author_email='openmdao@openmdao.org',
    url='http://openmdao.org',
    py_modules=['build_pyoptsparse'],
    entry_points={
        'console_scripts': [
            'build-pyoptsparse = build_pyoptsparse:perform_install',
            'build_pyoptsparse = build_pyoptsparse:perform_install',
        ]
    },
    extras_require=optional_dependencies
)
