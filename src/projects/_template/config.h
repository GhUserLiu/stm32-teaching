/**
  ******************************************************************************
  * @file    : config.h
  * @brief   : 项目配置文件 - 遵循HAL库规范
  * @author  : 项目开发者
  * @date    : 2026-06-11
  ******************************************************************************
  * @attention
  *
  * 本文件只配置项目特定参数
  * 硬件固定配置请参考 board.h
  *
  ******************************************************************************
  */

#ifndef __CONFIG_H
#define __CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

/* ========== Includes ========== */
#include "stm32f4xx_hal.h"

/* ========== 按键触发方式配置 ========== */

/**
  * @brief 按键触发方式说明
  * @note  根据外部电路决定：
  *        - 按键一端接GPIO，另一端接VCC → 高电平触发（需下拉电阻）
  *        - 按键一端接GPIO，另一端接GND → 低电平触发（需上拉电阻）
  */

// #define KEY0_TRIGGER_HIGH     1   /* BOARD_KEY0 = PE4 */
// #define KEY_UP_TRIGGER_HIGH   0   /* BOARD_KEY_UP = PA0 */

/* ========== 上拉/下拉选择宏 ========== */
#define KEY_PULL(__LEVEL__)  ((__LEVEL__) ? GPIO_PULLDOWN : GPIO_PULLUP)

/* ========== 时序配置 ========== */

/** @defgroup Timing_Config 时序配置
  * @{
  */
#define MAIN_LOOP_DELAY       10u    /**< 主循环延时（毫秒） */
#define KEY_DEBOUNCE_DELAY    20u    /**< 按键消抖延时（毫秒） */
#define LED_BLINK_DELAY       500u   /**< LED闪烁延时（毫秒） */
/** @} */

/* ========== 外设配置 ========== */

/** @defgroup Peripheral_Config 外设配置
  * @{
  */

/* UART配置（如需使用） */
// #define UART_BAUDRATE         115200u
// #define UART_TIMEOUT          1000u

/* SPI配置（如需使用） */
// #define SPI_BAUDRATE_PRESCALER  SPI_BAUDRATEPRESCALER_8

/* I2C配置（如需使用） */
// #define I2C_CLOCK_SPEED        100000u
// #define I2C_TIMEOUT            1000u

/* 定时器配置（如需使用） */
// #define TIMER_PERIOD           1000u
// #define TIMER_PRESCALER        8400u   /* 84MHz/8400 = 10kHz */

/** @} */

/* ========== 项目特定配置 ========== */

/**
  * @defgroup Project_Config 项目特定配置
  * @brief  在此添加你的项目配置
  * @{
  */

// TODO: 添加你的配置定义
// #define YOUR_CONFIG_VALUE    100

/** @} */

#ifdef __cplusplus
}
#endif

#endif /* __CONFIG_H */
