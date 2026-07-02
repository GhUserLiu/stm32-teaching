/**
  ******************************************************************************
  * @file    : error_handler.c
  * @brief   : 统一错误处理框架实现 - 遵循HAL库规范
  * @author  : 项目开发者
  * @date    : 2026-06-12
  * @version : 2.0.0 - 完善了UART输出和看门狗功能
  ******************************************************************************
  * @attention
  *
  * 本文件实现了项目统一的错误处理机制
  * - 支持UART错误信息输出
  * - 支持看门狗初始化和刷新
  * - 支持错误恢复机制
  *
  ******************************************************************************
  */

/* ========== Includes ========== */
#include "error_handler.h"
#include "stm32f4xx_hal.h"
#include <stdio.h>
#include <string.h>

/* ========== Private Variables ========== */
static volatile uint32_t error_count = 0;
static volatile ErrorCode_t last_error_code = ERR_OK;

/* UART句柄（用于错误信息输出）- 可选 */
/* 注意：如果使用UART输出，需要在main.c中定义并初始化huart1 */
#ifdef USE_ERROR_UART
extern UART_HandleTypeDef huart1;
#endif

/* ========== Private Function Prototypes ========== */
static void Error_LED_Update(ErrorLevel_t level);
static void Error_System_Reset(void);
static void Error_UART_Output(const char *message);

/* ========== Private Function Prototypes ========== */
static void Error_LED_Update(ErrorLevel_t level);
static void Error_System_Reset(void);

/* ========== Public Function Definitions ========== */

/**
  * @brief  默认错误处理函数
  * @retval None
  * @note   当发生严重错误时调用
  */
void Error_Handler(void)
{
    /* 更新错误统计 */
    error_count++;
    last_error_code = ERR_UNKNOWN;

    /* 禁用中断 */
    __disable_irq();

    /* 进入死循环（LED闪烁表示错误状态） */
    while (1)
    {
        HAL_GPIO_TogglePin(ERROR_LED_PORT, ERROR_LED_PIN);
        HAL_Delay(ERROR_BLINK_SLOW);
    }
}

/**
  * @brief  带错误代码的处理函数
  * @param  code: 错误代码
  * @retval None
  */
void Error_Handler_WithCode(ErrorCode_t code)
{
    /* 更新错误统计 */
    error_count++;
    last_error_code = code;

    /* 获取错误级别 */
    ErrorLevel_t level = Error_GetLevel(code);

    /* 根据错误级别决定处理方式 */
    if (level >= ERR_LEVEL_CRITICAL)
    {
        /* 严重错误：禁用中断并进入错误状态 */
        __disable_irq();

        while (1)
        {
            Error_LED_Update(level);
        }
    }
    else if (level >= ERR_LEVEL_ERROR)
    {
        /* 一般错误：保持中断，LED慢闪 */
        while (1)
        {
            Error_LED_Update(level);
        }
    }
    else
    {
        /* 警告或信息：仅记录，不停止程序 */
        /* 可以选择清空错误并继续运行 */
        Error_Clear();
    }
}

/**
  * @brief  带详细信息的错误处理函数
  * @param  code: 错误代码
  * @param  file: 发生错误的文件名
  * @param  line: 发生错误的代码行号
  * @retval None
  */
void Error_Handler_Detailed(ErrorCode_t code, const char *file, uint16_t line)
{
    /* 更新错误统计 */
    error_count++;
    last_error_code = code;

    /* 获取错误级别和消息 */
    ErrorLevel_t level = Error_GetLevel(code);
    const char *message = Error_GetMessage(code);

    /* 通过UART输出错误信息（如果UART已初始化） */
    char error_buffer[128];
    int len = snprintf(error_buffer, sizeof(error_buffer),
                       "Error: %s (0x%X) in %s:%d\r\n", message, code, file, line);
    if (len > 0 && len < sizeof(error_buffer))
    {
        Error_UART_Output(error_buffer);
    }

    /* 根据错误级别处理 */
    if (level >= ERR_LEVEL_CRITICAL)
    {
        __disable_irq();

        while (1)
        {
            Error_LED_Update(level);
        }
    }
}

/**
  * @brief  带完整错误信息的处理函数
  * @param  info: 错误信息结构体指针
  * @retval None
  */
void Error_Handler_WithInfo(const ErrorInfo_t *info)
{
    if (info == NULL)
    {
        Error_Handler();
        return;
    }

    /* 更新错误统计 */
    error_count++;
    last_error_code = info->code;

    /* 根据错误级别处理 */
    if (info->level >= ERR_LEVEL_CRITICAL)
    {
        __disable_irq();

        while (1)
        {
            Error_LED_Update(info->level);
        }
    }
}

