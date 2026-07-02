# Makefile for STM32F407 Projects (v2.1.0)
# 支持简单项目和CubeMX项目的统一构建
# Usage: make [PROJECT=01-turn-signal|07-car-gear] [target]
# 安全增强：PROJECT参数验证，防御命令注入

# ========================================
# 工具链配置
# ========================================
PREFIX = arm-none-eabi-
CC = $(PREFIX)gcc
AS = $(PREFIX)as
LD = $(PREFIX)ld
OBJCOPY = $(PREFIX)objcopy
SIZE = $(PREFIX)size
OBJDUMP = $(PREFIX)objdump

# ========================================
# 项目配置（安全验证）
# ========================================
PROJECT ?= 01-turn-signal
BUILD_TYPE ?= debug
export BUILD_TYPE    # 让 all 的递归 $(MAKE) build_simple 继承 BUILD_TYPE（修复 release/debug）

# ========== 安全参数验证 ==========
# 定义允许的项目列表（白名单）
ALLOWED_PROJECTS := 01-turn-signal 07-car-gear _template Test6

# 验证PROJECT参数是否在白名单中
ifeq ($(filter $(PROJECT),$(ALLOWED_PROJECTS)),)
    ifneq ($(PROJECT),)
        $(error 错误: 无效的项目名称 '$(PROJECT)'. 允许的项目: $(ALLOWED_PROJECTS))
    endif
endif

# 清理PROJECT参数中的危险字符（防御命令注入）
SAFE_PROJECT := $(shell echo '$(PROJECT)' | tr -cd 'A-Za-z0-9_-')

# 检查清理后的参数是否一致
ifneq ($(PROJECT),$(SAFE_PROJECT))
    $(error 错误: 项目名称包含非法字符. 仅允许字母、数字、下划线和连字符)
endif

# 使用验证后的PROJECT
PROJECT := $(SAFE_PROJECT)

# 项目目录
PROJECT_DIR = src/projects/$(PROJECT)
COMMON_DIR = src/common
BUILD_DIR = outputs/build/$(PROJECT)/$(BUILD_TYPE)

# ========================================
# 项目类型检测
# ========================================
# 检测是否为CubeMX项目（存在cubemx子目录）
IS_CUBEMX = $(wildcard $(PROJECT_DIR)/cubemx/Makefile)

# ========================================
# 编译选项
# ========================================
ifeq ($(BUILD_TYPE),release)
    CFLAGS += -O2 -DNDEBUG
else
    CFLAGS += -O0 -g3
endif

# 基础编译标志
BASE_CFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16
BASE_CFLAGS += -Wall -Wextra
BASE_CFLAGS += -DSTM32F407xx
BASE_LDFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16

# ========================================
# .PHONY 声明
# ========================================
.PHONY: all clean list size debug release flash help cubemx_check

# ========================================
# 默认目标
# ========================================
all: cubemx_check
	@echo "Building project: $(PROJECT)"
ifeq ($(IS_CUBEMX),)
	@$(MAKE) -f $(firstword $(MAKEFILE_LIST)) build_simple
else
	@$(MAKE) -f $(firstword $(MAKEFILE_LIST)) build_cubemx
endif

# ========================================
# 项目类型检查
# ========================================
cubemx_check:
ifeq ($(IS_CUBEMX),)
	@echo "Project type: Simple (single main.c)"
else
	@echo "Project type: CubeMX (generated project)"
endif

# ========================================
# 简单项目构建
# ========================================
build_simple: $(BUILD_DIR)/$(PROJECT).hex

# 源文件
ifeq ($(wildcard $(PROJECT_DIR)/main_interrupt.c),)
    C_SOURCES = $(PROJECT_DIR)/main.c \
                $(COMMON_DIR)/core/stm32f4xx_hal.c
    MAIN_OBJ = $(BUILD_DIR)/main.o
    HAL_EXT_OBJ =
