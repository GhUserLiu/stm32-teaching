/**
 ******************************************************************************
 * @file    stm32f4xx_hal_ext.h
 * @brief   STM32F4xx HAL库扩展版 - 支持RCC、EXTI、NVIC
 * @说明    : 在简化版HAL基础上扩展，支持时钟配置和外部中断
 ******************************************************************************
 */

#ifndef __STM32F4xx_HAL_EXT_H
#define __STM32F4xx_HAL_EXT_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* ========== 弱定义宏 ========== */
#ifndef __weak
#define __weak   __attribute__((weak))
#endif

/* ========== 扩展基地址定义 ========== */
#define PERIPH_BASE           0x40000000
#define AHB1PERIPH_BASE       (PERIPH_BASE + 0x00020000)
#define AHB2PERIPH_BASE       (PERIPH_BASE + 0x10000000)
#define APB1PERIPH_BASE       (PERIPH_BASE + 0x00040000)
#define APB2PERIPH_BASE       (PERIPH_BASE + 0x00010000)

/* ========== EXTI 基地址和结构 ========== */
#define EXTI_BASE             (APB2PERIPH_BASE + 0x3C00)
#define EXTI                 ((EXTI_TypeDef *) EXTI_BASE)

typedef struct
{
  __IO uint32_t IMR;     /* 中断屏蔽寄存器 */
  __IO uint32_t EMR;     /* 事件屏蔽寄存器 */
  __IO uint32_t RTSR;    /* 上升沿触发选择寄存器 */
  __IO uint32_t FTSR;    /* 下降沿触发选择寄存器 */
  __IO uint32_t SWIER;   /* 软件中断事件寄存器 */
  __IO uint32_t PR;      /* 挂起寄存器 */
  uint32_t      RESERVED1;
  __IO uint32_t IMR2;    /* 中断屏蔽寄存器2 (STM32F4xx扩展) */
  __IO uint32_t EMR2;    /* 事件屏蔽寄存器2 */
  __IO uint32_t RTSR2;   /* 上升沿触发选择寄存器2 */
  __IO uint32_t FTSR2;   /* 下降沿触发选择寄存器2 */
  __IO uint32_t SWIER2;  /* 软件中断事件寄存器2 */
  __IO uint32_t PR2;     /* 挂起寄存器2 */
} EXTI_TypeDef;

/* ========== SYSCFG 基地址和结构 ========== */
#define SYSCFG_BASE           (APB2PERIPH_BASE + 0x3800)
#define SYSCFG               ((SYSCFG_TypeDef *) SYSCFG_BASE)

typedef struct
{
  __IO uint32_t MEMRMP;       /* 内存映射寄存器 */
  __IO uint32_t PMC;          /* 外设模式配置寄存器 */
  __IO uint32_t EXTICR[4];    /* 外部中断配置寄存器 */
  uint32_t      RESERVED1;
  __IO uint32_t CMPCR;        /* Compensation cell控制寄存器 */
} SYSCFG_TypeDef;

/* ========== NVIC 相关定义 ========== */
#define NVIC_BASE            (0xE000E100)
#define NVIC               ((NVIC_Type *) NVIC_BASE)

typedef struct
{
  __IO uint32_t ISER[8];       /* 中断使能设置寄存器 */
  uint32_t      RESERVED0[24];
  __IO uint32_t ICER[8];       /* 中断使能清除寄存器 */
  uint32_t      RESERVED1[24];
  __IO uint32_t ISPR[8];       /* 中断使能设置寄存器 */
  uint32_t      RESERVED2[24];
  __IO uint32_t ICPR[8];       /* 中断使能清除寄存器 */
  uint32_t      RESERVED3[24];
  __IO uint32_t IABR[8];       /* 中断激活位寄存器 */
  uint32_t      RESERVED4[56];
  __IO uint8_t  IP[240];       /* 中断优先级寄存器 */
  uint32_t      RESERVED5[644];
  __IO uint32_t STIR;          /* 软件触发中断寄存器 */
} NVIC_Type;

#define __NVIC_PRIO_BITS      4

