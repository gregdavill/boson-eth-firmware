#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <crc.h>
#include <stdint.h>
#include <stdbool.h>

#include "include/time.h"
#include "include/boson.h"

#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/git.h>


#include <liblitedram/sdram.h>

#include <libliteeth/udp.h>

#include <irq.h>
#include <uart.h>

#define IPTOINT(a, b, c, d) ((a << 24)|(b << 16)|(c << 8)|d)

#ifndef LOCALIP1
#define LOCALIP1 192
#define LOCALIP2 168
#define LOCALIP3 1
#define LOCALIP4 50
#endif

#ifndef REMOTEIP1
#define REMOTEIP1 192
#define REMOTEIP2 168
#define REMOTEIP3 1
#define REMOTEIP4 100
#endif

static const unsigned char macadr[6] = {0x10, 0xe2, 0xd5, 0x00, 0x00, 0x01};

/* prototypes */
void isr(void);


void isr(void){
	__attribute__((unused)) unsigned int irqs;

	irqs = irq_pending() & irq_getmask();

#ifdef CSR_UART_BASE
#ifndef UART_POLLING
	if(irqs & (1 << UART_INTERRUPT))
		uart_isr();
#endif
#endif
}


uint32_t buffers[] = {
	0x00000000,
	0x01000000,
	0x02000000,
};

uint8_t buffer_owners[] = {0,0,0};



int main(int i, char **c)
{	

	
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
#ifdef CSR_UART_BASE
	uart_init();
#endif

	msleep(25);
	 
	printf("\n\n\e[1m  _______  _______  _______  __   __ \e[0m\n");
	printf("\e[1m |  _    ||       ||       ||  | |  |\e[0m\n");
	printf("\e[1m | |_|   ||    ___||_     _||  |_|  |\e[0m\n");
	printf("\e[1m |       ||   |___   |   |  |       |\e[0m\n");
	printf("\e[1m |  _   | |    ___|  |   |  |       |\e[0m\n");
	printf("\e[1m | |_|   ||   |___   |   |  |   _   |\e[0m\n");
	printf("\e[1m |_______||_______|  |___|  |__| |__|\e[0m\n");


	//terminal_set_fg(TERMINAL_YELLOW);
	printf("\e[92;1m    - Boson Ethernet interface - \e[0m\n");
	//terminal_set_fg(TERMINAL_CYAN);

 	printf("\n (c) Copyright 2021 GetLabs \n");
 	printf(" fw built: "__DATE__ " " __TIME__ " \n\n");

 	printf("   Firmware git sha1: "FW_GIT_SHA1"\n");
 	printf("      Migen git sha1: "MIGEN_GIT_SHA1"\n");
 	printf("      LiteX git sha1: "LITEX_GIT_SHA1"\n");

#if defined(CSR_ETHMAC_BASE) || defined(CSR_SDRAM_BASE)
    printf("--========== \e[1mInitialization\e[0m ============--\n");
#ifdef CSR_ETHMAC_BASE
	//eth_init();
#endif
#ifdef CSR_SDRAM_BASE
	int sdr_ok = sdram_init();
#else
#ifdef MAIN_RAM_TEST
	sdr_ok = memtest();
#endif
#endif
	if (sdr_ok !=1)
		printf("Memory initialization failed\n");
	printf("\n");
#endif

	_eth_init();

	//_microudp_start(macadr, IPTOINT(LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4));

	/* Enable single LED mode */
	eth_write_mmd_register(2, 0, 1 << 4);

	//loopback_test();

	printf("--==========-- \e[1mBoson Init\e[0m ===========--\n");
	
	dma0_boson_gpio_out_write(0);
	dma0_boson_gpio_oe_write(1);

	boson_init();



	printf("\n");
	msleep(10);
	char spin[] = "-\\|/";
	int spin_idx = 0;

	printf("Wait For Link Up");
	for(int timeout = 0; timeout < 40; timeout++){
		printf(".");
		msleep(250);
		if((ethphy_rx_inband_status_read() & 0x7) == 0x5){
			break;
		}	
	}

	unsigned int ip;
	ip = IPTOINT(REMOTEIP1, REMOTEIP2, REMOTEIP3, REMOTEIP4);

	printf("\nWait for partner address from ARP...");
	while(1) {
		_microudp_start(macadr, IPTOINT(LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4));

		if(microudp_arp_resolve(ip))
			break;

		printf("\b%c", spin[spin_idx]);
		spin_idx = (spin_idx + 1) % (sizeof(spin) - 1);
		msleep(250);
	}

	printf("\n Link Partner: ");
	eth_print_mac();
	printf("\n");

	

    while(1) {
		/* Start a capture */
		dma0_dma_enable_write(0);
		dma0_dma_base_write(0);
		dma0_dma_length_write(((512*640)*2));
		dma0_dma_enable_write(1);
		/* While capture is running */
		while(1){
			if(dma0_dma_done_read()){
				break;
			}
		}

		dma0_dma_enable_write(0);
//		flush_cpu_dcache();
//		flush_l2_cache();
//
//		while(dma0_dma_offset_read() == 0);

		uint32_t idx = 0;
		while(idx <= 512){

			busy_wait_us(10);

			dma1_enable_write(0);

			csr_idx_value_write(idx);
			csr_idx_level_write(64);
			dma1_base_write(0 + idx * 1280);
			dma1_length_write((1280));
			dma1_enable_write(1);

			/* While capture is running */
			while(1){
				if(dma1_done_read()){
					break;
				}
			}
			

			idx += 1;
		}

		//uint32_t idx = 0;
		//while(idx < 640){
		//	uint8_t* packet_data = microudp_get_tx_buffer();	
		//	uint8_t* dram_ptr = (uint8_t*)(MAIN_RAM_BASE);	
		//	dram_ptr+=2;	
		//	uint32_t len = 1280;//format_request(packet_data, TFTP_WRQ, filename);
		//	packet_data[0] = idx >> 8;
		//	packet_data[1] = idx & 0xFF;
		//	memcpy(packet_data + 2, dram_ptr + (idx * len), len );
		//	microudp_send(32765, 9001, len + 2);
		//	idx += 1;
		//}

		//microudp_service();
		//msleep(10);


	}
	
	return 0;
}
