/**
 * @file    f1_delay.h
 * @brief   SysTick 微秒/毫秒延时 + 毫秒滴答计数（72MHz）
 */
#ifndef F1_DELAY_H
#define F1_DELAY_H

#include <stdint.h>

/** @brief SysTick 初始化（1us 计数基准） */
void f1_delay_init(void);

/** @brief 微秒阻塞延时（基于 SysTick 轮询，不占中断） */
void delay_us(uint32_t us);

/** @brief 毫秒阻塞延时 */
void delay_ms(uint32_t ms);

/** @brief 毫秒滴答计数（SysTick 中断累加），供非阻塞周期调度用 */
uint32_t f1_tick(void);

/** @brief 非阻塞周期判定：now 距 *last >= period_ms 时更新 *last 并返回 1 */
int every_ms(uint32_t *last, uint32_t period_ms);

#endif /* F1_DELAY_H */
