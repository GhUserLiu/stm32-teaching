#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试数据生成脚本
Generate Test Data for Auto Grading System

生成符合规范格式的测试数据，用于GUI应用测试。
"""

import os
import zipfile
from pathlib import Path
from datetime import datetime


def create_sample_report(class_name: str, student_id: str, name: str) -> str:
    """创建示例实验报告内容"""
    return f"""
# {class_name} - 汽车档位模拟器设计实验报告

## 一、团队信息与分工

**学号**: {student_id}
**姓名**: {name}
**组号**: 第1组

**个人分工**:
- 负责GPIO配置和中断初始化
- 实现状态机逻辑
- 编写测试报告

## 二、实验目的与原理

### 实验目的
1. 掌握STM32外部中断的使用方法
2. 学习使用DWT计数器实现精确消抖
3. 理解状态机的设计和实现

### 实验原理
本实验通过外部中断检测按键按下，使用DWT周期计数器实现50ms消抖，通过状态机切换档位。

## 三、硬件设计与连接

### 硬件连接图
- LED0连接PF9（低电平有效）
- LED1连接PF10（低电平有效）
- KEY0连接PE4（外部中断，下降沿触发）

### 引脚配置
```c
GPIO_InitTypeDef GPIO_InitStruct = {0};
GPIO_InitStruct.Pin = GPIO_PIN_9 | GPIO_PIN_10;
GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
GPIO_InitStruct.Pull = GPIO_PULLUP;
HAL_GPIO_Init(GPIOF, &GPIO_InitStruct);
```

## 四、软件设计与实现

### 代码流程图
1. 初始化HAL库
2. 配置系统时钟
3. 初始化GPIO和外部中断
4. 主循环检测状态变化

### 关键代码
```c
// 档位枚举
typedef enum {{
    GEAR_P,   // 驻车档
    GEAR_R,   // 倒车档
    GEAR_N,   // 空档
    GEAR_D    // 行驶档
}} GearState;

// 当前档位
GearState current_gear = GEAR_P;
```

### 中断服务程序
```c
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{{
    // DWT消抖处理
    static uint32_t last_tick = 0;
    uint32_t current_tick = DWT->CYCCNT;

    if (current_tick - last_tick > 84000000) {{  // 约50ms@168MHz
        last_tick = current_tick;
        // 切换档位
        switch_gear();
    }}
}}
```

### 代码模块划分
- main.c: 主程序和状态机逻辑
- stm32f4xx_it.c: 中断服务函数
- gpio.c: GPIO配置函数

## 五、实验结果分析

### 实验现象记录
1. 上电后，LED0点亮，LED1熄灭（P档）
2. 按下按键，档位切换：P→R→N→D→P循环
3. LED状态正确显示当前档位

### 结果照片
（测试照片略）

### 结果对比分析
实际测试结果与预期一致，档位切换逻辑正确，LED显示符合要求。

## 六、问题与讨论

### 调试问题
1. 初始开发时LED状态不正确
2. 解决：检查LED极性，发现是低电平有效

### 团队协作
与小组成员讨论状态机设计，确定使用枚举类型管理档位状态。

### 个人心得
通过本次实验，我深入理解了STM32外部中断和DWT消抖的原理，学会了使用状态机处理复杂逻辑。

## 七、思考题回答

**Q1：为什么按键配置为下降沿触发？**
答：因为按键按下时电平从高变低（有上拉电阻），下降沿更可靠地检测按键动作。

**Q2：DWT消抖与软件延时消抖的区别？**
答：DWT使用硬件计数器，不阻塞CPU，精度高；软件延时阻塞CPU，影响实时性。
"""


def create_sample_source():
    """创建示例源代码"""
    return {
        "main.c": """
#include "stm32f4xx_hal.h"
#include "gpio.h"
#include "dwt.h"

// 档位枚举
typedef enum {
    GEAR_P,   // 驻车档
    GEAR_R,   // 倒车档
    GEAR_N,   // 空档
    GEAR_D    // 行驶档
} GearState;

// 当前档位
GearState current_gear = GEAR_P;

int main(void)
{
    HAL_Init();
    SystemClock_Config();

    // 初始化DWT
    DWT_Init();

    // 初始化GPIO
    MX_GPIO_Init();

    // 初始状态：P档
    update_gear_led(GEAR_P);

    while (1)
    {
        // 主循环可以添加其他任务
        HAL_Delay(100);
    }
}

// 切换档位
void switch_gear(void)
{
    switch (current_gear)
    {
        case GEAR_P:
            current_gear = GEAR_R;
            break;
        case GEAR_R:
            current_gear = GEAR_N;
            break;
        case GEAR_N:
            current_gear = GEAR_D;
            break;
        case GEAR_D:
            current_gear = GEAR_P;
            break;
    }
    update_gear_led(current_gear);
}

