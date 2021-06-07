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
#include <ethernet.h>
#include <telnet.h>

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

static unsigned char mac_addr[6] = {0x10, 0xe2, 0xd5, 0x00, 0x00, 0x01};
static unsigned char ip_addr[4] = {192,168,1,50};

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

	printf("\e[92;1m    - Boson Ethernet interface - \e[0m\n");
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

	printf("--========-- \e[1mEthernet Init\e[0m ==========--\n");
 	ethernet_init(mac_addr, ip_addr);
	
	telnet_init();

	printf("--==========-- \e[1mBoson Init\e[0m ===========--\n");
 	boson_init();

    while(1) {
		ethernet_service();

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
	}
	
	return 0;
}
