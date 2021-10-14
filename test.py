#!/usr/bin/env python3

from __future__ import print_function

import os

import pythondata_software_picolibc

print("Found picolibc @ version", pythondata_software_picolibc.version_str, "(with data", pythondata_software_picolibc.data_version_str, ")")
print()
print("Data is in", pythondata_software_picolibc.data_location)
assert os.path.exists(pythondata_software_picolibc.data_location)
print("Data is version", pythondata_software_picolibc.data_version_str, pythondata_software_picolibc.data_git_hash)
print("-"*75)
print(pythondata_software_picolibc.data_git_msg)
print("-"*75)
print()
print("It contains:")
for root, dirs, files in os.walk(pythondata_software_picolibc.data_location):
    dirs.sort()
    for f in sorted(files):
        path = os.path.relpath(os.path.join(root, f), pythondata_software_picolibc.data_location)
        print(" -", path)
