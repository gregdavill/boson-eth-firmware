
import sys
import argparse
import optparse
import subprocess
import os
import shutil

from migen import *

from rtl.platform import butterstick_r1d0


from litex.build.generic_platform import *
from litex.soc.cores.clock import *
from rtl.ecp5_dynamic_pll import ECP5PLL, period_ns
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import *

from litex.soc.interconnect.stream import Pipeline, StrideConverter, Endpoint, AsyncFIFO
from litex.soc.interconnect.csr import *

from migen.genlib.cdc import PulseSynchronizer

from rtl.video.boson import Boson
from rtl.video.framer import FrameExtraction

from litevideo.input.analysis import  ResolutionDetection

from litedram.frontend.dma import LiteDRAMDMAWriter


class DMAWriterVideo(LiteDRAMDMAWriter):
    def __init__(self, sdram_port):
        super().__init__(sdram_port, with_csr=False)

        self._sink = self.sink
        self.sink  = Endpoint([("data", self.port.data_width)])
        self.sof = Signal()

        self.wait_sof = Signal()

        self._base   = CSRStorage(32, reset=0)
        self._length = CSRStorage(32, reset=0)
        self._enable = CSRStorage(reset=0)
        self._done   = CSRStatus()
        self._loop   = CSRStorage(reset=0)
        self._offset = CSRStatus(32)

        # # #

        shift  = log2_int(self.port.data_width//8)
        base   = Signal(self.port.address_width)
        offset = Signal(self.port.address_width)
        length = Signal(self.port.address_width)
        self.comb += base.eq(self._base.storage[shift:])
        self.comb += length.eq(self._length.storage[shift:])

        self.comb += self._offset.status.eq(offset)

        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.submodules.fsm = fsm
        self.comb += [
            fsm.reset.eq(~self._enable.storage),
            self.wait_sof.eq(fsm.ongoing('IDLE'))
        ]
        fsm.act("IDLE",
            If(self.sof,
                self.sink.ready.eq(1),
                NextValue(offset, 0),
                NextState("RUN"),
            )
        )
        fsm.act("RUN",
            self._sink.valid.eq(self.sink.valid),
            self._sink.last.eq(offset == (length - 1)),
            self._sink.address.eq(base + offset),
            self._sink.data.eq(self.sink.data),
            self.sink.ready.eq(self._sink.ready),
            If(self.sink.valid & self.sink.ready,
                NextValue(offset, offset + 1),
                If(self._sink.last,
                    If(self._loop.storage,
                        NextValue(offset, 0)
                    ).Else(
                        NextState("DONE")
                    )
                )
            )
        )
        fsm.act("DONE", self._done.status.eq(1))




class FrameExtraction(Module, AutoCSR):
    def __init__(self):
        # in pix clock domain
        self.vsync = Signal()

        self.sof = Signal() 
        # # #

        # start of frame detection
        vsync = self.vsync
        vsync_r = Signal()
        self.new_frame = new_frame = Signal()
        self.comb += new_frame.eq(vsync & ~vsync_r)
        self.sync.pix += vsync_r.eq(vsync)

        ps = PulseSynchronizer("pix", "sys")
        self.comb += ps.i.eq(new_frame), self.sof.eq(ps.o)
        self.submodules += ps






class DMAVideoCapture(Module, AutoCSR):
    def __init__(self, platform, sdram_port):

        self.submodules.dma = dma = DMAWriterVideo(sdram_port)

        # Boson video stream
        self.submodules.boson = boson = Boson(platform, platform.request("boson"), platform.sys_clk_freq)
        self.submodules.resolution = res = ResolutionDetection()        
        fe = FrameExtraction()
        self.submodules += fe

        self.comb += [
            res.valid_i.eq(1),
            res.vsync.eq(boson.vsync),
            res.de.eq(boson.data_valid),

            fe.vsync.eq(boson.vsync),
        ]

        # 16bit -> 128bit coverter
        sc = StrideConverter([('data', 16)], [('data', len(dma.sink.data))], reverse=True)
        self.submodules += ResetInserter()(sc)
        
        # FIFO
        fifo = AsyncFIFO([('data', 16)], 256)
        fifo = ClockDomainsRenamer({"write": "pix", "read": "sys"})(fifo)
        fifo = ResetInserter(["pix", "sys"])(fifo)
        self.submodules += fifo
        self.fifo = fifo
        self.comb += [
            fifo.sink.data.eq(boson.source.data),
            fifo.sink.valid.eq(boson.source.valid),

            dma.sof.eq(fe.sof),
            
            fifo.reset_pix.eq(dma.wait_sof),
            fifo.reset_sys.eq(dma.wait_sof),   
            
            sc.reset.eq(dma.wait_sof),   
            dma.port.flush.eq(dma.wait_sof),
        ]

        self.submodules.pipeline = pipeline = Pipeline(fifo, sc, dma)

        self.comb += [
            boson.source.connect(pipeline.sink),
        ]
