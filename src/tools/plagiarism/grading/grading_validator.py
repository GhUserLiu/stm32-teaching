#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
评分一致性校验模块
Grading Consistency Validator

检查评分标准的一致性、异常分数预警、人工复核建议
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path
from statistics import mean, stdev
import math


class ValidationSeverity(Enum):
    """验证严重程度"""
    INFO = "info"           # 信息提示
    WARNING = "warning"     # 警告
    ERROR = "error"         # 错误
    CRITICAL = "critical"   # 严重错误


@dataclass
class ValidationIssue:
    """验证问题"""
    severity: ValidationSeverity
    category: str
    message: str
    student_id: str = ""
    details: Dict = field(default_factory=dict)


@dataclass
class ValidationReport:
    """验证报告"""
    total_students: int
    issue_count: int
    issues: List[ValidationIssue]
    statistics: Dict
    recommendations: List[str]
    validation_passed: bool


class GradingValidator:
    """评分验证器"""

    # 评分规则配置
    GRADING_RULES = {
        "max_score": 100,
        "min_score": 0,
        "max_single_category_score": 40,  # 单个类别最高分
        "min_category_count": 4,           # 最少类别数
        "expected_score_distribution": {   # 期望分数分布
            "A": (0.15, 0.25),   # A等占15-25%
            "B": (0.30, 0.45),   # B等占30-45%
            "C": (0.25, 0.35),   # C等占25-35%
            "D": (0.10, 0.20),   # D等占10-20%
            "F": (0.05, 0.15)    # F等占5-15%
        }
    }

    @staticmethod
    def validate_rubric(rubric: Dict) -> List[ValidationIssue]:
        """
        验证评分标准本身的一致性

        Args:
            rubric: 评分标准字典

        Returns:
            问题列表
        """
        issues = []

        # 1. 检查总分
        total_points = rubric.get('total_points', 0)
        if total_points != 100:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="评分标准",
                message=f"总分不是100分: {total_points}",
                details={"total_points": total_points}
            ))

        # 2. 检查类别完整性
        categories = rubric.get('categories', [])
        if len(categories) < 4:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="评分标准",
                message=f"评分类别过少: {len(categories)}个，建议至少4个",
                details={"category_count": len(categories)}
            ))

        # 3. 检查类别分值（仅基础分；points_outside_base 的加分项不计入总分校验）
        base_categories = [c for c in categories if not c.get('points_outside_base')]
        base_sum = sum(c.get('points', 0) for c in base_categories)
        if abs(base_sum - total_points) > 1:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="评分标准",
                message=f"基础类别分值总和({base_sum})不等于总分({total_points})",
                details={"base_sum": base_sum, "total_points": total_points,
                         "outside_base_count": len(categories) - len(base_categories)}
            ))

        # 4. 检查评分类别分值合理性
        for category in categories:
            points = category.get('points', 0)
            if points > 40:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="评分标准",
                    message=f"类别 '{category.get('name')}' 分值过高: {points}分",
                    details={"category": category.get('name'), "points": points}
                ))
            elif points < 5:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    category="评分标准",
                    message=f"类别 '{category.get('name')}' 分值较低: {points}分",
                    details={"category": category.get('name'), "points": points}
                ))

        # 5. 检查评分标准关键词
        for category in categories:
            criteria = category.get('criteria', [])
            for criterion in criteria:
                keywords = criterion.get('keywords', [])
                if not keywords:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="评分标准",
                        message=f"评分项 '{criterion.get('description')}' 没有关键词",
                        details={"criterion": criterion.get('description')}
                    ))

        # 6. 检查评分等级
        grading_scale = rubric.get('grading_scale', {})
        required_grades = ['A', 'B', 'C', 'D', 'F']
        for grade in required_grades:
            if grade not in grading_scale:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="评分标准",
                    message=f"缺少评分等级: {grade}",
                    details={"missing_grade": grade}
                ))

        return issues

    @staticmethod
    def validate_student_score(result: Dict) -> List[ValidationIssue]:
        """
        验证单个学生评分的合理性

        Args:
            result: 学生评分结果

        Returns:
            问题列表
        """
        issues = []
        student_id = result.get('student_id', '')
        name = result.get('name', '')

        # 1. 检查总分范围
        total_score = result.get('total_score', 0)
        if total_score > 100:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                category="分数异常",
                message=f"{name}({student_id}) 总分超过100分: {total_score}",
                student_id=student_id,
                details={"score": total_score}
            ))
        elif total_score < 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                category="分数异常",
                message=f"{name}({student_id}) 总分为负数: {total_score}",
                student_id=student_id,
                details={"score": total_score}
            ))

        # 2. 检查等级与分数的一致性
        grade = result.get('grade', '')
        percentage = result.get('percentage', 0)

        grade_ranges = {
            'A': (90, 100),
            'B': (80, 89.99),
            'C': (70, 79.99),
            'D': (60, 69.99),
            'F': (0, 59.99)
        }

        if grade in grade_ranges:
            min_score, max_score = grade_ranges[grade]
            if not (min_score <= percentage <= max_score):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="等级不一致",
                    message=f"{name}({student_id}) 等级{grade}与分数{percentage:.1f}%不匹配",
                    student_id=student_id,
                    details={"grade": grade, "percentage": percentage}
                ))

        # 3. 检查评分类别得分
        category_scores = result.get('category_scores', {})
        for cat_id, cat_score in category_scores.items():
            if isinstance(cat_score, dict):
                earned = cat_score.get('points_earned', 0)
                possible = cat_score.get('points_possible', 0)

                if earned > possible:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category="类别分数异常",
                        message=f"{name}({student_id}) 类别 '{cat_score.get('name')}' 得分({earned})超过满分({possible})",
                        student_id=student_id,
                        details={"category": cat_id, "earned": earned, "possible": possible}
                    ))

                if earned < 0:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category="类别分数异常",
                        message=f"{name}({student_id}) 类别 '{cat_score.get('name')}' 得分为负数: {earned}",
                        student_id=student_id,
                        details={"category": cat_id, "earned": earned}
                    ))

        # 4. 检查未提交学生
        if total_score == 0 and grade == 'F':
            weaknesses = result.get('weaknesses', [])
            if not any('未提交' in w for w in weaknesses):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    category="提交状态",
                    message=f"{name}({student_id}) 得分为0但未标记为未提交",
                    student_id=student_id
                ))

        # 5. 检查抄袭风险
        plagiarism_risk = result.get('plagiarism_risk', 0)
        if plagiarism_risk > 0.7 and grade not in ['F', 'D']:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="抄袭风险",
                message=f"{name}({student_id}) 抄袭风险{plagiarism_risk*100:.0f}%但等级为{grade}",
                student_id=student_id,
                details={"plagiarism_risk": plagiarism_risk, "grade": grade}
            ))

        return issues

    @staticmethod
    def validate_class_distribution(results: List[Dict]) -> List[ValidationIssue]:
        """
        验证班级分数分布是否合理

        Args:
            results: 所有学生评分结果

        Returns:
            问题列表
        """
        issues = []

        if not results:
            return issues

        # 1. 统计各等级人数
        grade_counts = {}
        for result in results:
            grade = result.get('grade', 'F')
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

        total = len(results)
        expected = GradingValidator.GRADING_RULES["expected_score_distribution"]

        for grade, (min_ratio, max_ratio) in expected.items():
            count = grade_counts.get(grade, 0)
            actual_ratio = count / total if total > 0 else 0

            if actual_ratio < min_ratio:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    category="分数分布",
                    message=f"{grade}等比例偏低: {actual_ratio*100:.1f}% (期望{min_ratio*100:.1f}%-{max_ratio*100:.1f}%)",
                    details={
                        "grade": grade,
                        "actual": actual_ratio,
                        "expected_min": min_ratio,
                        "expected_max": max_ratio
                    }
                ))
            elif actual_ratio > max_ratio:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="分数分布",
                    message=f"{grade}等比例偏高: {actual_ratio*100:.1f}% (期望{min_ratio*100:.1f}%-{max_ratio*100:.1f}%)",
                    details={
                        "grade": grade,
                        "actual": actual_ratio,
                        "expected_min": min_ratio,
                        "expected_max": max_ratio
                    }
                ))

        # 2. 统计分析
        scores = [r.get('total_score', 0) for r in results if r.get('total_score', 0) > 0]

        if scores:
            avg_score = mean(scores)
            if len(scores) > 1:
                std_dev = stdev(scores)
            else:
                std_dev = 0

            # 检查平均分
            if avg_score < 60:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="分数统计",
                    message=f"班级平均分偏低: {avg_score:.1f}分",
                    details={"average": avg_score}
                ))
            elif avg_score > 85:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    category="分数统计",
                    message=f"班级平均分较高: {avg_score:.1f}分",
                    details={"average": avg_score}
                ))

            # 检查标准差
            if std_dev < 5:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="分数统计",
                    message=f"分数标准差过小: {std_dev:.1f}，可能存在评分趋同",
                    details={"std_dev": std_dev}
                ))
            elif std_dev > 25:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    category="分数统计",
                    message=f"分数标准差较大: {std_dev:.1f}，分数差异明显",
                    details={"std_dev": std_dev}
                ))

        # 3. 检查极端分数
        for result in results:
            score = result.get('total_score', 0)
            student_id = result.get('student_id', '')
            name = result.get('name', '')

            if score >= 98:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    category="复核建议",
                    message=f"{name}({student_id}) 分数接近满分 ({score}分)，建议复核",
                    student_id=student_id,
                    details={"score": score, "reason": "near_perfect"}
                ))

        return issues

    @classmethod
    def validate_all(
        cls,
        results: List[Dict],
        rubric: Dict
    ) -> ValidationReport:
        """
        执行完整验证

        Args:
            results: 所有学生评分结果
            rubric: 评分标准

        Returns:
            验证报告
        """
        all_issues = []
        recommendations = []

        # 1. 验证评分标准
        rubric_issues = cls.validate_rubric(rubric)
        all_issues.extend(rubric_issues)

        # 2. 验证每个学生评分
        for result in results:
            student_issues = cls.validate_student_score(result)
            all_issues.extend(student_issues)

        # 3. 验证班级分布
        distribution_issues = cls.validate_class_distribution(results)
        all_issues.extend(distribution_issues)

        # 4. 生成建议
        recommendations = cls._generate_recommendations(all_issues, results)

        # 5. 统计问题
        critical_count = sum(1 for i in all_issues if i.severity == ValidationSeverity.CRITICAL)
        error_count = sum(1 for i in all_issues if i.severity == ValidationSeverity.ERROR)

        validation_passed = critical_count == 0 and error_count == 0

        # 6. 统计信息
        statistics = cls._generate_statistics(results, all_issues)

        return ValidationReport(
            total_students=len(results),
            issue_count=len(all_issues),
            issues=all_issues,
            statistics=statistics,
            recommendations=recommendations,
            validation_passed=validation_passed
        )

    @staticmethod
    def _generate_recommendations(issues: List[ValidationIssue], results: List[Dict]) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 按类别统计问题
        category_counts = {}
        for issue in issues:
            category = issue.category
            if issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
                category_counts[category] = category_counts.get(category, 0) + 1

        # 生成建议
        if category_counts.get("分数异常", 0) > 0:
            recommendations.append("存在分数异常的学生，请检查评分计算逻辑")

        if category_counts.get("等级不一致", 0) > 0:
            recommendations.append("存在等级与分数不一致的情况，请检查等级计算逻辑")

        if category_counts.get("抄袭风险", 0) > 0:
            recommendations.append("存在高抄袭风险但得分较高的学生，建议人工复核")

        # 复核建议
        review_students = [
            i.student_id for i in issues
            if i.category == "复核建议" and i.student_id
        ]

        if review_students:
            recommendations.append(f"建议复核以下学生的评分: {', '.join(review_students[:5])}{'...' if len(review_students) > 5 else ''}")

        # 评分标准建议
        if category_counts.get("评分标准", 0) > 0:
            recommendations.append("评分标准存在配置问题，请检查rubric.json文件")

        return recommendations

    @staticmethod
    def _generate_statistics(results: List[Dict], issues: List[ValidationIssue]) -> Dict:
        """生成统计信息"""
        scores = [r.get('total_score', 0) for r in results]

        grade_counts = {}
        for result in results:
            grade = result.get('grade', 'F')
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

        return {
            "total_students": len(results),
            "average_score": mean(scores) if scores else 0,
            "score_range": (min(scores) if scores else 0, max(scores) if scores else 0),
            "grade_distribution": grade_counts,
            "total_issues": len(issues),
            "critical_issues": sum(1 for i in issues if i.severity == ValidationSeverity.CRITICAL),
            "error_issues": sum(1 for i in issues if i.severity == ValidationSeverity.ERROR),
            "warning_issues": sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)
        }

    @staticmethod
    def generate_validation_report(report: ValidationReport) -> str:
        """
        生成验证报告

        Args:
            report: 验证报告

        Returns:
            Markdown格式报告
        """
        lines = [
            "# 评分一致性验证报告",
            "",
            f"**验证时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**学生总数**: {report.total_students}",
            f"**问题总数**: {report.issue_count}",
            f"**验证状态**: {'✅ 通过' if report.validation_passed else '❌ 未通过'}",
            ""
        ]

        # 统计信息
        stats = report.statistics
        lines.append("## 📊 统计信息")
        lines.append("")
        lines.append(f"- 平均分: {stats['average_score']:.1f}")
        lines.append(f"- 分数范围: {stats['score_range'][0]:.1f} - {stats['score_range'][1]:.1f}")
        lines.append("")
        lines.append("等级分布:")
        for grade in ['A', 'B', 'C', 'D', 'F']:
            count = stats['grade_distribution'].get(grade, 0)
            ratio = count / report.total_students * 100 if report.total_students > 0 else 0
            lines.append(f"  - {grade}等: {count}人 ({ratio:.1f}%)")
        lines.append("")

        # 问题统计
        lines.append("## ⚠️ 问题统计")
        lines.append("")
        lines.append(f"- 🔴 严重错误: {stats['critical_issues']}个")
        lines.append(f"- 🟠 错误: {stats['error_issues']}个")
        lines.append(f"- 🟡 警告: {stats['warning_issues']}个")
        lines.append("")

        # 详细问题（按严重程度）
        if report.issues:
            severity_groups = {
                ValidationSeverity.CRITICAL: "🔴 严重错误",
                ValidationSeverity.ERROR: "🟠 错误",
                ValidationSeverity.WARNING: "🟡 警告",
                ValidationSeverity.INFO: "🔵 信息"
            }

            lines.append("## 📝 问题详情")
            lines.append("")

            # 只显示错误和警告
            display_severities = [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR, ValidationSeverity.WARNING]

            for severity in display_severities:
                severity_issues = [i for i in report.issues if i.severity == severity]
                if severity_issues:
                    lines.append(f"### {severity_groups.get(severity, severity.value)}")
                    lines.append("")

                    for issue in severity_issues[:10]:  # 最多显示10个
                        student_info = f" [{issue.student_id}]" if issue.student_id else ""
                        lines.append(f"- **{issue.category}**{student_info}: {issue.message}")
                        if issue.details:
                            details_str = ', '.join(f"{k}={v}" for k, v in issue.details.items())
                            lines.append(f"  - 详情: {details_str}")

                    if len(severity_issues) > 10:
                        lines.append(f"- ...还有 {len(severity_issues) - 10} 个同类问题")

                    lines.append("")

        # 改进建议
        if report.recommendations:
            lines.append("## 💡 改进建议")
            lines.append("")
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # 验证结论
        lines.append("---")
        lines.append("")
        if report.validation_passed:
            lines.append("**验证通过**: 评分数据基本正常，建议抽查复核。")
        else:
            lines.append("**验证未通过**: 发现评分异常，请核查问题项后重新评分。")
        lines.append("")

        return '\n'.join(lines)

    @staticmethod
    def save_validation_report(report: ValidationReport, output_path: Path):
        """
        保存验证报告

        Args:
            report: 验证报告
            output_path: 输出路径
        """
        output_path.parent.mkdir(exist_ok=True)

        # 生成Markdown报告
        md_content = GradingValidator.generate_validation_report(report)
        md_path = output_path.with_suffix('.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        # 生成JSON报告
        json_data = {
            'validation_passed': report.validation_passed,
            'statistics': report.statistics,
            'issues': [
                {
                    'severity': i.severity.value,
                    'category': i.category,
                    'message': i.message,
                    'student_id': i.student_id,
                    'details': i.details
                }
                for i in report.issues
            ],
            'recommendations': report.recommendations
        }
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        return md_path, json_path


def validate_grading_results(
    results: List[Dict],
    rubric: Dict,
    output_dir: Path = None
) -> ValidationReport:
    """
    验证评分结果

    Args:
        results: 评分结果列表
        rubric: 评分标准
        output_dir: 输出目录（可选）

    Returns:
        验证报告
    """
    report = GradingValidator.validate_all(results, rubric)

    if output_dir:
        GradingValidator.save_validation_report(
            report,
            output_dir / 'grading_validation_report'
        )

    return report
