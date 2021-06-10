#!/usr/bin/env python3

# This file is Copyright (c) 2021 Gregory Davill <greg.davill@gmail.com>
# License: BSD

# This variable defines all the external programs that this module
# relies on.  lxbuildenv reads this variable in order to ensure
# the build will finish without exiting due to missing third-party
# programs.
LX_DEPENDENCIES = ["riscv", "nextpnr-ecp5", "yosys"]

# Import lxbuildenv to integrate the deps/ directory
import lxbuildenv

import argparse
import subprocess
import os

from migen import *

from rtl.platform import butterstick_r1d0



from migen.genlib.resetsync import AsyncResetSynchronizer
from litex.build.generic_platform import *
from litex.soc.cores.clock import *
from rtl.ecp5_dynamic_pll import ECP5PLL, period_ns
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import *

from litex.soc.cores.bitbang import I2CMaster

from litex.soc.interconnect.stream import StrideConverter, SyncFIFO
from litex.soc.interconnect.csr import *


from litex.soc.cores.led import LedChaser

from liteeth.core import LiteEthMAC
from liteeth.phy.ecp5rgmii import LiteEthPHYRGMII

from litedram.modules import MT41K256M16
from litedram.phy import ECP5DDRPHY
from litedram.frontend.dma import LiteDRAMDMAReader

from rtl.video.DMACapture import DMAVideoCapture
from litex.soc.interconnect.packet import Packetizer


class idxCSR(Module, AutoCSR):
    def __init__(self):       
        # CSR control
        self.value = CSRStorage(16)
        self.level = CSRStorage(16)



class _CRG(Module, AutoCSR):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_init     = ClockDomain()
        self.clock_domains.cd_por      = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys      = ClockDomain()
        self.clock_domains.cd_sys2x    = ClockDomain()
        self.clock_domains.cd_sys2x_i  = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys2x_eb = ClockDomain(reset_less=True)

        # # #

        self.stop  = Signal()
        self.reset = Signal()

        # Clk / Rst
        clk30 = platform.request("clk30")
        rst_n = platform.request("user_btn")
        platform.add_period_constraint(clk30, period_ns(30e6))

        # Power on reset
        por_count = Signal(16, reset=2**16-1)
        por_done  = Signal()
        self.comb += self.cd_por.clk.eq(clk30)
        self.comb += por_done.eq(por_count == 0)
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # PLL
        sys2x_clk_ecsout = Signal()
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~por_done | ~rst_n)
        pll.register_clkin(clk30, 30e6)
        pll.create_clkout(self.cd_sys2x_i, 2*sys_clk_freq)
        pll.create_clkout(self.cd_init, 15e6)
        self.specials += [
            Instance("ECLKBRIDGECS",
                i_CLK0   = self.cd_sys2x_i.clk,
                i_SEL    = 0,
                o_ECSOUT = sys2x_clk_ecsout),
            Instance("ECLKSYNCB",
                i_ECLKI = sys2x_clk_ecsout,
                i_STOP  = self.stop,
                o_ECLKO = self.cd_sys2x.clk),
            Instance("CLKDIVF",
                p_DIV     = "2.0",
                i_ALIGNWD = 0,
                i_CLKI    = self.cd_sys2x.clk,
                i_RST     = self.reset,
                o_CDIVX   = self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_sys,   ~pll.locked | self.reset),
            AsyncResetSynchronizer(self.cd_sys2x, ~pll.locked | self.reset),
        ]
       

from litex.soc.interconnect.packet import Header, HeaderField
from litex.soc.interconnect.stream import EndpointDescription

