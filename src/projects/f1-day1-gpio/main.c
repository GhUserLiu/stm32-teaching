/**
 * @file    main.c
 * @brief   Day1 例程：GPIO 点灯 / 按键 / 蜂鸣器（基础层）
 *
 * 现象：
 *   1. 板载 RGB 红灯（PA1）以 1Hz 闪烁（非阻塞，SysTick 滴答）
 *   2. 按住板载 KEY1（PA0）：红灯常亮、蜂鸣器响；松开恢复闪烁
 *   3. 短按一次：蜂鸣器短鸣 100ms 提示
 *
 * 学习点：GPIO 输入/输出配置、上拉输入、软件消抖、非阻塞调度。
 */
#include "board_f1.h"
#include "f1_delay.h"
#include "f1_key.h"

int main(void)
{
    sysclock_init_72m();
    f1_delay_init();
    board_led_init();
    board_key_init();
    board_buzzer_init();

    key_state_t ks = {0};
    uint32_t t_led = 0;
    int beep_until = 0;

    while (1) {
        uint32_t now = f1_tick();

        /* 1Hz 闪烁（非阻塞） */
        if (every_ms(&t_led, 500)) {
            static int ledv;
            ledv = !ledv;
            board_led(ledv);
        }

        /* 按键消抖（10ms 周期由 key_update 自身节流） */
        if (key_update(&ks, board_key_pressed(), now)) {
            beep_until = (int)now + 100;    /* 短按 → 短鸣 */
        }

        if (ks.stable) {                    /* 按住 → 常亮 + 长响 */
            board_led(1);
            board_buzzer(1);
        } else {
            if (beep_until && (int)now < beep_until) {
                board_buzzer(1);            /* 短按 → 100ms 短鸣 */
            } else {
                beep_until = 0;
                board_buzzer(0);
            }
        }
    }
}
