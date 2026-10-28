/**
 * @file    main.c
 * @brief   Day2~3 例程：感知层 —— DHT11 温湿度 + 光敏/热敏 ADC（串口输出）
 *
 * 现象（串口 115200，每 1s 一行）：
 *   [SEN] T:25.0C H:41% LIGHT:1890 NTC:2050 NTC_T:26.3C
 *
 * 学习点：单总线时序（DHT11）、ADC 单次转换与均值滤波、
 *         NTC B 值公式换算（B=3950，10K 上拉）、数据记录表填写。
 */
#include <stdio.h>
#include "board_f1.h"
#include "f1_delay.h"
#include "dht11.h"
#include "f1_adc.h"

int main(void)
{
    sysclock_init_72m();
    f1_delay_init();
    board_uart1_init(115200);
    dht11_init();
    f1_adc_init();

    printf("=== Day2-3 Sensors ===\r\n");

    uint32_t t_sen = 0;
    while (1) {
        if (every_ms(&t_sen, 1000)) {
            int16_t temp = 0, humi = 0;
            int rc = dht11_read(&temp, &humi);

            uint16_t light = f1_adc_read_avg(ADC_CH_LIGHT, 8);
            uint16_t ntc   = f1_adc_read_avg(ADC_CH_NTC, 8);
            int16_t ntc_t  = f1_ntc_temp_x10(ntc);

            if (rc == 0)
                printf("[SEN] T:%d.%dC H:%d%% ", temp / 10, temp % 10, humi / 10);
            else
                printf("[SEN] DHT11 ERR(%d) ", rc);
            printf("LIGHT:%4u NTC:%4u NTC_T:%d.%dC\r\n", light, ntc,
                   ntc_t / 10, ntc_t % 10);
        }
    }
}
