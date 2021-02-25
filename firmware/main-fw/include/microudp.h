#ifndef MICROUDP_H__
#define MICROUDP_H__

#include <stdint.h>
#include <generated/csr.h>
#include <generated/mem.h>

#define ETHMAC_EV_SRAM_WRITER	0x1
#define ETHMAC_EV_SRAM_READER	0x1

#define IPTOINT(a, b, c, d) ((a << 24)|(b << 16)|(c << 8)|d)

#define UDP_BUFSIZE (1532)


typedef void (*udp_callback)(unsigned int src_ip, unsigned short src_port, unsigned short dst_port, void *data, unsigned int length);

//#define DEBUG_MICROUDP_TX
//#define DEBUG_MICROUDP_RX

#define ETHERTYPE_ARP 0x0806
#define ETHERTYPE_IP  0x0800

#ifdef CSR_ETHMAC_PREAMBLE_CRC_ADDR
#define HW_PREAMBLE_CRC
#endif

struct ethernet_header {
#ifndef HW_PREAMBLE_CRC
	unsigned char preamble[8];
#endif
	unsigned char destmac[6];
	unsigned char srcmac[6];
	unsigned short ethertype;
} __attribute__((packed));


int microudp_arp_resolve(unsigned int ip);
void *microudp_get_tx_buffer(void);
int microudp_send(unsigned short src_port, unsigned short dst_port, unsigned int length);
int microudp_send_1(unsigned short src_port, unsigned short dst_port, unsigned int length);
int microudp_send_2(unsigned int length);
void microudp_set_callback(udp_callback callback);
void microudp_start(const unsigned char *macaddr, unsigned int ip);
void microudp_service(void);
void eth_print_mac(void);
void eth_get_mac(uint8_t** mac);
void _eth_init(void);
void eth_mode(void);

#endif