ipv4_header_length = 20 + 8 + 2
ipv4_header_fields = {
    #"target_mac":    HeaderField(0,  0, 48),
    #"sender_mac":    HeaderField(6,  0, 48),
    #"ethernet_type": HeaderField(12, 0, 16),
    
    "ihl":            HeaderField(0,  0,  4),
    "version":        HeaderField(0,  4,  4),
    "total_length":   HeaderField(2,  0, 16),
    "identification": HeaderField(4,  0, 16),
    "ttl":            HeaderField(8,  0,  8),
    "protocol":       HeaderField(9,  0,  8),
    "checksum":       HeaderField(10, 0, 16),
    "sender_ip":      HeaderField(12, 0, 32),
    "target_ip":      HeaderField(16, 0, 32),
    
    "src_port":     HeaderField(20+0, 0, 16),
    "dst_port":     HeaderField(20+2, 0, 16),
    "length":       HeaderField(20+4, 0, 16),
    "udp_checksum": HeaderField(20+6, 0, 16),
    "idx": HeaderField(20+8, 0, 16),
    
}
udp_header = Header(ipv4_header_fields, ipv4_header_length, swap_field_bytes=True)


def ip_udp_description(dw):
    param_layout = udp_header.get_layout()
    payload_layout = [
        ("data",     dw),
        ("last_be",  dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout)

class ethSoC(SoCCore):
    csr_map = {
        "rgb"        :  10, 
        "crg"        :  11, 
        "ethmac"     :  12,
        "ethphy"     :  13,
        "boson"      :  14,
        "i2c"        :  15,
        "res_detect":  16,
        "frame_extract":  17,
        "video_latch"         : 19,
        "dma0"        :  18,
        "dma1"        :  20,
        "csr_idx"       : 21,
        
    }
    csr_map.update(SoCCore.csr_map)

    mem_map = { 
        "ethmac"    : 0x81000000,
    }
    mem_map.update(SoCCore.mem_map)

    interrupt_map = {
        "ethmac"   : 2,
    }
    interrupt_map.update(SoCCore.interrupt_map)

    def __init__(self):
        
        self.platform = platform = butterstick_r1d0.ButterStickPlatform()
        platform.add_extension(butterstick_r1d0._uart_debug)
        platform.add_extension(butterstick_r1d0._i2c)
        platform.add_extension(butterstick_r1d0._syzygy_boson)
        
        ethernet = True
        sdram = True

        # crg
        platform.sys_clk_freq = sys_clk_freq = 60e6
        self.submodules.crg = _CRG(platform, sys_clk_freq)
        
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq,
                          cpu_type='vexriscv', with_uart=True, # uart_name='stream',
                          csr_data_width=32,
                          ident="Boson Ethernet SoC", ident_version=True, wishbone_timeout_cycles=128,
                          integrated_rom_size=64*1024, 
                          integrated_sram_size=16*1024)

        self.submodules.i2c = I2CMaster(platform.request("i2c"))

        if sdram:
            ddram_pads = platform.request("ddram")
            self.submodules.ddrphy = ECP5DDRPHY(
                pads         = ddram_pads,
                sys_clk_freq = sys_clk_freq,
                #dm_remapping = {0:1, 1:0}
                )
            self.ddrphy.settings.rtt_nom = "disabled"
            self.add_csr("ddrphy")
            if hasattr(ddram_pads, "vccio"):
                self.comb += ddram_pads.vccio.eq(0b111111)
            if hasattr(ddram_pads, "gnd"):
                self.comb += ddram_pads.gnd.eq(0)
            self.comb += self.crg.stop.eq(self.ddrphy.init.stop)
            self.comb += self.crg.reset.eq(self.ddrphy.init.reset)
            self.add_sdram("sdram",
                phy                     = self.ddrphy,
                module                  = MT41K256M16(sys_clk_freq, "1:2"),
                origin                  = self.mem_map["main_ram"],
                size                    = 0x80000000,
                l2_cache_size           = 8192,
                l2_cache_min_data_width = 128,
                l2_cache_reverse        = True
            )
            
            
            self.submodules.dma0 = dma0 = DMAVideoCapture(platform, self.sdram.crossbar.get_port())
            self.submodules.dma1 = dma1 = LiteDRAMDMAReader(self.sdram.crossbar.get_port(), with_csr=True)
        


        self.platform.toolchain.build_template[0] = "yosys -q -l {build_name}.rpt {build_name}.ys"
        self.platform.toolchain.build_template[1] += f" --router router1"

        # Blue LEDs only
        led = platform.request("led")
        self.comb += led.c.eq(2)

        # ButterStick r1.0 requires 
        # VccIO set on port 2 before ULPI signals work.
        vccio_pins = platform.request("vccio_ctrl")
        pwm_timer = Signal(14)
        self.sync += pwm_timer.eq(pwm_timer + 1)
        self.comb += [
            vccio_pins.pdm[0].eq(pwm_timer < int(2**14 * (0.70))),  # 1.8v
            vccio_pins.pdm[1].eq(pwm_timer < int(2**14 * (0.15))),  # 3.3v
            vccio_pins.pdm[2].eq(pwm_timer < int(2**14 * (0.15))), # 3.3v
        ]

        counter = Signal(32)
        self.sync += [
            counter.eq(counter + 1),
            If(counter[21] == 1,
                vccio_pins.en.eq(1),
            )
        ]
        
        if ethernet:
            # ethernet mac/udp/ip stack
            self.submodules.ethphy = ethphy = LiteEthPHYRGMII(platform.request("eth_clk"),
                            platform.request("eth"))

            
            platform.add_period_constraint(ClockSignal('eth_rx'), period_ns(125e6))
            platform.add_period_constraint(ClockSignal('eth_tx'), period_ns(125e6))

            # MAC
            self.submodules.ethmac = ethmac = LiteEthMAC(
                phy        = ethphy,
                dw         = 32,
                interface  = "hybrid",
                endianness = self.cpu.endianness,
                hw_mac=None)
            
            ethmac_region = SoCRegion(origin=self.mem_map.get("ethmac", None), size=0x2000, cached=False)
            self.bus.add_slave(name="ethmac", slave=ethmac.bus, region=ethmac_region)

            if hasattr(ethmac, "crossbar"):
                port = ethmac.crossbar.get_port(0, dw=32)

                #from eth_packet_streamer import EthPacketStreamer
                #self.submodules.eps = eps = EthPacketStreamer()

                sc = StrideConverter([('data', len(dma1.source.data))], [('data', 32)], reverse=True)
                self.submodules += sc

                self.submodules.fifo0 = fifo = SyncFIFO([('data', 32)], 512)

                self.submodules.packet = p = Packetizer(ip_udp_description(32), [('data', 32), ('last_be', 4)], udp_header)       


                self.submodules.csr_idx = idxCSR()

                en = Signal()

                self.comb += [
                    dma1.source.connect(sc.sink),
                    sc.source.connect(fifo.sink),

                    fifo.source.connect(p.sink, omit={"valid", "ready"}),

                    p.sink.valid.eq(fifo.source.valid & en),
                    fifo.source.ready.eq(p.sink.ready & en),

                    p.source.connect(port.sink),

                    port.sink.target_mac.eq(0xa0cec8d5873d),
                    port.sink.sender_mac.eq(0x10e2d5000001),
                    port.sink.ethernet_type.eq(0x0800),
                    p.sink.ihl.eq(5),
                    p.sink.version.eq(4),
                    p.sink.total_length.eq(1306),
                    p.sink.identification.eq(0),
                    p.sink.ttl.eq(64),
                    p.sink.protocol.eq(17),
                    p.sink.checksum.eq(0xf1ec),
                    p.sink.sender_ip.eq(0xc0a80132),
                    p.sink.target_ip.eq(0xc0a80164),

                    p.sink.src_port.eq(32765),
                    p.sink.dst_port.eq(9001),
                    p.sink.length.eq(1286),
                    p.sink.udp_checksum.eq(0),
                    p.sink.idx.eq(self.csr_idx.value.storage),

                    
                    #eps.source.connect(port.sink),
                    # Add dummy RX path
                    port.source.ready.eq(1),
                ]

                self.sync += [
                    If(~en,
                        If(fifo.level >= self.csr_idx.level.storage,
                            en.eq(1),
                        )
                    ).Elif(fifo.level == 0,
                        en.eq(0),
                    )
                ]

                self.comb += [
                    If(en & (fifo.level == 1),
                        p.sink.last.eq(1),
                        p.sink.last_be.eq(0b1000),
                    )
                ]
    

        # Leds -------------------------------------------------------------------------------------
        self.submodules.leds = LedChaser(
            pads         = platform.request_all("user_led"),
            sys_clk_freq = sys_clk_freq)
        self.add_csr("leds")


        # Add git version into firmware 
        def get_git_revision():
            try:
                r = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                        stderr=subprocess.DEVNULL)[:-1].decode("utf-8")
            except:
                r = "--------"
            return r
        self.add_constant("FW_GIT_SHA1", get_git_revision())

    def do_exit(self, vns):
        if hasattr(self, "analyzer"):
            self.analyzer.export_csv(vns, "test/analyzer.csv")


    def PackageFirmware(self, builder):  
        self.finalize()

        os.makedirs(builder.output_dir, exist_ok=True)

        builder.add_software_package("uip", "{}/../firmware/uip".format(os.getcwd()))
        builder.add_software_package("main-fw", "{}/../firmware/main-fw".format(os.getcwd()))

        builder._prepare_rom_software()
        builder._generate_includes()
        builder._generate_rom_software(compile_bios=False)
        
        firmware_file = os.path.join(builder.output_dir, "software", "main-fw","main-fw.bin")
        firmware_data = get_mem_data(firmware_file, self.cpu.endianness)
        self.initialize_rom(firmware_data)

        # lock out compiling firmware during build steps
        builder.compile_software = False


