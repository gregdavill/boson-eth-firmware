#
# This file is part of LiteX.
#
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2014-2015 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2014-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2017 bunnie <bunnie@kosagi.com>
# Copyright (c) 2018-2017 Tim 'mithro' Ansell <me@mith.ro>
# Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2019 Larry Doolittle <ldoolitt@recycle.lbl.gov>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import sys
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.xilinx import common

# Constraints (.ucf) -------------------------------------------------------------------------------

def _format_constraint(c):
    if isinstance(c, Pins):
        return "LOC=" + c.identifiers[0]
    elif isinstance(c, IOStandard):
        return "IOSTANDARD=" + c.name
    elif isinstance(c, Drive):
        return "DRIVE=" + str(c.strength)
    elif isinstance(c, Misc):
        return c.misc

def _format_ucf(signame, pin, others, resname):
    fmt_c = []
    for c in [Pins(pin)] + others:
        fc = _format_constraint(c)
        if fc is not None:
            fmt_c.append(fc)
    fmt_r = resname[0] + ":" + str(resname[1])
    if resname[2] is not None:
        fmt_r += "." + resname[2]
    return "NET \"" + signame + "\" " + " | ".join(fmt_c) + "; # " + fmt_r + "\n"

def _build_ucf(named_sc, named_pc):
    r = ""
    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                r += _format_ucf(sig + "(" + str(i) + ")", p, others, resname)
        else:
            r += _format_ucf(sig, pins[0], others, resname)
    if named_pc:
        r += "\n" + "\n\n".join(named_pc)
    return r

# Project (.xst) -----------------------------------------------------------------------------------

def _build_xst(device, sources, vincpaths, build_name, xst_opt):
    prj_contents = ""
    for filename, language, library in sources:
        prj_contents += language + " " + library + " " + tools.cygpath(filename) + "\n"
    tools.write_to_file(build_name + ".prj", prj_contents)

    xst_contents = """run
-ifn {build_name}.prj
-top {build_name}
{xst_opt}
-ofn {build_name}.ngc
-p {device}
""".format(build_name=build_name, xst_opt=xst_opt, device=device)
    if vincpaths:
        xst_contents += "-vlgincdir {"
        for path in vincpaths:
            xst_contents += tools.cygpath(path) + " "
        xst_contents += "}"
    tools.write_to_file(build_name + ".xst", xst_contents)

# Yosys Run ----------------------------------------------------------------------------------------

def _run_yosys(device, sources, vincpaths, build_name):
    ys_contents = ""
    incflags = ""
    for path in vincpaths:
        incflags += " -I" + path
    for filename, language, library in sources:
        ys_contents += "read_{}{} {}\n".format(language, incflags, filename)

    family = ""
    if (device.startswith("xc7") or device.startswith("xa7") or device.startswith("xq7")):
        family = "xc7"
    elif (device.startswith("xc6s") or device.startswith("xa6s") or device.startswith("xq6s")):
        family = "xc6s"
    else:
        raise OSError("Unsupported device")

    ys_contents += """hierarchy -top top
synth_xilinx -top top -family {family} -ise
write_edif -pvector bra {build_name}.edif""".format(build_name=build_name, family=family)

    ys_name = build_name + ".ys"
    tools.write_to_file(ys_name, ys_contents)
    r = subprocess.call(["yosys", ys_name])
    if r != 0:
        raise OSError("Subprocess failed")

# ISE Run ------------------------------------------------------------------------------------------

