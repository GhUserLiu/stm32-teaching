/**
  ******************************************************************************
  * @file    stm32f4xx_hal.h
  * @brief   STM32F4xx HAL库头文件 - 简化版
  ******************************************************************************
  */

#ifndef __STM32F4xx_HAL_H
#define __STM32F4xx_HAL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

/* ========== 定义 ========== */
#define __IO            volatile
#define __I             volatile const
#define __O             volatile
#define __IC            volatile const
#define __STATIC_INLINE static inline

#ifndef __NVIC_PRIO_BITS
#define __NVIC_PRIO_BITS 4
#endif

/* ========== 中断号定义 ========== */
typedef enum {
  SysTick_IRQn = -1,
} IRQn_Type;

/* ========== Cortex-M核定义 ========== */
#define SCB_BASE      (0xE000E000)
#define SCB           ((SCB_Type *) SCB_BASE)

typedef struct
{
  __IO uint32_t CPUID;
  __IO uint32_t ICSR;
  __IO uint32_t VTOR;
  __IO uint32_t AIRCR;
  __IO uint32_t SCR;
  __IO uint32_t CCR;
  __IO uint8_t  SHP[12];
  __IO uint32_t SHCSR;
  __IO uint32_t CFSR;
  __IO uint32_t HFSR;
  __IO uint32_t DFSR;
  __IO uint32_t MMFAR;
  __IO uint32_t BFAR;
  __IO uint32_t AFSR;
  __IO uint32_t PFR[2];
  __IO uint32_t DFR;
  __IO uint32_t ADR;
  __IO uint32_t MMFR[4];
  __IO uint32_t ISAR[5];
       uint32_t RESERVED0[5];
  __IO uint32_t CPACR;
} SCB_Type;

__STATIC_INLINE void NVIC_SetPriority(IRQn_Type IRQn, uint32_t priority)
{
  if ((int32_t)IRQn < 0)
  {
    SCB->SHP[((uint32_t)(IRQn) & 0xF)-4] = ((priority << (8 - __NVIC_PRIO_BITS)) & 0xff);
  }
}

/* ========== 基地址定义 ========== */
#define PERIPH_BASE           0x40000000
#define AHB1PERIPH_BASE       (PERIPH_BASE + 0x00020000)

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
  __IO uint32_t MODER;
  __IO uint32_t OTYPER;
  __IO uint32_t OSPEEDR;
  __IO uint32_t PUPDR;
  __IO uint32_t IDR;
  __IO uint32_t ODR;
  __IO uint32_t BSRR;
  __IO uint32_t LCKR;
  __IO uint32_t AFR[2];
} GPIO_TypeDef;

/* ========== RCC寄存器结构（简化版） ========== */
typedef struct
{
  __IO uint32_t CR;
  __IO uint32_t PLLCFGR;
  __IO uint32_t CFGR;
  __IO uint32_t CIR;
  __IO uint32_t AHB1RSTR;
  __IO uint32_t AHB2RSTR;
  __IO uint32_t AHB3RSTR;
  uint32_t      RESERVED0[2];
  __IO uint32_t APB1RSTR;
  __IO uint32_t APB2RSTR;
  uint32_t      RESERVED1[2];
  __IO uint32_t AHB1ENR;
  __IO uint32_t AHB2ENR;
  __IO uint32_t AHB3ENR;
  uint32_t      RESERVED2[2];
  __IO uint32_t APB1ENR;
  __IO uint32_t APB2ENR;
  uint32_t      RESERVED3[2];
  __IO uint32_t AHB1LPENR;
  __IO uint32_t AHB2LPENR;
  __IO uint32_t AHB3LPENR;
  uint32_t      RESERVED4[2];
  __IO uint32_t APB1LPENR;
  __IO uint32_t APB2LPENR;
  uint32_t      RESERVED5[2];
  __IO uint32_t BDCR;
  __IO uint32_t CSR;
  uint32_t      RESERVED6[2];
  __IO uint32_t SSCGR;
  __IO uint32_t PLLI2SCFGR;
} RCC_TypeDef;

/* ========== SysTick寄存器结构 ========== */
#define SysTick_BASE      (0xE000E010)
#define SysTick           ((SysTick_Type *) SysTick_BASE)

typedef struct
{
  __IO uint32_t CTRL;
  __IO uint32_t LOAD;
  __IO uint32_t VAL;
  __IC uint32_t CALIB;
} SysTick_Type;

#define SysTick_CTRL_COUNTFLAG_Msk  (1UL << 16)
#define SysTick_CTRL_CLKSOURCE_Msk  (1UL << 2)
#define SysTick_CTRL_TICKINT_Msk    (1UL << 1)
#define SysTick_CTRL_ENABLE_Msk     (1UL << 0)

/* ========== 外设声明 ========== */
#define GPIOA               ((GPIO_TypeDef *) GPIOA_BASE)
#define GPIOB               ((GPIO_TypeDef *) GPIOB_BASE)
#define GPIOC               ((GPIO_TypeDef *) GPIOC_BASE)
#define GPIOD               ((GPIO_TypeDef *) GPIOD_BASE)
#define GPIOE               ((GPIO_TypeDef *) GPIOE_BASE)
#define GPIOF               ((GPIO_TypeDef *) GPIOF_BASE)
#define GPIOG               ((GPIO_TypeDef *) GPIOG_BASE)
#define GPIOH               ((GPIO_TypeDef *) GPIOH_BASE)
#define RCC                 ((RCC_TypeDef *) RCC_BASE)

