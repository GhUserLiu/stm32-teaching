# -*- coding: utf-8 -*-
"""
增强关键词匹配器
Enhanced Keyword Matcher

使用词边界、模糊匹配和语义相似度来改进关键词检测
防止通过简单的字符分割、空格插入等手段绕过
"""

import re
import math
from typing import List, Dict, Tuple, Set, Optional, Pattern
from dataclasses import dataclass, field
from enum import Enum
from difflib import SequenceMatcher

try:
    from jieba import lcut as jieba_lcut
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


class MatchMethod(Enum):
    """匹配方法"""
    EXACT = "exact"           # 精确匹配
    WORD_BOUNDARY = "word_boundary"  # 词边界匹配
    FUZZY = "fuzzy"           # 模糊匹配
    SEMANTIC = "semantic"     # 语义匹配（需要embedding）
    HYBRID = "hybrid"         # 混合匹配


@dataclass
class MatchResult:
    """匹配结果"""
    keyword: str
    matched: bool
    matched_text: str = ""
    similarity: float = 0.0
    position: int = -1
    method: MatchMethod = MatchMethod.EXACT
    confidence: float = 1.0


class FuzzyMatcher:
    """模糊匹配器 - 使用编辑距离和相似度算法"""

    # 欺骗模式检测
    OBFUSCATION_PATTERNS = [
        r'\s+',           # 空格插入
        r'[_\-\.]+',      # 特殊字符插入
        r'[0-9]+',        # 数字插入
        r'\(.+?\)',       # 括号内容
    ]

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """计算Levenshtein编辑距离"""
        if len(s1) < len(s2):
            return FuzzyMatcher.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))

        for i, c1 in enumerate(s1):
            current_row = [i + 1]

            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)

                current_row.append(min(insertions, deletions, substitutions))

            previous_row = current_row

        return previous_row[-1]

    @staticmethod
    def similarity_ratio(s1: str, s2: str) -> float:
        """计算相似度比率"""
        return SequenceMatcher(None, s1, s2).ratio()

    @staticmethod
    def clean_obfuscation(text: str) -> str:
        """
        清理常见的混淆模式
        例如: "G P I O" -> "GPIO", "G-P-I-O" -> "GPIO"
        """
        # 移除空格和特殊分隔符（保留字母数字和中文）
        cleaned = re.sub(r'[\s_\-\.]+', '', text)
        return cleaned

    @staticmethod
    def detect_obfuscation_type(text: str) -> List[str]:
        """检测文本中使用的混淆类型"""
        detected = []

        if re.search(r'\s+[A-Za-z0-9]', text):
            detected.append('space_insertion')

        if re.search(r'[_\-\.]{2,}', text):
            detected.append('special_char_insertion')

        if re.search(r'[A-Za-z]\d[A-Za-z]', text):
            detected.append('number_insertion')

        return detected

    @staticmethod
    def fuzzy_match_keyword(keyword: str, text: str, threshold: float = 0.85) -> MatchResult:
        """
        模糊匹配关键词

        Args:
            keyword: 关键词
            text: 搜索文本
            threshold: 相似度阈值

        Returns:
            匹配结果
        """
        # 首先尝试清理混淆后的匹配
        cleaned_text = FuzzyMatcher.clean_obfuscation(text)
        if keyword.lower() in cleaned_text.lower():
            return MatchResult(
                keyword=keyword,
                matched=True,
                matched_text=keyword,
                similarity=1.0,
                method=MatchMethod.FUZZY,
                confidence=0.95
            )

        # 在文本中查找所有可能的匹配位置
        text_lower = text.lower()
        keyword_lower = keyword.lower()

        # 滑动窗口搜索
        best_match = None
        best_similarity = 0.0

        # 窗口大小：关键词长度的80%到120%
        min_window = max(3, int(len(keyword) * 0.8))
        max_window = int(len(keyword) * 1.5) + 5

        for window_size in range(min_window, max_window + 1):
            for i in range(len(text) - window_size + 1):
                window = text[i:i + window_size]
                window_clean = FuzzyMatcher.clean_obfuscation(window)

                # 计算相似度
                sim = FuzzyMatcher.similarity_ratio(keyword_lower, window_clean.lower())

                if sim > best_similarity:
                    best_similarity = sim
                    best_match = window

                    if sim >= threshold:
                        break

            if best_similarity >= threshold:
                break

        if best_similarity >= threshold:
            return MatchResult(
                keyword=keyword,
                matched=True,
                matched_text=best_match or "",
                similarity=best_similarity,
                method=MatchMethod.FUZZY,
                confidence=best_similarity
            )

        return MatchResult(
            keyword=keyword,
            matched=False,
            similarity=best_similarity,
            method=MatchMethod.FUZZY,
            confidence=best_similarity
        )


