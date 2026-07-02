/**
 ******************************************************************************
 * @file    : board.h
 * @brief   : M144Z-M4最小系统板固定硬件配置
 * @说明    : 开发板固定的引脚分配，不可修改
 * @开发板  : M144Z-M4最小系统板 (STM32F407ZGTx)
 ******************************************************************************
 */

#ifndef __BOARD_H
#define __BOARD_H

#include "stm32f4xx_hal.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ========== 开发板信息 ========== */
#define BOARD_NAME     "M144Z-M4"
#define BOARD_MCU      "STM32F407ZGTx"

/* ========== LED引脚（固定） ========== */
/*
 * LED类型: 共阳极，低电平点亮
 */
#define BOARD_LED0_PORT        GPIOF
#define BOARD_LED0_PIN         GPIO_PIN_9      /* 左转向灯 */

#define BOARD_LED1_PORT        GPIOF
#define BOARD_LED1_PIN         GPIO_PIN_10     /* 右转向灯 */

/* LED控制宏（低电平亮） */
#define BOARD_LED_ON(__LED__)    HAL_GPIO_WritePin(__LED__##_PORT, __LED__##_PIN, GPIO_PIN_RESET)
#define BOARD_LED_OFF(__LED__)   HAL_GPIO_WritePin(__LED__##_PORT, __LED__##_PIN, GPIO_PIN_SET)
#define BOARD_LED_TOGGLE(__LED__) HAL_GPIO_TogglePin(__LED__##_PORT, __LED__##_PIN)

// 使用示例:
//   BOARD_LED_ON(BOARD_LED0);
//   BOARD_LED_OFF(BOARD_LED1);

/* ========== 按键引脚（固定位置，触发方式可变） ========== */
/*
 * 注意：这里只定义引脚位置
 * 触发方式（高/低电平）由项目配置决定
 */
#define BOARD_KEY0_PORT       GPIOE
#define BOARD_KEY0_PIN        GPIO_PIN_4       /* PE4 - 模式切换/BOOT0 */

#define BOARD_KEY_UP_PORT     GPIOA
#define BOARD_KEY_UP_PIN      GPIO_PIN_0       /* PA0 - 双闪开关/WKUP */

/* ========== 完全独立的IO引脚（可用作GPIO） ========== */
/*
 * 以下引脚通过跳线帽或焊接可达到完全悬空状态
 * 适合用作通用GPIO输入/输出
 */
#define BOARD_GPIO_PA1        GPIO_PIN_1
#define BOARD_GPIO_PA2        GPIO_PIN_2
#define BOARD_GPIO_PA3        GPIO_PIN_3
#define BOARD_GPIO_PA5        GPIO_PIN_5
#define BOARD_GPIO_PA7        GPIO_PIN_7
#define BOARD_GPIO_PA15       GPIO_PIN_15

#define BOARD_GPIO_PB10       GPIO_PIN_10
#define BOARD_GPIO_PB11       GPIO_PIN_11
#define BOARD_GPIO_PB12       GPIO_PIN_12
#define BOARD_GPIO_PB13       GPIO_PIN_13

#define BOARD_GPIO_PC0        GPIO_PIN_0
#define BOARD_GPIO_PC1        GPIO_PIN_1
#define BOARD_GPIO_PC2        GPIO_PIN_2
#define BOARD_GPIO_PC3        GPIO_PIN_3
#define BOARD_GPIO_PC4        GPIO_PIN_4
#define BOARD_GPIO_PC5        GPIO_PIN_5

#define BOARD_GPIO_PD3        GPIO_PIN_3

#define BOARD_GPIO_PE2        GPIO_PIN_2
#define BOARD_GPIO_PE3        GPIO_PIN_3

#define BOARD_GPIO_PF6        GPIO_PIN_6
#define BOARD_GPIO_PF7        GPIO_PIN_7
#define BOARD_GPIO_PF8        GPIO_PIN_8

#define BOARD_GPIO_PG6        GPIO_PIN_6
#define BOARD_GPIO_PG7        GPIO_PIN_7
#define BOARD_GPIO_PG8        GPIO_PIN_8
#define BOARD_GPIO_PG11       GPIO_PIN_11
#define BOARD_GPIO_PG13       GPIO_PIN_13
#define BOARD_GPIO_PG14       GPIO_PIN_14
#define BOARD_GPIO_PG15       GPIO_PIN_15

/* ========== 调试接口 ========== */
#define BOARD_SWDIO_PIN       GPIO_PIN_13      /* PA13 */
#define BOARD_SWCLK_PIN       GPIO_PIN_14      /* PA14 */

/* ========== 串口（CH340C） ========== */
#define BOARD_USART1_TX_PORT  GPIOA
#define BOARD_USART1_TX_PIN   GPIO_PIN_9       /* 需跳线帽 */

#define BOARD_USART1_RX_PORT  GPIOA
#define BOARD_USART1_RX_PIN   GPIO_PIN_10      /* 需跳线帽 */

/* ========== 系统配置 ========== */
#define BOARD_SYSCLK_FREQ     168000000UL      /* 168MHz */

#ifdef __cplusplus
}
#endif

#endif /* __BOARD_H */
