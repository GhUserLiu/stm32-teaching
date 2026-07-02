/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : STM32F407 转向灯 - HAL库版本（安全增强版）
  *                 LED: 共阳极，低电平点亮
  *                 改进：使用非阻塞消抖
  ******************************************************************************
  */

#include <stdint.h>
#include "stm32f4xx_hal.h"
#include "board.h"
#include "config.h"
#include "debounce.h"

/* ========== 模式定义 ========== */
typedef enum {
    MODE_OFF = 0,
    MODE_LEFT,
    MODE_RIGHT,
    MODE_HAZARD
} LightMode;

volatile LightMode light_mode = MODE_OFF;
volatile LightMode previous_mode = MODE_OFF;
volatile uint8_t led0_state = 1;  /* 1=灭, 0=亮（低电平点亮） */
volatile uint8_t led1_state = 1;
volatile uint32_t toggle_counter = 0;

/* ========== 按键状态变量（非阻塞消抖） ========== */
static KeyState_t key0_state;
static KeyState_t key_up_state;

/* ========== HAL初始化 ========== */
void SystemClock_Config(void)
{
  /* 使用默认HSI时钟，暂不配置PLL */
}

/* ========== GPIO初始化（HAL库） ========== */
void GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    /* 配置KEY_UP引脚 */
    GPIO_InitStruct.Pin = BOARD_KEY_UP_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = KEY_PULL(KEY_UP_TRIGGER_HIGH);
    HAL_GPIO_Init(BOARD_KEY_UP_PORT, &GPIO_InitStruct);

    /* 配置KEY0引脚 */
    GPIO_InitStruct.Pin = BOARD_KEY0_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = KEY_PULL(KEY0_TRIGGER_HIGH);
    HAL_GPIO_Init(BOARD_KEY0_PORT, &GPIO_InitStruct);
}

/* ========== 读取按键状态 ========== */
uint8_t Read_KEY0(void)
{
    GPIO_PinState pin_state = HAL_GPIO_ReadPin(BOARD_KEY0_PORT, BOARD_KEY0_PIN);
    return KEY0_TRIGGER_HIGH ? pin_state : !pin_state;
}

uint8_t Read_KEY_UP(void)
{
    GPIO_PinState pin_state = HAL_GPIO_ReadPin(BOARD_KEY_UP_PORT, BOARD_KEY_UP_PIN);
    return KEY_UP_TRIGGER_HIGH ? pin_state : !pin_state;
}

/* ========== 按键扫描（非阻塞版本） ========== */
void Key_Init_All(void)
{
    /* 初始化按键消抖状态 */
    Key_Init(&key0_state);
    Key_Init(&key_up_state);
}

void Key_Scan(void)
{
    /**
     * @brief 按键扫描（非阻塞消抖版本）
     *
     * 改进说明:
     * - 移除HAL_Delay阻塞调用
     * - 使用状态机消抖（debounce模块）
     * - 系统响应性更好，不影响LED闪烁
     */
    uint8_t key0_now, key_up_now;

    key0_now = Read_KEY0();
    key_up_now = Read_KEY_UP();

    /* 更新消抖状态 */
    Key_Update(&key0_state, key0_now);
    Key_Update(&key_up_state, key_up_now);

    /* 处理KEY0按下事件（消抖后） */
    if (Key_IsPressed(&key0_state)) {
        light_mode = (LightMode)((light_mode + 1) % 4);
        if (light_mode != MODE_HAZARD)
            previous_mode = light_mode;
        toggle_counter = 0;
    }

    /* 处理KEY_UP按下事件（消抖后）- 记忆模式↔HAZARD切换 */
    if (Key_IsPressed(&key_up_state)) {
        if (light_mode == MODE_HAZARD)
            light_mode = previous_mode;
        else {
            previous_mode = light_mode;
            light_mode = MODE_HAZARD;
        }
        toggle_counter = 0;
    }
}

