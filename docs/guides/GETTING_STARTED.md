# 快速入门指南

欢迎使用 STM32F407 嵌入式开发项目！本指南将带你从零开始使用本开发框架。

---

## 📋 目录

1. [项目简介](#项目简介)
2. [环境准备](#环境准备)
3. [第一个项目](#第一个项目)
4. [理解项目结构](#理解项目结构)
5. [常见问题](#常见问题)
6. [进阶学习](#进阶学习)

---

## 项目简介

### 硬件平台

- **开发板**: M144Z-M4 最小系统板
- **MCU**: STM32F407ZGTx
  - 168MHz 主频
  - 1MB Flash
  - 192KB RAM
  - 丰富的外设接口

### 板载资源

| 资源 | 说明 | 引脚 |
|------|------|------|
| LED0 | 红色LED（共阳极） | PF9 |
| LED1 | 绿色LED（共阳极） | PF10 |
| KEY0 | 用户按键 | PE4 |
| KEY_UP | 复位按键 | PA0 |

### 项目特点

- ✅ 模块化设计，共享代码库
- ✅ 统一的 HAL 库接口
- ✅ 完善的驱动支持
- ✅ 详细的代码规范
- ✅ 多项目支持

---

## 环境准备

### 方法一：VSCode + EIDE（推荐）

#### 1. 安装 VSCode

下载并安装 [Visual Studio Code](https://code.visualstudio.com/)

#### 2. 安装 EIDE 插件

1. 打开 VSCode
2. 按 `Ctrl+Shift+X` 打开扩展面板
3. 搜索 "EIDE"
4. 点击 "Install" 安装

#### 3. 打开项目

```bash
# 克隆或下载项目后，在VSCode中打开
code /path/to/stm32-teaching
```

#### 4. 配置 EIDE

1. 点击左下角 EIDE 图标
2. 选择 "配置项目"
3. 选择 STM32/Cortex-M
4. 工具链会自动下载

### 方法二：命令行开发

#### 1. 安装 ARM 工具链

**Windows**: 从 [ARM官网](https://developer.arm.com/downloads/-/gnu-rm) 下载

**Linux**:
```bash
sudo apt install gcc-arm-none-eabi
```

**macOS**:
```bash
brew install arm-none-eabi-gcc
```

#### 2. 安装烧录工具

- ST-Link Utility: 从ST官网下载
- 或使用 OpenOCD: `sudo apt install openocd`

#### 3. 克隆项目

```bash
git clone https://github.com/GhUserLiu/ProjectF407.git
cd ProjectF407
```

---

## 第一个项目

### 任务：LED闪烁

让我们创建一个让LED闪烁的项目，这是嵌入式开发的"Hello World"。

#### 1. 创建项目

**使用脚本**:
```bash
bash tools/scripts/new_project.sh 02 led-blink
```

**手动创建**:
```bash
cp -r projects/_template projects/02-led-blink
```

#### 2. 编写代码

编辑 `projects/02-led-blink/main.c`:

```c
#include <stdint.h>
#include "stm32f4xx_hal.h"
#include "board.h"
#include "config.h"

/* ========== 私有变量 ========== */
static uint32_t blink_count = 0;

/* ========== 私有函数声明 ========== */
static void Error_Handler(void);
static void SystemClock_Config(void);
static void GPIO_Init(void);

/* ========== 主函数 ========== */
int main(void)
{
    /* HAL库初始化 */
    HAL_Init();
    SystemClock_Config();

    /* GPIO初始化 */
    GPIO_Init();

    /* 主循环 */
    while (1)
    {
        /* 翻转LED0 */
        HAL_GPIO_TogglePin(BOARD_LED0_PORT, BOARD_LED0_PIN);

        /* 更新计数 */
        blink_count++;

        /* 延时500ms */
        HAL_Delay(500);
    }

    return 0;
}

/* ========== GPIO初始化 ========== */
void GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    /* 使能GPIOF时钟 */
    __HAL_RCC_GPIOF_CLK_ENABLE();

    /* 配置LED0引脚（PF9） */
    GPIO_InitStruct.Pin = BOARD_LED0_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;

    if (HAL_GPIO_Init(BOARD_LED0_PORT, &GPIO_InitStruct) != HAL_OK)
    {
        Error_Handler();
    }

    /* 初始状态：熄灭（高电平） */
    HAL_GPIO_WritePin(BOARD_LED0_PORT, BOARD_LED0_PIN, GPIO_PIN_SET);
}

/* ========== 系统时钟配置 ========== */
void SystemClock_Config(void)
{
    /* 使用默认HSI时钟（16MHz） */
}

/* ========== 错误处理 ========== */
static void Error_Handler(void)
{
    while (1)
    {
        /* LED快速闪烁表示错误 */
        HAL_GPIO_TogglePin(BOARD_LED0_PORT, BOARD_LED0_PIN);
        HAL_Delay(100);
    }
}
```

#### 3. 构建项目

**使用 Make**:
```bash
make PROJECT=02-led-blink
```

**使用 EIDE**:
1. 点击 "构建" 按钮
2. 或按 `F7` 快捷键

#### 4. 烧录到板子

**使用 ST-Link**:
```bash
# 使用 st-flash
st-flash build/02-led-blink.bin

# 或使用 EIDE 的 "烧录" 按钮
```

#### 5. 观察结果

如果一切正常，你应该看到LED0以500ms的间隔闪烁。

---

## 理解项目结构

```
stm32-teaching/
├── projects/              # 各个项目
│   ├── _template/         # 项目模板
│   ├── 01-turn-signal/    # 转向灯项目
│   ├── 02-led-blink/      # 你的LED项目
│   └── 07-car-gear/       # 汽车档位项目
├── common/                # 共享代码库
│   ├── core/              # HAL库核心
│   │   ├── stm32f4xx_hal.h
│   │   └── error_handler.h
│   ├── bsp/               # 板级支持包
│   │   └── board.h        # 硬件定义
│   ├── drivers/           # 外设驱动
│   │   ├── uart/          # UART驱动
│   │   └── timer/         # 定时器驱动
│   └── inc/               # 公共头文件
├── docs/                  # 文档
├── tools/                 # 开发工具
└── Makefile              # 构建脚本
```

### 代码组织原则

1. **共享代码放在 `common/`**
   - HAL 库核心：`common/core/`
   - 硬件定义：`common/bsp/`
   - 外设驱动：`common/drivers/`

2. **项目特定代码放在 `projects/XX/`**
   - 不要修改 `common/` 中的文件
   - 项目配置放在 `config.h`

3. **遵循代码规范**
   - 阅读 `docs/guides/CODING_STYLE.md`
   - 统一使用 HAL 库
   - 检查返回值

---

## 常见问题

### Q1: 编译错误 "arm-none-eabi-gcc: command not found"

**解决方法**: 工具链未正确安装或未添加到PATH。

**Windows**: 确保 EIDE 已正确下载工具链，或手动添加到PATH

**Linux/macOS**:
```bash
# 检查是否安装
which arm-none-eabi-gcc

# 如果没有，重新安装
# Linux
sudo apt install gcc-arm-none-eabi

# macOS
brew install arm-none-eabi-gcc
```

### Q2: 烧录失败 "ST-Link not found"

**解决方法**:
1. 检查ST-Link连接
2. 安装驱动（Windows）
3. 尝试使用 sudo（Linux）

### Q3: LED不亮或不闪烁

**可能原因**:
1. 代码逻辑错误 - 检查HAL函数返回值
2. GPIO配置错误 - 确认引脚和模式
3. 硬件问题 - 检查LED连接

**调试方法**:
```c
// 添加调试代码
HAL_GPIO_WritePin(BOARD_LED0_PORT, BOARD_LED0_PIN, GPIO_PIN_RESET);  // 强制点亮
while(1);  // 停止在这里，用万用表测量电压
```

### Q4: 如何使用UART打印调试信息？

**参考**:
```c
#include "uart.h"

UART_HandleTypeDef uart_handle;
static const UART_Config_t uart_config = UART_DEFAULT_CONFIG_INIT;

void UART_Init_Debug(void)
{
    UART_Init(&uart_handle, USART1, &uart_config);
    UART_SendString(&uart_handle, "Debug Start\r\n", 1000);
}

void main(void)
{
    HAL_Init();
    UART_Init_Debug();

    UART_Printf(&uart_handle, "Counter: %lu\r\n", counter);
}
```

---

## 进阶学习

### 1. 学习HAL库API

阅读 [HAL API 文档](../api/HAL_API.md)，了解：
- GPIO操作
- UART通信
- 定时器使用
- 中断处理

### 2. 查看示例项目

- **01-turn-signal**: 转向灯系统（状态机实现）
- **07-car-gear**: 汽车档位模拟器（中断+DWT延时）

### 3. 实现更多功能

尝试实现：
- [ ] 按键控制LED
- [ ] PWM调光
- [ ] UART通信
- [ ] 定时器中断
- [ ] ADC采集

### 4. 使用驱动库

参考 [驱动库文档](../../common/drivers/README.md)：
- UART驱动
- Timer驱动

### 5. 错误处理

使用统一错误处理框架：
```c
#include "error_handler.h"

if (HAL_UART_Transmit(...) != HAL_OK)
{
    ERROR_HANDLER(ERR_UART_TX);
}
```

---

## 下一步

恭喜你完成了第一个项目！现在可以：

1. 阅读 [代码风格指南](CODING_STYLE.md)
2. 查看 [API 文档](../api/HAL_API.md)
3. 尝试 [新建项目指南](NEW_PROJECT.md)
4. 探索更多 [示例项目](../../projects/)

---

**祝你学习愉快！如有问题，请参考项目文档或联系课程教师。**
