import os.path
__dir__ = os.path.split(os.path.abspath(os.path.realpath(__file__)))[0]
data_location = os.path.join(__dir__, "data")
src = "https://git.llvm.org/git/compiler-rt.git/"

# Module version
version_str = "0.0.post6206"
version_tuple = (0, 0, 6206)
try:
    from packaging.version import Version as V
    pversion = V("0.0.post6206")
except ImportError:
    pass

# Data version info
data_version_str = "0.0.post6140"
data_version_tuple = (0, 0, 6140)
try:
    from packaging.version import Version as V
    pdata_version = V("0.0.post6140")
except ImportError:
    pass
data_git_hash = "81fb4f00c2cfe13814765968e09931ffa93b5138"
data_git_describe = "v0.0-6140-g81fb4f00c"
data_git_msg = """\
commit 81fb4f00c2cfe13814765968e09931ffa93b5138
Author: Chris Bieneman <beanz@apple.com>
Date:   Fri Nov 6 23:19:29 2015 +0000

    [CMake] Need to filter ${arch}/*.c builtins as well as ${arch}/*.S builtins.
    
    This was broken in r248542 when I refactored this to support builtins where ${arch} didn't match the directory prefix (i.e. armv7s).
    
    git-svn-id: https://llvm.org/svn/llvm-project/compiler-rt/trunk@252365 91177308-0d34-0410-b5e6-96231b3b80d8

"""

# Tool version info
tool_version_str = "0.0.post66"
tool_version_tuple = (0, 0, 66)
try:
    from packaging.version import Version as V
    ptool_version = V("0.0.post66")
except ImportError:
    pass


def data_file(f):
    """Get absolute path for file inside pythondata_software_compiler_rt."""
    fn = os.path.join(data_location, f)
    fn = os.path.abspath(fn)
    if not os.path.exists(fn):
        raise IOError("File {f} doesn't exist in pythondata_software_compiler_rt".format(f))
    return fn
