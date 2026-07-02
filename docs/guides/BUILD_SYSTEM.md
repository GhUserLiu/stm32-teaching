# 构建系统说明

本项目支持多种构建方式，包括 Makefile 和 EIDE。

## Makefile 构建系统

### 基本用法

```bash
# 默认构建（构建 01-turn-signal 项目）
make

# 构建指定项目
make PROJECT=07-car-gear

# 查看帮助
make help
```

### 构建类型

```bash
# 调试构建（默认，包含调试符号，-O0）
make debug
make PROJECT=XX debug

# 发布构建（优化，-O2）
make release
make PROJECT=XX release
```

### 其他目标

```bash
# 清理构建文件
make clean

# 列出所有可用项目
make list

# 显示内存使用情况
make size
make PROJECT=XX size

# 生成反汇编列表
make disasm
make PROJECT=XX disasm
```

### 输出文件

构建成功后，输出文件位于 `build/<项目名>/<构建类型>/`：

| 文件 | 说明 |
|------|------|
| `<project>.elf` | ELF 可执行文件（用于调试） |
| `<project>.hex` | Intel HEX 格式（常用烧录格式） |
| `<project>.bin` | 二进制格式 |
| `<project>.map` | 内存映射文件 |
| `<project>.lst` | 反汇编列表（需 make disasm） |

## EIDE 构建系统

EIDE (Embedded IDE) 是 VSCode 的嵌入式开发插件。

### 切换项目

使用 `switch_project.sh` 脚本切换 EIDE 的活动项目：

```bash
bash tools/scripts/switch_project.sh <项目名称>
```

然后重新加载 VSCode 窗口。

### VSCode 任务

可用的构建任务（按 `Ctrl+Shift+P` 或 `F1`，然后输入 "Tasks: Run Task"）：

| 任务 | 说明 |
|------|------|
| `build` | 构建项目 |
| `flash` | 烧录到设备 |
| `build and flash` | 构建并烧录 |
| `rebuild` | 重新构建 |
| `clean` | 清理构建文件 |
| `make help` | 显示 Makefile 帮助 |
| `make size` | 显示内存使用 |

### 快捷键

默认快捷键（可在 VSCode 键盘设置中自定义）：

| 快捷键 | 功能 |
|--------|------|
| `F5` | 启动调试 |
| `F6` | 构建 |
| `Ctrl+F5` | 构建并烧录 |

## 工具链

项目使用 ARM GCC 工具链：

- **编译器**: `arm-none-eabi-gcc`
- **汇编器**: `arm-none-eabi-as`
- **链接器**: `arm-none-eabi-ld`
- **对象复制**: `arm-none-eabi-objcopy`

### 安装工具链

#### Windows

使用 EIDE 自动安装，或手动下载：
https://developer.arm.com/downloads/-/gnu-rm

#### Linux

```bash
sudo apt install gcc-arm-none-eabi
```

#### macOS

```bash
brew install arm-none-eabi-gcc
```

## 链接脚本

项目使用 `STM32F407XX_FLASH.ld` 链接脚本定义内存布局：

- Flash: 1MB (0x08000000 - 0x080FFFFF)
- RAM: 128KB (0x20000000 - 0x2001FFFF)

## 项目类型检测

Makefile 自动检测项目类型：

1. **标准项目**: 包含 `main.c`
2. **中断项目**: 包含 `main_interrupt.c`（优先级更高）
3. **CubeMX 项目**: 使用独立的构建系统

CubeMX 项目需要在其 `cubemx/` 目录下单独构建。
