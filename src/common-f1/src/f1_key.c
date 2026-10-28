/**
 * @file    f1_key.c
 * @brief   按键消抖与短按/长按判定（非阻塞，基于毫秒滴答）
 */
#include "f1_key.h"

#define DEBOUNCE_MS   20u
#define LONG_MS       1000u

int key_update(key_state_t *k, int pressed, uint32_t now_ms)
{
    int event = 0;

    if ((int)k->last_raw != !!pressed) {
        k->last_raw  = (uint8_t)!!pressed;
        k->last_change = now_ms;
    }

    /* 原始电平稳定超过消抖窗口才更新稳定态 */
    if ((now_ms - k->last_change) >= DEBOUNCE_MS && k->stable != k->last_raw) {
        k->stable = k->last_raw;
        if (k->stable) {                    /* 按下沿 */
            k->press_start = now_ms;
            k->long_fired  = 0;
        } else {                            /* 释放沿 */
            if (!k->long_fired) event = 1;  /* 未触发过长按 → 短按 */
        }
    }
    return event;
}

int key_long_reached(key_state_t *k, uint32_t now_ms)
{
    if (k->stable && !k->long_fired
        && (now_ms - k->press_start) >= LONG_MS) {
        k->long_fired = 1;
        return 1;
    }
    return 0;
}