/* ========== 中断号定义扩展 (STM32F407xx) ========== */
/* 注意：基础IRQn_Type已在stm32f4xx_hal.h中定义，这里只添加STM32特定的中断 */
enum {
  /* STM32特定中断号 */
  WWDG_IRQn                   = 0,      /*!< Window WatchDog Interrupt                           */
  PVD_IRQn                    = 1,      /*!< PVD through EXTI Line detection Interrupt          */
  TAMP_STAMP_IRQn             = 2,      /*!< Tamper and TimeStamp interrupts through the EXTI line */
  RTC_WKUP_IRQn               = 3,      /*!< RTC Wakeup interrupt through the EXTI line          */
  FLASH_IRQn                  = 4,      /*!< FLASH global Interrupt                              */
  RCC_IRQn                    = 5,      /*!< RCC global Interrupt                                */
  EXTI0_IRQn                  = 6,      /*!< EXTI Line0 Interrupt                                */
  EXTI1_IRQn                  = 7,      /*!< EXTI Line1 Interrupt                                */
  EXTI2_IRQn                  = 8,      /*!< EXTI Line2 Interrupt                                */
  EXTI3_IRQn                  = 9,      /*!< EXTI Line3 Interrupt                                */
  EXTI4_IRQn                  = 10,     /*!< EXTI Line4 Interrupt                                */
  DMA1_Stream0_IRQn           = 11,     /*!< DMA1 Stream 0 global Interrupt                      */
  DMA1_Stream1_IRQn           = 12,     /*!< DMA1 Stream 1 global Interrupt                      */
  DMA1_Stream2_IRQn           = 13,     /*!< DMA1 Stream 2 global Interrupt                      */
  DMA1_Stream3_IRQn           = 14,     /*!< DMA1 Stream 3 global Interrupt                      */
  DMA1_Stream4_IRQn           = 15,     /*!< DMA1 Stream 4 global Interrupt                      */
  DMA1_Stream5_IRQn           = 16,     /*!< DMA1 Stream 5 global Interrupt                      */
  DMA1_Stream6_IRQn           = 17,     /*!< DMA1 Stream 6 global Interrupt                      */
  ADC_IRQn                    = 18,     /*!< ADC1, ADC2 and ADC3 global Interrupts               */
  CAN1_TX_IRQn                = 19,     /*!< CAN1 TX Interrupt                                   */
  CAN1_RX0_IRQn               = 20,     /*!< CAN1 RX0 Interrupt                                  */
  CAN1_RX1_IRQn               = 21,     /*!< CAN1 RX1 Interrupt                                  */
  CAN1_SCE_IRQn               = 22,     /*!< CAN1 SCE Interrupt                                  */
  EXTI9_5_IRQn                = 23,     /*!< External Line[9:5] Interrupts                       */
  TIM1_BRK_TIM9_IRQn          = 24,     /*!< TIM1 Break interrupt and TIM9 global interrupt      */
  TIM1_UP_TIM10_IRQn          = 25,     /*!< TIM1 Update Interrupt and TIM10 global interrupt    */
  TIM1_TRG_COM_TIM11_IRQn     = 26,     /*!< TIM1 Trigger and Commutation Interrupt and TIM11 global interrupt */
  TIM1_CC_IRQn                = 27,     /*!< TIM1 Capture Compare Interrupt                     */
  TIM2_IRQn                   = 28,     /*!< TIM2 global Interrupt                               */
  TIM3_IRQn                   = 29,     /*!< TIM3 global Interrupt                               */
  TIM4_IRQn                   = 30,     /*!< TIM4 global Interrupt                               */
  I2C1_EV_IRQn                = 31,     /*!< I2C1 Event Interrupt                               */
  I2C1_ER_IRQn                = 32,     /*!< I2C1 Error Interrupt                               */
  I2C2_EV_IRQn                = 33,     /*!< I2C2 Event Interrupt                               */
  I2C2_ER_IRQn                = 34,     /*!< I2C2 Error Interrupt                               */
  SPI1_IRQn                   = 35,     /*!< SPI1 global Interrupt                               */
  SPI2_IRQn                   = 36,     /*!< SPI2 global Interrupt                               */
  USART1_IRQn                 = 37,     /*!< USART1 global Interrupt                             */
  USART2_IRQn                 = 38,     /*!< USART2 global Interrupt                             */
  USART3_IRQn                 = 39,     /*!< USART3 global Interrupt                             */
  EXTI15_10_IRQn              = 40,     /*!< External Line[15:10] Interrupts                     */
  RTC_Alarm_IRQn              = 41,     /*!< RTC Alarm through EXTI Line Interrupt               */
  OTG_FS_WKUP_IRQn            = 42,     /*!< USB OTG FS Wakeup through EXTI line interrupt       */
  TIM8_BRK_TIM12_IRQn         = 43,     /*!< TIM8 Break interrupt and TIM12 global interrupt     */
  TIM8_UP_TIM13_IRQn          = 44,     /*!< TIM8 Update Interrupt and TIM13 global interrupt    */
  TIM8_TRG_COM_TIM14_IRQn     = 45,     /*!< TIM8 Trigger and Commutation Interrupt and TIM14 global interrupt */
  TIM8_CC_IRQn                = 46,     /*!< TIM8 Capture Compare Interrupt                     */
  DMA1_Stream7_IRQn           = 47,     /*!< DMA1 Stream7 Interrupt                              */
  FMC_IRQn                    = 48,     /*!< FMC global Interrupt                                */
  SDIO_IRQn                   = 49,     /*!< SDIO global Interrupt                               */
  TIM5_IRQn                   = 50,     /*!< TIM5 global Interrupt                               */
  SPI3_IRQn                   = 51,     /*!< SPI3 global Interrupt                               */
  UART4_IRQn                  = 52,     /*!< UART4 global Interrupt                              */
  UART5_IRQn                  = 53,     /*!< UART5 global Interrupt                              */
  TIM6_DAC_IRQn               = 54,     /*!< TIM6 global and DAC1&2 underrun error interrupts   */
  TIM7_IRQn                   = 55,     /*!< TIM7 global Interrupt                               */
  DMA2_Stream0_IRQn           = 56,     /*!< DMA2 Stream 0 global Interrupt                      */
  DMA2_Stream1_IRQn           = 57,     /*!< DMA2 Stream 1 global Interrupt                      */
  DMA2_Stream2_IRQn           = 58,     /*!< DMA2 Stream 2 global Interrupt                      */
  DMA2_Stream3_IRQn           = 59,     /*!< DMA2 Stream 3 global Interrupt                      */
  DMA2_Stream4_IRQn           = 60,     /*!< DMA2 Stream 4 global Interrupt                      */
  ETH_IRQn                    = 61,     /*!< Ethernet global Interrupt                           */
  ETH_WKUP_IRQn               = 62,     /*!< Ethernet Wakeup through EXTI line interrupt         */
  CAN2_TX_IRQn                = 63,     /*!< CAN2 TX Interrupt                                   */
  CAN2_RX0_IRQn               = 64,     /*!< CAN2 RX0 Interrupt                                  */
  CAN2_RX1_IRQn               = 65,     /*!< CAN2 RX1 Interrupt                                  */
  CAN2_SCE_IRQn               = 66,     /*!< CAN2 SCE Interrupt                                  */
  OTG_FS_IRQn                 = 67,     /*!< USB OTG FS global Interrupt                         */
  DMA2_Stream5_IRQn           = 68,     /*!< DMA2 Stream 5 global Interrupt                      */
  DMA2_Stream6_IRQn           = 69,     /*!< DMA2 Stream 6 global Interrupt                      */
  DMA2_Stream7_IRQn           = 70,     /*!< DMA2 Stream 7 global Interrupt                      */
  USART6_IRQn                 = 71,     /*!< USART6 global Interrupt                             */
  I2C3_EV_IRQn                = 72,     /*!< I2C3 event Interrupt                                */
  I2C3_ER_IRQn                = 73,     /*!< I2C3 error Interrupt                                */
  OTG_HS_EP1_OUT_IRQn         = 74,     /*!< USB OTG HS End Point 1 Out global Interrupt         */
  OTG_HS_EP1_IN_IRQn          = 75,     /*!< USB OTG HS End Point 1 In global Interrupt          */
  OTG_HS_WKUP_IRQn            = 76,     /*!< USB OTG HS Wakeup through EXTI interrupt            */
  OTG_HS_IRQn                 = 77,     /*!< USB OTG HS global Interrupt                         */
  DCMI_IRQn                   = 78,     /*!< DCMI global Interrupt                               */
  CRYP_IRQn                   = 79,     /*!< CRYP crypto global Interrupt                        */
  HASH_RNG_IRQn               = 80,     /*!< Hash and Rng global Interrupt                       */
  FPU_IRQn                    = 81,     /*!< FPU global Interrupt                                */
  UART7_IRQn                  = 82,     /*!< UART7 global Interrupt                              */
  UART8_IRQn                  = 83,     /*!< UART8 global Interrupt                              */
  SPI4_IRQn                   = 84,     /*!< SPI4 global Interrupt                               */
  SPI5_IRQn                   = 85,     /*!< SPI5 global Interrupt                               */
  SPI6_IRQn                   = 86,     /*!< SPI6 global Interrupt                               */
  SAI1_IRQn                   = 87,     /*!< SAI1 global Interrupt                               */
  LTDC_IRQn                   = 88,     /*!< LTDC global Interrupt                               */
  LTDC_ER_IRQn                = 89,     /*!< LTDC Error global Interrupt                         */
  DMA2D_IRQn                  = 90,     /*!< DMA2D global Interrupt                              */
  QUADSPI_IRQn                = 91,     /*!< QUADSPI global Interrupt                            */
  DSI_IRQn                    = 92,     /*!< DSI global Interrupt                                */
};

