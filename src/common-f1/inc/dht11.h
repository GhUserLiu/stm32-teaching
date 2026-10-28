/**
 * @file    dht11.h
 * @brief   DHT11 温湿度传感器驱动（单总线，PB12）
 */
#ifndef DHT11_H
#define DHT11_H

#include <stdint.h>

/** @brief DHT11 引脚初始化 */
void dht11_init(void);

/**
 * @brief 读取温湿度（阻塞约 25ms，建议 ≥1s 调用一次）
 * @param temp_out 十分之一摄氏度（如 253 = 25.3℃；DHT11 精度 1℃，恒为 x0）
 * @param humi_out 十分之一相对湿度
 * @return 0 成功；-1 器件无响应；-2 校验和错误
 */
int dht11_read(int16_t *temp_out, int16_t *humi_out);

#endif /* DHT11_H */
