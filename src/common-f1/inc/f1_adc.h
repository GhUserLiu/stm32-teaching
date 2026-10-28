/**
 * @file    f1_adc.h
 * @brief   ADC1 辅助：初始化 + 光敏/热敏原始值 + 热敏摄氏温度换算
 */
#ifndef F1_ADC_H
#define F1_ADC_H

#include <stdint.h>

/** @brief ADC1 初始化（校准，单次转换模式） */
void f1_adc_init(void);

/** @brief 读取并平均 n 次的原始值（0~4095） */
uint16_t f1_adc_read_avg(uint8_t channel, uint8_t n);

/**
 * @brief NTC 10K（B=3950，上拉 10K 到 3.3V）热敏电阻 → 摄氏温度
 * @param raw ADC 原始值
 * @return 温度（℃，保留 1 位小数的整 10 倍值，如 253 = 25.3℃）
 *
 * 接法：3.3V —10K— ADC_PIN—NTC—GND
 * V_ntc = 3.3 * R_ntc / (R_fixed + R_ntc) ……
 * R_ntc = R_fixed * V/(3.3 - V)
 * T(K) = 1 / (1/T0 + ln(R_ntc/R0)/B)，T0=298.15K，R0=10K
 */
int16_t f1_ntc_temp_x10(uint16_t raw);

#endif /* F1_ADC_H */
