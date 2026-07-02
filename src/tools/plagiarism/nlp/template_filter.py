# -*- coding: utf-8 -*-
"""
高级模板过滤器
Advanced Template Filter

使用N-gram、词向量和语义相似度来改进模板过滤
防止通过简单的字符修改绕过模板检测
"""

import re
import hashlib
from typing import List, Dict, Tuple, Set, Optional, Pattern
from dataclasses import dataclass, field
from collections import Counter, defaultdict
from enum import Enum

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from jieba import lcut as jieba_lcut
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


class FilterMethod(Enum):
    """过滤方法"""
    NGRAM = "ngram"           # N-gram匹配
    SEMANTIC = "semantic"     # 语义相似度
    HYBRID = "hybrid"         # 混合方法
    STRUCTURAL = "structural" # 结构化匹配


@dataclass
class TemplatePattern:
    """模板模式"""
    text: str
    ngram_signatures: List[str] = field(default_factory=list)
    semantic_hash: str = ""
    length: int = 0
    position_in_template: int = 0

    def __post_init__(self):
        self.length = len(self.text)


@dataclass
class FilterResult:
    """过滤结果"""
    original_text: str
    filtered_text: str
    removed_patterns: List[str] = field(default_factory=list)
    removal_ratio: float = 0.0
    confidence: float = 0.0
    method_used: FilterMethod = FilterMethod.HYBRID


class NgramExtractor:
    """N-gram提取器"""

    @staticmethod
    def extract_char_ngrams(text: str, n: int = 3) -> List[str]:
        """
        提取字符级N-gram

        Args:
            text: 输入文本
            n: N-gram大小

        Returns:
            N-gram列表
        """
        # 清理文本（保留中文、字母、数字）
        cleaned = re.sub(r'[^\w一-鿿]', '', text)

        if len(cleaned) < n:
            return [cleaned]

        return [cleaned[i:i+n] for i in range(len(cleaned) - n + 1)]

    @staticmethod
    def extract_word_ngrams(text: str, n: int = 2) -> List[str]:
        """
        提取词级N-gram

        Args:
            text: 输入文本
            n: N-gram大小

        Returns:
            词N-gram列表
        """
        if JIEBA_AVAILABLE:
            words = jieba_lcut(text)
        else:
            # 简单分词
            words = re.findall(r'[\w一-鿿]+', text)

        # 过滤短词
        words = [w for w in words if len(w) > 1]

        if len(words) < n:
            return [' '.join(words)]

        ngrams = []
        for i in range(len(words) - n + 1):
            ngrams.append(' '.join(words[i:i+n]))

        return ngrams

    @staticmethod
    def compute_ngram_similarity(ngrams1: List[str], ngrams2: List[str]) -> float:
        """
        计算N-gram集合相似度（Jaccard）

        Args:
            ngrams1: N-gram列表1
            ngrams2: N-gram列表2

        Returns:
            相似度 0-1
        """
        set1 = set(ngrams1)
        set2 = set(ngrams2)

        if not set1 or not set2:
            return 0.0

        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def compute_containment(ngrams_container: List[str], ngrams_contained: List[str]) -> float:
        """
        计算包含度（contained在container中的比例）

        Args:
            ngrams_container: 容器N-gram
            ngrams_contained: 被包含N-gram

        Returns:
            包含度 0-1
        """
        set_container = set(ngrams_container)
        set_contained = set(ngrams_contained)

        if not set_contained:
            return 0.0

        intersection = set_container & set_contained
        return len(intersection) / len(set_contained)