/* ========== GPIO引脚定义 ========== */
#define GPIO_PIN_0          ((uint16_t)0x0001)
#define GPIO_PIN_1          ((uint16_t)0x0002)
#define GPIO_PIN_2          ((uint16_t)0x0004)
#define GPIO_PIN_3          ((uint16_t)0x0008)
#define GPIO_PIN_4          ((uint16_t)0x0010)
#define GPIO_PIN_5          ((uint16_t)0x0020)
#define GPIO_PIN_6          ((uint16_t)0x0040)
#define GPIO_PIN_7          ((uint16_t)0x0080)
#define GPIO_PIN_8          ((uint16_t)0x0100)
#define GPIO_PIN_9          ((uint16_t)0x0200)
#define GPIO_PIN_10         ((uint16_t)0x0400)
#define GPIO_PIN_11         ((uint16_t)0x0800)
#define GPIO_PIN_12         ((uint16_t)0x1000)
#define GPIO_PIN_13         ((uint16_t)0x2000)
#define GPIO_PIN_14         ((uint16_t)0x4000)
#define GPIO_PIN_15         ((uint16_t)0x8000)
#define GPIO_PIN_All        ((uint16_t)0xFFFF)

/* ========== GPIO模式定义 ========== */
#define GPIO_MODE_INPUT      0x00000000
#define GPIO_MODE_OUTPUT_PP  0x00000001
#define GPIO_MODE_OUTPUT_OD  0x00000011
#define GPIO_MODE_AF_PP      0x00000002
#define GPIO_MODE_AF_OD      0x00000012
#define GPIO_MODE_ANALOG     0x00000003

/* ========== GPIO上拉/下拉定义 ========== */
#define GPIO_NOPULL          0x00000000
#define GPIO_PULLUP          0x00000001
#define GPIO_PULLDOWN        0x00000002

/* ========== GPIO速度定义 ========== */
#define GPIO_SPEED_FREQ_LOW         0x00000000
#define GPIO_SPEED_FREQ_MEDIUM      0x00000001
#define GPIO_SPEED_FREQ_HIGH        0x00000002
#define GPIO_SPEED_FREQ_VERY_HIGH   0x00000003

/* ========== GPIO电平状态枚举 ========== */
typedef enum
{
  GPIO_PIN_RESET = 0,
  GPIO_PIN_SET
} GPIO_PinState;

/* ========== GPIO电平宏（与枚举值一致） ========== */
#define GPIO_PIN_RESET      0
#define GPIO_PIN_SET        1

/* ========== GPIO初始化结构体 ========== */
typedef struct
{
  uint32_t Pin;
  uint32_t Mode;
  uint32_t Pull;
  uint32_t Speed;
  uint32_t Alternate;
} GPIO_InitTypeDef;

/* ========== HAL状态定义 ========== */
typedef enum
{
  HAL_OK       = 0x00,
  HAL_ERROR    = 0x01,
  HAL_BUSY     = 0x02,
  HAL_TIMEOUT  = 0x03
} HAL_StatusTypeDef;

/* ========== HAL标志定义 ========== */
typedef enum
{
  RESET = 0,
  SET   = !RESET
} FlagStatus, ITStatus;

/* ========== HAL全局变量 ========== */
extern volatile uint32_t uwTick;
extern volatile uint32_t uwTickPrio;

/* ========== RCC时钟使能宏 ========== */
#define __HAL_RCC_GPIOA_CLK_ENABLE()   do { \
                                        RCC->AHB1ENR |= (1U << 0); \
                                      } while(0)

#define __HAL_RCC_GPIOB_CLK_ENABLE()   do { \
                                        RCC->AHB1ENR |= (1U << 1); \
                                      } while(0)

#define __HAL_RCC_GPIOE_CLK_ENABLE()   do { \
                                        RCC->AHB1ENR |= (1U << 4); \
                                      } while(0)

#define __HAL_RCC_GPIOF_CLK_ENABLE()   do { \
                                        RCC->AHB1ENR |= (1U << 5); \
                                      } while(0)

/* ========== GPIO宏函数 ========== */
#define __HAL_GPIO_EXTI_GET_FLAG(__EXTI_LINE__)   0
#define __HAL_GPIO_EXTI_CLEAR_FLAG(__EXTI_LINE__) 0

/* ========== HAL函数声明 ========== */
HAL_StatusTypeDef HAL_Init(void);
HAL_StatusTypeDef HAL_DeInit(void);
HAL_StatusTypeDef HAL_SYSTICK_Config(uint32_t TicksNumb);
void HAL_IncTick(void);
uint32_t HAL_GetTick(void);
void HAL_Delay(__IO uint32_t Delay);
void HAL_GPIO_Init(GPIO_TypeDef* GPIOx, GPIO_InitTypeDef* GPIO_InitStruct);
void HAL_GPIO_WritePin(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin, GPIO_PinState PinState);
void HAL_GPIO_TogglePin(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);
GPIO_PinState HAL_GPIO_ReadPin(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);
void SysTick_Handler(void);

#ifdef __cplusplus
}
#endif

#endif /* __STM32F4xx_HAL_H */
