/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
UART_HandleTypeDef huart1;

/* USER CODE BEGIN PV */
// LED系统状态
LED_System_t led_system = {0};

// 模式名称字符串
const char* mode_names[] = {
    "关闭",
    "左转",
    "右转",
    "双闪"
};

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART1_UART_Init(void);
/* USER CODE BEGIN PFP */
// LED控制函数
void LED_Update(void);
void LED_SetMode(LED_Mode_t mode);
void LED_ToggleHazard(void);
void LED_PrintMode(void);

// 串口重定向
int fputc(int ch, FILE *f);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART1_UART_Init();
  /* USER CODE BEGIN 2 */
  // 初始化LED系统
  led_system.current_mode = LED_MODE_OFF;
  led_system.saved_mode = LED_MODE_OFF;
  led_system.hazard_active = 0;
  led_system.tick_counter = 0;
  led_system.led_state = 0;

  // 打印欢迎信息
  printf("\r\n=== 智能灯光控制系统 ===\r\n");
  printf("KEY0: 切换模式 | KEY_UP: 紧急双闪\r\n");
  LED_PrintMode();
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    // 更新LED状态（非阻塞）
    LED_Update();
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 25;
  RCC_OscInitStruct.PLL.PLLN = 336;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 4;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART1_UART_Init(void)
{

  /* USER CODE BEGIN USART1_Init 0 */

  /* USER CODE END USART1_Init 0 */

  /* USER CODE BEGIN USART1_Init 1 */

  /* USER CODE END USART1_Init 1 */
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 115200;
  huart1.Init.WordLength = UART_WORDLENGTH_8B;
  huart1.Init.StopBits = UART_STOPBITS_1;
  huart1.Init.Parity = UART_PARITY_NONE;
  huart1.Init.Mode = UART_MODE_TX_RX;
  huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart1.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART1_Init 2 */

  /* USER CODE END USART1_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOE_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOF_CLK_ENABLE();
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOF, LED0_Pin|LED1_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : KEY0_Pin */
  GPIO_InitStruct.Pin = KEY0_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(KEY0_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pins : LED0_Pin LED1_Pin */
  GPIO_InitStruct.Pin = LED0_Pin|LED1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOF, &GPIO_InitStruct);

  /*Configure GPIO pin : KEY_UP_Pin */
  GPIO_InitStruct.Pin = KEY_UP_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(KEY_UP_GPIO_Port, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI0_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI0_IRQn);

  HAL_NVIC_SetPriority(EXTI4_IRQn, 1, 0);
  HAL_NVIC_EnableIRQ(EXTI4_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
/**
 * @brief 串口重定向函数
 */
int fputc(int ch, FILE *f)
{
    HAL_UART_Transmit(&huart1, (uint8_t*)&ch, 1, HAL_MAX_DELAY);
    return ch;
}

/**
 * @brief 打印当前模式
 */
void LED_PrintMode(void)
{
    printf("当前模式: %s\r\n", mode_names[led_system.current_mode]);
}

/**
 * @brief 设置LED模式
 */
void LED_SetMode(LED_Mode_t mode)
{
    if (mode >= LED_MODE_MAX)
    {
        mode = LED_MODE_OFF;
    }
    led_system.current_mode = mode;
    led_system.tick_counter = 0;
    led_system.led_state = 0;
    LED_PrintMode();
}

/**
 * @brief 切换紧急双闪模式
 */
void LED_ToggleHazard(void)
{
    if (led_system.hazard_active)
    {
        // 退出双闪，恢复之前模式
        led_system.hazard_active = 0;
        led_system.current_mode = led_system.saved_mode;
        printf("退出紧急双闪，恢复模式: %s\r\n", mode_names[led_system.current_mode]);
    }
    else
    {
        // 进入双闪，保存当前模式
        led_system.saved_mode = led_system.current_mode;
        led_system.hazard_active = 1;
        led_system.current_mode = LED_MODE_HAZARD;
        led_system.tick_counter = 0;
        printf("进入紧急双闪模式，保存原模式: %s\r\n", mode_names[led_system.saved_mode]);
    }
}

/**
 * @brief LED状态更新函数（状态机）
 * 使用时间基准而非HAL_Delay
 */
void LED_Update(void)
{
    static uint32_t last_tick[LED_MODE_MAX] = {0};
    uint32_t current_tick = HAL_GetTick();
    uint32_t elapsed = current_tick - last_tick[led_system.current_mode];

    // 根据不同模式处理LED
    switch (led_system.current_mode)
    {
        case LED_MODE_OFF:
            // 关闭模式：两个LED都熄灭
            HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, GPIO_PIN_RESET);
            break;

        case LED_MODE_LEFT_TURN:
            // 左转模式：LED0以1Hz闪烁，LED1灭
            if (elapsed >= 500)
            {
                last_tick[led_system.current_mode] = current_tick;
                led_system.led_state = !led_system.led_state;
                HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, led_system.led_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
                HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, GPIO_PIN_RESET);
            }
            break;

        case LED_MODE_RIGHT_TURN:
            // 右转模式：LED1以1Hz闪烁，LED0灭
            if (elapsed >= 500)
            {
                last_tick[led_system.current_mode] = current_tick;
                led_system.led_state = !led_system.led_state;
                HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, GPIO_PIN_RESET);
                HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, led_system.led_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
            }
            break;

        case LED_MODE_HAZARD:
            // 紧急双闪模式：LED0和LED1同时以2Hz闪烁
            if (elapsed >= 250)
            {
                last_tick[led_system.current_mode] = current_tick;
                led_system.led_state = !led_system.led_state;
                HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, led_system.led_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
                HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, led_system.led_state ? GPIO_PIN_SET : GPIO_PIN_RESET);
            }
            break;

        default:
            break;
    }
}

/**
 * @brief 按键中断回调函数
 * KEY0: EXTI4, 优先级1
 * KEY_UP: EXTI0, 优先级0
 */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == KEY0_Pin)
    {
        // 紧急双闪模式下KEY0无效
        if (led_system.hazard_active)
        {
            return;
        }

        // 简单消抖
        static uint32_t last_key0_time = 0;
        uint32_t current_time = HAL_GetTick();

        if (current_time - last_key0_time < 200)
        {
            return;
        }
        last_key0_time = current_time;

        // 切换到下一个模式：关闭→左转→右转→双闪→关闭
        LED_SetMode(led_system.current_mode + 1);
    }
    else if (GPIO_Pin == KEY_UP_Pin)
    {
        // 简单消抖
        static uint32_t last_keyup_time = 0;
        uint32_t current_time = HAL_GetTick();

        if (current_time - last_keyup_time < 200)
        {
            return;
        }
        last_keyup_time = current_time;

        // 切换紧急双闪模式
        LED_ToggleHazard();
    }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
