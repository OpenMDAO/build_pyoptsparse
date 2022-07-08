from distutils.core import setup
from setuptools import find_packages

setup(name='build_pyoptsparse',
    version='0.1',
    license='Apache License',
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        'ansicolor',
    ],
