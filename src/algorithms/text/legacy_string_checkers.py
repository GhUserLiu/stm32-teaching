#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapters wrapping the legacy string similarity functions 1:1.

Each adapter delegates to ``tools/plagiarism/core/algorithms.py`` unchanged;
byte-for-byte parity with the legacy dispatch (``compute_similarity``) is
pinned by tests/unit/test_algorithm_adapters.py across empty/whitespace/
identical/CJK/disjoint cases.

Naming mirrors ``SimilarityMethod`` enum values ('sequence', 'cosine', ...)
so the future similarity_service maps ``SimilarityMethod.X.value`` straight
onto a factory key. 'ngram' has no enum counterpart -- it was implemented
but never wired into the legacy dispatch, which is exactly the kind of
half-finished asset the factory makes reachable.

All are ContentKind.ANY: the legacy pipeline ran these on prose AND on code
segments alike, so the adapters must be visible from both modality lookups.
"""

from __future__ import annotations

from algorithms.base import BaseSimilarityChecker, ContentKind
from algorithms.factory import register_checker
from tools.plagiarism.core.algorithms import (
    cosine_similarity,
    hybrid_similarity,
    jaccard_similarity,
    levenshtein_similarity,
    ngram_similarity,
    sequence_similarity,
)


@register_checker
class SequenceChecker(BaseSimilarityChecker):
    """difflib SequenceMatcher -- the engine behind legacy code-segment sim."""

    name = "sequence"
    kind = ContentKind.ANY
    description = "序列匹配（difflib，与旧链路逐字节等价）"

    def compare(self, left: str, right: str) -> float:
        return sequence_similarity(left, right)


@register_checker
class CosineChecker(BaseSimilarityChecker):
    """Bag-of-words TF cosine (legacy 'cosine'; NOT TF-IDF -- see TfidfChecker)."""

    name = "cosine"
    kind = ContentKind.ANY
    description = "词频余弦（词袋 TF，旧 cosine 语义）"

    def compare(self, left: str, right: str) -> float:
        return cosine_similarity(left, right)


@register_checker
class JaccardChecker(BaseSimilarityChecker):
    """Token-set Jaccard."""

    name = "jaccard"
    kind = ContentKind.ANY
    description = "Jaccard 集合相似度"

    def compare(self, left: str, right: str) -> float:
        return jaccard_similarity(left, right)


@register_checker
class LevenshteinChecker(BaseSimilarityChecker):
    """Edit-distance similarity (legacy truncates inputs to 1000 chars)."""

    name = "levenshtein"
    kind = ContentKind.ANY
    description = "编辑距离相似度（长文本截断 1000 字符，沿用旧行为）"

    def compare(self, left: str, right: str) -> float:
        return levenshtein_similarity(left, right)


@register_checker
class HybridChecker(BaseSimilarityChecker):
    """Legacy 0.4/0.4/0.2 blend of sequence+cosine+jaccard (weights fixed
    in the legacy function; expose as options only if ever needed)."""

    name = "hybrid"
    kind = ContentKind.ANY
    description = "混合相似度（sequence/cosine/jaccard 加权，旧权重）"

    def compare(self, left: str, right: str) -> float:
        return hybrid_similarity(left, right)


@register_checker
class NgramChecker(BaseSimilarityChecker):
    """Character n-gram Jaccard -- previously implemented but never wired."""

    name = "ngram"
    kind = ContentKind.ANY
    description = "字符 N-gram 相似度（局部相似检测；旧代码未接线，工厂化后可达）"

    def __init__(self, n: int = 3, **options):
        super().__init__(**options)
        self._n = n

    def compare(self, left: str, right: str) -> float:
        return ngram_similarity(left, right, self._n)
