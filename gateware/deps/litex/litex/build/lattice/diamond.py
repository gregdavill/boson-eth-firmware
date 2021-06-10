#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017-2018 Sergiusz Bazanski <q3k@q3k.org>
# Copyright (c) 2017 William D. Jones <thor0505@comcast.net>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import sys
import math
import subprocess
import shutil
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.gen.fhdl.verilog import DummyAttrTranslate

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.lattice import common

# Helpers ------------------------------------------------------------------------------------------

def _produces_jedec(device):
    return device.startswith("LCMX")

# Constraints (.lpf) -------------------------------------------------------------------------------

def _format_constraint(c):
    if isinstance(c, Pins):
        return ("LOCATE COMP ", " SITE " + "\"" + c.identifiers[0] + "\"")
    elif isinstance(c, IOStandard):
        return ("IOBUF PORT ", " IO_TYPE=" + c.name)
    elif isinstance(c, Misc):
        return ("IOBUF PORT ", " " + c.misc)


def _format_lpf(signame, pin, others, resname):
    fmt_c = [_format_constraint(c) for c in ([Pins(pin)] + others)]
    lpf = []
    for pre, suf in fmt_c:
        lpf.append(pre + "\"" + signame + "\"" + suf + ";")
    return "\n".join(lpf)


def _build_lpf(named_sc, named_pc, clocks, vns, build_name):
    lpf = []
    lpf.append("BLOCK RESETPATHS;")
    lpf.append("BLOCK ASYNCPATHS;")
    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                lpf.append(_format_lpf(sig + "[" + str(i) + "]", p, others, resname))
        else:
            lpf.append(_format_lpf(sig, pins[0], others, resname))
    if named_pc:
        lpf.append("\n".join(named_pc))

    # Note: .lpf is only used post-synthesis, Synplify constraints clocks by default to 200MHz.
    for clk, period in clocks.items():
        clk_name = vns.get_name(clk)
        lpf.append("FREQUENCY {} \"{}\" {} MHz;".format(
            "PORT" if clk_name in [name for name, _, _, _ in named_sc] else "NET",
            clk_name,
            str(1e3/period)))

    tools.write_to_file(build_name + ".lpf", "\n".join(lpf))

# Project (.tcl) -----------------------------------------------------------------------------------

def _build_tcl(device, sources, vincpaths, build_name):
    tcl = []
    # Create project
    tcl.append(" ".join([
        "prj_project",
        "new -name \"{}\"".format(build_name),
        "-impl \"impl\"",
        "-dev {}".format(device),
        "-synthesis \"synplify\""
    ]))

    def tcl_path(path): return path.replace("\\", "/")

    # Add include paths
    vincpath = ";".join(map(lambda x: tcl_path(x), vincpaths))
    tcl.append("prj_impl option {include path} {\"" + vincpath + "\"}")

    # Add sources
    for filename, language, library in sources:
        tcl.append("prj_src add \"{}\" -work {}".format(tcl_path(filename), library))

    # Set top level
    tcl.append("prj_impl option top \"{}\"".format(build_name))

    # Save project
    tcl.append("prj_project save")

    # Build flow
    tcl.append("prj_run Synthesis -impl impl -forceOne")
    tcl.append("prj_run Translate -impl impl")
    tcl.append("prj_run Map -impl impl")
    tcl.append("prj_run PAR -impl impl")
    tcl.append("prj_run Export -impl impl -task Bitgen")
    if _produces_jedec(device):
        tcl.append("prj_run Export -impl impl -task Jedecgen")

    # Close project
    tcl.append("prj_project close")

    tools.write_to_file(build_name + ".tcl", "\n".join(tcl))

# Script -------------------------------------------------------------------------------------------

def _build_script(build_name, device):
    on_windows = sys.platform in ("win32", "cygwin")
    if on_windows:
        script_ext = ".bat"
        script_contents = "@echo off\nrem Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n\n"
        copy_stmt = "copy"
        fail_stmt = " || exit /b"
    else:
        script_ext = ".sh"
        script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\nset -e\n"
        copy_stmt = "cp"
        fail_stmt = ""

    script_contents += "{tool} {tcl_script}{fail_stmt}\n".format(
        tool = "pnmainc" if on_windows else "diamondc",
        tcl_script = build_name + ".tcl",
        fail_stmt  = fail_stmt)
    for ext in (".bit", ".jed"):
        if ext == ".jed" and not _produces_jedec(device):
            continue
        script_contents += "{copy_stmt} {diamond_product} {migen_product} {fail_stmt}\n".format(
            copy_stmt       = copy_stmt,
            fail_stmt       = fail_stmt,
            diamond_product = os.path.join("impl", build_name + "_impl" + ext),
            migen_product   = build_name + ext)

    build_script_file = "build_" + build_name + script_ext
    tools.write_to_file(build_script_file, script_contents, force_unix=False)
    return build_script_file

