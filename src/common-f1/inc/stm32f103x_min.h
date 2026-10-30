/**
 * @file    stm32f103x_min.h
 * @brief   STM32F103x8/xB 最小寄存器定义（自包含，无外部依赖）
 *
 * 面向《新能源汽车工程实训（电子控制方向）》STM32F103C8T6 套件。
 * 仅覆盖实训所需外设：RCC / GPIO / USART1 / TIM1 / TIM2~4 /
 * ADC1 / I2C1 / EXTI / SysTick / NVIC / SCB / FLASH(等待周期) / AFIO。
 *
 * 写法约定：全部 volatile 直访结构体，偏移依据 RM0008 Reference Manual。
 */
#ifndef STM32F103X_MIN_H
#define STM32F103X_MIN_H

#include <stdint.h>

/* CPU 主频（MHz）——delay/uart/timer 统一引用；HSI 调试=8，PLL 修复后改 72 */
#define F1_CPU_FREQ_MHZ  8

/* ------------------------------------------------------------------ */
/* 基址                                                               */
/* ------------------------------------------------------------------ */
#define PERIPH_BASE      0x40000000u
#define APB2PERIPH_BASE  (PERIPH_BASE + 0x00000u)
#define APB1PERIPH_BASE  (PERIPH_BASE + 0x10000u)
#define AHBPERIPH_BASE   (PERIPH_BASE + 0x20000u)

/* ------------------------------------------------------------------ */
/* Cortex-M3 核心外设（SCB / NVIC / SysTick）                          */
/* ------------------------------------------------------------------ */
typedef struct {
    volatile uint32_t ISER[8];
    uint32_t _r0[24];
    volatile uint32_t ICER[8];
    uint32_t _r1[24];
    volatile uint32_t ISPR[8];
    uint32_t _r2[24];
    volatile uint32_t ICPR[8];
    uint32_t _r3[24];
    volatile uint32_t IABR[8];
    uint32_t _r4[56];
    volatile uint8_t  IP[240];
    uint32_t _r5[644];
} NVIC_Type;

typedef struct {
    volatile uint32_t CPUID;
    volatile uint32_t ICSR;
    volatile uint32_t VTOR;
    volatile uint32_t AIRCR;
    volatile uint32_t SCR;
    volatile uint32_t CCR;
    volatile uint8_t  SHPR[12];
    volatile uint32_t SHCSR;
    volatile uint32_t CFSR;
    volatile uint32_t HFSR;
    volatile uint32_t DFSR;
    volatile uint32_t MMFAR;
    volatile uint32_t BFAR;
} SCB_Type;

typedef struct {
    volatile uint32_t CTRL;
    volatile uint32_t LOAD;
    volatile uint32_t VAL;
    volatile uint32_t CALIB;
} SysTick_Type;

#define SCS_BASE      (PERIPH_BASE + 0xE000EuL)
#define SysTick_BASE  (SCS_BASE + 0x0010u)
#define NVIC_BASE     (SCS_BASE + 0x0100u)
#define SCB_BASE      (SCS_BASE + 0x0D00u)

#define SCB      ((SCB_Type *)   SCB_BASE)
#define NVIC_    ((NVIC_Type *)  NVIC_BASE)
#define SysTick  ((SysTick_Type *)SysTick_BASE)

/* SysTick CTRL 位 */
#define SysTick_CTRL_ENABLE_Pos    0u
#define SysTick_CTRL_TICKINT_Pos   1u
#define SysTick_CTRL_CLKSOURCE_Pos 2u
#define SysTick_CTRL_COUNTFLAG_Pos 16u

/* AIRCR 解锁键 */
#define SCB_AIRCR_VECTKEY     0x05FA0000u
#define SCB_AIRCR_SYSRESETREQ (1u << 2)

/* NVIC 使能（IRQn 从 0 起） */
static inline void nvic_enable_irq(int irqn)
{
    NVIC_->ISER[irqn >> 5] = (1u << (irqn & 0x1F));
}
static inline void nvic_set_priority(int irqn, uint8_t prio)
{
    NVIC_->IP[irqn] = prio << 4;   /* 高 4 位有效 */
}

