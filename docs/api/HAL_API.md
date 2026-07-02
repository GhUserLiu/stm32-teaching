# HAL 库 API 参考 (v2.0)

本文档描述了 STM32F407 自定义 HAL 库的 API 接口，包括核心 HAL 功能和外设驱动。

---

## 📑 目录

1. [HAL 核心](#hal-核心)
2. [GPIO](#gpio)
3. [UART 驱动](#uart-驱动)
4. [Timer 驱动](#timer-驱动)
5. [错误处理](#错误处理)
6. [数据类型](#数据类型)
7. [使用示例](#使用示例)

---

## HAL 核心

### 初始化和去初始化

#### `HAL_Init`

```c
HAL_StatusTypeDef HAL_Init(void);
```

**描述**: 初始化 HAL 库，配置 SysTick 定时器（1ms时基）

**返回值**:
| 值 | 描述 |
|-----|------|
| `HAL_OK` | 初始化成功 |
| `HAL_ERROR` | 初始化失败 |
| `HAL_BUSY` | HAL 库忙 |
| `HAL_TIMEOUT` | 操作超时 |

**示例**:
```c
if (HAL_Init() != HAL_OK)
{
    Error_Handler();
}
```

---

#### `HAL_DeInit`

```c
HAL_StatusTypeDef HAL_DeInit(void);
```

**描述**: 去初始化 HAL 库，恢复默认状态

**返回值**: 同上

---

### 时间管理

#### `HAL_GetTick`

```c
uint32_t HAL_GetTick(void);
```

**描述**: 获取系统启动后的毫秒数

**返回值**: 当前系统时间（毫秒），`uint32_t` 类型（约49.7天溢出）

**注意**: 此函数在中断和主循环中都可安全调用

**示例**:
```c
uint32_t start_time = HAL_GetTick();
// 执行某些操作
uint32_t elapsed = HAL_GetTick() - start_time;
```

---

#### `HAL_Delay`

```c
void HAL_Delay(__IO uint32_t Delay);
```

**描述**: 阻塞延时指定的毫秒数

**参数**:
| 参数 | 描述 |
|------|------|
| `Delay` | 延时时间（毫秒） |

**注意**: 此函数使用 `HAL_GetTick()` 实现，在延时期间会进入等待状态

**示例**:
```c
HAL_Delay(500);  // 延时500ms
```

---

#### `HAL_IncTick`

```c
void HAL_IncTick(void);
```

**描述**: SysTick 中断调用，增加系统时间计数

**注意**: 通常不需要用户调用，由 HAL 库在中断中自动调用

---

## GPIO

### 时钟使能宏

```c
__HAL_RCC_GPIOA_CLK_ENABLE();
__HAL_RCC_GPIOB_CLK_ENABLE();
__HAL_RCC_GPIOC_CLK_ENABLE();
__HAL_RCC_GPIOD_CLK_ENABLE();
__HAL_RCC_GPIOE_CLK_ENABLE();
__HAL_RCC_GPIOF_CLK_ENABLE();
__HAL_RCC_GPIOG_CLK_ENABLE();
__HAL_RCC_GPIOH_CLK_ENABLE();
```

**描述**: 使能对应 GPIO 端口的时钟

**注意**: 使用任何 GPIO 外设前必须先使能其时钟

---

### GPIO 初始化

#### `HAL_GPIO_Init`

```c
void HAL_GPIO_Init(GPIO_TypeDef* GPIOx, GPIO_InitTypeDef* GPIO_InitStruct);
```

**描述**: 初始化 GPIO 引脚

**参数**:
| 参数 | 描述 |
|------|------|
| `GPIOx` | GPIO 端口 (GPIOA-GPIOH) |
| `GPIO_InitStruct` | 初始化结构体指针 |

**GPIO_InitTypeDef 结构体**:
```c
typedef struct {
    uint32_t Pin;       // 引脚号 (GPIO_PIN_0 - GPIO_PIN_15)
    uint32_t Mode;      // 模式
    uint32_t Pull;      // 上拉/下拉配置
    uint32_t Speed;     // 输出速度
    uint32_t Alternate; // 复用功能选择
} GPIO_InitTypeDef;
```

**Mode 可选值**:
| 值 | 描述 |
|-----|------|
| `GPIO_MODE_INPUT` | 输入模式 |
| `GPIO_MODE_OUTPUT_PP` | 推挽输出 |
| `GPIO_MODE_OUTPUT_OD` | 开漏输出 |
| `GPIO_MODE_AF_PP` | 推挽复用 |
| `GPIO_MODE_AF_OD` | 开漏复用 |
| `GPIO_MODE_ANALOG` | 模拟模式 |

**Pull 可选值**:
| 值 | 描述 |
|-----|------|
| `GPIO_NOPULL` | 无上下拉 |
| `GPIO_PULLUP` | 上拉 |
| `GPIO_PULLDOWN` | 下拉 |

**Speed 可选值**:
| 值 | 描述 |
|-----|------|
| `GPIO_SPEED_FREQ_LOW` | 低速 (2MHz) |
| `GPIO_SPEED_FREQ_MEDIUM` | 中速 (25MHz) |
| `GPIO_SPEED_FREQ_HIGH` | 高速 (50MHz) |
| `GPIO_SPEED_FREQ_VERY_HIGH` | 极高速 (100MHz) |

**返回值**: 无

**示例**:
```c
GPIO_InitTypeDef GPIO_InitStruct = {0};

// 配置LED引脚（推挽输出）
GPIO_InitStruct.Pin = GPIO_PIN_9;
GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
GPIO_InitStruct.Pull = GPIO_NOPULL;
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
HAL_GPIO_Init(GPIOF, &GPIO_InitStruct);
```

---

### GPIO 读写操作

#### `HAL_GPIO_ReadPin`

```c
GPIO_PinState HAL_GPIO_ReadPin(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);
```

**描述**: 读取 GPIO 引脚状态

**参数**:
| 参数 | 描述 |
|------|------|
| `GPIOx` | GPIO 端口 |
| `GPIO_Pin` | 引脚号 (GPIO_PIN_0 - GPIO_PIN_15) |

**返回值**:
| 值 | 描述 |
|-----|------|
| `GPIO_PIN_RESET` | 低电平 (0) |
| `GPIO_PIN_SET` | 高电平 (1) |

**示例**:
```c
GPIO_PinState state = HAL_GPIO_ReadPin(GPIOE, GPIO_PIN_4);
if (state == GPIO_PIN_RESET)
{
    // 按键被按下（低电平）
}
```

---

#### `HAL_GPIO_WritePin`

```c
void HAL_GPIO_WritePin(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin, GPIO_PinState PinState);
```

**描述**: 设置 GPIO 引脚状态

**参数**:
| 参数 | 描述 |
|------|------|
| `GPIOx` | GPIO 端口 |
| `GPIO_Pin` | 引脚号 |
| `PinState` | `GPIO_PIN_RESET` 或 `GPIO_PIN_SET` |

**返回值**: 无

**示例**:
```c
// 点亮LED（低电平有效）
HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_RESET);

// 熄灭LED（高电平）
HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_SET);
```

---

#### `HAL_GPIO_TogglePin`

```c
void HAL_GPIO_TogglePin(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);
```

**描述**: 切换 GPIO 引脚状态

**参数**:
| 参数 | 描述 |
|------|------|
| `GPIOx` | GPIO 端口 |
| `GPIO_Pin` | 引脚号 |

**返回值**: 无

**示例**:
```c
// LED闪烁
HAL_GPIO_TogglePin(GPIOF, GPIO_PIN_9);
HAL_Delay(500);
```

---

## UART 驱动

UART 驱动提供简化的串口通信接口。详见 [`uart.h`](../../common/drivers/include/uart.h)。

### 数据结构

#### `UART_Config_t`

```c
typedef struct {
    uint32_t baud_rate;    // 波特率
    uint32_t word_length;  // 数据位长度
    uint32_t stop_bits;    // 停止位
    uint32_t parity;       // 校验位
    uint32_t mode;         // 模式（TX/RX/TX_RX）
} UART_Config_t;
```

---

### UART 初始化

#### `UART_Init`

```c
UART_State_t UART_Init(UART_HandleTypeDef *huart,
                       USART_TypeDef *instance,
                       const UART_Config_t *config);
```

**描述**: 初始化 UART 外设

**参数**:
| 参数 | 描述 |
|------|------|
| `huart` | UART句柄指针 |
| `instance` | UART外设实例 (USART1, USART2, etc.) |
| `config` | UART配置指针 |

**返回值**:
| 值 | 描述 |
|-----|------|
| `UART_STATE_OK` | 初始化成功 |
| `UART_STATE_ERROR` | 初始化失败 |
| `UART_STATE_NOT_READY` | 参数无效 |

**示例**:
```c
#include "uart.h"

UART_HandleTypeDef uart_handle;
static const UART_Config_t uart_config = UART_DEFAULT_CONFIG_INIT;

void UART_Init_Debug(void)
{
    if (UART_Init(&uart_handle, USART1, &uart_config) != UART_STATE_OK)
    {
        Error_Handler();
    }
}
```

---

### UART 数据发送

#### `UART_SendString`

```c
UART_State_t UART_SendString(UART_HandleTypeDef *huart,
                             const char *str,
                             uint32_t timeout);
```

**描述**: 发送字符串

**参数**:
| 参数 | 描述 |
|------|------|
| `huart` | UART句柄指针 |
| `str` | 要发送的字符串（以'\0'结尾） |
| `timeout` | 超时时间（毫秒） |

**返回值**: `UART_STATE_OK` 成功，其他值表示失败

**示例**:
```c
UART_SendString(&uart_handle, "Hello, World!\r\n", 1000);
```

---

#### `UART_Printf`

```c
int UART_Printf(UART_HandleTypeDef *huart, const char *format, ...);
```

**描述**: 格式化打印（类似 printf）

**参数**:
| 参数 | 描述 |
|------|------|
| `huart` | UART句柄指针 |
| `format` | 格式化字符串 |
| `...` | 可变参数 |

**返回值**: 发送的字符数

**示例**:
```c
UART_Printf(&uart_handle, "Temperature: %d.%d C\r\n", temp_int, temp_dec);
UART_Printf(&uart_handle, "Counter: %lu\r\n", counter);
```

---

### UART 数据接收

#### `UART_Receive`

```c
UART_State_t UART_Receive(UART_HandleTypeDef *huart,
                          uint8_t *data,
                          uint16_t length,
                          uint32_t timeout);
```

**描述**: 阻塞接收数据

**参数**:
| 参数 | 描述 |
|------|------|
| `huart` | UART句柄指针 |
| `data` | 接收缓冲区 |
| `length` | 接收长度 |
| `timeout` | 超时时间（毫秒） |

**返回值**: `UART_STATE_OK` 成功，其他值表示失败

**示例**:
```c
uint8_t rx_buffer[32];
if (UART_Receive(&uart_handle, rx_buffer, sizeof(rx_buffer), 1000) == UART_STATE_OK)
{
    // 数据接收成功
}
```

---

## Timer 驱动

Timer 驱动提供精准延时功能。详见 [`timer.h`](../../common/drivers/include/timer.h)。

### DWT 精准延时

#### `DWT_Init`

```c
void DWT_Init(void);
```

**描述**: 初始化 DWT 周期计数器（用于精准延时）

**注意**: 仅需初始化一次

**示例**:
```c
#include "timer.h"

int main(void)
{
    HAL_Init();
    DWT_Init();  // 初始化DWT

    while (1)
    {
        HAL_GPIO_TogglePin(GPIOF, GPIO_PIN_9);
        delay_us(500);  // 微秒级延时
    }
}
```

---

#### `DWT_Delay_us`

```c
void DWT_Delay_us(uint32_t us);
```

**描述**: DWT 微秒级精准延时

**参数**:
| 参数 | 描述 |
|------|------|
| `us` | 延时时间（微秒） |

**精度**: ±1微秒

**示例**:
```c
// 500微秒延时
DWT_Delay_us(500);
```

---

#### `delay_us` / `delay_ms`

```c
void delay_us(uint32_t us);
void delay_ms(uint32_t ms);
```

**描述**: 便捷延时宏（基于 DWT 和 HAL_Delay）

**示例**:
```c
delay_us(100);  // 延时100微秒
delay_ms(500);  // 延时500毫秒
```

---

## 错误处理

错误处理框架提供统一的错误管理机制。详见 [`error_handler.h`](../../common/core/error_handler.h)。

### 错误代码

```c
typedef enum {
    ERR_OK = 0,                  // 无错误
    ERR_UNKNOWN,                 // 未知错误
    ERR_HAL_INIT,               // HAL初始化失败
    ERR_CLOCK_CONFIG,            // 时钟配置失败
    ERR_GPIO_INIT,               // GPIO初始化失败
    ERR_UART_INIT,               // UART初始化失败
    ERR_UART_TX,                 // UART发送失败
    ERR_UART_RX,                 // UART接收失败
    ERR_TIMER_INIT,              // 定时器初始化失败
    ERR_HARD_FAULT,              // 硬件错误
    ERR_TIMEOUT,                 // 超时错误
    ERR_BUSY,                    // 资源忙
    ERR_PARAM,                   // 参数错误
    // ... 更多错误代码
} ErrorCode_t;
```

---

### 错误处理函数

#### `Error_Handler`

```c
void Error_Handler(void);
```

**描述**: 默认错误处理函数（进入死循环，LED闪烁）

**注意**: 此函数不会返回

---

#### `ERROR_HANDLER`

```c
#define ERROR_HANDLER(code)  Error_Handler_Detailed((code), __FILE__, __LINE__)
```

**描述**: 带详细信息的错误处理宏

**参数**:
| 参数 | 描述 |
|------|------|
| `code` | 错误代码 |

**示例**:
```c
#include "error_handler.h"

if (HAL_UART_Transmit(...) != HAL_OK)
{
    ERROR_HANDLER(ERR_UART_TX);
}
```

---

#### `Error_GetMessage`

```c
const char* Error_GetMessage(ErrorCode_t code);
```

**描述**: 获取错误代码对应的消息字符串

**返回值**: 错误消息字符串

**示例**:
```c
const char* msg = Error_GetMessage(ERR_UART_TX);
// msg = "UART Transmission Failed"
```

---

## 数据类型

### HAL 状态类型

```c
typedef enum {
    HAL_OK       = 0x00,
    HAL_ERROR    = 0x01,
    HAL_BUSY     = 0x02,
    HAL_TIMEOUT  = 0x03
} HAL_StatusTypeDef;
```

---

### GPIO 引脚状态

```c
typedef enum {
    GPIO_PIN_RESET = 0,
    GPIO_PIN_SET
} GPIO_PinState;
```

---

### 标志状态

```c
typedef enum {
    RESET = 0,
    SET   = !RESET
} FlagStatus, ITStatus;
```

---

## 使用示例

### LED 控制

```c
#include "stm32f4xx_hal.h"
#include "board.h"
#include "error_handler.h"

void LED_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    __HAL_RCC_GPIOF_CLK_ENABLE();

    GPIO_InitStruct.Pin = BOARD_LED0_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;

    if (HAL_GPIO_Init(BOARD_LED0_PORT, &GPIO_InitStruct) != HAL_OK)
    {
        ERROR_HANDLER(ERR_GPIO_INIT);
    }

    // 初始状态：熄灭
    HAL_GPIO_WritePin(BOARD_LED0_PORT, BOARD_LED0_PIN, GPIO_PIN_SET);
}

int main(void)
{
    HAL_Init();
    LED_Init();

    while (1)
    {
        HAL_GPIO_TogglePin(BOARD_LED0_PORT, BOARD_LED0_PIN);
        HAL_Delay(500);
    }

    return 0;
}
```

---

### 按键读取

```c
#include "stm32f4xx_hal.h"
#include "board.h"

void KEY_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    __HAL_RCC_GPIOE_CLK_ENABLE();

    GPIO_InitStruct.Pin = BOARD_KEY0_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_PULLUP;  // 上拉

    HAL_GPIO_Init(BOARD_KEY0_PORT, &GPIO_InitStruct);
}

uint8_t KEY_IsPressed(void)
{
    return (HAL_GPIO_ReadPin(BOARD_KEY0_PORT, BOARD_KEY0_PIN) == GPIO_PIN_RESET);
}

int main(void)
{
    HAL_Init();
    KEY_Init();

    while (1)
    {
        if (KEY_IsPressed())
        {
            // 按键被按下
        }
        HAL_Delay(10);
    }

    return 0;
}
```

---

### UART 调试输出

```c
#include "stm32f4xx_hal.h"
#include "uart.h"
#include "error_handler.h"

UART_HandleTypeDef uart_handle;
static const UART_Config_t uart_config = UART_DEFAULT_CONFIG_INIT;

void UART_Init_Debug(void)
{
    if (UART_Init(&uart_handle, USART1, &uart_config) != UART_STATE_OK)
    {
        ERROR_HANDLER(ERR_UART_INIT);
    }

    UART_SendString(&uart_handle, "UART Initialized!\r\n", 1000);
}

int main(void)
{
    HAL_Init();
    UART_Init_Debug();

    uint32_t counter = 0;
    while (1)
    {
        UART_Printf(&uart_handle, "Counter: %lu\r\n", counter++);
        HAL_Delay(1000);
    }

    return 0;
}
```

---

### DWT 精准延时

```c
#include "stm32f4xx_hal.h"
#include "timer.h"

int main(void)
{
    HAL_Init();

    // 初始化DWT
    DWT_Init();

    // 配置LED
    // ...

    while (1)
    {
        // 产生精确的PWM波形
        HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_RESET);  // 高电平
        delay_us(1000);  // 1ms

        HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_SET);    // 低电平
        delay_us(1000);  // 1ms
    }

    return 0;
}
```

---

## 硬件连接

### LED
| 设备 | 引脚 | 极性 |
|------|------|------|
| LED0 | PF9 | 共阳极（低点亮） |
| LED1 | PF10 | 共阳极（低点亮） |

### 按键
| 设备 | 引脚 | 触发方式 |
|------|------|----------|
| KEY0 | PE4 | 低电平触发 |
| KEY_UP | PA0 | 高电平触发 |

### UART
| 功能 | 引脚 | 备注 |
|------|------|------|
| USART1_TX | PA9 | 需配置复用功能 |
| USART1_RX | PA10 | 需配置复用功能 |

---

**更多详细信息，请参考对应的头文件和源代码。**
