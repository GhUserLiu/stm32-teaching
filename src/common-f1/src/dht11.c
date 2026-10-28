/**
 * @file    dht11.c
 * @brief   DHT11 单总线驱动（时序依据 DHT11 数据手册）
 *
 * 起始：主机拉低 ≥18ms → 拉高 20~40us → 释放
 * 响应：DHT 拉低 80us → 拉高 80us
 * 数据：每 bit 以 50us 低电平开始，高电平 26~28us=0、70us=1
 * 校验：前 4 字节之和低 8 位 == 第 5 字节
 */
#include "dht11.h"
#include "board_f1.h"
#include "f1_delay.h"

#define DHT_PORT DHT11_PORT
#define DHT_PIN  DHT11_PIN

static void dht_out(void) { gpio_init(DHT_PORT, DHT_PIN, GPIO_MODE_OUT_PP_2); }
static void dht_in(void)  { gpio_init(DHT_PORT, DHT_PIN, GPIO_MODE_IN_PUPD);
                            gpio_set(DHT_PORT, DHT_PIN); }   /* 上拉输入 */

/* 等待引脚变到 level，超时返回 -1 */
static int wait_level(int level, uint32_t timeout_us)
{
    while (timeout_us--) {
        if (gpio_read(DHT_PORT, DHT_PIN) == level) return 0;
        delay_us(1);
    }
    return -1;
}

void dht11_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPB;
    dht_in();   /* 空闲态：上拉输入 */
}

int dht11_read(int16_t *temp_out, int16_t *humi_out)
{
    uint8_t d[5] = {0, 0, 0, 0, 0};

    /* 起始信号 */
    dht_out();
    gpio_reset(DHT_PORT, DHT_PIN);
    delay_ms(20);
    gpio_set(DHT_PORT, DHT_PIN);
    delay_us(30);
    dht_in();

    /* 响应：低 80us → 高 80us */
    if (wait_level(0, 60)  != 0) return -1;   /* 等 DHT 拉低 */
    if (wait_level(1, 100) != 0) return -1;   /* 等 DHT 释放 */
    if (wait_level(0, 100) != 0) return -1;   /* 80us 高结束 */

    for (int i = 0; i < 40; i++) {
        if (wait_level(1, 80) != 0) return -1;   /* 50us 低结束 */
        /* 高电平时长判 0/1：以 50us 为界 */
        uint32_t t = 0;
        while (gpio_read(DHT_PORT, DHT_PIN) == 1 && t < 100) { delay_us(1); t++; }
        if (t >= 100) return -1;
        d[i / 8] <<= 1;
        if (t > 40) d[i / 8] |= 1;   /* >40us 视为 1（26~28 vs 70） */
    }

    if ((uint8_t)(d[0] + d[1] + d[2] + d[3]) != d[4]) return -2;

    *humi_out = (int16_t)(d[0] * 10 + d[1]);   /* DHT11 小数恒 0 */
    *temp_out = (int16_t)(d[2] * 10 + d[3]);
    return 0;
}
