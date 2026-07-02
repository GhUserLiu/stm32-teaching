#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强反馈生成器
Enhanced Feedback Generator

提供更精准、更有用的学生报告改进意见
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any


@dataclass
class Issue:
    """问题诊断"""
    id: str                    # 问题ID
    category: str              # 类别：technical/content/quality
    severity: str              # 严重程度：high/medium/low
    title: str                 # 问题标题
    description: str          # 详细描述
    location: Optional[str] = None    # 位置（章节/代码行）
    evidence: str = ""               # 证据（原文内容）
    points_affected: float = 0      # 影响分数


@dataclass
class Suggestion:
    """改进建议"""
    issue: Issue
    priority: int                      # 优先级 1-5（1最高）
    action_steps: List[str] = field(default_factory=list)
    code_example: Optional[str] = None
    resource_links: Dict[str, str] = field(default_factory=dict)
    estimated_time: str = ""


@dataclass
class QuickWin:
    """快速改进项（低挂果实）"""
    title: str
    description: str
    points: float
    time: str


@dataclass
class LearningResource:
    """学习资源"""
    name: str
    path: str
    description: str


@dataclass
class EnhancedFeedbackResult:
    """增强反馈结果"""
    student_id: str
    name: str
    score_summary: Dict[str, Any]
    issues: List[Issue] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    quick_wins: List[QuickWin] = field(default_factory=list)
    learning_path: List[str] = field(default_factory=list)
    resources: List[LearningResource] = field(default_factory=list)

    def get_high_priority_issues(self) -> List[Issue]:
        """获取高优先级问题（必须修改）"""
        return [i for i in self.issues if i.severity == 'high']

    def get_medium_priority_issues(self) -> List[Issue]:
        """获取中优先级问题（建议改进）"""
        return [i for i in self.issues if i.severity == 'medium']

    def get_low_priority_issues(self) -> List[Issue]:
        """获取低优先级问题（可选改进）"""
        return [i for i in self.issues if i.severity == 'low']


