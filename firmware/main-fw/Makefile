include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

CFLAGS += -fpack-struct -O3 -I$(MAIN-FW_DIRECTORY)/include -fdata-sections -ffunction-sections

OBJECTS=main.o time.o i2c.o boson.o flirCRC.o Serializer_BuiltIn.o microudp.o eth.o

vpath % $(MAIN-FW_DIRECTORY) $(MAIN-FW_DIRECTORY)/boson

all: main-fw.bin size

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
ifneq ($(OS),Windows_NT)
	chmod -x $@
endif
ifeq ($(CPUENDIANNESS),little)
	$(PYTHON) -m litex.soc.software.mkmscimg $@ --little
else
	$(PYTHON) -m litex.soc.software.mkmscimg $@
endif

main-fw.elf: $(MAIN-FW_DIRECTORY)/linker.ld $(OBJECTS)

%.elf: 
	$(LD) $(LDFLAGS) -L$(BUILDINC_DIRECTORY)/generated -T $(MAIN-FW_DIRECTORY)/linker.ld -N -o $@ \
		../libbase/crt0.o \
		$(OBJECTS) \
		-gc-sections \
		-L../libbase \
		-L../libcompiler_rt \
		-L../liblitedram \
		-L../libliteeth \
		-llitedram -lliteeth -lbase-nofloat -lcompiler_rt
ifneq ($(OS),Windows_NT)
	chmod -x $@
endif

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: %.c
	$(compile)

%.o: %.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) main-fw.elf main-fw.bin .*~ *~

size:
	$(TARGET_PREFIX)size main-fw.elf


.PHONY: all clean