def _run_script(script):
    on_windows = sys.platform in ("win32", "cygwin")
    if on_windows:
        shell = ["cmd", "/c"]
    else:
        shell = ["bash"]

    if which("pnmainc" if on_windows else "diamondc") is None:
        msg = "Unable to find Diamond toolchain, please:\n"
        msg += "- Add Diamond toolchain to your $PATH.\n"
        raise OSError(msg)

    if subprocess.call(shell + [script]) != 0:
        raise OSError("Error occured during Diamond's script execution.")

def _check_timing(build_name):
    lines = open("impl/{}_impl.par".format(build_name), "r").readlines()
    runs = [None, None]
    for i in range(len(lines)-1):
        if lines[i].startswith("Level/") and lines[i+1].startswith("Cost "):
            runs[0] = i + 2
        if lines[i].startswith("* : Design saved.") and runs[0] is not None:
            runs[1] = i
            break
    assert all(map(lambda x: x is not None, runs))

    p = re.compile(r"(^\s*\S+\s+\*?\s+[0-9]+\s+)(\S+)(\s+\S+\s+)(\S+)(\s+.*)")
    for l in lines[runs[0]:runs[1]]:
        m = p.match(l)
        if m is None: continue
        limit = 1e-8
        setup = m.group(2)
        hold  = m.group(4)
        # If there were no freq constraints in lpf, ratings will be dashed.
        # results will likely be terribly unreliable, so bail
        assert not setup == hold == "-", "No timing constraints were provided"
        setup, hold = map(float, (setup, hold))
        if setup > limit and hold > limit:
            # At least one run met timing
            # XXX is this necessarily the run from which outputs will be used?
            return
    raise Exception("Failed to meet timing")

# LatticeDiamondToolchain --------------------------------------------------------------------------

class LatticeDiamondToolchain:
    attr_translate = {
        # FIXME: document
        "keep":             ("syn_keep", "true"),
        "no_retiming":      ("syn_no_retiming", "true"),
        "async_reg":        None,
        "mr_ff":            None,
        "mr_false_path":    None,
        "ars_ff1":          None,
        "ars_ff2":          None,
        "ars_false_path":   None,
        "no_shreg_extract": None
    }

    special_overrides = common.lattice_ecp5_special_overrides

    def __init__(self):
        self.clocks      = {}
        self.false_paths = set() # FIXME: use it

    def build(self, platform, fragment,
        build_dir      = "build",
        build_name     = "top",
        run            = True,
        timingstrict   = False,
        **kwargs):

        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # Finalize design
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        # Generate verilog
        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        named_sc, named_pc = platform.resolve_signals(v_output.ns)
        v_file = build_name + ".v"
        v_output.write(v_file)
        platform.add_source(v_file)

        # Generate design constraints file (.lpf)
        _build_lpf(named_sc, named_pc, self.clocks, v_output.ns, build_name)

        # Generate design script file (.tcl)
        _build_tcl(platform.device, platform.sources, platform.verilog_include_paths, build_name)

        # Generate build script
        script = _build_script(build_name, platform.device)

        # Run
        if run:
            _run_script(script)
            if timingstrict:
                _check_timing(build_name)

        os.chdir(cwd)

        return v_output.ns

    def add_period_constraint(self, platform, clk, period):
        clk.attr.add("keep")
        period = math.floor(period*1e3)/1e3 # round to lowest picosecond
        if clk in self.clocks:
            if period != self.clocks[clk]:
                raise ValueError("Clock already constrained to {:.2f}ns, new constraint to {:.2f}ns"
                    .format(self.clocks[clk], period))
        self.clocks[clk] = period

    def add_false_path_constraint(self, platform, from_, to):
        from_.attr.add("keep")
        to.attr.add("keep")
        if (to, from_) not in self.false_paths:
            self.false_paths.add((from_, to))