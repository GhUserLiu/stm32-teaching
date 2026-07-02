/**
  ******************************************************************************
  * @file    stm32f4xx_hal.c
  * @brief   STM32F4xx HAL库函数实现 - 简化版
  ******************************************************************************
  */

#include "stm32f4xx_hal.h"

/* ========== 全局变量 ========== */
volatile uint32_t uwTick = 0;
volatile uint32_t uwTickPrio = 0;

/* ========== HAL初始化函数 ========== */

/**
  * @brief  初始化HAL库
  * @retval HAL状态
  */
HAL_StatusTypeDef HAL_Init(void)
{
  /* 初始化SysTick（1ms中断）
   * 注意：使用默认HSI时钟 (16MHz)，如需168MHz需配置PLL
   */
  HAL_SYSTICK_Config(16000000 / 1000);

  return HAL_OK;
}

/**
  * @brief  反初始化HAL库
  * @retval HAL状态
  */
HAL_StatusTypeDef HAL_DeInit(void)
{
  return HAL_OK;
}

/**
  * @brief  配置SysTick
  * @param  TicksNumb: SysTick重载值
  * @retval HAL状态
  */
HAL_StatusTypeDef HAL_SYSTICK_Config(uint32_t TicksNumb)
{
  if ((TicksNumb - 1) > 0xFFFFFFUL)
  {
    return HAL_ERROR;
  }

  SysTick->LOAD  = TicksNumb - 1;
  NVIC_SetPriority(SysTick_IRQn, 0);
  SysTick->VAL   = 0;
  SysTick->CTRL  = SysTick_CTRL_CLKSOURCE_Msk |
                    SysTick_CTRL_TICKINT_Msk |
                    SysTick_CTRL_ENABLE_Msk;

  return HAL_OK;
}

/**
  * @brief  增加全局计数器（在SysTick中断中调用）
  * @retval 无
  */
void HAL_IncTick(void)
{
  uwTick++;
}

/**
  * @brief  获取全局计数器值
  * @retval 当前计数值（毫秒）
  */
uint32_t HAL_GetTick(void)
{
  return uwTick;
}

/**
  * @brief  毫秒级延时
  * @param  Delay: 延时时间（毫秒）
  * @retval 无
  */
void HAL_Delay(__IO uint32_t Delay)
{
  uint32_t tickstart = HAL_GetTick();
  uint32_t wait = Delay;

  while ((HAL_GetTick() - tickstart) < wait);
}

/**
  * @brief  SysTick中断处理函数
  * @retval 无
  */
void SysTick_Handler(void)
{
  HAL_IncTick();
}

/* ========== GPIO函数实现 ========== */

/**
  * @brief  初始化GPIO引脚
  * @param  GPIOx: GPIO端口指针（GPIOA, GPIOB等）
  * @param  GPIO_InitStruct: GPIO初始化结构体指针
  * @retval 无
  */
void HAL_GPIO_Init(GPIO_TypeDef* GPIOx, GPIO_InitTypeDef* GPIO_InitStruct)
{
  uint32_t pinpos;
  uint32_t pos;
  uint32_t currentpin;

  /* 配置每个引脚 */
  for (pinpos = 0; pinpos < 16; pinpos++)
  {
    pos = ((uint32_t)0x01) << pinpos;
    currentpin = (GPIO_InitStruct->Pin) & pos;

    if (currentpin == pos)
    {
      uint32_t tmp;

      /* 配置模式 */
      tmp = GPIOx->MODER;
      tmp &= ~(0x03U << (pinpos * 2));

      if (GPIO_InitStruct->Mode == GPIO_MODE_OUTPUT_PP)
      {
        tmp |= (0x01U << (pinpos * 2));
      }
      else if (GPIO_InitStruct->Mode == GPIO_MODE_OUTPUT_OD)
      {
        tmp |= (0x01U << (pinpos * 2));
        /* 配置输出类型 */
        GPIOx->OTYPER |= (0x01U << pinpos);
      }
      else if (GPIO_InitStruct->Mode == GPIO_MODE_AF_PP)
      {
        tmp |= (0x02U << (pinpos * 2));
      }
      else if (GPIO_InitStruct->Mode == GPIO_MODE_AF_OD)
      {
        tmp |= (0x02U << (pinpos * 2));
        GPIOx->OTYPER |= (0x01U << pinpos);
      }
      else if (GPIO_InitStruct->Mode == GPIO_MODE_ANALOG)
      {
        tmp |= (0x03U << (pinpos * 2));
      }

      GPIOx->MODER = tmp;

      /* 配置速度 */
      tmp = GPIOx->OSPEEDR;
      tmp &= ~(0x03U << (pinpos * 2));
      tmp |= (GPIO_InitStruct->Speed << (pinpos * 2));
      GPIOx->OSPEEDR = tmp;

      /* 配置上拉/下拉 */
      tmp = GPIOx->PUPDR;
      tmp &= ~(0x03U << (pinpos * 2));
      tmp |= (GPIO_InitStruct->Pull << (pinpos * 2));
      GPIOx->PUPDR = tmp;
    }
  }
}

/**
  * @brief  写GPIO引脚
  * @param  GPIOx: GPIO端口指针
  * @param  GPIO_Pin: GPIO引脚
  * @param  PinState: 引脚状态（GPIO_PIN_SET或GPIO_PIN_RESET）
  * @retval 无
  */
void HAL_GPIO_WritePin(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin, GPIO_PinState PinState)
{
  if (PinState == GPIO_PIN_SET)
  {
    GPIOx->BSRR = GPIO_Pin;
  }
  else
  {
    GPIOx->BSRR = (uint32_t)GPIO_Pin << 16;
  }
}

/**
  * @brief  读GPIO引脚
  * @param  GPIOx: GPIO端口指针
  * @param  GPIO_Pin: GPIO引脚
  * @retval 引脚状态（GPIO_PIN_SET或GPIO_PIN_RESET）
  */
GPIO_PinState HAL_GPIO_ReadPin(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin)
{
  GPIO_PinState bitstatus;

  if ((GPIOx->IDR & GPIO_Pin) != (uint32_t)GPIO_PIN_RESET)
  {
    bitstatus = GPIO_PIN_SET;
  }
  else
  {
    bitstatus = GPIO_PIN_RESET;
  }

  return bitstatus;
}

/**
  * @brief  翻转GPIO引脚状态
  * @param  GPIOx: GPIO端口指针
  * @param  GPIO_Pin: GPIO引脚
  * @retval 无
  */
void HAL_GPIO_TogglePin(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin)
{
  uint32_t odr = GPIOx->ODR;
  GPIOx->BSRR = ((odr & GPIO_Pin) << 16) | (~odr & GPIO_Pin);
}
