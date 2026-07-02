# -*- coding: utf-8 -*-
"""
增强评分模块
Enhanced Grading Module

集成NLP增强功能的评分系统
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from .enhanced_matcher import EnhancedKeywordMatcher, MatchMethod, MatchResult
from ..grading import (
    RubricGrader, GradingResult, CriterionScore,
    KeywordMatcher, CategoryScore
)


@dataclass
class EnhancedMatchDetail:
    """增强匹配详情"""
    criterion_id: str
    keyword: str
    matched: bool
    method: str
    confidence: float
    context: str = ""
    similarity: float = 0.0


@dataclass
class EnhancedGradingResult(GradingResult):
    """增强评分结果"""
    match_details: List[EnhancedMatchDetail] = field(default_factory=list)
    detected_obfuscation: List[str] = field(default_factory=list)
    nlp_confidence: float = 0.0


class EnhancedGradingMatcher(KeywordMatcher):
    """增强评分匹配器 - 使用NLP技术"""

    def __init__(self, fuzzy_threshold: float = 0.85):
        """
        初始化匹配器

        Args:
            fuzzy_threshold: 模糊匹配阈值
        """
        super().__init__()
        self.enhanced_matcher = EnhancedKeywordMatcher(
            use_fuzzy=True,
            use_variants=True,
            fuzzy_threshold=fuzzy_threshold,
            enable_jieba=True
        )

    def match_keywords(
        self,
        text: str,
        keywords: List[str]
    ) -> Tuple[List[str], float]:
        """
        匹配关键词（增强版）

        Args:
            text: 报告文本
            keywords: 关键词列表

        Returns:
            (匹配的关键词列表, 匹配比例)
        """
        # 使用增强匹配器
        results, match_ratio = self.enhanced_matcher.match_keywords(
            text, keywords, MatchMethod.HYBRID
        )

        matched = [r.keyword for r in results if r.matched]
        return matched, match_ratio

    def match_keywords_detailed(
        self,
        text: str,
        keywords: List[str],
        criterion_id: str = ""
    ) -> List[EnhancedMatchDetail]:
        """
        详细匹配关键词（返回更多信息）

        Args:
            text: 报告文本
            keywords: 关键词列表
            criterion_id: 评分标准ID

        Returns:
            详细匹配结果列表
        """
        results, _ = self.enhanced_matcher.match_keywords(
            text, keywords, MatchMethod.HYBRID
        )

        details = []
        for r in results:
            context = self.enhanced_matcher.extract_context(
                text, r.keyword, context_size=30
            )

            details.append(EnhancedMatchDetail(
                criterion_id=criterion_id,
                keyword=r.keyword,
                matched=r.matched,
                method=r.method.value,
                confidence=r.confidence,
                context=context,
                similarity=r.similarity
            ))

        return details


class EnhancedRubricGrader(RubricGrader):
    """增强版Rubric评分器 - 集成NLP功能"""

    def __init__(self, rubric: Dict, fuzzy_threshold: float = 0.85):
        """
        初始化评分器

        Args:
            rubric: 评分标准数据
            fuzzy_threshold: 模糊匹配阈值
        """
        super().__init__(rubric)
        self.enhanced_matcher = EnhancedGradingMatcher(fuzzy_threshold)
        self.all_match_details: List[EnhancedMatchDetail] = []

    def grade(
        self,
        student_id: str,
        name: str,
        text: str,
        return_details: bool = False
    ) -> EnhancedGradingResult:
        """
        评估学生报告（增强版）

        Args:
            student_id: 学号
            name: 姓名
            text: 报告文本
            return_details: 是否返回详细匹配信息

        Returns:
            增强评分结果
        """
        # 清空之前的详情
        self.all_match_details = []

        # 使用父类的基础评分
        base_result = super().grade(student_id, name, text)

        # 转换为增强结果
        enhanced_result = EnhancedGradingResult(
            student_id=base_result.student_id,
            name=base_result.name,
            total_score=base_result.total_score,
            total_possible=base_result.total_possible,
            percentage=base_result.percentage,
            grade=base_result.grade,
            category_scores=base_result.category_scores,
            strengths=base_result.strengths,
            weaknesses=base_result.weaknesses,
            recommendations=base_result.recommendations,
            detailed_feedback=base_result.detailed_feedback,
            auto_confidence=base_result.auto_confidence,
            match_details=self.all_match_details if return_details else [],
            nlp_confidence=self._calculate_nlp_confidence(text)
        )

        return enhanced_result

    def _grade_criterion(
        self,
        criterion: Dict,
        content: str,
        full_text: str
    ) -> CriterionScore:
        """评估单个标准（增强版）"""
        criterion_id = criterion.get('id', '')
        description = criterion['description']
        points = criterion['points']
        keywords = criterion.get('keywords', [])

        # 使用增强匹配器
        matched, match_ratio = self.enhanced_matcher.match_keywords(
            full_text, keywords
        )

        # 收集详细匹配信息
        details = self.enhanced_matcher.match_keywords_detailed(
            full_text, keywords, criterion_id
        )
        self.all_match_details.extend(details)

        # 根据匹配比例和置信度计算得分
        confidence = sum(d.confidence for d in details if d.matched) / len(details) if details else 0

        # 综合匹配比例和置信度
        effective_ratio = (match_ratio + confidence) / 2

        if effective_ratio >= 0.8:
            earned = points
        elif effective_ratio >= 0.5:
            earned = points * 0.6
        elif effective_ratio >= 0.2:
            earned = points * 0.3
        else:
            earned = 0

        return CriterionScore(
            criterion_id=criterion_id,
            description=description,
            points_earned=earned,
            points_possible=points,
            matched_keywords=matched,
            feedback=f"匹配关键词: {', '.join(matched)} (置信度: {confidence:.1f})" if matched else "未找到关键词"
        )

    def _calculate_nlp_confidence(self, text: str) -> float:
        """计算NLP置信度"""
        # 基于匹配详情的置信度
        if not self.all_match_details:
            return 0.5

        matched_count = sum(1 for d in self.all_match_details if d.matched)
        total_count = len(self.all_match_details)

        base_confidence = matched_count / total_count if total_count > 0 else 0

        # 根据匹配方法调整
        fuzzy_matches = sum(1 for d in self.all_match_details
                          if d.matched and d.method == 'fuzzy')
        fuzzy_bonus = (fuzzy_matches / total_count) * 0.1 if total_count > 0 else 0

        return min(base_confidence + fuzzy_bonus, 0.95)

    def get_match_summary(self) -> Dict[str, any]:
        """获取匹配摘要统计"""
        if not self.all_match_details:
            return {}

        matched = [d for d in self.all_match_details if d.matched]
        unmatched = [d for d in self.all_match_details if not d.matched]

        method_counts = {}
        for d in matched:
            method_counts[d.method] = method_counts.get(d.method, 0) + 1

        return {
            'total_keywords': len(self.all_match_details),
            'matched_count': len(matched),
            'unmatched_count': len(unmatched),
            'match_rate': len(matched) / len(self.all_match_details) if self.all_match_details else 0,
            'method_distribution': method_counts,
            'average_confidence': sum(d.confidence for d in matched) / len(matched) if matched else 0
        }


def enhance_grading_system(
    rubric: Dict,
    fuzzy_threshold: float = 0.85
) -> EnhancedRubricGrader:
    """
    创建增强评分系统（便捷函数）

    Args:
        rubric: 评分标准
        fuzzy_threshold: 模糊匹配阈值

    Returns:
        增强评分器
    """
    return EnhancedRubricGrader(rubric, fuzzy_threshold)