/* ------------------------------------------------------------------ */
/* RCC                                                                 */
/* ------------------------------------------------------------------ */
typedef struct {
    volatile uint32_t CR;       /* 0x00 */
    volatile uint32_t CFGR;     /* 0x04 */
    volatile uint32_t CIR;      /* 0x08 */
    volatile uint32_t APB2RSTR; /* 0x0C */
    volatile uint32_t APB1RSTR; /* 0x10 */
    volatile uint32_t AHBENR;   /* 0x14 */
    volatile uint32_t APB2ENR;  /* 0x18 */
    volatile uint32_t APB1ENR;  /* 0x1C */
    volatile uint32_t BDCR;     /* 0x20 */
    volatile uint32_t CSR;      /* 0x24 */
} RCC_Type;

#define RCC_BASE  (AHBPERIPH_BASE + 0x1000u)
#define RCC       ((RCC_Type *)RCC_BASE)

/* RCC_CR 位 */
#define RCC_CR_HSION   (1u << 0)
#define RCC_CR_HSIRDY  (1u << 1)
#define RCC_CR_HSEON   (1u << 16)
#define RCC_CR_HSERDY  (1u << 17)
#define RCC_CR_PLLON   (1u << 24)
#define RCC_CR_PLLRDY  (1u << 25)

/* RCC_CFGR */
#define RCC_CFGR_SW_PLL        0x00000002u
#define RCC_CFGR_SWS_PLL       0x00000008u
#define RCC_CFGR_HPRE_DIV1     0u
#define RCC_CFGR_PPRE1_DIV2    (0x4u << 8)
#define RCC_CFGR_PPRE2_DIV1    0u
#define RCC_CFGR_PLLSRC_HSE    (1u << 16)
#define RCC_CFGR_PLLXTPRE_HSE  (0u << 17)
#define RCC_CFGR_PLLMUL9       (0x7u << 18)
#define RCC_CFGR_ADCPRE_DIV6   (0x4u << 14)   /* 72/6 = 12MHz */

/* AHBENR */
#define RCC_AHBENR_DMA1   (1u << 0)

/* APB2ENR */
#define RCC_APB2ENR_AFIO   (1u << 0)
#define RCC_APB2ENR_IOPA   (1u << 2)
#define RCC_APB2ENR_IOPB   (1u << 3)
#define RCC_APB2ENR_IOPC   (1u << 4)
#define RCC_APB2ENR_IOPD   (1u << 5)
#define RCC_APB2ENR_ADC1   (1u << 9)
#define RCC_APB2ENR_TIM1   (1u << 11)
#define RCC_APB2ENR_USART1 (1u << 14)

/* APB1ENR */
#define RCC_APB1ENR_TIM2   (1u << 0)
#define RCC_APB1ENR_TIM3   (1u << 1)
#define RCC_APB1ENR_TIM4   (1u << 2)
#define RCC_APB1ENR_I2C1   (1u << 21)

/* ------------------------------------------------------------------ */
/* FLASH（等待周期）                                                    */
/* ------------------------------------------------------------------ */
typedef struct {
    volatile uint32_t ACR;
    volatile uint32_t KEYR;
    volatile uint32_t OPTKEYR;
    volatile uint32_t SR;
    volatile uint32_t CR;
    volatile uint32_t AR;
    volatile uint32_t RESERVED;
    volatile uint32_t OBR;
    volatile uint32_t WRPR;
} FLASH_Type;

#define FLASH_BASE (AHBPERIPH_BASE + 0x0000u)
#define FLASH      ((FLASH_Type *)FLASH_BASE)
#define FLASH_AIRCR_UNUSED  /* 占位删除用，勿引用 */
#define FLASH_ACR_PRFTBE    (1u << 4)
#define FLASH_ACR_LATENCY_2 (2u)

/* ------------------------------------------------------------------ */
/* GPIO                                                               */
/* ------------------------------------------------------------------ */
typedef struct {
    volatile uint32_t CRL;  /* 0x00 配置低 8 位引脚 */
    volatile uint32_t CRH;  /* 0x04 配置高 8 位引脚 */
    volatile uint32_t IDR;  /* 0x08 输入数据 */
    volatile uint32_t ODR;  /* 0x0C 输出数据 */
    volatile uint32_t BSRR; /* 0x10 置位/复位 */
    volatile uint32_t BRR;  /* 0x14 复位 */
    volatile uint32_t LCKR; /* 0x18 锁定 */
} GPIO_Type;

