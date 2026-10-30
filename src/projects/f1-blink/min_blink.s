@ LED 常亮测试：低电平点亮（共阳），ODR 写 0 = 全亮
    .syntax unified
    .cpu cortex-m3
    .thumb
    .section .text
    .word 0x20000400
    .word Reset_Handler
    .word 0
    .word 0
    .rept 59
    .word 0
    .endr
    .thumb_func
    .global Reset_Handler
Reset_Handler:
    ldr   r0, =0x40021018
    mov   r1, #4
    str   r1, [r0]
    ldr   r1, [r0]

    ldr   r0, =0x40000800
    ldr   r1, =0x00003330       @ PA1/2/3 推挽输出 50MHz
    str   r1, [r0]
    ldr   r1, [r0]

    @ ODR = 0（全部拉低 = LED 全亮，共阳低电平点亮！）
    ldr   r0, =0x4000080C       @ GPIOA_ODR
    mov   r1, #0                @ PA1/2/3 = LOW = 亮！
    str   r1, [r0]

    b     .                      @ 死循环，灯常亮
