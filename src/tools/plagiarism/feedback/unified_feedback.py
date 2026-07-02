#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一反馈系统
Unified Feedback System

整合基础反馈、增强反馈和智能反馈，提供统一的接口
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Literal
from enum import Enum


class FeedbackFormat(Enum):
    """反馈格式"""
    MARKDOWN = "md"
    HTML = "html"
    JSON = "json"
    DOCX = "docx"


class FeedbackStyle(Enum):
    """反馈风格"""
    STANDARD = "standard"      # 标准风格
    DETAILED = "detailed"      # 详细风格
    CONCISE = "concise"        # 简洁风格
    ENCOURAGING = "encouraging" # 鼓励风格
    TECHNICAL = "technical"    # 技术风格


@dataclass
class FeedbackIssue:
    """问题诊断"""
    id: str
    category: str              # technical/content/quality/code
    severity: str              # critical/high/medium/low
    title: str
    description: str
    location: Optional[str] = None
    evidence: str = ""
    points_affected: float = 0
    fix_time: str = ""          # 预计修复时间


@dataclass
class FeedbackSuggestion:
    """改进建议"""
    issue_id: str
    priority: int               # 1-5, 1最高
    action_steps: List[str] = field(default_factory=list)
    code_example: Optional[str] = None
    resources: Dict[str, str] = field(default_factory=dict)
    expected_improvement: str = ""


@dataclass
class QuickWin:
    """快速改进项"""
    title: str
    description: str
    points: float
    time: str


@dataclass
class LearningResource:
    """学习资源"""
    name: str
    path: str
    type: str                   # doc/video/tutorial/example
    description: str = ""


@dataclass
class SimilarityInfo:
    """相似度详细信息"""
    student_id: str             # 相似学生的学号
    name: str                   # 相似学生的姓名
    similarity: float           # 相似度百分比 (0-100)
    is_cross_group: bool = False  # 是否跨组


@dataclass
class UnifiedFeedbackResult:
    """统一反馈结果"""
    student_id: str
    name: str

    # 评分信息
    total_score: float
    total_possible: float
    percentage: float
    grade: str

    # 分类得分
    category_scores: Dict[str, Any] = field(default_factory=dict)

    # 问题诊断
    issues: List[FeedbackIssue] = field(default_factory=list)

    # 改进建议
    suggestions: List[FeedbackSuggestion] = field(default_factory=list)

    # 快速改进
    quick_wins: List[QuickWin] = field(default_factory=list)

    # 亮点与不足
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)

    # 学习路径
    learning_path: List[str] = field(default_factory=list)

    # 推荐资源
    resources: List[LearningResource] = field(default_factory=list)

    # 抄袭风险
    plagiarism_risk: float = 0.0

    # 相似度详细信息（与哪些学生相似度高）
    similarity_details: List[SimilarityInfo] = field(default_factory=list)

    # 元数据
    experiment_type: str = ""
    generated_at: str = ""

    def get_issues_by_severity(self, severity: str) -> List[FeedbackIssue]:
        """按严重程度获取问题"""
        return [i for i in self.issues if i.severity == severity]

    def get_issues_by_category(self, category: str) -> List[FeedbackIssue]:
        """按类别获取问题"""
        return [i for i in self.issues if i.category == category]

    def get_high_priority_suggestions(self, limit: int = 5) -> List[FeedbackSuggestion]:
        """获取高优先级建议"""
        return sorted(self.suggestions, key=lambda x: x.priority)[:limit]


