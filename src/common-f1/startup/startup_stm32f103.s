/**
 * @file    startup_stm32f103.s
 * @brief   STM32F103C8T6 最小启动文件（向量表 + 默认中断处理）
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .isr_vector, "a", %progbits
    .word _estack               /* 0: 初始栈顶（RAM 末尾） */
    .word Reset_Handler         /* 1: 复位 */
    .word Default_Handler       /* 2: NMI */
    .word HardFault_Handler     /* 3: HardFault */
    .word Default_Handler       /* 4: MemManage */
    .word Default_Handler       /* 5: BusFault */
    .word Default_Handler       /* 6: UsageFault */
    .word 0                     /* 7 */
    .word 0                     /* 8 */
    .word 0                     /* 9 */
    .word 0                     /* 10 */
    .word Default_Handler       /* 11: SVCall */
    .word Default_Handler       /* 12: DebugMon */
    .word 0                     /* 13 */
    .word Default_Handler       /* 14: PendSV */
    .word SysTick_Handler       /* 15: SysTick */

    /* 外设中断（IRQ0~43，C8T6 实际到 IRQ59，留到 43 已覆盖实训所需） */
    .rept 44
    .word Default_Handler
    .endr

    .section .text
    .weak Default_Handler
    .thumb_func
Default_Handler:
    b Default_Handler

    .weak HardFault_Handler
    .thumb_set HardFault_Handler, Default_Handler

    .global Reset_Handler
    .thumb_func
Reset_Handler:
    /* 复制 .data 从 Flash 到 RAM */
    ldr r0, =_sdata
    ldr r1, =_edata
    ldr r2, =_sidata
1:  cmp r1, r0
    beq 2f
    ldr r3, [r2], #4
    str r3, [r0], #4
    b 1b
2:  /* 清零 .bss */
    ldr r0, =_sbss
    ldr r1, =_ebss
3:  cmp r1, r0
    beq 4f
    mov r3, #0
    str r3, [r0], #4
    b 3b
4:  bl main
    b Default_Handler

    .end