/* ========== RCC 配置结构体 ========== */
typedef struct
{
  uint32_t OscillatorType;       /*!< 使能的振荡器类型 */
  uint32_t HSEState;             /*!< HSE状态 */
  uint32_t LSEState;             /*!< LSE状态 */
  uint32_t HSICalibrationValue;  /*!< HSI校准值 */
  uint32_t LSIState;             /*!< LSI状态 */
  struct {
    uint32_t PLLState;           /*!< PLL状态 */
    uint32_t PLLSource;          /*!< PLL时钟源 */
    uint32_t PLLM;               /*!< PLL分频系数M */
    uint32_t PLLN;               /*!< PLL倍频系数N */
    uint32_t PLLP;               /*!< PLL分频系数P */
    uint32_t PLLQ;               /*!< PLL分频系数Q */
  } PLL;
} RCC_OscInitTypeDef;

typedef struct
{
  uint32_t ClockType;            /*!< 要配置的时钟类型 */
  uint32_t SYSCLKSource;         /*!< 系统时钟源 */
  uint32_t AHBCLKDivider;        /*!< AHB时钟分频 */
  uint32_t APB1CLKDivider;       /*!< APB1时钟分频 */
  uint32_t APB2CLKDivider;       /*!< APB2时钟分频 */
} RCC_ClkInitTypeDef;