else
    C_SOURCES = $(PROJECT_DIR)/main_interrupt.c \
                $(COMMON_DIR)/core/stm32f4xx_hal.c \
                $(COMMON_DIR)/core/stm32f4xx_hal_ext.c
    MAIN_OBJ = $(BUILD_DIR)/main_interrupt.o
    HAL_EXT_OBJ = $(BUILD_DIR)/stm32f4xx_hal_ext.o
endif

# 项目特定源文件（如果存在）
PROJECT_DEBOUNCE_C = $(wildcard $(PROJECT_DIR)/debounce.c)
ifeq ($(PROJECT_DEBOUNCE_C),)
    DEBOUNCE_OBJ =
else
    DEBOUNCE_OBJ = $(BUILD_DIR)/debounce.o
endif

ASM_SOURCES = $(COMMON_DIR)/startup/startup_stm32f407xx.s
LDSCRIPT = STM32F407XX_FLASH.ld

# 编译标志（用 := 快照，避免原 = 形式的递归自引用）
CFLAGS := $(BASE_CFLAGS) $(CFLAGS)
CFLAGS += -I$(PROJECT_DIR) -I$(COMMON_DIR)/inc -I$(COMMON_DIR)/core -I$(COMMON_DIR)/bsp
CFLAGS += -I$(COMMON_DIR)/drivers/include

# 链接标志
LDFLAGS = $(BASE_LDFLAGS)
LDFLAGS += -T$(LDSCRIPT) -specs=nano.specs -lc -lm -nostartfiles
LDFLAGS += -Wl,-Map=$(BUILD_DIR)/$(PROJECT).map

# 目标文件
OBJECTS = $(MAIN_OBJ) \
          $(BUILD_DIR)/core_stm32f4xx_hal.o \
          $(HAL_EXT_OBJ) \
          $(DEBOUNCE_OBJ) \
          $(BUILD_DIR)/startup_stm32f407xx.o

# 输出文件
ELF = $(BUILD_DIR)/$(PROJECT).elf
HEX = $(BUILD_DIR)/$(PROJECT).hex
BIN = $(BUILD_DIR)/$(PROJECT).bin

# 构建规则
$(BUILD_DIR)/$(PROJECT).hex: $(ELF)
	@echo "Creating BIN file..."
	@mkdir -p $(BUILD_DIR)
	$(OBJCOPY) -O binary $< $(BUILD_DIR)/$(PROJECT).bin
	$(OBJCOPY) -O ihex $< $(BUILD_DIR)/$(PROJECT).hex
	@echo "Build complete!"
	@echo "Output: $(BUILD_DIR)/$(PROJECT).bin"

$(ELF): $(OBJECTS)
	@echo "Linking..."
	@mkdir -p $(BUILD_DIR)
	$(CC) $(LDFLAGS) $(OBJECTS) -o $@

$(BUILD_DIR)/main.o: $(PROJECT_DIR)/main.c
	@echo "Compiling $<..."
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/main_interrupt.o: $(PROJECT_DIR)/main_interrupt.c
	@echo "Compiling $<..."
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/stm32f4xx_hal_ext.o: $(COMMON_DIR)/core/stm32f4xx_hal_ext.c
	@echo "Compiling $<..."
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/core_stm32f4xx_hal.o: $(COMMON_DIR)/core/stm32f4xx_hal.c
	@echo "Compiling $<..."
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/startup_stm32f407xx.o: $(COMMON_DIR)/startup/startup_stm32f407xx.s
	@echo "Assembling $<..."
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

# 项目特定源文件编译规则
$(BUILD_DIR)/debounce.o: $(PROJECT_DIR)/debounce.c
	@echo "Compiling $<..."
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

# ========================================
# CubeMX 项目构建
# ========================================
build_cubemx:
	@echo "Building CubeMX project..."
	@cd $(PROJECT_DIR)/cubemx && $(MAKE) DEBUG=$(if $(filter release,$(BUILD_TYPE)),,1)

