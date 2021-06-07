// This file is Copyright (c) 2021 Gregory Davill <greg.davill@gmail.com>
// License: BSD

#include <stdint.h>


enum proto_id {
    BLOB_PROTOCOL_ID = 0xB4,
};

enum msg_id {
    BLOB_DATA = 0x01,
    BLOB_COMPLETE_ACK = 0x81,
    BLOB_RESEND = 0x82,
};


typedef struct {
    uint8_t data[1024*1024*2];
    void* tex0 = 0;
    bool generated = false;
    float delta;
} image_t;



typedef struct {
    uint8_t data[1024*1024*4];
    uint32_t sequence = 0;
    uint32_t max_idx;

    uint8_t idx_seen[1024];
    uint16_t channel;   
    bool valid; 
} blob_t;


void open_socket();
void rx_close();
image_t* getImage();



uint32_t extract_uint32_t(uint8_t* p);



