/**
 * @file    main.c
 * @brief   Day5~6 例程：执行层 —— TB6612 风扇 PWM 调速 + LED 呼吸灯
 *
 * 现象：
 *   风扇按 0→20→…→100→0 每 2s 一档循环调速（OLED 显示当前占空比）；
 *   LED 用 TIM 软件模拟呼吸（渐亮渐暗，周期 4s）。
 *
 * 学习点：TIM1 PWM（PSC/ARR/CCR 计算）、TIM1 主输出使能 BDTR.MOE、
 *         呼吸灯占空比斜坡、电机独立供电与共地（安全规范）。
 */
#include <stdio.h>
#include "board_f1.h"
#include "f1_delay.h"
#include "ssd1306.h"
#include "f1_fan.h"

int main(void)
{
    sysclock_init_72m();
    f1_delay_init();
    board_led_init();
    ssd1306_init();
    fan_init();

    uint32_t t_fan = 0, t_breath = 0;
    uint8_t duty = 0;
    int breath = 0, dir = 1;

    while (1) {
        /* 风扇 2s 一档 */
        if (every_ms(&t_fan, 2000)) {
            duty = (uint8_t)((duty + 20) % 120);
            if (duty > 100) duty = 0;
            fan_set(duty);

            char buf[20];
            snprintf(buf, sizeof(buf), "FAN DUTY: %3u%%", duty);
            ssd1306_clear();
            ssd1306_string(0, 0, "DAY5 ACTUATOR");
            ssd1306_string(0, 3, buf);
            ssd1306_flush();
        }

        /* 外接 LED 呼吸（20ms 一档，100 档 ≈ 4s 周期） */
        if (every_ms(&t_breath, 20)) {
            breath += dir;
            if (breath >= 100 || breath <= 0) dir = -dir;
            /* PC13 无 PWM 复用，用占空比软件模拟：周期 2ms 内高电平时间 */
            for (int i = 0; i < 2; i++) {
                board_led((i * 100 + breath) < 100 ? 0 : 1);
                delay_us(1000);
            }
        }
    }
}
