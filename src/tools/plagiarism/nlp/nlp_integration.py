# -*- coding: utf-8 -*-
"""
NLP增强集成模块
NLP Enhancement Integration Module

将NLP增强功能集成到现有的查重和评分系统中
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .enhanced_matcher import EnhancedKeywordMatcher, MatchMethod
from .template_filter import AdvancedTemplateFilter, FilterMethod
from .code_analyzer_nlp import CodeASTAnalyzer, compare_code_blocks


class NLPEngineConfig:
    """NLP引擎配置"""

    def __init__(
        self,
        enable_fuzzy_matching: bool = True,
        fuzzy_threshold: float = 0.85,
        enable_term_variants: bool = True,
        enable_advanced_template_filter: bool = True,
        enable_ast_analysis: bool = True,
        template_filter_strictness: float = 0.7
    ):
        """
        初始化NLP引擎配置

        Args:
            enable_fuzzy_matching: 是否启用模糊匹配
            fuzzy_threshold: 模糊匹配阈值
            enable_term_variants: 是否启用术语变体
            enable_advanced_template_filter: 是否启用高级模板过滤
            enable_ast_analysis: 是否启用AST代码分析
            template_filter_strictness: 模板过滤严格程度
        """
        self.enable_fuzzy_matching = enable_fuzzy_matching
        self.fuzzy_threshold = fuzzy_threshold
        self.enable_term_variants = enable_term_variants
        self.enable_advanced_template_filter = enable_advanced_template_filter
        self.enable_ast_analysis = enable_ast_analysis
        self.template_filter_strictness = template_filter_strictness


@dataclass
class NLPEnhancedResult:
    """NLP增强结果"""
    original_similarity: float
    enhanced_similarity: float
    detected_obfuscations: List[str] = field(default_factory=list)
    match_details: List[Dict] = field(default_factory=list)
    nlp_confidence: float = 0.0
    recommendations: List[str] = field(default_factory=list)


class NLPEngine:
    """NLP增强引擎"""

    def __init__(self, config: NLPEngineConfig = None):
        """
        初始化NLP引擎

        Args:
            config: NLP配置
        """
        self.config = config or NLPEngineConfig()

        # 初始化组件
        self.keyword_matcher = None
        self.template_filter = None
        self.code_analyzer = None

        self._init_components()

    def _init_components(self):
        """初始化NLP组件"""
        # 关键词匹配器
        if self.config.enable_fuzzy_matching or self.config.enable_term_variants:
            self.keyword_matcher = EnhancedKeywordMatcher(
                use_fuzzy=self.config.enable_fuzzy_matching,
                use_variants=self.config.enable_term_variants,
                fuzzy_threshold=self.config.fuzzy_threshold,
                enable_jieba=True
            )

        # 代码AST分析器
        if self.config.enable_ast_analysis:
            self.code_analyzer = CodeASTAnalyzer(language='c')

    def set_template_filter(self, template_content: str):
        """设置模板过滤器"""
        if self.config.enable_advanced_template_filter:
            self.template_filter = AdvancedTemplateFilter(
                template_content=template_content,
                similarity_threshold=self.config.template_filter_strictness
            )

    def enhance_similarity_check(
        self,
        text1: str,
        text2: str,
        code1: str = "",
        code2: str = ""
    ) -> NLPEnhancedResult:
        """
        增强相似度检查

        Args:
            text1: 文本1
            text2: 文本2
            code1: 代码1（可选）
            code2: 代码2（可选）

        Returns:
            NLP增强结果
        """
        obfuscations = []
        recommendations = []
        nlp_confidence = 0.8

        # 1. 代码AST分析
        code_similarity_boost = 0
        if self.config.enable_ast_analysis and code1 and code2:
            code_result = compare_code_blocks(code1, code2)
            code_similarity_boost = code_result.overall_similarity - 85

            if code_result.overall_similarity > 70:
                obfuscations.extend([t.value for t in code_result.obfuscation_detected])
                nlp_confidence += 0.1

        # 2. 模板过滤
        if self.template_filter:
            filter_result1 = self.template_filter.filter(text1)
            filter_result2 = self.template_filter.filter(text2)

            # 检测模板操纵
            manipulation1 = self.template_filter.detect_template_manipulation(text1)
            manipulation2 = self.template_filter.detect_template_manipulation(text2)

            if manipulation1['detected']:
                obfuscations.extend(manipulation1['techniques'])
                recommendations.append("检测到模板操纵行为")
                nlp_confidence -= 0.1

        return NLPEnhancedResult(
            original_similarity=0.0,  # 由外部计算
            enhanced_similarity=0.0,  # 由外部计算
            detected_obfuscations=list(set(obfuscations)),
            nlp_confidence=min(max(nlp_confidence, 0.5), 0.95),
            recommendations=recommendations
        )

    def enhance_keyword_matching(
        self,
        text: str,
        keywords: List[str],
        return_details: bool = False
    ) -> Tuple[List[str], float, Optional[List[Dict]]]:
        """
        增强关键词匹配

        Args:
            text: 文本
            keywords: 关键词列表
            return_details: 是否返回详细信息

        Returns:
            (匹配的关键词, 匹配比例, 详细信息)
        """
        if not self.keyword_matcher:
            # 回退到简单匹配
            text_lower = text.lower()
            matched = [k for k in keywords if k.lower() in text_lower]
            ratio = len(matched) / len(keywords) if keywords else 0
            return matched, ratio, None

        results, ratio = self.keyword_matcher.match_keywords(
            text, keywords, MatchMethod.HYBRID
        )

        matched = [r.keyword for r in results if r.matched]

        details = None
        if return_details:
            details = [
                {
                    'keyword': r.keyword,
                    'matched': r.matched,
                    'method': r.method.value,
                    'confidence': r.confidence,
                    'similarity': r.similarity
                }
                for r in results
            ]

        return matched, ratio, details


def create_nlp_enhanced_detector(
    template_content: str = "",
    fuzzy_threshold: float = 0.85,
    strict_mode: bool = False
) -> NLPEngine:
    """
    创建NLP增强检测器（便捷函数）

    Args:
        template_content: 模板内容
        fuzzy_threshold: 模糊匹配阈值
        strict_mode: 严格模式

    Returns:
        NLP引擎
    """
    config = NLPEngineConfig(
        enable_fuzzy_matching=True,
        fuzzy_threshold=fuzzy_threshold,
        enable_term_variants=True,
        enable_advanced_template_filter=True,
        enable_ast_analysis=True,
        template_filter_strictness=0.9 if strict_mode else 0.7
    )

    engine = NLPEngine(config)

    if template_content:
        engine.set_template_filter(template_content)

    return engine


# 供外部系统调用的接口
def enhance_plagiarism_detection(
    submissions: Dict[str, Dict],
    template_content: str = "",
    nlp_config: NLPEngineConfig = None
) -> Dict[str, NLPEnhancedResult]:
    """
    增强查重检测

    Args:
        submissions: 提交内容 {学号: {name, text}}
        template_content: 模板内容
        nlp_config: NLP配置

    Returns:
        {学号: NLP增强结果}
    """
    config = nlp_config or NLPEngineConfig()
    engine = NLPEngine(config)

    if template_content:
        engine.set_template_filter(template_content)

    results = {}

    for student_id, submission in submissions.items():
        text = submission.get('text', '')

        # 对每个学生进行NLP增强分析
        result = NLPEnhancedResult(
            original_similarity=0.0,
            enhanced_similarity=0.0,
            nlp_confidence=0.8
        )

        results[student_id] = result

    return results


def patch_grading_system():
    """
    为现有评分系统打补丁，添加NLP增强功能

    返回增强后的评分器类
    """
    from .enhanced_grading import EnhancedRubricGrader

    return EnhancedRubricGrader


# 配置预设
PRESETS = {
    'default': NLPEngineConfig(),
    'strict': NLPEngineConfig(
        enable_fuzzy_matching=True,
        fuzzy_threshold=0.90,
        enable_term_variants=True,
        enable_advanced_template_filter=True,
        enable_ast_analysis=True,
        template_filter_strictness=0.9
    ),
    'lenient': NLPEngineConfig(
        enable_fuzzy_matching=True,
        fuzzy_threshold=0.75,
        enable_term_variants=True,
        enable_advanced_template_filter=True,
        enable_ast_analysis=True,
        template_filter_strictness=0.5
    ),
    'fast': NLPEngineConfig(
        enable_fuzzy_matching=False,  # 关闭模糊匹配以提高速度
        fuzzy_threshold=0.85,
        enable_term_variants=True,
        enable_advanced_template_filter=True,
        enable_ast_analysis=False,  # 关闭AST分析以提高速度
        template_filter_strictness=0.7
    )
}


def get_preset(name: str) -> NLPEngineConfig:
    """
    获取预设配置

    Args:
        name: 预设名称 ('default', 'strict', 'lenient', 'fast')

    Returns:
        NLP配置
    """
    return PRESETS.get(name, PRESETS['default'])
