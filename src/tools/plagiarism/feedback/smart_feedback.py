#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能反馈建议系统
Smart Feedback Recommendation System

基于学生报告的具体问题，生成针对性的改进建议和学习资源推荐
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path


class LearningResource:
    """学习资源"""
    def __init__(self, title: str, url: str, resource_type: str, description: str = ""):
        self.title = title
        self.url = url
        self.resource_type = resource_type  # doc, video, tutorial, example
        self.description = description


class FeedbackCategory(Enum):
    """反馈类别"""
    TECHNICAL = "technical"       # 技术问题
    STRUCTURE = "structure"       # 结构问题
    CODE = "code"                # 代码问题
    WRITING = "writing"          # 写作问题
    COMPLETENESS = "completeness" # 完整性问题


@dataclass
class SmartFeedback:
    """智能反馈"""
    category: FeedbackCategory
    priority: int              # 优先级 1-5
    problem_description: str   # 问题描述
    specific_suggestion: str   # 具体建议
    learning_resources: List[LearningResource] = field(default_factory=list)
    example_code: str = ""     # 示例代码
    expected_improvement: str = ""  # 预期改进


class SmartFeedbackEngine:
    """智能反馈引擎"""

    # 知识库：问题映射到反馈建议
    KNOWLEDGE_BASE = {
        # 技术问题 - GPIO
        "gpio_missing": {
            "patterns": [r'缺少.*GPIO', r'GPIO.*配置.*错误', r'GPIO.*不完整'],
            "feedback": SmartFeedback(
                category=FeedbackCategory.TECHNICAL,
                priority=5,
                problem_description="GPIO配置说明不完整",
                specific_suggestion="""
1. 在报告中添加GPIO配置说明表，包含：
   - 引脚功能（如LED0/LED1/按键）
   - GPIO引脚号（如PF9/PF10/PE4）
   - 配置模式（输出/中断/上拉）
   - 速度等级

2. 示例表格格式：
| 功能   | GPIO引脚 | 配置模式       | 说明         |
|--------|----------|----------------|--------------|
| LED0   | PF9      | 推挽输出       | 低电平点亮   |
| LED1   | PF10     | 推挽输出       | 低电平点亮   |
| 按键   | PE4      | 外部中断+上拉  | 下降沿触发   |
                """,
                learning_resources=[
                    LearningResource(
                        title="STM32 GPIO配置指南",
                        url="https://doc嵌入式.org/gpio-guide",
                        resource_type="doc",
                        description="GPIO工作原理和配置方法"
                    )
                ]
            )
        },

        # 技术问题 - 中断
        "interrupt_missing": {
            "patterns": [r'缺少.*中断', r'中断.*配置.*错误', r'EXTI.*不完整'],
            "feedback": SmartFeedback(
                category=FeedbackCategory.TECHNICAL,
                priority=5,
                problem_description="中断配置说明不完整",
                specific_suggestion="""
1. 补充中断配置说明：
   - 中断线配置（EXTI4 for PE4）
   - 触发方式（下降沿/上升沿/双边沿）
   - 中断优先级设置
   - 中断服务函数实现

2. 关键代码示例：
```c
// 1. 使能时钟
__HAL_RCC_GPIOE_CLK_ENABLE();

// 2. 配置GPIO为中断模式
GPIO_InitStruct.Pin = GPIO_PIN_4;
GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;  // 下降沿触发
GPIO_InitStruct.Pull = GPIO_PULLUP;          // 内部上拉
HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);

// 3. 配置中断优先级
HAL_NVIC_SetPriority(EXTI4_IRQn, 5, 0);
HAL_NVIC_EnableIRQ(EXTI4_IRQn);

// 4. 实现中断回调
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if(GPIO_Pin == GPIO_PIN_4)
    {
        // 消抖处理...
        // 状态切换...
    }
}
```
                """,
                learning_resources=[
                    LearningResource(
                        title="STM32外部中断详解",
                        url="https://doc嵌入式.org/exti-guide",
                        resource_type="doc",
                        description="EXTI工作原理和配置步骤"
                    )
                ]
            )
        },

        # 技术问题 - DWT消抖
        "dwt_missing": {
            "patterns": [r'缺少.*DWT', r'DWT.*不完整', r'消抖.*未实现'],
            "feedback": SmartFeedback(
                category=FeedbackCategory.TECHNICAL,
                priority=4,
                problem_description="DWT消抖实现缺失或不完整",
                specific_suggestion="""
1. DWT消抖原理：
   - 使用ARM Cortex-M4的DWT（Data Watchpoint and Trace）单元
   - CYCCNT计数器提供精确的周期计数
   - 不阻塞CPU，优于软件延时消抖

2. 完整实现代码：
```c
// DWT初始化（在main函数开始）
void DWT_Init(void)
{
    // 使能DWT
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;

    // 复位CYCCNT计数器
    DWT->CYCCNT = 0;

    // 使能CYCCNT
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    // 解锁（部分MCU需要）
    // *((volatile uint32_t*)0xE0001FB0) = 0xC5ACCE55;
}

// 消抖函数（在中断回调中使用）
#define DEBOUNCE_CYCLES (50 * 84000000 / 1000)  // 50ms@168MHz

static uint32_t last_interrupt = 0;

uint32_t DWT_Get_Tick(void)
{
    return DWT->CYCCNT;
}

int DWT_Time_Elapsed(uint32_t start, uint32_t cycles)
{
    return ((DWT_Get_Tick() - start) >= cycles);
}

// 在中断回调中
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    static uint32_t last_tick = 0;

    // 消抖检查
    if(DWT_Time_Elapsed(last_tick, DEBOUNCE_CYCLES))
    {
        last_tick = DWT_Get_Tick();

        // 状态切换逻辑...
    }
}
```
                """,
                learning_resources=[
                    LearningResource(
                        title="DWT精确消抖实现",
                        url="https://doc嵌入式.org/dwt-debounce",
                        resource_type="tutorial",
                        description="DWT消抖完整教程"
                    )
                ]
            )
        },

        # 技术问题 - 状态机
        "state_machine_missing": {
            "patterns": [r'缺少.*状态机', r'状态.*不完整', r'档位.*逻辑.*错误'],
            "feedback": SmartFeedback(
                category=FeedbackCategory.TECHNICAL,
                priority=5,
                problem_description="状态机实现不完整或逻辑有误",
                specific_suggestion="""
1. 档位状态机实现要点：
   - 使用enum定义状态枚举
   - 使用switch-case实现状态转换
   - 实现P→R→N→D循环切换
   - D档直接切R档需经过N档

2. 推荐实现方式：
```c
// 定义状态枚举
typedef enum {
    GEAR_P = 0,
    GEAR_R,
    GEAR_N,
    GEAR_D
} GearState_t;

// 当前状态
GearState_t current_gear = GEAR_P;

// 状态转换函数
void Gear_Switch(void)
{
    switch(current_gear)
    {
        case GEAR_P:
            current_gear = GEAR_R;  // P → R
            break;

        case GEAR_R:
            current_gear = GEAR_N;  // R → N
            break;

        case GEAR_N:
            current_gear = GEAR_D;  // N → D
            break;

        case GEAR_D:
            current_gear = GEAR_P;  // D → P
            break;

        default:
            current_gear = GEAR_P;
            break;
    }

    // 更新LED显示
    Gear_Update_LED();
}

// LED显示更新
void Gear_Update_LED(void)
{
    switch(current_gear)
    {
        case GEAR_P:  // P档: LED0亮，LED1灭
            HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, GPIO_PIN_SET);
            break;

        case GEAR_R:  // R档: LED0灭，LED1亮
            HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, GPIO_PIN_SET);
            HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, GPIO_PIN_RESET);
            break;

        case GEAR_N:  // N档: LED0灭，LED1灭
            HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, GPIO_PIN_SET);
            HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, GPIO_PIN_SET);
            break;

        case GEAR_D:  // D档: LED0亮，LED1亮
            HAL_GPIO_WritePin(LED0_GPIO_Port, LED0_Pin, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(LED1_GPIO_Port, LED1_Pin, GPIO_PIN_RESET);
            break;
    }
}
```

3. 思考题：D档如何直接切到R档？
   答案：在状态机中添加条件判断，D档时按键先切换到N档，再按一次才到R档
                """,
                learning_resources=[
                    LearningResource(
                        title="状态机设计模式",
                        url="https://doc嵌入式.org/state-machine",
                        resource_type="doc",
                        description="有限状态机(FSM)设计原理"
                    )
                ]
            )
        },

        # 代码问题 - 注释
        "code_comment_lacking": {
            "patterns": [r'注释.*不足', r'代码.*缺少.*注释', r'注释.*偏少'],
            "feedback": SmartFeedback(
                category=FeedbackCategory.CODE,
                priority=3,
                problem_description="代码注释不足",
                specific_suggestion="""
良好的代码注释应该：

1. 文件头部注释：
```c
/**
  * @file    main.c
  * @brief   汽车档位模拟器主程序
  * @details 使用STM32F407实现档位状态机
  *          - PE4按键触发外部中断
  *          - PF9/PF10 LED显示档位状态
  *          - DWT实现50ms消抖
  * @author  学生姓名
  * @date    2026-06-10
  */
```

2. 函数注释：
```c
/**
  * @brief  初始化DWT周期计数器
  * @retval None
  * @note   用于实现精确的软件消抖
  */
void DWT_Init(void)
{
    // ...
}
```

3. 关键代码注释：
```c
// 使能DWT单元（Data Watchpoint and Trace）
CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;

// 复位周期计数器
DWT->CYCCNT = 0;

// 使能周期计数器（CYCCNT）
DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
```

4. 行内注释：
```c
gear_state = (gear_state + 1) % 4;  // 循环切换状态 (0-3)
```

注释比例建议：代码总行数的15-25%
                """,
                learning_resources=[
                    LearningResource(
                        title="C代码注释规范",
                        url="https://doc嵌入式.org/c-comments",
                        resource_type="doc",
                        description="Doxygen注释标准"
                    )
                ]
            )
        },

        # 代码问题 - 函数规范
        "code_function_naming": {
            "patterns": [r'函数.*命名.*规范', r'驼峰.*命名'],
            "feedback": SmartFeedback(
                category=FeedbackCategory.CODE,
                priority=2,
                problem_description="函数命名不规范",
                specific_suggestion="""
嵌入式C代码命名规范：

1. 函数命名：小写字母+下划线
   ✓ 正确：`hal_gpio_init()`, `get_gear_state()`, `timer_start()`
   ✗ 错误：`HalGpioInit()`, `getGearState()`, `TimerStart()`

2. 模块前缀：添加模块名前缀
   ✓ `gear_init()`, `gear_switch()`, `gear_update_led()`
   ✓ `led_on()`, `led_off()`, `led_toggle()`

3. 私有函数：添加static
   ```c
   static void update_display(void)  // 内部使用
   void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)  // HAL回调
   ```

4. 宏定义：全大写+下划线
   ✓ `#define LED_ON_PIN  GPIO_PIN_9`
   ✓ `#define MAX_GEAR    4`
   ✗ `#define ledPin  GPIO_PIN_9`

命名示例：
```c
// 文件: gear_control.c

// 状态枚举
typedef enum {
    GEAR_P = 0,  // 驻车档
    GEAR_R,       // 倒档
    GEAR_N,       // 空档
    GEAR_D        // 前进档
} GearState_t;

// 函数声明
void gear_init(void);
void gear_switch(void);
static void gear_update_led(GearState_t state);
```
                """,
                learning_resources=[
                    LearningResource(
                        title="嵌入式C代码命名规范",
                        url="https://doc嵌入式.org/c-naming",
                        resource_type="doc",
                        description="MISRA-C命名规范"
                    )
                ]
            )
        },

        # 结构问题 - 流程图
        "flowchart_missing": {
            "patterns": [r'缺少.*流程图', r'流程图.*不完整'],
            "feedback": SmartFeedback(
                category=FeedbackCategory.STRUCTURE,
                priority=3,
                problem_description="代码流程图缺失或不完整",
                specific_suggestion="""
1. 流程图绘制工具：
   - draw.io (免费在线工具)
   - Visio (Windows)
   - ProcessOn (在线)

2. 档位实验主程序流程图：
```
  ┌──────────┐
  │  系统初始化  │
  └─────┬────┘
        ▼
  ┌──────────┐
  │ DWT初始化 │
  └─────┬────┘
        ▼
  ┌──────────┐
  │GPIO初始化 │
  └─────┬────┘
        ▼
  ┌──────────┐
  │中断使能   │
  └─────┬────┘
        ▼
  ┌──────────┐
  │  等待中断  │◄────┐
  └─────┬────┘     │
        ▼          │
  ┌──────────┐     │按键触发
  │ 消抖检查  │     │
  └─────┬────┘     │
   是  │  否       │
      ▼            │
  ┌──────────┐     │
  │ 状态切换  │     │
  └─────┬────┘     │
        ▼          │
  ┌──────────┐     │
  │LED显示更新│     │
  └─────┬────┘     │
        │──────────┘
        ▼
  ┌──────────┐
  │  返回等待  │
  └──────────┘
```

3. 中断服务流程图：
```
  ┌──────────┐
  │进入中断回调│
  └─────┬────┘
        ▼
  ┌──────────┐
  │消抖检查   │
  └─────┬────┘
   是  │  否
      ▼
  ┌──────────┐
  │状态机切换 │
  └─────┬────┘
        ▼
  ┌──────────┐
  │LED状态更新│
  └─────┬────┘
        ▼
  ┌──────────┐
  │  退出中断  │
  └──────────┘
```
                """,
                learning_resources=[
                    LearningResource(
                        title="嵌入式流程图绘制指南",
                        url="https://doc嵌入式.org/flowchart",
                        resource_type="tutorial",
                        description="流程图符号和使用规范"
                    )
                ]
            )
        },

        # 完整性问题 - 缺少章节
        "section_missing": {
            "patterns": [r'缺少.*章节', r'内容.*不完整'],
            "feedback": SmartFeedback(
                category=FeedbackCategory.COMPLETENESS,
                priority=4,
                problem_description="报告缺少必需章节",
                specific_suggestion="""
完整的实验报告应包含以下章节：

一、团队信息与分工（5分）
   ✓ 成员基本信息表
   ✓ 个人分工说明
   ✓ 团队协作过程记录

二、实验目的与原理（10分）
   ✓ 实验目的（3条）
   ✓ 实验原理阐述
   ✓ 汽车电子应用场景说明

三、硬件设计与连接（15分）
   ✓ 硬件连接图
   ✓ 引脚配置说明表
   ✓ ISP烧录电路说明

四、软件设计与实现（30分）
   ✓ 代码流程图
   ✓ 关键代码片段及注释
   ✓ 中断服务程序说明
   ✓ 团队成员代码模块说明

五、实验结果分析（20分）
   ✓ 实验现象记录
   ✓ 结果照片或截图
   ✓ 与预期结果对比分析

六、问题与讨论（15分）
   ✓ 调试过程中遇到的问题
   ✓ 团队协作解决过程
   ✓ 个人心得体会（独立撰写）

七、思考题回答（5分）
   ✓ 完整回答所有思考题

字数要求：不少于2000字
                """,
                learning_resources=[
                    LearningResource(
                        title="实验报告撰写指南",
                        url="https://doc嵌入式.org/report-guide",
                        resource_type="doc",
                        description="实验报告结构和要求"
                    )
                ]
            )
        },
    }

    @classmethod
    def analyze_report(
        cls,
        grading_result,
        technical_check_result,
        code_analysis_result=None
    ) -> List[SmartFeedback]:
        """
        分析报告并生成智能反馈

        Args:
            grading_result: 评分结果
            technical_check_result: 技术检查结果
            code_analysis_result: 代码分析结果（可选）

        Returns:
            智能反馈列表
        """
        feedback_list = []

        # 1. 基于评分类别生成反馈
        for category_id, category_score in grading_result.category_scores.items():
            if category_score.percentage < 60:
                category_name = category_score.name
                feedback = cls._generate_category_feedback(category_id, category_name)
                if feedback:
                    feedback_list.append(feedback)

        # 2. 基于技术检查结果生成反馈
        if technical_check_result:
            _, _, strengths, weaknesses = technical_check_result
            for weakness in weaknesses[:3]:  # 最多3个主要问题
                feedback = cls._generate_technical_feedback(weakness)
                if feedback:
                    feedback_list.append(feedback)

        # 3. 基于代码分析结果生成反馈
        if code_analysis_result:
            high_priority_issues = [
                issue for issue in code_analysis_result.issues
                if issue.severity in [Severity.CRITICAL, Severity.HIGH]
            ]
            for issue in high_priority_issues[:2]:
                feedback = cls._generate_code_feedback(issue)
                if feedback:
                    feedback_list.append(feedback)

        # 4. 按优先级排序
        feedback_list.sort(key=lambda x: x.priority, reverse=True)

        return feedback_list

    @classmethod
    def _generate_category_feedback(cls, category_id: str, category_name: str) -> Optional[SmartFeedback]:
        """基于评分类别生成反馈"""
        # 映射类别到知识库
        category_mapping = {
            "team_collaboration": None,  # 团队协作不自动生成
            "attitude": None,            # 态度不自动生成
            "principle_understanding": "section_missing",
            "completion": "section_missing",
            "code_quality": "code_comment_lacking",
            "report_quality": "section_missing"
        }

        knowledge_key = category_mapping.get(category_id)
        if knowledge_key and knowledge_key in cls.KNOWLEDGE_BASE:
            return cls.KNOWLEDGE_BASE[knowledge_key]["feedback"]

        return None

    @classmethod
    def _generate_technical_feedback(cls, weakness: str) -> Optional[SmartFeedback]:
        """基于技术检查弱点生成反馈"""
        # 根据弱点内容匹配知识库
        for key, value in cls.KNOWLEDGE_BASE.items():
            patterns = value["patterns"]
            for pattern in patterns:
                if re.search(pattern, weakness):
                    return value["feedback"]

        return None

    @classmethod
    def _generate_code_feedback(cls, issue) -> Optional[SmartFeedback]:
        """基于代码问题生成反馈"""
        # 根据问题类别生成反馈
        if "GPIO" in issue.message or "引脚" in issue.message:
            return cls.KNOWLEDGE_BASE.get("gpio_missing", {}).get("feedback")

        elif "中断" in issue.message or "EXTI" in issue.message:
            return cls.KNOWLEDGE_BASE.get("interrupt_missing", {}).get("feedback")

        elif "DWT" in issue.message or "消抖" in issue.message:
            return cls.KNOWLEDGE_BASE.get("dwt_missing", {}).get("feedback")

        elif "状态" in issue.message or "档位" in issue.message:
            return cls.KNOWLEDGE_BASE.get("state_machine_missing", {}).get("feedback")

        return None

    @classmethod
    def generate_learning_path(cls, student_id: str, feedback_list: List[SmartFeedback]) -> List[str]:
        """
        生成个性化学习路径

        Args:
            student_id: 学号
            feedback_list: 反馈列表

        Returns:
            学习资源列表
        """
        learning_resources = []

        for feedback in feedback_list:
            learning_resources.extend(feedback.learning_resources)

        # 去重
        seen = set()
        unique_resources = []
        for resource in learning_resources:
            if resource.url not in seen:
                seen.add(resource.url)
                unique_resources.append(resource)

        return unique_resources