/* ========== 更新LED显示 ========== */
void LED_Update(void)
{
    /* 双闪模式频率是普通模式的2倍 */
    uint16_t interval = (light_mode == MODE_HAZARD) ?
                        (LED_TOGGLE_COUNT / 2) : LED_TOGGLE_COUNT;
    toggle_counter++;

    if (toggle_counter >= interval)
    {
        toggle_counter = 0;

        switch(light_mode)
        {
            case MODE_LEFT:
                led0_state = !led0_state;
                led1_state = 1;
                break;

            case MODE_RIGHT:
                led1_state = !led1_state;
                led0_state = 1;
                break;

            case MODE_HAZARD:
                led0_state = !led0_state;
                led1_state = led0_state;
                break;

            default:
                led0_state = 1;
                led1_state = 1;
                break;
        }
    }

    /* 输出LED（低电平点亮：led_state=0时亮，led_state=1时灭） */
    HAL_GPIO_WritePin(BOARD_LED0_PORT, BOARD_LED0_PIN, led0_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(BOARD_LED1_PORT, BOARD_LED1_PIN, led1_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

/* ========== 外部变量 ========== */
extern uint32_t _estack;
extern uint32_t _sidata, _sdata, _edata;
extern uint32_t _sbss, _ebss;

/* ========== 主函数 ========== */
int main(void)
{
    /* HAL初始化 */
    HAL_Init();
    SystemClock_Config();

    /* GPIO初始化（按键部分由HAL初始化，LED已在Reset_Handler中初始化） */
    GPIO_Init();

    /* 按键消抖初始化 */
    Key_Init_All();

    /* 主循环（非阻塞） */
    while (1)
    {
        Key_Scan();
        LED_Update();

        /* 注意：移除了HAL_Delay以实现非阻塞循环
         * LED闪烁频率由LED_Update()内部的计数器控制
         * 主循环以CPU速度运行，确保按键响应及时
         */
    }

    return 0;
}

/* ========== 寄存器地址定义 ========== */
#define RCC_AHB1ENR_ADDR   (*(volatile uint32_t*)0x40023830)
#define GPIOF_BASE         0x40021400
#define GPIOF_MODER_ADDR   (*(volatile uint32_t*)(GPIOF_BASE + 0x00))
#define GPIOF_ODR_ADDR     (*(volatile uint32_t*)(GPIOF_BASE + 0x14))

/* ========== Reset_Handler - 直接操作寄存器初始化LED ========== */
void Reset_Handler(void)
{
    uint32_t *src, *dst;

    /* 设置栈指针 */
    __asm volatile("ldr sp, =_estack");

    /* 复制data段 */
    src = &_sidata;
    dst = &_sdata;
    while (dst < &_edata)
        *dst++ = *src++;

    /* 清零bss段 */
    dst = &_sbss;
    while (dst < &_ebss)
        *dst++ = 0;

    /* ========== GPIOF LED寄存器初始化（成功测试版本） ========== */
    /* 1. 使能GPIOF时钟 (AHB1ENR bit 5) */
    RCC_AHB1ENR_ADDR |= (1U << 5);

    /* 2. 配置PF9和PF10为输出模式 */
    GPIOF_MODER_ADDR &= ~(0x3U << (9 * 2));   // 清除PF9模式位
    GPIOF_MODER_ADDR |= (0x1U << (9 * 2));     // 设置PF9为通用输出
    GPIOF_MODER_ADDR &= ~(0x3U << (10 * 2));  // 清除PF10模式位
    GPIOF_MODER_ADDR |= (0x1U << (10 * 2));    // 设置PF10为通用输出

    /* 3. 初始LED状态：灭（高电平） */
    GPIOF_ODR_ADDR |= (1U << 9);   // PF9 = 1
    GPIOF_ODR_ADDR |= (1U << 10);  // PF10 = 1

    /* 调用主函数 */
    main();

    while (1)
    {
        /* 不应该到达这里 */
    }
}

/* ========== 异常处理 ========== */
void NMI_Handler(void)        { while (1); }
void HardFault_Handler(void)  { while (1); }
void MemManage_Handler(void)  { while (1); }
void BusFault_Handler(void)   { while (1); }
void UsageFault_Handler(void) { while (1); }
void SVC_Handler(void)        { while (1); }
void DebugMon_Handler(void)   { while (1); }
void PendSV_Handler(void)     { while (1); }
