from distutils.core import setup
from setuptools import find_packages

setup(name='build_pyoptsparse',
    version='0.1',
    license='Apache License',
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        'ansicolor',
        'numpy',
        'sqlitedict'
    ],
    description="Automated installer for pyOptSparse",
    long_description="""pyOptSparse has several dependencies which can be tricky
    to build. This script attempts to automate the process as much as possible
    with command line arguments to customize the functionality.
    """,
    author='OpenMDAO Team',
    author_email='openmdao@openmdao.org',
    url='http://openmdao.org',
    package_data={
        'build_pyoptsparse': [ 'build_pyoptsparse.py' ]
    },
    entry_points={
        'console_scripts': [
            'build-pyoptsparse = build_pyoptsparse:perform_install',
            'build_pyoptsparse = build_pyoptsparse:perform_install',
        ]
    }
)