#define GPIOA_BASE (APB2PERIPH_BASE + 0x0800u)
#define GPIOB_BASE (APB2PERIPH_BASE + 0x0C00u)
#define GPIOC_BASE (APB2PERIPH_BASE + 0x1000u)
#define GPIOD_BASE (APB2PERIPH_BASE + 0x1400u)
#define GPIOA ((GPIO_Type *)GPIOA_BASE)
#define GPIOB ((GPIO_Type *)GPIOB_BASE)
#define GPIOC ((GPIO_Type *)GPIOC_BASE)
#define GPIOD ((GPIO_Type *)GPIOD_BASE)

/* GPIO 模式（CRL/CRH 每引脚 4bit：CNF[1:0] 高 2 位 + MODE[1:0] 低 2 位） */
typedef enum {
    GPIO_MODE_IN_ANALOG = 0x0,   /* 模拟输入               CNF=00 MODE=00 */
    GPIO_MODE_IN_FLOAT  = 0x4,   /* 浮空输入               CNF=01 MODE=00 */
    GPIO_MODE_IN_PUPD   = 0x8,   /* 上拉/下拉输入（ODR 选） CNF=10 MODE=00 */
    GPIO_MODE_OUT_PP_2  = 0x2,   /* 推挽输出 2MHz          CNF=00 MODE=10 */
    GPIO_MODE_OUT_PP_50 = 0x3,   /* 推挽输出 50MHz         CNF=00 MODE=11 */
    GPIO_MODE_OUT_OD_2  = 0x6,   /* 开漏输出 2MHz          CNF=01 MODE=10 */
    GPIO_MODE_OUT_OD_50 = 0x7,   /* 开漏输出 50MHz         CNF=01 MODE=11 */
    GPIO_MODE_AF_PP_50  = 0xB,   /* 复用推挽 50MHz         CNF=10 MODE=11 */
    GPIO_MODE_AF_OD_50  = 0xF,   /* 复用开漏 50MHz         CNF=11 MODE=11 */
} gpio_mode_t;

/**
 * @brief 配置单个 GPIO 引脚模式
 * @param port GPIOA/B/C/D 指针
 * @param pin  0~15
 * @param mode gpio_mode_t
 */
static inline void gpio_init(GPIO_Type *port, int pin, gpio_mode_t mode)
{
    volatile uint32_t *cr = (pin < 8) ? &port->CRL : &port->CRH;
    int shift = (pin % 8) * 4;
    uint32_t tmp = *cr;
    tmp &= ~(0xFu << shift);
    tmp |= ((uint32_t)mode << shift);
    *cr = tmp;
}

static inline void gpio_set(GPIO_Type *port, int pin)   { port->BSRR = 1u << pin; }
static inline void gpio_reset(GPIO_Type *port, int pin) { port->BRR  = 1u << pin; }
static inline void gpio_write(GPIO_Type *port, int pin, int v)
{
    if (v) gpio_set(port, pin); else gpio_reset(port, pin);
}
static inline int gpio_read(GPIO_Type *port, int pin)   { return (int)((port->IDR >> pin) & 1u); }

/* ------------------------------------------------------------------ */
/* USART1                                                             */
/* ------------------------------------------------------------------ */
typedef struct {
    volatile uint32_t SR;    /* 0x00 */
    volatile uint32_t DR;    /* 0x04 */
    volatile uint32_t BRR;   /* 0x08 */
    volatile uint32_t CR1;   /* 0x0C */
    volatile uint32_t CR2;   /* 0x10 */
    volatile uint32_t CR3;   /* 0x14 */
    volatile uint32_t GTPR;  /* 0x18 */
} USART_Type;

#define USART1_BASE (APB2PERIPH_BASE + 0x3800u)
#define USART1      ((USART_Type *)USART1_BASE)

#define USART_SR_TXE  (1u << 7)
#define USART_SR_RXNE (1u << 5)
#define USART_CR1_UE  (1u << 13)
#define USART_CR1_TE  (1u << 3)
#define USART_CR1_RE  (1u << 2)

/**
 * @brief USART1 初始化（72MHz PCLK2，8N1）
 * @param baud 波特率，如 115200
 */
static inline void uart1_init(uint32_t baud)
{
    uint32_t freq = (uint32_t)F1_CPU_FREQ_MHZ * 1000000u;
    uint32_t div_x16 = (freq + baud / 2u) / baud;
    USART1->BRR = div_x16 & 0xFFFFu;
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;
}