class EnhancedFeedbackGenerator:
    """增强反馈生成器"""

    def __init__(self, resources_path: Optional[Path] = None):
        """
        初始化增强反馈生成器

        Args:
            resources_path: 资源配置文件路径
        """
        if resources_path is None:
            resources_path = Path(__file__).parent / 'feedback_resources.json'

        # 资源文件缺失/损坏时降级为空资源，而非崩溃（增强反馈退化为无建议词条的基础模式）
        try:
            with open(resources_path, 'r', encoding='utf-8') as f:
                self.resources = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: 反馈资源 {resources_path.name} 不可用({e})，增强反馈将退化为基础模式")
            self.resources = {}

        self.technical_issues = self.resources.get('technical_issues', [])
        self.content_gaps = self.resources.get('content_gaps', [])
        self.quality_improvements = self.resources.get('quality_improvements', [])
        self.quick_wins_data = self.resources.get('quick_wins', [])

        self.experiment_info = self.resources.get('experiment_info', {})

    def generate_enhanced_feedback(
        self,
        student_id: str,
        name: str,
        text: str,
        grading_result: Any,
        technical_results: Optional[Tuple] = None
    ) -> EnhancedFeedbackResult:
        """
        生成增强反馈

        Args:
            student_id: 学号
            name: 姓名
            text: 报告文本
            grading_result: 评分结果
            technical_results: 技术检查结果

        Returns:
            增强反馈结果
        """
        result = EnhancedFeedbackResult(
            student_id=student_id,
            name=name,
            score_summary={
                'total_score': getattr(grading_result, 'total_score', 0),
                'total_possible': getattr(grading_result, 'total_possible', 100),
                'percentage': getattr(grading_result, 'percentage', 0),
                'grade': getattr(grading_result, 'grade', 'F')
            }
        )

        # 1. 诊断技术问题
        technical_issues = self._diagnose_technical_issues(text)
        result.issues.extend(technical_issues)

        # 2. 诊断内容缺失
        content_issues = self._diagnose_content_gaps(text)
        result.issues.extend(content_issues)

        # 3. 诊断质量问题
        quality_issues = self._diagnose_quality_issues(text)
        result.issues.extend(quality_issues)

        # 4. 为每个问题生成建议
        for issue in result.issues:
            suggestion = self._generate_suggestion(issue)
            result.suggestions.append(suggestion)

        # 5. 按优先级排序建议
        result.suggestions.sort(key=lambda x: x.priority)

        # 6. 生成快速改进项
        result.quick_wins = self._generate_quick_wins(text, result.issues)

        # 7. 生成个性化学习路径
        result.learning_path = self._generate_learning_path(result.issues)

        # 8. 推荐学习资源
        result.resources = self._recommend_resources(result.issues)

        return result

    def _diagnose_technical_issues(self, text: str) -> List[Issue]:
        """诊断技术问题"""
        issues = []
        text_lower = text.lower()

        for issue_data in self.technical_issues:
            # 检测规则
            detection = issue_data.get('detection', {})

            # 检查缺失关键词
            if 'missing_keywords' in detection:
                missing = [kw for kw in detection['missing_keywords']
                          if kw.lower() not in text_lower]

                # 如果有上下文关键词要求
                if 'context_keywords' in detection:
                    has_context = any(kw.lower() in text_lower
                                   for kw in detection['context_keywords'])
                    if not has_context:
                        continue  # 没有相关上下文，跳过

                # 缺失部分关键词则认为有问题
                if len(missing) >= len(detection['missing_keywords']) * 0.5:
                    issues.append(Issue(
                        id=issue_data['id'],
                        category=issue_data['category'],
                        severity=issue_data['severity'],
                        title=issue_data['title'],
                        description=issue_data['description'],
                        location=issue_data.get('section'),
                        evidence=f"缺失关键词: {', '.join(missing)}",
                        points_affected=issue_data.get('points_affected', 0)
                    ))

            # 检查错误模式
            if 'error_patterns' in detection:
                for pattern in detection['error_patterns']:
                    if re.search(pattern, text, re.IGNORECASE):
                        issues.append(Issue(
                            id=issue_data['id'],
                            category=issue_data['category'],
                            severity=issue_data['severity'],
                            title=issue_data['title'],
                            description=issue_data['description'],
                            location=issue_data.get('section'),
                            evidence=f"匹配错误模式: {pattern}",
                            points_affected=issue_data.get('points_affected', 0)
                        ))
                        break

        return issues

    def _diagnose_content_gaps(self, text: str) -> List[Issue]:
        """诊断内容缺失"""
        issues = []
        text_lower = text.lower()

        for gap_data in self.content_gaps:
            detection = gap_data.get('detection', {})

            # 检查缺失关键词
            if 'missing_keywords' in detection:
                missing = [kw for kw in detection['missing_keywords']
                          if kw.lower() not in text_lower]

                threshold = len(detection['missing_keywords']) * 0.6
                if len(missing) >= threshold:
                    issues.append(Issue(
                        id=gap_data['id'],
                        category=gap_data['category'],
                        severity=gap_data['severity'],
                        title=gap_data['title'],
                        description=gap_data['description'],
                        location=gap_data.get('section'),
                        evidence=f"缺失内容: {', '.join(missing)}",
                        points_affected=gap_data.get('points_affected', 0)
                    ))

            # 检查必需项
            if 'required_pins' in detection:
                required_pins = detection['required_pins']
                found_pins = [pin for pin in required_pins if pin in text]
                if len(found_pins) < len(required_pins):
                    issues.append(Issue(
                        id=gap_data['id'],
                        category=gap_data['category'],
                        severity=gap_data['severity'],
                        title=gap_data['title'],
                        description=gap_data['description'],
                        location=gap_data.get('section'),
                        evidence=f"引脚说明缺失: {set(required_pins) - set(found_pins)}",
                        points_affected=gap_data.get('points_affected', 0)
                    ))

            # 检查必需问题数量
            if 'required_questions' in detection:
                # 检测思考题编号 Q1-Q7
                question_pattern = r'[Qq][1-7]|问题[1-7]|[一二三四五六七]、'
                found_questions = len(re.findall(question_pattern, text))
                required = detection['required_questions']

                if found_questions < required:
                    issues.append(Issue(
                        id=gap_data['id'],
                        category=gap_data['category'],
                        severity=gap_data['severity'],
                        title=gap_data['title'],
                        description=gap_data['description'],
                        location=gap_data.get('section'),
                        evidence=f"仅回答{found_questions}题，共{required}题",
                        points_affected=gap_data.get('points_affected', 0)
                    ))

        return issues

    def _diagnose_quality_issues(self, text: str) -> List[Issue]:
        """诊断质量问题"""
        issues = []

        for quality_data in self.quality_improvements:
            detection = quality_data.get('detection', {})

            # 检查代码块格式
            if detection.get('missing_code_blocks'):
                code_count = text.count('```')
                if code_count < 2:  # 需要至少一对````
                    issues.append(Issue(
                        id=quality_data['id'],
                        category=quality_data['category'],
                        severity=quality_data['severity'],
                        title=quality_data['title'],
                        description=quality_data['description'],
                        evidence="未检测到代码块格式",
                        points_affected=quality_data.get('points_affected', 0)
                    ))

            # 检查章节数量
            if 'min_section_count' in detection:
                section_count = len(re.findall(r'[一二三四五六七八九十]+[、．.]', text))
                if section_count < detection['min_section_count']:
                    issues.append(Issue(
                        id=quality_data['id'],
                        category=quality_data['category'],
                        severity=quality_data['severity'],
                        title=quality_data['title'],
                        description=quality_data['description'],
                        evidence=f"检测到{section_count}个章节，建议至少{detection['min_section_count']}个",
                        points_affected=quality_data.get('points_affected', 0)
                    ))

        return issues

    def _generate_suggestion(self, issue: Issue) -> Suggestion:
        """为问题生成建议"""
        # 查找对应的资源数据
        issue_data = None
        for data_list in [self.technical_issues, self.content_gaps, self.quality_improvements]:
            for item in data_list:
                if item['id'] == issue.id:
                    issue_data = item
                    break
            if issue_data:
                break

        if not issue_data:
            return Suggestion(issue=issue, priority=3)

        # 计算优先级
        severity_to_priority = {'high': 1, 'medium': 2, 'low': 3}
        priority = severity_to_priority.get(issue.severity, 3)

        # 资源链接
        resource_links = {}
        if 'resources' in issue_data:
            resources = issue_data['resources']
            if 'task_section' in resources:
                task_path = self.experiment_info.get('task_doc', '')
                resource_links['任务书'] = f"{task_path}#{resources['task_section']}"
            if 'reference_code' in resources:
                code_path = self.experiment_info.get('reference_code', '')
                resource_links['参考代码'] = f"{code_path}:{resources['reference_code']}"
            if 'thinking_question' in resources:
                task_path = self.experiment_info.get('task_doc', '')
                resource_links['思考题'] = f"{task_path}#思考题:{resources['thinking_question']}"

        return Suggestion(
            issue=issue,
            priority=priority,
            action_steps=issue_data.get('suggestions', []),
            code_example=issue_data.get('code_example'),
            resource_links=resource_links,
            estimated_time=issue_data.get('estimated_time', '')
        )

    def _generate_quick_wins(self, text: str, issues: List[Issue]) -> List[QuickWin]:
        """生成快速改进项"""
        quick_wins = []

        # 从配置中获取
        for win_data in self.quick_wins_data:
            # 检查是否已经存在类似问题
            existing = any(i.id == win_data.get('issue_ref') for i in issues)
            if not existing:
                quick_wins.append(QuickWin(
                    title=win_data['title'],
                    description=win_data['description'],
                    points=win_data['points'],
                    time=win_data['time']
                ))

        return quick_wins

    def _generate_learning_path(self, issues: List[Issue]) -> List[str]:
        """生成个性化学习路径"""
        path = []

        # 按问题类型和严重程度排序
        high_priority = [i for i in issues if i.severity == 'high']
        medium_priority = [i for i in issues if i.severity == 'medium']

        # 生成学习步骤
        if high_priority:
            path.append("## 第一优先级：核心技术要点（必须掌握）")
            for issue in high_priority[:3]:
                path.append(f"1. **{issue.title}** - {issue.description}")

        if medium_priority:
            path.append("")
            path.append("## 第二优先级：内容完善（建议完成）")
            for issue in medium_priority[:3]:
                path.append(f"1. **{issue.title}** - {issue.description}")

        return path

    def _recommend_resources(self, issues: List[Issue]) -> List[LearningResource]:
        """推荐学习资源"""
        resources = []

        # 实验任务书
        resources.append(LearningResource(
            name="完整任务书",
            path=self.experiment_info.get('task_doc', ''),
            description="包含实验原理、技术要点、思考题答案"
        ))

        # 参考代码
        resources.append(LearningResource(
            name="参考实现代码",
            path=self.experiment_info.get('reference_code', ''),
            description="完整的档位实验参考实现"
        ))

        # 实验报告模板
        resources.append(LearningResource(
            name="实验报告模板",
            path=self.experiment_info.get('template', ''),
            description="标准报告结构和格式"
        ))

        return resources

    def format_enhanced_feedback(self, result: EnhancedFeedbackResult) -> str:
        """格式化增强反馈为Markdown"""
        lines = [
            f"# 📊 实验报告增强反馈",
            "",
            f"**学号**: {result.student_id}",
            f"**姓名**: {result.name}",
            f"**总分**: {result.score_summary['total_score']}/{result.score_summary['total_possible']} ({result.score_summary['percentage']:.1f}%)",
            f"**等级**: {result.score_summary['grade']}",
            "",
            "---",
            ""
        ]

        # 1. 必须修改的问题
        high_issues = result.get_high_priority_issues()
        if high_issues:
            lines.extend([
                "## 🔴 必须修改的问题",
                "",
                f"发现 {len(high_issues)} 个需要优先修改的问题：",
                ""
            ])

            for i, issue in enumerate(high_issues, 1):
                lines.append(f"### {i}. {issue.title}")
                if issue.location:
                    lines.append(f"**位置**: {issue.location}")
                lines.append(f"**问题**: {issue.description}")
                if issue.points_affected > 0:
                    lines.append(f"**影响**: 约 {issue.points_affected} 分")
                lines.append("")

        # 2. 建议改进的问题
        medium_issues = result.get_medium_priority_issues()
        if medium_issues:
            lines.extend([
                "## 🟡 建议改进的问题",
                "",
                f"发现 {len(medium_issues)} 个可以改进的地方：",
                ""
            ])

            for i, issue in enumerate(medium_issues, 1):
                lines.append(f"### {i}. {issue.title}")
                lines.append(f"**问题**: {issue.description}")
                lines.append("")

        # 3. 详细改进建议
        if result.suggestions:
            lines.extend([
                "## 📝 详细改进建议",
                ""
            ])

            for suggestion in result.suggestions[:5]:  # 最多显示5个
                issue = suggestion.issue
                lines.append(f"### {issue.title}")

                if suggestion.action_steps:
                    lines.append("**改进步骤**:")
                    for step in suggestion.action_steps:
                        lines.append(f"1. {step}")
                    lines.append("")

                if suggestion.code_example:
                    lines.append("**代码示例**:")
                    lines.append("```c")
                    lines.append(suggestion.code_example)
                    lines.append("```")
                    lines.append("")

                if suggestion.resource_links:
                    lines.append("**学习资源**:")
                    for name, link in suggestion.resource_links.items():
                        lines.append(f"- 📖 [{name}]({link})")
                    lines.append("")

                if suggestion.estimated_time:
                    lines.append(f"⏱️ 预计时间: {suggestion.estimated_time}")
                    lines.append("")

        # 4. 快速改进（低挂果实）
        if result.quick_wins:
            lines.extend([
                "## ⚡ 快速改进（低挂果实）",
                "",
                "这些改进简单但有效：",
                ""
            ])

            for win in result.quick_wins:
                lines.append(f"- ✓ **{win.title}** (+{win.points}分, {win.time})")
                lines.append(f"  - {win.description}")
            lines.append("")

        # 5. 个性化学习路径
        if result.learning_path:
            lines.extend([
                "---",
                "",
                "## 🎯 学习路径（基于您的薄弱环节）",
                "",
                "根据您的报告分析，建议按以下顺序学习：",
                ""
            ])
            lines.extend(result.learning_path)
            lines.append("")

        # 6. 推荐资源
        if result.resources:
            lines.extend([
                "---",
                "",
                "## 📚 推荐资源",
                "",
                "| 资源 | 位置 | 用途 |",
                "|------|------|------|"
            ])

            for res in result.resources:
                lines.append(f"| {res.name} | [{res.path}]({res.path}) | {res.description} |")
            lines.append("")

        lines.extend([
            "---",
            "",
            "*本反馈由增强评估系统自动生成*"
        ])

        return '\n'.join(lines)


def save_enhanced_feedback(
    result: EnhancedFeedbackResult,
    output_dir: Path,
    generator: EnhancedFeedbackGenerator
) -> Path:
    """
    保存增强反馈到文件

    Args:
        result: 增强反馈结果
        output_dir: 输出目录
        generator: 增强反馈生成器

    Returns:
        输出文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    content = generator.format_enhanced_feedback(result)
    # 清理文件名中的特殊字符
    safe_name = result.name.replace('/', '_').replace('\\', '_').replace(':', '_')
    file_path = output_dir / f"{result.student_id}_{safe_name}_增强反馈.md"

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return file_path


# 导出主要类和函数
__all__ = [
    'Issue',
    'Suggestion',
    'QuickWin',
    'LearningResource',
    'EnhancedFeedbackResult',
    'EnhancedFeedbackGenerator',
    'save_enhanced_feedback'
]
