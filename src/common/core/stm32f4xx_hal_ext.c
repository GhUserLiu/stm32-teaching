/**
 ******************************************************************************
 * @file    stm32f4xx_hal_ext.c
 * @brief   STM32F4xx HAL库扩展版实现
 ******************************************************************************
 */

#include <stddef.h>
#include "stm32f4xx_hal.h"
#include "stm32f4xx_hal_ext.h"

/* ========== 外部变量声明 ========== */
extern volatile uint32_t uwTick;

/* ========== RCC寄存器访问宏 ========== */
#define RCC_CR_HSIRDY                ((uint32_t)RCC_CR_HSIRDY_BB)
#define RCC_CR_HSERDY                ((uint32_t)RCC_CR_HSERDY_BB)
#define RCC_CR_PLLRDY                ((uint32_t)RCC_CR_PLLRDY_BB)

/* RCC已在stm32f4xx_hal.h中定义为宏，不需要extern声明 */

/* ========== RCC 全局变量 ========== */
uint32_t SystemCoreClock = 16000000;  /* 默认HSI 16MHz */
const uint8_t AHBPrescTable[16] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 6, 7, 8, 9};
const uint8_t APBPrescTable[8]  = {0, 0, 0, 0, 1, 2, 3, 4};

/* ========== HAL_RCC_OscConfig - 配置振荡器 ========== */
HAL_StatusTypeDef HAL_RCC_OscConfig(RCC_OscInitTypeDef *RCC_OscInitStruct)
{
  uint32_t tickstart;

  /* 校验参数 */
  if (RCC_OscInitStruct == NULL)
  {
    return HAL_ERROR;
  }

  /* 配置HSE */
  if ((RCC_OscInitStruct->OscillatorType & RCC_OSCILLATORTYPE_HSE) != 0U)
  {
    /* 配置HSE */
    if ((RCC_OscInitStruct->HSEState) != RCC_HSE_OFF)
    {
      /* 使能HSE */
      RCC->CR |= RCC_CR_HSEON;

      /* 等待HSE就绪 */
      tickstart = HAL_GetTick();
      while ((RCC->CR & RCC_CR_HSERDY) == 0U)
      {
        if ((HAL_GetTick() - tickstart) > HSE_TIMEOUT_VALUE)
        {
          return HAL_TIMEOUT;
        }
      }
    }
    else
    {
      /* 禁用HSE */
      RCC->CR &= ~RCC_CR_HSEON;

      /* 等待HSE禁用完成 */
      tickstart = HAL_GetTick();
      while ((RCC->CR & RCC_CR_HSERDY) != 0U)
      {
        if ((HAL_GetTick() - tickstart) > HSE_TIMEOUT_VALUE)
        {
          return HAL_TIMEOUT;
        }
      }
    }
  }

  /* 配置PLL */
  if ((RCC_OscInitStruct->OscillatorType & RCC_OSCILLATORTYPE_HSE) != 0U)
  {
    if (RCC_OscInitStruct->PLL.PLLState != RCC_PLL_NONE)
    {
      /* 禁用PLL */
      RCC->CR &= ~RCC_CR_PLLON;

      /* 等待PLL禁用完成 */
      tickstart = HAL_GetTick();
      while ((RCC->CR & RCC_CR_PLLRDY) != 0U)
      {
        if ((HAL_GetTick() - tickstart) > PLL_TIMEOUT_VALUE)
        {
          return HAL_TIMEOUT;
        }
      }

      /* 配置PLL */
      RCC->PLLCFGR = (RCC_OscInitStruct->PLL.PLLM) |
                     ((RCC_OscInitStruct->PLL.PLLN) << 6) |
                     (((RCC_OscInitStruct->PLL.PLLP >> 1) - 1) << 16) |
                     ((RCC_OscInitStruct->PLL.PLLQ) << 24) |
                     (RCC_OscInitStruct->PLL.PLLSource);

      /* 使能PLL */
      RCC->CR |= RCC_CR_PLLON;

      /* 等待PLL就绪 */
      tickstart = HAL_GetTick();
      while ((RCC->CR & RCC_CR_PLLRDY) == 0U)
      {
        if ((HAL_GetTick() - tickstart) > PLL_TIMEOUT_VALUE)
        {
          return HAL_TIMEOUT;
        }
      }
    }
  }

  return HAL_OK;
}

