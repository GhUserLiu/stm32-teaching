/**
 * @file    f1_delay.c
 * @brief   SysTick 延时实现（频率自适应：F1_CPU_FREQ_MHZ 统一控制）
 */
#include "f1_delay.h"
#include "stm32f103x_min.h"

static volatile uint32_t s_tick_ms = 0;

void f1_delay_init(void)
{
    /* 1ms 周期中断：F1_CPU_FREQ_MHZ × 1000 个计数 */
    SysTick->LOAD = (F1_CPU_FREQ_MHZ * 1000u) - 1u;
    SysTick->VAL  = 0;
    SysTick->CTRL = (1u << SysTick_CTRL_CLKSOURCE_Pos)
                  | (1u << SysTick_CTRL_TICKINT_Pos)
                  | (1u << SysTick_CTRL_ENABLE_Pos);
}

void SysTick_Handler(void)
{
    s_tick_ms++;
}

void delay_us(uint32_t us)
{
    uint32_t ctrl_bak = SysTick->CTRL;
    uint32_t load_bak = SysTick->LOAD;

    SysTick->CTRL = 0;
    SysTick->LOAD = (uint32_t)F1_CPU_FREQ_MHZ * us;
    SysTick->VAL  = 0;
    SysTick->CTRL = (1u << SysTick_CTRL_CLKSOURCE_Pos)
                  | (1u << SysTick_CTRL_ENABLE_Pos);
    while (!(SysTick->CTRL & (1u << SysTick_CTRL_COUNTFLAG_Pos))) { }

    SysTick->CTRL = 0;
    SysTick->LOAD = load_bak;
    SysTick->VAL  = 0;
    SysTick->CTRL = ctrl_bak | (1u << SysTick_CTRL_ENABLE_Pos);
}

void delay_ms(uint32_t ms)
{
    while (ms--) delay_us(1000);
}

uint32_t f1_tick(void) { return s_tick_ms; }

int every_ms(uint32_t *last, uint32_t period_ms)
{
    uint32_t now = s_tick_ms;
    if (now - *last >= period_ms) {
        *last = now;
        return 1;
    }
    return 0;
}
