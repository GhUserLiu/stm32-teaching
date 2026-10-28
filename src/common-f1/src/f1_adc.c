/**
 * @file    f1_adc.c
 * @brief   ADC1 初始化与热敏换算实现
 */
#include "f1_adc.h"
#include "board_f1.h"

void f1_adc_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_ADC1;
    board_adc_pins_init();

    /* 采样时间：通道 4（光敏）/5（MQ-135）/6（热敏）取 239.5 周期
     * SMPR2 管通道 0~9，每通道 3bit：ch4=bit12-14, ch5=bit15-17, ch6=bit18-20 */
    ADC1->SMPR2 = (7u << 12) | (7u << 15) | (7u << 18);
    ADC1->CR1 = 0;
    ADC1->CR2 = ADC_CR2_ADON;                 /* 第一次写 ADON 唤醒 */
    for (volatile int i = 0; i < 1000; i++) { }

    ADC1->CR2 |= ADC_CR2_RSTCAL;              /* 复位校准 */
    while (ADC1->CR2 & ADC_CR2_RSTCAL) { }
    ADC1->CR2 |= ADC_CR2_CAL;                 /* 开始校准 */
    while (ADC1->CR2 & ADC_CR2_CAL) { }
}

uint16_t f1_adc_read_avg(uint8_t channel, uint8_t n)
{
    if (n == 0) n = 1;
    uint32_t sum = 0;
    for (uint8_t i = 0; i < n; i++)
        sum += adc1_read(channel);
    return (uint16_t)(sum / n);
}

int16_t f1_ntc_temp_x10(uint16_t raw)
{
    /* 保护边界 */
    if (raw < 20)   raw = 20;
    if (raw > 4075) raw = 4075;

    /* R_ntc = 10000 * raw / (4096 - raw)  （定阻上拉在上侧时） */
    int32_t r_ntc = (int32_t)((10000.0 * raw) / (4096.0 - raw) + 0.5);

    /* T = B / ( ln(R/R0) + B/T0 ) ，B=3950，T0=298.15K */
    /* ln 查无 libm 依赖：用近似 ln(x) = 2*Σ …，教学上用对数级数+范围归一。
     * 简洁做法：ln(r/10000) = ln(r) - ln(10000)。这里用逐次开方近似太繁，
     * 直接链接 libm（-lm，newlib 提供 log()）。 */
    extern double log(double);
    double b = 3950.0;
    double t0 = 298.15;
    double t_k = 1.0 / (log((double)r_ntc / 10000.0) / b + 1.0 / t0);
    return (int16_t)((t_k - 273.15) * 10.0 + 0.5);
}
