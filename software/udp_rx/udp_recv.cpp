// This file is Copyright (c) 2021 Gregory Davill <greg.davill@gmail.com>
// License: BSD

#include <stdio.h>
#include <netdb.h>
#include <mutex>
#include <thread>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <atomic>
#include "udp_recv.h"
#include <string.h>

#include <GL/glew.h>            // Needs to be initialized with glewInit() in user's code.

// Used for frame rate calculations
#include <SDL.h>
static uint64_t last_time;




#define BUFSIZE 4*1024*1024

struct sockaddr_in myaddr;      /* our address */
struct sockaddr_in remaddr;     /* remote address */
socklen_t addrlen = sizeof(remaddr);            /* length of addresses */
int recvlen;                    /* # bytes received */
int fd;                         /* our socket */
unsigned char buf[BUFSIZE];     /* receive buffer */


std::mutex mu;
std::atomic_bool stop_thread_1;


image_t image0;
image_t image1;

image_t* front_buffer;
image_t* back_buffer;

std::thread* t;

void rx_thread();
void swap_buffers();

void open_socket(){

    stop_thread_1 = false;


    image0 = {0};
    image1 = {0};
    swap_buffers();
    
    if ((fd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("cannot create socket");
    }

    
    /* bind the socket to any valid IP address and a specific port */
    memset((char *)&myaddr, 0, sizeof(myaddr));
    myaddr.sin_family = AF_INET;
    myaddr.sin_addr.s_addr = htonl(INADDR_ANY);
    myaddr.sin_port = htons(9001);


    int recvBuff = 4*1024*1024;

    if (setsockopt(fd, SOL_SOCKET, SO_RCVBUF, (const void*)&recvBuff, sizeof(recvBuff)) < 0) {
        perror("Error setsockopt rcvbuf\n");
    }

    struct timeval tv;
    tv.tv_sec = 0;
    tv.tv_usec = 1500;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO,&tv,sizeof(tv)) < 0) {
        perror("Error");
    }


    if (bind(fd, (struct sockaddr *)&myaddr, sizeof(myaddr)) < 0) {
            perror("bind failed");
    }

    /* now loop, receiving data and printing what we received */
    t = new std::thread(&rx_thread);
}

void find_bounds(uint16_t* min, uint16_t* max, uint8_t* in){
    *min = 0xFFFF;
    *max = 0;

    for(int i= 0; i < 640*512; i++){
        uint16_t pixel = *in++;
        pixel |= ((*in++)<<8);

        if(pixel == 0xFFFF)
            continue;


        if(pixel == 0)
            continue;

        if(*min > pixel)
            *min = pixel;
        if(pixel > *max)
            *max = pixel;
    }
}

void create_colour_image(uint8_t* out, uint8_t* in){
    uint16_t min, max;
    find_bounds(&min, &max, in);

    double s = 255.0/(max - min);
    if(s > 1.0){
        s = 1.0;
    }

    for(int i = 0; i < 512; i++){
        for(int j = 0; j < 640; j++){
            int index = (i*1280) + (j*2);
            if(j & 1){
                index -= 2;
            }else{
                index += 2;
            }

        
            uint16_t pixel = (in[index]) | ((in[index+1])<<8);

            /* scale pixel */
            pixel = pixel - min;
            pixel *= s;

            *out++ = pixel;
            *out++ = pixel;
            *out++ = pixel;
            *out++ = 0xFF;
        }
    }

}

void format_buffer(image_t* i){
    // Load from file
    int image_width = 640;
    int image_height = 512;

    // Setup time step (we don't use SDL_GetTicks() because it is using millisecond resolution)
    static uint64_t frequency = SDL_GetPerformanceFrequency();
    uint64_t current_time = SDL_GetPerformanceCounter();
    float delta_time = last_time > 0 ? (float)((double)(current_time - last_time) / frequency) : (float)(1.0f / 60.0f);
    last_time = current_time;

    i->delta = delta_time;

    // Create a OpenGL texture identifier
    if(i->tex0 == 0){
        glGenTextures(1, (GLuint*)&i->tex0);
    }
    glBindTexture(GL_TEXTURE_2D, *(GLuint*)(&i->tex0));

    // Setup filtering parameters for display
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

    // Upload pixels into texture
    glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);

    uint8_t* image_colour = (uint8_t*)malloc(image_width * image_height * 4 * 2);
    create_colour_image(image_colour, i->data);

    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, image_width, image_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, image_colour);

    free(image_colour);
    i->generated = true;
}

uint32_t extract_uint32_t(uint8_t* p){
    return (p[0]) + (p[1] << 8) + (p[2] << 16) + (p[3] << 24);
}

uint16_t extract_uint16_t(uint8_t* p){
    return (p[0] << 8) + (p[1]);
}

int recvblock(int __fd, void* __buf, int __n, int __flags, sockaddr* __addr, socklen_t* __addr_len){
    int len = 0;
    uint8_t* offset_buf = (uint8_t*)__buf;

    while((len < __n) && !stop_thread_1){
        int rxlen = recv(__fd, offset_buf, __n - len, __flags);

        if(rxlen == -1){
            break;
        }

        len += rxlen;
        offset_buf += rxlen;
    }

    if(len == 0)
        return -1;

    return len;
}


void process_packet(uint8_t* p, int rxlen){
    if(rxlen > 6){
        int idx = extract_uint16_t(p);

        if(idx == 0){
            back_buffer->generated = false;
            swap_buffers();
        }

        memcpy(back_buffer->data + (1280 * idx), p + 2, 1280);

    }else{
        printf("rxlen=%u\n", rxlen);
    }
}



void rx_thread(){
    while(!stop_thread_1){
        recvlen = recvfrom(fd, buf, BUFSIZE, 0, (struct sockaddr *)&remaddr, &addrlen);
        
        /* Recieve block */
        if(recvlen == -1)
        {

        }else{
            /* Breakout data */
            process_packet(buf, recvlen);
        }
    }
}

void rx_close(){
    stop_thread_1 = true;
    t->join();
}

void swap_buffers(){
    mu.lock();
    if(front_buffer == &image0){
        front_buffer = &image1;
        back_buffer = &image0;
    }else{
        front_buffer = &image0;
        back_buffer = &image1;
    }
    mu.unlock();
}

image_t* getImage(){
    image_t* i;
    
    mu.lock();
    /* Pull out front buffer */
    i = front_buffer;
    
    if(i->generated == false){
        format_buffer(i);
    }
    mu.unlock();

    return i;
}