class AdvancedTemplateFilter:
    """高级模板过滤器"""

    def __init__(
        self,
        template_content: str = "",
        ngram_sizes: List[int] = None,
        similarity_threshold: float = 0.7,
        use_semantic: bool = False
    ):
        """
        初始化过滤器

        Args:
            template_content: 模板内容
            ngram_sizes: N-gram大小列表
            similarity_threshold: 相似度阈值
            use_semantic: 是否使用语义相似度
        """
        self.template_content = template_content
        self.ngram_sizes = ngram_sizes or [3, 4, 5]
        self.similarity_threshold = similarity_threshold
        self.use_semantic = use_semantic

        # 提取模板特征
        self.template_patterns = self._extract_template_patterns()

    def _extract_template_patterns(self) -> List[TemplatePattern]:
        """
        从模板内容中提取特征模式

        使用多种策略：
        1. 完整句子（长度>15）
        2. 关键短语
        3. 结构化标记
        """
        patterns = []

        if not self.template_content:
            return patterns

        # 按句子分割
        sentences = re.split(r'[。！？\n]+', self.template_content)

        for i, sent in enumerate(sentences):
            sent = sent.strip()
            if len(sent) < 10:
                continue

            # 计算签名
            ngrams = []
            for n in self.ngram_sizes:
                ngrams.extend(NgramExtractor.extract_char_ngrams(sent, n))

            # 计算语义哈希
            semantic_hash = self._compute_semantic_hash(sent)

            pattern = TemplatePattern(
                text=sent,
                ngram_signatures=ngrams,
                semantic_hash=semantic_hash,
                position_in_template=i
            )
            patterns.append(pattern)

        return patterns

    def _compute_semantic_hash(self, text: str) -> str:
        """
        计算语义哈希（对字符顺序变化不敏感）

        Args:
            text: 输入文本

        Returns:
            哈希值
        """
        # 清理并排序字符
        cleaned = re.sub(r'[^\w一-鿿]', '', text)
        sorted_chars = ''.join(sorted(cleaned.lower()))

        return hashlib.md5(sorted_chars.encode('utf-8')).hexdigest()[:16]

    def filter(
        self,
        text: str,
        method: FilterMethod = FilterMethod.HYBRID
    ) -> FilterResult:
        """
        过滤文本中的模板内容

        Args:
            text: 输入文本
            method: 过滤方法

        Returns:
            过滤结果
        """
        if not self.template_patterns:
            return FilterResult(
                original_text=text,
                filtered_text=text,
                removal_ratio=0.0,
                confidence=1.0
            )

        removed_patterns = []
        filtered_text = text
        total_removed = 0

        # 按句子处理
        sentences = re.split(r'([。！？\n])', text)
        filtered_sentences = []

        for i in range(0, len(sentences) - 1, 2):
            sent = sentences[i] if i < len(sentences) else ''
            punct = sentences[i + 1] if i + 1 < len(sentences) else ''

            is_template = False

            for pattern in self.template_patterns:
                similarity = self._compute_pattern_similarity(sent, pattern, method)

                if similarity >= self.similarity_threshold:
                    is_template = True
                    removed_patterns.append(pattern.text[:50] + "...")
                    total_removed += len(sent)
                    break

            if not is_template:
                filtered_sentences.append(sent + punct)

        filtered_text = ''.join(filtered_sentences)
        removal_ratio = total_removed / len(text) if text else 0

        return FilterResult(
            original_text=text,
            filtered_text=filtered_text,
            removed_patterns=removed_patterns,
            removal_ratio=removal_ratio,
            confidence=1.0 - removal_ratio,
            method_used=method
        )

    def _compute_pattern_similarity(
        self,
        text: str,
        pattern: TemplatePattern,
        method: FilterMethod
    ) -> float:
        """
        计算文本与模板模式的相似度

        Args:
            text: 文本
            pattern: 模板模式
            method: 计算方法

        Returns:
            相似度 0-1
        """
        if method == FilterMethod.NGRAM:
            return self._ngram_similarity(text, pattern)
        elif method == FilterMethod.SEMANTIC:
            return self._semantic_similarity(text, pattern)
        elif method == FilterMethod.STRUCTURAL:
            return self._structural_similarity(text, pattern)
        else:  # HYBRID
            ngram_sim = self._ngram_similarity(text, pattern)
            semantic_sim = self._semantic_similarity(text, pattern)
            return (ngram_sim * 0.6 + semantic_sim * 0.4)

    def _ngram_similarity(self, text: str, pattern: TemplatePattern) -> float:
        """使用N-gram计算相似度"""
        # 提取文本的N-gram
        text_ngrams = []
        for n in self.ngram_sizes:
            text_ngrams.extend(NgramExtractor.extract_char_ngrams(text, n))

        # 计算包含度
        containment = NgramExtractor.compute_containment(
            pattern.ngram_signatures,
            text_ngrams
        )

        return containment

    def _semantic_similarity(self, text: str, pattern: TemplatePattern) -> float:
        """使用语义哈希计算相似度"""
        text_hash = self._compute_semantic_hash(text)

        # 精确匹配
        if text_hash == pattern.semantic_hash:
            return 1.0

        # 使用编辑距离作为备用
        ratio = self._sequence_similarity(text, pattern.text)
        return ratio

    def _structural_similarity(self, text: str, pattern: TemplatePattern) -> float:
        """计算结构相似度"""
        # 提取结构特征（标点、空格、换行位置）
        text_structure = self._extract_structure(text)
        pattern_structure = self._extract_structure(pattern.text)

        return self._sequence_similarity(text_structure, pattern_structure)

    def _extract_structure(self, text: str) -> str:
        """提取文本的结构特征"""
        # 保留标点、空格、换行
        structure = re.sub(r'[^\s\n，。！？、；：""''（）【】《》]', 'X', text)
        return structure

    def _sequence_similarity(self, s1: str, s2: str) -> float:
        """计算序列相似度"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1, s2).ratio()

    def detect_template_manipulation(self, text: str) -> Dict[str, any]:
        """
        检测模板操纵行为

        Args:
            text: 输入文本

        Returns:
            操纵检测结果
        """
        result = {
            'detected': False,
            'techniques': [],
            'confidence': 0.0
        }

        # 检测1: 字符插入
        for pattern in self.template_patterns:
            # 检查语义哈希匹配但字符不匹配（可能插入字符）
            text_hash = self._compute_semantic_hash(text)
            if text_hash == pattern.semantic_hash:
                if text != pattern.text:
                    result['detected'] = True
                    result['techniques'].append('character_insertion')
                    result['confidence'] = max(result['confidence'], 0.7)

            # 检查N-gram高相似但文本不同（可能改写）
            text_ngrams = NgramExtractor.extract_char_ngrams(text, 3)
            pattern_ngrams = pattern.ngram_signatures

            containment = NgramExtractor.compute_containment(
                pattern_ngrams, text_ngrams
            )

            if 0.6 <= containment < 0.95:
                result['detected'] = True
                result['techniques'].append('paraphrasing')
                result['confidence'] = max(result['confidence'], containment)

        return result

    def create_filter_from_reports(
        reports: List[str],
        min_occurrence: int = 3,
        threshold: float = 0.4
    ) -> 'AdvancedTemplateFilter':
        """
        从多份报告中分析提取模板内容

        Args:
            reports: 报告文本列表
            min_occurrence: 最小出现次数
            threshold: 出现比例阈值

        Returns:
            模板过滤器
        """
        # 提取所有句子
        all_sentences = []
        for report in reports:
            sentences = re.split(r'[。！？\n]+', report)
            all_sentences.extend([s.strip() for s in sentences if len(s.strip()) > 10])

        # 统计句子出现频率
        sentence_counts = Counter(all_sentences)

        # 计算N-gram签名并聚类相似句子
        ngram_signatures = {}
        for sent in all_sentences:
            ngrams = NgramExtractor.extract_char_ngrams(sent, 3)
            ngram_signatures[sent] = set(ngrams)

        # 找出高频句子作为模板
        template_sentences = []
        for sent, count in sentence_counts.items():
            if count >= min_occurrence:
                ratio = count / len(reports)
                if ratio >= threshold:
                    template_sentences.append(sent)

        # 构建模板内容
        template_content = '\n'.join(template_sentences)

        return AdvancedTemplateFilter(
            template_content=template_content,
            similarity_threshold=0.7
        )

    def update_template(self, new_template_content: str):
        """
        更新模板内容

        Args:
            new_template_content: 新的模板内容
        """
        self.template_content = new_template_content
        self.template_patterns = self._extract_template_patterns()


class TemplateFilterPipeline:
    """模板过滤流水线 - 支持多阶段过滤"""

    def __init__(self, filters: List[AdvancedTemplateFilter] = None):
        """
        初始化流水线

        Args:
            filters: 过滤器列表
        """
        self.filters = filters or []

    def add_filter(self, filter_obj: AdvancedTemplateFilter):
        """添加过滤器"""
        self.filters.append(filter_obj)

    def filter(self, text: str) -> FilterResult:
        """
        执行流水线过滤

        Args:
            text: 输入文本

        Returns:
            最终过滤结果
        """
        current_text = text
        all_removed = []

        for filter_obj in self.filters:
            result = filter_obj.filter(current_text)
            current_text = result.filtered_text
            all_removed.extend(result.removed_patterns)

        return FilterResult(
            original_text=text,
            filtered_text=current_text,
            removed_patterns=all_removed,
            removal_ratio=(len(text) - len(current_text)) / len(text) if text else 0,
            confidence=1.0,
            method_used=FilterMethod.HYBRID
        )


def create_robust_template_filter(
    template_content: str,
    strictness: float = 0.7
) -> AdvancedTemplateFilter:
    """
    创建健壮的模板过滤器

    Args:
        template_content: 模板内容
        strictness: 严格程度 (0-1)

    Returns:
        配置好的过滤器
    """
    # 根据严格程度调整参数
    ngram_sizes = [3, 4] if strictness < 0.5 else [3, 4, 5, 6]
    threshold = 0.5 + strictness * 0.3  # 0.5 - 0.8

    return AdvancedTemplateFilter(
        template_content=template_content,
        ngram_sizes=ngram_sizes,
        similarity_threshold=threshold,
        use_semantic=strictness > 0.7
    )
