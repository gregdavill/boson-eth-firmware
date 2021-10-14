import os.path
__dir__ = os.path.split(os.path.abspath(os.path.realpath(__file__)))[0]
data_location = os.path.join(__dir__, "data")
src = "https://github.com/picolibc/picolibc"

# Module version
version_str = "0.0.post21383"
version_tuple = (0, 0, 21383)
try:
    from packaging.version import Version as V
    pversion = V("0.0.post21383")
except ImportError:
    pass

# Data version info
data_version_str = "0.0.post21271"
data_version_tuple = (0, 0, 21271)
try:
    from packaging.version import Version as V
    pdata_version = V("0.0.post21271")
except ImportError:
    pass
data_git_hash = "1dacd304c2f0f5b5e8abe664d63cd31f68cd3ea6"
data_git_describe = "v0.0-21271-g1dacd304c"
data_git_msg = """\
commit 1dacd304c2f0f5b5e8abe664d63cd31f68cd3ea6
Author: Keith Packard <keithp@keithp.com>
Date:   Thu Oct 14 10:21:14 2021 -0700

    newlib: Use PICOLIBC_TLS instead of NEWLIB_TLS
    
    There's just one place in the tree using NEWLIB_TLS
    
    Signed-off-by: Keith Packard <keithp@keithp.com>

"""

# Tool version info
tool_version_str = "0.0.post112"
tool_version_tuple = (0, 0, 112)
try:
    from packaging.version import Version as V
    ptool_version = V("0.0.post112")
except ImportError:
    pass


def data_file(f):
    """Get absolute path for file inside pythondata_software_picolibc."""
    fn = os.path.join(data_location, f)
    fn = os.path.abspath(fn)
    if not os.path.exists(fn):
        raise IOError("File {f} doesn't exist in pythondata_software_picolibc".format(f))
    return fn
