#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技术要点检查模块
Technical Points Verification Module

详细的实验技术要点验证，用于准确评估报告的技术内容
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum


class ExperimentType(Enum):
    """实验类型"""
    CAR_GEAR = "档位实验"
    TURN_SIGNAL = "转向灯实验"
    GENERAL = "通用实验"


@dataclass
class TechnicalCheck:
    """技术检查项"""
    name: str                    # 检查项名称
    description: str             # 描述
    points: float                # 分值
    patterns: List[str]          # 匹配模式
    category: str                # 类别（硬件/软件/结果）
    required: bool = True        # 是否必需


@dataclass
class CheckResult:
    """检查结果"""
    check: TechnicalCheck
    passed: bool
    matched_text: str = ""
    feedback: str = ""
    partial_credit: float = 0.0


class TechnicalChecker:
    """技术要点检查器"""

    # 档位实验技术要点
    CAR_GEAR_CHECKS = [
        # 硬件连接类 (15分)
        TechnicalCheck(
            name="LED0引脚配置",
            description="正确说明LED0连接到PF9（低电平有效）",
            points=4,
            patterns=[r'PF9.*LED', r'LED0.*PF9', r'PF9.*低电平'],
            category="硬件"
        ),
        TechnicalCheck(
            name="LED1引脚配置",
            description="正确说明LED1连接到PF10（低电平有效）",
            points=4,
            patterns=[r'PF10.*LED', r'LED1.*PF10', r'PF10.*低电平'],
            category="硬件"
        ),
        TechnicalCheck(
            name="按键中断配置",
            description="正确说明按键连接到PE4，外部中断下降沿触发",
            points=7,
            patterns=[
                r'PE4.*(下降沿|中断|EXTI)',
                r'EXTI.*PE4',
                r'按键.*PE4',
                r'外部中断.*下降沿'
            ],
            category="硬件"
        ),

        # 软件设计类 (25分)
        TechnicalCheck(
            name="GPIO初始化",
            description="正确配置GPIO模式（输出/中断/上拉）",
            points=5,
            patterns=[
                r'GPIO.*MODE.*OUTPUT',
                r'GPIO.*MODE.*IT.*RISING',
                r'GPIO.*PULL.*UP',
                r'HAL_GPIO_Init'
            ],
            category="软件"
        ),
        TechnicalCheck(
            name="DWT消抖实现",
            description="使用DWT周期计数器实现消抖（约50ms）",
            points=8,
            patterns=[
                r'DWT.*CYCCNT',
                r'DWT.*消抖',
                r'CoreDebug.*DEMCR',
                r'50000000|84\s*000\s*000',
                r'50.*ms'
            ],
            category="软件"
        ),
        TechnicalCheck(
            name="中断服务函数",
            description="正确实现HAL_GPIO_EXTI_Callback回调函数",
            points=5,
            patterns=[
                r'HAL_GPIO_EXTI_Callback',
                r'EXTI.*IRQHandler',
                r'void.*EXTI.*\('
            ],
            category="软件"
        ),
        TechnicalCheck(
            name="状态机逻辑",
            description="正确实现P→R→N→D→P状态循环切换",
            points=7,
            patterns=[
                r'P.*R.*N.*D',
                r'gear.*state',
                r'switch.*gear',
                r'enum.*gear',
                r'档位.*状态'
            ],
            category="软件"
        ),

        # 实验结果类 (20分)
        TechnicalCheck(
            name="档位显示功能",
            description="正确实现各档位LED显示（P/R/N/D）",
            points=8,
            patterns=[
                r'P.*档.*LED',
                r'R.*档.*LED',
                r'N.*档.*LED',
                r'D.*档.*LED',
                r'档位.*(显示|切换|变化)'
            ],
            category="结果"
        ),
        TechnicalCheck(
            name="消抖效果验证",
            description="说明消抖效果，按键响应稳定无误触发",
            points=6,
            patterns=[
                r'消抖.*(效果|稳定|正常)',
                r'按键.*(稳定|正确|无误)',
                r'无(误触发|抖动)'
            ],
            category="结果"
        ),
        TechnicalCheck(
            name="功能完整性",
            description="所有档位切换正常，功能完整",
            points=6,
            patterns=[
                r'(功能|切换).*(正常|完整|成功)',
                r'实验.*达到.*预期',
                r'演示.*成功'
            ],
            category="结果"
        ),
    ]

    # 转向灯实验技术要点
    TURN_SIGNAL_CHECKS = [
        TechnicalCheck(
            name="GPIO输出配置",
            description="正确配置LED为GPIO输出模式",
            points=10,
            patterns=[r'GPIO.*MODE.*OUTPUT', r'LED.*输出'],
            category="硬件"
        ),
        TechnicalCheck(
            name="延时控制",
            description="实现延时或定时器控制闪烁频率",
            points=15,
            patterns=[r'HAL_Delay', r'定时器', r'TIM', r'延时'],
            category="软件"
        ),
        TechnicalCheck(
            name="转向模式切换",
            description="实现左转/右转/紧急/关闭模式",
            points=20,
            patterns=[r'左转|右转|紧急|关闭', r'mode|模式'],
            category="软件"
        ),
        TechnicalCheck(
            name="闪烁功能",
            description="LED按要求频率闪烁",
            points=15,
            patterns=[r'闪烁|频率|周期', r'LED.*(亮|灭|翻转)'],
            category="结果"
        ),
    ]

    @staticmethod
    def get_checks(experiment_type: ExperimentType) -> List[TechnicalCheck]:
        """获取实验类型对应的技术检查项"""
        if experiment_type == ExperimentType.CAR_GEAR:
            return TechnicalChecker.CAR_GEAR_CHECKS
        elif experiment_type == ExperimentType.TURN_SIGNAL:
            return TechnicalChecker.TURN_SIGNAL_CHECKS
        else:
            return []

    @classmethod
    def check_all(
        cls,
        text: str,
        experiment_type: ExperimentType = ExperimentType.CAR_GEAR
    ) -> Tuple[float, List[CheckResult], List[str], List[str]]:
        """
        检查所有技术要点

        Args:
            text: 报告文本
            experiment_type: 实验类型

        Returns:
            (总分, 检查结果列表, 亮点列表, 问题列表)
        """
        checks = cls.get_checks(experiment_type)
        if not checks:
            return 0.0, [], [], []

        results = []
        total_earned = 0.0
        total_possible = sum(check.points for check in checks)

        strengths = []
        weaknesses = []

        for check in checks:
            result = cls._check_single(text, check)
            results.append(result)
            total_earned += result.partial_credit

            # 收集反馈
            if result.passed:
                strengths.append(f"✓ {check.description}")
            elif result.partial_credit > 0:
                weaknesses.append(f"△ {check.description} (部分得分)")
            else:
                weaknesses.append(f"✗ {check.description}")

        return total_earned, results, strengths, weaknesses

    @classmethod
    def _check_single(cls, text: str, check: TechnicalCheck) -> CheckResult:
        """检查单个技术要点"""
        matched_patterns = []
        matched_text = ""

        # 检查每个模式
        for pattern in check.patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                matched_patterns.append(pattern)
                # 获取匹配的文本
                matched_text = match.group(0) if match.groups() else match.group(0)
                break  # 找到一个匹配即可

        # 计算得分
        passed = len(matched_patterns) > 0
        match_ratio = len(matched_patterns) / len(check.patterns)

        if match_ratio >= 0.5:
            partial_credit = check.points
        elif match_ratio > 0:
            partial_credit = check.points * 0.5
        else:
            partial_credit = 0

        # 生成反馈
        if passed:
            feedback = f"正确：{check.description}"
        else:
            feedback = f"缺失：{check.description}"

        return CheckResult(
            check=check,
            passed=passed,
            matched_text=matched_text,
            feedback=feedback,
            partial_credit=partial_credit
        )


