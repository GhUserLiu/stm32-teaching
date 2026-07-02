# -*- coding: utf-8 -*-
"""
增强语义检测模块
Enhanced Semantic Detection Module

支持层次化检测、改写检测和篇章结构分析
"""

import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
from collections import Counter, defaultdict

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from .detector import SemanticDetector, SemanticMethod, SemanticSimilarityResult, ChineseTextProcessor


class ParaphraseType(Enum):
    """改写类型"""
    SYNONYM_REPLACEMENT = "synonym"      # 同义词替换
    STRUCTURE_CHANGE = "structure"       # 句式变换
    ABBREVIATION = "abbreviation"        # 缩写/扩展
    REORDERING = "reordering"            # 词序调整
    MIXED = "mixed"                      # 混合改写


@dataclass
class ParaphraseMatch:
    """改写匹配结果"""
    text1: str
    text2: str
    similarity: float              # 语义相似度 (0-100)
    text_similarity: float         # 文本相似度 (0-100)
    paraphrase_type: ParaphraseType
    confidence: float               # 改写置信度 (0-1)
    position1: int
    position2: int


@dataclass
class StructureAnalysis:
    """篇章结构分析结果"""
    section_order_similarity: float     # 章节顺序相似度
    section_content_similarity: float    # 章节内容相似度
    paragraph_density_similarity: float # 段落密度相似度
    overall_structure_score: float      # 综合结构相似度 (0-100)


