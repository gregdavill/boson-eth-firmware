from migen import *

from litex.soc.interconnect.stream import *

from litedram.common import LiteDRAMNativePort

from litevideo.output.core import VideoOutCore

from litedram.frontend.dma import LiteDRAMDMAWriter, LiteDRAMDMAReader

from litex.soc.interconnect.packet import Packetizer

from litex.soc.interconnect.packet import Header, HeaderField
from litex.compat.stream_sim import *

from liteeth.common import *
from liteeth.core import  LiteEthMAC

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
    "idx":          HeaderField(20+8, 0, 16),
    
}
udp_header = Header(ipv4_header_fields, ipv4_header_length, swap_field_bytes=True)

def ip_udp_description(dw):
    param_layout = udp_header.get_layout()
    payload_layout = [
        ("data",     dw),
        ("last_be",  dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout)


# Helpers ------------------------------------------------------------------------------------------

def print_phy(s):
    print_with_prefix(s, "[PHY]")


# PHY Source ---------------------------------------------------------------------------------------

class PHYSource(PacketStreamer):
    def __init__(self, dw):
        PacketStreamer.__init__(self, eth_phy_description(dw))

# PHY Sink -----------------------------------------------------------------------------------------

class PHYSink(PacketLogger):
    def __init__(self, dw):
        PacketLogger.__init__(self, eth_phy_description(dw))

# PHY ----------------------------------------------------------------------------------------------

class PHY(Module):
    def __init__(self, dw, debug=False):
        self.dw    = dw
        self.debug = debug

        self.submodules.phy_source = PHYSource(dw)
        self.submodules.phy_sink   = PHYSink(dw)

        self.source = self.phy_source.source
        self.sink   = self.phy_sink.sink

        self.mac_callback = None

    def set_mac_callback(self, callback):
        self.mac_callback = callback

    def send(self, datas):
        packet = Packet(datas)
        if self.debug:
            r = ">>>>>>>>\n"
            r += "length " + str(len(datas)) + "\n"
            for d in datas:
                r += "{:02x}".format(d)
            print_phy(r)
        self.phy_source.send(packet)

    def receive(self):
        yield from self.phy_sink.receive()
        if self.debug:
            r = "<<<<<<<<\n"
            r += "length " + str(len(self.phy_sink.packet)) + "\n"
            for d in self.phy_sink.packet:
                r += "{:02x}".format(d)
            print_phy(r)
        self.packet = self.phy_sink.packet

    @passive
    def generator(self):
        while True:
            yield from self.receive()
            if self.mac_callback is not None:
                self.mac_callback(self.packet)



class TB(Module):
    def __init__(self):
        self.dram_port = LiteDRAMNativePort(mode="read", address_width=32, data_width=32, clock_domain="sys")
        

        self.submodules.dma = LiteDRAMDMAReader(self.dram_port, with_csr=True)
        sc = StrideConverter([('data', len(self.dma.source.data))], [('data', 32)], reverse=True)

        self.submodules.fifo = fifo = SyncFIFO([('data', 32)], 128)

        self.submodules.packet = p = Packetizer(ip_udp_description(32), [('data', 32), ('last_be', 4)], udp_header)        
        self.submodules += sc

        self.submodules.phy_model = ethphy= PHY(8, debug=False)

        print(p.sink.layout)
        # MAC
        self.submodules.ethmac = ethmac = LiteEthMAC(
            phy        = ethphy,
            dw         = 32,
            interface  = "hybrid",
            endianness = "little",
            hw_mac=None)

        self.port = port = ethmac.crossbar.get_port(0, dw=32)

        en = Signal()
        self.comb += [
            self.dma.source.connect(sc.sink),
            sc.source.connect(fifo.sink),
            fifo.source.connect(p.sink, omit={"valid", "ready"}),
            #fifo.source.connect(p.sink, omit={"valid", "ready"}),
            p.source.connect(port.sink),

            p.sink.valid.eq(fifo.source.valid & en),
            fifo.source.ready.eq(p.sink.ready & en),


                        
        ]


        self.sync += [
            If(~en,
                If(fifo.level >= 32,
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
           
        #self.sync += \
            


class DRAMMemory:
    def __init__(self, width, depth, init=[]):
        self.width = width
        self.depth = depth
        self.mem = []
        for d in init:
            self.mem.append(d)
        for _ in range(depth-len(init)):
            self.mem.append(0)

    @passive
    def read_generator(self, dram_port):
        address = 0
        pending = 0
        while True:
            yield dram_port.cmd.ready.eq(0)
            yield dram_port.rdata.valid.eq(0)
            if pending:
                yield dram_port.rdata.valid.eq(1)
                yield dram_port.rdata.data.eq(self.mem[address%self.depth])
                yield
                yield dram_port.rdata.valid.eq(0)
                yield dram_port.rdata.data.eq(0)
                pending = 0
            elif (yield dram_port.cmd.valid):
                pending = not (yield dram_port.cmd.we)
                address = (yield dram_port.cmd.addr)
                yield
                yield dram_port.cmd.ready.eq(1)
            yield


video_data = []

@passive
def video_capture_generator(dut):
    while True:
        if ((yield dut.core.source.valid) and
            (yield dut.core.source.ready) and
            (yield dut.core.source.de)):
            video_data.append((yield dut.core.source.data))
        yield

def main_generator(dut):
    for i in range(100):
        yield

    yield dut.port.sink.target_mac.eq(0xa0cec8d5873d)
    yield dut.port.sink.sender_mac.eq(0x10e2d5000001)
    yield dut.port.sink.ethernet_type.eq(0x0800)
    yield dut.packet.sink.ihl.eq(5)
    yield dut.packet.sink.version.eq(4)
    yield dut.packet.sink.total_length.eq(1310)
    yield dut.packet.sink.identification.eq(0)
    yield dut.packet.sink.ttl.eq(64)
    yield dut.packet.sink.protocol.eq(17)
    yield dut.packet.sink.checksum.eq(0xb1e8)
    yield dut.packet.sink.sender_ip.eq(0xc0a80132)
    yield dut.packet.sink.sender_ip.eq(0xc0a80164)
    yield dut.packet.sink.src_port.eq(32765)
    yield dut.packet.sink.dst_port.eq(9001)
    yield dut.packet.sink.length.eq(1290)
    yield dut.packet.sink.udp_checksum.eq(0)


    # init dma
    yield dut.dma._enable.storage.eq(0)
    yield dut.dma._base.storage.eq(0)
    yield dut.dma._length.storage.eq(128)

    yield
    yield dut.dma._enable.storage.eq(1)
    yield
    
    
    # init video
   

    # delay
    for i in range(512):
       yield



if __name__ == "__main__":
    #for video_clk_ns in  [20, 10, 5]:
    video_clk_ns = 5
    tb = TB()
    mem = DRAMMemory(32, 512, [i for i in range(256)])
    generators = {
        "sys":   [main_generator(tb), mem.read_generator(tb.dram_port)],
       # "video": [video_capture_generator(tb)],
            "eth_tx": [tb.phy_model.phy_sink.generator(),
                       tb.phy_model.generator()],
            "eth_rx":  tb.phy_model.phy_source.generator()
    }
    clocks = {"sys":   15,
                "video": video_clk_ns,
            
                  "eth_rx": 8,
                  "eth_tx": 8
            }
    video_data = []
    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
