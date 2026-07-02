# Test6 完整中断版本实现指南

本文档提供两种方法实现Test6的完整中断功能（KEY_UP可打断KEY0）。

---

## 方法一：使用扩展版HAL库 ⭐ 推荐（教学用）

### 1. 文件结构

扩展版HAL库已创建，包含以下文件：

```
common/hal/
├── stm32f4xx_hal.h        # 原简化版HAL库
├── stm32f4xx_hal.c        # 原简化版实现
├── stm32f4xx_hal_ext.h    # 🆕 扩展版头文件（RCC、EXTI、NVIC）
└── stm32f4xx_hal_ext.c    # 🆕 扩展版实现
```

### 2. 使用方法

在 `main.c` 中添加扩展头文件：

```c
#include "stm32f4xx_hal.h"
#include "stm32f4xx_hal_ext.h"  // 🆕 添加这行
#include "board.h"
#include "config.h"
```

### 3. 中断版本代码示例

```c
/* ========== 中断回调函数 ========== */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == BOARD_KEY0_PIN)
    {
        /* KEY0中断: 循环切换模式 */
        light_mode = (LightMode)((light_mode + 1) % 4);
        if (light_mode != MODE_HAZARD)
            previous_mode = light_mode;
        last_toggle_time = HAL_GetTick();
    }
    else if (GPIO_Pin == BOARD_KEY_UP_PIN)
    {
        /* KEY_UP中断: 切换双闪模式（高优先级） */
        if (light_mode == MODE_HAZARD)
            light_mode = previous_mode;
        else
        {
            previous_mode = light_mode;
            light_mode = MODE_HAZARD;
        }
        last_toggle_time = HAL_GetTick();
    }
}
```

### 4. GPIO中断初始化

```c
void GPIO_Init_WithEXTI(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    /* 使能SYSCFG时钟（EXTI需要） */
    __HAL_RCC_SYSCFG_CLK_ENABLE();

    /* 配置LED引脚 */
    GPIO_InitStruct.Pin = BOARD_LED0_PIN | BOARD_LED1_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(BOARD_LED0_PORT, &GPIO_InitStruct);

    /* 初始状态: 灭 */
    HAL_GPIO_WritePin(BOARD_LED0_PORT, BOARD_LED0_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(BOARD_LED1_PORT, BOARD_LED1_PIN, GPIO_PIN_SET);

    /* 配置KEY0 (PE4) 为外部中断 */
    GPIO_InitStruct.Pin = BOARD_KEY0_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;  // 上升沿触发
    GPIO_InitStruct.Pull = GPIO_PULLDOWN;         // 下拉
    HAL_GPIO_Init(BOARD_KEY0_PORT, &GPIO_InitStruct);

    /* 配置KEY_UP (PA0) 为外部中断 */
    GPIO_InitStruct.Pin = BOARD_KEY_UP_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;  // 上升沿触发
    GPIO_InitStruct.Pull = GPIO_PULLDOWN;         // 下拉
    HAL_GPIO_Init(BOARD_KEY_UP_PORT, &GPIO_InitStruct);

    /* 配置SYSCFG外部中断线 */
    /* PA0 -> EXTI0 */
    SYSCFG->EXTICR[0] &= ~SYSCFG_EXTICR1_EXTI0;
    SYSCFG->EXTICR[0] |= SYSCFG_EXTI_PORTA;

    /* PE4 -> EXTI4 */
    SYSCFG->EXTICR[1] &= ~SYSCFG_EXTICR2_EXTI4;
    SYSCFG->EXTICR[1] |= SYSCFG_EXTI_PORTE;

    /* 配置NVIC中断优先级 */
    HAL_NVIC_SetPriority(EXTI0_IRQn, 0, 0);  // KEY_UP - 最高优先级
    HAL_NVIC_EnableIRQ(EXTI0_IRQn);

    HAL_NVIC_SetPriority(EXTI4_IRQn, 1, 0);  // KEY0 - 较低优先级
    HAL_NVIC_EnableIRQ(EXTI4_IRQn);
}
```

### 5. 中断处理函数

```c
/* EXTI0中断处理函数 (KEY_UP - PA0) */
void EXTI0_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BOARD_KEY_UP_PIN);
}

/* EXTI4中断处理函数 (KEY0 - PE4) */
void EXTI4_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BOARD_KEY0_PIN);
}
```

### 6. 时钟配置

