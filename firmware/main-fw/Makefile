include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

CFLAGS += -fpack-struct -O2 -I$(MAIN-FW_DIRECTORY)/include -fdata-sections -ffunction-sections

OBJECTS=main.o time.o i2c.o boson.o flirCRC.o Serializer_BuiltIn.o telnet.o ethernet.o stdio_wrap.o

vpath % $(MAIN-FW_DIRECTORY) $(MAIN-FW_DIRECTORY)/boson


include $(UIP_DIRECTORY)/Makefile.mk

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

vpath %.a $(PACKAGES:%=../%)

%.elf: crt0.o libuip.a $(LIBS:%=%.a)
	$(CC) $(LDFLAGS) -T $(MAIN-FW_DIRECTORY)/linker.ld -N -o $@ \
		crt0.o \
		$(OBJECTS) \
		$(PACKAGES:%=-L../%) -L../uip \
		-Wl,--whole-archive \
		-Wl,--gc-sections \
		-luip $(LIBS:lib%=-l%)

ifneq ($(OS),Windows_NT)
	chmod -x $@
endif

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: %.c
	$(compile)

%.o: %.S
	$(assemble)

crt0.o: $(CPU_DIRECTORY)/crt0.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) main-fw.elf main-fw.bin .*~ *~

size:
	$(TARGET_PREFIX)size main-fw.elf


.PHONY: all clean
