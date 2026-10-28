/**
 * @file    f1_fan.h
 * @brief   TB6612FNG 有刷电机（风扇）驱动：PWM 调速 + 正反转
 *
 * PWMA = PA8 (TIM1_CH1，72MHz/72=1MHz 计数，ARR=999 → 1kHz PWM)
 * AIN1 = PB0，AIN2 = PB1
 * 注意：电机用独立 5V 电源，与核心板共地（实施方案安全条款）。
 */
#ifndef F1_FAN_H
#define F1_FAN_H

#include <stdint.h>

/** @brief TB6612 引脚与 TIM1 CH1 PWM 初始化（风扇停转态） */
void fan_init(void);

/** @brief 设置风扇占空比 0~100（0=停） */
void fan_set(uint8_t duty);

/** @brief 风扇停转 */
void fan_stop(void);

#endif /* F1_FAN_H */
