/**
 ******************************************************************************
 * @file    : config.h
 * @brief   : Test6 项目配置 - 智能灯光控制系统（状态机版本）
 ******************************************************************************
 */

#ifndef __CONFIG_H
#define __CONFIG_H

/* ========== 按键触发方式配置 ========== */
/* KEY0 - PE4: 低电平触发 */
#define KEY0_TRIGGER_HIGH  0

/* KEY_UP - PA0: 低电平触发 */
#define KEY_UP_TRIGGER_HIGH 0

/* ========== 上拉/下拉选择宏 ========== */
#define KEY_PULL(__LEVEL__)  ((__LEVEL__) ? GPIO_PULLDOWN : GPIO_PULLUP)

/* ========== 时序配置（毫秒） ========== */
#define MAIN_LOOP_DELAY   10            /* 主循环延时 */
#define LED_TOGGLE_COUNT  50            /* LED切换计数 (500ms = 1Hz闪烁周期) */

/* ========== 按键消抖配置（毫秒） ========== */
#define KEY_DEBOUNCE_DELAY   20         /* 消抖延时 */

#endif /* __CONFIG_H */
