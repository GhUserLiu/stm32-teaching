#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回归 / characterization 测试 —— 相似度算法核心链路。

被测: tools.plagiarism.core.algorithms
  - sequence_similarity / cosine_similarity / jaccard_similarity / levenshtein_similarity
  - hybrid_similarity
  - compute_similarity (method 分发)
  - ngram_similarity / find_similar_segments

目的: 锁定【当前实际行为】，给后续重构（拆 grade_submission 巨函数、改阈值/正则/单位）
装安全网。任何静默漂移都能被抓住。

断言用的全部是 2026-06-30 在当前源码上跑出来的具体数值，不是理想值。

运行:
    PYTHONPATH=src python -m pytest tests/unit/test_similarity_algorithms.py -q
"""

import pytest

from tools.plagiarism.core.algorithms import (
    compute_similarity,
    cosine_similarity,
    find_similar_segments,
    hybrid_similarity,
    jaccard_similarity,
    levenshtein_similarity,
    ngram_similarity,
    sequence_similarity,
    _tokenize,
)
from tools.plagiarism.core.detector import SimilarityMethod


# ---------------------------------------------------------------------------
# ① 单位 / 区间 —— 锁定本模块所有相似度函数返回 0-100（不是 0-1）
# ---------------------------------------------------------------------------

class TestReturnValueRange:
    """锁定所有函数返回的是 0-100 百分比区间（min(hybrid,100.0) 也佐证）。"""

    def test_identical_text_all_methods_return_100(self):
        # 相同文本在所有 method 下都给出上界 100.0（不是 1.0）
        t = "hello world"
        assert compute_similarity(t, t, SimilarityMethod.SEQUENCE) == 100.0
        assert compute_similarity(t, t, SimilarityMethod.COSINE) == 100.0
        assert compute_similarity(t, t, SimilarityMethod.JACCARD) == 100.0
        assert compute_similarity(t, t, SimilarityMethod.LEVENSHTEIN) == 100.0
        assert compute_similarity(t, t, SimilarityMethod.HYBRID) == 100.0

    def test_hybrid_is_capped_at_100(self):
        # hybrid_similarity 末尾 min(hybrid, 100.0)：相同文本三项子分都 100，
        # 加权 100，结果上限 100.0。
        assert hybrid_similarity("hello", "hello") == 100.0

    def test_unit_is_100_not_1_for_partials(self):
        # 部分相似时数值是 0-100 区间内的百分比，不是 0-1 小数
        v = compute_similarity("hello", "help", SimilarityMethod.SEQUENCE)
        assert v == pytest.approx(66.66666666666667)
        assert 60 < v <= 100  # 66.67 表明单位是百分比而非小数（小数会是 0.667）

    def test_hybrid_never_negative_and_within_range(self):
        # 无关输入给出下界 0.0
        assert compute_similarity("hello", "zzzzz", SimilarityMethod.HYBRID) == 0.0


# ---------------------------------------------------------------------------
# ② method 分发 —— compute_similarity 按 method 选择算法，相同高分/无关低分
# ---------------------------------------------------------------------------

class TestComputeSimilarityDispatch:
    """compute_similarity(text1, text2, method) 按 method 分发到不同算法。"""

    def test_default_method_is_hybrid(self):
        # 不传 method 时默认 HYBRID
        t = "hello world"
        assert compute_similarity(t, t) == compute_similarity(t, t, SimilarityMethod.HYBRID)

    def test_each_method_dispatches_independently_on_same_input(self):
        # 用 hello vs help：各 method 给出各自算法的精确值（来自实际跑数）
        x, y = "hello", "help"
        assert compute_similarity(x, y, SimilarityMethod.SEQUENCE) == pytest.approx(66.66666666666667)
        # cosine/jaccard 因 tokenizer 把整串字母合并成单 token，对"相似但不等"返回 0.0（见疑似 bug）
        assert compute_similarity(x, y, SimilarityMethod.COSINE) == 0.0
        assert compute_similarity(x, y, SimilarityMethod.JACCARD) == 0.0
        assert compute_similarity(x, y, SimilarityMethod.LEVENSHTEIN) == pytest.approx(60.0)
        assert compute_similarity(x, y, SimilarityMethod.HYBRID) == pytest.approx(26.666666666666668)

    def test_identical_input_high_unrelated_low_per_method(self):
        # 对每个 method：相同文本 >= 相似文本 >= 无关文本（相对大小符合预期）
        for method in [
            SimilarityMethod.SEQUENCE,
            SimilarityMethod.COSINE,
            SimilarityMethod.JACCARD,
            SimilarityMethod.LEVENSHTEIN,
            SimilarityMethod.HYBRID,
        ]:
            same = compute_similarity("hello", "hello", method)
            similar = compute_similarity("hello", "help", method)
            unrelated = compute_similarity("hello", "zzzzz", method)
            assert same >= similar >= unrelated, (
                f"method={method.value}: same={same} similar={similar} unrelated={unrelated}"
            )

    def test_unknown_method_falls_back_to_sequence(self):
        # else 分支：未识别的 method（如 SEMANTIC / CODE_OBFUSCATION）落到 sequence_similarity
        x, y = "hello", "help"
        seq_value = compute_similarity(x, y, SimilarityMethod.SEQUENCE)
        assert compute_similarity(x, y, SimilarityMethod.SEMANTIC) == pytest.approx(seq_value)
        assert compute_similarity(x, y, SimilarityMethod.CODE_OBFUSCATION) == pytest.approx(seq_value)
        assert compute_similarity(x, y, SimilarityMethod.SEMANTIC_HYBRID) == pytest.approx(seq_value)

    def test_dispatch_to_direct_function_matches(self):
        # compute_similarity 分发后与直接调用底层函数结果一致（清洗相同）
        x, y = "hello", "help"
        # SEQUENCE 分支直接调用 sequence_similarity（compute_similarity 会先清空白，这里无空白）
        assert compute_similarity(x, y, SimilarityMethod.SEQUENCE) == pytest.approx(
            sequence_similarity(x, y)
        )
        assert compute_similarity(x, y, SimilarityMethod.LEVENSHTEIN) == pytest.approx(
            levenshtein_similarity(x, y)
        )


# ---------------------------------------------------------------------------
# ③ hybrid 加权 —— 锁定 0.4 / 0.4 / 0.2 (sequence/cosine/jaccard)
# ---------------------------------------------------------------------------

class TestHybridWeighting:
    """hybrid_similarity = 0.4*seq + 0.4*cos + 0.2*jac，末尾 min(.,100.0)。"""

    def test_weighting_formula_exact(self):
        # 用一对 cosine/jaccard 为 0、sequence 非 0 的输入精确验证权重
        x, y = "hello world", "world hello"
        seq = sequence_similarity(x, y)
        cos = cosine_similarity(x, y)
        jac = jaccard_similarity(x, y)
        expected = seq * 0.4 + cos * 0.4 + jac * 0.2
        assert hybrid_similarity(x, y) == pytest.approx(expected)
        # 实际数值（来自跑数）
        assert seq == pytest.approx(45.45454545454545)
        assert cos == 0.0
        assert jac == 0.0
        assert hybrid_similarity(x, y) == pytest.approx(18.181818181818183)

    def test_weighting_hello_help_exact(self):
        # 另一对样本锁定：seq=66.67, cos=0, jac=0 -> 0.4*66.67 = 26.667
        assert hybrid_similarity("hello", "help") == pytest.approx(26.666666666666668)

    def test_hybrid_uses_subfunctions_not_recompute(self):
        # hybrid 内部调用的是 sequence/cosine/jaccard_similarity（同输入下与直接调用相等）
        x, y = "abc", "abd"
        assert hybrid_similarity(x, y) == pytest.approx(
            sequence_similarity(x, y) * 0.4
            + cosine_similarity(x, y) * 0.4
            + jaccard_similarity(x, y) * 0.2
        )


# ---------------------------------------------------------------------------
# ④ 空输入与空白清洗 —— re.sub(r"\s+","") + 空 -> 0.0
# ---------------------------------------------------------------------------

class TestEmptyAndWhitespace:
    """空 / 仅空白 -> 0.0；compute_similarity 用 re.sub(r'\\s+','') 清洗空白。"""

    def test_both_empty_returns_zero(self):
        for method in SimilarityMethod:
            assert compute_similarity("", "", method) == 0.0

    def test_one_empty_returns_zero(self):
        assert compute_similarity("hello", "", SimilarityMethod.SEQUENCE) == 0.0
        assert compute_similarity("", "hello", SimilarityMethod.HYBRID) == 0.0
        assert compute_similarity("", "hello", SimilarityMethod.COSINE) == 0.0

    def test_whitespace_only_returns_zero(self):
        # re.sub 清洗后变空串 -> 0.0
        assert compute_similarity("   ", "  ", SimilarityMethod.SEQUENCE) == 0.0
        assert compute_similarity("\t\n", "hello", SimilarityMethod.HYBRID) == 0.0
        assert compute_similarity("   \t\n", "hello", SimilarityMethod.HYBRID) == 0.0

    def test_whitespace_cleaned_before_comparison(self):
        # 带空白的相同文本，清洗后等价于无空白，SEQUENCE 给满分 100
        assert compute_similarity("hello world", "hello world", SimilarityMethod.SEQUENCE) == 100.0
        assert compute_similarity("  hello   world  ", "hello world", SimilarityMethod.SEQUENCE) == 100.0
        assert compute_similarity("hello\nworld", "hello\tworld", SimilarityMethod.SEQUENCE) == 100.0

    def test_whitespace_reordering_not_equalized(self):
        # 清洗只去空白，不重排："hello world" vs "world hello" 清洗后仍不同
        assert compute_similarity("hello world", "world hello", SimilarityMethod.SEQUENCE) == pytest.approx(
            50.0
        )

    def test_direct_functions_empty_returns_zero(self):
        # 直接调用底层函数也各自有空守卫 -> 0.0
        assert sequence_similarity("", "x") == 0.0
        assert cosine_similarity("", "x") == 0.0
        assert jaccard_similarity("", "x") == 0.0
        assert levenshtein_similarity("", "x") == 0.0
        assert hybrid_similarity("", "x") == 0.0


# ---------------------------------------------------------------------------
# ⑤ 各 method 精确数值（相同 / 相似 / 无关 各至少一对）
# ---------------------------------------------------------------------------

class TestExactValuesPerMethod:
    """每个 method 的相同/相似/无关输入给出锁定数值（来自实际跑数）。"""

    # ---- sequence_similarity ----
    def test_sequence_exact(self):
        assert sequence_similarity("hello", "hello") == 100.0
        assert sequence_similarity("hello", "help") == pytest.approx(66.66666666666667)
        assert sequence_similarity("hello", "zzzzz") == 0.0

    # ---- levenshtein_similarity ----
    def test_levenshtein_exact(self):
        assert levenshtein_similarity("hello", "hello") == 100.0
        assert levenshtein_similarity("hello", "help") == pytest.approx(60.0)
        assert levenshtein_similarity("hello", "world") == pytest.approx(20.0)
        assert levenshtein_similarity("hello", "zzzzz") == 0.0

    def test_levenshtein_long_text_truncated_to_1000(self):
        # >1000 字符只比较前 1000；两段全 'a' 仍判为相等 -> 100.0
        assert levenshtein_similarity("a" * 1500, "a" * 1500) == 100.0
        # 前 1000 字符全不同 -> 距离 1000 -> 0.0
        assert levenshtein_similarity("a" * 1500, "b" * 1500) == 0.0

    # ---- cosine_similarity ----
    def test_cosine_exact(self):
        # 相同 -> 100.0
        assert cosine_similarity("hello", "hello") == 100.0
        # tokenizer 把连续字母合并成单 token，"hello"/"help" 各为一个不等的整体 token -> 0.0
        assert cosine_similarity("hello", "help") == 0.0
        assert cosine_similarity("hello", "zzzzz") == 0.0

    # ---- jaccard_similarity ----
    def test_jaccard_exact(self):
        assert jaccard_similarity("hello", "hello") == 100.0
        assert jaccard_similarity("hello", "help") == 0.0
        assert jaccard_similarity("hello", "zzzzz") == 0.0

    # ---- hybrid_similarity ----
    def test_hybrid_exact(self):
        assert hybrid_similarity("hello", "hello") == 100.0
        assert hybrid_similarity("hello", "help") == pytest.approx(26.666666666666668)
        assert hybrid_similarity("hello", "world") == pytest.approx(8.0)
        assert hybrid_similarity("hello", "zzzzz") == 0.0


# ---------------------------------------------------------------------------
# ⑥ 中文文本行为（锁定 tokenizer 的当前实际行为，含疑似 bug）
# ---------------------------------------------------------------------------

class TestChineseTextBehavior:
    """锁定 _tokenize 对中文的实际处理：连续中文被合并成单个长 token。"""

    def test_tokenize_merges_consecutive_chinese_into_one_token(self):
        # 疑似 bug：'一'.isalpha() == True，合并循环把整段中文聚成一个 token
        a = "今天天气真好我想出去玩"
        assert _tokenize(a) == ["今天天气真好我想出去玩"]
        assert len(_tokenize(a)) == 1

    def test_chinese_identical_all_methods_100(self):
        a = "今天天气真好我想出去玩"
        assert sequence_similarity(a, a) == 100.0
        assert cosine_similarity(a, a) == 100.0
        assert jaccard_similarity(a, a) == 100.0
        assert levenshtein_similarity(a, a) == 100.0
        assert hybrid_similarity(a, a) == 100.0

    def test_chinese_similar_text_cosine_jaccard_zero(self):
        # 疑似 bug 后果：仅末字不同的中文，cosine/jaccard 仍 0.0（各自单 token 不等）
        a = "今天天气真好我想出去玩"
        c = "今天天气真好我想出去打球"
        assert cosine_similarity(a, c) == 0.0
        assert jaccard_similarity(a, c) == 0.0
        # sequence / levenshtein 基于原始字符序列，能正确识别相似
        assert sequence_similarity(a, c) == pytest.approx(86.95652173913044)
        assert levenshtein_similarity(a, c) == pytest.approx(83.33333333333334)
        # hybrid = 0.4*86.957 + 0.4*0 + 0.2*0 = 34.783
        assert hybrid_similarity(a, c) == pytest.approx(34.78260869565218)

    def test_chinese_unrelated_all_zero(self):
        a = "今天天气真好我想出去玩"
        d = "完全不同的内容关于物理学"
        assert sequence_similarity(a, d) == 0.0
        assert cosine_similarity(a, d) == 0.0
        assert jaccard_similarity(a, d) == 0.0
        assert levenshtein_similarity(a, d) == 0.0
        assert hybrid_similarity(a, d) == 0.0


# ---------------------------------------------------------------------------
# ⑦ _tokenize 详细行为（辅助函数，但脆点集中）
# ---------------------------------------------------------------------------

class TestTokenizer:
    """锁定 _tokenize 的当前实际行为。"""

    def test_whitespace_dropped(self):
        # 循环逐字符，空白既非中文也非 alnum -> 直接被丢弃
        assert _tokenize("hello world") == ["helloworld"]
        assert _tokenize("abc def") == ["abcdef"]

    def test_letters_lowercased_and_merged(self):
        assert _tokenize("AbC") == ["abc"]

    def test_digits_kept_as_single_tokens(self):
        # 数字 isalnum 但非 isalpha：合并循环不合并数字，过滤后单字符数字被保留
        assert _tokenize("12a") == ["1", "2", "a"]

    def test_letters_and_digits_split(self):
        # 'AbC123' -> 合并得 ['abc','1','2','3'] -> 过滤掉单字符英文 -> ['abc']
        assert _tokenize("AbC123") == ["abc"]

    def test_single_letter_falls_back_to_unfiltered(self):
        # 疑似 bug 的"修复"：仅单英文字符时 filtered 为空，回退到 merged
        assert _tokenize("a") == ["a"]


# ---------------------------------------------------------------------------
# ⑧ ngram_similarity / find_similar_segments
# ---------------------------------------------------------------------------

class TestNgramSimilarity:
    def test_identical_100(self):
        assert ngram_similarity("hello", "hello") == 100.0

    def test_default_n3(self):
        # 默认 n=3：'hello'={hel,ell,llo}, 'help'={hel,elp} -> 交集{hel}=1, 并集4 -> 25.0
        assert ngram_similarity("hello", "help") == 25.0

    def test_n2(self):
        # n=2：'hello'={he,el,ll,lo}, 'help'={he,el,lp} -> 交集2, 并集5 -> 40.0
        assert ngram_similarity("hello", "help", 2) == 40.0

    def test_empty(self):
        assert ngram_similarity("", "hello") == 0.0

    def test_whitespace_cleaned(self):
        # ngram 内部也 re.sub(r'\s+','') 清洗
        assert ngram_similarity("he llo", "hello") == 100.0


class TestFindSimilarSegments:
    def test_identical_long_segments_detected(self):
        t = "这是一段很长的文本内容用来测试相似度检测算法的准确性需要超过最小长度阈值"
        res = find_similar_segments(t, t, threshold=80.0, min_length=10)
        assert len(res) == 1
        assert res[0]["similarity"] == 100.0
        assert res[0]["position1"] == 0
        assert res[0]["position2"] == 0

    def test_unrelated_returns_empty(self):
        t1 = "这是一段很长的文本内容用来测试相似度检测算法的准确性需要超过最小长度阈值"
        t2 = "完全不一样的另一段内容但是也要足够长才能被纳入比较范围"
        res = find_similar_segments(t1, t2, threshold=80.0, min_length=10)
        assert res == []

    def test_min_length_filters_short_sentences(self):
        # 短句（清洗后 strip 长度 < min_length）被跳过
        t1 = "短句。"
        t2 = "短句。"
        assert find_similar_segments(t1, t2, threshold=80.0, min_length=10) == []
