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

uint32_t frame_count = 0;

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

	telnet_active = 0;
	time_init();

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

	uint32_t wait = 5000;

    while(1) {
		ethernet_service();
	

		if(telnet_active)
		{
			capture_service();
			transmit_service();
			hb_service();
		}
	}
	
	return 0;
}


static int init = 0;
static uip_ipaddr_t addr;
static struct uip_udp_conn *c;
static uint8_t data[64];
void _udp_service()
{
	static int last_event;

	if(init == 0){
		uip_ipaddr(&addr, 192,168,1,100);
		c = uip_udp_new(&addr, UIP_HTONS(12345));
		if(c != NULL) {
			uip_udp_bind(c, UIP_HTONS(12344));
			init = 1;
		}
	}else{
		/* Test UDP output */
		if(elapsed(&last_event, CONFIG_CLOCK_FREQUENCY/1) && init) {
			uip_udp_packet_send(c, data, 64);
		}
	}
}


void hb_service()
{
	static int last_event;
	static int counter;

	if(elapsed(&last_event, CONFIG_CLOCK_FREQUENCY/100)) {
		counter = counter + 1;
		if(counter > 10) {
			wprintf("frame_count: 0x%08x\n", frame_count);
			counter = 0;
		}
	}
}


enum {
	BUFFER_CLAIMED = 1,
	BUFFER_COMPLETE = 2,
};

uint32_t buffers[] = {
	0x00000000,
	0x02000000,
	0x04000000,
};

uint8_t buffer_owners[] = {0,0,0};


int32_t get_free_buffer(){
	for(int i = 0; i < 3; i++){
		if(!(buffer_owners[i] & BUFFER_CLAIMED)){
			if(!(buffer_owners[i] & BUFFER_COMPLETE)){
				return i;
			}
		}
	}

	for(int i = 0; i < 3; i++){
		if(!(buffer_owners[i] & BUFFER_CLAIMED)){
			return i;
		}
	}

	return -1;
}


int32_t get_complete_buffer(){
	for(int i = 0; i < 3; i++){
		if((buffer_owners[i] & BUFFER_COMPLETE)){
			return i;
		}
	}

	return -1;
}


void capture_service(){
	static int i = -1;
	if(dma0_dma_enable_read()){
		if(dma0_dma_done_read()){
			/* Capture completed */
			dma0_dma_enable_write(0);
			buffer_owners[i] = BUFFER_COMPLETE;
		}
	}
	else{
		/* Get Buffer */
		i = get_free_buffer();
		if(i != -1){
			buffer_owners[i] = BUFFER_CLAIMED;

			/* Start a capture */
			dma0_dma_base_write(buffers[i]);
			dma0_dma_length_write(((512*640)*2));
			dma0_dma_enable_write(1);
		}
	}
}


enum state {
	STATE_WAIT = 0,
	STATE_TRANSMIT
};

void transmit_service(){
	static uint32_t idx = 0;
	static enum state s = STATE_WAIT;
	static uint32_t buffer_address = -1;

	static uint32_t ipg = 0;
	

	switch(s){
		case STATE_WAIT:
			buffer_address = get_complete_buffer();
			if(buffer_address != -1){
				frame_count++;
				s = STATE_TRANSMIT;
				buffer_owners[buffer_address] = BUFFER_CLAIMED;
				idx = 0;
				dma1_enable_write(0);
			}
		break;

		case STATE_TRANSMIT:

			if(dma1_enable_read()){
				if(dma1_done_read()){
					dma1_enable_write(0);

					ipg = 1;
					idx += 1;
					if(idx == 512){
						buffer_owners[buffer_address] = 0;
						s = STATE_WAIT;
						break;
					}
				}
			}else{
				if(ipg > 0){
					ipg--;
				}else{
					csr_idx_value_write(idx);
					csr_idx_level_write(320);
					dma1_base_write(buffers[buffer_address] + idx * 1280);
					dma1_length_write(1280);
					dma1_enable_write(1);
				}
			}

		break;
	}

}