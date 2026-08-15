#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""算法适配器单测（P3b）：与 legacy 分发逐字节 parity 钉死 + TF-IDF 行为。

parity 是本文件的核心：对 sequence/cosine/jaccard/levenshtein/hybrid 五个
适配器，断言 checker.score(a, b) == compute_similarity(a, b, method) 在
空串/纯空白/全同/前缀/CJK 近似/完全不相关/代码标识符 各类输入下成立
——适配器只是薄包装，不允许任何行为漂移。
"""

import algorithms.text  # noqa: F401  (import-time registration side effect)
from algorithms.base import BaseSimilarityChecker, ContentKind
from algorithms.factory import SimilarityCheckerFactory
from tools.plagiarism.core.algorithms import (
    compute_similarity,
    ngram_similarity,
)
from tools.plagiarism.core.detector import SimilarityMethod

# Covers: empty, whitespace-only, identical, prefix-extension, CJK
# near-duplicate, CJK disjoint, code identifiers.
CASES = [
    ("", ""),
    ("", "abc"),
    ("   \t\n", "abc"),
    ("abc", "abc"),
    ("abcdef", "abcdefgh"),
    ("基于STM32的汽车档位模拟器设计", "基于STM32汽车档位模拟器系统设计"),
    ("完全不同的两段中文文本内容甲", "毫无关联的另一段文字乙丙丁"),
    ("HAL_GPIO_Init", "HAL_GPIO_DeInit"),
]

ENUM_MAPPING = {
    "sequence": SimilarityMethod.SEQUENCE,
    "cosine": SimilarityMethod.COSINE,
    "jaccard": SimilarityMethod.JACCARD,
    "levenshtein": SimilarityMethod.LEVENSHTEIN,
    "hybrid": SimilarityMethod.HYBRID,
}


# ------------------------------------------------------- legacy string parity

def test_string_adapters_parity_with_legacy_dispatch():
    for name, method in ENUM_MAPPING.items():
        checker = SimilarityCheckerFactory.create(name)
        for a, b in CASES:
            expected = compute_similarity(a, b, method)
            assert checker.score(a, b) == expected, (name, repr(a), repr(b))


def test_ngram_adapter_parity():
    checker = SimilarityCheckerFactory.create("ngram", n=3)
    for a, b in CASES:
        expected = ngram_similarity(a, b, 3)   # strips ws internally, idempotent
        assert checker.score(a, b) == expected, (repr(a), repr(b))


def test_any_kind_adapters_visible_from_both_modalities():
    for name in list(ENUM_MAPPING) + ["ngram"]:
        assert name in SimilarityCheckerFactory.names(ContentKind.TEXT)
        assert name in SimilarityCheckerFactory.names(ContentKind.CODE)
    # tfidf is TEXT-only
    assert "tfidf" in SimilarityCheckerFactory.names(ContentKind.TEXT)
    assert "tfidf" not in SimilarityCheckerFactory.names(ContentKind.CODE)


def test_compare_detail_default_is_none():
    checker = SimilarityCheckerFactory.create("sequence")
    assert isinstance(checker, BaseSimilarityChecker)
    assert checker.compare_detail("a", "b") is None


# ---------------------------------------------------------------- tfidf

CORPUS = [
    "基于STM32的汽车档位模拟器设计实验报告内容",
    "基于STM32的汽车档位模拟器设计实验总结内容",
    "今天天气很好适合出去散步放风筝",
]


def test_tfidf_registered_and_kinds():
    assert SimilarityCheckerFactory.is_registered("tfidf")
    engines = {type(e).__name__
               for e in SimilarityCheckerFactory.create_for_kind(ContentKind.TEXT)}
    assert "TfidfChecker" in engines


def test_tfidf_matrix_properties():
    checker = SimilarityCheckerFactory.create("tfidf")
    checker.prepare(CORPUS)
    m = checker.compare_matrix(CORPUS)

    assert len(m) == 3 and all(len(r) == 3 for r in m)
    for i in range(3):
        assert m[i][i] == 100.0                     # SET, not computed
        for j in range(3):
            assert 0.0 <= m[i][j] <= 100.0
            assert m[i][j] == m[j][i]               # symmetric
    assert m[0][1] > 50.0                           # near-duplicate reports
    assert m[0][2] < m[0][1]                        # unrelated scores lower


def test_tfidf_matrix_matches_pairwise_scores():
    checker = SimilarityCheckerFactory.create("tfidf")
    checker.prepare(CORPUS)
    m = checker.compare_matrix(CORPUS)
    for i in range(3):
        for j in range(3):
            if i != j:
                assert abs(m[i][j] - checker.score(CORPUS[i], CORPUS[j])) < 1e-6


def test_tfidf_score_without_prepare_uses_legacy_two_doc_fallback():
    # Legacy per-pair fallback (_detect_with_tfidf): IDF from [t1, t2],
    # then TF-IDF cosine -- NOT raw-TF cosine.
    from tools.plagiarism.semantic.detector import TfidfCalculator
    calc = TfidfCalculator()
    checker = SimilarityCheckerFactory.create("tfidf")
    a, b = CORPUS[0], CORPUS[1]
    expected = calc.cosine_similarity(a, b, calc.calculate_idf([a, b])) * 100
    assert abs(checker.score(a, b) - expected) < 1e-9
    # identical documents still 100; central empty guard holds
    assert checker.score("汽车档位模拟器设计", "汽车档位模拟器设计") == 100.0
    assert checker.score("", "abc") == 0.0
    assert checker.score("   ", "abc") == 0.0


def test_tfidf_parity_with_legacy_flow_on_whitespace_text():
    # The first review round measured 77.6 (legacy) vs 0.0 (adapter with
    # whitespace-collapsed preprocess) here -- preprocess must be pass-through.
    from tools.plagiarism.semantic.detector import TfidfCalculator
    words_corpus = [
        "the turn signal system uses GPIO init and timer",
        "the turn signal system uses GPIO deinit and timer",
        "cooking recipes for dinner tonight",
    ]
    calc = TfidfCalculator()
    calc.calculate_idf([d for d in words_corpus if d])
    checker = SimilarityCheckerFactory.create("tfidf")
    checker.prepare(words_corpus)
    for i in range(3):
        for j in range(3):
            expected = calc.cosine_similarity(
                words_corpus[i], words_corpus[j]) * 100
            assert abs(
                checker.score(words_corpus[i], words_corpus[j])
                - expected) < 1e-9, (i, j)
    assert checker.score(words_corpus[0], words_corpus[1]) > 50.0


def test_tfidf_matrix_without_prepare_self_prepares_idf():
    # Contract rule 5: valid scores without prepare. The underlying
    # cosine_matrix drops zero-IDF tokens, so an empty cache must not be
    # used as-is (that yielded an all-zero matrix before the fix).
    checker = SimilarityCheckerFactory.create("tfidf")
    m = checker.compare_matrix(["汽车档位模拟器设计", "汽车档位模拟器设计", "完全无关内容文本"])
    assert m[0][0] == 100.0
    assert m[0][1] > 0.0
    assert 0.0 <= m[0][2] <= 100.0


def test_tfidf_creation_is_lazy_and_does_not_load_jieba():
    # Contract rule 5: create() must stay cheap -- constructing
    # TfidfCalculator builds the jieba prefix dict (~0.8s), so it must be
    # deferred to first use. Verified in a fresh interpreter.
    import os
    import subprocess
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src"
    code = (
        "import sys; sys.path.insert(0, {src!r}); "
        "import algorithms.text; "
        "from algorithms.factory import SimilarityCheckerFactory; "
        "SimilarityCheckerFactory.create('tfidf'); "
        "print('jieba' in sys.modules)"
    ).format(src=str(src))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, "-c", code],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("False"), result.stdout + result.stderr


def test_tfidf_parity_with_calculator_scaled():
    # Thin-wrapper proof: adapter score == calculator cosine * 100
    from tools.plagiarism.semantic.detector import TfidfCalculator
    calc = TfidfCalculator()
    checker = SimilarityCheckerFactory.create("tfidf")
    calc.calculate_idf([d for d in CORPUS if d])
    checker.prepare(CORPUS)
    expected = calc.cosine_similarity(CORPUS[0], CORPUS[1]) * 100
    assert abs(checker.score(CORPUS[0], CORPUS[1]) - expected) < 1e-9


def test_tfidf_empty_doc_diagonal_zero():
    checker = SimilarityCheckerFactory.create("tfidf")
    checker.prepare(["", "汽车档位模拟器", "今天天气"])
    m = checker.compare_matrix(["", "汽车档位模拟器", "今天天气"])
    assert m[0][0] == 0.0
    assert m[0][1] == 0.0 and m[1][0] == 0.0
