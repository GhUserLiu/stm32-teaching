# STM32F407 嵌入式教学平台 - 项目结构说明

## 模块化组织

本项目采用模块化的目录结构，便于代码组织和维护。

```
stm32f407/
├── src/                          # 源代码
│   ├── common/                   # 共享代码库（模块化 HAL）
│   │   ├── core/                 # 核心 HAL 库（stm32f4xx_hal + error_handler）
│   │   ├── bsp/                  # 板级支持包（board.h 开发板引脚定义）⭐
│   │   ├── drivers/              # 外设驱动（UART、Timer）
│   │   ├── inc/                  # 公共头文件
│   │   └── startup/              # 启动文件（startup_stm32f407xx.s）
│   ├── projects/                 # 实验项目
│   │   ├── _template/            # 新项目模板
│   │   ├── 01-turn-signal/       # 转向灯系统（简单项目）
│   │   ├── 07-car-gear/          # 汽车档位模拟器（CubeMX）
│   │   └── Test6/                # 示例项目（CubeMX）
│   └── tools/                    # 教学管理工具（Python）
│       ├── auto_grading/         # 自动化批阅
│       ├── plagiarism/           # 查重检测
│       ├── teaching_management_gui/  # 教学管理 GUI（PyQt6）
│       ├── student_submission_gui/   # 学生端提交 GUI
│       ├── security/             # 安全工具（路径/ZIP/XML）
│       └── teaching_scripts/     # 教学处理脚本
├── data/                         # 配置 / 模板 / 教学业务数据
├── docs/                         # 文档（api / guides / security / teaching / archive）
├── scripts/                      # 构建 / 重跑辅助脚本
├── tests/                        # 单元 / 集成测试
├── outputs/                      # 运行时输出（不入库）
├── models/                       # 模型文件
├── Makefile                      # 构建脚本
├── STM32F407XX_FLASH.ld          # 链接脚本
├── build_student.spec            # 学生端 exe 构建配置
├── requirements.txt              # Python 依赖
├── PROJECT_STRUCTURE.md          # 结构说明
└── README.md                     # 项目说明
```

## 模块说明

### common/core/
核心 HAL 库实现，包含：
- GPIO 操作
- SysTick 定时器
- 基础时钟控制
- 扩展功能（RCC, EXTI, NVIC）

### common/bsp/
板级支持包，定义：
- LED 引脚和控制宏
- 按键引脚
- 可用 GPIO 列表
- 调试接口
- 串口引脚

### common/drivers/
预留的外设驱动目录，可添加：
- UART 驱动
- SPI 驱动
- I2C 驱动
- Timer 驱动
- ADC 驱动

### common/utils/
预留的工具函数目录，可添加：
- 数学函数库
- 字符串处理
- 数据结构
- 协议实现

## 依赖关系

```
项目代码 (projects/XX/)
    ↓
board.h (common/bsp/)
    ↓
stm32f4xx_hal.h (common/core/)
    ↓
stm32f4xx.h (common/inc/)
    ↓
寄存器定义
```

## 扩展指南

### 添加新的驱动模块

1. 在 `common/drivers/` 创建对应目录
2. 实现驱动接口
3. 在项目中包含对应头文件
4. 更新 Makefile（如需要）

### 支持新的芯片系列

1. 在 `common/core/` 下创建芯片特定目录
2. 添加对应的头文件和源文件
3. 通过编译宏切换

### 添加工具函数

1. 在 `common/utils/` 创建对应文件
2. 实现工具函数
3. 在项目中包含使用
