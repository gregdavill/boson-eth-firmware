# This file is Copyright (c) 2020 Gregory Davill <greg.davill@gmail.com>
# License: BSD

from litex.build.generic_platform import *

def boson_syzygy_r0d1(syzygy_id=0):
    _id = f'SYZYGY{syzygy_id}'
    
    return [ 
    ("Boson", 0,
        Subsignal("data", Pins(f'{_id}:S27 {_id}:P2C_CLKN {_id}:D5P {_id}:S26 \
             {_id}:D7N {_id}:D2P {_id}:D2N {_id}:S17 \
                  {_id}:D1N {_id}:S16 {_id}:D5N {_id}:S18 \
                       {_id}:C2P_CLKN {_id}:S25 {_id}:D1P {_id}:D6P \
                            {_id}:D4P {_id}:D0P {_id}:D6N {_id}:S23 \
                                 {_id}:'),IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW")),
        Subsignal("clk", Pins("A17"),IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW")),
        Subsignal("vsync", Pins("A13"),IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW")),
        Subsignal("hsync", Pins("D16"),IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW")),
        Subsignal("valid", Pins("C16"),IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW")),
        Subsignal("tx", Pins("A3"),IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW")),
        Subsignal("rx", Pins("B9"),IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW")),
        Subsignal("reset", Pins("B2"),IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW")),
        Subsignal("ext_sync", Pins("B18"),IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW")),


        Subsignal("rst_n",     Pins("SYZYGY1:D5N"),       IOStandard("LVCMOS18"),Misc("SLEWRATE=FAST TERMINATION=OFF")),    
        Subsignal("clk_p",     Pins("SYZYGY1:D4P"),       IOStandard("LVCMOS18"),Misc("SLEWRATE=FAST TERMINATION=OFF")),
        Subsignal("clk_n",     Pins("SYZYGY1:D4N"),       IOStandard("LVCMOS18"),Misc("SLEWRATE=FAST TERMINATION=OFF")),
        Subsignal("cs_n",      Pins("SYZYGY1:D6P"),       IOStandard("LVCMOS18"),Misc("SLEWRATE=SLOW TERMINATION=OFF")),
        Subsignal("dq",        Pins("SYZYGY1:D2N SYZYGY1:D0N SYZYGY1:D5P SYZYGY1:D2P SYZYGY1:D3P SYZYGY1:D1N SYZYGY1:D1P SYZYGY1:D0P"),     IOStandard("LVCMOS18"),Misc("SLEWRATE=FAST TERMINATION=OFF")),
        Subsignal("rwds",      Pins("SYZYGY1:D3N"),       IOStandard("LVCMOS18"),Misc("SLEWRATE=FAST TERMINATION=OFF")),
    ),
   
]