/* ========== RCC 配置常量 ========== */
#define RCC_OSCILLATORTYPE_NONE       0x00000000U
#define RCC_OSCILLATORTYPE_HSE        0x00000001U
#define RCC_OSCILLATORTYPE_HSI        0x00000002U
#define RCC_OSCILLATORTYPE_LSE        0x00000004U
#define RCC_OSCILLATORTYPE_LSI        0x00000008U

/* ========== RCC 寄存器定义 ========== */
#define RCC_CR_HSEBYP                 ((uint32_t)0x00040000U)
#define RCC_CR_HSEON                  ((uint32_t)0x00010000U)
#define RCC_CR_HSERDY                 ((uint32_t)0x00020000U)
#define RCC_CR_PLLON                  ((uint32_t)0x01000000U)
#define RCC_CR_PLLRDY                 ((uint32_t)0x02000000U)

#define RCC_PLLCFGR_PLLSRC            ((uint32_t)0x00400000U)
#define RCC_PLLCFGR_PLLM              ((uint32_t)0x0000003FU)
#define RCC_PLLCFGR_PLLN              ((uint32_t)0x00007FC0U)
#define RCC_PLLCFGR_PLLP              ((uint32_t)0x00030000U)
#define RCC_PLLCFGR_PLLQ              ((uint32_t)0x0F000000U)

#define RCC_CFGR_SW                   ((uint32_t)0x00000003U)
#define RCC_CFGR_SWS                  ((uint32_t)0x0000000CU)
#define RCC_CFGR_HPRE                 ((uint32_t)0x000000F0U)
#define RCC_CFGR_PPRE1                ((uint32_t)0x00001C00U)
#define RCC_CFGR_PPRE2                ((uint32_t)0x0000E000U)

#define RCC_CFGR_SW_HSI               ((uint32_t)0x00000000U)
#define RCC_CFGR_SW_HSE               ((uint32_t)0x00000001U)
#define RCC_CFGR_SW_PLL               ((uint32_t)0x00000002U)
#define RCC_CFGR_SWS_HSI              ((uint32_t)0x00000000U)
#define RCC_CFGR_SWS_HSE              ((uint32_t)0x00000004U)
#define RCC_CFGR_SWS_PLL              ((uint32_t)0x00000008U)

