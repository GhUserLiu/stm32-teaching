/**
 * @file    main.c
 * @brief   联调参考工程：智能座舱温控系统（必做功能全实现）
 *
 * 《新能源汽车工程实训（电子控制方向）》项目《智能座舱温控系统设计》
 * 感知→决策→执行闭环：
 *   感知：DHT11 温湿度（2s）+ 光敏 ADC（500ms）
 *   决策：温度滞回控制（升温 ≥28℃ 开风扇、降温 <26℃ 关风扇；
 *         ≥32℃ 风扇全速 + 蜂鸣器过温报警；光照暗 → LED 氛围灯）
 *   执行：TB6612 风扇调速 / 蜂鸣器 / LED
 *   交互：按键短按 → 手动/自动切换（手动下再短按风扇 0→25→50→75→100 循环）
 *
 * 教师参考实现：学生项目按任务书要求自行完成，本工程供验收对照与排障。
 */
#include <stdio.h>
#include "board_f1.h"
#include "f1_delay.h"
#include "f1_key.h"
#include "dht11.h"
#include "ssd1306.h"
#include "f1_fan.h"
#include "f1_adc.h"

/* ---- 控制参数（滞回阈值，防临界抖动） ---- */
#define T_FAN_ON_X10     280    /* ≥28.0℃ 开风扇 */
#define T_FAN_OFF_X10    260    /* <26.0℃ 关风扇 */
#define T_ALARM_X10      320    /* ≥32.0℃ 过温报警 */
#define T_FULL_X10       300    /* ≥30.0℃ 风扇全速 */
#define LIGHT_DARK       1200   /* 光照原始值低于此值视为“暗” */

/* ---- 烟雾/空气质量联动（MQ-135，备用件） ----
 * 接 PA5（AO）。烟雾或过温任一触发 → 电机风扇全速排风 + 报警。
 * 未接 MQ-135 时置 0（否则 PA5 悬空读数随机，会误触发）。 */
#define SMOKE_ENABLE     1
#define SMOKE_TH_ON      2200   /* 原始值 ≥ 此值判定空气污染/烟雾（按实测调） */
#define SMOKE_TH_OFF     1800   /* 回落 < 此值才解除（滞回） */
#define SMOKE_WARMUP_MS  60000  /* MQ-135 预热 60s（通电初期读数漂高属正常） */

typedef enum { MODE_AUTO, MODE_MANUAL } mode_t;