```c
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    /* 配置电压缩放 */
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

    /* 配置HSE振荡器 (8MHz晶振) */
    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    RCC_OscInitStruct.HSEState = RCC_HSE_ON;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLM = 8;       // 8MHz晶振
    RCC_OscInitStruct.PLL.PLLN = 336;     // 倍频到336MHz
    RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;  // 分频到168MHz
    RCC_OscInitStruct.PLL.PLLQ = 4;

    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        Error_Handler();
    }

    /* 配置系统时钟 */
    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                                | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
    {
        Error_Handler();
    }
}
```

### 7. 主循环（非阻塞版本）

```c
int main(void)
{
    HAL_Init();
    SystemClock_Config();
    GPIO_Init_WithEXTI();

    /* 主循环 - 只更新LED */
    while (1)
    {
        update_lighting();
        HAL_Delay(MAIN_LOOP_DELAY);
    }
}
```

---

## 方法二：使用STM32CubeMX生成完整框架 ⭐⭐ 工业标准

### 1. 安装STM32CubeMX

- 下载地址: https://www.st.com/zh/development-tools/stm32cubemx.html
- 需要注册ST账号

### 2. 创建新项目

#### 步骤1：选择芯片
```
1. 打开STM32CubeMX
2. 点击 "New Project"
3. 在搜索框输入 "STM32F407ZGT6"
4. 双击选中芯片
```

#### 步骤2：配置RCC（时钟源）
```
1. 左侧 Categories → RCC
2. High Speed Clock (HSE): Crystal/Ceramic Resonator
3. Low Speed Clock (LSE): Disable（可选）
```

#### 步骤3：配置GPIO引脚
```
芯片引脚图上操作：

LED相关:
- 点击 PF9 → GPIO_Output → 标签名改为 "LED0"
- 点击 PF10 → GPIO_Output → 标签名改为 "LED1"

按键相关（外部中断）:
- 点击 PE4 → GPIO_EXTI4 → 标签名改为 "KEY0"
- 点击 PA0 → GPIO_EXTI0 → 标签名改为 "KEY_UP"
```

#### 步骤4：配置GPIO参数
```
左侧 Categories → GPIO

对于LED引脚:
- GPIO output level: High (初始熄灭)
- Mode: Output Push Pull
- Pull-up and Pull-down: No pull-up and no pull-down
- Maximum output speed: Low

对于按键引脚:
- GPIO mode: External Interrupt Mode with Rising edge trigger detection
- Pull-up and Pull-down: No pull-up and no pull-down (根据硬件电路调整)
```

#### 步骤5：配置NVIC（中断优先级）
```
左侧 Categories → NVIC

勾选并设置:
☑ EXTI line0 interrupt (KEY_UP)
  - Preemption Priority: 0 (最高)
  - Sub Priority: 0

☑ EXTI line4 interrupt (KEY0)
  - Preemption Priority: 1 (较低)
  - Sub Priority: 0
```

#### 步骤6：配置USART1（可选，用于串口调试）
```
左侧 Categories → Connectivity → USART1

Mode: Asynchronous

Parameter Settings:
- Baud Rate: 115200
- Word Length: 8 Bits
- Parity: None
- Stop Bits: 1
```

#### 步骤7：配置时钟树
```
点击顶部 "Clock Configuration" 选项卡

配置步骤:
1. 选择 HSE 作为PLL源 (输入框填 8 MHz)
2. PLLM = 8 (PLLM分频系数)
3. PLLN = 336 (PLLN倍频系数)
4. PLLP = /2 (PLLP分频系数)
5. System Clock = PLLCLK
6. 确认 HCLK = 168 MHz, APB1 = 42 MHz, APB2 = 84 MHz
```

#### 步骤8：生成代码
```
点击顶部 "Project Manager" 选项卡

Project Settings:
- Project Name: Test6_CubeMX
- Project Location: 选择路径
- Toolchain / IDE: MDK-ARM V5 (或 SW4STM32)

Code Generator Settings:
☑ Generate peripheral initialization as a pair of '.c/.h' files per peripheral
☑ Delete previously generated files when not re-generated

点击右上角 "GENERATE CODE" 按钮
```

### 3. 在生成的代码中添加用户代码

打开生成的 `main.c`，在 `/* USER CODE BEGIN ... */` 区域添加代码：

#### 在 USER CODE BEGIN 0 中添加：

