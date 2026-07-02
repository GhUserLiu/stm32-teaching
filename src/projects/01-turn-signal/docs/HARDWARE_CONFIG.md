# 硬件配置记录

> 创建时间: 2026-05-24
> 开发板: M144Z-M4最小系统板 (STM32F407ZGTx)
> 数据来源: M144Z-M4最小系统板IO引脚分配表——STM32F407.csv

---

## 一、项目引脚配置

### LED 配置

| 功能 | 端口-引脚 | 点亮电平 | 说明 |
|------|-----------|----------|------|
| LED0 | PF9 | 低电平 | 左转向灯 |
| LED1 | PF10 | 低电平 | 右转向灯 |

**说明**: LED为共阳极类型，低电平点亮

---

### 按键配置

| 功能 | 端口-引脚 | 触发电平 | 上拉/下拉 | 说明 |
|------|-----------|----------|-----------|------|
| KEY0 | PE4 | **高电平触发** | 下拉电阻 | 模式切换/BOOT0 |
| KEY_UP | PA0 | 低电平触发 | 上拉电阻 | 双闪开关/WKUP |

---

## 二、当前代码配置 (inc/config.h)

```c
// LED引脚 - 正确 ✅
#define LED0_PIN          GPIO_PIN_9    /* PF9 */
#define LED1_PIN          GPIO_PIN_10   /* PF10 */

// KEY0 - 错误 ❌ (应为高电平触发)
#define KEY0_PIN          GPIO_PIN_4    /* PE4 */
#define KEY0_TRIGGER_HIGH 0             /* 当前: 低电平触发, 应改为: 1 */

// KEY_UP - 正确 ✅
#define KEY_UP_PIN        GPIO_PIN_0    /* PA0 */
#define KEY_UP_TRIGGER_HIGH 0           /* 低电平触发 */
```

---

## 三、需要修改的地方

### 问题：KEY0 触发方式错误

**当前配置**:
```c
#define KEY0_TRIGGER_HIGH 0    // 低电平触发
```

**应改为**:
```c
#define KEY0_TRIGGER_HIGH 1    // 高电平触发
```

---

## 四、程序功能说明

### 4种工作模式

| 模式 | LED0 (PF9) | LED1 (PF10) |
|------|------------|-------------|
| 关闭 | 灭 | 灭 |
| 左转 | 闪烁 | 灭 |
| 右转 | 灭 | 闪烁 |
| 双闪 | 同步闪烁(2倍频) | 同步闪烁(2倍频) |

### 按键功能

| 按键 | 功能 |
|------|------|
| KEY0 | 循环切换: 关闭→左转→右转→双闪→关闭... |
| KEY_UP | 双闪↔记忆模式切换 |

### 记忆模式说明
`previous_mode` 用于记忆进入双闪前的模式。
- 从左转进入双闪，再按双闪键 → 恢复左转
- 从右转进入双闪，再按双闪键 → 恢复右转

---

## 五、时序参数

```c
#define MAIN_LOOP_DELAY   10            // 主循环延时 10ms
#define LED_TOGGLE_COUNT  25            // LED切换计数 (250ms闪烁周期)
#define POWER_ON_BLINK_TIMES  3         // 开机闪烁次数
#define POWER_ON_BLINK_DELAY  300       // 开机闪烁延时 300ms
#define KEY_DEBOUNCE_DELAY   20         // 消抖延时 20ms
```

---

## 六、开发板完整IO资源映射

### GPIOA (16个IO)

| 引脚 | 功能 | 说明 |
|------|------|------|
| PA0 | KEY_UP/WKUP | 双闪按键/唤醒 |
| PA1 | 完全独立 | - |
| PA2 | 完全独立 | - |
| PA3 | 完全独立 | - |
| PA4 | OLED/CAMERA DCMI_HREF | - |
| PA5 | 完全独立 | - |
| PA6 | OLED/CAMERA DCMI_PCLK | - |
| PA7 | 完全独立 | - |
| PA8 | OLED/CAMERA DCMI_XCLK | - |
| PA9 | USART1_TX | CH340C, 跳线帽 |
| PA10 | USART1_RX | CH340C, 跳线帽 |
| PA11 | USB_OTG_FS_DM | - |
| PA12 | USB_OTG_FS_DP | - |
| PA13 | SWDIO | 调试接口 |
| PA14 | SWCLK | 调试接口 |
| PA15 | 完全独立 | - |

### GPIOB (16个IO)

| 引脚 | 功能 | 说明 |
|------|------|------|
| PB0 | TFTLCD T_SCK | - |
| PB1 | TFTLCD T_PEN | - |
| PB2 | TFTLCD T_MISO | - |
| PB3 | SPI1_SCK | SPI Flash, 非完全独立 |
| PB4 | SPI1_MISO | SPI Flash, 非完全独立 |
| PB5 | SPI1_MOSI | SPI Flash, 非完全独立 |
| PB6 | OLED/CAMERA DCMI_D5 | - |
| PB7 | OLED/CAMERA DCMI_VSYNC | - |
| PB8 | I2C1_SCL | EEPROM, 有4.7K上拉 |
| PB9 | I2C1_SDA | EEPROM, 有4.7K上拉 |
| PB10-15 | 完全独立/外设 | 详见下方备注 |

### GPIOC (16个IO)

| 引脚 | 功能 | 说明 |
|------|------|------|
| PC0-5 | 完全独立 | - |
| PC6-11 | OLED/CAMERA/TF卡 | DCMI数据线/SDIO |
| PC12 | TF卡 SDIO_SCK | - |
| PC13 | TFTLCD T_CS | - |
| PC14 | OSC32_IN | 晶振, 不可作普通IO |
| PC15 | OSC32_OUT | 晶振, 不可作普通IO |

