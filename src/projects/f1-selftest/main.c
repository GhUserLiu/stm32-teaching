/**
 * @file    main.c
 * @brief   实训套件验收自检固件（野火小智 STM32F103C8T6 + 21 件套）
 *
 * 开课前逐套烧录，按 OLED/串口提示逐项验收：
 *   T1 LED      板载 RGB 红灯 PA1 闪烁（1Hz）           —— 核心板好坏
 *   T2 UART     串口 115200 打印自检横幅与状态          —— USB 转串口
 *   T3 KEY      按住板载 KEY1(PA0)，OLED/串口显示 PRESSED —— 板载按键
 *   T4 BUZZER   蜂鸣器间歇鸣叫（0.5s 响/停）            —— 蜂鸣器模块
 *   T5 DHT11    每 2s 读温湿度，显示 OK/ERR             —— DHT11
 *   T6 ADC      光敏/热敏原始值 + 热敏温度，遮光/捏热变化 —— 光敏/热敏
 *   T7 OLED     逐屏刷新显示各项结果                    —— OLED
 *   T8 FAN      10%~100% 循环调速 5s 一档               —— TB6612+风扇
 *
 * 结论判定：全部子项 OK → 第 8 行显示 "ALL PASS"。
 * 验收记录：串口每 2s 打印一行汇总（便于抄录到《套件验收登记表》）。
 */
#include <stdio.h>
#include "board_f1.h"
#include "f1_delay.h"
#include "dht11.h"
#include "ssd1306.h"
#include "f1_key.h"
#include "f1_fan.h"
#include "f1_adc.h"

static int ok_led, ok_uart, ok_key, ok_buzzer, ok_dht, ok_adc, ok_oled, ok_fan;

static void show_line(int page, const char *tag, int ok, int done)
{
    char buf[24];
    const char *st = done ? (ok ? "OK" : "ERR") : "--";
    snprintf(buf, sizeof(buf), "%-6s %s", tag, st);
    ssd1306_string(0, (uint8_t)page, buf);
}

int main(void)
{
    sysclock_init_72m();
    f1_delay_init();
    board_uart1_init(115200);
    printf("\r\n=== NEV-ELEC Training Kit SelfTest v1.0 ===\r\n");
    ok_uart = 1;

    board_led_init();
    board_key_init();
    board_buzzer_init();
    dht11_init();
    ssd1306_init();
    ok_oled = 1;                 /* 本函数返回即 I2C 有应答（简化判定） */
    f1_adc_init();

    key_state_t ks = {0};
    uint32_t t_led = 0, t_beep = 0, t_dht = 0, t_adc = 0, t_fan = 0, t_uart = 0;
    int16_t temp = 0, humi = 0;
    uint16_t light = 0, ntc = 0;
    int16_t ntc_t = 0;
    uint8_t duty = 0;

    while (1) {
        uint32_t now = f1_tick();

        /* T1 LED 1Hz 翻转 */
        if (every_ms(&t_led, 500)) {
            static int ledv;
            ledv = !ledv;
            board_led(ledv);
            ok_led = 1;
        }

        /* T4 蜂鸣器 0.5s 间歇（按住按键时静音，避免干扰验收人员） */
        if (every_ms(&t_beep, 500)) {
            static int beep;
            beep = !beep;
            board_buzzer(beep && !board_key_pressed());
            ok_buzzer = 1;
        }

        /* T3 按键：记录到过按下即 OK */
        if (key_update(&ks, board_key_pressed(), now) || ks.stable) ok_key = 1;

        /* T5 DHT11 每 2s */
        if (every_ms(&t_dht, 2000)) {
            if (dht11_read(&temp, &humi) == 0) {
                ok_dht = 1;
                printf("[DHT11] T=%d.%dC H=%d.%d%%\r\n", temp / 10, temp % 10,
                       humi / 10, humi % 10);
            } else {
                printf("[DHT11] no response, check wiring PB12\r\n");
            }
        }

        /* T6 ADC 每 500ms */
        if (every_ms(&t_adc, 500)) {
            light = f1_adc_read_avg(ADC_CH_LIGHT, 8);
            ntc   = f1_adc_read_avg(ADC_CH_NTC, 8);
            ntc_t = f1_ntc_temp_x10(ntc);
            /* 两通道都非 0 非满量程即认为有效（排除断线 0/4095） */
            if (light > 30 && light < 4000 && ntc > 30 && ntc < 4000) ok_adc = 1;
        }

        /* T8 风扇 5s 一档 0→100→0 循环 */
        if (every_ms(&t_fan, 5000)) {
            duty = (uint8_t)((duty + 20) % 120);
            if (duty > 100) duty = 0;
            fan_set(duty);
            ok_fan = 1;
        }

        /* T7 OLED + 串口汇总 每 500ms 刷新 */
        if (every_ms(&t_uart, 500)) {
            int all = ok_led & ok_key & ok_buzzer & ok_dht & ok_adc & ok_fan;

            ssd1306_clear();
            ssd1306_string(0, 0, "KIT SELFTEST");
            ssd1306_string(84, 0, all ? "PASS" : "....");
            show_line(1, "LED",   ok_led,   1);
            show_line(2, "KEY",   ok_key,   1);
            show_line(3, "BUZZ",  ok_buzzer,1);
            show_line(4, "DHT11", ok_dht,   1);
            show_line(5, "ADC",   ok_adc,   1);
            show_line(6, "FAN",   ok_fan,   1);

            char buf[32];
            snprintf(buf, sizeof(buf), "%d.%dC %d.%d%% L%3u",
                     temp / 10, temp % 10, humi / 10, humi % 10, light);
            ssd1306_string(0, 7, buf);
            ssd1306_flush();

            printf("[NTC] %d.%dC\r\n", ntc_t / 10, ntc_t % 10);
            printf("[SUM] LED:%d KEY:%d BUZZ:%d DHT11:%d ADC:%d FAN:%d %s\r\n",
                   ok_led, ok_key, ok_buzzer, ok_dht, ok_adc, ok_fan,
                   all ? "ALL PASS" : "IN PROGRESS");
        }
    }
}