static inline void uart1_putc(char c)
{
    while (!(USART1->SR & USART_SR_TXE)) { }
    USART1->DR = (uint8_t)c;
}
static inline int uart1_getc_nb(void)
{
    if (USART1->SR & USART_SR_RXNE) return (int)(USART1->DR & 0xFFu);
    return -1;
}

/* ------------------------------------------------------------------ */
/* 定时器（TIM1 高级 / TIM2~4 通用；CCR1 均在 0x34，共用一个结构）       */
/* ------------------------------------------------------------------ */
typedef struct {
    volatile uint32_t CR1;      /* 0x00 */
    volatile uint32_t CR2;      /* 0x04 */
    volatile uint32_t SMCR;     /* 0x08 */
    volatile uint32_t DIER;     /* 0x0C */
    volatile uint32_t SR;       /* 0x10 */
    volatile uint32_t EGR;      /* 0x14 */
    volatile uint32_t CCMR1;    /* 0x18 */
    volatile uint32_t CCMR2;    /* 0x1C */
    volatile uint32_t CCER;     /* 0x20 */
    volatile uint32_t CNT;      /* 0x24 */
    volatile uint32_t PSC;      /* 0x28 */
    volatile uint32_t ARR;      /* 0x2C */
    volatile uint32_t RCR;      /* 0x30（仅 TIM1 有效；TIM2~4 无此寄存器） */
    volatile uint32_t CCR1;     /* 0x34 */
    volatile uint32_t CCR2;     /* 0x38 */
    volatile uint32_t CCR3;     /* 0x3C */
    volatile uint32_t CCR4;     /* 0x40 */
    volatile uint32_t BDTR;     /* 0x44 仅 TIM1 有效；TIM2~4 此偏移为保留区 */
    volatile uint32_t DCR;      /* 0x48 */
    volatile uint32_t DMAR;     /* 0x4C */
} TIM_Type;

#define TIM1_BASE (APB2PERIPH_BASE + 0x2000u)
#define TIM2_BASE (APB1PERIPH_BASE + 0x0000u)
#define TIM3_BASE (APB1PERIPH_BASE + 0x0400u)
#define TIM4_BASE (APB1PERIPH_BASE + 0x0800u)
#define TIM1 ((TIM_Type *)TIM1_BASE)
#define TIM2 ((TIM_Type *)TIM2_BASE)
#define TIM3 ((TIM_Type *)TIM3_BASE)
#define TIM4 ((TIM_Type *)TIM4_BASE)

#define TIM_CR1_CEN    (1u << 0)
#define TIM_CR1_ARPE   (1u << 7)
#define TIM_EGR_UG     (1u << 0)
#define TIM_CCER_CC1E  (1u << 0)
#define TIM_CCER_CC2E  (1u << 4)
#define TIM_CCER_CC3E  (1u << 8)
#define TIM_CCER_CC4E  (1u << 12)
#define TIM1_BDTR_MOE  (1u << 15)  /* TIM1 专用主输出使能 */
#define TIM_SR_UIF     (1u << 0)

#define TIM_CCMR1_OC1M_PWM1 (6u << 4)    /* PWM 模式 1 + 预装载见下 */
#define TIM_CCMR1_OC1PE     (1u << 3)
#define TIM_CCMR2_OC2M_PWM1 (6u << 12)
#define TIM_CCMR2_OC2PE     (1u << 11)

/* ------------------------------------------------------------------ */
/* ADC1                                                               */
/* ------------------------------------------------------------------ */
typedef struct {
    volatile uint32_t SR;      /* 0x00 */
    volatile uint32_t CR1;     /* 0x04 */
    volatile uint32_t CR2;     /* 0x08 */
    volatile uint32_t SMPR1;   /* 0x0C */
    volatile uint32_t SMPR2;   /* 0x10 */
    uint32_t _r0[4];           /* 0x14~0x20 JOFR1~4 */
    volatile uint32_t HTR;     /* 0x24 */
    volatile uint32_t LTR;     /* 0x28 */
    uint32_t _r1;              /* 0x2C 保留 */
    volatile uint32_t SQR1;    /* 0x30 */
    volatile uint32_t SQR2;    /* 0x34 */
    volatile uint32_t SQR3;    /* 0x38 */
    volatile uint32_t JSQR;    /* 0x3C */
    volatile uint32_t JDR1;    /* 0x40 */
    volatile uint32_t JDR2;    /* 0x44 */
    volatile uint32_t JDR3;    /* 0x48 */
    volatile uint32_t JDR4;    /* 0x4C */
    volatile uint32_t DR;      /* 0x50 */
} ADC_Type;