/**
  * @brief  获取错误消息字符串
  * @param  code: 错误代码
  * @retval const char*: 错误消息字符串
  */
const char* Error_GetMessage(ErrorCode_t code)
{
    switch (code)
    {
        case ERR_OK:              return "No Error";
        case ERR_UNKNOWN:         return "Unknown Error";
        case ERR_HAL_INIT:        return "HAL Initialization Failed";
        case ERR_CLOCK_CONFIG:    return "Clock Configuration Failed";
        case ERR_GPIO_INIT:       return "GPIO Initialization Failed";
        case ERR_UART_INIT:       return "UART Initialization Failed";
        case ERR_UART_TX:         return "UART Transmission Failed";
        case ERR_UART_RX:         return "UART Reception Failed";
        case ERR_TIMER_INIT:      return "Timer Initialization Failed";
        case ERR_HARD_FAULT:      return "Hard Fault";
        case ERR_MEM_MANAGE:      return "Memory Manage Fault";
        case ERR_BUS_FAULT:       return "Bus Fault";
        case ERR_USAGE_FAULT:     return "Usage Fault";
        case ERR_TIMEOUT:         return "Timeout";
        case ERR_BUSY:            return "Resource Busy";
        case ERR_PARAM:           return "Invalid Parameter";
        case ERR_NO_RESOURCE:     return "No Resource Available";
        case ERR_BUFFER_OVERFLOW: return "Buffer Overflow";
        case ERR_WATCHDOG_RESET:  return "Watchdog Reset";
        default:                  return "Unknown Error Code";
    }
}

/**
  * @brief  获取错误级别
  * @param  code: 错误代码
  * @retval ErrorLevel_t: 错误级别
  */
ErrorLevel_t Error_GetLevel(ErrorCode_t code)
{
    switch (code)
    {
        case ERR_OK:
            return ERR_LEVEL_INFO;

        case ERR_TIMEOUT:
        case ERR_BUSY:
            return ERR_LEVEL_WARNING;

        case ERR_PARAM:
        case ERR_NO_RESOURCE:
        case ERR_BUFFER_OVERFLOW:
            return ERR_LEVEL_ERROR;

        case ERR_HAL_INIT:
        case ERR_CLOCK_CONFIG:
        case ERR_GPIO_INIT:
        case ERR_UART_INIT:
        case ERR_UART_TX:
        case ERR_UART_RX:
        case ERR_TIMER_INIT:
            return ERR_LEVEL_CRITICAL;

        case ERR_HARD_FAULT:
        case ERR_MEM_MANAGE:
        case ERR_BUS_FAULT:
        case ERR_USAGE_FAULT:
        case ERR_WATCHDOG_RESET:
        default:
            return ERR_LEVEL_FATAL;
    }
}

/**
  * @brief  记录错误信息
  * @param  code: 错误代码
  * @param  level: 错误级别
  * @param  message: 错误消息
  * @retval None
  * @note   错误日志通过UART输出，可扩展为保存到Flash
  */
void Error_Log(ErrorCode_t code, ErrorLevel_t level, const char *message)
{
    /* 更新错误统计 */
    error_count++;
    last_error_code = code;

    /* 通过UART输出错误日志 */
    char log_buffer[128];
    int len = snprintf(log_buffer, sizeof(log_buffer),
                       "[LOG] Level=%d Code=0x%X: %s\r\n", level, code, message);
    if (len > 0 && len < sizeof(log_buffer))
    {
        Error_UART_Output(log_buffer);
    }

    /* TODO: 将日志保存到非易失性存储器（Flash/EEPROM） */
    /* 实现方法：分配一个Flash扇区用于循环存储日志 */
}

/**
  * @brief  清除错误状态
  * @retval None
  * @note   仅清除非致命错误
  */
void Error_Clear(void)
{
    ErrorLevel_t level = Error_GetLevel(last_error_code);

    if (level < ERR_LEVEL_CRITICAL)
    {
        last_error_code = ERR_OK;
    }
}

/**
  * @brief  错误恢复
  * @param  code: 错误代码
  * @retval None
  */
void Error_Recover(ErrorCode_t code)
{
    if (Error_CanRecover(code))
    {
        last_error_code = ERR_OK;

        /* 重新初始化必要的外设 */
        /* TODO: 根据具体错误类型进行恢复 */
    }
}

/**
  * @brief  检查错误是否可恢复
  * @param  code: 错误代码
  * @retval bool: true=可恢复, false=不可恢复
  */
bool Error_CanRecover(ErrorCode_t code)
{
    ErrorLevel_t level = Error_GetLevel(code);

    /* 只有非致命错误可以恢复 */
    return (level < ERR_LEVEL_CRITICAL);
}