/* ========== HSI/HSE 值 ========== */
#define HSI_VALUE                    16000000U  /* HSI默认16MHz */
#define HSE_VALUE                    8000000U   /* HSE默认8MHz */

/* ========== 超时定义 ========== */
#define HSE_TIMEOUT_VALUE             5000U     /* HSE超时5秒 */
#define PLL_TIMEOUT_VALUE             5000U     /* PLL超时5秒 */
#define CLOCKSWITCH_TIMEOUT_VALUE     5000U     /* 时钟切换超时5秒 */

#define RCC_HSE_OFF                   0x00000000U
#define RCC_HSE_ON                    0x00010000U

#define RCC_LSE_OFF                   0x00000000U
#define RCC_LSE_ON                    0x00000001U

#define RCC_PLL_NONE                  0x00000000U
#define RCC_PLL_OFF                   0x00000000U
#define RCC_PLL_ON                    0x00010000U
#define RCC_PLLSOURCE_HSE             0x00400000U
#define RCC_PLLSOURCE_HSI             0x00000000U
#define RCC_PLLP_DIV2                 0x00000002U
#define RCC_PLLP_DIV4                 0x00000004U
#define RCC_PLLP_DIV6                 0x00000006U
#define RCC_PLLP_DIV8                 0x00000008U

#define RCC_CLOCKTYPE_NONE            0x00000000U
#define RCC_CLOCKTYPE_HCLK            0x00000001U
#define RCC_CLOCKTYPE_SYSCLK          0x00000002U
#define RCC_CLOCKTYPE_PCLK1           0x00000004U
#define RCC_CLOCKTYPE_PCLK2           0x00000008U

#define RCC_SYSCLKSOURCE_HSI          0x00000000U
#define RCC_SYSCLKSOURCE_HSE          0x00000001U
#define RCC_SYSCLKSOURCE_PLLCLK       0x00000002U

#define RCC_SYSCLK_DIV1               0x00000000U
#define RCC_HCLK_DIV1                 0x00000000U
#define RCC_HCLK_DIV2                 0x00000080U
#define RCC_HCLK_DIV4                 0x00000100U
#define RCC_HCLK_DIV8                 0x00000180U
#define RCC_HCLK_DIV16                0x00000200U
#define RCC_APB1_DIV1                 0x00000000U
#define RCC_APB1_DIV2                 0x00001000U
#define RCC_APB1_DIV4                 0x00002000U
#define RCC_APB1_DIV8                 0x00003000U
#define RCC_APB1_DIV16                0x00004000U
#define RCC_APB2_DIV1                 0x00000000U
#define RCC_APB2_DIV2                 0x00008000U
#define RCC_APB2_DIV4                 0x00010000U
#define RCC_APB2_DIV8                 0x00018000U
#define RCC_APB2_DIV16                0x00020000U

#define RCC_CR_HSION_BB               (PERIPH_BB_BASE + 0x4000U + 0x18U * 32U + 0x00U)
#define RCC_CR_HSEON_BB               (PERIPH_BB_BASE + 0x4000U + 0x18U * 32U + 0x10U)
#define RCC_CR_PLLON_BB               (PERIPH_BB_BASE + 0x4000U + 0x18U * 32U + 0x18U)
#define RCC_CR_HSIRDY_BB              (PERIPH_BB_BASE + 0x4000U + 0x18U * 32U + 0x01U)
#define RCC_CR_HSERDY_BB              (PERIPH_BB_BASE + 0x4000U + 0x18U * 32U + 0x11U)
#define RCC_CR_PLLRDY_BB              (PERIPH_BB_BASE + 0x4000U + 0x18U * 32U + 0x19U)
#define PERIPH_BB_BASE                0xA0000000U

#define FLASH_LATENCY_0              0x00000000U
#define FLASH_LATENCY_1              0x00000001U
#define FLASH_LATENCY_2              0x00000002U
#define FLASH_LATENCY_3              0x00000003U
#define FLASH_LATENCY_4              0x00000004U
#define FLASH_LATENCY_5              0x00000005U
#define FLASH_LATENCY_6              0x00000006U
#define FLASH_LATENCY_7              0x00000007U