# ========================================
# 清理
# ========================================
clean:
ifeq ($(IS_CUBEMX),)
	@echo "Cleaning simple project..."
	rm -rf build/$(PROJECT) outputs/build/$(PROJECT)
else
	@echo "Cleaning CubeMX project..."
	-cd $(PROJECT_DIR)/cubemx && $(MAKE) clean
	rm -rf build/$(PROJECT) outputs/build/$(PROJECT)
endif

# ========================================
# 显示内存使用
# ========================================
size: all
ifeq ($(IS_CUBEMX),)
	@echo "=== Memory Usage ==="
	$(SIZE) $(BUILD_DIR)/$(PROJECT).elf
	@echo ""
	@echo "=== Section Details ==="
	$(SIZE) -A $(BUILD_DIR)/$(PROJECT).elf
else
	@echo "=== Memory Usage ==="
	@cd $(PROJECT_DIR)/cubemx && $(MAKE) size || echo "Size info not available"
endif

# ========================================
# 烧录
# ========================================
flash: all
	@echo "Flashing $(PROJECT)..."
ifeq ($(IS_CUBEMX),)
	st-flash write $(BUILD_DIR)/$(PROJECT).bin 0x8000000
else
	st-flash write $(PROJECT_DIR)/cubemx/build/$(PROJECT).bin 0x8000000
endif

# ========================================
# 调试构建（默认）
# ========================================
debug: BUILD_TYPE = debug
debug: all

# ========================================
# 发布构建
# ========================================
release: BUILD_TYPE = release
release: all

# ========================================
# 反汇编
# ========================================
disasm: all
ifeq ($(IS_CUBEMX),)
	@echo "Generating disassembly..."
	$(OBJDUMP) -d $(BUILD_DIR)/$(PROJECT).elf > $(BUILD_DIR)/$(PROJECT).lst
	@echo "Disassembly saved to $(BUILD_DIR)/$(PROJECT).lst"
else
	@echo "Disassembly for CubeMX projects not yet supported"
endif

# ========================================
# 列出所有项目
# ========================================
list:
	@echo "Available projects:"
	@echo ""
	@echo "Simple Projects:"
	@for dir in src/projects/*/; do \
		if [ ! -d "$$dir/cubemx" ]; then \
			echo "  - $$(basename $$dir)"; \
		fi; \
	done
	@echo ""
	@echo "CubeMX Projects:"
	@for dir in src/projects/*/; do \
		if [ -d "$$dir/cubemx" ]; then \
			echo "  - $$(basename $$dir) (CubeMX)"; \
		fi; \
	done

# ========================================
# 帮助信息
# ========================================
help:
	@echo "STM32F407 Project Makefile v2.0"
	@echo "========================================"
	@echo ""
	@echo "Usage: make [PROJECT=name] [target] [BUILD_TYPE=debug|release]"
	@echo ""
	@echo "Projects:"
	@echo "  01-turn-signal    - LED转向灯系统 (简单项目)"
	@echo "  07-car-gear       - 汽车档位模拟器 (CubeMX项目)"
	@echo "  _template         - 项目模板"
	@echo ""
	@echo "Targets:"
	@echo "  all (default)     - 构建项目（自动检测类型）"
	@echo "  debug             - 调试构建（默认）"
	@echo "  release           - 发布构建（优化）"
	@echo "  clean             - 清理构建文件"
	@echo "  size              - 显示内存使用"
	@echo "  disasm            - 生成反汇编文件"
	@echo "  flash             - 烧录到设备（需要ST-Link）"
	@echo "  list              - 列出所有可用项目"
	@echo "  help              - 显示此帮助信息"
	@echo ""
	@echo "Examples:"
	@echo "  make PROJECT=01-turn-signal"
	@echo "  make PROJECT=07-car-gear release"
	@echo "  make PROJECT=01-turn-signal clean"
	@echo "  make PROJECT=07-car-gear flash"
	@echo ""
	@echo "Build types:"
	@echo "  debug   - 调试版本（-O0 -g3）"
	@echo "  release - 发布版本（-O2）"
