# -*- coding: utf-8 -*-
"""
语义相似度评分系统
Semantic Scoring Engine

基于语义理解的智能评分，支持评分标准的语义匹配和要点检测
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class SemanticMatch:
    """语义匹配结果"""
    criterion_id: str           # 评分标准ID
    criterion_desc: str          # 评分标准描述
    similarity: float            # 相似度 (0-100)
    matched_text: str            # 匹配到的文本片段
    position: int                # 位置
    confidence: float            # 置信度 (0-1)


@dataclass
class SemanticScoreResult:
    """语义评分结果"""
    category_id: str             # 类别ID
    category_name: str           # 类别名称
    semantic_score: float       # 语义评分
    keyword_score: float        # 关键词评分
    final_score: float          # 最终评分（加权融合）
    max_points: float           # 满分
    matches: List[SemanticMatch]  # 匹配详情
    missing_aspects: List[str]   # 缺失的方面
    confidence: float           # 整体置信度


class SemanticScoringEngine:
    """语义评分引擎"""

    def __init__(self, rubric_path: Path, use_jieba: bool = True):
        """
        初始化语义评分引擎

        Args:
            rubric_path: 评分标准文件路径
            use_jieba: 是否使用jieba分词
        """
        self.rubric_path = rubric_path
        self.use_jieba = use_jieba

        # 加载评分标准
        with open(rubric_path, 'r', encoding='utf-8') as f:
            self.rubric = json.load(f)

        # 初始化语义检测器
        self._init_semantic_detector()

        # 预处理评分标准
        self._preprocess_rubric()

    def _init_semantic_detector(self):
        """初始化语义检测器"""
        try:
            # 优先使用增强的语义检测器
            import sys
            plagiarism_path = Path(__file__).parent.parent.parent.parent / "tools" / "plagiarism"
            if str(plagiarism_path) not in sys.path:
                sys.path.insert(0, str(plagiarism_path))

            from semantic import EnhancedSemanticDetector, SemanticMethod
            self.semantic_detector = EnhancedSemanticDetector(
                method=SemanticMethod.TFIDF,
                use_jieba=self.use_jieba
            )
            self.has_semantic = True
        except ImportError:
            self.semantic_detector = None
            self.has_semantic = False

    def _preprocess_rubric(self):
        """预处理评分标准，生成嵌入"""
        self.criterion_embeddings = {}
        self.category_structure = {}

        for category in self.rubric.get('categories', []):
            cat_id = category['id']
            cat_name = category['name']

            self.category_structure[cat_id] = {
                'name': cat_name,
                'points': category['points'],
                'criteria': []
            }

            for criterion in category.get('criteria', []):
                crit_text = criterion.get('description', '')
                keywords = criterion.get('keywords', [])

                # 创建增强的查询文本（描述+关键词）
                enhanced_query = f"{crit_text} {' '.join(keywords)}"

                self.criterion_embeddings[criterion['description']] = {
                    'category_id': cat_id,
                    'points': criterion['points'],
                    'query': enhanced_query,
                    'keywords': keywords
                }

                self.category_structure[cat_id]['criteria'].append({
                    'description': criterion['description'],
                    'points': criterion['points'],
                    'keywords': keywords
                })

    def score_by_semantics(
        self,
        text: str,
        category: Dict
    ) -> Tuple[float, List[SemanticMatch]]:
        """
        基于语义相似度评分

        Args:
            text: 学生的文本内容
            category: 评分标准类别

        Returns:
            (评分, 匹配列表)
        """
        matches = []
        total_score = 0
        max_points = category['points']

        for criterion in category.get('criteria', []):
            desc = criterion['description']
            keywords = criterion.get('keywords', [])
            points = criterion['points']

            # 构建查询文本
            query_text = f"{desc} {' '.join(keywords)}"

            # 在学生文本中搜索相关内容
            matched_text, similarity = self._find_best_match(text, query_text)

            if matched_text:
                # 计算得分
                if similarity >= 0.8:
                    earned_points = points
                elif similarity >= 0.6:
                    earned_points = int(points * 0.8)
                elif similarity >= 0.4:
                    earned_points = int(points * 0.5)
                else:
                    earned_points = int(points * 0.3)

                matches.append(SemanticMatch(
                    criterion_id=desc,
                    criterion_desc=desc,
                    similarity=similarity * 100,
                    matched_text=matched_text[:100],
                    position=text.find(matched_text),
                    confidence=min(similarity + 0.1, 0.95)
                ))

                total_score += earned_points

        return min(total_score, max_points), matches

    def _find_best_match(self, text: str, query: str) -> Tuple[str, float]:
        """
        在文本中查找与查询最匹配的部分

        Args:
            text: 学生文本
            query: 查询文本

        Returns:
            (匹配文本, 相似度)
        """
        if not self.has_semantic or not self.semantic_detector:
            # 回退到关键词匹配
            return self._keyword_match(text, query)

        # 分段处理
        segments = self._split_into_segments(text)

        best_match = ""
        best_similarity = 0.0

        for segment in segments:
            if len(segment.strip()) < 10:
                continue

            # 使用语义检测器计算相似度
            result = self.semantic_detector.base_detector.detect(
                query, segment, compare_sentences=False
            )

            if result.similarity > best_similarity:
                best_similarity = result.similarity / 100
                best_match = segment

        return best_match, best_similarity

    def _keyword_match(self, text: str, query: str) -> Tuple[str, float]:
        """基于关键词的简单匹配"""
        keywords = re.findall(r'[\w一-鿟]{2,}', query)
        if not keywords:
            return "", 0.0

        matched_count = 0
        for kw in keywords:
            if kw in text:
                matched_count += 1

        similarity = matched_count / len(keywords) if keywords else 0
        return query if similarity > 0 else "", similarity

    def _split_into_segments(self, text: str) -> List[str]:
        """将文本分段"""
        # 按段落分割
        segments = re.split(r'\n\n+|\n\s*\n', text)

        # 如果段落太长，按句子进一步分割
        result = []
        for seg in segments:
            if len(seg) > 200:
                sentences = re.split(r'[。！？]', seg)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) > 150 and current:
                        result.append(current)
                        current = sent
                    else:
                        current += sent
                if current:
                    result.append(current)
            else:
                result.append(seg)

        return [s.strip() for s in result if len(s.strip()) > 10]

    def evaluate_with_semantics(
        self,
        student_text: str,
        include_keyword_score: bool = True
    ) -> Dict[str, SemanticScoreResult]:
        """
        使用语义方法评估整个报告

        Args:
            student_text: 学生的文本内容
            include_keyword_score: 是否同时计算关键词评分

        Returns:
            {类别ID: 评分结果}
        """
        results = {}

        for category in self.rubric.get('categories', []):
            cat_id = category['id']

            # 跳过需要手工评定的类别
            if category.get('manual_evaluation'):
                continue

            # 语义评分
            semantic_score, matches = self.score_by_semantics(student_text, category)

            # 关键词评分
            keyword_score = 0
            if include_keyword_score:
                keyword_score = self._score_by_keywords(student_text, category)

            # 融合评分
            final_score = self._aggregate_scores(semantic_score, keyword_score, category['points'])

            # 识别缺失的方面
            missing_aspects = self._identify_missing_aspects(matches, category)

            # 计算置信度
            confidence = self._compute_confidence(matches, category)

            results[cat_id] = SemanticScoreResult(
                category_id=cat_id,
                category_name=category['name'],
                semantic_score=semantic_score,
                keyword_score=keyword_score,
                final_score=final_score,
                max_points=category['points'],
                matches=matches,
                missing_aspects=missing_aspects,
                confidence=confidence
            )

        return results

    def _score_by_keywords(self, text: str, category: Dict) -> float:
        """基于关键词的评分"""
        score = 0

        for criterion in category.get('criteria', []):
            keywords = criterion.get('keywords', [])
            points = criterion['points']

            if not keywords:
                score += points
                continue

            matched = sum(1 for kw in keywords if kw in text)
            coverage = matched / len(keywords)

            if coverage >= 0.6:
                score += points
            elif coverage >= 0.3:
                score += int(points * 0.7)

        return min(score, category['points'])

    def _aggregate_scores(self, semantic: float, keyword: float, max_points: float) -> float:
        """融合语义和关键词评分"""
        # 使用加权融合，关键词作为基础，语义作为增强
        semantic_weight = 0.4
        keyword_weight = 0.6

        # 如果两个评分差异过大，使用较低的
        diff_ratio = abs(semantic - keyword) / max(max_points, 1)

        if diff_ratio > 0.3:
            # 差异大，使用保守策略
            return min(semantic, keyword)
        else:
            # 差异小，加权融合
            aggregated = semantic * semantic_weight + keyword * keyword_weight
            return round(aggregated, 1)

    def _identify_missing_aspects(self, matches: List[SemanticMatch], category: Dict) -> List[str]:
        """识别缺失的评分方面"""
        matched_descriptions = {m.criterion_desc for m in matches}

        missing = []
        for criterion in category.get('criteria', []):
            if criterion['description'] not in matched_descriptions:
                missing.append(criterion['description'])

        return missing

    def _compute_confidence(self, matches: List[SemanticMatch], category: Dict) -> float:
        """计算评分置信度"""
        if not matches:
            return 0.3

        # 基于匹配数量和质量
        match_ratio = len(matches) / len(category.get('criteria', []))

        avg_similarity = sum(m.similarity for m in matches) / len(matches) if matches else 0

        # 高相似度匹配的比例
        high_quality_ratio = sum(1 for m in matches if m.similarity > 70) / len(matches) if matches else 0

        confidence = (
            match_ratio * 0.4 +
            (avg_similarity / 100) * 0.3 +
            high_quality_ratio * 0.3
        )

        return min(confidence, 0.95)


def create_semantic_scorer(rubric_path: Path, use_jieba: bool = True) -> SemanticScoringEngine:
    """
    创建语义评分引擎（便捷函数）

    Args:
        rubric_path: 评分标准文件路径
        use_jieba: 是否使用jieba分词

    Returns:
        语义评分引擎实例
    """
    return SemanticScoringEngine(rubric_path, use_jieba=use_jieba)
