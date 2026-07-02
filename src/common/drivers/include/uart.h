/**
  ******************************************************************************
  * @file    : uart.h
  * @brief   : UART驱动头文件 - 遵循HAL库规范
  * @author  : 项目开发者
  * @date    : 2026-06-11
  ******************************************************************************
  * @attention
  *
  * 本驱动基于STM32 HAL库实现，提供简化的UART接口
  * 支持基本的发送、接收功能
  *
  ******************************************************************************
  */

#ifndef __UART_H
#define __UART_H

#ifdef __cplusplus
extern "C" {
#endif

/* ========== Includes ========== */
#include "stm32f4xx_hal.h"
#include <stdint.h>
#include <stdbool.h>

/* ========== Macros ========== */

/** @defgroup UART_Exported_Constants UART导出常量
  * @{
  */

/* UART缓冲区大小 */
#define UART_RX_BUFFER_SIZE     256u
#define UART_TX_BUFFER_SIZE     256u

/* UART超时时间（毫秒） */
#define UART_DEFAULT_TIMEOUT    1000u

/* UART波特率选项 */
#define UART_BAUDRATE_9600      9600u
#define UART_BAUDRATE_19200     19200u
#define UART_BAUDRATE_38400     38400u
#define UART_BAUDRATE_57600     57600u
#define UART_BAUDRATE_115200    115200u

/** @} */

/* ========== Type Definitions ========== */

/** @defgroup UART_Exported_Types UART导出类型
  * @{
  */

/**
  * @brief  UART状态枚举
  */
typedef enum {
    UART_STATE_OK = 0,          /**< 操作成功 */
    UART_STATE_ERROR,           /**< 一般错误 */
    UART_STATE_BUSY,            /**< UART忙 */
    UART_STATE_TIMEOUT,         /**< 超时 */
    UART_STATE_NOT_READY        /**< 未准备好 */
} UART_State_t;

/**
  * @brief  UART配置结构体
  */
typedef struct {
    uint32_t baud_rate;         /**< 波特率 */
    uint32_t word_length;       /**< 数据位长度 */
    uint32_t stop_bits;         /**< 停止位 */
    uint32_t parity;            /**< 校验位 */
    uint32_t mode;              /**< 模式（TX/RX/TX_RX） */
} UART_Config_t;

/**
  * @brief  UART句柄结构体
  */
typedef struct {
    UART_HandleTypeDef handle;           /**< HAL库句柄 */
    UART_Config_t config;                /**< 配置参数 */
    uint8_t *rx_buffer;                 /**< 接收缓冲区 */
    uint8_t *tx_buffer;                 /**< 发送缓冲区 */
    volatile uint16_t rx_count;          /**< 接收计数 */
    volatile uint16_t tx_count;          /**< 发送计数 */
    volatile bool is_ready;              /**< 就绪标志 */
} UART_HandleTypeDef;

/** @} */

/* ========== Function Declarations ========== */

/** @defgroup UART_Exported_Functions UART导出函数
  * @{
  */

/* 初始化和配置 */
UART_State_t UART_Init(UART_HandleTypeDef *huart, USART_TypeDef *instance, const UART_Config_t *config);
void UART_DeInit(UART_HandleTypeDef *huart);

/* 数据发送 */
UART_State_t UART_Transmit(UART_HandleTypeDef *huart, const uint8_t *data, uint16_t length, uint32_t timeout);
UART_State_t UART_Transmit_IT(UART_HandleTypeDef *huart, const uint8_t *data, uint16_t length);
UART_State_t UART_Transmit_DMA(UART_HandleTypeDef *huart, const uint8_t *data, uint16_t length);

/* 数据接收 */
UART_State_t UART_Receive(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length, uint32_t timeout);
UART_State_t UART_Receive_IT(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length);
UART_State_t UART_Receive_DMA(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length);

/* 字符发送/接收（简化接口） */
UART_State_t UART_SendChar(UART_HandleTypeDef *huart, uint8_t ch, uint32_t timeout);
UART_State_t UART_SendString(UART_HandleTypeDef *huart, const char *str, uint32_t timeout);
UART_State_t UART_SendBuffer(UART_HandleTypeDef *huart, const uint8_t *buffer, uint16_t length, uint32_t timeout);
int UART_GetChar(UART_HandleTypeDef *huart, uint32_t timeout);

/* 状态查询 */
bool UART_IsReady(UART_HandleTypeDef *huart);
bool UART_IsBusy(UART_HandleTypeDef *huart);
void UART_ClearError(UART_HandleTypeDef *huart);

/* 打印函数（类似printf） */
int UART_Printf(UART_HandleTypeDef *huart, const char *format, ...);

/** @} */

/* ========== Default Configuration ========== */

/** @defgroup UART_Default_Configuration UART默认配置
  * @{
  */

/* 默认UART配置宏 */
#define UART_DEFAULT_CONFIG_INIT    \
{                                   \
    .baud_rate = UART_BAUDRATE_115200,  \
    .word_length = UART_WORDLENGTH_8B,  \
    .stop_bits = UART_STOPBITS_1,       \
    .parity = UART_PARITY_NONE,         \
    .mode = UART_MODE_TX_RX             \
}

/** @} */

#ifdef __cplusplus
}
#endif

#endif /* __UART_H */
