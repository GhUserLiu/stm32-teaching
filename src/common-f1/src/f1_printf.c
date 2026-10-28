/**
 * @file    f1_printf.c
 * @brief   printf 重定向到 UART1（115200-8N1）
 */
#include <stdio.h>
#include "board_f1.h"

int f1_stdio_uart_ready = 0;   /* board_uart1_init 后置 1 */

int _write(int fd, char *ptr, int len)
{
    (void)fd;
    for (int i = 0; i < len; i++) {
        uart1_putc(ptr[i]);
    }
    return len;
}

int _read(int fd, char *ptr, int len)
{
    (void)fd; (void)ptr; (void)len;
    return 0;
}