### GPIOD (16个IO)

| 引脚 | 功能 | 说明 |
|------|------|------|
| PD0-2 | SRAM/TFTLCD/TF卡 | FSMC/SDIO |
| PD3 | 完全独立 | - |
| PD4-15 | SRAM/TFTLCD FSMC | 非完全独立 |

### GPIOE (16个IO)

| 引脚 | 功能 | 说明 |
|------|------|------|
| PE0-1 | SRAM FSMC_NBL | 非完全独立 |
| PE2-3 | 完全独立 | - |
| PE4 | KEY0/BOOT0 | 模式切换按键 |
| PE5-6 | OLED/CAMERA DCMI | - |
| PE7-15 | SRAM/TFTLCD FSMC | 非完全独立 |

### GPIOF (16个IO)

| 引脚 | 功能 | 说明 |
|------|------|------|
| PF0-5 | SRAM FSMC | 非完全独立 |
| PF6-8 | 完全独立 | - |
| PF9 | LED0 | 左转向灯 |
| PF10 | LED1 | 右转向灯 |
| PF11 | TFTLCD T_MOSI | - |
| PF12-15 | SRAM FSMC | 非完全独立 |

### GPIOG (16个IO)

| 引脚 | 功能 | 说明 |
|------|------|------|
| PG0-5 | SRAM FSMC | 非完全独立 |
| PG6-8 | 完全独立 | - |
| PG9 | OLED/CAMERA DCMI_PWDN | - |
| PG10 | SRAM FSMC_NE3 | 有10K上拉, SRAM片选 |
| PG11 | 完全独立 | - |
| PG12 | TFTLCD FSMC_NE4 | - |
| PG13-15 | 完全独立/CAMERA | - |

### GPIOH (2个IO)

| 引脚 | 功能 | 说明 |
|------|------|------|
| PH0 | OSC_IN | 8MHz晶振, 不可作普通IO |
| PH1 | OSC_OUT | 8MHz晶振, 不可作普通IO |

---

## 七、术语说明

- **完全独立**: 该IO通过一定方法可达到完全悬空效果
- **非完全独立**: 该IO连接了外设，禁用外设后可作普通IO
- **晶振引脚**: PC14/PC15, PH0/PH1 不可作普通IO使用

---

## 八、文件结构

```
src/
├── main.c              # HAL 版本主程序
├── stm32f4xx_hal.c     # HAL 库实现
└── startup_stm32f407xx.s

inc/
├── config.h            # 项目配置 ⚠️ KEY0需修改
└── stm32f4xx_hal.h     # HAL 库头文件
```

---

## 九、LED初始化方式 (✅ 验证成功)

### 方法：Reset_Handler中直接操作寄存器

**原因**: HAL库初始化可能存在问题，直接操作寄存器更可靠

**代码位置**: [main.c:Reset_Handler](../main.c#L204)

```c
/* GPIOF LED寄存器初始化 */
#define RCC_AHB1ENR_ADDR   (*(volatile uint32_t*)0x40023830)
#define GPIOF_MODER_ADDR   (*(volatile uint32_t*)0x40021400)
#define GPIOF_ODR_ADDR     (*(volatile uint32_t*)0x40021414)

// 1. 使能GPIOF时钟 (AHB1ENR bit 5)
RCC_AHB1ENR_ADDR |= (1U << 5);

// 2. 配置PF9和PF10为输出模式
GPIOF_MODER_ADDR &= ~(0x3U << (9 * 2));   // 清除PF9模式位
GPIOF_MODER_ADDR |= (0x1U << (9 * 2));     // PF9 = 输出
GPIOF_MODER_ADDR &= ~(0x3U << (10 * 2));  // 清除PF10模式位
GPIOF_MODER_ADDR |= (0x1U << (10 * 2));    // PF10 = 输出

// 3. 初始LED状态：灭（高电平）
GPIOF_ODR_ADDR |= (1U << 9);   // PF9 = 1
GPIOF_ODR_ADDR |= (1U << 10);  // PF10 = 1
```

### LED控制宏定义

```c
/* 低电平点亮 */
#define LED_ON(state)     ((state) ? GPIO_PIN_SET : GPIO_PIN_RESET)
#define LED_OFF(state)    ((state) ? GPIO_PIN_RESET : GPIO_PIN_SET)
```

---

## 十、修改记录

| 日期 | 修改内容 |
|------|----------|
| 2026-05-24 | 创建HAL版本，识别KEY0触发方式错误 |
| 2026-05-24 | 合并board.h完整IO映射，删除冗余文件 |
| 2026-05-24 | **LED点亮验证成功：使用寄存器直接操作方式** |
| 2026-05-24 | 创建故障排查日志 [TROUBLESHOOTING_LOG.md](../../docs/TROUBLESHOOTING_LOG.md) |

---

## 十一、常见问题

### Q1: LED不亮怎么办？
**A**: 参考 [TROUBLESHOOTING_LOG.md](../../docs/TROUBLESHOOTING_LOG.md) 中的错误记录#1

### Q2: 如何验证编译是否成功？
**A**: 使用以下命令：
```bash
# 检查文件大小
ls -la build/01-turn-signal/Debug/01-turn-signal.*

# 反汇编检查
arm-none-eabi-objdump -d build/01-turn-signal/Debug/01-turn-signal.elf | grep -A 30 "<Reset_Handler>"
```

### Q3: 两个项目文件的hex文件名相同怎么办？
**A**: Makefile已更新，现在生成项目命名的hex文件：
```
build/01-turn-signal/Debug/01-turn-signal.hex
```