// 更新LED显示
void update_gear_led(GearState gear)
{
    switch (gear)
    {
        case GEAR_P:  // P档：LED0亮，LED1灭
            HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(GPIOF, GPIO_PIN_10, GPIO_PIN_SET);
            break;
        case GEAR_R:  // R档：LED0灭，LED1亮
            HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_SET);
            HAL_GPIO_WritePin(GPIOF, GPIO_PIN_10, GPIO_PIN_RESET);
            break;
        case GEAR_N:  // N档：都灭
            HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_SET);
            HAL_GPIO_WritePin(GPIOF, GPIO_PIN_10, GPIO_PIN_SET);
            break;
        case GEAR_D:  // D档：都亮
            HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(GPIOF, GPIO_PIN_10, GPIO_PIN_RESET);
            break;
    }
}

// 中断回调函数
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    static uint32_t last_tick = 0;
    uint32_t current_tick = DWT->CYCCNT;

    // 50ms消抖 @168MHz
    if (current_tick - last_tick > 84000000)
    {
        last_tick = current_tick;
        switch_gear();
    }
}
""",
        "stm32f4xx_it.c": """
#include "stm32f4xx_hal.h"
#include "stm32f4xx_it.h"

void EXTI4_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_4);
}
""",
        "dwt.h": """
#ifndef DWT_H
#define DWT_H

#include <stdint.h>

void DWT_Init(void);
uint32_t DWT_Get_Cycles(void);

#endif
""",
        "dwt.c": """
#include "dwt.h"
#include "stm32f4xx_hal.h"

void DWT_Init(void)
{
    // 使能DWT
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

uint32_t DWT_Get_Cycles(void)
{
    return DWT->CYCCNT;
}
"""
    }


def create_student_zip(
    output_dir: Path,
    class_name: str,
    student_id: str,
    name: str
):
    """创建学生提交压缩包"""
    student_zip_name = f"{student_id}-{name}.zip"
    student_zip_path = output_dir / student_zip_name

    # 创建临时目录
    import tempfile
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # 1. 创建实验报告
        report_content = create_sample_report(class_name, student_id, name)
        report_path = temp_dir / "实验报告.txt"
        report_path.write_text(report_content, encoding='utf-8')

        # 2. 创建源代码压缩包
        source_zip_path = temp_dir / "源代码.zip"
        with zipfile.ZipFile(source_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            sources = create_sample_source()
            for filename, content in sources.items():
                zf.writestr(filename, content)

        # 3. 创建学生压缩包
        with zipfile.ZipFile(student_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(report_path, "实验报告.txt")
            zf.write(source_zip_path, "源代码.zip")

        print(f"[OK] 创建学生提交: {student_zip_name}")

    finally:
        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir)


def create_class_zip(
    output_dir: Path,
    class_name: str,
    experiment_id: str,
    num_students: int = 5
):
    """创建班级压缩包"""
    print(f"\n创建班级测试数据...")
    print(f"班级: {class_name}")
    print(f"实验: {experiment_id}")
    print(f"学生数: {num_students}")

    # 示例学生数据
    students = [
        ("23071140101", "张三"),
        ("23071140102", "李四"),
        ("23071140103", "王五"),
        ("23071140104", "赵六"),
        ("23071140105", "钱七"),
    ]

    if num_students > len(students):
        # 生成更多学生
        for i in range(len(students), num_students):
            student_id = f"2307114010{((i % 5) + 1)}{chr(65 + i)}"
            students.append((student_id, f"学生{i+1}"))

    # 创建班级临时目录
    class_temp_dir = output_dir / f"{class_name}_{experiment_id}"
    class_temp_dir.mkdir(exist_ok=True)

    # 创建学生压缩包
    for student_id, name in students[:num_students]:
        create_student_zip(class_temp_dir, class_name, student_id, name)

    # 创建班级压缩包
    class_zip_name = f"{class_name}-{experiment_id}.zip"
    class_zip_path = output_dir / class_zip_name

    with zipfile.ZipFile(class_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for student_zip in class_temp_dir.glob("*.zip"):
            zf.write(student_zip, student_zip.name)

    # 清理临时目录
    import shutil
    shutil.rmtree(class_temp_dir)

    print(f"\n[OK] 班级压缩包创建完成: {class_zip_name}")
    print(f"  位置: {class_zip_path.absolute()}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='生成测试数据')
    parser.add_argument('--output', type=Path, default='test_data', help='输出目录')
    parser.add_argument('--class-name', type=str, default='汽服2302B班', help='班级名称')
    parser.add_argument('--experiment-id', type=str, default='07-car-gear', help='实验ID')
    parser.add_argument('--num-students', type=int, default=5, help='学生数量')

    args = parser.parse_args()

    # 创建输出目录
    args.output.mkdir(exist_ok=True)

    # 生成班级压缩包
    create_class_zip(
        args.output,
        args.class_name,
        args.experiment_id,
        args.num_students
    )

    print(f"\n测试数据已生成到: {args.output.absolute()}")
    print(f"\n使用方法:")
    print(f"1. 启动GUI: python -m auto_grading_gui.main")
    print(f"2. 选择压缩包: {args.output.absolute()}/{args.class_name}-{args.experiment_id}.zip")


if __name__ == '__main__':
    main()
