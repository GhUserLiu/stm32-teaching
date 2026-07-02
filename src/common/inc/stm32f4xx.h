/**
  ******************************************************************************
  * @file    stm32f4xx.h
  * @brief   STM32F4xx标准外设库头文件 - 简化版
  ******************************************************************************
  */

#ifndef __STM32F4xx_H
#define __STM32F4xx_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* ========== 定义和类型 ========== */
#define __IO    volatile
#define __I     volatile const
#define __O     volatile

typedef uint32_t uint32_t;
typedef uint16_t uint16_t;
typedef uint8_t  uint8_t;

/* ========== 位带操作 ========== */
#define BITBAND(addr, bitnum) ((addr & 0xF0000000)+0x2000000+((addr &0xFFFFF)<<5)+(bitnum<<2))
#define MEM_ADDR(addr)  *((volatile unsigned long  *)(addr))
#define BIT_ADDR(addr, bitnum)   MEM_ADDR(BITBAND(addr, bitnum))

/* GPIO地址映射 */
#define GPIOA_ODR_Addr    (GPIOA_BASE+20)
#define GPIOB_ODR_Addr    (GPIOB_BASE+20)
#define GPIOC_ODR_Addr    (GPIOC_BASE+20)
#define GPIOD_ODR_Addr    (GPIOD_BASE+20)
#define GPIOE_ODR_Addr    (GPIOE_BASE+20)
#define GPIOF_ODR_Addr    (GPIOF_BASE+20)
#define GPIOG_ODR_Addr    (GPIOG_BASE+20)
#define GPIOH_ODR_Addr    (GPIOH_BASE+20)

#define GPIOA_IDR_Addr    (GPIOA_BASE+16)
#define GPIOB_IDR_Addr    (GPIOB_BASE+16)
#define GPIOC_IDR_Addr    (GPIOC_BASE+16)
#define GPIOD_IDR_Addr    (GPIOD_BASE+16)
#define GPIOE_IDR_Addr    (GPIOE_BASE+16)
#define GPIOF_IDR_Addr    (GPIOF_BASE+16)
#define GPIOG_IDR_Addr    (GPIOG_BASE+16)
#define GPIOH_IDR_Addr    (GPIOH_BASE+16)

/* GPIO位操作别名 */
#define PAout(n)   BIT_ADDR(GPIOA_ODR_Addr,n)
#define PAin(n)    BIT_ADDR(GPIOA_IDR_Addr,n)
#define PBout(n)   BIT_ADDR(GPIOB_ODR_Addr,n)
#define PBin(n)    BIT_ADDR(GPIOB_IDR_Addr,n)
#define PCout(n)   BIT_ADDR(GPIOC_ODR_Addr,n)
#define PCin(n)    BIT_ADDR(GPIOC_IDR_Addr,n)
#define PDout(n)   BIT_ADDR(GPIOD_ODR_Addr,n)
#define PDin(n)    BIT_ADDR(GPIOD_IDR_Addr,n)
#define PEout(n)   BIT_ADDR(GPIOE_ODR_Addr,n)
#define PEin(n)    BIT_ADDR(GPIOE_IDR_Addr,n)
#define PFout(n)   BIT_ADDR(GPIOF_ODR_Addr,n)
#define PFin(n)    BIT_ADDR(GPIOF_IDR_Addr,n)

/* ========== 基地址定义 ========== */
#define PERIPH_BASE           0x40000000
#define AHB1PERIPH_BASE       (PERIPH_BASE + 0x00020000)
#define AHB2PERIPH_BASE       (PERIPH_BASE + 0x10000000)

#define GPIOA_BASE            (AHB1PERIPH_BASE + 0x0000)
#define GPIOB_BASE            (AHB1PERIPH_BASE + 0x0400)
#define GPIOC_BASE            (AHB1PERIPH_BASE + 0x0800)
#define GPIOD_BASE            (AHB1PERIPH_BASE + 0x0C00)
#define GPIOE_BASE            (AHB1PERIPH_BASE + 0x1000)
#define GPIOF_BASE            (AHB1PERIPH_BASE + 0x1400)
#define GPIOG_BASE            (AHB1PERIPH_BASE + 0x1800)
#define GPIOH_BASE            (AHB1PERIPH_BASE + 0x1C00)
#define RCC_BASE              (AHB1PERIPH_BASE + 0x3800)

