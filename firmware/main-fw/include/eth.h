#ifndef ETH_H__
#define ETH_H__

#include <stdint.h>

typedef enum {
	RX_SKEW = 1,
	TX_SKEW = 2,
}rx_skew_path_t;

int eth_link_status(void);
void eth_write_mmd_register(uint8_t mmd_device_address, uint8_t mmd_register, uint16_t value);
uint16_t eth_read_mmd_register(uint8_t mmd_device_address, uint8_t mmd_register);
void eth_enable_loopback(void);
void eth_gigabit_enable(void);
uint8_t eth_skew_calibrate(rx_skew_path_t path);
int loopback_packet(void);
int loopback_test(void);

#endif