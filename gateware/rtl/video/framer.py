# This file is Copyright (c) 2020 Gregory Davill <greg.davill@gmail.com>
# License: BSD

from migen import *
from litex.soc.interconnect.stream import Endpoint
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from rtl.edge_detect import EdgeDetect


from litex.soc.interconnect import stream

from litex.soc.interconnect.csr import AutoCSR, CSR, CSRStatus, CSRStorage
from litex.soc.interconnect.stream import Endpoint, EndpointDescription, AsyncFIFO

def framer_params():
    return [
        ("x_start", 16),
        ("y_start", 16),
        ("x_stop", 16),
        ("y_stop", 16),
    ]

class Framer(Module, AutoCSR):
    def __init__(self):
        self.sink = sink = Endpoint([("data", 32)])

        self.params = params = Endpoint(framer_params())

        self.hsync = hsync = Signal()
        self.vsync = vsync = Signal()


        # VGA output
        self.red   = red   = Signal(8)
        self.green = green = Signal(8)
        self.blue  = blue  = Signal(8)
        self.data_valid = data_valid = Signal()

        # parameters
        pixel_counter = Signal(14)
        line_counter  = Signal(14)

        h_det = EdgeDetect(mode="fall", input_cd="video", output_cd="video")
        v_det = EdgeDetect(mode="fall", input_cd="video", output_cd="video")
        self.submodules += h_det, v_det
        self.comb += [
            h_det.i.eq(hsync),
            v_det.i.eq(vsync),
        ]

        self.comb += [
            If((line_counter >= params.y_start) & (line_counter < params.y_stop),
                If((pixel_counter >= params.x_start) & (pixel_counter < params.x_stop),
                    sink.ready.eq(1)
                )
            )
        ]

        self.sync.video += [
            # Default values
            red.eq(0),
            green.eq(0),
            blue.eq(0),
            data_valid.eq(0),

            # Show pixels
            If((line_counter >= params.y_start) & (line_counter < params.y_stop),
                If((pixel_counter >= params.x_start) & (pixel_counter < params.x_stop),
                    data_valid.eq(1),
                    If(sink.valid,
                        red.eq(sink.data[0:8]),
                        green.eq(sink.data[8:16]),
                        blue.eq(sink.data[16:24])
                    ).Else( 
                        red.eq(0xFF),
                        green.eq(0x77),
                        blue.eq(0xFF)
                    )
                )
            ),

            # Horizontal timing for one line
            pixel_counter.eq(pixel_counter + 1),

            If(h_det.o,
                pixel_counter.eq(0),
                line_counter.eq(line_counter + 1),
            ),
            If(v_det.o,
                line_counter.eq(0),
            )
        ]



class FrameExtraction(Module, AutoCSR):
    def __init__(self, fifo_depth):
        # in pix clock domain
        self.valid_i = Signal()
        self.vsync = Signal()
        self.de = Signal()
        self.data = Signal(16)

        # in sys clock domain
        word_layout = [("sof", 1), ("pixels", 16)]
        self.frame = stream.Endpoint(word_layout)
        self.busy = Signal()

        self._overflow = CSR()

        # # #

        # start of frame detection
        vsync = self.vsync
        vsync_r = Signal()
        self.new_frame = new_frame = Signal()
        self.comb += new_frame.eq(vsync & ~vsync_r)
        self.sync.pix += vsync_r.eq(vsync)

        # FIFO
        fifo = stream.AsyncFIFO(word_layout, fifo_depth)
        fifo = ClockDomainsRenamer({"write": "pix", "read": "sys"})(fifo)
        self.submodules += fifo
        self.fifo = fifo
        self.comb += [
            fifo.sink.pixels.eq(self.data),
            fifo.sink.valid.eq(self.de)
        ]
        self.sync.pix += \
            If(new_frame,
                fifo.sink.sof.eq(1)
            ).Elif(self.de,
                fifo.sink.sof.eq(0)
            )

        self.comb += [
            fifo.source.connect(self.frame),
            self.busy.eq(0)
        ]

        # overflow detection
        pix_overflow = Signal()
        pix_overflow_reset = Signal()
        self.sync.pix += [
            If(fifo.sink.valid & ~fifo.sink.ready,
                pix_overflow.eq(1)
            ).Elif(pix_overflow_reset,
                pix_overflow.eq(0)
            )
        ]

        sys_overflow = Signal()
        self.specials += MultiReg(pix_overflow, sys_overflow)
        self.submodules.overflow_reset = PulseSynchronizer("sys", "pix")
        self.submodules.overflow_reset_ack = PulseSynchronizer("pix", "sys")
        self.comb += [
            pix_overflow_reset.eq(self.overflow_reset.o),
            self.overflow_reset_ack.i.eq(pix_overflow_reset)
        ]

        overflow_mask = Signal()
        self.comb += [
            self._overflow.w.eq(sys_overflow & ~overflow_mask),
            self.overflow_reset.i.eq(self._overflow.re)
        ]
        self.sync += \
            If(self._overflow.re,
                overflow_mask.eq(1)
            ).Elif(self.overflow_reset_ack.o,
                overflow_mask.eq(0)
            )