/**
  * @brief  获取错误计数
  * @retval uint32_t: 错误总数
  */
uint32_t Error_GetCount(void)
{
    return error_count;
}

/**
  * @brief  重置错误计数
  * @retval None
  */
void Error_ResetCount(void)
{
    error_count = 0;
    last_error_code = ERR_OK;
}

/* ========== Private Function Definitions ========== */

/**
  * @brief  更新错误LED指示
  * @param  level: 错误级别
  * @retval None
  */
static void Error_LED_Update(ErrorLevel_t level)
{
    uint32_t delay;

    switch (level)
    {
        case ERR_LEVEL_FATAL:
            delay = ERROR_BLINK_FAST;    /* 快速闪烁 */
            break;
        case ERR_LEVEL_CRITICAL:
            delay = ERROR_BLINK_FAST;
            break;
        case ERR_LEVEL_ERROR:
            delay = ERROR_BLINK_SLOW;    /* 慢速闪烁 */
            break;
        case ERR_LEVEL_WARNING:
            delay = ERROR_BLINK_SLOW;
            break;
        default:
            delay = ERROR_BLINK_SLOW;
            break;
    }

    HAL_GPIO_TogglePin(ERROR_LED_PORT, ERROR_LED_PIN);
    HAL_Delay(delay);
}

/**
  * @brief  系统复位
  * @retval None
  */
static void Error_System_Reset(void)
{
    /* 使用NVIC触发系统复位 */
    HAL_NVIC_SystemReset();
}

/* ========== Watchdog Functions (可选) ========== */

#if defined(USE_WATCHDOG) && (USE_WATCHDOG == 1)

/* 独立看门狗句柄 */
static IWDG_HandleTypeDef hiwdg;

/**
  * @brief  初始化看门狗
  * @retval None
  * @note   使用独立看门狗（IWDG），超时时间约4秒（LSI=32kHz）
  */
void Watchdog_Init(void)
{
    hiwdg.Instance = IWDG;
    hiwdg.Init.Prescaler = IWDG_PRESCALER_32;   /* LSI/32 = 1kHz */
    hiwdg.Init.Reload = 4095;                     /* 4095/1kHz ≈ 4秒 */
    hiwdg.Init.Window = 4095;                     /* 窗口模式不使用 */

    if (HAL_IWDG_Init(&hiwdg) != HAL_OK)
    {
        /* 看门狗初始化失败 */
        Error_Handler_WithCode(ERR_WATCHDOG_INIT);
    }
}

/**
  * @brief  刷新看门狗（喂狗）
  * @retval None
  */
void Watchdog_Refresh(void)
{
    HAL_IWDG_Refresh(&hiwdg);
}

/**
  * @brief  看门狗中断回调
  * @retval None
  */
void Watchdog_Handler(void)
{
    /* 看门狗即将超时时的处理 */
    Error_Handler_WithCode(ERR_WATCHDOG_RESET);
}

#endif /* USE_WATCHDOG */

/* ========== Exception Handlers ========== */

/**
  * @brief  非屏蔽中断处理函数
  */
void NMI_Handler(void)
{
    Error_Handler_WithCode(ERR_UNKNOWN);
}

/**
  * @brief  硬件错误处理函数
  */
void HardFault_Handler(void)
{
    Error_Handler_WithCode(ERR_HARD_FAULT);
}

/**
  * @brief  内存管理错误处理函数
  */
void MemManage_Handler(void)
{
    Error_Handler_WithCode(ERR_MEM_MANAGE);
}

/**
  * @brief  总线错误处理函数
  */
void BusFault_Handler(void)
{
    Error_Handler_WithCode(ERR_BUS_FAULT);
}

/**
  * @brief  使用错误处理函数
  */
void UsageFault_Handler(void)
{
    Error_Handler_WithCode(ERR_USAGE_FAULT);
}

/* ========== Private Function Implementations ========== */

/**
  * @brief  通过UART输出错误信息
  * @param  message: 要输出的消息
  * @retval None
  * @note   如果UART未定义或未初始化，函数将静默返回
  */
static void Error_UART_Output(const char *message)
{
#ifdef USE_ERROR_UART
    /* 检查UART是否已初始化（通过检查huart1实例） */
    extern UART_HandleTypeDef huart1;

    /* 简单检查：如果huart1.Instance非NULL，认为已初始化 */
    if (huart1.Instance != NULL)
    {
        /* 阻塞发送错误信息 */
        HAL_UART_Transmit(&huart1, (uint8_t *)message, strlen(message), HAL_MAX_DELAY);
    }
#endif
    /* 如果UART未定义或未初始化，静默返回 - 不影响系统运行 */
}
