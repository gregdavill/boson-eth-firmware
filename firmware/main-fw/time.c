#include "include/time.h"
#include <generated/csr.h>

void msleep(int ms)
{
    int last_event = 0;
    elapsed(&last_event, -1); /* Get current time */

    while(!elapsed(&last_event, ms * CONFIG_CLOCK_FREQUENCY/1000)){}
}