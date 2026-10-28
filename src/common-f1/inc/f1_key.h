/**
 * @file    f1_key.h
 * @brief   按键扫描 + 软件消抖 + 短按/长按判定（非阻塞）
 */
#ifndef F1_KEY_H
#define F1_KEY_H

#include <stdint.h>

typedef struct {
    uint8_t  stable;        /* 消抖后的稳定电平（1=按下） */
    uint8_t  last_raw;      /* 上次原始电平 */
    uint32_t last_change;   /* 原始电平上次变化时刻 ms */
    uint32_t press_start;   /* 本次按下起始时刻 ms */
    uint8_t  long_fired;    /* 长按已触发标志 */
} key_state_t;

/**
 * @brief 周期调用（建议 10ms）更新按键状态
 * @param k        状态结构体（首次使用前清零）
 * @param pressed  当前原始电平（1=按下）
 * @param now_ms   当前毫秒滴答
 * @return 1=短按释放（一次完整短按）；
 *         长按在达到阈值时通过 key_long_reached() 查询，不在此返回
 */
int key_update(key_state_t *k, int pressed, uint32_t now_ms);

/** @brief 长按是否已触发（>=1000ms，触发一次后清零），需在 key_update 后查询 */
int key_long_reached(key_state_t *k, uint32_t now_ms);

#endif /* F1_KEY_H */
