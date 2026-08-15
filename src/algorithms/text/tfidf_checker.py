#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TF-IDF cosine adapter over tools.plagiarism.semantic.detector.TfidfCalculator.

Scale: the calculator emits 0-1 everywhere; this adapter converts to the
canonical 0-100 at every boundary.

Equivalence mapping (all pinned by tests, INCLUDING whitespace-bearing
corpora -- the first review round measured a near-duplicate English pair
at 77.6 legacy vs 0.0 with whitespace-collapsed input):

  * ``preprocess`` is a PASS-THROUGH. The legacy semantic flow (precompute_idf
    -> cosine_similarity on raw text) never strips whitespace, and jieba
    merges space-separated runs into different tokens ('GPIO init' ->
    'GPIOinit'), which then miss the IDF table and vanish from the vectors.
    Collapsing whitespace would silently destroy English similarity.
  * ``prepare(corpus)`` -> corpus-level IDF, mirroring
    SemanticDetector.precompute_idf (empty docs filtered, min_df=1).
  * ``compare()`` after prepare -> corpus-IDF cosine (verified == legacy
    flow, diff 0.0). WITHOUT prepare -> the LEGACY two-document fallback:
    IDF computed from [left, right] then TF-IDF cosine (this is what
    _detect_with_tfidf does per pair), NOT a raw-TF cosine.
  * ``compare_matrix()`` without prepare -> self-prepares IDF from its own
    texts (contract rule 5: valid scores without prepare; the underlying
    cosine_matrix drops zero-IDF tokens, so an empty cache would produce
    an all-zero matrix). Diagonal SET explicitly; symmetric; clamped.
  * ``TfidfCalculator`` is constructed lazily on first use: construction
    builds the jieba prefix dict (~0.8s) and contract rule 5 demands that
    ``__init__`` / ``create_for_kind()`` stay cheap.

No thresholds live here (rule 6) -- SemanticDetector's 0.6 paraphrase
threshold is deliberately NOT carried over; it belongs to the service.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from algorithms.base import (
    BaseSimilarityChecker,
    ContentKind,
    clamp_score,
)
from algorithms.factory import register_checker


@register_checker
class TfidfChecker(BaseSimilarityChecker):
    """TF-IDF cosine similarity (jieba + Chinese stopwords), kind=TEXT."""

    name = "tfidf"
    kind = ContentKind.TEXT
    description = "TF-IDF 余弦（jieba 分词、语料级 IDF、向量化矩阵；原文直比不清洗）"

    def __init__(self, min_df: int = 1, **options):
        super().__init__(**options)
        self._min_df = min_df
        self._calc = None   # lazy: construction builds the jieba prefix dict

    # ------------------------------------------------------------ laziness

    @property
    def _calculator(self):
        if self._calc is None:
            from tools.plagiarism.semantic.detector import TfidfCalculator
            self._calc = TfidfCalculator()
        return self._calc

    # ------------------------------------------------------- normalization

    def preprocess(self, text: str) -> str:
        # PASS-THROUGH (see module docstring): the legacy TF-IDF path
        # compares raw text; whitespace-collapsing merges space-separated
        # English tokens and silently zeroes their similarity.
        return text

    # ------------------------------------------------------------ corpus API

    def prepare(self, corpus: Sequence[str]) -> None:
        """Corpus-level IDF (mirrors SemanticDetector.precompute_idf)."""
        docs = [d for d in corpus if d]
        if docs:
            self._calculator.calculate_idf(docs, min_df=self._min_df)

    def _idf_for(self, texts: Sequence[str]) -> dict:
        """Corpus IDF when prepared; otherwise IDF from the given texts
        themselves (legacy two-doc fallback generalized to n docs)."""
        calc = self._calculator
        if calc.idf_cache:
            return calc.idf_cache
        docs = [t for t in texts if t]
        return calc.calculate_idf(docs) if docs else {}

    # ------------------------------------------------------------ pairwise

    def compare(self, left: str, right: str) -> float:
        calc = self._calculator
        idf = self._idf_for([left, right])
        return calc.cosine_similarity(left, right, idf) * 100.0

    # --------------------------------------------------------------- matrix

    def compare_matrix(self, texts: Sequence[str]) -> List[List[float]]:
        """Vectorized n x n matrix via cosine_matrix(texts, texts).

        Uses corpus IDF after prepare(); without prepare it self-prepares
        from its own texts (rule 5). Guarantees per the base contract:
        symmetric, diagonal set explicitly (100.0 / 0.0 for empty docs),
        0-100 scale via clamp_score.
        """
        n = len(texts)
        if n == 0:
            return []
        prepared = [self.preprocess(t) for t in texts]
        idf = self._idf_for(prepared)
        values = self._calculator.cosine_matrix(prepared, prepared, idf=idf)

        matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        for i in range(n):
            matrix[i][i] = 100.0 if prepared[i] else 0.0
            for j in range(i + 1, n):
                value = clamp_score(float(values[i][j]) * 100.0)
                matrix[i][j] = value
                matrix[j][i] = value
        return matrix
