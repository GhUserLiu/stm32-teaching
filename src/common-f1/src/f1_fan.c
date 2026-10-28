/**
 * @file    f1_fan.c
 * @brief   TB6612FNG 风扇驱动实现（TIM1_CH1 PWM @ PA8）
 */
#include "f1_fan.h"
#include "board_f1.h"

void fan_init(void)
{
    /* 方向引脚 */
    RCC->APB2ENR |= RCC_APB2ENR_IOPB | RCC_APB2ENR_IOPA | RCC_APB2ENR_TIM1;
    gpio_init(TB6612_AIN1_PORT, TB6612_AIN1_PIN, GPIO_MODE_OUT_PP_2);
    gpio_init(TB6612_AIN2_PORT, TB6612_AIN2_PIN, GPIO_MODE_OUT_PP_2);
    gpio_reset(TB6612_AIN1_PORT, TB6612_AIN1_PIN);   /* AIN1=0 AIN2=0 → 待机 */
    gpio_reset(TB6612_AIN2_PORT, TB6612_AIN2_PIN);

    /* PWMA：PA8 = TIM1_CH1，复用推挽 */
    gpio_init(TB6612_PWMA_PORT, TB6612_PWMA_PIN, GPIO_MODE_AF_PP_50);

    /* TIM1：PSC=71（72MHz/72=1MHz），ARR=999 → 1kHz */
    TIM1->PSC = 71;
    TIM1->ARR = 999;
    TIM1->CCR1 = 0;
    TIM1->CCMR1 = TIM_CCMR1_OC1M_PWM1 | TIM_CCMR1_OC1PE;
    TIM1->CCER  = TIM_CCER_CC1E;
    TIM1->EGR   = TIM_EGR_UG;          /* 装载影子寄存器 */
    TIM1->BDTR  = TIM1_BDTR_MOE;       /* TIM1 必须开主输出 */
    TIM1->CR1  |= TIM_CR1_CEN;
}

void fan_set(uint8_t duty)
{
    if (duty > 100) duty = 100;
    /* 正转：AIN1=1 AIN2=0 */
    gpio_set(TB6612_AIN1_PORT, TB6612_AIN1_PIN);
    gpio_reset(TB6612_AIN2_PORT, TB6612_AIN2_PIN);
    TIM1->CCR1 = ((uint32_t)duty * 1000u) / 100u;   /* ARR=999 */
}

void fan_stop(void)
{
    TIM1->CCR1 = 0;
    gpio_reset(TB6612_AIN1_PORT, TB6612_AIN1_PIN);
    gpio_reset(TB6612_AIN2_PORT, TB6612_AIN2_PIN);  /* 待机（滑行停转） */
}
