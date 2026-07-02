#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细评分反馈生成器
Detailed Feedback Generator

为学生生成详细的评分反馈报告
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path


@dataclass
class FeedbackItem:
    """反馈项"""
    category: str
    message: str
    score_impact: float  # 对分数的影响
    suggestion: str = ""


class FeedbackGenerator:
    """反馈生成器"""

    # 通用反馈模板
    COMMON_TEMPLATES = {
        "missing_section": "【{section}】报告缺少该章节，请补充相关内容。",
        "incomplete_section": "【{section}】该章节内容不够完整，建议{action}。",
        "incorrect_technical": "【{point}】技术要点可能有误，建议检查{detail}。",
        "good_work": "【{section}】该部分完成良好，{praise}。",
        "code_comment": "代码注释{status}，建议{action}。",
        "plagiarism_warning": "⚠️ 抄袭警告：报告内容与其他同学高度相似（{similarity}%），请确认是否为原创。",
        "low_quality": "报告整体质量{level}，建议{focus}。"
    }

    @staticmethod
    def generate_for_student(
        student_id: str,
        name: str,
        grading_result,
        technical_results,
        plagiarism_risk: float = 0.0
    ) -> str:
        """
        为学生生成详细反馈

        Args:
            student_id: 学号
            name: 姓名
            grading_result: 评分结果
            technical_results: 技术检查结果
            plagiarism_risk: 抄袭风险

        Returns:
            反馈文本
        """
        lines = [
            f"# 实验报告评分反馈",
            "",
            f"**学号**: {student_id}",
            f"**姓名**: {name}",
            f"**总分**: {grading_result.total_score}/{grading_result.total_possible} ({grading_result.percentage:.1f}%)",
            f"**等级**: {grading_result.grade}",
            "",
            "---",
            ""
        ]

        # 1. 各项得分详情
        lines.extend(FeedbackGenerator._generate_category_scores(grading_result))

        # 2. 技术要点检查
        lines.extend(FeedbackGenerator._generate_technical_feedback(technical_results))

        # 3. 亮点与不足
        lines.extend(FeedbackGenerator._generate_strengths_weaknesses(
            grading_result.strengths,
            grading_result.weaknesses
        ))

        # 4. 改进建议
        if grading_result.recommendations:
            lines.append("\n## 改进建议\n")
            for rec in grading_result.recommendations:
                lines.append(f"- {rec}")

        # 5. 抄袭警告（分级显示）
        if plagiarism_risk > 0.85:
            lines.append("\n---")
            lines.append(f"\n⛔ **抄袭警告**: 检测到抄袭 ({plagiarism_risk*100:.1f}%)")
            lines.append("\n您的报告与其他同学高度相似，被系统检测为抄袭。")
            lines.append("\n**请立即确认：**")
            lines.append("- 是否为原创作品？")
            lines.append("- 如确属抄袭，请主动联系教师说明情况")
            lines.append("- 如确属原创，请在下次提交时注意避免过度参考他人")
        elif plagiarism_risk > 0.60:
            lines.append("\n---")
            lines.append(f"\n⚠️ **相似度提醒**: 相似度 {plagiarism_risk*100:.1f}%")
            lines.append("\n您的报告内容与其他同学相似度较高，请注意原创性。")
            lines.append("\n建议：")
            lines.append("- 确认是否为原创，避免过度参考同学报告")
            lines.append("- 使用自己的语言描述实验过程")
            lines.append("- 添加个人独特的思考和体会")

        # 6. 鼓励语
        lines.extend(FeedbackGenerator._generate_encouragement(grading_result))

        return '\n'.join(lines)

    @staticmethod
    def _generate_category_scores(grading_result) -> List[str]:
        """生成各项得分"""
        lines = ["## 各项得分详情\n"]

        for category_id, score in grading_result.category_scores.items():
            status_emoji = "✅" if score.percentage >= 80 else "⚠️" if score.percentage >= 60 else "❌"

            lines.append(f"### {status_emoji} {score.name} ({score.points_earned}/{score.points_possible})")

            for feedback in score.feedback:
                lines.append(f"- {feedback}")

            lines.append("")

        return lines

    @staticmethod
    def _generate_technical_feedback(technical_results) -> List[str]:
        """生成技术要点反馈"""
        if not technical_results:
            return []

        lines = ["## 技术要点检查\n"]

        total_earned, results, strengths, weaknesses = technical_results

        lines.append(f"**技术要点得分**: {total_earned:.1f}分\n")

        if strengths:
            lines.append("### ✅ 正确掌握的技术要点")
            for strength in strengths[:5]:  # 最多显示5个
                lines.append(f"- {strength}")
            lines.append("")

        if weaknesses:
            lines.append("### ⚠️ 需要加强的技术要点")
            for weakness in weaknesses[:5]:
                lines.append(f"- {weakness}")
            lines.append("")

        return lines

    @staticmethod
    def _generate_strengths_weaknesses(strengths: List[str], weaknesses: List[str]) -> List[str]:
        """生成亮点与不足"""
        lines = ["## 报告评价\n"]

        if strengths:
            lines.append("### 🌟 亮点")
            for strength in strengths:
                lines.append(f"- {strength}")
            lines.append("")

        if weaknesses:
            lines.append("### 📝 需要改进")
            for weakness in weaknesses:
                lines.append(f"- {weakness}")
            lines.append("")

        return lines

    @staticmethod
    def _generate_encouragement(grading_result) -> List[str]:
        """生成鼓励语"""
        lines = ["\n---\n"]

        if grading_result.percentage >= 90:
            lines.append("🎉 **优秀！** 您的实验报告质量很高，继续保持！")
        elif grading_result.percentage >= 80:
            lines.append("👍 **良好！** 您的实验报告完成得不错，继续努力！")
        elif grading_result.percentage >= 70:
            lines.append("📈 **中等！** 您的实验报告基本达标，仍有提升空间。")
        elif grading_result.percentage >= 60:
            lines.append("📝 **及格！** 建议参考优秀同学报告，完善您的实验报告。")
        else:
            lines.append("💪 **加油！** 建议认真补充报告内容，下次争取更好成绩！")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*本报告由系统自动生成，如有疑问请联系教师。*")

        return lines


