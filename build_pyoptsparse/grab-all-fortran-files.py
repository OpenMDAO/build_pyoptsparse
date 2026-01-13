#!/usr/bin/env python

# Standard Python modules
import os
from pathlib import Path

CURDIR = os.path.abspath(os.path.dirname(__file__))

TO_SKIP = [
    "snopth.f",     # Exclude this file
]

all_source_files = list(Path(CURDIR).glob("*.f"))

if "sn27lu.f" in all_source_files:
    TO_SKIP.extend([ "sn27lu77.f",  "sn27lu90.f"])
elif "sn27lu90.f" in all_source_files:
    TO_SKIP.append("sn27lu77.f")

for path in all_source_files:
    if os.path.basename(path) not in TO_SKIP:
        print(path)
