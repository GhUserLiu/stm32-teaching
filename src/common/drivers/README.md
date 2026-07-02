# 外设驱动库

本目录包含基于STM32 HAL库的简化外设驱动，遵循项目代码规范。

---

## 驱动列表

| 驱动 | 状态 | 说明 |
|------|------|------|
| **UART** | ✅ 完成 | 串口通信驱动，支持发送/接收/Printf |
| **Timer** | ✅ 完成 | 定时器驱动，支持精准延时（DWT） |
| SPI | 🚧 计划中 | SPI通信驱动 |
| I2C | 🚧 计划中 | I2C通信驱动 |
| ADC | 🚧 计划中 | 模数转换驱动 |

---

## UART驱动使用示例

### 初始化UART

```c
#include "uart.h"

/* 定义UART句柄 */
UART_HandleTypeDef uart_handle;

/* 定义UART配置 */
static const UART_Config_t uart_config = UART_DEFAULT_CONFIG_INIT;

int main(void)
{
    HAL_Init();

    /* 初始化UART1 */
    if (UART_Init(&uart_handle, USART1, &uart_config) != UART_STATE_OK)
    {
        Error_Handler();
    }

    /* 使用UART... */
    UART_SendString(&uart_handle, "UART Initialized!\r\n", 1000);

    while (1)
    {
        /* 主循环 */
    }
}
```

### 发送数据

```c
/* 发送字符串 */
UART_SendString(&uart_handle, "Hello, World!\r\n", 1000);

/* 发送单个字符 */
UART_SendChar(&uart_handle, 'A', 1000);

/* 发送缓冲区 */
uint8_t data[] = {0x01, 0x02, 0x03};
UART_SendBuffer(&uart_handle, data, sizeof(data), 1000);
```

### 接收数据

```c
/* 接收单个字符 */
int ch = UART_GetChar(&uart_handle, 1000);
if (ch >= 0)
{
    /* 成功接收字符 */
}

/* 接收缓冲区 */
uint8_t rx_buffer[32];
if (UART_Receive(&uart_handle, rx_buffer, sizeof(rx_buffer), 1000) == UART_STATE_OK)
{
    /* 成功接收数据 */
}
```

### Printf功能

```c
/* 使用Printf输出格式化字符串 */
UART_Printf(&uart_handle, "Temperature: %d.%d C\r\n", temp_int, temp_dec);
UART_Printf(&uart_handle, "Counter: %lu\r\n", counter);
```

---

## Timer驱动使用示例

### DWT精准延时

```c
#include "timer.h"

int main(void)
{
    HAL_Init();

    /* 初始化DWT（仅需初始化一次） */
    DWT_Init();

    while (1)
    {
        /* 点亮LED */
        HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_RESET);

        /* 微秒级延时 */
        delay_us(500);

        /* 熄灭LED */
        HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_SET);

        /* 毫秒级延时 */
        delay_ms(500);
    }
}
```

### 获取DWT周期计数

```c
/* 获取当前周期计数 */
uint32_t start = DWT_GetCycle();

/* 执行某些操作... */
Do_Something();

/* 计算耗时（微秒） */
uint32_t cycles = DWT_GetCycle() - start;
uint32_t us_time = cycles / (SystemCoreClock / 1000000u);
```

---

## GPIO使用示例

### LED控制

```c
/* 初始化LED引脚（输出模式） */
GPIO_InitTypeDef GPIO_InitStruct = {0};
GPIO_InitStruct.Pin = GPIO_PIN_9;        /* PF9: LED0 */
GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
GPIO_InitStruct.Pull = GPIO_NOPULL;
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
HAL_GPIO_Init(GPIOF, &GPIO_InitStruct);

/* 控制LED */
HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_RESET);  /* 点亮（低电平） */
HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_SET);    /* 熄灭（高电平） */
HAL_GPIO_TogglePin(GPIOF, GPIO_PIN_9);                 /* 翻转 */
```

### 按键读取

```c
/* 初始化按键引脚（输入模式，上拉） */
GPIO_InitTypeDef GPIO_InitStruct = {0};
GPIO_InitStruct.Pin = GPIO_PIN_4;        /* PE4: KEY0 */
GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
GPIO_InitStruct.Pull = GPIO_PULLUP;
HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);

/* 读取按键状态 */
GPIO_PinState key_state = HAL_GPIO_ReadPin(GPIOE, GPIO_PIN_4);
if (key_state == GPIO_PIN_RESET)
{
    /* 按键被按下（低电平） */
}
```

---

## 硬件连接参考

### UART1
| 功能 | 引脚 | 备注 |
|------|------|------|
| TX | PA9 | USART1_TX |
| RX | PA10 | USART1_RX |

### UART2
| 功能 | 引脚 | 备注 |
|------|------|------|
| TX | PA2 | USART2_TX |
| RX | PA3 | USART2_RX |

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

---

## 注意事项

1. **时钟配置**: 使用外设前必须先使能相应时钟
2. **GPIO配置**: UART等外设需要配置GPIO复用功能
3. **错误处理**: 所有驱动函数都返回状态码，应检查返回值
4. **中断优先级**: 如使用中断模式，需合理配置NVIC优先级
5. **Printf支持**: UART_Printf需要在链接器中配置（使用`_write`函数）

---

## 下一步

- 查看具体驱动的头文件了解更多API
- 参考 [01-turn-signal](../../projects/01-turn-signal/) 项目示例
- 参考 [07-car-gear](../../projects/07-car-gear/) 项目了解DWT使用

---

**如有问题，请参考项目文档或联系课程教师。**
