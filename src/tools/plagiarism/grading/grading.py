#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于 Rubric 的评分引擎
Rubric-Based Grading Engine

根据实验评分标准（rubric.json）自动评估学生实验报告
"""

import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class CriterionScore:
    """单个评分标准得分"""
    criterion_id: str
    description: str
    points_earned: float
    points_possible: float
    matched_keywords: List[str] = field(default_factory=list)
    missing_keywords: List[str] = field(default_factory=list)
    feedback: str = ""


@dataclass
class CategoryScore:
    """评分类别得分"""
    category_id: str
    name: str
    points_earned: float
    points_possible: float
    percentage: float
    criteria_scores: List[CriterionScore] = field(default_factory=list)
    feedback: List[str] = field(default_factory=list)


@dataclass
class PlagiarismInfo:
    """抄袭相关信息"""
    max_similarity: float = 0.0           # 最高相似度 0-100
    similar_to: Optional[str] = None     # 与谁相似
    is_cross_group: bool = False         # 是否跨组
    penalty_applied: float = 0.0         # 已扣分数
    risk_level: str = "none"             # 'none', 'warning', 'severe', 'critical'
    shared_count: int = 0                # 共享段落数


@dataclass
class GradingResult:
    """完整评分结果"""
    student_id: str
    name: str
    total_score: float
    total_possible: float
    percentage: float
    grade: str
    category_scores: Dict[str, CategoryScore]
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    detailed_feedback: str = ""
    auto_confidence: float = 0.85  # 自动评分置信度
    # 新增字段：按组提交评分
    is_team_leader: bool = False
    experience_quality: str = ""  # 'missing', 'poor', 'fair', 'good'
    attitude_adjustment: float = 0.0
    # v2.6.0 新增：抄袭相关信息
    plagiarism_info: PlagiarismInfo = field(default_factory=PlagiarismInfo)
    original_score: float = 0.0    # 抄袭扣分前的原始分数


class RubricLoader:
    """加载评分标准"""

    @staticmethod
    def load(rubric_path: Path) -> Dict:
        """
        加载 rubric.json 文件

        Args:
            rubric_path: rubric 文件路径

        Returns:
            rubric 数据字典
        """
        if not rubric_path.exists():
            # 返回默认 rubric
            return RubricLoader.get_default_rubric()

        with open(rubric_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def get_default_rubric() -> Dict:
        """获取默认评分标准"""
        return {
            "experiment_name": "实验报告",
            "total_points": 100,
            "grading_scale": {
                "A": {"min": 90, "max": 100, "label": "优"},
                "B": {"min": 80, "max": 89, "label": "良"},
                "C": {"min": 70, "max": 79, "label": "中"},
                "D": {"min": 60, "max": 69, "label": "及格"},
                "F": {"min": 0, "max": 59, "label": "不及格"}
            },
            "categories": []
        }


class KeywordMatcher:
    """关键词匹配器"""

    def __init__(self, enable_nlp: bool = True):
        """
        初始化匹配器

        Args:
            enable_nlp: 是否启用NLP增强匹配
        """
        self.enable_nlp = enable_nlp
        self.enhanced_matcher = None

        if enable_nlp:
            try:
                from .nlp.enhanced_matcher import EnhancedKeywordMatcher
                self.enhanced_matcher = EnhancedKeywordMatcher(
                    use_fuzzy=True,
                    use_variants=True,
                    fuzzy_threshold=0.85
                )
            except ImportError:
                # NLP模块不可用，使用传统方法
                self.enable_nlp = False

    def match_keywords(self, text: str, keywords: List[str]) -> Tuple[List[str], float]:
        """
        匹配关键词

        Args:
            text: 报告文本
            keywords: 关键词列表

        Returns:
            (匹配的关键词列表, 匹配比例)
        """
        # 使用NLP增强匹配器
        if self.enable_nlp and self.enhanced_matcher:
            try:
                from .nlp.enhanced_matcher import MatchMethod
                results, ratio = self.enhanced_matcher.match_keywords(
                    text, keywords, MatchMethod.HYBRID
                )
                matched = [r.keyword for r in results if r.matched]
                return matched, ratio
            except Exception:
                # NLP匹配失败，回退到传统方法
                pass

        # 传统匹配方法（后备）
        text_lower = text.lower()
        matched = []

        for keyword in keywords:
            if keyword.lower() in text_lower:
                matched.append(keyword)

        match_ratio = len(matched) / len(keywords) if keywords else 0
        return matched, match_ratio


class SectionDetector:
    """章节检测器"""

    # 章节标题模式
    SECTION_PATTERNS = [
        r'^[一二三四五六七八九十]+[、．.]\s*(.+)$',
        r'^\d+[、．.]\s*(.+)$',
        r'^(\d+)\.\s*(.+)$',
        r'^#{1,3}\s*(.+)$',
        r'^\[([一二三四五六七八九十]+)\]\s*(.+)$',
    ]

    @staticmethod
    def detect_sections(text: str) -> Dict[str, str]:
        """
        检测报告章节

        Args:
            text: 报告文本

        Returns:
            {章节名称: 内容}
        """
        sections = {}
        lines = text.split('\n')

        current_section = "其他"
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否是章节标题
            is_section = False
            section_name = None

            for pattern in SectionDetector.SECTION_PATTERNS:
                match = re.match(pattern, line)
                if match:
                    section_name = match.group(1) if match.groups() else line
                    is_section = True
                    break

            if is_section:
                # 保存上一个章节
                if current_content:
                    sections[current_section] = '\n'.join(current_content)

                current_section = section_name
                current_content = []
            else:
                current_content.append(line)

        # 保存最后一个章节
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    @staticmethod
    def find_section_content(text: str, section_keywords: List[str]) -> Optional[str]:
        """
        查找包含特定关键词的章节内容

        Args:
            text: 报告文本
            section_keywords: 章节关键词列表

        Returns:
            章节内容或 None
        """
        sections = SectionDetector.detect_sections(text)

        for section_name, content in sections.items():
            for keyword in section_keywords:
                if keyword in section_name:
                    return content

        return None


class RubricGrader:
    """基于 Rubric 的评分器"""

    def __init__(self, rubric: Dict, enable_nlp: bool = True):
        """
        初始化评分器

        Args:
            rubric: 评分标准数据
            enable_nlp: 是否启用NLP增强匹配
        """
        self.rubric = rubric
        self.experiment_name = rubric.get('experiment_name', '实验')
        self.total_points = rubric.get('total_points', 100)
        self.grading_scale = rubric.get('grading_scale', {})
        self.categories = rubric.get('categories', [])
        self.enable_nlp = enable_nlp

        # 初始化关键词匹配器
        self.keyword_matcher = KeywordMatcher(enable_nlp=enable_nlp)

        # 加载期校验评分标准一致性（仅记录 ERROR，不阻断评分）
        self._validate_rubric_quietly()

    def _validate_rubric_quietly(self):
        """用 GradingValidator 校验 rubric，仅对 ERROR 级问题记日志。"""
        try:
            from .grading_validator import GradingValidator, ValidationSeverity
            for iss in GradingValidator.validate_rubric(self.rubric):
                if iss.severity == ValidationSeverity.ERROR:
                    logger.warning("评分标准校验失败 [%s] %s", iss.category, iss.message)
        except Exception:
            logger.debug("评分标准校验跳过", exc_info=True)

    def grade(self, student_id: str, name: str, text: str, is_leader: bool = False, experience_info: dict = None) -> GradingResult:
        """
        评估学生报告

        Args:
            student_id: 学号
            name: 姓名
            text: 报告文本
            is_leader: 是否是组长
            experience_info: 心得体会信息

        Returns:
            评分结果
        """
        category_scores = {}
        total_earned = 0.0
        all_strengths = []
        all_weaknesses = []
        all_recommendations = []

        # 检测章节
        sections = SectionDetector.detect_sections(text)

        # 评估每个类别
        for category in self.categories:
            category_id = category['id']
            category_name = category['name']
            category_points = category['points']

            # 跳过条件类别（如组长加分），在后面处理
            if category.get('conditional', False):
                continue

            # 获取对应的章节内容
            source_section = category.get('source_section', '')
            section_content = self._find_section_content(sections, source_section)

            # 如果没找到对应章节，使用全文
            if not section_content:
                section_content = text

            category_score = self._grade_category(
                category, section_content, text
            )

            category_scores[category_id] = category_score
            total_earned += category_score.points_earned

            # 收集反馈
            all_strengths.extend([
                f"{category_name}: {fb}" for fb in category_score.feedback
                if "正确" in fb or "完整" in fb or "详细" in fb
            ])
            all_weaknesses.extend([
                f"{category_name}: {fb}" for fb in category_score.feedback
                if "缺少" in fb or "不足" in fb or "错误" in fb
            ])

        # 处理组长加分
        attitude_adjustment = 0.0
        if is_leader:
            # 查找组长加分类别
            leader_category = next((c for c in self.categories if c.get('id') == 'team_leader_bonus'), None)
            if leader_category:
                leader_score = CategoryScore(
                    category_id='team_leader_bonus',
                    name='组长加分',
                    points_earned=5.0,
                    points_possible=5.0,
                    percentage=100.0,
                    criteria_scores=[],
                    feedback=['✓ 担任组长，加5分']
                )
                category_scores['team_leader_bonus'] = leader_score
                total_earned += 5
                all_strengths.append('组长加分: 担任组长')

        # 根据心得体会调整态度得分
        if experience_info and 'attitude' in category_scores:
            quality = experience_info.get('quality', 'fair')
            adjustment_rules = {
                'missing': -3,
                'poor': -2,
                'fair': 0,
                'good': 1
            }
            attitude_adjustment = adjustment_rules.get(quality, 0)

            # 应用调整
            attitude_score = category_scores['attitude']
            old_points = attitude_score.points_earned
            adjusted = max(0, min(10, attitude_score.points_earned + attitude_adjustment))
            attitude_score.points_earned = adjusted
            total_earned += (adjusted - old_points)
            attitude_score.percentage = (adjusted / attitude_score.points_possible * 100) if attitude_score.points_possible > 0 else 0

            # 添加反馈说明
            if attitude_adjustment < 0:
                all_weaknesses.append(f'实验态度: 心得体会{quality}，扣{abs(attitude_adjustment)}分')
            elif attitude_adjustment > 0:
                all_strengths.append(f'实验态度: 心得体会{quality}，加{attitude_adjustment}分')

            # 更新反馈列表
            if attitude_adjustment != 0:
                attitude_score.feedback.append(f'△ 心得体会调整: {attitude_adjustment:+.0f}分')

        # 计算总分和等级
        percentage = (total_earned / self.total_points * 100) if self.total_points > 0 else 0
        grade = self._calculate_grade(percentage)

        # 生成详细反馈
        detailed_feedback = self._generate_feedback(
            category_scores, total_earned, self.total_points
        )

        return GradingResult(
            student_id=student_id,
            name=name,
            total_score=round(total_earned, 1),
            total_possible=self.total_points,
            percentage=round(percentage, 1),
            grade=grade,
            category_scores=category_scores,
            strengths=all_strengths,
            weaknesses=all_weaknesses,
            recommendations=all_recommendations,
            detailed_feedback=detailed_feedback,
            is_team_leader=is_leader,
            experience_quality=experience_info.get('quality', '') if experience_info else '',
            attitude_adjustment=attitude_adjustment
        )

    def _find_section_content(self, sections: Dict, source_hint: str) -> str:
        """根据提示查找章节内容"""
        # 直接匹配
        if source_hint in sections:
            return sections[source_hint]

        # 关键词匹配
        for section_name, content in sections.items():
            if any(keyword in section_name for keyword in source_hint.split()):
                return content

        return ""

    def _grade_category(
        self,
        category: Dict,
        content: str,
        full_text: str
    ) -> CategoryScore:
        """评估单个类别"""
        category_id = category['id']
        category_name = category['name']
        category_points = category['points']
        criteria = category.get('criteria', [])
        is_manual = category.get('manual_evaluation', False)

        criteria_scores = []
        category_earned = 0.0
        feedback = []

        # 手动评分类别（如实验态度）：从配置读取默认分
        if is_manual:
            default_score = category.get('default_points', 6.0)  # 从配置读取，默认6分
            category_earned = min(default_score, category_points)  # 不超过满分
            feedback.append(f"📝 教师评定（默认{default_score}分，可手动调整）")
            feedback.append(f"  - 全勤：10分")
            feedback.append(f"  - 缺勤1次：5分")
            feedback.append(f"  - 缺勤2次及以上：0分")
        else:
            # 自动评分类别：根据关键词匹配
            for criterion in criteria:
                criterion_score = self._grade_criterion(criterion, content, full_text)
                criteria_scores.append(criterion_score)
                category_earned += criterion_score.points_earned

                # 生成反馈
                if criterion_score.points_earned == criterion['points']:
                    feedback.append(f"✓ {criterion['description']}")
                elif criterion_score.points_earned > 0:
                    feedback.append(f"△ {criterion['description']} (部分)")
                else:
                    feedback.append(f"✗ {criterion['description']}")

        percentage = (category_earned / category_points * 100) if category_points > 0 else 0

        return CategoryScore(
            category_id=category_id,
            name=category_name,
            points_earned=round(category_earned, 1),
            points_possible=category_points,
            percentage=round(percentage, 1),
            criteria_scores=criteria_scores,
            feedback=feedback
        )

    def _grade_criterion(
        self,
        criterion: Dict,
        content: str,
        full_text: str
    ) -> CriterionScore:
        """评估单个标准"""
        criterion_id = criterion.get('id', '')
        description = criterion['description']
        points = criterion['points']
        keywords = criterion.get('keywords', [])

        # 在内容中查找关键词
        matched, match_ratio = self.keyword_matcher.match_keywords(content, keywords)

        # 如果在指定章节没找到，尝试在全文中查找
        if not matched and keywords:
            matched, match_ratio = self.keyword_matcher.match_keywords(full_text, keywords)

        # 未命中的关键词（用于直击式反馈：告诉学生具体缺什么）
        matched_set = set(matched)
        missing = [kw for kw in keywords if kw not in matched_set]

        # 根据匹配比例计算得分
        if match_ratio >= 0.8:
            earned = points
        elif match_ratio >= 0.5:
            earned = points * 0.6
        elif match_ratio >= 0.2:
            earned = points * 0.3
        else:
            earned = 0

        return CriterionScore(
            criterion_id=criterion_id,
            description=description,
            points_earned=earned,
            points_possible=points,
            matched_keywords=matched,
            missing_keywords=missing,
            feedback=f"匹配关键词: {', '.join(matched)}" if matched else "未找到关键词"
        )

    def _calculate_grade(self, percentage: float) -> str:
        """根据百分比计算等级

        半开区间匹配（按 min 降序，取首个 min <= percentage 的档），
        消除闭区间下 B.max=89.9 / A.min=90 之类的边界缝隙导致 89.95 落到 F 的问题。
        """
        for grade, scale in sorted(self.grading_scale.items(), key=lambda x: x[1]['min'], reverse=True):
            if percentage >= scale['min']:
                return grade
        return 'F'

    def _generate_feedback(
        self,
        category_scores: Dict[str, CategoryScore],
        total_earned: float,
        total_possible: float
    ) -> str:
        """生成详细反馈"""
        lines = [
            f"# {self.experiment_name} 评分反馈",
            "",
            f"**总分**: {total_earned}/{total_possible} ({total_earned/total_possible*100:.1f}%)",
            "",
            "## 各项得分"
        ]

        for category_id, score in category_scores.items():
            lines.append(f"\n### {score.name} ({score.points_earned}/{score.points_possible})")

            for feedback in score.feedback:
                lines.append(f"- {feedback}")

        return '\n'.join(lines)


class EnhancedRubricGrader(RubricGrader):
    """增强版 Rubric 评分器"""

    def grade(self, student_id: str, name: str, text: str, is_leader: bool = False, experience_info: dict = None) -> GradingResult:
        """增强评估

        签名与父类 RubricGrader.grade 保持一致（is_leader/experience_info 透传），
        以便 batch_grade 能在 RubricGrader / EnhancedRubricGrader 之间无差别替换，
        避免因签名收窄导致的调用方 TypeError。
        """
        result = super().grade(student_id, name, text, is_leader=is_leader, experience_info=experience_info)

        # 增强反馈
        result.recommendations = self._generate_recommendations(result, text)

        # 计算自动评分置信度
        result.auto_confidence = self._calculate_confidence(result, text)

        return result

    def _generate_recommendations(self, result: GradingResult, text: str) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 基于薄弱项生成建议
        for category_id, score in result.category_scores.items():
            if score.percentage < 60:
                recommendations.append(f"【{score.name}】需要加强，请补充相关内容")

        # 检查字数
        char_count = len(re.sub(r'\s', '', text))
        if char_count < 500:
            recommendations.append("报告内容偏少，建议增加详细说明")

        # 检查图表
        if not re.search(r'图|表|截图|照片', text):
            recommendations.append("建议添加图表或截图来说明实验结果")

        # 检查代码
        if not re.search(r'代码|程序|函数|HAL_|GPIO', text):
            recommendations.append("请补充关键代码说明")

        return recommendations

    def _calculate_confidence(self, result: GradingResult, text: str) -> float:
        """计算自动评分置信度"""
        confidence = 0.85  # 基础置信度

        # 根据报告质量调整
        char_count = len(re.sub(r'\s', '', text))
        if char_count < 300:
            confidence -= 0.2  # 内容太少，降低置信度
        elif char_count > 1000:
            confidence += 0.05  # 内容充分，提高置信度

        # 根据得分分布调整
        if result.percentage > 90 or result.percentage < 30:
            confidence -= 0.1  # 极端分数需要人工复核

        return max(0.5, min(confidence, 0.95))


def load_rubric_for_experiment(
    experiment_type: str,
    base_dir: Path = None
) -> Dict:
    """
    为指定实验类型加载评分标准

    Args:
        experiment_type: 实验类型（如 '07_car_gear_experiment'）
        base_dir: 基础目录

    Returns:
        rubric 数据
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent.parent.parent / 'data/rubrics'

    rubric_file = base_dir / 'rubric.json'

    if rubric_file.exists():
        return RubricLoader.load(rubric_file)

    return RubricLoader.get_default_rubric()