def _run_ise(build_name, mode, ngdbuild_opt, toolchain, platform):
    if sys.platform == "win32" or sys.platform == "cygwin":
        script_ext = ".bat"
        shell = ["cmd", "/c"]
        build_script_contents = "@echo off\nrem Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n"
        fail_stmt = " || exit /b"
    else:
        script_ext = ".sh"
        shell = ["bash"]
        build_script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\nset -e\n"
        if os.getenv("LITEX_ENV_ISE", False):
            build_script_contents += "source " + os.path.join(os.getenv("LITEX_ENV_ISE"), "settings64.sh\n")
        fail_stmt = ""
    if mode == "edif":
        ext = "ngo"
        build_script_contents += """
edif2ngd {build_name}.edif {build_name}.{ext}{fail_stmt}
"""
    else:
        ext = "ngc"
        build_script_contents += """
xst -ifn {build_name}.xst{fail_stmt}
"""

    # This generates a .v file for post synthesis simulation
    build_script_contents += """
netgen -ofmt verilog -w -sim {build_name}.{ext} {build_name}_synth.v
"""

    build_script_contents += """
ngdbuild {ngdbuild_opt} -uc {build_name}.ucf {build_name}.{ext} {build_name}.ngd{fail_stmt}
"""
    if mode == "cpld":
        build_script_contents += """
cpldfit -ofmt verilog {par_opt} -p {device} {build_name}.ngd{fail_stmt}
taengine -f {build_name}.vm6 -detail -iopath -l {build_name}.tim{fail_stmt}
hprep6 -s IEEE1532 -i {build_name}.vm6{fail_stmt}
"""
    else:
        build_script_contents += """
map {map_opt} -o {build_name}_map.ncd {build_name}.ngd {build_name}.pcf{fail_stmt}
par {par_opt} {build_name}_map.ncd {build_name}.ncd {build_name}.pcf{fail_stmt}
bitgen {bitgen_opt} {build_name}.ncd {build_name}.bit{fail_stmt}
"""
    build_script_contents = build_script_contents.format(build_name=build_name,
            ngdbuild_opt=ngdbuild_opt, bitgen_opt=toolchain.bitgen_opt, ext=ext,
            par_opt=toolchain.par_opt, map_opt=toolchain.map_opt,
            device=platform.device, fail_stmt=fail_stmt)
    build_script_contents += toolchain.ise_commands.format(build_name=build_name)
    build_script_file = "build_" + build_name + script_ext
    tools.write_to_file(build_script_file, build_script_contents, force_unix=False)
    command = shell + [build_script_file]

    if which("ise") is None and os.getenv("LITEX_ENV_ISE", False) == False:
        msg = "Unable to find or source ISE toolchain, please either:\n"
        msg += "- Source ISE's settings manually.\n"
        msg += "- Or set LITEX_ENV_ISE environment variant to ISE's settings path.\n"
        msg += "- Or add ISE toolchain to your $PATH."
        raise OSError(msg)

    if tools.subprocess_call_filtered(command, common.colors) != 0:
        raise OSError("Error occured during ISE's script execution.")

# XilinxISEToolchain --------------------------------------------------------------------------------

class XilinxISEToolchain:
    attr_translate = {
        "keep":             ("keep", "true"),
        "no_retiming":      ("register_balancing", "no"),
        "async_reg":        None,
        "mr_ff":            None,
        "ars_ff1":          None,
        "ars_ff2":          None,
        "no_shreg_extract": ("shreg_extract", "no")
    }

    def __init__(self):
        self.xst_opt = "-ifmt MIXED\n-use_new_parser yes\n-opt_mode SPEED\n-register_balancing yes"
        self.map_opt = "-ol high -w"
        self.par_opt = "-ol high -w"
        self.ngdbuild_opt = ""
        self.bitgen_opt   = "-g Binary:Yes -w"
        self.ise_commands = ""

    def build(self, platform, fragment,
        build_dir      = "build",
        build_name     = "top",
        run            = True,
        mode           = "xst",
        **kwargs):

        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # Finalize design
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        vns = None
        try:
            if mode in ["xst", "yosys", "cpld"]:
                # Generate verilog
                v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
                vns = v_output.ns
                named_sc, named_pc = platform.resolve_signals(vns)
                v_file = build_name + ".v"
                v_output.write(v_file)
                platform.add_source(v_file)

                # Generate design project (.xst)
                if mode in ["xst", "cpld"]:
                    _build_xst(platform.device, platform.sources, platform.verilog_include_paths, build_name, self.xst_opt)
                    isemode = mode
                else:
                    # Run Yosys
                    if run:
                        _run_yosys(platform.device, platform.sources, platform.verilog_include_paths, build_name)
                    isemode = "edif"
                    self.ngdbuild_opt += "-p " + platform.device

            if mode in ["edif"]:
                # Generate edif
                e_output = platform.get_edif(fragment)
                vns = e_output.ns
                named_sc, named_pc = platform.resolve_signals(vns)
                e_file = build_name + ".edif"
                e_output.write(e_file)
                isemode = "edif"

            # Generate design constraints (.ucf)
            tools.write_to_file(build_name + ".ucf", _build_ucf(named_sc, named_pc))

            # Run ISE
            if run:
                _run_ise(build_name, isemode, self.ngdbuild_opt, self, platform)
        finally:
            os.chdir(cwd)

        return vns

    # ISE is broken and you must use *separate* TNM_NET objects for period
    # constraints and other constraints otherwise it will be unable to trace
    # them through clock objects like DCM and PLL objects.

    def add_period_constraint(self, platform, clk, period):
        clk.attr.add("keep")
        platform.add_platform_command(
            """
NET "{clk}" TNM_NET = "PRD{clk}";
TIMESPEC "TS{clk}" = PERIOD "PRD{clk}" """ + str(period) + """ ns HIGH 50%;
""",
            clk=clk,
            )

    def add_false_path_constraint(self, platform, from_, to):
        from_.attr.add("keep")
        to.attr.add("keep")
        platform.add_platform_command(
            """
NET "{from_}" TNM_NET = "TIG{from_}";
NET "{to}" TNM_NET = "TIG{to}";
TIMESPEC "TS{from_}TO{to}" = FROM "TIG{from_}" TO "TIG{to}" TIG;
""",
            from_=from_,
            to=to,
            )
