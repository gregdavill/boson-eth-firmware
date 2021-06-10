#!/usr/bin/env python3
import os

import pythondata_software_compiler_rt

print("Found compiler_rt @ version", pythondata_software_compiler_rt.version_str, "(with data", pythondata_software_compiler_rt.data_version_str, ")")
print()
print("Data is in", pythondata_software_compiler_rt.data_location)
assert os.path.exists(pythondata_software_compiler_rt.data_location)
print("Data is version", pythondata_software_compiler_rt.data_version_str, pythondata_software_compiler_rt.data_git_hash)
print("-"*75)
print(pythondata_software_compiler_rt.data_git_msg)
print("-"*75)
print()
print("It contains:")
for root, dirs, files in os.walk(pythondata_software_compiler_rt.data_location):
    dirs.sort()
    for f in sorted(files):
        path = os.path.relpath(os.path.join(root, f), pythondata_software_compiler_rt.data_location)
        print(" -", path)