int main(void)
{
    sysclock_init_72m();
    f1_delay_init();
    board_uart1_init(115200);
    board_led_init();
    board_key_init();
    board_buzzer_init();
    dht11_init();
    ssd1306_init();
    f1_adc_init();
    fan_init();

    printf("=== Cabin Thermal Control v1.0 ===\r\n");

    mode_t mode = MODE_AUTO;
    uint8_t manual_duty = 0;
    int fan_on = 0, alarm = 0;

    key_state_t ks = {0};
    uint32_t t_dht = 0, t_light = 0, t_ui = 0, t_beep = 0;
    int16_t temp = 0, humi = 0;
    uint16_t light = 0;
#if SMOKE_ENABLE
    uint16_t mq = 0;
    int smoke = 0;
#else
    const int smoke = 0;
#endif

    while (1) {
        uint32_t now = f1_tick();

        /* ---- 感知：DHT11（2s） ---- */
        if (every_ms(&t_dht, 2000)) {
            if (dht11_read(&temp, &humi) != 0) {
                printf("[DHT11] read err\r\n");
            }
        }

        /* ---- 感知：光照（500ms） ---- */
        if (every_ms(&t_light, 500)) {
            light = f1_adc_read_avg(ADC_CH_LIGHT, 8);
#if SMOKE_ENABLE
            mq = f1_adc_read_avg(ADC_CH_MQ135, 8);
            /* 烟雾判定：预热期后，滞回（≥ON 触发，<OFF 解除） */
            if (now >= SMOKE_WARMUP_MS) {
                if (mq >= SMOKE_TH_ON)  smoke = 1;
                if (mq <  SMOKE_TH_OFF) smoke = 0;
            }
#endif
        }

        /* ---- 交互：按键 ---- */
        if (key_update(&ks, board_key_pressed(), now)) {
            if (mode == MODE_AUTO) {
                mode = MODE_MANUAL;
                manual_duty = 0;
            } else {
                manual_duty = (uint8_t)((manual_duty + 25) % 125);
                if (manual_duty > 100) manual_duty = 0;
            }
            printf("[KEY] mode=%s duty=%u\r\n",
                   mode == MODE_AUTO ? "AUTO" : "MANUAL", manual_duty);
        }

        /* ---- 决策（优先级：烟雾 > 过温 > 常规温控；烟雾/过温均强制排风） ---- */
        if (smoke) {
            /* 烟雾触发：无论自动/手动，电机风扇全速排风 + 双闪报警 */
            alarm = 1; fan_on = 1;
            fan_set(100);
        } else if (mode == MODE_AUTO) {
            if (temp >= T_ALARM_X10) {
                alarm = 1; fan_on = 1;
                fan_set(100);
            } else {
                alarm = 0;
                if (temp >= T_FAN_ON_X10)  fan_on = 1;
                if (temp <  T_FAN_OFF_X10) fan_on = 0;
                if (fan_on) {
                    if (temp >= T_FULL_X10) fan_set(100);
                    else {   /* 28~30℃ 线性 20%→80% */
                        int d = 20 + (temp - T_FAN_ON_X10) * 60
                                    / (T_FULL_X10 - T_FAN_ON_X10);
                        fan_set((uint8_t)d);
                    }
                } else {
                    fan_stop();
                }
            }
        } else {
            alarm = 0;                 /* 手动模式不自动报警（教学简化） */
            if (manual_duty == 0) fan_stop();
            else fan_set(manual_duty);
        }

        /* 报警：1Hz 断续鸣叫（烟雾=2Hz 快鸣，过温=1Hz 慢鸣） */
        if (alarm) {
            uint32_t half = smoke ? 250 : 500;
            if (every_ms(&t_beep, half)) {
                static int beep;
                beep = !beep;
                board_buzzer(beep);
            }
        } else {
            board_buzzer(0);
        }

        /* 氛围灯：光照暗 → LED 亮；报警时 LED 随蜂鸣器节奏闪 */
        if (alarm) {
            static int led_b;
            static uint32_t t_led_b;
            if (every_ms(&t_led_b, smoke ? 250 : 500)) led_b = !led_b;
            board_led(led_b);
        } else {
            board_led(light < LIGHT_DARK);
        }

        /* ---- 显示与日志（1s） ---- */
        static uint32_t t_log = 0;
        if (every_ms(&t_ui, 1000)) {
            char buf[24];
            ssd1306_clear();
            ssd1306_string(0, 0, "CABIN THERMAL");
            snprintf(buf, sizeof(buf), "T:%d.%dC H:%d%%",
                     temp / 10, temp % 10, humi / 10);
            ssd1306_string(0, 2, buf);
            snprintf(buf, sizeof(buf), "%s FAN:%u%%",
                     mode == MODE_AUTO ? "AUTO" : "MANL",
                     mode == MODE_AUTO
                       ? (alarm ? 100u : (fan_on ? (unsigned)(TIM1->CCR1 / 10) : 0u))
                       : manual_duty);
            ssd1306_string(0, 4, buf);
            snprintf(buf, sizeof(buf), "L:%4u %s", light,
                     smoke ? "SMOKE!" : (alarm ? "ALARM!" : (light < LIGHT_DARK ? "DIM" : "")));
            ssd1306_string(0, 5, buf);
#if SMOKE_ENABLE
            snprintf(buf, sizeof(buf), "MQ:%4u %s", mq,
                     now < SMOKE_WARMUP_MS ? "WARM" : (smoke ? "EVAC!" : ""));
            ssd1306_string(0, 6, buf);
#endif
            ssd1306_flush();

            t_log++;
            printf("[LOG %u] T:%d.%d H:%d L:%u MQ:%u mode=%s fan=%s %s%s\r\n",
                   (unsigned)t_log, temp / 10, temp % 10, humi / 10, light,
#if SMOKE_ENABLE
                   mq,
#else
                   0u,
#endif
                   mode == MODE_AUTO || smoke ? "AUTO" : "MANUAL",
                   fan_on ? "ON" : "OFF",
                   smoke ? "SMOKE " : "", alarm ? "ALARM" : "");
        }
    }
}