class HTMLFeedbackGenerator:
    """HTML格式反馈生成器"""

    @staticmethod
    def generate(
        student_id: str,
        name: str,
        grading_result,
        technical_results,
        plagiarism_risk: float = 0.0
    ) -> str:
        """生成HTML格式反馈"""
        text_feedback = FeedbackGenerator.generate_for_student(
            student_id, name, grading_result, technical_results, plagiarism_risk
        )

        # 转换为HTML
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>实验报告反馈 - {name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .header-info {{
            background: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .score-display {{
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
        }}
        .grade-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            background: #4CAF50;
            color: white;
            font-weight: bold;
        }}
        .category {{
            margin: 20px 0;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 5px;
        }}
        .category-header {{
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .strength {{
            color: #2e7d32;
        }}
        .weakness {{
            color: #c62828;
        }}
        .warning {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
        ul {{
            margin: 10px 0;
        }}
        li {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 实验报告反馈</h1>

        <div class="header-info">
            <p><strong>学号:</strong> {student_id}</p>
            <p><strong>姓名:</strong> {name}</p>
            <p><strong>总分:</strong> <span class="score-display">{grading_result.total_score}/{grading_result.total_possible}</span>
            <p><strong>等级:</strong> <span class="grade-badge">{grading_result.grade}</span></p>
        </div>

        {HTMLFeedbackGenerator._generate_categories_html(grading_result)}

        {HTMLFeedbackGenerator._generate_technical_html(technical_results)}

        {HTMLFeedbackGenerator._generate_feedback_html(grading_result)}

        {HTMLFeedbackGenerator._generate_warning_html(plagiarism_risk)}

        <div style="text-align: center; margin-top: 40px; color: #666; font-size: 14px;">
            <p>— 本报告由系统自动生成 —</p>
        </div>
    </div>
</body>
</html>"""
        return html

    @staticmethod
    def _generate_categories_html(grading_result) -> str:
        """生成评分分类HTML"""
        lines = ["<h2>📋 各项得分</h2>"]

        for category_id, score in grading_result.category_scores.items():
            percentage = score.percentage
            color = "#4CAF50" if percentage >= 80 else "#FF9800" if percentage >= 60 else "#F44336"

            lines.append(f"""
        <div class="category">
            <div class="category-header" style="color: {color};">
                {score.name} ({score.points_earned}/{score.points_possible}) - {percentage:.0f}%
            </div>
            <ul>""")

            for feedback in score.feedback:
                css_class = "strength" if "✓" in feedback else "weakness" if "✗" in feedback else ""
                lines.append(f'<li class="{css_class}">{feedback}</li>')

            lines.append("    </ul>")
            lines.append("</div>")

        return '\n'.join(lines)

    @staticmethod
    def _generate_technical_html(technical_results) -> str:
        """生成技术要点HTML"""
        if not technical_results:
            return ""

        total_earned, results, strengths, weaknesses = technical_results

        lines = ["<h2>🔧 技术要点检查</h2>"]
        lines.append(f"<p><strong>技术要点得分:</strong> {total_earned:.1f}分</p>")

        if strengths:
            lines.append("<h3 style='color: #2e7d32;'>✅ 正确掌握</h3><ul>")
            for strength in strengths[:5]:
                lines.append(f"<li>{strength}</li>")
            lines.append("</ul>")

        if weaknesses:
            lines.append("<h3 style='color: #c62828;'>⚠️ 需要加强</h3><ul>")
            for weakness in weaknesses[:5]:
                lines.append(f"<li>{weakness}</li>")
            lines.append("</ul>")

        return '\n'.join(lines)

    @staticmethod
    def _generate_feedback_html(grading_result) -> str:
        """生成反馈HTML"""
        lines = ["<h2>💬 详细反馈</h2>"]

        if grading_result.strengths:
            lines.append("<h3 style='color: #2e7d32;'>🌟 亮点</h3><ul>")
            for strength in grading_result.strengths:
                lines.append(f"<li>{strength}</li>")
            lines.append("</ul>")

        if grading_result.weaknesses:
            lines.append("<h3 style='color: #c62828;'>📝 需要改进</h3><ul>")
            for weakness in grading_result.weaknesses:
                lines.append(f"<li>{weakness}</li>")
            lines.append("</ul>")

        if grading_result.recommendations:
            lines.append("<h3>💡 改进建议</h3><ul>")
            for rec in grading_result.recommendations:
                lines.append(f"<li>{rec}</li>")
            lines.append("</ul>")

        return '\n'.join(lines)

    @staticmethod
    def _generate_warning_html(plagiarism_risk: float) -> str:
        """生成警告HTML"""
        if plagiarism_risk <= 0.60:
            return ""

        # 根据相似度级别显示不同的警告
        if plagiarism_risk > 0.85:
            title = "⛔ 抄袭警告"
            risk_label = "检测到抄袭"
            suggestions = [
                "请立即确认是否为原创作品",
                "如确属抄袭，请主动联系教师说明情况",
                "如确属原创，请在下次提交时注意避免过度参考他人"
            ]
        else:
            title = "⚠️ 相似度提醒"
            risk_label = "相似度较高"
            suggestions = [
                "确认是否为原创，避免过度参考同学报告",
                "使用自己的语言描述实验过程",
                "添加个人独特的思考和体会"
            ]

        suggestions_html = "\n".join(f"<li>{s}</li>" for s in suggestions)

        return f"""
        <div class="warning">
            <h3>{title}</h3>
            <p><strong>{risk_label}:</strong> {plagiarism_risk*100:.1f}%</p>
            <p>您的报告内容与其他同学相似度较高，请注意原创性。</p>
            <p>建议：</p>
            <ul>
                {suggestions_html}
            </ul>
        </div>"""


def save_student_feedback(
    student_id: str,
    name: str,
    grading_result,
    technical_results,
    output_dir: Path,
    plagiarism_risk: float = 0.0,
    format: str = "md",
    enhanced: bool = False,
    text: str = ""
) -> Path:
    """
    保存学生反馈文件

    Args:
        student_id: 学号
        name: 姓名
        grading_result: 评分结果
        technical_results: 技术检查结果
        output_dir: 输出目录
        plagiarism_risk: 抄袭风险
        format: 输出格式 (md/html)
        enhanced: 是否生成增强反馈
        text: 报告全文（增强反馈需要）

    Returns:
        输出文件路径
    """
    output_dir.mkdir(exist_ok=True)

    if enhanced:
        # 导入增强反馈生成器
        try:
            from .enhanced_feedback import EnhancedFeedbackGenerator, save_enhanced_feedback

            generator = EnhancedFeedbackGenerator()
            enhanced_result = generator.generate_enhanced_feedback(
                student_id, name, text, grading_result, technical_results
            )
            return save_enhanced_feedback(enhanced_result, output_dir, generator)
        except (ImportError, FileNotFoundError, ValueError) as e:
            # 资源文件缺失/损坏等不应崩溃，降级为标准反馈
            print(f"Warning: Enhanced feedback 不可用({e})，改用标准反馈")

    if format == "html":
        content = HTMLFeedbackGenerator.generate(
            student_id, name, grading_result, technical_results, plagiarism_risk
        )
        file_path = output_dir / f"{student_id}_{name}_反馈.html"
    else:
        content = FeedbackGenerator.generate_for_student(
            student_id, name, grading_result, technical_results, plagiarism_risk
        )
        file_path = output_dir / f"{student_id}_{name}_反馈.md"

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return file_path
