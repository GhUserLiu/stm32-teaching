/**
 * @file    main.c
 * @brief   Day4 例程：显示层 —— OLED 显示 + 串口 printf
 *
 * 现象：
 *   OLED 第一行显示标题，第二行显示运行秒数，第三/四行显示温湿度与光照；
 *   串口同步输出同样数据。
 *
 * 学习点：SSD1306 初始化序列、软件 I2C 时序、帧缓冲刷新、
 *         printf 重定向（f1_printf.c 的 _write）。
 */
#include <stdio.h>
#include "board_f1.h"
#include "f1_delay.h"
#include "dht11.h"
#include "ssd1306.h"
#include "f1_adc.h"

int main(void)
{
    sysclock_init_72m();
    f1_delay_init();
    board_uart1_init(115200);
    dht11_init();
    ssd1306_init();
    f1_adc_init();

    uint32_t t_ui = 0, t_dht = 0;
    int16_t temp = 0, humi = 0;
    uint16_t light = 0;
    uint32_t secs = 0;

    while (1) {
        /* 温湿度 2s 一次（DHT11 最快 1Hz） */
        if (every_ms(&t_dht, 2000))
            dht11_read(&temp, &humi);
        /* 光照 500ms 一次 */
        if (every_ms(&t_ui, 500)) {
            light = f1_adc_read_avg(ADC_CH_LIGHT, 8);
        }
        /* OLED + 串口 1s 刷新 */
        static uint32_t t_disp = 0;
        if (every_ms(&t_disp, 1000)) {
            secs++;
            char buf[24];

            ssd1306_clear();
            ssd1306_string(0, 0, "DAY4 OLED DEMO");
            snprintf(buf, sizeof(buf), "t=%us", (unsigned)secs);
            ssd1306_string(0, 2, buf);
            snprintf(buf, sizeof(buf), "T:%d.%dC H:%d%%",
                     temp / 10, temp % 10, humi / 10);
            ssd1306_string(0, 4, buf);
            snprintf(buf, sizeof(buf), "LIGHT:%4u", light);
            ssd1306_string(0, 5, buf);
            ssd1306_flush();

            printf("[UI] t=%u T:%d.%dC H:%d%% L:%u\r\n",
                   (unsigned)secs, temp / 10, temp % 10, humi / 10, light);
        }
    }
}