class ContentStructureChecker:
    """内容结构检查器"""

    @staticmethod
    def check_report_structure(text: str) -> Tuple[float, List[str]]:
        """
        检查报告结构完整性

        Args:
            text: 报告文本

        Returns:
            (结构分, 问题列表)
        """
        # 必需章节
        required_sections = {
            r'实验目的|目标': ('实验目的', 10),
            r'实验原理|设计思路': ('实验原理', 15),
            r'硬件.*连接|接线|电路': ('硬件连接', 15),
            r'软件.*设计|程序设计|代码': ('软件设计', 20),
            r'实验结果|测试|现象': ('实验结果', 20),
            r'问题.*讨论|心得|体会': ('问题讨论', 10),
            r'思考题|问答': ('思考题', 10),
        }

        score = 0.0
        max_score = sum(points for _, points in required_sections.values())
        issues = []

        for pattern, (name, points) in required_sections.items():
            if re.search(pattern, text, re.IGNORECASE):
                score += points
            else:
                issues.append(f"缺少章节: {name}")

        percentage = (score / max_score * 100) if max_score > 0 else 0

        return percentage, issues


class CodeSnippetChecker:
    """代码片段检查器"""

    @staticmethod
    def extract_and_check_code(text: str) -> Tuple[float, List[str]]:
        """
        提取并检查代码片段

        Args:
            text: 报告文本

        Returns:
            (代码质量分, 问题列表)
        """
        # 提取代码块
        code_blocks = re.findall(r'```[^\n]*\n(.*?)```', text, re.DOTALL)

        if not code_blocks:
            # 尝试其他格式
            code_blocks = re.findall(r'~~[^\n]*\n(.*?)~~~', text, re.DOTALL)

        if not code_blocks:
            return 0.0, ["未检测到代码块，请使用```或~~~标记代码"]

        all_code = '\n'.join(code_blocks)
        score = 0.0
        issues = []

        # 检查注释
        comment_ratio = 0.0
        lines = all_code.split('\n')
        code_lines = [l for l in lines if l.strip() and not l.strip().startswith('//')]
        comment_lines = [l for l in lines if '//' in l or l.strip().startswith('*')]

        if code_lines:
            comment_ratio = len(comment_lines) / len(lines)

        if comment_ratio >= 0.2:
            score += 25
        elif comment_ratio >= 0.1:
            score += 15
            issues.append("代码注释偏少，建议增加关键代码说明")
        else:
            issues.append("缺少代码注释，请添加说明")

        # 检查函数完整性
        if re.search(r'void\s+\w+\([^)]*\)\s*{', all_code):
            score += 25
        else:
            issues.append("未检测到完整的函数定义")

        # 检查HAL函数使用
        hal_count = len(re.findall(r'HAL_[A-Z_]+', all_code))
        if hal_count >= 3:
            score += 25
        elif hal_count >= 1:
            score += 15
        else:
            issues.append("HAL库函数使用较少")

        # 检查GPIO配置
        if re.search(r'GPIO.*[MODE|PULL|SPEED]', all_code):
            score += 25
        else:
            issues.append("缺少GPIO配置代码")

        return min(score, 100), issues


