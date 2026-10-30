# GPIO 调试状态（2026-10-30 深夜存档）

> 新会话从此文档恢复上下文。问题锁定但未解决。

## 核心矛盾

| 路径 | 写 GPIO | 结果 |
|---|---|---|
| **SWD（OpenOCD）** 写 ODR | `mww 0x4000080C 0xFFFF` | ✅ **LED 灭了**（证明 SWD→GPIO 通） |
| **CPU 固件** 写 CRL+ODR | 全部 33 脚输出低 | ❌ **LED 不亮**（证明 CPU→GPIO 不通） |

两条路径理论上走同一 AHB 总线到达同一外设，但行为不同。

## 已排除

- ❌ DAP/SWD/Flash 问题（链路完美，官方固件正常跑）
- ❌ 时钟频率（HSI 8MHz 和 PLL 64MHz 都试过）
- ❌ 引脚号错误（全部 33 脚都试过）
- ❌ 向量表位置（已修正并验证）
- ❌ GPIO 时钟未使能（RCC 读回确认已使能）
- ❌ 固件未执行（SRAM 步骤标记全部写入成功）

## 已确认

- ✅ 官方固件（Keil 编译）正常控制 LED
- ✅ SWD 写 GPIO ODR **有效**（LED 响应）
- ✅ SWD 读 GPIO **无效**（永远返回 0x00000000，可能只写寄存器）
- ✅ CPU 固件写入 RCC **有效**（读回正确）
- ✅ CPU 固件写入 SRAM **有效**（步骤标记正确）
- ❌ CPU 固件写入 GPIO **无效**（LED 不响应）

## 芯片信息

- 丝印：STM32F103C8T6（批号 99GIP，疑兼容片）
- SWD DPIDR：0x1BA01477
- Device ID：0x20036410（中等密度）
- 板卡：野火小智核心板双 USB 款（插扩展板上）

## 明天计划

### 方案 A：改造官方固件（推荐）
1. 用 Python 读官方 hex → 修改延时值 → 写回 hex → 烧录
2. 确认修改后的官方固件仍然跑（证明可以改）
3. 逐步替换代码段，找到精确断点

### 方案 B：地址空间扫描
1. 官方固件运行中 → halt → 用 OpenOCD `mww` 写不同地址区间
2. 找到 LED 实际响应的地址（GPIO 真实基址）

### 方案 C：反编译官方固件
1. 完整反汇编官方 hex（Thumb 模式）
2. 找到 GPIO 写入指令的实际目标地址
3. 用该地址重写我们的代码

## 文件位置

- 官方流水灯 hex：`outputs/tmp_led.hex`
- 官方按键点灯 hex：`outputs/tmp_key.hex`
- 官方 bin（正确解析）：`outputs/official_led.bin`
- 我们的测试固件：`outputs/st.bin`（最新版=全端口常亮测试）
- SRAM 诊断结果：`outputs/sram*.bin`
- OpenOCD：`D:\arm_tool\xpack-openocd-0.12.0-7\bin\openocd.exe`
- 编译器：`C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\`
- DAP 设备：VID_0416&PID_5021（CMSIS-DAP v1.2.0）

## 烧录命令模板

```powershell
cd D:\4-Workspace\教学\单片机
$ocd = 'D:\arm_tool\xpack-openocd-0.12.0-7\bin\openocd.exe'
$cfg = 'D:\arm_tool\xpack-openocd-0.12.0-7\share\openocd\scripts'
& $ocd -s $cfg -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg -c "init; reset halt; program outputs/st.bin 0x08000000 verify; reset run; shutdown"
```

## 编译命令模板

```powershell
$dir = 'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin'
& "$dir\arm-none-eabi-as.exe" -mcpu=cortex-m3 -mthumb <file>.s -o <file>.o
& "$dir\arm-none-eabi-ld.exe" -Ttext=0x08000000 <file>.o -o <file>.elf
& "$dir\arm-none-eabi-objcopy.exe" -O binary -S <file>.elf outputs/st.bin
```
