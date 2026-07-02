# 代码风格指南 (v2.0)

本文档定义了 STM32F407 嵌入式教学平台的统一编码规范。**所有项目必须遵循此规范。**

---

## 🎯 核心原则

### 统一编程方式
**本项目统一使用 STM32 HAL 库进行开发**，禁止以下做法：
- ❌ 混合使用 HAL 库和直接寄存器操作
- ❌ 完全使用直接寄存器操作（特殊情况需文档说明）
- ❌ 不同的代码风格在不同项目中

### 例外情况
允许使用寄存器操作的情况：
- 性能关键代码（需注释说明）
- HAL 库不支持的硬件功能
- 启动代码（startup、Reset_Handler）

---

## 📝 命名规范

### 文件命名
```c
// C 源文件：小写，下划线分隔
stm32f4xx_hal.c
gpio_config.c

// 头文件：小写，下划线分隔
stm32f4xx_hal.h
gpio_config.h
```

### 变量命名
```c
// 全局变量：小写，下划线分隔
uint32_t toggle_counter = 0;
volatile uint8_t led0_state = 1;

// 局部变量：小写，下划线分隔
uint8_t key0_now, key_up_now;

// 静态变量：小写，下划线分隔
static uint32_t private_counter = 0;

// 常量/宏：大写，下划线分隔
#define MAX_COUNT  100
#define LED_PIN    GPIO_PIN_9
#define LED_TOGGLE_INTERVAL  25
```

### 函数命名
```c
// 公共函数：大驼峰（PascalCase）
void SystemClock_Config(void);
void GPIO_Init(void);
uint8_t Read_KEY0(void);
void LED_Update(void);

// 私有函数：小驼峰（camelCase）+ static
static void ledUpdateInternal(void);
static uint8_t getKeyState(void);

// HAL 库函数：保持 ST 原有命名
HAL_GPIO_Init(...);
HAL_GPIO_WritePin(...);
```

### 类型定义
```c
// 枚举类型：大驼峰 + _t 后缀
typedef enum {
    MODE_OFF = 0,
    MODE_LEFT,
    MODE_RIGHT
} LightMode_t;

// 结构体：大驼峰 + _t 后缀
typedef struct {
    uint32_t pin;
    uint32_t mode;
    uint32_t speed;
} GPIOConfig_t;
```

---

## 📐 格式规范

### 缩进和对齐
```c
// 使用 4 个空格缩进（不使用 Tab）
// 大括号独占一行（Allman 风格）
void Function_Name(void)
{
    if (condition)
    {
        Do_Something();
    }
    else
    {
        Do_Other_Thing();
    }

    // switch 语句格式
    switch (value)
    {
        case VALUE1:
            doSomething();
            break;

        case VALUE2:
            doOtherThing();
            break;

        default:
            doDefault();
            break;
    }
}
```

### 注释规范
```c
/* ========== 单行注释 ========== */

/* ========== 区域分隔注释 ========== */
/* ========== 功能区域名称 ========== */

/**
  ******************************************************************************
  * @file    : filename.h
  * @brief   : 文件简短描述
  * @author  : 作者名称
  * @date    : 创建日期
  ******************************************************************************
  */

/**
  * @brief  函数简短描述
  * @param  param1: 参数1描述
  * @param  param2: 参数2描述
  * @retval 返回值描述
  */
```

---

## 📂 代码组织

### 头文件结构
```c
#ifndef __FILENAME_H
#define __FILENAME_H

#ifdef __cplusplus
extern "C" {
#endif

/* ========== Includes ========== */
#include <stdint.h>
#include "stm32f4xx_hal.h"

/* ========== Macros ========== */
#define CONFIG_VALUE  100

/* ========== Type Definitions ========== */
typedef enum { ... } MyEnum_t;

/* ========== Function Declarations ========== */
void Function_Name(void);

#ifdef __cplusplus
}
#endif

#endif /* __FILENAME_H */
```

### 源文件结构
```c
/* ========== Includes ========== */
#include "main.h"
#include "config.h"

/* ========== Private Macros ========== */
#define PRIVATE_MACRO  100

/* ========== Private Type Definitions ========== */
typedef enum { ... } PrivateEnum_t;

/* ========== Global Variables ========== */
volatile uint8_t system_flag = 0;

/* ========== Private Variables ========== */
static uint32_t counter = 0;

/* ========== Private Function Prototypes ========== */
static void Private_Function(void);

/* ========== Public Function Definitions ========== */
void Public_Function(void)
{
    // ...
}

/* ========== Private Function Definitions ========== */
static void Private_Function(void)
{
    // ...
}
```

---

## ✅ 最佳实践

### 1. 使用 volatile 关键字
```c
// 中断中修改的变量必须使用 volatile
volatile uint32_t system_tick = 0;
volatile uint8_t data_ready = 0;
```

### 2. 检查返回值
```c
// 必须检查 HAL 函数返回值
if (HAL_GPIO_Init(...) != HAL_OK)
{
    Error_Handler();
}

if (HAL_UART_Transmit(...) != HAL_OK)
{
    // 错误处理
}
```

### 3. 避免魔术数字
```c
// ✅ 好的做法
#define LED_TOGGLE_INTERVAL  25
if (toggle_counter >= LED_TOGGLE_INTERVAL)

// ❌ 不好的做法
if (toggle_counter >= 25)
```

### 4. 使用宏定义替代硬编码
```c
// ✅ 好
#define LED0_PIN    GPIO_PIN_9
#define LED0_PORT   GPIOF

// ❌ 不好
HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, state);
```

### 5. 错误处理
```c
// 定义统一的错误处理函数
void Error_Handler(void)
{
    // 禁用中断
    __disable_irq();

    // 点亮错误指示LED
    HAL_GPIO_WritePin(ERROR_LED_PORT, ERROR_LED_PIN, GPIO_PIN_RESET);

    // 进入死循环
    while (1)
    {
        // 可添加闪烁等错误提示
    }
}
```

---

## 🔧 工具支持

### VSCode 配置
在 `.vscode/settings.json` 中：
```json
{
    "editor.formatOnSave": true,
    "C_Clint.clang_format_style": "file",
    "C_Clint.default.cStandard": "c11",
    "C_Clint.default.cppStandard": "c++11"
}
```

### Clang-Format 配置
项目提供 `.clang-format` 配置文件，自动格式化代码：
```bash
# 格式化单个文件
clang-format -i filename.c

# 格式化整个项目
find . -name "*.c" -o -name "*.h" | xargs clang-format -i
```

---

## 📋 代码审查清单

提交代码前，确保：
- [ ] 遵循命名规范
- [ ] 使用 4 空格缩进
- [ ] 检查所有 HAL 函数返回值
- [ ] 没有魔术数字
- [ ] 中断变量使用 volatile
- [ ] 有适当的注释
- [ ] 通过 clang-format 格式化
- [ ] 编译无警告

---

## 🚫 禁止事项

1. ❌ 混合使用 HAL 和寄存器操作（特殊情况除外）
2. ❌ 使用 Tab 字符缩进
3. ❌ 魔术数字
4. ❌ 不检查返回值
5. ❌ 全局变量不加 volatile（中断相关）
6. ❌ 函数超过 100 行（应拆分）

---

## 📚 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v2.0 | 2026-06-11 | 统一使用HAL库，明确禁止混合编程 |
| v1.0 | 2025-xx-xx | 初始版本 |

---

## 🔗 相关文档

- [HAL 库 API 文档](../api/HAL_API.md)
- [板级支持包 API](../api/BOARD_API.md)
- [新建项目指南](NEW_PROJECT.md)