/* ========== EXTI 配置常量 ========== */
#define EXTI_LINE_0                  0x00000001U
#define EXTI_LINE_1                  0x00000002U
#define EXTI_LINE_2                  0x00000004U
#define EXTI_LINE_3                  0x00000008U
#define EXTI_LINE_4                  0x00000010U
#define EXTI_LINE_5                  0x00000020U
#define EXTI_LINE_6                  0x00000040U
#define EXTI_LINE_7                  0x00000080U
#define EXTI_LINE_8                  0x00000100U
#define EXTI_LINE_9                  0x00000200U
#define EXTI_LINE_10                 0x00000400U
#define EXTI_LINE_11                 0x00000800U
#define EXTI_LINE_12                 0x00001000U
#define EXTI_LINE_13                 0x00002000U
#define EXTI_LINE_14                 0x00004000U
#define EXTI_LINE_15                 0x00008000U

/* ========== GPIO 扩展模式定义 ========== */
#define GPIO_MODE_IT_RISING          0x10110000U
#define GPIO_MODE_IT_FALLING         0x10210000U
#define GPIO_MODE_IT_RISING_FALLING  0x10310000U

/* ========== NVIC 和 EXTI 函数声明 ========== */
void HAL_NVIC_SetPriority(IRQn_Type IRQn, uint32_t PreemptPriority, uint32_t SubPriority);
void HAL_NVIC_EnableIRQ(IRQn_Type IRQn);
void HAL_GPIO_EXTI_IRQHandler(uint16_t GPIO_Pin);
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin);

/* ========== RCC 函数声明 ========== */
HAL_StatusTypeDef HAL_RCC_OscConfig(RCC_OscInitTypeDef *RCC_OscInitStruct);
HAL_StatusTypeDef HAL_RCC_ClockConfig(RCC_ClkInitTypeDef *RCC_ClkInitStruct, uint32_t FLatency);
uint32_t HAL_RCC_GetSysClockFreq(void);

/* ========== PWR CR 寄存器定义 ========== */
#define PWR_CR_VOS                   ((uint32_t)0x0000C000U)

/* ========== 时钟使能宏（扩展） ========== */
#define __HAL_RCC_SYSCFG_CLK_ENABLE()   do { \
                                        RCC->APB2ENR |= (1U << 14); \
                                      } while(0)

/* ========== SYSCFG EXTI 宏 ========== */
#define SYSCFG_EXTI_PORTA           0x0000U
#define SYSCFG_EXTI_PORTB           0x0001U
#define SYSCFG_EXTI_PORTC           0x0002U
#define SYSCFG_EXTI_PORTD           0x0003U
#define SYSCFG_EXTI_PORTE           0x0004U
#define SYSCFG_EXTI_PORTF           0x0005U
#define SYSCFG_EXTI_PORTG           0x0006U
#define SYSCFG_EXTI_PORTH           0x0007U

/* ========== SYSCFG_EXTICR 寄存器定义 ========== */
#define SYSCFG_EXTICR1_EXTI0_Msk    (0x000FU << 0)
#define SYSCFG_EXTICR1_EXTI0_Pos    (0)
#define SYSCFG_EXTICR2_EXTI4_Msk    (0x000FU << 0)
#define SYSCFG_EXTICR2_EXTI4_Pos    (0)

/* ========== 中断控制宏 ========== */
#define __disable_irq()             __asm volatile("cpsid i" : : : "memory")
#define __enable_irq()              __asm volatile("cpsie i" : : : "memory")

/* ========== PWR 定义 ========== */
#define PWR_BASE                     (APB1PERIPH_BASE + 0x7000)
#define PWR                         ((PWR_TypeDef *) PWR_BASE)

typedef struct
{
  __IO uint32_t CR;     /* PWR 电源控制寄存器 */
  __IO uint32_t CSR;    /* PWR 电源控制/状态寄存器 */
} PWR_TypeDef;

#define PWR_REGULATOR_VOLTAGE_SCALE1  0x00004000U
#define PWR_REGULATOR_VOLTAGE_SCALE2  0x00008000U
#define PWR_REGULATOR_VOLTAGE_SCALE3  0x0000C000U

#define __HAL_RCC_PWR_CLK_ENABLE()    (RCC->APB1ENR |= (1U << 28))

#define __HAL_PWR_VOLTAGESCALING_CONFIG(__REGULATOR__)  do { \
                                                     __IO uint32_t tmp = PWR->CR & ~PWR_CR_VOS; \
                                                     PWR->CR = tmp | (__REGULATOR__); \
                                                   } while(0)

#ifdef __cplusplus
}
#endif

#endif /* __STM32F4xx_HAL_EXT_H */
