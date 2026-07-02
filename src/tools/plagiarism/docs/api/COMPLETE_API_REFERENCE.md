# STM32F407 嵌入式教学平台 - 完整 API 参考

## 目录

1. [HAL 库 API](#hal-库-api)
2. [板级支持包 API](#板级支持包-api)
3. [驱动库 API](#驱动库-api)
4. [Python 工具 API](#python-工具-api)

---

## HAL 库 API

### 核心 HAL 函数

#### `HAL_Init()`
```c
HAL_StatusTypeDef HAL_Init(void);
```
**描述**: 初始化 HAL 库

**返回值**:
- `HAL_OK`: 成功
- `HAL_ERROR`: 错误
- `HAL_BUSY`: 忙碌
- `HAL_TIMEOUT`: 超时

#### `SystemClock_Config()`
```c
void SystemClock_Config(void);
```
**描述**: 配置系统时钟为 168MHz

---

### GPIO 操作

#### `HAL_GPIO_Init()`
```c
void HAL_GPIO_Init(GPIO_TypeDef *GPIOx, GPIO_InitTypeDef *GPIO_Init);
```
**描述**: 初始化 GPIO 引脚

#### `HAL_GPIO_WritePin()`
```c
void HAL_GPIO_WritePin(GPIO_TypeDef *GPIOx, uint16_t GPIO_Pin, GPIO_PinState PinState);
```
**描述**: 写入 GPIO 引脚状态

#### `HAL_GPIO_ReadPin()`
```c
GPIO_PinState HAL_GPIO_ReadPin(GPIO_TypeDef *GPIOx, uint16_t GPIO_Pin);
```
**描述**: 读取 GPIO 引脚状态

---

## 板级支持包 API

### LED 控制
```c
#define LED0_PIN        GPIO_PIN_9   // PF9
#define LED1_PIN        GPIO_PIN_10  // PF10

// 点亮 LED（低电平有效）
HAL_GPIO_WritePin(LED0_PORT, LED0_PIN, GPIO_PIN_RESET);

// 翻转 LED
HAL_GPIO_TogglePin(LED0_PORT, LED0_PIN);
```

### 按键读取
```c
#define KEY0_PIN        GPIO_PIN_4   // PE4
#define KEY_UP_PIN      GPIO_PIN_0   // PA0

GPIO_PinState key_state = HAL_GPIO_ReadPin(GPIOE, KEY0_PIN);
```

---

## 驱动库 API

### UART 驱动
```c
// 初始化
UART_Init(&uart_handle, USART1, &uart_config);

// 发送
UART_SendString(&uart_handle, "Hello\r\n", 1000);

// 接收
int ch = UART_GetChar(&uart_handle, 1000);

// Printf
UART_Printf(&uart_handle, "Temperature: %d\r\n", temp);
```

### Timer 驱动
```c
// 初始化 DWT
DWT_Init();

// 微秒延时
delay_us(500);

// 获取周期计数
uint32_t cycles = DWT_GetCycle();
```

---

## Python 工具 API

### 查重检测
```python
from tools.plagiarism.core import PlagiarismDetector, SimilarityMethod

detector = PlagiarismDetector(
    method=SimilarityMethod.HYBRID,
    threshold=60.0
)
results = detector.detect(submissions)
```

### 评分系统
```python
from tools.plagiarism.grading import EnhancedGradingSystem

grading = EnhancedGradingSystem(rubric_path='rubric.json')
results = grading.grade(submissions)
```

### 反馈生成
```python
from tools.plagiarism.feedback import UnifiedFeedbackGenerator

generator = UnifiedFeedbackGenerator(style='detailed')
feedback = generator.generate(student_result)
```

---

## 完整示例

### STM32 LED 闪烁
```c
#include "stm32f4xx_hal.h"
#include "board.h"

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    
    // 初始化 LED
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = LED0_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(LED0_PORT, &GPIO_InitStruct);
    
    while (1) {
        HAL_GPIO_TogglePin(LED0_PORT, LED0_PIN);
        HAL_Delay(500);
    }
}
```

---

## 更多资源

- [HAL API 详细文档](HAL_API.md)
- [板级支持包 API](BOARD_API.md)
- [驱动使用指南](../../common/drivers/README.md)

---
**最后更新**: 2026-06-12
