/**
 ******************************************************************************
 * @file           : debounce.c
 * @brief          : 非阻塞按键消抖模块实现
 * @author         : STM32F407 教学团队
 * @version        : 1.0.0
 ******************************************************************************
 */

#include "debounce.h"
#include "stm32f4xx_hal.h"

/* ========== 外部函数声明 ========== */
/**
 * @brief 获取系统时间戳（毫秒）
 *
 * 依赖HAL库的HAL_GetTick()函数
 * 该函数在SysTick中断中每毫秒递增一次
 */
extern uint32_t HAL_GetTick(void);

/* ========== 函数实现 ========== */

void Key_Init(KeyState_t *key)
{
    /**
     * @brief 初始化按键状态结构体
     *
     * 将所有状态重置为初始值
     */
    if (key == (void *)0) {
        return;  /* 安全检查：防止空指针 */
    }

    key->state = KEY_STATE_IDLE;
    key->pin_state = 0;
    key->last_tick = 0;
    key->pressed_flag = 0;
    key->released_flag = 0;
}

uint8_t Key_Update(KeyState_t *key, uint8_t current_pin_state)
{
    /**
     * @brief 更新按键状态（状态机实现）
     *
     * @param key 按键状态结构体指针
     * @param current_pin_state 当前引脚状态
     * @return 状态是否改变
     *
     * 状态机逻辑:
     * - IDLE: 检测到按下进入DEBOUNCE
     * - DEBOUNCE: 消抖时间到后确认按下
     * - PRESSED: 检测到释放进入RELEASE
     * - RELEASE: 消抖时间到后确认释放，返回IDLE
     */
    uint32_t current_tick;
    uint8_t state_changed = 0;

    /* 安全检查 */
    if (key == (void *)0) {
        return 0;
    }

    /* 获取当前时间戳 */
    current_tick = HAL_GetTick();

    /* 清除事件标志（每次Update清除） */
    key->pressed_flag = 0;
    key->released_flag = 0;

    /* 缓存当前引脚状态 */
    key->pin_state = current_pin_state;

    /* 状态机处理 */
    switch (key->state)
    {
        case KEY_STATE_IDLE:
            /* 空闲状态：等待按键按下 */
            if (current_pin_state) {
                /* 检测到按下，进入消抖状态 */
                key->state = KEY_STATE_DEBOUNCE;
                key->last_tick = current_tick;
            }
            break;

        case KEY_STATE_DEBOUNCE:
            /* 消抖状态：确认是否真的按下 */
            if ((current_tick - key->last_tick) >= DEBOUNCE_DELAY_TICKS) {
                /* 消抖时间到 */
                if (current_pin_state) {
                    /* 确认按下 */
                    key->state = KEY_STATE_PRESSED;
                    key->pressed_flag = 1;  /* 触发按下事件 */
                    state_changed = 1;
                } else {
                    /* 误触发，返回空闲 */
                    key->state = KEY_STATE_IDLE;
                }
            }
            /* 消抖期间如果释放，返回空闲 */
            else if (!current_pin_state) {
                key->state = KEY_STATE_IDLE;
            }
            break;

        case KEY_STATE_PRESSED:
            /* 按下确认状态：等待释放 */
            if (!current_pin_state) {
                /* 检测到释放，进入释放消抖 */
                key->state = KEY_STATE_RELEASE;
                key->last_tick = current_tick;
            }
            break;

        case KEY_STATE_RELEASE:
            /* 释放消抖状态：确认是否真的释放 */
            if ((current_tick - key->last_tick) >= DEBOUNCE_DELAY_TICKS) {
                /* 消抖时间到 */
                if (!current_pin_state) {
                    /* 确认释放 */
                    key->state = KEY_STATE_IDLE;
                    key->released_flag = 1;  /* 触发释放事件 */
                    state_changed = 1;
                } else {
                    /* 还没消抖完又按下，返回按下状态 */
                    key->state = KEY_STATE_PRESSED;
                }
            }
            /* 消抖期间如果又按下，返回按下状态 */
            else if (current_pin_state) {
                key->state = KEY_STATE_PRESSED;
            }
            break;

        default:
            /* 异常状态：重置 */
            key->state = KEY_STATE_IDLE;
            break;
    }

    return state_changed;
}

uint8_t Key_IsPressed(KeyState_t *key)
{
    /**
     * @brief 检查是否有按下事件
     *
     * @param key 按键状态结构体指针
     * @return 是否有按下事件
     */
    if (key == (void *)0) {
        return 0;
    }

    return key->pressed_flag;
}

uint8_t Key_IsReleased(KeyState_t *key)
{
    /**
     * @brief 检查是否有释放事件
     *
     * @param key 按键状态结构体指针
     * @return 是否有释放事件
     */
    if (key == (void *)0) {
        return 0;
    }

    return key->released_flag;
}

uint8_t Key_IsCurrentlyDown(KeyState_t *key)
{
    /**
     * @brief 检查按键当前是否处于按下状态
     *
     * @param key 按键状态结构体指针
     * @return 当前是否按下
     *
     * @note 此函数不进行消抖，仅返回物理状态
     */
    if (key == (void *)0) {
        return 0;
    }

    /* 在PRESSED或DEBOUNCE状态时认为按键按下 */
    return (key->state == KEY_STATE_PRESSED || key->state == KEY_STATE_DEBOUNCE);
}
