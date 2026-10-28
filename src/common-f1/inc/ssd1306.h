/**
 * @file    ssd1306.h
 * @brief   0.96 寸 OLED（SSD1306，I2C 7 位地址 0x3C）驱动 —— 128x64，软件 I2C
 */
#ifndef SSD1306_H
#define SSD1306_H

#include <stdint.h>

#define SSD1306_WIDTH   128
#define SSD1306_HEIGHT  64

/** @brief 软件 I2C 引脚与 SSD1306 初始化（PB6=SCL PB7=SDA，见 board_f1.h） */
void ssd1306_init(void);

/** @brief 全屏填充/清屏（0=黑 1=亮） */
void ssd1306_fill(uint8_t val);
void ssd1306_clear(void);

/** @brief 把帧缓冲推送到屏（每帧绘制后调用） */
void ssd1306_flush(void);

/**
 * @brief 在 (x, y) 显示一个 6x8 ASCII 字符（x 单位=像素列，y 单位=页 0~7）
 */
void ssd1306_char(uint8_t x, uint8_t page, char c);

/** @brief 显示字符串 */
void ssd1306_string(uint8_t x, uint8_t page, const char *s);

/** @brief 显示无符号整数（十进制） */
void ssd1306_uint(uint8_t x, uint8_t page, uint32_t v);

#endif
