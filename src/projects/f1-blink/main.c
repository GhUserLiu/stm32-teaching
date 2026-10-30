/**
 * @file    main.c
 * @brief   终极扫脚：全部 33 个 GPIO 同时闪（PA0~15 + PB0~15 + PC13）
 */
#include "stm32f103x_min.h"

void my_delay(volatile uint32_t n) { while(n--) __asm("nop"); }

int main(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPA | RCC_APB2ENR_IOPB | RCC_APB2ENR_IOPC;

    /* PA0~PA15 + PB0~PB15 全推挽输出：CRL + CRH 都写 */
    GPIOA->CRL = 0x22222222;
    GPIOA->CRH = 0x22222222;
    GPIOB->CRL = 0x22222222;
    GPIOB->CRH = 0x22222222;
    /* PC13 推挽输出（CRL 位 20~23） */
    GPIOC->CRL = (GPIOC->CRL & ~(0xFu << 20)) | (0x2u << 20);

    while (1) {
        GPIOA->BSRR = 0xFFFFFFFF;
        GPIOB->BSRR = 0xFFFFFFFF;
        GPIOC->BSRR = (1u << 13);
        my_delay(400000);
        GPIOA->BRR = 0xFFFFFFFF;
        GPIOB->BRR = 0xFFFFFFFF;
        GPIOC->BRR = (1u << 13);
        my_delay(400000);
    }
}
