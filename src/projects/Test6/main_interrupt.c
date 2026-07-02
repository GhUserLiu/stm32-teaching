/**
 ******************************************************************************
 * @file           : main_interrupt.c
 * @brief          : Test6 - 最简LED测试（完全复制之前能工作的方式）
 ******************************************************************************
 */

#include <stdint.h>

/* ========== 寄存器地址 ========== */
#define RCC_AHB1ENR_ADDR   (*(volatile uint32_t*)0x40023830)
#define GPIOF_BASE         0x40021400
#define GPIOF_MODER_ADDR   (*(volatile uint32_t*)(GPIOF_BASE + 0x00))
#define GPIOF_ODR_ADDR     (*(volatile uint32_t*)(GPIOF_BASE + 0x14))

/* ========== 简单延时函数 ========== */
void simple_delay(uint32_t count)
{
    while (count--)
    {
        __asm volatile("nop");
    }
}

/* ========== 主函数 ========== */
int main(void)
{
    /* 1. 使能GPIOF时钟 */
    RCC_AHB1ENR_ADDR |= (1U << 5);  // bit 5 = GPIOF

    /* 2. 配置PF9和PF10为输出模式 */
    GPIOF_MODER_ADDR &= ~(0x3U << (9 * 2));   // 清除PF9
    GPIOF_MODER_ADDR |= (0x1U << (9 * 2));    // PF9 = 输出
    GPIOF_MODER_ADDR &= ~(0x3U << (10 * 2));  // 清除PF10
    GPIOF_MODER_ADDR |= (0x1U << (10 * 2));   // PF10 = 输出

    /* 3. 主循环 - LED交替闪烁 */
    while (1)
    {
        /* 点亮LED0 (PF9) - 低电平 */
        GPIOF_ODR_ADDR &= ~(1U << 9);
        GPIOF_ODR_ADDR |= (1U << 10);  // LED1灭
        simple_delay(500000);

        /* 点亮LED1 (PF10) - 低电平 */
        GPIOF_ODR_ADDR |= (1U << 9);   // LED0灭
        GPIOF_ODR_ADDR &= ~(1U << 10);
        simple_delay(500000);
    }

    return 0;
}

/* ========== 外部变量 ========== */
extern uint32_t _estack;
extern uint32_t _sidata, _sdata, _edata;
extern uint32_t _sbss, _ebss;

/* ========== Reset_Handler ========== */
void Reset_Handler(void)
{
    uint32_t *src, *dst;

    /* 设置栈指针 */
    __asm volatile("ldr sp, =_estack");

    /* 复制data段 */
    src = &_sidata;
    dst = &_sdata;
    while (dst < &_edata)
        *dst++ = *src++;

    /* 清零bss段 */
    dst = &_sbss;
    while (dst < &_ebss)
        *dst++ = 0;

    /* 调用主函数 */
    main();

    while (1);
}

/* ========== 异常处理 ========== */
void NMI_Handler(void)        { while (1); }
void HardFault_Handler(void)  { while (1); }
void MemManage_Handler(void)  { while (1); }
void BusFault_Handler(void)   { while (1); }
void UsageFault_Handler(void) { while (1); }
void SVC_Handler(void)        { while (1); }
void DebugMon_Handler(void)   { while (1); }
void PendSV_Handler(void)     { while (1); }
