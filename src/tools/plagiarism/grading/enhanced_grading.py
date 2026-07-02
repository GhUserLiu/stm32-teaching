#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强评分引擎
Enhanced Grading Engine

基于问题诊断结果进行更精准的评分
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

try:
    from ..feedback.enhanced_feedback import Issue, EnhancedFeedbackGenerator
except ImportError:
    try:
        from .enhanced_feedback import Issue, EnhancedFeedbackGenerator
    except ImportError:
        from enhanced_feedback import Issue, EnhancedFeedbackGenerator


@dataclass
class GradingAdjustment:
    """评分调整"""
    issue_id: str
    issue_title: str
    category: str
    original_points: float      # 原始得分
    adjusted_points: float       # 调整后得分
    deduction: float             # 扣分
    reason: str                  # 扣分原因


@dataclass
class EnhancedGradingResult:
    """增强评分结果"""
    student_id: str
    name: str
    original_score: float        # 原始评分（基于关键词）
    adjusted_score: float         # 调整后评分（基于问题诊断）
    adjustments: List[GradingAdjustment] = field(default_factory=list)
    category_scores: Dict[str, float] = field(default_factory=dict)
    grade: str = ""
    confidence: float = 0.85     # 评分置信度

    @property
    def total_deduction(self) -> float:
        """总扣分"""
        return sum(adj.deduction for adj in self.adjustments)

    @property
    def deduction_count(self) -> int:
        """扣分项数量"""
        return len([adj for adj in self.adjustments if adj.deduction > 0])


class EnhancedGradingEngine:
    """增强评分引擎"""

    def __init__(self, rubric_path: Optional[Path] = None, resources_path: Optional[Path] = None):
        """
        初始化增强评分引擎

        Args:
            rubric_path: rubric配置文件路径
            resources_path: 反馈资源配置文件路径
        """
        if rubric_path is None:
            rubric_path = Path(__file__).parent.parent.parent.parent.parent / 'data/rubrics/rubric.json'

        with open(rubric_path, 'r', encoding='utf-8') as f:
            self.rubric = json.load(f)

        # 初始化反馈生成器（用于问题诊断）
        self.feedback_generator = EnhancedFeedbackGenerator(resources_path)

        # 建立问题ID到评分类别的映射
        self._build_issue_category_mapping()

    def _build_issue_category_mapping(self):
        """建立问题到评分类别的映射"""
        self.issue_to_category = {}

        # 技术问题映射
        technical_mapping = {
            'gpio_mode_missing': 'completion',
            'led_polarity_error': 'completion',
            'pe4_edge_missing': 'completion',
            'dwt_principle_missing': 'code_quality',
            'state_machine_logic_error': 'code_quality',
            'interrupt_priority_missing': 'code_quality',
            'callback_function_missing': 'code_quality',
        }

        # 内容缺失映射
        content_mapping = {
            'missing_hardware_diagram': 'completion',
            'pin_config_incomplete': 'completion',
            'missing_flowchart': 'code_quality',
            'code_comment_insufficient': 'code_quality',
            'missing_test_results': 'report_quality',
            'missing_test_photo': 'report_quality',
            'missing_result_analysis': 'report_quality',
            'missing_debug_log': 'report_quality',
            'generic_personal_reflection': 'report_quality',
            'thinking_questions_incomplete': 'report_quality',
        }

        # 质量问题映射
        quality_mapping = {
            'code_formatting': 'report_quality',
            'report_structure': 'report_quality',
        }

        self.issue_to_category.update(technical_mapping)
        self.issue_to_category.update(content_mapping)
        self.issue_to_category.update(quality_mapping)

    def grade(
        self,
        student_id: str,
        name: str,
        text: str,
        original_score: float,
        original_category_scores: Optional[Dict[str, float]] = None
    ) -> EnhancedGradingResult:
        """
        进行增强评分

        Args:
            student_id: 学号
            name: 姓名
            text: 报告文本
            original_score: 原始评分（基于关键词匹配）
            original_category_scores: 原始分类得分

        Returns:
            增强评分结果
        """
        # 使用反馈生成器进行问题诊断
        from types import SimpleNamespace
        grading_result = SimpleNamespace(
            total_score=original_score,
            total_possible=100,
            percentage=original_score,
            grade=''
        )

        enhanced_feedback = self.feedback_generator.generate_enhanced_feedback(
            student_id, name, text, grading_result
        )

        # 计算调整
        adjustments = self._calculate_adjustments(
            enhanced_feedback.issues,
            original_category_scores or {}
        )

        # 计算调整后分数
        total_deduction = sum(adj.deduction for adj in adjustments)
        adjusted_score = max(0, original_score - total_deduction)

        # 计算各分类得分
        category_scores = self._calculate_category_scores(
            original_category_scores or {},
            adjustments
        )

        # 计算等级
        grade = self._calculate_grade(adjusted_score)

        # 计算置信度
        confidence = self._calculate_confidence(enhanced_feedback.issues)

        return EnhancedGradingResult(
            student_id=student_id,
            name=name,
            original_score=original_score,
            adjusted_score=adjusted_score,
            adjustments=adjustments,
            category_scores=category_scores,
            grade=grade,
            confidence=confidence
        )

    def _calculate_adjustments(
        self,
        issues: List[Issue],
        original_category_scores: Dict[str, float]
    ) -> List[GradingAdjustment]:
        """计算评分调整"""
        adjustments = []

        for issue in issues:
            # 获取该问题影响的评分类别
            category = self.issue_to_category.get(issue.id, 'report_quality')

            # 获取该类别的满分
            category_info = self._get_category_info(category)
            if not category_info:
                continue

            max_points = category_info['points']

            # 计算扣分
            deduction = self._calculate_deduction(issue, max_points)

            if deduction > 0:
                adjustments.append(GradingAdjustment(
                    issue_id=issue.id,
                    issue_title=issue.title,
                    category=category,
                    original_points=max_points,
                    adjusted_points=max_points - deduction,
                    deduction=deduction,
                    reason=issue.description
                ))

        return adjustments

    def _calculate_deduction(self, issue: Issue, max_points: float) -> float:
        """
        计算扣分

        扣分规则：
        - high严重性：扣该类别分的30-50%
        - medium严重性：扣该类别分的10-20%
        - low严重性：扣该类别分的5%
        - 考虑issue.points_affected（如果有）
        """
        if issue.points_affected > 0:
            # 如果配置了具体影响分数，使用配置值
            return min(issue.points_affected, max_points * 0.5)  # 最多扣50%

        # 根据严重程度计算
        severity_ratios = {
            'high': 0.4,      # 40%
            'medium': 0.15,   # 15%
            'low': 0.05       # 5%
        }

        ratio = severity_ratios.get(issue.severity, 0.1)
        return max_points * ratio

    def _get_category_info(self, category_id: str) -> Optional[Dict]:
        """获取评分类别信息"""
        for category in self.rubric.get('categories', []):
            if category['id'] == category_id:
                return category
        return None

    def _calculate_category_scores(
        self,
        original_scores: Dict[str, float],
        adjustments: List[GradingAdjustment]
    ) -> Dict[str, float]:
        """计算各分类调整后得分"""
        adjusted_scores = original_scores.copy()

        # 按类别汇总扣分
        category_deductions = {}
        for adj in adjustments:
            if adj.category not in category_deductions:
                category_deductions[adj.category] = 0
            category_deductions[adj.category] += adj.deduction

        # 应用扣分
        for category, deduction in category_deductions.items():
            if category in adjusted_scores:
                category_max = self._get_category_info(category)['points']
                adjusted_scores[category] = max(0, adjusted_scores[category] - deduction)

        return adjusted_scores

    def _calculate_grade(self, score: float) -> str:
        """根据分数计算等级"""
        grading_scale = self.rubric.get('grading_scale', {})

        for grade, range_data in sorted(grading_scale.items(), key=lambda x: x[1]['min'], reverse=True):
            if range_data['min'] <= score <= range_data['max']:
                return grade
        return 'F'

    def _calculate_confidence(self, issues: List[Issue]) -> float:
        """计算评分置信度"""
        confidence = 0.90  # 基础置信度

        # 高优先级问题越多，置信度越高（说明诊断准确）
        high_count = len([i for i in issues if i.severity == 'high'])
        confidence += high_count * 0.01

        # 问题越少，调整越保守，置信度越高
        if len(issues) < 5:
            confidence += 0.05

        return min(confidence, 0.98)


