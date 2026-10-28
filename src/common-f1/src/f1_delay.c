/**
 * @file    f1_delay.c
 * @brief   SysTick 延时实现（72MHz，24bit 递减计数器）
 */
#include "f1_delay.h"
#include "stm32f103x_min.h"

static volatile uint32_t s_tick_ms = 0;

void f1_delay_init(void)
{
    /* 1ms 周期中断：72 000 000 / 1000 = 72000 个计数 */
    SysTick->LOAD = 72000u - 1u;
    SysTick->VAL  = 0;
    SysTick->CTRL = (1u << SysTick_CTRL_CLKSOURCE_Pos)   /* 处理器时钟 72MHz */
                  | (1u << SysTick_CTRL_TICKINT_Pos)      /* 产生中断 */
                  | (1u << SysTick_CTRL_ENABLE_Pos);
    nvic_set_priority((int)(15 /* SysTick_IRQn 用 exception 15，不走 NVIC_IP */), 0);
}

void SysTick_Handler(void)
{
    s_tick_ms++;
}

void delay_us(uint32_t us)
{
    /* 用 SysTick 作 24bit 递减计数（轮询 COUNTFLAG，不依赖中断）。
     * 先停掉 1ms 中断配置会破坏 tick，改用独立的 DWT 不可用（M3 无），
     * 因此采用：暂存 CTRL，重配为 72 个计数/us 的自由运行。 */
    uint32_t ctrl_bak = SysTick->CTRL;
    uint32_t load_bak = SysTick->LOAD;

    SysTick->CTRL = 0;                       /* 先停 */
    SysTick->LOAD = 72u * us;                /* 1 count = 1/72MHz */
    SysTick->VAL  = 0;
    SysTick->CTRL = (1u << SysTick_CTRL_CLKSOURCE_Pos)
                  | (1u << SysTick_CTRL_ENABLE_Pos);
    while (!(SysTick->CTRL & (1u << SysTick_CTRL_COUNTFLAG_Pos))) { }

    SysTick->CTRL = 0;                       /* 恢复 1ms 配置 */
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