/* ========== GPIO寄存器结构 ========== */
typedef struct
{
  __IO uint32_t MODER;        /* 模式寄存器 */
  __IO uint32_t OTYPER;       /* 输出类型寄存器 */
  __IO uint32_t OSPEEDR;      /* 输出速度寄存器 */
  __IO uint32_t PUPDR;        /* 上拉/下拉寄存器 */
  __IO uint32_t IDR;          /* 输入数据寄存器 */
  __IO uint32_t ODR;          /* 输出数据寄存器 */
  __IO uint32_t BSRR;         /* 置位/复位寄存器 */
  __IO uint32_t LCKR;         /* 配置锁定寄存器 */
  __IO uint32_t AFR[2];       /* 复用功能寄存器 */
} GPIO_TypeDef;

/* ========== RCC寄存器结构 ========== */
typedef struct
{
  __IO uint32_t CR;            /* 时钟控制寄存器 */
  __IO uint32_t PLLCFGR;       /* PLL配置寄存器 */
  __IO uint32_t CFGR;          /* 时钟配置寄存器 */
  __IO uint32_t CIR;           /* 时钟中断寄存器 */
  __IO uint32_t AHB1RSTR;      /* AHB1外设复位寄存器 */
  __IO uint32_t AHB2RSTR;      /* AHB2外设复位寄存器 */
  __IO uint32_t AHB3RSTR;      /* AHB3外设复位寄存器 */
  uint32_t      RESERVED0[2];
  __IO uint32_t APB1RSTR;      /* APB1外设复位寄存器 */
  __IO uint32_t APB2RSTR;      /* APB2外设复位寄存器 */
  uint32_t      RESERVED1[2];
  __IO uint32_t AHB1ENR;       /* AHB1外设时钟使能寄存器 */
  __IO uint32_t AHB2ENR;       /* AHB2外设时钟使能寄存器 */
  __IO uint32_t AHB3ENR;       /* AHB3外设时钟使能寄存器 */
  uint32_t      RESERVED2[2];
  __IO uint32_t APB1ENR;       /* APB1外设时钟使能寄存器 */
  __IO uint32_t APB2ENR;       /* APB2外设时钟使能寄存器 */
  uint32_t      RESERVED3[2];
  __IO uint32_t AHB1LPENR;     /* AHB1低功耗模式时钟使能寄存器 */
  __IO uint32_t AHB2LPENR;     /* AHB2低功耗模式时钟使能寄存器 */
  __IO uint32_t AHB3LPENR;     /* AHB3低功耗模式时钟使能寄存器 */
  uint32_t      RESERVED4[2];
  __IO uint32_t APB1LPENR;     /* APB1低功耗模式时钟使能寄存器 */
  __IO uint32_t APB2LPENR;     /* APB2低功耗模式时钟使能寄存器 */
  uint32_t      RESERVED5[2];
  __IO uint32_t BDCR;          /* 备份域控制寄存器 */
  __IO uint32_t CSR;           /* 时钟控制状态寄存器 */
  uint32_t      RESERVED6[2];
  __IO uint32_t SSCGR;         /* 扩展时钟控制寄存器 */
  __IO uint32_t PLLI2SCFGR;    /* PLLI2S配置寄存器 */
} RCC_TypeDef;

/* ========== GPIO外设声明 ========== */
#define GPIOA               ((GPIO_TypeDef *) GPIOA_BASE)
#define GPIOB               ((GPIO_TypeDef *) GPIOB_BASE)
#define GPIOC               ((GPIO_TypeDef *) GPIOC_BASE)
#define GPIOD               ((GPIO_TypeDef *) GPIOD_BASE)
#define GPIOE               ((GPIO_TypeDef *) GPIOE_BASE)
#define GPIOF               ((GPIO_TypeDef *) GPIOF_BASE)
#define GPIOG               ((GPIO_TypeDef *) GPIOG_BASE)
#define GPIOH               ((GPIO_TypeDef *) GPIOH_BASE)

