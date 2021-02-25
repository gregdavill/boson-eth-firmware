#include <eth.h>
#include <libliteeth/mdio.h>
#include <stdio.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <libliteeth/udp.h>

#include <time.h>


int eth_link_status(void){
    uint16_t reg_value = mdio_read(0, 1);

    return (reg_value & (1 << 2)) == (1 << 2);
}


void eth_write_mmd_register(uint8_t mmd_device_address, uint8_t mmd_register, uint16_t value){
	mdio_write(0, 0xD, mmd_device_address);
	mdio_write(0, 0xE, mmd_register);
	mdio_write(0, 0xD, 0x4002);
	mdio_write(0, 0xE, value);
}

uint16_t eth_read_mmd_register(uint8_t mmd_device_address, uint8_t mmd_register){
	mdio_write(0, 0xD, mmd_device_address);
	mdio_write(0, 0xE, mmd_register);
	mdio_write(0, 0xD, 0x4000 | mmd_device_address);
	uint16_t data = mdio_read(0, 0xE);
    return data;
}

void eth_enable_loopback(void){
	uint16_t v = 0;

	v = mdio_read(0, 0x0);

	v |= (1 << 14) | (1 << 6) | (1<<8);
	v &= ~((1 << 13) | (1 << 12));
	mdio_write(0, 0x0, v);


	v = mdio_read(0, 0x9);
	v |= (1 << 12);
	v &= ~(1 << 11);
	mdio_write(0, 0x9, v);	
}

void eth_gigabit_enable(void){
    uint16_t v = 0;

	v = mdio_read(0, 0x0);

	v |= (1 << 6) | (1<<8);
	v &= ~((1 << 14) | (1 << 13) | (1 << 12));
	mdio_write(0, 0x0, v);


	v = mdio_read(0, 0x9);
    v |= (1 << 9);
    v &= ~((1 << 8) | (1 << 12));
	mdio_write(0, 0x9, v);


    mdio_write(0, 0x4, 0x0001);	

    v = mdio_read(0, 0x0);
	v |= (1 << 9) | (1 << 12);
	mdio_write(0, 0x0, v);
}


uint8_t eth_skew_calibrate(rx_skew_path_t path){
	
	int min = 31;
	int max = 0;

	for(int p = 31; p >= 0; p--){
		uint16_t v = eth_read_mmd_register(2,8);
		if(path == RX_SKEW){
			v &= ~(0b11111);
			v |= (p & 0b11111);
		} else if(path == TX_SKEW) {
			v &= ~(0b11111 << 5);
			v |= ((p & 0b11111) << 5);
		}else {
			continue;
		}
		eth_write_mmd_register(2, 8, v);
		v = eth_read_mmd_register(2,8);	

		int count = 0;
		for(int i = 0; i < 32; i++){
			int r =	loopback_packet();
			if(r){
				count++;
			}
		}
		if(count == 0){
			printf(".");
		}
		else if(count == 32){
			printf("#");
			if(max < p)
				max = p;
			if(min > p)
				min = p;
		}
		else if(count > 0){
			printf("-");
		}
	}


	int sel = ((max - min) / 2) + min;
	printf("\n");
	for(int i = 0; i < (10-3+31-sel); i++)
		printf(" ");
	printf("--^\n");
	return sel;
}

/* check if we can recieve loopback packet */
int loopback_test(void)
{
	eth_enable_loopback();

	/* Give PHY some time to create the link*/
	msleep(500);

	printf(" RX clock calibration\n");
	printf("  - Skew: ");
	int rx_skew_val = eth_skew_calibrate(RX_SKEW);
	eth_write_mmd_register(2, 8, (0x01111 << 5) | (rx_skew_val & 0b11111));	

	printf(" TX clock calibration\n");
	printf("  - Skew: ");
	int tx_skew_val = eth_skew_calibrate(TX_SKEW);
	eth_write_mmd_register(2, 8, ((tx_skew_val & 0b11111) << 5) | (rx_skew_val & 0b11111));	

    printf(" RX clock calibration\n");
	printf("  - Skew: ");
	rx_skew_val = eth_skew_calibrate(RX_SKEW);
	eth_write_mmd_register(2, 8, ((tx_skew_val & 0b11111) << 5) | (rx_skew_val & 0b11111));	


	/* Enable standard operation */
    //eth_gigabit_enable();
    return 0;
}

int loopback_packet(void){

	/* Take TXSLOT 0 */
	char* buff = (char*)(ETHMAC_BASE + ETHMAC_SLOT_SIZE * (ETHMAC_TX_SLOTS + 0));
	for(int i = 0; i < 64; i++)
		buff[i] = i;

	/* wait for reader to be available */
	while(!(ethmac_sram_reader_ready_read()));

	/* Senh data in TXSLOT0 out to PHY */
	ethmac_sram_reader_slot_write(0);
	ethmac_sram_reader_length_write(64);
	ethmac_sram_reader_start_write(1);
	

	for(int timeout = 0; timeout < 100; timeout++){

		if(ethmac_sram_writer_ev_pending_read() & ETHMAC_EV_SRAM_WRITER) {
			//int rxslot = ethmac_sram_writer_slot_read();
			//char* rxbuffer = (char*)(ETHMAC_BASE + ETHMAC_SLOT_SIZE * rxslot);
			//int rxlen = ethmac_sram_writer_length_read();
			
			ethmac_sram_writer_ev_pending_write(ETHMAC_EV_SRAM_WRITER);
			return 1;
		}
	}


	
	return 0;
}
