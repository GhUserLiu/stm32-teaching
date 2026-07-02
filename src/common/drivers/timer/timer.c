/**
  ******************************************************************************
  * @file    : timer.c
  * @brief   : 定时器驱动实现 - 遵循HAL库规范
  * @author  : 项目开发者
  * @date    : 2026-06-11
  ******************************************************************************
  * @attention
  *
  * 本驱动基于STM32 HAL库实现，提供简化的定时器接口
  * 支持基本定时、DWT精准延时等功能
  *
  ******************************************************************************
  */

/* ========== Includes ========== */
#include "timer.h"

/* ========== Private Macros ========== */
#define DWT_CYCCNT       (*(volatile uint32_t*)DWT_CYCCNT_ADDR)
#define DWT_CONTROL      (*(volatile uint32_t*)DWT_CONTROL_ADDR)

/* ========== Private Variables ========== */
static DWT_Handle_t dwt_handle = {0};

/* ========== Public Function Definitions ========== */

/**
  * @brief  初始化定时器
  * @param  htim: 定时器句柄指针
  * @param  instance: 定时器外设实例（TIM1, TIM2, etc.）
  * @param  config: 定时器配置指针
  * @retval Timer_State_t: 初始化状态
  */
Timer_State_t Timer_Init(Timer_HandleTypeDef_t *htim, TIM_TypeDef *instance, const Timer_Config_t *config)
{
    if (htim == NULL || config == NULL)
    {
        return TIMER_STATE_ERROR;
    }

    /* 保存配置 */
    htim->config = *config;
    htim->handle.Instance = instance;
    htim->is_running = false;
    htim->counter = 0;
    htim->tick_count = 0;

    /* 配置定时器参数 */
    htim->handle.Init.Period = config->period;
    htim->handle.Init.Prescaler = config->prescaler;
    htim->handle.Init.ClockDivision = config->clock_division;
    htim->handle.Init.CounterMode = config->counter_mode;
    htim->handle.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;

    /* 初始化定时器 */
    if (HAL_TIM_Base_Init(&htim->handle) != HAL_OK)
    {
        return TIMER_STATE_ERROR;
    }

    return TIMER_STATE_OK;
}

/**
  * @brief  反初始化定时器
  * @param  htim: 定时器句柄指针
  * @retval None
  */
void Timer_DeInit(Timer_HandleTypeDef_t *htim)
{
    if (htim != NULL)
    {
        HAL_TIM_Base_DeInit(&htim->handle);
        htim->is_running = false;
    }
}

/**
  * @brief  启动定时器
  * @param  htim: 定时器句柄指针
  * @retval Timer_State_t: 启动状态
  */
Timer_State_t Timer_Start(Timer_HandleTypeDef_t *htim)
{
    if (htim == NULL)
    {
        return TIMER_STATE_ERROR;
    }

    if (HAL_TIM_Base_Start(&htim->handle) != HAL_OK)
    {
        return TIMER_STATE_ERROR;
    }

    htim->is_running = true;
    return TIMER_STATE_OK;
}

/**
  * @brief  停止定时器
  * @param  htim: 定时器句柄指针
  * @retval Timer_State_t: 停止状态
  */
Timer_State_t Timer_Stop(Timer_HandleTypeDef_t *htim)
{
    if (htim == NULL)
    {
        return TIMER_STATE_ERROR;
    }

    if (HAL_TIM_Base_Stop(&htim->handle) != HAL_OK)
    {
        return TIMER_STATE_ERROR;
    }

    htim->is_running = false;
    return TIMER_STATE_OK;
}

/**
  * @brief  检查定时器是否正在运行
  * @param  htim: 定时器句柄指针
  * @retval bool: true=运行中, false=已停止
  */
bool Timer_IsRunning(Timer_HandleTypeDef_t *htim)
{
    return (htim != NULL && htim->is_running);
}

/**
  * @brief  毫秒级延时（基于HAL库）
  * @param  ms: 延时时间（毫秒）
  * @retval None
  */
void Timer_Delay_ms(uint32_t ms)
{
    HAL_Delay(ms);
}

/**
  * @brief  微秒级延时（占位，实际使用DWT）
  * @param  us: 延时时间（微秒）
  * @retval None
  * @note   请使用 DWT_Delay_us() 实现精准延时
  */
void Timer_Delay_us(uint32_t us)
{
    /* 占位函数，建议使用DWT实现精准微秒延时 */
    /* HAL库不提供微秒级延时，使用DWT替代 */
    DWT_Delay_us(us);
}

/* ========== DWT精准延时功能 ========== */

/**
  * @brief  初始化DWT周期计数器
  * @retval None
  * @note   使用DWT（Data Watchpoint and Trace）单元实现精准延时
  */
void DWT_Init(void)
{
    /* 使能DWT计数器 */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT_CONTROL |= DWT_CYCCNT_EN_BIT;
    DWT_CYCCNT = 0;

    /* 计算时钟参数（假设系统时钟为168MHz） */
    dwt_handle.clock_freq = SystemCoreClock;  /* 从HAL库获取系统时钟频率 */
    dwt_handle.us_per_tick = 1000000u / dwt_handle.clock_freq;
}

/**
  * @brief  获取DWT周期计数器当前值
  * @retval uint32_t: 当前周期计数值
  */
uint32_t DWT_GetCycle(void)
{
    return DWT_CYCCNT;
}

/**
  * @brief  DWT微秒级精准延时
  * @param  us: 延时时间（微秒）
  * @retval None
  * @note   基于DWT周期计数器实现高精度延时
  */
void DWT_Delay_us(uint32_t us)
{
    uint32_t start_tick = DWT_GetCycle();
    uint32_t delay_ticks = us * (dwt_handle.clock_freq / 1000000u);

    /* 等待延迟时间到达 */
    while ((DWT_GetCycle() - start_tick) < delay_ticks)
    {
        /* 等待 */
    }
}

/* ========== 定时器中断和回调函数 ========== */

/**
  * @brief  定时器周期溢出回调函数
  * @param  htim: HAL定时器句柄
  * @retval None
  */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    /* 用户可在此添加定时器中断处理代码 */

    /* 示例：更新软件计数器 */
    // if (htim->Instance == TIM2)
    // {
    //     user_counter++;
    // }
}
