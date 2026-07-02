/**
  ******************************************************************************
  * @file    : uart.c
  * @brief   : UART驱动实现 - 遵循HAL库规范
  * @author  : 项目开发者
  * @date    : 2026-06-11
  ******************************************************************************
  * @attention
  *
  * 本驱动基于STM32 HAL库实现，提供简化的UART接口
  *
  ******************************************************************************
  */

/* ========== Includes ========== */
#include "uart.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

/* ========== Private Macros ========== */
/* 确保printf支持 */
#define ENABLE_UART_PRINTF

/* ========== Private Function Prototypes ========== */
static void UART_GPIO_Init(USART_TypeDef *instance);
static void UART_CLK_Enable(USART_TypeDef *instance);

/* ========== Public Function Definitions ========== */

/**
  * @brief  初始化UART
  * @param  huart: UART句柄指针
  * @param  instance: UART外设实例（USART1, USART2, etc.）
  * @param  config: UART配置指针
  * @retval UART_State_t: 初始化状态
  */
UART_State_t UART_Init(UART_HandleTypeDef *huart, USART_TypeDef *instance, const UART_Config_t *config)
{
    if (huart == NULL || config == NULL)
    {
        return UART_STATE_ERROR;
    }

    /* 保存配置 */
    huart->config = *config;
    huart->handle.Instance = instance;
    huart->is_ready = false;
    huart->rx_count = 0;
    huart->tx_count = 0;

    /* 使能时钟 */
    UART_CLK_Enable(instance);

    /* 初始化GPIO */
    UART_GPIO_Init(instance);

    /* 配置UART参数 */
    huart->handle.Init.BaudRate = config->baud_rate;
    huart->handle.Init.WordLength = config->word_length;
    huart->handle.Init.StopBits = config->stop_bits;
    huart->handle.Init.Parity = config->parity;
    huart->handle.Init.Mode = config->mode;
    huart->handle.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart->handle.Init.OverSampling = UART_OVERSAMPLING_16;

    /* 初始化UART */
    if (HAL_UART_Init(&huart->handle) != HAL_OK)
    {
        return UART_STATE_ERROR;
    }

    huart->is_ready = true;
    return UART_STATE_OK;
}

/**
  * @brief  反初始化UART
  * @param  huart: UART句柄指针
  * @retval None
  */
void UART_DeInit(UART_HandleTypeDef *huart)
{
    if (huart != NULL)
    {
        HAL_UART_DeInit(&huart->handle);
        huart->is_ready = false;
    }
}

/**
  * @brief  阻塞发送数据
  * @param  huart: UART句柄指针
  * @param  data: 发送数据缓冲区
  * @param  length: 数据长度
  * @param  timeout: 超时时间（毫秒）
  * @retval UART_State_t: 发送状态
  */
UART_State_t UART_Transmit(UART_HandleTypeDef *huart, const uint8_t *data, uint16_t length, uint32_t timeout)
{
    if (huart == NULL || data == NULL || !huart->is_ready)
    {
        return UART_STATE_NOT_READY;
    }

    HAL_StatusTypeDef status = HAL_UART_Transmit(&huart->handle, (uint8_t*)data, length, timeout);

    switch (status)
    {
        case HAL_OK:
            huart->tx_count += length;
            return UART_STATE_OK;
        case HAL_ERROR:
            return UART_STATE_ERROR;
        case HAL_BUSY:
            return UART_STATE_BUSY;
        case HAL_TIMEOUT:
            return UART_STATE_TIMEOUT;
        default:
            return UART_STATE_ERROR;
    }
}

/**
  * @brief  阻塞接收数据
  * @param  huart: UART句柄指针
  * @param  data: 接收数据缓冲区
  * @param  length: 数据长度
  * @param  timeout: 超时时间（毫秒）
  * @retval UART_State_t: 接收状态
  */