def CreateFirmwareInit(init, output_file):
    content = ""
    for d in init:
        content += "{:08x}\n".format(d)
    with open(output_file, "w") as o:
        o.write(content)    
     
def main():
    parser = argparse.ArgumentParser(
        description="Build DiVA Gateware")
    parser.add_argument(
        "--update-firmware", default=False, action='store_true',
        help="compile firmware and update existing gateware"
    )
    args = parser.parse_args()

    soc = ethSoC()
    builder = Builder(soc, output_dir="build", csr_csv="build/csr.csv")


    # Build firmware
    soc.PackageFirmware(builder)
        

    # Check if we have the correct files
    firmware_file = os.path.join(builder.output_dir, "software", "main-fw", "main-fw.bin")
    firmware_data = get_mem_data(firmware_file, soc.cpu.endianness)
    firmware_init = os.path.join(builder.output_dir, "software", "main-fw", "main-fw.init")
    CreateFirmwareInit(firmware_data, firmware_init)
    
    rand_rom = os.path.join(builder.output_dir, "gateware", "rand.data")
    
    input_config = os.path.join(builder.output_dir, "gateware", f"{soc.platform.name}.config")
    output_config = os.path.join(builder.output_dir, "gateware", f"{soc.platform.name}_patched.config")
    
    # If we don't have a random file, create one, and recompile gateware
    if (os.path.exists(rand_rom) == False) or (args.update_firmware == False):
        os.makedirs(os.path.join(builder.output_dir,'gateware'), exist_ok=True)
        os.makedirs(os.path.join(builder.output_dir,'software'), exist_ok=True)

        os.system(f"ecpbram  --generate {rand_rom} --seed {0} --width {32} --depth {soc.integrated_rom_size // 4}")

        # patch random file into BRAM
        data = []
        with open(rand_rom, 'r') as inp:
            for d in inp.readlines():
                data += [int(d, 16)]
        soc.initialize_rom(data)

        # Build gateware
        vns = builder.build(nowidelut=False)
        soc.do_exit(vns)    


    # Insert Firmware into Gateware
    os.system(f"ecpbram  --input {input_config} --output {output_config} --from {rand_rom} --to {firmware_init}")

    # create a compressed bitstream
    output_bit = os.path.join(builder.output_dir, "gateware", "boson-eth.dfu")
    os.system(f"ecppack --freq 38.8 --compress --input {output_config} --bit {output_bit}")

    # Add DFU suffix
    os.system(f"dfu-suffix -p 16d0 -d 0fad -a {output_bit}")

    print(
    f"""Boson Ethernet build complete!  Output files:
    
    Bitstream file. (Compressed, Higher CLK)  Load this into FLASH.
        {builder.output_dir}/gateware/boson-eth.dfu
    """)



if __name__ == "__main__":
    main()