def batch_grade(
    submissions: Dict[str, Dict],
    rubric: Dict,
    experiment_type: str = '档位实验',
    enable_nlp: bool = True
) -> List[GradingResult]:
    """
    批量评分

    Args:
        submissions: 提交内容 {学号: {name, text, is_leader?, experience?}}
        rubric: 评分标准
        experiment_type: 实验类型
        enable_nlp: 是否启用NLP增强

    Returns:
        评分结果列表
    """
    # 按 enable_nlp 选择评分器（旧实现用 hasattr(RubricGrader,'__init__') 判断，恒为 True，
    # 导致永远选中 EnhancedRubricGrader 并丢弃 enable_nlp）。
    grader = EnhancedRubricGrader(rubric) if enable_nlp else RubricGrader(rubric, enable_nlp=False)
    results = []

    for student_id, submission in submissions.items():
        name = submission.get('name', '')
        text = submission.get('text', '')
        is_leader = submission.get('is_leader', False)
        experience_info = submission.get('experience')

        if not text:
            # 未提交
            result = GradingResult(
                student_id=student_id,
                name=name,
                total_score=0.0,
                total_possible=rubric.get('total_points', 100),
                percentage=0.0,
                grade='F',
                category_scores={},
                strengths=[],
                weaknesses=['未提交报告'],
                recommendations=['请尽快提交实验报告'],
                detailed_feedback="未提交报告",
                auto_confidence=1.0,
                is_team_leader=is_leader,
                experience_quality=experience_info.get('quality', '') if experience_info else '',
                attitude_adjustment=0.0
            )
            results.append(result)
            continue

        result = grader.grade(student_id, name, text, is_leader, experience_info)
        results.append(result)

    return results