#define ADC1_BASE (APB2PERIPH_BASE + 0x2400u)
#define ADC1      ((ADC_Type *)ADC1_BASE)

#define ADC_CR2_ADON    (1u << 0)
#define ADC_CR2_CONT    (1u << 1)
#define ADC_CR2_CAL     (1u << 2)
#define ADC_CR2_RSTCAL  (1u << 3)
#define ADC_CR2_SWSTART (1u << 22)
#define ADC_SR_EOC      (1u << 1)

/**
 * @brief 单次软件触发 ADC 采样
 * @param channel 0~17（0~7 = PA0~PA7，8~9 = PB0~PB1，...）
 * @return 12bit 转换值 0~4095
 */
static inline uint16_t adc1_read(uint8_t channel)
{
    /* 规则序列长度 = 1，第 1 个转换 = channel */
    ADC1->SQR1 = 0;
    ADC1->SQR3 = channel & 0x1Fu;
    ADC1->CR2 |= ADC_CR2_SWSTART;
    while (!(ADC1->SR & ADC_SR_EOC)) { }
    uint16_t v = (uint16_t)(ADC1->DR & 0xFFFu);
    ADC1->SR &= ~ADC_SR_EOC;
    return v;
}

/* ------------------------------------------------------------------ */
/* I2C1（OLED 例程用软件 I2C，硬件 I2C 定义保留备用）                    */
/* ------------------------------------------------------------------ */
typedef struct {
    volatile uint32_t CR1;     /* 0x00 */
    volatile uint32_t CR2;     /* 0x04 */
    volatile uint32_t OAR1;    /* 0x08 */
    volatile uint32_t OAR2;    /* 0x0C */
    volatile uint32_t DR;      /* 0x10 */
    volatile uint32_t SR1;     /* 0x14 */
    volatile uint32_t SR2;     /* 0x18 */
    volatile uint32_t CCR;     /* 0x1C */
    volatile uint32_t TRISE;   /* 0x20 */
} I2C_Type;

#define I2C1_BASE (APB1PERIPH_BASE + 0x5400u)
#define I2C1      ((I2_Type *)I2C1_BASE)
#define I2C_CR1_PE (1u << 0)

/* ------------------------------------------------------------------ */
/* EXTI / AFIO                                                        */
/* ------------------------------------------------------------------ */
typedef struct {
    volatile uint32_t EVCR;     /* 0x00 */
    volatile uint32_t MAPR;     /* 0x04 */
    volatile uint32_t EXTICR[4];/* 0x08~ */
} AFIO_Type;

typedef struct {
    volatile uint32_t IMR;      /* 0x00 */
    volatile uint32_t EMR;      /* 0x04 */
    volatile uint32_t RTSR;     /* 0x08 */
    volatile uint32_t FTSR;     /* 0x0C */
    volatile uint32_t SWIER;    /* 0x10 */
    volatile uint32_t PR;       /* 0x14 */
} EXTI_Type;

#define AFIO_BASE (APB2PERIPH_BASE + 0x0000u)
#define EXTI_BASE (APB2PERIPH_BASE + 0x0400u + 0x0000u) /* 0x40010400? 见下 */
/* 修正：EXTI 实际基址 0x40010400 = PERIPH_BASE + 0x10400 */
#undef  EXTI_BASE
#define EXTI_BASE (PERIPH_BASE + 0x10400u)
#define AFIO ((AFIO_Type *)AFIO_BASE)
#define EXTI ((EXTI_Type *)EXTI_BASE)

/* ------------------------------------------------------------------ */
/* 时钟初始化：HSI 直跑 8MHz（调试模式——PLL 切换在部分板上有 HardFault，
 * 先用 HSI 跑通全链路，后续排查 PLL 问题后切回 72MHz）                    */
/* ------------------------------------------------------------------ */
static inline void sysclock_init_72m(void)
{
    /* HSI 是复位默认时钟（8MHz），无需配置——待 PLL 问题修复后切回 72MHz */
}

#endif /* STM32F103X_MIN_H */