class EnhancedKeywordMatcher:
    """增强关键词匹配器 - 综合多种匹配策略"""

    # 技术术语词典（包含常见变体）
    TECH_VARIANTS = {
        'gpio': ['gpio', 'Gpio', 'GPIO', 'G P I O', 'G-P-I-O', '通用IO', '通用输入输出'],
        '中断': ['中断', '外部中断', 'EXTI', 'exti', '中断服务', 'ISR', 'isr'],
        'exti': ['exti', 'EXTI', '外部中断', 'External Interrupt'],
        'dwt': ['dwt', 'DWT', 'Data Watchpoint', '数据断点'],
        '消抖': ['消抖', '去抖', 'debounce', 'Debounce', '防抖'],
        '状态机': ['状态机', '状态机', 'State Machine', 'FSM', 'fsm'],
        '档位': ['档位', '档位', 'gear', 'Gear', '档'],
        'led': ['led', 'LED', '发光二极管', 'Light Emitting Diode'],
        '烧录': ['烧录', '烧写', '下载', 'Download', 'Flash', 'Programming'],
        'isp': ['isp', 'ISP', '在系统编程', 'In-System Programming'],
        'pf9': ['pf9', 'PF9', 'PF_9', 'PF-9'],
        'pf10': ['pf10', 'PF10', 'PF_10', 'PF-10'],
        'pe4': ['pe4', 'PE4', 'PE_4', 'PE-4'],
        'hal': ['hal', 'HAL', 'Hardware Abstraction Layer'],
        'cubemx': ['cubemx', 'CubeMX', 'STM32CubeMX'],
    }

    # 词边界正则模式
    WORD_BOUNDARY_PATTERNS = {
        'english': r'\b[a-zA-Z_][a-zA-Z0-9_]*\b',
        'chinese': r'[一-鿿]+',
        'mixed': r'[\w一-鿿]+',
    }

    def __init__(
        self,
        use_fuzzy: bool = True,
        use_variants: bool = True,
        fuzzy_threshold: float = 0.85,
        enable_jieba: bool = True
    ):
        """
        初始化匹配器

        Args:
            use_fuzzy: 是否启用模糊匹配
            use_variants: 是否使用术语变体词典
            fuzzy_threshold: 模糊匹配阈值
            enable_jieba: 是否启用jieba分词
        """
        self.use_fuzzy = use_fuzzy
        self.use_variants = use_variants
        self.fuzzy_threshold = fuzzy_threshold
        self.enable_jieba = enable_jieba and JIEBA_AVAILABLE

        # 构建反向索引（变体 -> 标准词）
        self.variant_to_canonical = {}
        if use_variants:
            for canonical, variants in self.TECH_VARIANTS.items():
                for variant in variants:
                    self.variant_to_canonical[variant.lower()] = canonical

    def match_keywords(
        self,
        text: str,
        keywords: List[str],
        method: MatchMethod = MatchMethod.HYBRID
    ) -> Tuple[List[MatchResult], float]:
        """
        匹配关键词列表

        Args:
            text: 搜索文本
            keywords: 关键词列表
            method: 匹配方法

        Returns:
            (匹配结果列表, 匹配比例)
        """
        results = []

        for keyword in keywords:
            result = self.match_single_keyword(text, keyword, method)
            results.append(result)

        matched_count = sum(1 for r in results if r.matched)
        match_ratio = matched_count / len(keywords) if keywords else 0

        return results, match_ratio

    def match_single_keyword(
        self,
        text: str,
        keyword: str,
        method: MatchMethod = MatchMethod.HYBRID
    ) -> MatchResult:
        """
        匹配单个关键词

        Args:
            text: 搜索文本
            keyword: 关键词
            method: 匹配方法

        Returns:
            匹配结果
        """
        text_lower = text.lower()
        keyword_lower = keyword.lower()

        # 方法1: 精确匹配
        if keyword_lower in text_lower:
            pos = text_lower.find(keyword_lower)
            return MatchResult(
                keyword=keyword,
                matched=True,
                matched_text=text[pos:pos + len(keyword)],
                similarity=1.0,
                position=pos,
                method=MatchMethod.EXACT,
                confidence=1.0
            )

        # 方法2: 术语变体匹配
        if self.use_variants:
            variant_result = self._match_variant(text, keyword)
            if variant_result.matched:
                return variant_result

        # 方法3: 词边界匹配
        boundary_result = self._match_with_word_boundary(text, keyword)
        if boundary_result.matched:
            return boundary_result

        # 方法4: 模糊匹配
        if self.use_fuzzy and method in [MatchMethod.FUZZY, MatchMethod.HYBRID]:
            fuzzy_result = FuzzyMatcher.fuzzy_match_keyword(
                keyword, text, self.fuzzy_threshold
            )
            if fuzzy_result.matched:
                return fuzzy_result

        # 未匹配
        return MatchResult(
            keyword=keyword,
            matched=False,
            method=method,
            confidence=0.0
        )

    def _match_variant(self, text: str, keyword: str) -> MatchResult:
        """匹配术语变体"""
        # 检查是否是标准词
        canonical = self.TECH_VARIANTS.get(keyword.lower())
        if canonical:
            # keyword是标准词，查找其变体
            for variant in self.TECH_VARIANTS[keyword.lower()]:
                if variant.lower() in text.lower():
                    return MatchResult(
                        keyword=keyword,
                        matched=True,
                        matched_text=variant,
                        similarity=0.9,
                        method=MatchMethod.EXACT,
                        confidence=0.9
                    )
        else:
            # keyword可能是变体，查找其标准词
            canonical = self.variant_to_canonical.get(keyword.lower())
            if canonical:
                # 查找所有相关变体
                for variant in self.TECH_VARIANTS.get(canonical, []):
                    if variant.lower() in text.lower():
                        return MatchResult(
                            keyword=keyword,
                            matched=True,
                            matched_text=variant,
                            similarity=0.9,
                            method=MatchMethod.EXACT,
                            confidence=0.9
                        )

        return MatchResult(keyword=keyword, matched=False)

    def _match_with_word_boundary(self, text: str, keyword: str) -> MatchResult:
        """使用词边界匹配"""
        # 判断关键词类型
        is_chinese = bool(re.search(r'[一-鿿]', keyword))
        is_mixed = bool(re.search(r'[a-zA-Z]', keyword) and re.search(r'[一-鿿]', keyword))

        if is_chinese and not is_mixed:
            # 中文词边界
            pattern = re.compile(re.escape(keyword))
        else:
            # 英文或混合词边界
            pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)

        match = pattern.search(text)
        if match:
            return MatchResult(
                keyword=keyword,
                matched=True,
                matched_text=match.group(),
                similarity=1.0,
                position=match.start(),
                method=MatchMethod.WORD_BOUNDARY,
                confidence=0.95
            )

        return MatchResult(keyword=keyword, matched=False)

    def extract_context(
        self,
        text: str,
        keyword: str,
        context_size: int = 50
    ) -> str:
        """
        提取关键词所在位置的上下文

        Args:
            text: 文本
            keyword: 关键词
            context_size: 上下文大小

        Returns:
            上下文文本
        """
        result = self.match_single_keyword(text, keyword)

        if result.matched and result.position >= 0:
            start = max(0, result.position - context_size)
            end = min(len(text), result.position + len(keyword) + context_size)
            return text[start:end]

        return ""

    def batch_match(
        self,
        texts: Dict[str, str],
        keywords: List[str]
    ) -> Dict[str, Tuple[List[MatchResult], float]]:
        """
        批量匹配多个文本

        Args:
            texts: {文本ID: 文本内容}
            keywords: 关键词列表

        Returns:
            {文本ID: (匹配结果, 匹配比例)}
        """
        results = {}

        for text_id, text in texts.items():
            match_results, ratio = self.match_keywords(text, keywords)
            results[text_id] = (match_results, ratio)

        return results


