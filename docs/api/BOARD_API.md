# 板级支持包 (BSP) API 参考 (v2.0)

本文档描述了 M144Z-M4 开发板 (STM32F407ZGTx) 的硬件抽象层 API。

---

## 📑 目录

1. [概述](#概述)
2. [开发板信息](#开发板信息)
3. [LED](#led)
4. [按键](#按键)
5. [可用 GPIO](#可用-gpio)
6. [调试接口](#调试接口)
7. [串口](#串口)
8. [完整示例](#完整示例)

---

## 概述

`board.h` 定义了 M144Z-M4 开发板的固定硬件配置，包括：

- LED 引脚定义
- 按键引脚定义
- 可用 GPIO 列表
- 调试接口定义
- 串口引脚定义

**注意**: `board.h` 中的定义是开发板固定的，通常不需要修改。

项目特定配置应放在 `config.h` 中。

---

## 开发板信息

### 硬件规格

```c
#define BOARD_NAME           "M144Z-M4"
#define BOARD_MCU            "STM32F407ZGTx"
#define BOARD_SYSCLK_FREQ    168000000UL  // 168MHz
#define BOARD_FLASH_SIZE      1024         // 1MB
#define BOARD_RAM_SIZE        192          // 192KB
```

### MCU 特性

- **内核**: ARM Cortex-M4F
- **主频**: 168MHz
- **Flash**: 1MB
- **SRAM**: 192KB (128KB 主SRAM + 64KB CCM)
- **封装**: LQFP144
- **外设**: 丰富的定时器、通信接口、ADC等

---

## LED

### 引脚定义

| LED | 端口 | 引脚 | 描述 | 极性 |
|-----|------|------|------|------|
| LED0 | GPIOF | PF9 | 左转向灯 | 共阳极（低点亮） |
| LED1 | GPIOF | PF10 | 右转向灯 | 共阳极（低点亮） |

```c
#define BOARD_LED0_PORT  GPIOF
#define BOARD_LED0_PIN   GPIO_PIN_9

#define BOARD_LED1_PORT  GPIOF
#define BOARD_LED1_PIN   GPIO_PIN_10
```

---

### 控制宏

LED 为共阳极类型，**低电平点亮**：

```c
// 点亮 LED（低电平）
BOARD_LED_ON(BOARD_LED0);

// 熄灭 LED（高电平）
BOARD_LED_OFF(BOARD_LED1);

// 切换 LED 状态
BOARD_LED_TOGGLE(BOARD_LED0);

// 检查 LED 状态（0=亮，1=灭）
BOARD_LED_IS_ON(BOARD_LED0);
```

---

### 使用示例

```c
#include "stm32f4xx_hal.h"
#include "board.h"

void LED_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    // 使能 GPIOF 时钟
    __HAL_RCC_GPIOF_CLK_ENABLE();

    // 配置 LED 引脚
    GPIO_InitStruct.Pin = BOARD_LED0_PIN | BOARD_LED1_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;

    if (HAL_GPIO_Init(BOARD_LED0_PORT, &GPIO_InitStruct) != HAL_OK)
    {
        Error_Handler();
    }

    // 初始状态：熄灭（高电平）
    BOARD_LED_OFF(BOARD_LED0);
    BOARD_LED_OFF(BOARD_LED1);
}

void LED_Blink(uint32_t delay_ms)
{
    BOARD_LED_TOGGLE(BOARD_LED0);
    HAL_Delay(delay_ms);
}
```

---

### LED 闪烁模式示例

```c
void LED_Pattern_Single(void)
{
    // 单闪模式
    BOARD_LED_ON(BOARD_LED0);
    HAL_Delay(500);
    BOARD_LED_OFF(BOARD_LED0);
    HAL_Delay(500);
}

void LED_Pattern_Double(void)
{
    // 双闪模式
    BOARD_LED_ON(BOARD_LED0);
    HAL_Delay(250);
    BOARD_LED_OFF(BOARD_LED0);
    HAL_Delay(250);
    BOARD_LED_ON(BOARD_LED0);
    HAL_Delay(250);
    BOARD_LED_OFF(BOARD_LED0);
    HAL_Delay(500);
}
```

---

## 按键

### 引脚定义

| 按键 | 端口 | 引脚 | 描述 | 默认触发方式 |
|------|------|------|------|-------------|
| KEY0 | GPIOE | PE4 | 模式切换 / BOOT0 | 低电平 |
| KEY_UP | GPIOA | PA0 | 双闪开关 / WKUP | 高电平 |

```c
#define BOARD_KEY0_PORT  GPIOE
#define BOARD_KEY0_PIN   GPIO_PIN_4

#define BOARD_KEY_UP_PORT  GPIOA
#define BOARD_KEY_UP_PIN  GPIO_PIN_0
```

---

### 触发方式配置

触发方式由项目配置文件 `config.h` 决定：

```c
// 在 config.h 中定义
#define KEY0_TRIGGER_HIGH   0   // 1=高电平触发, 0=低电平触发
#define KEY_UP_TRIGGER_HIGH  1   // 1=高电平触发, 0=低电平触发

// 上拉/下拉选择宏
#define KEY_PULL(__LEVEL__)  ((__LEVEL__) ? GPIO_PULLDOWN : GPIO_PULLUP)
```

**根据电路决定触发方式**:
- 按键一端接GPIO，另一端接VCC → 高电平触发（需下拉电阻）
- 按键一端接GPIO，另一端接GND → 低电平触发（需上拉电阻）

---

### 使用示例

```c
#include "stm32f4xx_hal.h"
#include "board.h"
#include "config.h"

void KEY_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    // 使能时钟
    __HAL_RCC_GPIOE_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    // 配置 KEY0（PE4）
    GPIO_InitStruct.Pin = BOARD_KEY0_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = KEY_PULL(KEY0_TRIGGER_HIGH);
    HAL_GPIO_Init(BOARD_KEY0_PORT, &GPIO_InitStruct);

    // 配置 KEY_UP（PA0）
    GPIO_InitStruct.Pin = BOARD_KEY_UP_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = KEY_PULL(KEY_UP_TRIGGER_HIGH);
    HAL_GPIO_Init(BOARD_KEY_UP_PORT, &GPIO_InitStruct);
}

// 读取按键状态
uint8_t KEY0_IsPressed(void)
{
    GPIO_PinState state = HAL_GPIO_ReadPin(BOARD_KEY0_PORT, BOARD_KEY0_PIN);
    return KEY0_TRIGGER_HIGH ? (state == GPIO_PIN_SET) : (state == GPIO_PIN_RESET);
}

uint8_t KEY_UP_IsPressed(void)
{
    GPIO_PinState state = HAL_GPIO_ReadPin(BOARD_KEY_UP_PORT, BOARD_KEY_UP_PIN);
    return KEY_UP_TRIGGER_HIGH ? (state == GPIO_PIN_SET) : (state == GPIO_PIN_RESET);
}
```

---

### 按键消抖示例

```c
#include "timer.h"  // 使用 DWT 延时

// 简单消抖（阻塞式）
uint8_t KEY_Scan(void)
{
    static uint8_t key0_pressed = 0;
    uint8_t key0_now = KEY0_IsPressed();

    // 检测上升沿（按下）
    if (key0_now && !key0_pressed)
    {
        delay_ms(KEY_DEBOUNCE_DELAY);  // 消抖延时
        if (KEY0_IsPressed())
        {
            key0_pressed = 1;
            return 1;  // 按键按下
        }
    }

    // 检测下降沿（释放）
    if (!key0_now && key0_pressed)
    {
        key0_pressed = 0;
    }

    return 0;
}
```

---

## 可用 GPIO

以下引脚可用作通用 GPIO 输入/输出（已被系统功能占用的除外）：

### Port A 可用引脚

```c
BOARD_GPIO_PA1   // PA1
BOARD_GPIO_PA2   // PA2 (USART2_TX)
BOARD_GPIO_PA3   // PA3 (USART2_RX)
BOARD_GPIO_PA5   // PA5
BOARD_GPIO_PA7   // PA7
BOARD_GPIO_PA15  // PA15
```

### Port B 可用引脚

```c
BOARD_GPIO_PB10  // PB10
BOARD_GPIO_PB11  // PB11
BOARD_GPIO_PB12  // PB12
BOARD_GPIO_PB13  // PB13
```

### Port C 可用引脚

```c
BOARD_GPIO_PC0   // PC0
BOARD_GPIO_PC1   // PC1
BOARD_GPIO_PC2   // PC2
BOARD_GPIO_PC3   // PC3
BOARD_GPIO_PC4   // PC4
BOARD_GPIO_PC5   // PC5
```

### Port D 可用引脚

```c
BOARD_GPIO_PD3   // PD3
```

### Port E 可用引脚

```c
BOARD_GPIO_PE2   // PE2
BOARD_GPIO_PE3   // PE3
```

### Port F 可用引脚

```c
BOARD_GPIO_PF6   // PF6
BOARD_GPIO_PF7   // PF7
BOARD_GPIO_PF8   // PF8
// PF9, PF10 = LED
```

### Port G 可用引脚

```c
BOARD_GPIO_PG6   // PG6
BOARD_GPIO_PG7   // PG7
BOARD_GPIO_PG8   // PG8
BOARD_GPIO_PG11  // PG11
BOARD_GPIO_PG13  // PG13
BOARD_GPIO_PG14  // PG14
BOARD_GPIO_PG15  // PG15
```

---

### 使用示例

```c
#define BOARD_SENSOR_PORT  GPIOB
#define BOARD_SENSOR_PIN   BOARD_GPIO_PB10

void SENSOR_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitStruct.Pin = BOARD_SENSOR_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(BOARD_SENSOR_PORT, &GPIO_InitStruct);
}

uint8_t SENSOR_Read(void)
{
    return HAL_GPIO_ReadPin(BOARD_SENSOR_PORT, BOARD_SENSOR_PIN) == GPIO_PIN_SET;
}
```

---

## 调试接口

### SWD 调试引脚

```c
#define BOARD_SWDIO_PORT  GPIOA
#define BOARD_SWDIO_PIN   GPIO_PIN_13  // PA13 - SWDIO

#define BOARD_SWCLK_PORT  GPIOA
#define BOARD_SWCLK_PIN   GPIO_PIN_14  // PA14 - SWCLK
```

**注意**: 这些引脚用于 SWD 调试，通常不应作他用，否则会失去调试功能。

---

## 串口

### USB 转串口（CH340C）

板载 CH340C USB 转串口芯片，需跳线帽连接：

```c
#define BOARD_USART1_TX_PORT  GPIOA
#define BOARD_USART1_TX_PIN   GPIO_PIN_9   // PA9

#define BOARD_USART1_RX_PORT  GPIOA
#define BOARD_USART1_RX_PIN   GPIO_PIN_10  // PA10
```

**使用说明**:
1. 确保跳线帽连接正确
2. 安装 CH340 驱动程序
3. 使用串口调试助手（波特率默认115200）

---

### UART 使用示例

```c
#include "stm32f4xx_hal.h"
#include "uart.h"
#include "board.h"

UART_HandleTypeDef uart_handle;
static const UART_Config_t uart_config = UART_DEFAULT_CONFIG_INIT;

void UART_Init_Debug(void)
{
    // 初始化 UART
    if (UART_Init(&uart_handle, USART1, &uart_config) != UART_STATE_OK)
    {
        Error_Handler();
    }

    UART_SendString(&uart_handle, "\r\n=== System Started ===\r\n", 1000);
}

void main(void)
{
    HAL_Init();
    UART_Init_Debug();

    UART_Printf(&uart_handle, "System Clock: %lu Hz\r\n", SystemCoreClock);
    UART_Printf(&uart_handle, "Board: %s\r\n", BOARD_NAME);

    while (1)
    {
        // 主循环
        HAL_Delay(1000);
    }
}
```

---

## 硬件连接图

### LED 连接

```
        VCC (3.3V)
          |
         LED (共阳极)
          |
        220Ω 电阻
          |
        PF9/PF10
          |
        MCU GPIO
```

### 按键连接

```
        VCC/GND
          |
        按键
          |
        PE4/PA0
          |
        MCU GPIO
```

---

## 完整示例

```c
/**
  ******************************************************************************
  * @file    : example_board_usage.c
  * @brief   : 板级API使用示例
  ******************************************************************************
  */

#include <stdint.h>
#include "stm32f4xx_hal.h"
#include "board.h"
#include "config.h"
#include "error_handler.h"
#include "uart.h"

/* ========== 私有变量 ========== */
static UART_HandleTypeDef uart_handle;
static const UART_Config_t uart_config = UART_DEFAULT_CONFIG_INIT;

/* ========== 函数声明 ========== */
void SystemClock_Config(void);
void GPIO_Init(void);
void KEY_Init(void);

/* ========== 主函数 ========== */
int main(void)
{
    /* HAL 初始化 */
    if (HAL_Init() != HAL_OK)
    {
        ERROR_HANDLER(ERR_HAL_INIT);
    }

    /* 系统时钟配置 */
    SystemClock_Config();

    /* GPIO 初始化 */
    GPIO_Init();
    KEY_Init();

    /* UART 初始化 */
    if (UART_Init(&uart_handle, USART1, &uart_config) != UART_STATE_OK)
    {
        ERROR_HANDLER(ERR_UART_INIT);
    }

    UART_SendString(&uart_handle, "\r\n=== M144Z-M4 Board Test ===\r\n", 1000);
    UART_Printf(&uart_handle, "MCU: %s\r\n", BOARD_MCU);
    UART_Printf(&uart_handle, "SysClk: %lu Hz\r\n", SystemCoreClock);

    /* 主循环 */
    uint32_t counter = 0;
    while (1)
    {
        /* 检测按键 */
        if (KEY0_IsPressed())
        {
            BOARD_LED_ON(BOARD_LED0);
            UART_Printf(&uart_handle, "KEY0 Pressed! Count: %lu\r\n", counter++);
        }
        else
        {
            BOARD_LED_OFF(BOARD_LED0);
        }

        HAL_Delay(MAIN_LOOP_DELAY);
    }

    return 0;
}

/* ========== GPIO 初始化 ========== */
void GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    /* 使能 GPIOF 时钟 */
    __HAL_RCC_GPIOF_CLK_ENABLE();

    /* 配置 LED 引脚 */
    GPIO_InitStruct.Pin = BOARD_LED0_PIN | BOARD_LED1_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;

    if (HAL_GPIO_Init(BOARD_LED0_PORT, &GPIO_InitStruct) != HAL_OK)
    {
        ERROR_HANDLER(ERR_GPIO_INIT);
    }

    /* 初始状态：熄灭 */
    BOARD_LED_OFF(BOARD_LED0);
    BOARD_LED_OFF(BOARD_LED1);
}

/* ========== 按键初始化 ========== */
void KEY_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    /* 使能时钟 */
    __HAL_RCC_GPIOE_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    /* 配置 KEY0 */
    GPIO_InitStruct.Pin = BOARD_KEY0_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = KEY_PULL(KEY0_TRIGGER_HIGH);
    HAL_GPIO_Init(BOARD_KEY0_PORT, &GPIO_InitStruct);

    /* 配置 KEY_UP */
    GPIO_InitStruct.Pin = BOARD_KEY_UP_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = KEY_PULL(KEY_UP_TRIGGER_HIGH);
    HAL_GPIO_Init(BOARD_KEY_UP_PORT, &GPIO_InitStruct);
}

/* ========== 系统时钟配置 ========== */
void SystemClock_Config(void)
{
    /* 使用默认 HSI 时钟（16MHz） */
    /* TODO: 配置 PLL 以获得 168MHz 全速 */
}

/* ========== 错误处理 ========== */
void Error_Handler(void)
{
    UART_SendString(&uart_handle, "\r\n!!! ERROR !!!\r\n", 1000);

    while (1)
    {
        BOARD_LED_TOGGLE(BOARD_LED0);
        HAL_Delay(100);
    }
}
```

---

## 注意事项

1. **时钟配置**: 使用任何 GPIO 外设前必须先使能相应时钟
2. **LED 极性**: 本板 LED 为共阳极，低电平点亮
3. **调试引脚**: PA13/PA14 用于 SWD 调试，不应作他用
4. **按键触发**: 根据外部电路决定触发方式（高/低电平）
5. **串口跳线**: 使用板载串口需要连接跳线帽

---

## 相关文档

- [HAL API 参考](HAL_API.md)
- [代码风格指南](../guides/CODING_STYLE.md)
- [快速入门指南](../guides/GETTING_STARTED.md)

---

**如有问题，请参考项目文档或联系课程教师。**