class ThinkingQuestionsChecker:
    """思考题检查器"""

    # 档位实验思考题及答案要点
    CAR_GEAR_QUESTIONS = [
        {
            "id": "Q1",
            "question": "为什么按键配置为下降沿触发？",
            "keywords": ["高电平", "变低", "按下", "下降沿", "可靠"],
            "points": 5
        },
        {
            "id": "Q2",
            "question": "DWT消抖与软件延时消抖的区别",
            "keywords": ["硬件", "不阻塞", "CPU", "精度", "实时"],
            "points": 5
        },
        {
            "id": "Q3",
            "question": "如何实现D档直接切换到R档？",
            "keywords": ["条件", "判断", "N档", "中间", "先切"],
            "points": 5
        },
        {
            "id": "Q4",
            "question": "中断服务程序为什么要尽可能短？",
            "keywords": ["优先级", "阻塞", "实时", "响应", "其他中断"],
            "points": 5
        },
        {
            "id": "Q5",
            "question": "LED是高电平点亮还是低电平点亮？",
            "keywords": ["低电平", "RESET", "SET", "点亮", "熄灭"],
            "points": 5
        },
        {
            "id": "Q6",
            "question": "实际汽车中档位传感器如何工作？",
            "keywords": ["数字量", "CAN", "LIN", "总线", "开关", "传感器"],
            "points": 5
        },
        {
            "id": "Q7",
            "question": "如何扩展S档和L档？",
            "keywords": ["enum", "状态", "增加", "case", "LED"],
            "points": 5
        },
    ]

    @classmethod
    def check_thinking_questions(
        cls,
        text: str,
        experiment_type: ExperimentType = ExperimentType.CAR_GEAR
    ) -> Tuple[float, List[Dict]]:
        """
        检查思考题回答情况

        Args:
            text: 报告文本
            experiment_type: 实验类型

        Returns:
            (总分, 各题详情列表)
        """
        if experiment_type != ExperimentType.CAR_GEAR:
            return 0.0, []

        questions = cls.CAR_GEAR_QUESTIONS
        results = []
        total_score = 0.0

        for q in questions:
            # 检查关键词匹配
            matched_count = sum(1 for kw in q['keywords'] if kw in text)

            # 计算得分
            if matched_count >= 3:
                earned = q['points']
                status = "完整"
            elif matched_count >= 1:
                earned = q['points'] * 0.5
                status = "部分"
            else:
                earned = 0
                status = "未回答"

            total_score += earned

            results.append({
                "question": q['question'],
                "points_earned": earned,
                "points_possible": q['points'],
                "status": status,
                "matched_keywords": matched_count
            })

        return total_score, results