UART_State_t UART_Receive(UART_HandleTypeDef *huart, uint8_t *data, uint16_t length, uint32_t timeout)
{
    if (huart == NULL || data == NULL || !huart->is_ready)
    {
        return UART_STATE_NOT_READY;
    }

    HAL_StatusTypeDef status = HAL_UART_Receive(&huart->handle, data, length, timeout);

    switch (status)
    {
        case HAL_OK:
            huart->rx_count += length;
            return UART_STATE_OK;
        case HAL_ERROR:
            return UART_STATE_ERROR;
        case HAL_BUSY:
            return UART_STATE_BUSY;
        case HAL_TIMEOUT:
            return UART_STATE_TIMEOUT;
        default:
            return UART_STATE_ERROR;
    }
}

/**
  * @brief  发送单个字符
  * @param  huart: UART句柄指针
  * @param  ch: 要发送的字符
  * @param  timeout: 超时时间（毫秒）
  * @retval UART_State_t: 发送状态
  */
UART_State_t UART_SendChar(UART_HandleTypeDef *huart, uint8_t ch, uint32_t timeout)
{
    return UART_Transmit(huart, &ch, 1, timeout);
}

/**
  * @brief  发送字符串
  * @param  huart: UART句柄指针
  * @param  str: 要发送的字符串（以'\0'结尾）
  * @param  timeout: 超时时间（毫秒）
  * @retval UART_State_t: 发送状态
  */
UART_State_t UART_SendString(UART_HandleTypeDef *huart, const char *str, uint32_t timeout)
{
    if (str == NULL)
    {
        return UART_STATE_ERROR;
    }

    uint16_t length = (uint16_t)strlen(str);
    return UART_Transmit(huart, (const uint8_t*)str, length, timeout);
}

/**
  * @brief  发送缓冲区数据
  * @param  huart: UART句柄指针
  * @param  buffer: 发送数据缓冲区
  * @param  length: 数据长度
  * @param  timeout: 超时时间（毫秒）
  * @retval UART_State_t: 发送状态
  */
UART_State_t UART_SendBuffer(UART_HandleTypeDef *huart, const uint8_t *buffer, uint16_t length, uint32_t timeout)
{
    return UART_Transmit(huart, buffer, length, timeout);
}

/**
  * @brief  接收单个字符
  * @param  huart: UART句柄指针
  * @param  timeout: 超时时间（毫秒）
  * @retval int: 接收到的字符（>=0）或错误码（<0）
  */
int UART_GetChar(UART_HandleTypeDef *huart, uint32_t timeout)
{
    uint8_t ch;

    if (huart == NULL || !huart->is_ready)
    {
        return -1;
    }

    UART_State_t status = UART_Receive(huart, &ch, 1, timeout);

    if (status == UART_STATE_OK)
    {
        return (int)ch;
    }

    return -1;
}

/**
  * @brief  检查UART是否就绪
  * @param  huart: UART句柄指针
  * @retval bool: true=就绪, false=未就绪
  */
bool UART_IsReady(UART_HandleTypeDef *huart)
{
    return (huart != NULL && huart->is_ready);
}

/**
  * @brief  检查UART是否忙
  * @param  huart: UART句柄指针
  * @retval bool: true=忙, false=空闲
  */
bool UART_IsBusy(UART_HandleTypeDef *huart)
{
    if (huart == NULL)
    {
        return false;
    }

    return (huart->handle.gState != HAL_UART_STATE_READY);
}

/**
  * @brief  清除UART错误
  * @param  huart: UART句柄指针
  * @retval None
  */
void UART_ClearError(UART_HandleTypeDef *huart)
{
    if (huart != NULL)
    {
        __HAL_UART_CLEAR_FLAG(&huart->handle, UART_CLEAR_OREF | UART_CLEAR_NEF | UART_CLEAR_FEF);
    }
}

#ifdef ENABLE_UART_PRINTF