def batch_enhanced_grade(
    submissions: Dict[str, Dict],
    original_evaluations: List[Dict],
    rubric_path: Optional[Path] = None,
    resources_path: Optional[Path] = None
) -> List[EnhancedGradingResult]:
    """
    批量增强评分

    Args:
        submissions: 提交内容 {学号: {name, text}}
        original_evaluations: 原始评分结果列表
        rubric_path: rubric路径
        resources_path: 资源路径

    Returns:
        增强评分结果列表
    """
    engine = EnhancedGradingEngine(rubric_path, resources_path)
    results = []

    for eval_data in original_evaluations:
        student_id = eval_data['student_id']
        name = eval_data.get('name', '')

        # 获取报告文本
        submission = submissions.get(student_id)
        if not submission:
            continue

        text = submission.get('text', '')

        # 获取原始评分
        original_score = eval_data.get('total_score', 0)
        original_scores = eval_data.get('scores', {})

        # 进行增强评分
        result = engine.grade(student_id, name, text, original_score, original_scores)
        results.append(result)

    return results


def format_enhanced_grading_result(result: EnhancedGradingResult) -> str:
    """格式化增强评分结果"""
    lines = [
        f"## {result.name} ({result.student_id})",
        "",
        f"**原始评分**: {result.original_score} 分",
        f"**调整后评分**: {result.adjusted_score} 分",
        f"**扣分**: {result.total_deduction:.1f} 分",
        f"**等级**: {result.grade}",
        f"**置信度**: {result.confidence:.1%}",
        ""
    ]

    if result.adjustments:
        lines.extend([
            "### 评分调整详情",
            "",
            "| 问题 | 类别 | 扣分 | 原因 |",
            "|------|------|------|------|"
        ])

        for adj in result.adjustments:
            category_name = adj.category.replace('_', ' ').title()
            lines.append(f"| {adj.issue_title} | {category_name} | -{adj.deduction:.1f} | {adj.reason[:30]}... |")

        lines.append("")

    return '\n'.join(lines)
