/**
 * @file    board_f1.h
 * @brief   野火小智 STM32F103C8T6 核心板【初款】实训套件引脚分配（板级支持包）
 * @author  刘兆骐（汽车工程学院单片机课程组）
 *
 * ⚠ 板型基准：见 docs/teaching/板卡档案.md（实物=初款；官方资料多为双USB款，
 *   IO 定义两版一致，板载串口部分不适用）。改引脚必须同步该档案。
 * ⚠ 封装限制：C8T6/LQFP48 的 C 口仅 PC13~PC15（PC0~PC12 不存在）。
 *
 * 引脚分配依据（官方《[野火小智]STM32F103C8核心板_双USB款_引脚分配表》）：
 *   LED      板载 RGB：LED_R=PA1 LED_G=PA2 LED_B=PA3（本框架默认用红 PA1）
 *   KEY      板载 KEY1=PA0（低电平按下）；KEY2=PC13 备用（进阶可用）
 *   BUZZER   PB5   高电平响（有源蜂鸣器模块）
 *           （注意：C8T6/LQFP48 的 C 口只有 PC13~PC15——PC0~PC12 物理不存在，
 *            早期方案的 PC2 因此作废，2026-10 实物核对后改 PB5）
 *   DHT11    PB12  单总线（对齐官方例程 [29]）
 *   OLED     SCL=PB6 SDA=PB7（软件 I2C，0.96 寸 SSD1306 4Pin；与官方 [31] 同脚）
 *   光敏     PA4   ADC1_IN4（对齐官方例程 [21-2] Light_AO=PA4）
 *   热敏     PA6   ADC1_IN6（对齐官方例程 [21-2] Hot_AO=PA6）
 *   MQ-135   PA5   ADC1_IN5（备用件：空气质量/烟雾；未接时应用层须关宏）
 *            （官方例程 [21-2] 的 Ir_AO 也用 PA5，互斥使用）
 *   TB6612   AIN1=PB0  AIN2=PB1  PWMA=PA8（TIM1_CH1；官方 [26] 用 PA4/5/7 与光敏冲突，故本框架另行分配，STBY 直拉 3.3V）
 *   UART1    PA9(TX) PA10(RX) 115200-8N1（外接 CH340 USB 转 TTL 线：
 *            线的 RXD→PA9、TXD→PA10、GND→GND；初款核心板无板载串口）
 */
#ifndef BOARD_F1_H
#define BOARD_F1_H

#include "stm32f103x_min.h"

/* ---- LED（板载 RGB，本框架默认驱动红色脚 PA1） ----
 * RGB 三脚：LED_R=PA1 LED_G=PA2 LED_B=PA3；进阶可三脚齐驱做彩色氛围灯。
 * 极性默认低电平点亮（共阳接 3.3V）；若实测相反，把 LED_ACTIVE_LOW 改 0。 */
#define LED_PORT   GPIOA
#define LED_PIN    1
#define LED_ACTIVE_LOW 1

/* RGB 其余两脚（进阶用） */
#define LED_G_PORT  GPIOA
#define LED_G_PIN   2
#define LED_B_PORT  GPIOA
#define LED_B_PIN   3

static inline void board_led_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPA;
    gpio_init(LED_PORT, LED_PIN, GPIO_MODE_OUT_PP_2);
#if LED_ACTIVE_LOW
    gpio_set(LED_PORT, LED_PIN);            /* 默认灭（低亮极性） */
#else
    gpio_reset(LED_PORT, LED_PIN);
#endif
}
static inline void board_led(int on)
{
#if LED_ACTIVE_LOW
    gpio_write(LED_PORT, LED_PIN, on ? 0 : 1);
#else
    gpio_write(LED_PORT, LED_PIN, on ? 1 : 0);
#endif
}

/* ---- 按键（板载 KEY1=PA0，低电平有效；KEY2=PC13 备用） ---- */
#define KEY_PORT   GPIOA
#define KEY_PIN    0

static inline void board_key_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPA;
    gpio_init(KEY_PORT, KEY_PIN, GPIO_MODE_IN_PUPD);
    gpio_set(KEY_PORT, KEY_PIN);          /* ODR=1 → 上拉 */
}
static inline int board_key_pressed(void)  /* 1=按下 */
{
    return !gpio_read(KEY_PORT, KEY_PIN);
}

/* ---- 蜂鸣器（有源，高电平响；PB5——C8T6 无 PC0~PC12） ---- */
#define BUZZER_PORT  GPIOB
#define BUZZER_PIN   5

static inline void board_buzzer_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPB;
    gpio_init(BUZZER_PORT, BUZZER_PIN, GPIO_MODE_OUT_PP_2);
    gpio_reset(BUZZER_PORT, BUZZER_PIN);
}
static inline void board_buzzer(int on)
{
    gpio_write(BUZZER_PORT, BUZZER_PIN, on);
}

/* ---- DHT11（PB12，对齐官方例程 [29]） ---- */
#define DHT11_PORT  GPIOB
#define DHT11_PIN   12

/* ---- OLED 软件 I2C ---- */
#define OLED_SCL_PORT  GPIOB
#define OLED_SCL_PIN   6
#define OLED_SDA_PORT  GPIOB
#define OLED_SDA_PIN   7

/* ---- ADC 通道（对齐官方例程 [21-2]） ----
 * 板载资源占用：PA0=KEY1、PA1/2/3=RGB LED，故模拟输入用 PA4/PA6。
 * 光敏 PA4（ADC1_IN4），热敏 PA6（ADC1_IN6）；PA5 留给反射传感器（官方 Ir_AO）。 */
#define ADC_CH_LIGHT   4    /* PA4 光敏 */
#define ADC_CH_NTC     6    /* PA6 热敏 */
#define ADC_CH_MQ135   5    /* PA5 MQ-135 空气质量/烟雾（备用件） */
static inline void board_adc_pins_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPA;
    gpio_init(GPIOA, 4, GPIO_MODE_IN_ANALOG);
    gpio_init(GPIOA, 6, GPIO_MODE_IN_ANALOG);
    gpio_init(GPIOA, 5, GPIO_MODE_IN_ANALOG);
}

/* ---- TB6612 电机驱动 ---- */
#define TB6612_AIN1_PORT  GPIOB
#define TB6612_AIN1_PIN   0
#define TB6612_AIN2_PORT  GPIOB
#define TB6612_AIN2_PIN   1
#define TB6612_PWMA_PORT  GPIOA   /* PA8 = TIM1_CH1 */
#define TB6612_PWMA_PIN   8

/* ---- UART1 ---- */
static inline void board_uart1_init(uint32_t baud)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPA | RCC_APB2ENR_USART1;
    gpio_init(GPIOA, 9, GPIO_MODE_AF_PP_50);    /* TX */
    gpio_init(GPIOA, 10, GPIO_MODE_IN_FLOAT);   /* RX */
    uart1_init(baud);
}

#endif /* BOARD_F1_H */