class UnifiedFeedbackGenerator:
    """统一反馈生成器"""

    # 反馈模板配置
    TEMPLATES = {
        FeedbackStyle.STANDARD: {
            "header": "# 实验报告评分反馈",
            "greeting": "",
            "sections": ["scores", "issues", "suggestions", "quick_wins", "encouragement"]
        },
        FeedbackStyle.DETAILED: {
            "header": "# 📊 实验报告详细反馈",
            "greeting": "亲爱的{name}同学：\n\n感谢你提交实验报告。以下是详细的反馈意见：",
            "sections": ["summary", "scores", "issues", "suggestions", "learning_path", "resources", "encouragement"]
        },
        FeedbackStyle.CONCISE: {
            "header": "# 实验报告反馈",
            "greeting": "",
            "sections": ["summary", "top_issues", "quick_wins"]
        },
        FeedbackStyle.ENCOURAGING: {
            "header": "# 🌟 实验报告反馈",
            "greeting": "你好{name}同学！\n\n我们一起来看看这份实验报告吧：",
            "sections": ["scores", "strengths", "suggestions", "encouragement"],
            "tone": "positive"
        },
        FeedbackStyle.TECHNICAL: {
            "header": "# 🔧 技术反馈报告",
            "greeting": "",
            "sections": ["summary", "scores", "issues", "suggestions", "resources"],
            "focus": "technical"
        }
    }

    def __init__(self, resources_path: Optional[Path] = None):
        """
        初始化统一反馈生成器

        Args:
            resources_path: 资源配置文件路径
        """
        if resources_path is None:
            resources_path = Path(__file__).parent / 'feedback_resources.json'

        self.resources_path = resources_path
        self.resources = self._load_resources()

    def _load_resources(self) -> Dict:
        """加载资源配置"""
        if self.resources_path.exists():
            with open(self.resources_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._get_default_resources()

    def _get_default_resources(self) -> Dict:
        """获取默认资源配置"""
        return {
            "experiment_info": {},
            "technical_issues": [],
            "content_gaps": [],
            "quality_improvements": [],
            "quick_wins": [],
            "learning_templates": [],
            "feedback_styles": {}
        }

    def generate(
        self,
        student_id: str,
        name: str,
        text: str,
        grading_result: Any,
        technical_result: Optional[Tuple] = None,
        plagiarism_risk: float = 0.0,
        similarity_details: Optional[List[SimilarityInfo]] = None,
        style: FeedbackStyle = FeedbackStyle.DETAILED,
        format: FeedbackFormat = FeedbackFormat.MARKDOWN
    ) -> UnifiedFeedbackResult:
        """
        生成统一反馈

        Args:
            student_id: 学号
            name: 姓名
            text: 报告文本
            grading_result: 评分结果
            technical_result: 技术检查结果
            plagiarism_risk: 抄袭风险
            similarity_details: 相似度详细信息列表
            style: 反馈风格
            format: 输出格式

        Returns:
            统一反馈结果
        """
        from datetime import datetime

        # 创建基础结果
        result = UnifiedFeedbackResult(
            student_id=student_id,
            name=name,
            total_score=getattr(grading_result, 'total_score', 0),
            total_possible=getattr(grading_result, 'total_possible', 100),
            percentage=getattr(grading_result, 'percentage', 0),
            grade=getattr(grading_result, 'grade', 'F'),
            plagiarism_risk=plagiarism_risk,
            similarity_details=similarity_details or [],
            experiment_type=self.resources.get('experiment_info', {}).get('name', ''),
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        # 转换分类得分
        if hasattr(grading_result, 'category_scores'):
            for cat_id, cat_score in grading_result.category_scores.items():
                result.category_scores[cat_id] = {
                    'name': cat_score.name,
                    'earned': cat_score.points_earned,
                    'possible': cat_score.points_possible,
                    'percentage': cat_score.percentage,
                    'feedback': cat_score.feedback
                }

        # 收集亮点和不足
        result.strengths = getattr(grading_result, 'strengths', [])
        result.weaknesses = getattr(grading_result, 'weaknesses', [])

        # 诊断问题
        result.issues = self._diagnose_issues(text, technical_result)

        # 生成建议
        result.suggestions = self._generate_suggestions(result.issues)

        # 生成快速改进项
        result.quick_wins = self._generate_quick_wins(text, result.issues)

        # 生成学习路径
        result.learning_path = self._generate_learning_path(result.issues, result.weaknesses)

        # 推荐资源
        result.resources = self._recommend_resources(result.issues)

        return result

    def _diagnose_issues(
        self,
        text: str,
        technical_result: Optional[Tuple]
    ) -> List[FeedbackIssue]:
        """诊断问题"""
        issues = []
        text_lower = text.lower()

        # 1. 从资源配置中检测技术问题
        for issue_data in self.resources.get('technical_issues', []):
            issue = self._check_issue(issue_data, text, text_lower, 'technical')
            if issue:
                issues.append(issue)

        # 2. 检测内容缺失
        for gap_data in self.resources.get('content_gaps', []):
            issue = self._check_issue(gap_data, text, text_lower, 'content')
            if issue:
                issues.append(issue)

        # 3. 检测质量问题
        for quality_data in self.resources.get('quality_improvements', []):
            issue = self._check_issue(quality_data, text, text_lower, 'quality')
            if issue:
                issues.append(issue)

        # 4. 从技术检查结果中提取问题
        if technical_result:
            _, _, strengths, weaknesses = technical_result
            for weakness in weaknesses[:5]:
                # 将弱点转换为问题
                issues.append(FeedbackIssue(
                    id=f"tech_{len(issues)}",
                    category="technical",
                    severity="medium",
                    title=weakness[:50] + "..." if len(weakness) > 50 else weakness,
                    description=weakness,
                    points_affected=2
                ))

        return issues

    def _check_issue(
        self,
        issue_data: Dict,
        text: str,
        text_lower: str,
        default_category: str
    ) -> Optional[FeedbackIssue]:
        """检查单个问题"""
        import re

        detection = issue_data.get('detection', {})

        # 检查缺失关键词
        if 'missing_keywords' in detection:
            missing = [kw for kw in detection['missing_keywords']
                      if kw.lower() not in text_lower]

            # 如果有上下文要求
            if 'context_keywords' in detection:
                has_context = any(kw.lower() in text_lower
                               for kw in detection['context_keywords'])
                if not has_context:
                    return None

            # 缺失达到阈值
            threshold = len(detection['missing_keywords']) * 0.5
            if len(missing) >= threshold:
                return FeedbackIssue(
                    id=issue_data['id'],
                    category=issue_data.get('category', default_category),
                    severity=issue_data.get('severity', 'medium'),
                    title=issue_data['title'],
                    description=issue_data['description'],
                    location=issue_data.get('section'),
                    evidence=f"缺失: {', '.join(missing[:3])}",
                    points_affected=issue_data.get('points_affected', 0),
                    fix_time=issue_data.get('estimated_time', '')
                )

        # 检查错误模式
        if 'error_patterns' in detection:
            for pattern in detection['error_patterns']:
                if re.search(pattern, text, re.IGNORECASE):
                    return FeedbackIssue(
                        id=issue_data['id'],
                        category=issue_data.get('category', default_category),
                        severity=issue_data.get('severity', 'high'),
                        title=issue_data['title'],
                        description=issue_data['description'],
                        location=issue_data.get('section'),
                        evidence=f"匹配模式: {pattern}",
                        points_affected=issue_data.get('points_affected', 0),
                        fix_time=issue_data.get('estimated_time', '')
                    )

        return None

    def _generate_suggestions(self, issues: List[FeedbackIssue]) -> List[FeedbackSuggestion]:
        """为问题生成建议"""
        suggestions = []

        for issue in issues:
            # 从资源配置中查找对应的建议
            suggestion_data = None
            for data_list in [
                self.resources.get('technical_issues', []),
                self.resources.get('content_gaps', []),
                self.resources.get('quality_improvements', [])
            ]:
                for item in data_list:
                    if item.get('id') == issue.id:
                        suggestion_data = item
                        break
                if suggestion_data:
                    break

            if not suggestion_data:
                continue

            # 计算优先级
            severity_to_priority = {
                'critical': 1, 'high': 2, 'medium': 3, 'low': 4
            }
            priority = severity_to_priority.get(issue.severity, 3)

            # 资源链接
            resources = {}
            if 'resources' in suggestion_data:
                exp_info = self.resources.get('experiment_info', {})
                for key, value in suggestion_data['resources'].items():
                    if key == 'task_section' and 'task_doc' in exp_info:
                        resources['任务书'] = f"{exp_info['task_doc']}#{value}"
                    elif key == 'reference_code' and 'reference_code' in exp_info:
                        resources['参考代码'] = f"{exp_info['reference_code']}:{value}"

            suggestions.append(FeedbackSuggestion(
                issue_id=issue.id,
                priority=priority,
                action_steps=suggestion_data.get('suggestions', []),
                code_example=suggestion_data.get('code_example'),
                resources=resources,
                expected_improvement=f"+{issue.points_affected}分"
            ))

        return sorted(suggestions, key=lambda x: x.priority)

    def _generate_quick_wins(
        self,
        text: str,
        issues: List[FeedbackIssue]
    ) -> List[QuickWin]:
        """生成快速改进项"""
        quick_wins = []
        issue_ids = {i.id for i in issues}

        for win_data in self.resources.get('quick_wins', []):
            # 如果没有对应问题，则作为快速改进建议
            if win_data.get('issue_ref') not in issue_ids:
                quick_wins.append(QuickWin(
                    title=win_data['title'],
                    description=win_data['description'],
                    points=win_data['points'],
                    time=win_data['time']
                ))

        return quick_wins

    def _generate_learning_path(
        self,
        issues: List[FeedbackIssue],
        weaknesses: List[str]
    ) -> List[str]:
        """生成个性化学习路径"""
        path = []

        # 按严重程度分组
        critical = [i for i in issues if i.severity == 'critical']
        high = [i for i in issues if i.severity == 'high']
        medium = [i for i in issues if i.severity == 'medium']

        # 生成学习步骤
        if critical:
            path.append("## 第一优先级：核心问题（必须解决）")
            for issue in critical[:3]:
                path.append(f"1. **{issue.title}** - {issue.description}")
            path.append("")

        if high:
            path.append("## 第二优先级：重要改进（建议完成）")
            for issue in high[:3]:
                path.append(f"1. **{issue.title}** - {issue.description}")
            path.append("")

        if medium:
            path.append("## 第三优先级：质量提升（可选完成）")
            for issue in medium[:3]:
                path.append(f"1. **{issue.title}** - {issue.description}")

        return path

    def _recommend_resources(self, issues: List[FeedbackIssue]) -> List[LearningResource]:
        """推荐学习资源"""
        resources = []
        exp_info = self.resources.get('experiment_info', {})

        # 基础资源
        if 'task_doc' in exp_info:
            resources.append(LearningResource(
                name="实验任务书",
                path=exp_info['task_doc'],
                type="doc",
                description="包含实验原理、技术要点和评分标准"
            ))

        if 'reference_code' in exp_info:
            resources.append(LearningResource(
                name="参考代码",
                path=exp_info['reference_code'],
                type="example",
                description="完整的参考实现"
            ))

        if 'template' in exp_info:
            resources.append(LearningResource(
                name="报告模板",
                path=exp_info['template'],
                type="doc",
                description="标准报告格式和结构"
            ))

        # 根据问题推荐专项资源
        for issue in issues:
            if 'GPIO' in issue.title or '引脚' in issue.title:
                resources.append(LearningResource(
                    name="GPIO配置指南",
                    path="#",
                    type="tutorial",
                    description="STM32 GPIO工作原理和配置方法"
                ))
            elif '中断' in issue.title or 'EXTI' in issue.title:
                resources.append(LearningResource(
                    name="中断系统详解",
                    path="#",
                    type="tutorial",
                    description="EXTI中断原理和配置"
                ))
            elif '状态' in issue.title or '档位' in issue.title:
                resources.append(LearningResource(
                    name="状态机设计",
                    path="#",
                    type="doc",
                    description="有限状态机设计模式"
                ))

        # 去重
        seen = set()
        unique = []
        for r in resources:
            if r.name not in seen:
                seen.add(r.name)
                unique.append(r)

        return unique

    def format_feedback(
        self,
        result: UnifiedFeedbackResult,
        style: FeedbackStyle = FeedbackStyle.DETAILED,
        format: FeedbackFormat = FeedbackFormat.MARKDOWN
    ) -> str:
        """
        格式化反馈输出

        Args:
            result: 反馈结果
            style: 反馈风格
            format: 输出格式

        Returns:
            格式化的反馈文本
        """
        if format == FeedbackFormat.JSON:
            return self._format_json(result)
        elif format == FeedbackFormat.HTML:
            return self._format_html(result, style)
        else:
            return self._format_markdown(result, style)

    def _format_markdown(
        self,
        result: UnifiedFeedbackResult,
        style: FeedbackStyle
    ) -> str:
        """格式化为Markdown"""
        template = self.TEMPLATES.get(style, self.TEMPLATES[FeedbackStyle.STANDARD])

        lines = []

        # 标题
        lines.append(template["header"])
        lines.append("")

        # 问候语
        if template.get("greeting"):
            lines.append(template["greeting"].format(name=result.name))
            lines.append("")

        # 基本信息
        lines.extend(self._format_summary(result))

        # 相似度详细信息（如果相似度 > 60%）
        if result.plagiarism_risk > 0.60 and result.similarity_details:
            lines.extend(self._format_similarity_details(result))

        # 根据风格添加不同部分
        sections = template.get("sections", [])

        if "scores" in sections and result.category_scores:
            lines.extend(self._format_scores(result))

        if "strengths" in sections and result.strengths:
            lines.extend(self._format_strengths(result))

        high_issues = [i for i in result.issues if i.severity in ['critical', 'high']]
        if "issues" in sections and high_issues:
            lines.extend(self._format_issues(result, high_issues))

        if "top_issues" in sections:
            lines.extend(self._format_top_issues(result))

        if "suggestions" in sections and result.suggestions:
            lines.extend(self._format_suggestions(result))

        if "quick_wins" in sections and result.quick_wins:
            lines.extend(self._format_quick_wins(result))

        if "learning_path" in sections and result.learning_path:
            lines.extend(self._format_learning_path(result))

        if "resources" in sections and result.resources:
            lines.extend(self._format_resources(result))

        if "encouragement" in sections:
            lines.extend(self._format_encouragement(result))

        # 页脚
        lines.extend([
            "---",
            "",
            f"*生成时间: {result.generated_at}*",
            f"*实验: {result.experiment_type}*",
            ""
        ])

        return '\n'.join(lines)

    def _format_summary(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化摘要"""
        lines = [
            "## 📋 评分摘要",
            "",
            f"| 项目 | 内容 |",
            f"|------|------|",
            f"| **学号** | {result.student_id} |",
            f"| **姓名** | {result.name} |",
            f"| **总分** | **{result.total_score}/{result.total_possible}** ({result.percentage:.1f}%) |",
            f"| **等级** | **{result.grade}** |",
        ]

        # 根据相似度阈值显示不同的警告
        if result.plagiarism_risk > 0.85:
            # 高于85%: 指出抄袭
            lines.append(f"| **⛔ 抄袭警告** | **检测到抄袭** ({result.plagiarism_risk*100:.1f}%) |")
        elif result.plagiarism_risk > 0.60:
            # 高于60%: 提醒
            lines.append(f"| **⚠️ 相似度提醒** | {result.plagiarism_risk*100:.1f}% |")

        lines.append("")
        return lines

    def _format_scores(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化得分详情"""
        lines = ["## 📊 各项得分", ""]

        for cat_id, score in result.category_scores.items():
            emoji = "✅" if score['percentage'] >= 80 else "⚠️" if score['percentage'] >= 60 else "❌"
            lines.append(f"### {emoji} {score['name']} ({score['earned']}/{score['possible']})")

            for fb in score['feedback']:
                lines.append(f"- {fb}")

            lines.append("")

        return lines

    def _format_strengths(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化亮点"""
        if not result.strengths:
            return []

        lines = ["## 🌟 亮点", ""]
        for strength in result.strengths[:5]:
            lines.append(f"- ✨ {strength}")
        lines.append("")
        return lines

    def _format_similarity_details(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化相似度详细信息"""
        lines = []

        # 根据相似度级别决定标题和内容
        if result.plagiarism_risk > 0.85:
            # 高于85%: 抄袭警告
            lines.append("## ⛔ 抄袭警告")
            lines.append("")
            lines.append(f"**您的报告与其他同学高度相似（最高相似度：{result.plagiarism_risk*100:.1f}%），系统检测为抄袭。**")
            lines.append("")
            lines.append("**与以下同学的报告高度相似：**")
        elif result.plagiarism_risk > 0.60:
            # 高于60%: 提醒
            lines.append("## ⚠️ 相似度提醒")
            lines.append("")
            lines.append(f"**您的报告与其他同学的相似度较高（最高相似度：{result.plagiarism_risk*100:.1f}%），请注意原创性。**")
            lines.append("")
            lines.append("**与以下同学的报告相似度较高：**")
        else:
            return []

        lines.append("")
        lines.append("| 学号 | 姓名 | 相似度 | 说明 |")
        lines.append("|------|------|--------|------|")

        for info in result.similarity_details:
            # 只显示相似度 > 60% 的
            if info.similarity > 60:
                group_info = "跨组" if info.is_cross_group else "同组"
                emoji = "🔴" if info.similarity > 85 else "🟠" if info.similarity > 70 else "🟡"
                lines.append(f"| {info.student_id} | {info.name} | {emoji} {info.similarity:.1f}% | {group_info} |")

        lines.append("")
        lines.append("**建议：**")
        if result.plagiarism_risk > 0.85:
            lines.append("- ⛔ **请立即确认是否为原创作品**")
            lines.append("- 如确属抄袭，请联系教师说明情况")
        else:
            lines.append("- 请确认是否为原创，避免过度参考同学报告")
            lines.append("- 建议使用自己的语言重新描述实验过程")
            lines.append("- 添加个人独特的思考和体会")
        lines.append("")
        lines.append("---")
        lines.append("")

        return lines

    def _format_issues(
        self,
        result: UnifiedFeedbackResult,
        issues: List[FeedbackIssue]
    ) -> List[str]:
        """格式化问题列表"""
        lines = ["## ⚠️ 需要改进的问题", ""]
        lines.append(f"发现 {len(issues)} 个需要优先解决的问题：")
        lines.append("")

        for i, issue in enumerate(issues, 1):
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue.severity, "📌")
            lines.append(f"### {emoji} {i}. {issue.title}")

            if issue.location:
                lines.append(f"**位置**: {issue.location}")
            lines.append(f"**问题**: {issue.description}")
            if issue.points_affected > 0:
                lines.append(f"**影响**: 约 {issue.points_affected} 分")
            if issue.fix_time:
                lines.append(f"**预计时间**: {issue.fix_time}")
            lines.append("")

        return lines

    def _format_top_issues(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化主要问题（简洁版）"""
        high_issues = [i for i in result.issues if i.severity in ['critical', 'high']]

        if not high_issues:
            return []

        lines = ["## ⚠️ 主要问题", ""]
        for issue in high_issues[:5]:
            lines.append(f"- **{issue.title}**: {issue.description}")
        lines.append("")
        return lines

    def _format_suggestions(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化改进建议"""
        lines = ["## 📝 详细改进建议", ""]

        for suggestion in result.get_high_priority_suggestions(5):
            issue = next((i for i in result.issues if i.id == suggestion.issue_id), None)
            if not issue:
                continue

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

            if suggestion.resources:
                lines.append("**学习资源**:")
                for name, link in suggestion.resources.items():
                    lines.append(f"- 📖 [{name}]({link})")
                lines.append("")

        return lines

    def _format_quick_wins(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化快速改进"""
        if not result.quick_wins:
            return []

        lines = ["## ⚡ 快速改进", ""]
        lines.append("这些改进简单但有效：")
        lines.append("")

        for win in result.quick_wins:
            lines.append(f"- ✓ **{win.title}** (+{win.points}分, {win.time})")
            lines.append(f"  - {win.description}")

        lines.append("")
        return lines

    def _format_learning_path(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化学习路径"""
        if not result.learning_path:
            return []

        lines = [
            "---",
            "",
            "## 🎯 学习路径",
            "",
            "根据您的情况，建议按以下顺序学习：",
            ""
        ]
        lines.extend(result.learning_path)
        lines.append("")
        return lines

    def _format_resources(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化资源推荐"""
        if not result.resources:
            return []

        lines = [
            "---",
            "",
            "## 📚 推荐资源",
            "",
            "| 资源 | 类型 | 说明 |",
            "|------|------|------|"
        ]

        for res in result.resources:
            type_icon = {"doc": "📄", "video": "🎥", "tutorial": "📖", "example": "💻"}.get(res.type, "🔗")
            lines.append(f"| {type_icon} [{res.name}]({res.path}) | {res.type} | {res.description} |")

        lines.append("")
        return lines

    def _format_encouragement(self, result: UnifiedFeedbackResult) -> List[str]:
        """格式化鼓励语"""
        lines = ["---", "", "## 💭 总结", ""]

        if result.percentage >= 90:
            lines.append("🎉 **优秀！** 您的实验报告质量很高，继续保持！")
        elif result.percentage >= 80:
            lines.append("👍 **良好！** 您的实验报告完成得不错，继续努力！")
        elif result.percentage >= 70:
            lines.append("📈 **中等！** 您的实验报告基本达标，仍有提升空间。")
        elif result.percentage >= 60:
            lines.append("📝 **及格！** 建议参考优秀同学报告，完善您的实验报告。")
        else:
            lines.append("💪 **加油！** 建议认真补充报告内容，下次争取更好成绩！")

        lines.extend(["", "---", ""])
        return lines

    def _format_html(self, result: UnifiedFeedbackResult, style: FeedbackStyle) -> str:
        """格式化为HTML"""
        # 简化版HTML生成，实际可扩展
        md_content = self._format_markdown(result, style)

        # 基础HTML模板
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>实验报告反馈 - {result.name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
        .score {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
        .grade {{ padding: 5px 15px; border-radius: 20px; background: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        {self._markdown_to_html(md_content)}
    </div>
</body>
</html>"""
        return html

    def _markdown_to_html(self, md: str) -> str:
        """简单的Markdown转HTML"""
        import re
        html = md

        # 标题
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

        # 粗体
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

        # 表格（简化处理）
        if '|' in html:
            lines = html.split('\n')
            in_table = False
            new_lines = []
            for line in lines:
                if '|' in line and '---' not in line:
                    if not in_table:
                        new_lines.append('<table>')
                        in_table = True
                    cells = [c.strip() for c in line.split('|')]
                    cells = [c for c in cells if c]  # 移除空
                    if cells:
                        tag = 'th' if '项目' in line or '------' in line else 'td'
                        new_lines.append('<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>')
                else:
                    if in_table:
                        new_lines.append('</table>')
                        in_table = False
                    new_lines.append(line)
            html = '\n'.join(new_lines)

        # 列表
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>\n)+', r'<ul>\g<0></ul>\n', html)

        # 代码块（简化）
        html = re.sub(r'```c\n(.*?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)

        # 段落
        html = re.sub(r'\n\n+', '</p><p>', html)
        html = '<p>' + html + '</p>'

        return html

    def _format_json(self, result: UnifiedFeedbackResult) -> str:
        """格式化为JSON"""
        import json
        data = {
            'student_id': result.student_id,
            'name': result.name,
            'scores': {
                'total': result.total_score,
                'possible': result.total_possible,
                'percentage': result.percentage,
                'grade': result.grade
            },
            'category_scores': result.category_scores,
            'issues': [
                {
                    'id': i.id,
                    'category': i.category,
                    'severity': i.severity,
                    'title': i.title,
                    'description': i.description,
                    'location': i.location,
                    'points_affected': i.points_affected,
                    'fix_time': i.fix_time
                }
                for i in result.issues
            ],
            'suggestions': [
                {
                    'issue_id': s.issue_id,
                    'priority': s.priority,
                    'action_steps': s.action_steps,
                    'expected_improvement': s.expected_improvement
                }
                for s in result.suggestions
            ],
            'quick_wins': [
                {'title': w.title, 'description': w.description, 'points': w.points, 'time': w.time}
                for w in result.quick_wins
            ],
            'strengths': result.strengths,
            'weaknesses': result.weaknesses,
            'learning_path': result.learning_path,
            'resources': [
                {'name': r.name, 'path': r.path, 'type': r.type, 'description': r.description}
                for r in result.resources
            ],
            'plagiarism_risk': result.plagiarism_risk,
            'generated_at': result.generated_at
        }
        return json.dumps(data, ensure_ascii=False, indent=2)


def save_unified_feedback(
    result: UnifiedFeedbackResult,
    output_dir: Path,
    generator: UnifiedFeedbackGenerator,
    style: FeedbackStyle = FeedbackStyle.DETAILED,
    format: FeedbackFormat = FeedbackFormat.MARKDOWN
) -> Path:
    """
    保存统一反馈到文件

    Args:
        result: 反馈结果
        output_dir: 输出目录
        generator: 反馈生成器
        style: 反馈风格
        format: 输出格式

    Returns:
        输出文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 根据格式选择子文件夹
    if format == FeedbackFormat.MARKDOWN:
        output_dir = output_dir / 'md'
    elif format == FeedbackFormat.HTML:
        output_dir = output_dir / 'html'
    elif format == FeedbackFormat.JSON:
        output_dir = output_dir / 'json'

    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成内容
    content = generator.format_feedback(result, style, format)

    # 确定文件名和扩展名
    safe_name = result.name.replace('/', '_').replace('\\', '_').replace(':', '_')
    ext_map = {
        FeedbackFormat.MARKDOWN: '.md',
        FeedbackFormat.HTML: '.html',
        FeedbackFormat.JSON: '.json'
    }

    ext = ext_map.get(format, '.md')
    style_suffix = f"_{style.value}" if style != FeedbackStyle.DETAILED else ""

    file_path = output_dir / f"{result.student_id}_{safe_name}{style_suffix}_反馈{ext}"

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return file_path


# 便捷函数
def generate_feedback(
    student_id: str,
    name: str,
    text: str,
    grading_result: Any,
    technical_result: Optional[Tuple] = None,
    plagiarism_risk: float = 0.0,
    resources_path: Optional[Path] = None,
    style: FeedbackStyle = FeedbackStyle.DETAILED,
    format: FeedbackFormat = FeedbackFormat.MARKDOWN
) -> UnifiedFeedbackResult:
    """
    生成反馈的便捷函数

    Args:
        student_id: 学号
        name: 姓名
        text: 报告文本
        grading_result: 评分结果
        technical_result: 技术检查结果
        plagiarism_risk: 抄袭风险
        resources_path: 资源文件路径
        style: 反馈风格
        format: 输出格式

    Returns:
        反馈结果
    """
    generator = UnifiedFeedbackGenerator(resources_path)
    result = generator.generate(
        student_id, name, text, grading_result,
        technical_result, plagiarism_risk, style, format
    )
    return result


# 导出
__all__ = [
    'FeedbackFormat',
    'FeedbackStyle',
    'SimilarityInfo',
    'UnifiedFeedbackResult',
    'UnifiedFeedbackGenerator',
    'save_unified_feedback',
    'generate_feedback'
]
