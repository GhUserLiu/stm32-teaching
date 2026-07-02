/**
  ******************************************************************************
  * @file    : error_handler.h
  * @brief   : 统一错误处理框架 - 遵循HAL库规范
  * @author  : 项目开发者
  * @date    : 2026-06-11
  ******************************************************************************
  * @attention
  *
  * 本文件定义了项目统一的错误处理机制
  * 包括错误代码、错误处理函数和错误恢复机制
  *
  ******************************************************************************
  */

#ifndef __ERROR_HANDLER_H
#define __ERROR_HANDLER_H

#ifdef __cplusplus
extern "C" {
#endif

/* ========== Includes ========== */
#include <stdint.h>
#include <stdbool.h>

/* ========== Macros ========== */

/** @defgroup ERROR_Exported_Constants 错误处理导出常量
  * @{
  */

/* 错误LED配置（可在board.h中覆盖） */
#ifndef ERROR_LED_PORT
#define ERROR_LED_PORT     GPIOF
#define ERROR_LED_PIN      GPIO_PIN_9
#endif

/* 错误指示闪烁频率（毫秒） */
#define ERROR_BLINK_FAST   100u    /**< 快速闪烁（严重错误） */
#define ERROR_BLINK_SLOW   500u    /**< 慢速闪烁（一般错误） */

/** @} */

/* ========== Type Definitions ========== */

/** @defgroup ERROR_Exported_Types 错误处理导出类型
  * @{
  */

/**
  * @brief  错误代码枚举
  */
typedef enum {
    ERR_OK = 0,                      /**< 无错误 */
    ERR_UNKNOWN,                     /**< 未知错误 */
    ERR_HAL_INIT,                    /**< HAL初始化失败 */
    ERR_CLOCK_CONFIG,                /**< 时钟配置失败 */
    ERR_GPIO_INIT,                   /**< GPIO初始化失败 */
    ERR_UART_INIT,                   /**< UART初始化失败 */
    ERR_UART_TX,                     /**< UART发送失败 */
    ERR_UART_RX,                     /**< UART接收失败 */
    ERR_TIMER_INIT,                  /**< 定时器初始化失败 */
    ERR_HARD_FAULT,                  /**< 硬件错误 */
    ERR_MEM_MANAGE,                  /**< 内存管理错误 */
    ERR_BUS_FAULT,                   /**< 总线错误 */
    ERR_USAGE_FAULT,                 /**< 使用错误 */
    ERR_TIMEOUT,                     /**< 超时错误 */
    ERR_BUSY,                        /**< 资源忙 */
    ERR_PARAM,                       /**< 参数错误 */
    ERR_NO_RESOURCE,                 /**< 资源不足 */
    ERR_BUFFER_OVERFLOW,             /**< 缓冲区溢出 */
    ERR_WATCHDOG_RESET               /**< 看门狗复位 */
} ErrorCode_t;

/**
  * @brief  错误严重级别枚举
  */
typedef enum {
    ERR_LEVEL_INFO = 0,              /**< 信息级别 */
    ERR_LEVEL_WARNING,               /**< 警告级别 */
    ERR_LEVEL_ERROR,                 /**< 错误级别 */
    ERR_LEVEL_CRITICAL,              /**< 严重错误 */
    ERR_LEVEL_FATAL                  /**< 致命错误 */
} ErrorLevel_t;

/**
  * @brief  错误信息结构体
  */
typedef struct {
    ErrorCode_t code;                /**< 错误代码 */
    ErrorLevel_t level;              /**< 错误级别 */
    const char *message;             /**< 错误消息 */
    uint32_t timestamp;              /**< 时间戳 */
    uint16_t line;                   /**< 代码行号（可选） */
    const char *file;                /**< 文件名（可选） */
} ErrorInfo_t;

/** @} */

/* ========== Function Declarations ========== */

/** @defgroup ERROR_Exported_Functions 错误处理导出函数
  * @{
  */

/* ========== 错误处理函数 ========== */
void Error_Handler(void);
void Error_Handler_WithCode(ErrorCode_t code);
void Error_Handler_WithInfo(const ErrorInfo_t *info);
void Error_Handler_Detailed(ErrorCode_t code, const char *file, uint16_t line);

/* ========== 错误信息函数 ========== */
const char* Error_GetMessage(ErrorCode_t code);
ErrorLevel_t Error_GetLevel(ErrorCode_t code);
void Error_Log(ErrorCode_t code, ErrorLevel_t level, const char *message);

/* ========== 错误恢复函数 ========== */
void Error_Clear(void);
void Error_Recover(ErrorCode_t code);
bool Error_CanRecover(ErrorCode_t code);

/* ========== 错误统计函数 ========== */
uint32_t Error_GetCount(void);
void Error_ResetCount(void);

/* ========== 便捷宏 ========== */
#define ERROR_HANDLER(code)              Error_Handler_Detailed((code), __FILE__, __LINE__)
#define ERROR_HANDLER_MSG(code, msg)     Error_Handler_Detailed((code), msg, 0)

/** @} */

/* ========== Watchdog Functions ========== */
#if defined(USE_WATCHDOG) && (USE_WATCHDOG == 1)
void Watchdog_Init(void);
void Watchdog_Refresh(void);
void Watchdog_Handler(void);
#endif

#ifdef __cplusplus
}
#endif

#endif /* __ERROR_HANDLER_H */
