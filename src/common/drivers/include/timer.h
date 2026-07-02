/**
  ******************************************************************************
  * @file    : timer.h
  * @brief   : 定时器驱动头文件 - 遵循HAL库规范
  * @author  : 项目开发者
  * @date    : 2026-06-11
  ******************************************************************************
  * @attention
  *
  * 本驱动基于STM32 HAL库实现，提供简化的定时器接口
  * 支持基本定时、延时、PWM输出等功能
  *
  ******************************************************************************
  */

#ifndef __TIMER_H
#define __TIMER_H

#ifdef __cplusplus
extern "C" {
#endif

/* ========== Includes ========== */
#include "stm32f4xx_hal.h"
#include <stdint.h>
#include <stdbool.h>

/* ========== Macros ========== */

/** @defgroup TIMER_Exported_Constants 定时器导出常量
  * @{
  */

/* DWT周期计数器配置 */
#define DWT_CYCCNT_ADDR    (0xE0001004u)
#define DWT_CONTROL_ADDR   (0xE0001000u)
#define DWT_CYCCNT_EN_BIT  (0x1u << 0)

/** @} */

/* ========== Type Definitions ========== */

/** @defgroup TIMER_Exported_Types 定时器导出类型
  * @{
  */

/**
  * @brief  定时器状态枚举
  */
typedef enum {
    TIMER_STATE_OK = 0,         /**< 操作成功 */
    TIMER_STATE_ERROR,          /**< 一般错误 */
    TIMER_STATE_BUSY,           /**< 定时器忙 */
    TIMER_STATE_TIMEOUT,        /**< 超时 */
    TIMER_STATE_NOT_READY       /**< 未准备好 */
} Timer_State_t;

/**
  * @brief  定时器配置结构体
  */
typedef struct {
    uint32_t period;            /**< 定时周期（计数器自动重装载值） */
    uint32_t prescaler;         /**< 预分频值 */
    uint32_t clock_division;    /**< 时钟分频 */
    uint32_t counter_mode;      /**< 计数模式 */
} Timer_Config_t;

/**
  * @brief  定时器句柄结构体
  */
typedef struct {
    TIM_HandleTypeDef handle;           /**< HAL库句柄 */
    Timer_Config_t config;              /**< 配置参数 */
    volatile uint32_t counter;          /**< 软件计数器 */
    volatile bool is_running;           /**< 运行标志 */
    volatile uint32_t tick_count;       /**< 系统滴答计数 */
} Timer_HandleTypeDef_t;

/**
  * @brief  DWT延时器句柄
  */
typedef struct {
    uint32_t clock_freq;        /**< 系统时钟频率（Hz） */
    uint32_t us_per_tick;       /**< 每个计数的微秒数 */
} DWT_Handle_t;

/** @} */

/* ========== Function Declarations ========== */

/** @defgroup TIMER_Exported_Functions 定时器导出函数
  * @{
  */

/* ========== 基本定时器功能 ========== */
Timer_State_t Timer_Init(Timer_HandleTypeDef_t *htim, TIM_TypeDef *instance, const Timer_Config_t *config);
void Timer_DeInit(Timer_HandleTypeDef_t *htim);
Timer_State_t Timer_Start(Timer_HandleTypeDef_t *htim);
Timer_State_t Timer_Stop(Timer_HandleTypeDef_t *htim);
bool Timer_IsRunning(Timer_HandleTypeDef_t *htim);

/* ========== 延时功能 ========== */
void Timer_Delay_ms(uint32_t ms);
void Timer_Delay_us(uint32_t us);

/* ========== DWT精准延时 ========== */
void DWT_Init(void);
uint32_t DWT_GetCycle(void);
void DWT_Delay_us(uint32_t us);

/* ========== 微秒级延时（基于DWT） ========== */
#define delay_us(us)      DWT_Delay_us(us)
#define delay_ms(ms)      Timer_Delay_ms(ms)

/** @} */

/* ========== Default Configuration ========== */

/** @defgroup TIMER_Default_Configuration 定时器默认配置
  * @{
  */

/* 默认定时器配置（1ms定时，假设84MHz时钟） */
#define TIMER_DEFAULT_CONFIG_INIT    \
{                                     \
    .period = 1000u,                  \
    .prescaler = 8400u,               \
    .clock_division = 0,              \
    .counter_mode = TIM_COUNTERMODE_UP \
}

/** @} */

#ifdef __cplusplus
}
#endif

#endif /* __TIMER_H */