/* ========== HAL_RCC_ClockConfig - 配置系统时钟 ========== */
HAL_StatusTypeDef HAL_RCC_ClockConfig(RCC_ClkInitTypeDef *RCC_ClkInitStruct, uint32_t FLatency)
{
  uint32_t tickstart;

  /* 校验参数 */
  if (RCC_ClkInitStruct == NULL)
  {
    return HAL_ERROR;
  }

  /* 配置APB和AHB分频 */
  RCC->CFGR &= ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2);
  RCC->CFGR |= (RCC_ClkInitStruct->AHBCLKDivider) |
               (RCC_ClkInitStruct->APB1CLKDivider) |
               (RCC_ClkInitStruct->APB2CLKDivider << 3);

  /* 配置系统时钟源 */
  RCC->CFGR &= ~RCC_CFGR_SW;
  RCC->CFGR |= RCC_ClkInitStruct->SYSCLKSource;

  /* 等待时钟切换完成 */
  tickstart = HAL_GetTick();
  while ((RCC->CFGR & RCC_CFGR_SWS) != (RCC_ClkInitStruct->SYSCLKSource << 2))
  {
    if ((HAL_GetTick() - tickstart) > CLOCKSWITCH_TIMEOUT_VALUE)
    {
      return HAL_TIMEOUT;
    }
  }

  /* 更新SystemCoreClock */
  SystemCoreClock = HAL_RCC_GetSysClockFreq() >> AHBPrescTable[(RCC->CFGR & RCC_CFGR_HPRE) >> 4];

  /* 配置Flash延迟 */
  (void)FLatency;

  return HAL_OK;
}

/* ========== HAL_RCC_GetSysClockFreq - 获取系统时钟频率 ========== */
uint32_t HAL_RCC_GetSysClockFreq(void)
{
  uint32_t pllvco = 0, pllp = 2, pllsource = 0, pllm = 2;
  uint32_t sysclockfreq = 0;

  /* 获取PLL源 */
  pllsource = (RCC->PLLCFGR & RCC_PLLCFGR_PLLSRC);

  if ((RCC->CFGR & RCC_CFGR_SWS) == 0x04U)  /* PLL作为系统时钟 */
  {
    /* PLLM */
    pllm = RCC->PLLCFGR & RCC_PLLCFGR_PLLM;

    /* PLLVCO = (HSE_VALUE or HSI_VALUE / PLLM) * PLLN */
    if (pllsource == 0x00U)  /* HSI */
    {
      pllvco = (HSI_VALUE / pllm) * ((RCC->PLLCFGR & RCC_PLLCFGR_PLLN) >> 6);
    }
    else  /* HSE */
    {
      pllvco = (HSE_VALUE / pllm) * ((RCC->PLLCFGR & RCC_PLLCFGR_PLLN) >> 6);
    }

    /* PLLP */
    pllp = (((RCC->PLLCFGR & RCC_PLLCFGR_PLLP) >> 16) + 1U) * 2U;

    /* 系统时钟 = PLLVCO / PLLP */
    sysclockfreq = pllvco / pllp;
  }
  else if ((RCC->CFGR & RCC_CFGR_SWS) == 0x08U)  /* HSE作为系统时钟 */
  {
    sysclockfreq = HSE_VALUE;
  }
  else  /* HSI作为系统时钟 */
  {
    sysclockfreq = HSI_VALUE;
  }

  return sysclockfreq;
}

/* ========== HAL_NVIC_SetPriority - 设置中断优先级 ========== */
void HAL_NVIC_SetPriority(IRQn_Type IRQn, uint32_t PreemptPriority, uint32_t SubPriority)
{
  uint32_t prioritygroup = 0x00;

  /* 校验参数 */
  if ((int32_t)IRQn < 0)
  {
    /* Cortex-M4内核中断 */
    SCB->SHP[((uint32_t)(IRQn) & 0xF) - 4] = (PreemptPriority << (8 - __NVIC_PRIO_BITS));
  }
  else
  {
    /* 设备特定中断 */
    prioritygroup = NVIC->IP[(((uint32_t)IRQn) >> 2U)];
    NVIC->IP[((uint32_t)IRQn)] = (uint8_t)(PreemptPriority << (8 - __NVIC_PRIO_BITS));
  }
}

/* ========== HAL_NVIC_EnableIRQ - 使能中断 ========== */
void HAL_NVIC_EnableIRQ(IRQn_Type IRQn)
{
  /* 校验参数 */
  if ((int32_t)IRQn >= 0)
  {
    /* 设备特定中断 */
    NVIC->ISER[(((uint32_t)IRQn) >> 5U)] = (1U << (((uint32_t)IRQn) & 0x1FU));
  }
}

/* ========== HAL_GPIO_EXTI_IRQHandler - EXTI中断处理函数 ========== */
void HAL_GPIO_EXTI_IRQHandler(uint16_t GPIO_Pin)
{
  /* 清除EXTI中断标志 */
  EXTI->PR = GPIO_Pin;

  /* 调用用户回调函数（弱定义，可被用户覆盖） */
  HAL_GPIO_EXTI_Callback(GPIO_Pin);
}

/* ========== HAL_GPIO_EXTI_Callback - EXTI回调函数（弱定义） ========== */
__weak void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
  /* 防止未使用警告 */
  (void)GPIO_Pin;

  /* 这个函数应该被用户代码重新实现 */
}