/**
  * @brief  UART格式化打印（类似printf）
  * @param  huart: UART句柄指针
  * @param  format: 格式化字符串
  * @param  ...: 可变参数
  * @retval int: 发送的字符数
  */
int UART_Printf(UART_HandleTypeDef *huart, const char *format, ...)
{
    if (huart == NULL || !huart->is_ready)
    {
        return -1;
    }

    static char buffer[256];
    va_list args;
    int len;

    va_start(args, format);
    len = vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);

    if (len > 0 && len < sizeof(buffer))
    {
        UART_Transmit(huart, (const uint8_t*)buffer, (uint16_t)len, UART_DEFAULT_TIMEOUT);
    }

    return len;
}

#endif /* ENABLE_UART_PRINTF */

/* ========== Private Function Definitions ========== */

/**
  * @brief  根据UART实例使能相应时钟
  * @param  instance: UART外设实例
  * @retval None
  */
static void UART_CLK_Enable(USART_TypeDef *instance)
{
#ifdef USART1
    if (instance == USART1)
    {
        __HAL_RCC_USART1_CLK_ENABLE();
        return;
    }
#endif

#ifdef USART2
    if (instance == USART2)
    {
        __HAL_RCC_USART2_CLK_ENABLE();
        return;
    }
#endif

#ifdef USART3
    if (instance == USART3)
    {
        __HAL_RCC_USART3_CLK_ENABLE();
        return;
    }
#endif

#ifdef UART4
    if (instance == UART4)
    {
        __HAL_RCC_UART4_CLK_ENABLE();
        return;
    }
#endif

#ifdef UART5
    if (instance == UART5)
    {
        __HAL_RCC_UART5_CLK_ENABLE();
        return;
    }
#endif
}

/**
  * @brief  根据UART实例初始化相应GPIO
  * @note   需要根据具体硬件配置修改
  * @param  instance: UART外设实例
  * @retval None
  */
static void UART_GPIO_Init(USART_TypeDef *instance)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    /* TODO: 根据实际硬件配置GPIO引脚
     *
     * USART1默认配置示例：
     * TX: PA9 (AF7)
     * RX: PA10 (AF7)
     *
     * USART2默认配置示例：
     * TX: PA2 (AF7)
     * RX: PA3 (AF7)
     */

#ifdef USART1
    if (instance == USART1)
    {
        /* 使能GPIOA时钟 */
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /* 配置TX引脚（PA9） */
        GPIO_InitStruct.Pin = GPIO_PIN_9;
        GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Pull = GPIO_PULLUP;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
        GPIO_InitStruct.Alternate = GPIO_AF7_USART1;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

        /* 配置RX引脚（PA10） */
        GPIO_InitStruct.Pin = GPIO_PIN_10;
        GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Pull = GPIO_PULLUP;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
        GPIO_InitStruct.Alternate = GPIO_AF7_USART1;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

        return;
    }
#endif

#ifdef USART2
    if (instance == USART2)
    {
        /* 使能GPIOA时钟 */
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /* 配置TX引脚（PA2） */
        GPIO_InitStruct.Pin = GPIO_PIN_2;
        GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Pull = GPIO_PULLUP;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
        GPIO_InitStruct.Alternate = GPIO_AF7_USART2;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

        /* 配置RX引脚（PA3） */
        GPIO_InitStruct.Pin = GPIO_PIN_3;
        GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Pull = GPIO_PULLUP;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
        GPIO_InitStruct.Alternate = GPIO_AF7_USART2;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

        return;
    }
#endif

    /* 其他UART实例的GPIO配置... */
}

/* ========== Interrupt and Callback Handlers ========== */

/**
  * @brief  UART接收完成回调函数
  * @param  huart: HAL UART句柄
  * @retval None
  */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    /* 用户可在此添加接收完成处理代码 */
}

/**
  * @brief  UART发送完成回调函数
  * @param  huart: HAL UART句柄
  * @retval None
  */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    /* 用户可在此添加发送完成处理代码 */
}
