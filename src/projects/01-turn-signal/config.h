/**
 ******************************************************************************
 * @file    : config.h
 * @brief   : 转向灯系统项目配置
 ******************************************************************************
 */

#ifndef __CONFIG_H
#define __CONFIG_H

/* ========== 按键触发方式配置 ========== */
/*
 * 说明：根据外部电路决定
 * - 按键一端接GPIO，另一端接VCC则高电平触发（需下拉电阻）
 * - 按键一端接GPIO，另一端接GND则低电平触发（需上拉电阻）
 */

/* KEY0 - PE4: 高电平触发 */
#define KEY0_TRIGGER_HIGH  1

/* KEY_UP - PA0: 低电平触发 */
#define KEY_UP_TRIGGER_HIGH 0

/* ========== 上拉/下拉选择宏 ========== */
#define KEY_PULL(__LEVEL__)  ((__LEVEL__) ? GPIO_PULLDOWN : GPIO_PULLUP)

/* ========== 时序配置（毫秒） ========== */
#define MAIN_LOOP_DELAY   10            /* 主循环延时 */
#define LED_TOGGLE_COUNT  25            /* LED切换计数 (250ms闪烁周期) */

/* ========== 开机演示配置 ========== */
#define POWER_ON_BLINK_TIMES  3         /* 开机闪烁次数 */
#define POWER_ON_BLINK_DELAY  300       /* 开机闪烁延时 300ms */

/* ========== 按键消抖配置（毫秒） ========== */
#define KEY_DEBOUNCE_DELAY   20         /* 消抖延时 */
#define KEY_WAIT_DELAY       10         /* 等待释放延时 */

#endif /* __CONFIG_H */