```c
/* USER CODE BEGIN 0 */
#include <stdio.h>

typedef enum {
    MODE_OFF = 0,
    MODE_LEFT,
    MODE_RIGHT,
    MODE_HAZARD
} LightMode;

volatile LightMode light_mode = MODE_OFF;
volatile LightMode previous_mode = MODE_OFF;
volatile uint32_t last_toggle_time = 0;
volatile uint8_t led0_state = 1;
volatile uint8_t led1_state = 1;

void print_mode(LightMode mode)
{
    switch(mode) {
        case MODE_OFF: printf("当前模式：关闭\r\n"); break;
        case MODE_LEFT: printf("当前模式：左转\r\n"); break;
        case MODE_RIGHT: printf("当前模式：右转\r\n"); break;
        case MODE_HAZARD: printf("当前模式：双闪\r\n"); break;
        default: break;
    }
}

void update_lighting(void)
{
    uint32_t now = HAL_GetTick();
    uint16_t interval = (light_mode == MODE_HAZARD) ? 250 : 500;

    if (now - last_toggle_time >= interval) {
        last_toggle_time = now;
        switch(light_mode) {
            case MODE_LEFT:
                led0_state = !led0_state;
                HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, led0_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
                HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, GPIO_PIN_SET);
                break;
            case MODE_RIGHT:
                led1_state = !led1_state;
                HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, led1_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
                HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, GPIO_PIN_SET);
                break;
            case MODE_HAZARD:
                led0_state = !led0_state;
                led1_state = led0_state;
                HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, led0_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
                HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, led1_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
                break;
            default:
                HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, GPIO_PIN_SET);
                HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, GPIO_PIN_SET);
                break;
        }
    }
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == KEY0_Pin) {
        light_mode = (LightMode)((light_mode + 1) % 4);
        if (light_mode != MODE_HAZARD) previous_mode = light_mode;
        print_mode(light_mode);
        last_toggle_time = HAL_GetTick();
    }
    else if (GPIO_Pin == KEY_UP_Pin) {
        if (light_mode == MODE_HAZARD) light_mode = previous_mode;
        else {
            previous_mode = light_mode;
            light_mode = MODE_HAZARD;
        }
        print_mode(light_mode);
        last_toggle_time = HAL_GetTick();
    }
}

/* printf重定向 */
int fputc(int ch, FILE *f)
{
    HAL_UART_Transmit(&huart1, (uint8_t *)&ch, 1, HAL_MAX_DELAY);
    return ch;
}
/* USER CODE END 0 */
```

#### 在 USER CODE BEGIN WHILE 中添加：

```c
/* USER CODE BEGIN WHILE */
while (1)
{
    update_lighting();
    HAL_Delay(10);
}
/* USER CODE END WHILE */
```

### 4. 编译和烧录

```bash
# 如果使用Keil MDK
1. 打开生成的 .uvprojx 文件
2. 按 F7 编译
3. 使用 ST-Link 下载

# 如果使用SW4STM32
1. 打开生成的 .cproject 文件
2. 右键项目 → Build Project
3. 使用 Run → Debug 下载
```

---

## 两种方法对比

| 特性 | 扩展HAL库 | STM32CubeMX |
|------|-----------|-------------|
| 学习难度 | 中等 | 低（图形界面） |
| 灵活性 | 高 | 中 |
| 代码量 | 少 | 多（自动生成） |
| 工业标准 | 否 | ✅ 是 |
| 适合教学 | ✅ 是 | ✅ 是 |
| 移植性 | 高 | 低（依赖CubeMX） |

---

## 常见问题

### Q1: 中断优先级如何理解？
- **抢占优先级** (Preemption Priority): 数值越小，优先级越高。高优先级可以打断低优先级的中断。
- **子优先级** (Sub Priority): 当抢占优先级相同时，子优先级决定执行顺序。

### Q2: 为什么KEY_UP可以打断KEY0？
因为KEY_UP配置为抢占优先级0，KEY0配置为抢占优先级1。当KEY_UP按下时，即使KEY0正在处理，也会被KEY_UP打断。

### Q3: 如何验证中断优先级是否生效？
```c
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    /* 添加延时，模拟长时间处理 */
    if (GPIO_Pin == KEY0_Pin) {
        HAL_Delay(1000);  // 延时1秒
    }
    /* 在延时期间按KEY_UP，如果立即响应说明优先级配置正确 */
}
```

### Q4: 时钟配置失败怎么办？
- 检查外部晶振是否为8MHz
- 检查BOOT跳线是否正确
- 使用内部HSI时钟测试：`RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;`