# ============================================
# v2.6.0 新增: 抄袭自动扣分机制
# ============================================

@dataclass
class PlagiarismThresholds:
    """抄袭扣分阈值配置"""
    warning: float = 80.0      # 警告阈值
    severe: float = 85.0       # 严重阈值
    critical: float = 90.0     # 临界阈值（零分）

    # 扣分规则
    warning_penalty: float = 10.0     # 警告扣分
    severe_penalty: float = 30.0      # 严重扣分
    critical_penalty: float = 100.0   # 临界扣分（记0分）


def apply_plagiarism_penalty(
    result: GradingResult,
    similarity_info: dict,
    thresholds: PlagiarismThresholds = None,
    grading_scale: Dict[str, Dict] = None
) -> GradingResult:
    """
    根据相似度自动扣分

    扣分规则:
    - 80-85%相似：扣10分
    - 85-90%相似：扣30分
    - 90%以上：记0分

    Args:
        result: 评分结果（将被修改）
        similarity_info: 相似度信息
            {
                'max_similarity': float,  # 最高相似度
                'similar_to': str,        # 与谁相似
                'is_cross_group': bool,   # 是否跨组
                'shared_count': int       # 共享段落数
            }
        thresholds: 阈值配置（可选）

    Returns:
        修改后的评分结果
    """
    if thresholds is None:
        thresholds = PlagiarismThresholds()

    # grading_scale 作为显式入参；未传入时回退到 result 上注入的属性
    # （batch_grade_with_plagiarism_check 仍会注入），再退到 None（由
    # _calculate_grade_from_percentage 用默认 scale）。旧实现直接读 result.grading_scale，
    # 独立调用时该属性不存在 → AttributeError。
    if grading_scale is None:
        grading_scale = getattr(result, 'grading_scale', None)

    max_sim = similarity_info.get('max_similarity', 0.0)
    similar_to = similarity_info.get('similar_to', '')
    is_cross_group = similarity_info.get('is_cross_group', False)
    shared_count = similarity_info.get('shared_count', 0)

    # 保存原始分数
    result.original_score = result.total_score

    # 确定风险等级和扣分
    penalty = 0.0
    risk_level = "none"

    if max_sim >= thresholds.critical:
        penalty = thresholds.critical_penalty
        risk_level = "critical"
        result.total_score = 0
        result.grade = 'F'
        result.weaknesses.append(
            f"🚨 严重抄袭: 与 {similar_to} 相似度 {max_sim:.1f}%，记0分"
        )
    elif max_sim >= thresholds.severe:
        penalty = thresholds.severe_penalty
        risk_level = "severe"
        result.total_score = max(0, result.total_score - penalty)
        # 重新计算等级
        result.percentage = (result.total_score / result.total_possible * 100) if result.total_possible > 0 else 0
        result.grade = _calculate_grade_from_percentage(result.percentage, grading_scale)
        result.weaknesses.append(
            f"⚠️ 高度相似: 与 {similar_to} 相似度 {max_sim:.1f}%，扣{penalty:.0f}分"
        )
    elif max_sim >= thresholds.warning:
        penalty = thresholds.warning_penalty
        risk_level = "warning"
        result.total_score = max(0, result.total_score - penalty)
        result.percentage = (result.total_score / result.total_possible * 100) if result.total_possible > 0 else 0
        result.grade = _calculate_grade_from_percentage(result.percentage, grading_scale)
        result.weaknesses.append(
            f"⚡ 相似度警告: 与 {similar_to} 相似度 {max_sim:.1f}%，扣{penalty:.0f}分"
        )
    elif is_cross_group and max_sim >= 70:
        # 跨组且相似度较高，轻度扣分
        penalty = 5.0
        risk_level = "warning"
        result.total_score = max(0, result.total_score - penalty)
        result.percentage = (result.total_score / result.total_possible * 100) if result.total_possible > 0 else 0
        result.grade = _calculate_grade_from_percentage(result.percentage, grading_scale)
        result.weaknesses.append(
            f"🔍 跨组相似: 与 {similar_to} 相似度 {max_sim:.1f}%，扣{penalty:.0f}分"
        )

    # 更新抄袭信息
    result.plagiarism_info = PlagiarismInfo(
        max_similarity=max_sim,
        similar_to=similar_to,
        is_cross_group=is_cross_group,
        penalty_applied=penalty,
        risk_level=risk_level,
        shared_count=shared_count
    )

    # 如果有扣分，降低自动评分置信度
    if penalty > 0:
        result.auto_confidence = max(0.5, result.auto_confidence - 0.15)

    return result


