/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : STM32F407 嵌入式教学平台项目模板 - 遵循 HAL 库规范
  * @author         : 项目开发者
  * @date           : 2026-06-11
  ******************************************************************************
  * @attention
  *
  * 本项目统一使用 STM32 HAL 库进行开发
  * 请遵循 docs/guides/CODING_STYLE.md 中的代码规范
  *
  ******************************************************************************
  */

/* ========== Includes ========== */
#include <stdint.h>
#include "stm32f4xx_hal.h"
#include "board.h"
#include "config.h"

/* ========== Private Macros ========== */
#define ERROR_LED_PIN    BOARD_LED0_PIN
#define ERROR_LED_PORT   BOARD_LED0_PORT

/* ========== Private Type Definitions ========== */
typedef enum {
    STATE_INIT = 0,
    STATE_RUNNING,
    STATE_ERROR
} SystemState_t;

/* ========== Global Variables ========== */
volatile SystemState_t system_state = STATE_INIT;

/* ========== Private Variables ========== */
static uint32_t error_count = 0;

/* ========== Private Function Prototypes ========== */
static void Error_Handler(void);
static void SystemClock_Config(void);
static void GPIO_Init(void);

/* ========== Public Function Definitions ========== */

/**
  * @brief  系统时钟配置
  * @retval None
  * @note   默认使用HSI时钟，可根据需要配置PLL
  */
void SystemClock_Config(void)
{
    /* 使用默认HSI时钟（16MHz）
     * 如需更高性能，请配置PLL：
     * - PLL源：HSI或HSE
     * - PLL倍频：可达168MHz
     * - 参考STM32 HAL库时钟配置示例
     */
}

/**
  * @brief  GPIO初始化
  * @retval None
  */
void GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    /* 使能GPIO时钟 */
    __HAL_RCC_GPIOF_CLK_ENABLE();

    /* TODO: 根据项目需求配置GPIO引脚 */

    /* 示例：配置LED引脚为输出 */
    GPIO_InitStruct.Pin = BOARD_LED0_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;

    if (HAL_GPIO_Init(BOARD_LED0_PORT, &GPIO_InitStruct) != HAL_OK)
    {
        Error_Handler();
    }
}

/**
  * @brief  主函数
  * @retval int: 程序返回值（应为0）
  */
int main(void)
{
    /* HAL库初始化 */
    if (HAL_Init() != HAL_OK)
    {
        Error_Handler();
    }

    /* 系统时钟配置 */
    SystemClock_Config();

    /* GPIO初始化 */
    GPIO_Init();

    /* 系统状态更新 */
    system_state = STATE_RUNNING;

    /* ========== 主循环 ========== */
    while (1)
    {
        /* TODO: 添加你的应用代码 */

        /* 示例：简单的LED闪烁 */
        HAL_GPIO_TogglePin(BOARD_LED0_PORT, BOARD_LED0_PIN);
        HAL_Delay(MAIN_LOOP_DELAY);
    }

    /* 不应该到达这里 */
    return 0;
}

/* ========== Private Function Definitions ========== */

/**
  * @brief  错误处理函数
  * @retval None
  * @note   当发生严重错误时调用此函数
  */
static void Error_Handler(void)
{
    /* 禁用中断 */
    __disable_irq();

    /* 更新系统状态 */
    system_state = STATE_ERROR;
    error_count++;

    /* 点亮错误指示LED（低电平点亮） */
    HAL_GPIO_WritePin(ERROR_LED_PORT, ERROR_LED_PIN, GPIO_PIN_RESET);

    /* 进入死循环 */
    while (1)
    {
        /* 可选：LED闪烁表示错误状态 */
        HAL_Delay(500);
        HAL_GPIO_TogglePin(ERROR_LED_PORT, ERROR_LED_PIN);
    }
}

/* ========== Exception Handlers ========== */

/**
  * @brief  非屏蔽中断处理函数
  */
void NMI_Handler(void)
{
    Error_Handler();
}

/**
  * @brief  硬件错误处理函数
  */
void HardFault_Handler(void)
{
    Error_Handler();
}

/**
  * @brief  内存管理错误处理函数
  */
void MemManage_Handler(void)
{
    Error_Handler();
}

/**
  * @brief  总线错误处理函数
  */
void BusFault_Handler(void)
{
    Error_Handler();
}

/**
  * @brief  使用错误处理函数
  */
void UsageFault_Handler(void)
{
    Error_Handler();
}

/**
  * @brief  SVC处理函数
  */
void SVC_Handler(void)
{
}

/**
  * @brief  调试监控处理函数
  */
void DebugMon_Handler(void)
{
}

/**
  * @brief  PendSVC处理函数
  */
void PendSV_Handler(void)
{
}