class EnhancedSemanticDetector:
    """增强语义检测器 - 支持层次化检测和改写识别"""

    def __init__(
        self,
        method: SemanticMethod = SemanticMethod.TFIDF,
        use_jieba: bool = True,
        paraphrase_threshold: float = 0.55
    ):
        """
        初始化增强检测器

        Args:
            method: 检测方法
            use_jieba: 是否使用 jieba 分词
            paraphrase_threshold: 改写判定阈值
        """
        self.base_detector = SemanticDetector(method=method, use_jieba=use_jieba)
        self.paraphrase_threshold = paraphrase_threshold
        self.text_processor = ChineseTextProcessor(use_jieba=use_jieba)

        # 同义词词典（简化版）
        self.synonym_groups = self._build_synonym_groups()

    def _build_synonym_groups(self) -> Dict[str, List[str]]:
        """构建同义词组"""
        return {
            '使用': ['利用', '采用', '应用', '运用'],
            '实现': ['完成', '达成', '实现', '做到'],
            '分析': ['研究', '探讨', '分析', '解析'],
            '设计': ['规划', '设计', '构划'],
            '测试': ['检测', '检验', '测试', '验证'],
            '问题': ['困难', '难题', '问题', '疑问'],
            '解决': ['处理', '解决', '解答', '克服'],
            '通过': ['经过', '通过', '透过'],
            '根据': ['按照', '根据', '依据'],
            '包括': ['包含', '包括', '含有'],
            '方法': ['方式', '方法', '途径'],
            '功能': ['作用', '功能', '用途'],
            '原理': ['道理', '原理', '机理'],
            '实验': ['测试', '实验', '试验'],
        }

    def detect_paraphrasing(
        self,
        text1: str,
        text2: str
    ) -> List[ParaphraseMatch]:
        """
        检测改写内容

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            改写匹配列表
        """
        # 提取句子
        sentences1 = self.text_processor.extract_sentences(text1)
        sentences2 = self.text_processor.extract_sentences(text2)

        paraphrases = []

        for i, sent1 in enumerate(sentences1):
            for j, sent2 in enumerate(sentences2):
                # 计算语义相似度
                semantic_result = self.base_detector.detect(sent1, sent2, compare_sentences=False)

                # 计算文本相似度（简单序列）
                text_sim = self._compute_sequence_similarity(sent1, sent2)

                # 判断是否改写：语义相似但文本不同
                if (semantic_result.similarity >= self.paraphrase_threshold * 100 and
                    text_sim < 0.8 and
                    text_sim > 0.2):  # 文本不能太不同

                    # 识别改写类型
                    para_type = self._identify_paraphrase_type(sent1, sent2)

                    # 计算改写置信度
                    confidence = self._compute_paraphrase_confidence(
                        semantic_result.similarity / 100,
                        text_sim,
                        para_type
                    )

                    paraphrases.append(ParaphraseMatch(
                        text1=sent1,
                        text2=sent2,
                        similarity=semantic_result.similarity,
                        text_similarity=text_sim * 100,
                        paraphrase_type=para_type,
                        confidence=confidence,
                        position1=i,
                        position2=j
                    ))

        return paraphrases

    def _compute_sequence_similarity(self, text1: str, text2: str) -> float:
        """计算序列相似度"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()

    def _identify_paraphrase_type(self, text1: str, text2: str) -> ParaphraseType:
        """识别改写类型"""
        tokens1 = set(self.text_processor.tokenize(text1))
        tokens2 = set(self.text_processor.tokenize(text2))

        # 计算词汇重叠度
        overlap = len(tokens1 & tokens2) / max(len(tokens1 | tokens2), 1)

        # 检查同义词替换
        synonym_count = 0
        for word in tokens1:
            for syn_group in self.synonym_groups.values():
                if word in syn_group:
                    synonym_count += 1
                    break

        if overlap > 0.6:
            return ParaphraseType.SYNONYM_REPLACEMENT
        elif synonym_count > 0:
            return ParaphraseType.MIXED
        else:
            return ParaphraseType.STRUCTURE_CHANGE

    def _compute_paraphrase_confidence(
        self,
        semantic_sim: float,
        text_sim: float,
        para_type: ParaphraseType
    ) -> float:
        """计算改写置信度"""
        # 基础置信度来自语义相似度
        base_confidence = semantic_sim

        # 文本相似度适中时置信度最高
        text_factor = 1.0 - abs(text_sim - 0.5) * 0.5

        # 不同改写类型的置信度权重
        type_weights = {
            ParaphraseType.SYNONYM_REPLACEMENT: 0.9,
            ParaphraseType.STRUCTURE_CHANGE: 0.7,
            ParaphraseType.ABBREVIATION: 0.8,
            ParaphraseType.REORDERING: 0.75,
            ParaphraseType.MIXED: 0.85
        }

        type_factor = type_weights.get(para_type, 0.7)

        confidence = base_confidence * text_factor * type_factor
        return min(confidence, 0.98)

    def compute_structure_similarity(
        self,
        doc1: Dict,
        doc2: Dict
    ) -> StructureAnalysis:
        """
        计算篇章结构相似度

        Args:
            doc1: 文档1结构 {headings: [], sections: {...}}
            doc2: 文档2结构

        Returns:
            结构分析结果
        """
        # 1. 章节顺序相似度
        section_order_sim = self._compute_section_order_similarity(doc1, doc2)

        # 2. 章节内容相似度
        section_content_sim = self._compute_section_content_similarity(doc1, doc2)

        # 3. 段落密度相似度
        density_sim = self._compute_density_similarity(doc1, doc2)

        # 综合评分
        overall = (
            section_order_sim * 0.4 +
            section_content_sim * 0.4 +
            density_sim * 0.2
        )

        return StructureAnalysis(
            section_order_similarity=section_order_sim * 100,
            section_content_similarity=section_content_sim * 100,
            paragraph_density_similarity=density_sim * 100,
            overall_structure_score=overall * 100
        )

    def _compute_section_order_similarity(self, doc1: Dict, doc2: Dict) -> float:
        """计算章节顺序相似度"""
        headings1 = doc1.get('headings', [])
        headings2 = doc2.get('headings', [])

        if not headings1 or not headings2:
            return 0.5

        # 提取章节编号
        sections1 = [self._extract_section_number(h) for h in headings1]
        sections2 = [self._extract_section_number(h) for h in headings2]

        # 计算顺序相关性
        matches = 0
        min_len = min(len(sections1), len(sections2))

        for i in range(min_len):
            if sections1[i] == sections2[i]:
                matches += 1

        return matches / max(len(sections1), len(sections2))

    def _extract_section_number(self, heading: str) -> str:
        """提取章节编号"""
        match = re.match(r'^([一二三四五六七八九十]+)[、．.]', heading)
        if match:
            return match.group(1)

        match = re.match(r'^(\d+)[、．.]', heading)
        if match:
            return match.group(1)

        return ''

    def _compute_section_content_similarity(self, doc1: Dict, doc2: Dict) -> float:
        """计算章节内容相似度"""
        sections1 = doc1.get('sections', {})
        sections2 = doc2.get('sections', {})

        if not sections1 or not sections2:
            return 0.5

        common_sections = set(sections1.keys()) & set(sections2.keys())

        if not common_sections:
            return 0.0

        total_similarity = 0.0
        for section in common_sections:
            text1 = ' '.join(sections1[section])
            text2 = ' '.join(sections2[section])

            result = self.base_detector.detect(text1, text2, compare_sentences=False)
            total_similarity += result.similarity / 100

        return total_similarity / len(common_sections)

    def _compute_density_similarity(self, doc1: Dict, doc2: Dict) -> float:
        """计算段落密度相似度"""
        text1 = doc1.get('full_text', '')
        text2 = doc2.get('full_text', '')

        # 计算每段平均字数
        paras1 = [p for p in text1.split('\n\n') if p.strip()]
        paras2 = [p for p in text2.split('\n\n') if p.strip()]

        if not paras1 or not paras2:
            return 0.5

        density1 = len(text1) / len(paras1)
        density2 = len(text2) / len(paras2)

        # 归一化差异
        max_density = max(density1, density2)
        if max_density == 0:
            return 1.0

        diff = abs(density1 - density2) / max_density
        return 1.0 - diff

    def hierarchical_detect(
        self,
        text1: str,
        text2: str
    ) -> Dict:
        """
        层次化检测（篇章级 + 句子级）

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            综合检测结果
        """
        # 1. 篇章级检测
        overall_result = self.base_detector.detect(text1, text2, compare_sentences=False)

        # 2. 叹写检测
        paraphrases = self.detect_paraphrasing(text1, text2)

        # 3. 结构分析
        doc1 = self._parse_document_structure(text1)
        doc2 = self._parse_document_structure(text2)
        structure_analysis = self.compute_structure_similarity(doc1, doc2)

        # 4. 综合风险评估
        risk_factors = []

        if overall_result.similarity > 70:
            risk_factors.append(f"整体语义相似度高({overall_result.similarity:.1f}%)")

        if len(paraphrases) > 3:
            risk_factors.append(f"检测到{len(paraphrases)}处疑似改写")

        if structure_analysis.overall_structure_score > 75:
            risk_factors.append(f"篇章结构高度相似({structure_analysis.overall_structure_score:.1f}%)")

        if structure_analysis.section_order_similarity > 80:
            risk_factors.append(f"章节顺序高度一致({structure_analysis.section_order_similarity:.1f}%)")

        # 判定是否改写
        is_paraphrase = (
            len(paraphrases) > 0 and
            overall_result.similarity > 50 and
            overall_result.similarity < 85 and
            structure_analysis.overall_structure_score > 60
        )

        return {
            'overall_similarity': overall_result.similarity,
            'is_paraphrase': is_paraphrase,
            'paraphrase_count': len(paraphrases),
            'paraphrases': [
                {
                    'text1': p.text1,
                    'text2': p.text2,
                    'similarity': p.similarity,
                    'type': p.paraphrase_type.value,
                    'confidence': p.confidence
                }
                for p in paraphrases[:10]  # 限制返回数量
            ],
            'structure_analysis': {
                'section_order': structure_analysis.section_order_similarity,
                'section_content': structure_analysis.section_content_similarity,
                'paragraph_density': structure_analysis.paragraph_density_similarity,
                'overall': structure_analysis.overall_structure_score
            },
            'risk_factors': risk_factors,
            'confidence': overall_result.confidence
        }

    def _parse_document_structure(self, text: str) -> Dict:
        """解析文档结构"""
        lines = text.split('\n')
        headings = []
        sections = defaultdict(list)
        current_section = 'intro'

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测标题
            match = re.match(r'^([一二三四五六七八九十]+)[、．.]\s*(.+)', line)
            if match:
                section_num = match.group(1)
                section_title = match.group(2)
                heading = f"{section_num}、{section_title}"
                headings.append(heading)
                current_section = section_num
            else:
                sections[current_section].append(line)

        return {
            'headings': headings,
            'sections': dict(sections),
            'full_text': text
        }

    def batch_hierarchical_detect(
        self,
        submissions: Dict[str, str]
    ) -> Dict[str, List[Dict]]:
        """
        批量层次化检测

        Args:
            submissions: {学号: 文本}

        Returns:
            {学号: [检测结果列表]}
        """
        results = {}
        student_ids = list(submissions.keys())

        for i, s1 in enumerate(student_ids):
            similarities = []
            for j in range(i + 1, len(student_ids)):
                s2 = student_ids[j]

                result = self.hierarchical_detect(
                    submissions[s1],
                    submissions[s2]
                )

                similarities.append({
                    'similar_to': s2,
                    **result
                })

            if similarities:
                results[s1] = similarities

        return results
