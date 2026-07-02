# 新建项目指南

本指南介绍如何创建一个新的 STM32F407 项目。

## 方法一：使用脚本（推荐）

使用 `new_project.sh` 脚本快速创建新项目：

```bash
# 在项目根目录执行
bash tools/scripts/new_project.sh <项目编号> <项目名称>

# 示例：创建项目 02-led-blink
bash tools/scripts/new_project.sh 02 led-blink
```

脚本会自动：
1. 创建项目目录结构
2. 复制模板文件（main.c, config.h）
3. 生成项目 README

## 方法二：手动创建

### 1. 创建项目目录

```bash
mkdir -p projects/02-my-project
cd projects/02-my-project
```

### 2. 创建必需文件

#### config.h - 项目配置

```c
#ifndef __CONFIG_H
#define __CONFIG_H

/* 硬件配置 */
#define YOUR_CONFIG_HERE  1

/* 时序配置（毫秒） */
#define MAIN_LOOP_DELAY   10

#endif /* __CONFIG_H */
```

#### main.c - 主程序

```c
#include <stdint.h>
#include "stm32f4xx_hal.h"
#include "board.h"
#include "config.h"

void SystemClock_Config(void)
{
    /* 使用默认HSI时钟 */
}

void GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    /* 配置你的GPIO */
}

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    GPIO_Init();

    while (1) {
        /* 你的代码 */
        HAL_Delay(MAIN_LOOP_DELAY);
    }

    return 0;
}
```

### 3. 创建文档目录

```bash
mkdir docs
```

## 项目结构

新建项目后的目录结构：

```
projects/XX-project-name/
├── main.c              # 主程序（必需）
├── config.h            # 项目配置（必需）
├── README.md           # 项目说明
└── docs/               # 项目文档
```

## 构建项目

### 使用 Makefile

```bash
# 构建指定项目
make PROJECT=02-my-project

# 构建调试版本
make PROJECT=02-my-project debug

# 构建发布版本
make PROJECT=02-my-project release

# 查看代码大小
make PROJECT=02-my-project size
```

### 使用 EIDE

1. 运行项目切换脚本：
   ```bash
   bash tools/scripts/switch_project.sh 02-my-project
   ```

2. 重新加载 VSCode 窗口

3. 使用 VSCode 任务或命令面板构建

## 开发流程

1. **编辑代码**：修改 `main.c` 实现你的功能
2. **配置硬件**：在 `config.h` 中配置项目特定参数
3. **构建**：编译生成 .hex 文件
4. **烧录**：使用 ST-Link 或 J-Link 烧录到开发板
5. **测试**：在硬件上验证功能

## 常见问题

### 如何使用更多的GPIO？

参考 `common/hal/board.h` 中定义的可用GPIO引脚：

```c
// 在你的代码中使用
#define BOARD_MY_GPIO_PORT  GPIOB
#define BOARD_MY_GPIO_PIN   GPIO_PIN_0
```

### 如何添加中断支持？

创建 `main_interrupt.c` 替代 `main.c`，Makefile 会自动检测并使用中断版本。

### 如何使用 CubeMX？

在 `projects/` 下创建带 `cubemx/` 子目录的结构，然后使用 STM32CubeMX 生成代码。
