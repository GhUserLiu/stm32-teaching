/**
 ******************************************************************************
 * @file           : debounce.h
 * @brief          : 非阻塞按键消抖模块头文件
 * @author         : STM32F407 教学团队
 * @version        : 1.0.0
 *
 * @description
 *
 * 提供非阻塞的按键消抖功能，基于状态机实现。
 * 解决HAL_Delay阻塞问题，提高系统响应性。
 *
 * 使用方法:
 * 1. 定义按键状态变量: KeyState_t key_state;
 * 2. 初始化: Key_Init(&key_state);
 * 3. 在主循环中调用:
 *    key_pin_state = Read_KEY();
 *    Key_Update(&key_state, key_pin_state);
 *    if (Key_IsPressed(&key_state)) {
 *        // 处理按键按下事件
 *    }
 *
 ******************************************************************************
 */

#ifndef DEBOUNCE_H
#define DEBOUNCE_H

#include <stdint.h>
#include <stdbool.h>

/* ========== 消抖配置参数 ========== */
/**
 * @brief 消抖延时（毫秒）
 *
 * 消抖时间建议20-50ms，可根据实际按键特性调整
 */
#define DEBOUNCE_DELAY_MS     20

/**
 * @brief 消抖时间（系统Tick数）
 *
 * 基于HAL_GetTick()返回值，1ms = 1 Tick
 */
#define DEBOUNCE_DELAY_TICKS  DEBOUNCE_DELAY_MS

/* ========== 消抖状态定义 ========== */
/**
 * @brief 按键状态枚举
 *
 * 状态机状态转移:
 * IDLE -> DEBOUNCE -> PRESSED -> RELEASE -> IDLE
 */
typedef enum {
    KEY_STATE_IDLE = 0,       /* 空闲状态，等待按键按下 */
    KEY_STATE_DEBOUNCE = 1,   /* 消抖状态，确认按下 */
    KEY_STATE_PRESSED = 2,    /* 按下确认状态 */
    KEY_STATE_RELEASE = 3     /* 释放确认状态 */
} KeyStateEnum_t;

/* ========== 按键状态结构体 ========== */
/**
 * @brief 按键状态结构体
 *
 * 存储按键的状态信息
 */
typedef struct {
    KeyStateEnum_t state;      /* 当前状态 */
    uint8_t pin_state;        /* 引脚状态缓存（0或1） */
    uint32_t last_tick;       /* 上次状态更新时间戳 */
    uint8_t pressed_flag;     /* 按下标志（消抖确认后的按下事件） */
    uint8_t released_flag;    /* 释放标志（消抖确认后的释放事件） */
} KeyState_t;

/* ========== 函数声明 ========== */

/**
 * @brief 初始化按键状态
 *
 * @param key 指向按键状态结构体的指针
 *
 * @note 使用前必须调用此函数初始化
 */
void Key_Init(KeyState_t *key);

/**
 * @brief 更新按键状态
 *
 * @param key 指向按键状态结构体的指针
 * @param current_pin_state 当前引脚状态（0或1）
 *
 * @return 状态是否改变（1=有事件，0=无事件）
 *
 * @note 此函数非阻塞，应在主循环中定期调用
 * @note 调用频率建议不低于10ms一次
 */
uint8_t Key_Update(KeyState_t *key, uint8_t current_pin_state);

/**
 * @brief 检查是否有按下事件
 *
 * @param key 指向按键状态结构体的指针
 * @return 是否有按下事件（1=有，0=无）
 *
 * @note 每次调用后会清除标志，需及时处理
 */
uint8_t Key_IsPressed(KeyState_t *key);

/**
 * @brief 检查是否有释放事件
 *
 * @param key 指向按键状态结构体的指针
 * @return 是否有释放事件（1=有，0=无）
 *
 * @note 每次调用后会清除标志，需及时处理
 */
uint8_t Key_IsReleased(KeyState_t *key);

/**
 * @brief 检查按键当前是否处于按下状态
 *
 * @param key 指向按键状态结构体的指针
 * @return 当前是否按下（1=按下，0=释放）
 *
 * @note 此函数不消除抖，仅返回当前物理状态
 */
uint8_t Key_IsCurrentlyDown(KeyState_t *key);

#endif /* DEBOUNCE_H */
