#ifndef TIME_H__
#define TIME_H__

#include <time.h>

void time_init(void);
int elapsed(int *last_event, int period);
void msleep(int);

#endif