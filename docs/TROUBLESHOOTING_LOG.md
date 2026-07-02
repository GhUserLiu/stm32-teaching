# STM32F407 转向灯项目 - 故障排查日志

## 日志说明
本文档记录项目开发过程中遇到的问题、原因分析、检查方法和解决方案。

---

## 错误记录 #1

### 问题描述
**日期**: 2026-05-24
**项目**: 01-turn-signal（转向灯）
**现象**: 烧录成功但LED不亮

### 错误原因分析

#### 根本原因
代码已修改为LED常亮测试，但编译后的二进制文件仍是旧版本（闪烁模式），导致烧录的是旧代码。

#### 技术细节
1. **源代码与编译输出不一致**：main.c中修改了LED为常亮（GPIO_PIN_RESET），但编译生成的代码仍是闪烁模式
2. **向量表正确**：Reset_Handler地址0x08000361指向正确的代码
3. **GPIO配置正确**：GPIOF时钟、MODER、ODR寄存器设置均正确
4. **问题定位**：通过反汇编发现main函数中调用的是LED闪烁逻辑，而非常亮逻辑

### 检查方法

#### 1. 验证编译输出
```bash
# 检查hex文件时间戳
ls -la build/01-turn-signal/Debug/*.hex

# 反汇编检查main函数
arm-none-eabi-objdump -d build/01-turn-signal/Debug/01-turn-signal.elf | grep -A 30 "<main>"
```

#### 2. 检查向量表
```bash
# 查看向量表前4个向量
head -2 build/01-turn-signal/Debug/01-turn-signal.hex
# 应该看到：栈指针和Reset_Handler地址
```

#### 3. 验证文件大小
```bash
# 对比新旧文件大小
# 旧版本（闪烁）：bin约1268字节
# 新版本（常亮）：bin约1896字节
```

#### 4. 硬件检查
- **BOOT跳线**: 确保BOOT0接GND（从Flash启动）
- **供电**: 检查3.3V电源是否正常
- **万用表测试**: 测量PF9/PF10引脚电平

### 解决方案

#### 方法1：强制重新编译
```bash
make clean && make
```

#### 方法2：使用寄存器直接操作（最终方案）
在Reset_Handler中直接操作寄存器初始化LED，绕过HAL库的潜在问题：

```c
/* GPIOF LED寄存器初始化 */
RCC_AHB1ENR_ADDR |= (1U << 5);              // 使能GPIOF时钟

GPIOF_MODER_ADDR &= ~(0x3U << (9 * 2));    // 清除PF9模式位
GPIOF_MODER_ADDR |= (0x1U << (9 * 2));      // PF9 = 输出
GPIOF_MODER_ADDR &= ~(0x3U << (10 * 2));   // 清除PF10模式位
GPIOF_MODER_ADDR |= (0x1U << (10 * 2));     // PF10 = 输出

GPIOF_ODR_ADDR |= (1U << 9);                // PF9 = 1（灭）
GPIOF_ODR_ADDR |= (1U << 10);               // PF10 = 1（灭）
```

### 硬件配置确认

| 参数 | 值 | 说明 |
|------|-----|------|
| LED类型 | 共阳极 | 低电平点亮 |
| LED引脚 | PF9, PF10 | 左转、右转 |
| 点亮电平 | 低电平（0V） | GPIO_PIN_RESET |
| 熄灭电平 | 高电平（3.3V） | GPIO_PIN_SET |

### 经验总结

1. **修改代码后务必重新编译**：仅保存文件不会自动更新二进制输出
2. **验证编译输出**：通过反汇编确认代码逻辑
3. **寄存器直接操作更可靠**：在关键初始化代码中使用寄存器操作，避免HAL库潜在问题
4. **简化测试**：遇到问题时，先用最简单的代码验证硬件

### 相关文件

- 主程序: [projects/01-turn-signal/main.c](../projects/01-turn-signal/main.c)
- 硬件配置: [common/hal/board.h](../common/hal/board.h)
- 编译脚本: [Makefile](../Makefile)

---

## 检查清单

### 编译前检查
- [ ] 确认源代码已保存
- [ ] 确认使用正确的项目配置
- [ ] 执行 `make clean` 清理旧文件

### 编译后检查
- [ ] 检查编译输出无错误
- [ ] 验证生成的hex/bin文件时间戳
- [ ] 检查文件大小是否合理

### 烧录前检查
- [ ] 确认烧录地址为 0x08000000
- [ ] 确认BOOT0接GND
- [ ] 确认开发板供电正常

### 烧录后检查
- [ ] 观察LED状态
- [ ] 如不亮，用万用表测量引脚电平
- [ ] 检查向量表和Reset_Handler地址

---

## 附录：寄存器地址参考

| 寄存器 | 地址 | 说明 |
|--------|------|------|
| RCC_BASE | 0x40023800 | RCC基地址 |
| RCC_AHB1ENR | 0x40023830 | AHB1外设时钟使能寄存器 |
| GPIOF_BASE | 0x40021400 | GPIOF基地址 |
| GPIOF_MODER | 0x40021400 | 模式寄存器 |
| GPIOF_ODR | 0x40021414 | 输出数据寄存器 |

| AHB1ENR位 | 外设 |
|----------|------|
| Bit 0 | GPIOA |
| Bit 4 | GPIOE |
| Bit 5 | GPIOF |