def enhance_grading_matcher(original_matcher_class=None):
    """
    装饰器：增强现有的评分匹配器

    用法：
    @enhance_grading_matcher
    class MyMatcher:
        ...
    """
    if original_matcher_class is None:
        def decorator(cls):
            return enhance_grading_matcher(cls)
        return decorator

    # 创建增强版本
    class EnhancedMatcher(original_matcher_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.enhanced_matcher = EnhancedKeywordMatcher(
                use_fuzzy=True,
                use_variants=True,
                fuzzy_threshold=0.85
            )

        def match_keywords(self, text: str, keywords: List[str]) -> Tuple[List[str], float]:
            """重写匹配方法，使用增强匹配器"""
            results, ratio = self.enhanced_matcher.match_keywords(
                text, keywords, MatchMethod.HYBRID
            )

            matched = [r.keyword for r in results if r.matched]
            return matched, ratio

    return EnhancedMatcher


# 便捷函数
def quick_match(text: str, keywords: List[str]) -> Dict[str, bool]:
    """
    快速匹配检查

    Args:
        text: 文本
        keywords: 关键词列表

    Returns:
        {关键词: 是否匹配}
    """
    matcher = EnhancedKeywordMatcher(use_fuzzy=True, use_variants=True)
    results, _ = matcher.match_keywords(text, keywords)

    return {r.keyword: r.matched for r in results}