/* ========== RCC外设声明 ========== */
#define RCC                 ((RCC_TypeDef *) RCC_BASE)

/* ========== GPIO引脚定义 ========== */
#define GPIO_Pin_0                 ((uint16_t)0x0001)
#define GPIO_Pin_1                 ((uint16_t)0x0002)
#define GPIO_Pin_2                 ((uint16_t)0x0004)
#define GPIO_Pin_3                 ((uint16_t)0x0008)
#define GPIO_Pin_4                 ((uint16_t)0x0010)
#define GPIO_Pin_5                 ((uint16_t)0x0020)
#define GPIO_Pin_6                 ((uint16_t)0x0040)
#define GPIO_Pin_7                 ((uint16_t)0x0080)
#define GPIO_Pin_8                 ((uint16_t)0x0100)
#define GPIO_Pin_9                 ((uint16_t)0x0200)
#define GPIO_Pin_10                ((uint16_t)0x0400)
#define GPIO_Pin_11                ((uint16_t)0x0800)
#define GPIO_Pin_12                ((uint16_t)0x1000)
#define GPIO_Pin_13                ((uint16_t)0x2000)
#define GPIO_Pin_14                ((uint16_t)0x4000)
#define GPIO_Pin_15                ((uint16_t)0x8000)
#define GPIO_Pin_All               ((uint16_t)0xFFFF)

/* ========== GPIO模式定义 ========== */
#define GPIO_Mode_IN               0x00000000
#define GPIO_Mode_OUT              0x00000001
#define GPIO_Mode_AF               0x00000002
#define GPIO_Mode_AN               0x00000003

/* ========== GPIO输出类型定义 ========== */
#define GPIO_OType_PP              0x00000000
#define GPIO_OType_OD              0x00000001

/* ========== GPIO输出速度定义 ========== */
#define GPIO_Speed_2MHz            0x00000000
#define GPIO_Speed_25MHz           0x00000001
#define GPIO_Speed_50MHz           0x00000002
#define GPIO_Speed_100MHz          0x00000003

/* ========== 功能状态定义 ========== */
typedef enum
{
  DISABLE = 0,
  ENABLE = !DISABLE
} FunctionalState;

/* ========== GPIO上拉/下拉定义 ========== */
#define GPIO_PuPd_NOPULL           0x00000000
#define GPIO_PuPd_UP               0x00000001
#define GPIO_PuPd_DOWN             0x00000002

/* ========== RCC时钟使能定义 ========== */
#define RCC_AHB1Periph_GPIOA       0x00000001
#define RCC_AHB1Periph_GPIOB       0x00000002
#define RCC_AHB1Periph_GPIOC       0x00000004
#define RCC_AHB1Periph_GPIOD       0x00000008
#define RCC_AHB1Periph_GPIOE       0x00000010
#define RCC_AHB1Periph_GPIOF       0x00000040
#define RCC_AHB1Periph_GPIOG       0x00000080
#define RCC_AHB1Periph_GPIOH       0x00000100

/* ========== GPIO初始化结构体 ========== */
typedef struct
{
  uint32_t GPIO_Pin;              /* 选择要配置的引脚 */
  uint32_t GPIO_Mode;             /* 选择工作模式 */
  uint32_t GPIO_OType;            /* 选择输出类型 */
  uint32_t GPIO_Speed;            /* 选择输出速度 */
  uint32_t GPIO_PuPd;             /* 选择上拉/下拉 */
} GPIO_InitTypeDef;

/* ========== 函数声明 ========== */
void RCC_AHB1PeriphClockCmd(uint32_t RCC_AHB1Periph, FunctionalState NewState);
void GPIO_Init(GPIO_TypeDef* GPIOx, GPIO_InitTypeDef* GPIO_InitStruct);
void GPIO_SetBits(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);
void GPIO_ResetBits(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);

#ifdef __cplusplus
}
#endif

#endif /* __STM32F4xx_H */