def _calculate_grade_from_percentage(percentage: float, grading_scale: Dict[str, Dict] = None) -> str:
    """根据百分比计算等级"""
    if grading_scale is None:
        grading_scale = {
            'A': {'min': 90, 'max': 100},
            'B': {'min': 80, 'max': 89},
            'C': {'min': 70, 'max': 79},
            'D': {'min': 60, 'max': 69},
            'F': {'min': 0, 'max': 59}
        }

    for grade, scale in sorted(grading_scale.items(), key=lambda x: x[1]['min'], reverse=True):
        if percentage >= scale['min']:
            return grade
    return 'F'


def batch_grade_with_plagiarism_check(
    submissions: Dict[str, Dict],
    rubric: Dict,
    experiment_type: str = '档位实验',
    enable_nlp: bool = True,
    enable_plagiarism_check: bool = True,
    plagiarism_thresholds: PlagiarismThresholds = None,
    group_info: Dict[str, str] = None
) -> List[GradingResult]:
    """
    批量评分（含抄袭检测）

    Args:
        submissions: 提交内容 {学号: {name, text, is_leader?, experience?}}
        rubric: 评分标准
        experiment_type: 实验类型
        enable_nlp: 是否启用NLP增强
        enable_plagiarism_check: 是否启用抄袭检测
        plagiarism_thresholds: 抄袭阈值配置
        group_info: 小组信息 {学号: 小组号}

    Returns:
        评分结果列表（含抄袭扣分）
    """
    # 先执行基础评分
    results = batch_grade(submissions, rubric, experiment_type, enable_nlp)

    # 添加 grading_scale 到结果中（用于等级计算）
    grading_scale = rubric.get('grading_scale', {})
    for result in results:
        result.grading_scale = grading_scale

    if not enable_plagiarism_check:
        return results

    # 执行抄袭检测
    try:
        from tools.plagiarism.core import PlagiarismDetector, SimilarityMethod
        from tools.plagiarism.utils.config import PlagiarismConfig, ThresholdConfig, SimilarityWeights

        # 创建检测器
        config = PlagiarismConfig(
            weights=SimilarityWeights(text=0.5, code=0.3, structure=0.1, semantic=0.1),
            thresholds=ThresholdConfig(
                suspicious=60.0,
                high_similarity=70.0,
                plagiarism=85.0
            ),
            group_info=group_info or {}
        )

        detector = PlagiarismDetector(
            method=SimilarityMethod.HYBRID,
            threshold=60.0,
            config=config,
            enable_adaptive_threshold=False
        )

        # 执行检测
        all_results, suspicious, _ = detector.detect(submissions)

        # 对每个学生应用抄袭扣分
        for result in results:
            student_id = result.student_id

            # 找到该学生的最高相似度
            max_sim = 0.0
            similar_to = ""
            is_cross_group = False
            shared_count = 0

            for sim_result in all_results.get(student_id, []):
                if sim_result.overall_similarity > max_sim:
                    max_sim = sim_result.overall_similarity
                    similar_to = sim_result.similar_to
                    is_cross_group = sim_result.is_cross_group
                    shared_count = len(sim_result.shared_paragraphs)

            # 如果有高相似度，应用扣分
            if max_sim >= 70 or is_cross_group:
                similarity_info = {
                    'max_similarity': max_sim,
                    'similar_to': similar_to,
                    'is_cross_group': is_cross_group,
                    'shared_count': shared_count
                }
                apply_plagiarism_penalty(result, similarity_info, plagiarism_thresholds)

    except Exception as e:
        print(f"[警告] 抄袭检测失败: {e}")
        # 继续返回基础评分结果

    return results
