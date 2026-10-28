# f1-selftest —— 实训套件验收自检固件
# 独立 Makefile：教师/学生端自检工具直接 `make` 即可（arm-none-eabi-gcc）
PREFIX  ?= arm-none-eabi-
CC      := $(PREFIX)gcc
OBJCOPY := $(PREFIX)objcopy
SIZE    := $(PREFIX)size

# common-f1 定位：仓库内用 ../common-f1；学生提交打包时把 common-f1 拷进工程目录，
# Makefile 自动回退到 ./common-f1
F1_DIR   := $(if $(wildcard ../common-f1/inc/stm32f103x_min.h),../common-f1,./common-f1)
BUILD    = build

CFLAGS  = -mcpu=cortex-m3 -mthumb -Wall -Wextra -std=c11
CFLAGS += -O0 -g3 -ffunction-sections -fdata-sections
CFLAGS += -I$(F1_DIR)/inc -I.
LDFLAGS = -mcpu=cortex-m3 -mthumb -T$(F1_DIR)/startup/stm32f103c8.ld
LDFLAGS += -Wl,--gc-sections -Wl,-Map=$(BUILD)/$(TARGET).map
LDFLAGS += --specs=nano.specs --specs=nosys.specs

SRC_C   = main.c \
          $(F1_DIR)/src/f1_delay.c \
          $(F1_DIR)/src/f1_printf.c \
          $(F1_DIR)/src/dht11.c \
          $(F1_DIR)/src/ssd1306.c \
          $(F1_DIR)/src/f1_key.c \
          $(F1_DIR)/src/f1_fan.c \
          $(F1_DIR)/src/f1_adc.c
SRC_S   = $(F1_DIR)/startup/startup_stm32f103.s

OBJ     = $(patsubst %.c,$(BUILD)/%.o,$(SRC_C)) \
          $(patsubst %.s,$(BUILD)/%.o,$(SRC_S))

TARGET  = f1-cabin-thermal

.PHONY: all clean flash size

all: $(BUILD)/$(TARGET).elf $(BUILD)/$(TARGET).hex $(BUILD)/$(TARGET).bin
	$(SIZE) $(BUILD)/$(TARGET).elf

$(BUILD)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/%.o: %.s
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/$(TARGET).elf: $(OBJ)
	$(CC) $(OBJ) $(LDFLAGS) -lm -o $@

$(BUILD)/$(TARGET).hex: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O ihex $< $@

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O binary -S $< $@

flash: $(BUILD)/$(TARGET).bin
	pyocd flash -t stm32f103c8 $<

clean:
	rm -rf $(BUILD)