def generate_smart_feedback_report(
    student_id: str,
    name: str,
    grading_result,
    technical_check_result,
    code_analysis_result=None
) -> str:
    """
    生成智能反馈报告

    Args:
        student_id: 学号
        name: 姓名
        grading_result: 评分结果
        technical_check_result: 技术检查结果
        code_analysis_result: 代码分析结果

    Returns:
        Markdown格式的反馈报告
    """
    # 生成智能反馈
    feedback_list = SmartFeedbackEngine.analyze_report(
        grading_result, technical_check_result, code_analysis_result
    )

    # 生成学习路径
    learning_path = SmartFeedbackEngine.generate_learning_path(student_id, feedback_list)

    # 构建报告
    lines = [
        f"# 智能学习反馈报告",
        "",
        f"**学号**: {student_id}",
        f"**姓名**: {name}",
        f"**总分**: {grading_result.total_score}/{grading_result.total_possible} ({grading_result.percentage:.1f}%)",
        "",
        "---",
        ""
    ]

    if feedback_list:
        lines.append("## 📝 个性化改进建议")
        lines.append("")

        priority_emoji = {5: "🔴", 4: "🟠", 3: "🟡", 2: "🟢", 1: "🔵"}

        for i, feedback in enumerate(feedback_list, 1):
            emoji = priority_emoji.get(feedback.priority, "📌")
            lines.append(f"### {emoji} 建议 {i}: {feedback.problem_description}")
            lines.append("")
            lines.append(feedback.specific_suggestion.strip())
            lines.append("")

            if feedback.learning_resources:
                lines.append("**学习资源**:")
                for resource in feedback.learning_resources:
                    lines.append(f"- [{resource.title}]({resource.url}) - {resource.description}")
                lines.append("")
    else:
        lines.append("## 🎉 太棒了！")
        lines.append("")
        lines.append("您的报告质量很好，没有需要特别改进的地方！")
        lines.append("")

    # 学习路径
    if learning_path:
        lines.append("---")
        lines.append("")
        lines.append("## 📚 推荐学习资源")
        lines.append("")
        for resource in learning_path:
            icon = {
                "doc": "📄",
                "video": "🎥",
                "tutorial": "📖",
                "example": "💻"
            }.get(resource.resource_type, "🔗")

            lines.append(f"{icon} [{resource.title}]({resource.url})")
            lines.append(f"   _{resource.description}_")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*本报告由智能反馈系统生成，建议结合教师意见进行改进。*")

    return '\n'.join(lines)


# 导入必要的类型
try:
    from tools.plagiarism.code_analysis import Severity
except ImportError:
    try:
        from ..code_analysis.code_analyzer import Severity
    except ImportError:
        from tools.plagiarism.code_analysis.code_analyzer import Severity
