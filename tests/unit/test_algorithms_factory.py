#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BaseSimilarityChecker 契约与 SimilarityCheckerFactory 注册表单测（P3）。

覆盖：抽象类不可实例化、注册生命周期（重复/抽象/非子类/空名字拒绝、
replace 覆盖、装饰器形式）、create 选项透传、score 钳制、默认预清洗
（去空白，与 legacy compute_similarity 一致）、compare_matrix 形状/对称/
对角线/每文档只预处理一次、按模态过滤（ANY 计入两侧）。
"""

import pytest

from algorithms.base import (
    BaseSimilarityChecker,
    ContentKind,
    collapse_whitespace,
)
from algorithms.factory import SimilarityCheckerFactory, register_checker


# ------------------------------------------------------------------ dummies

class _RecordingChecker(BaseSimilarityChecker):
    """Deterministic: 100 if equal after preprocess, else 42. Records calls."""

    name = "dummy-record"
    kind = ContentKind.ANY

    def __init__(self, **options):
        super().__init__(**options)
        self.preprocess_calls = []
        self.compare_calls = []

    def preprocess(self, text):
        self.preprocess_calls.append(text)
        return collapse_whitespace(text)

    def compare(self, left, right):
        self.compare_calls.append((left, right))
        return 100.0 if left == right else 42.0


class _ClampChecker(BaseSimilarityChecker):
    """Always returns a fixed value -- used to prove score() clamping."""

    name = "dummy-clamp"
    kind = ContentKind.TEXT

    def __init__(self, value=0.0, **options):
        super().__init__(**options)
        self._value = value

    def compare(self, left, right):
        return self._value


class _CodeDummy(BaseSimilarityChecker):
    name = "dummy-code"
    kind = ContentKind.CODE

    def preprocess(self, text):
        return text   # passthrough: avoids the CODE-without-override warning

    def compare(self, left, right):
        return 0.0


class _PlainChecker(BaseSimilarityChecker):
    """NO preprocess override -- exercises the base default."""

    name = "dummy-plain"
    kind = ContentKind.TEXT

    def compare(self, left, right):
        return 100.0 if left == right else 0.0


class _ImageDummy(BaseSimilarityChecker):
    name = "dummy-image"
    kind = ContentKind.IMAGE

    def compare(self, left, right):
        return 0.0


_DUMMIES = (_RecordingChecker, _ClampChecker, _CodeDummy,
            _PlainChecker, _ImageDummy)


@pytest.fixture()
def registered_dummies():
    for cls in _DUMMIES:
        SimilarityCheckerFactory.register(cls, replace=True)
    yield
    for cls in _DUMMIES:
        SimilarityCheckerFactory.unregister(cls.name)


# ------------------------------------------------------------- base contract

def test_base_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseSimilarityChecker()


def test_score_clamps_out_of_range():
    checker = _ClampChecker(value=150.0)
    assert checker.score("a", "b") == 100.0
    assert _ClampChecker(value=-5.0).score("a", "b") == 0.0


def test_nan_maps_to_zero_not_perfect_score():
    # min/max clamp lets NaN through as 100.0 -- clamp_score must not
    checker = _ClampChecker(value=float("nan"))
    assert checker.score("a", "b") == 0.0


def test_empty_input_scores_zero_on_all_paths():
    checker = _PlainChecker()
    assert checker.score("", "abc") == 0.0
    assert checker.score("   \t\n", "abc") == 0.0   # preprocesses to empty
    assert checker.compare_pairs([("", ""), ("ab", "ab")]) == [0.0, 100.0]


def test_base_default_preprocess_strips_all_whitespace():
    # _PlainChecker does NOT override preprocess -- this exercises the base
    # default (the earlier _RecordingChecker test only proved its own override)
    checker = _PlainChecker()
    assert checker.score("a b\tc\n", "abc") == 100.0


def test_compare_pairs_preprocesses_each_document_once():
    checker = _RecordingChecker()
    scores = checker.compare_pairs([("a", "b"), ("a", "c"), ("b", "a")])
    assert scores == [42.0, 42.0, 42.0]
    # 3 distinct documents -> 3 preprocess calls, not 2 per pair
    assert len(checker.preprocess_calls) == 3


def test_matrix_shape_symmetric_diagonal_and_once_preprocess():
    checker = _RecordingChecker()
    matrix = checker.compare_matrix(["aa", "aa", "zz"])

    assert len(matrix) == 3
    assert all(len(row) == 3 for row in matrix)
    assert all(matrix[i][i] == 100.0 for i in range(3))
    assert matrix[0][1] == 100.0
    assert matrix[0][2] == 42.0
    assert matrix[0][2] == matrix[2][0]
    # The perf lesson: each document preprocessed exactly ONCE, not per pair
    assert len(checker.preprocess_calls) == 3


def test_matrix_empty_document_diagonal_is_zero():
    # An empty doc is not similar even to itself (central empty guard)
    matrix = _PlainChecker().compare_matrix(["", "ab"])
    assert matrix[0][0] == 0.0
    assert matrix[1][1] == 100.0
    assert matrix[0][1] == 0.0 and matrix[1][0] == 0.0


# ---------------------------------------------------------------- registry

def test_register_and_create_roundtrip(registered_dummies):
    checker = SimilarityCheckerFactory.create("dummy-record")
    assert isinstance(checker, _RecordingChecker)
    assert checker.score("abc", "abc") == 100.0
    assert checker.score("abc", "xyz") == 42.0


def test_create_passes_options_through(registered_dummies):
    checker = SimilarityCheckerFactory.create("dummy-clamp", value=99.0)
    assert checker.score("x", "y") == 99.0


def test_duplicate_registration_rejected(registered_dummies):
    with pytest.raises(ValueError, match="already registered"):
        SimilarityCheckerFactory.register(_RecordingChecker)


def test_replace_allows_override(registered_dummies):
    SimilarityCheckerFactory.register(_RecordingChecker, replace=True)
    assert SimilarityCheckerFactory.is_registered("dummy-record")


def test_abstract_class_rejected():
    class _Abstract(BaseSimilarityChecker):
        name = "dummy-abstract"
        # no compare() implementation

    with pytest.raises(TypeError, match="abstract"):
        SimilarityCheckerFactory.register(_Abstract)


def test_non_subclass_rejected():
    with pytest.raises(TypeError, match="BaseSimilarityChecker"):
        SimilarityCheckerFactory.register(object)


def test_empty_name_rejected():
    class _NoName(BaseSimilarityChecker):
        # name intentionally left as the base default ""
        def compare(self, left, right):
            return 0.0

    with pytest.raises(ValueError, match="non-empty"):
        SimilarityCheckerFactory.register(_NoName)


def test_invalid_kind_rejected():
    class _BadKind(BaseSimilarityChecker):
        name = "dummy-badkind"
        kind = "code"   # str, not ContentKind -- must fail loudly

        def compare(self, left, right):
            return 0.0

    with pytest.raises(ValueError, match="invalid kind"):
        SimilarityCheckerFactory.register(_BadKind)


def test_unknown_name_error_lists_available(registered_dummies):
    with pytest.raises(KeyError, match="dummy-record"):
        SimilarityCheckerFactory.create("nope")


# ------------------------------------------------------------- modality split

def test_names_filtered_by_kind_including_any(registered_dummies):
    text_names = SimilarityCheckerFactory.names(ContentKind.TEXT)
    assert "dummy-record" in text_names      # ANY counts for both sides
    assert "dummy-clamp" in text_names
    assert "dummy-code" not in text_names
    assert "dummy-image" not in text_names   # IMAGE never leaks into TEXT

    code_names = SimilarityCheckerFactory.names(ContentKind.CODE)
    assert "dummy-record" in code_names
    assert "dummy-code" in code_names
    assert "dummy-clamp" not in code_names
    assert "dummy-image" not in code_names

    image_names = SimilarityCheckerFactory.names(ContentKind.IMAGE)
    assert image_names == ["dummy-image"]    # exact match only, ANY excluded


def test_create_for_kind_returns_any_plus_own(registered_dummies):
    # Subset assertions on purpose: the registry is process-global and the
    # upcoming real adapters (import-time @register_checker) will add more
    # TEXT/ANY engines -- exact-set equality would be a time bomb.
    engines = SimilarityCheckerFactory.create_for_kind(ContentKind.TEXT)
    names = {type(e).__name__ for e in engines}
    assert {"_RecordingChecker", "_ClampChecker"} <= names
    assert "_CodeDummy" not in names
    assert "_ImageDummy" not in names

    code_engines = SimilarityCheckerFactory.create_for_kind(ContentKind.CODE)
    code_names = {type(e).__name__ for e in code_engines}
    assert {"_RecordingChecker", "_CodeDummy"} <= code_names
    assert "_ClampChecker" not in code_names


# ------------------------------------------------------------- lifecycle

def test_unregister_removes_registration(registered_dummies):
    assert SimilarityCheckerFactory.is_registered("dummy-code")
    SimilarityCheckerFactory.unregister("dummy-code")
    assert not SimilarityCheckerFactory.is_registered("dummy-code")
    with pytest.raises(KeyError):
        SimilarityCheckerFactory.create("dummy-code")


def test_code_checker_without_preprocess_override_warns():
    class _BareCode(BaseSimilarityChecker):
        name = "dummy-barecode"
        kind = ContentKind.CODE
        # no preprocess override -> the // comment hazard warning

        def compare(self, left, right):
            return 0.0

    try:
        with pytest.warns(UserWarning, match="preprocess"):
            SimilarityCheckerFactory.register(_BareCode)
    finally:
        SimilarityCheckerFactory.unregister("dummy-barecode")


def test_decorator_form_registers_and_returns_class():
    @register_checker
    class _Decorated(BaseSimilarityChecker):
        name = "dummy-decorated"
        kind = ContentKind.TEXT

        def compare(self, left, right):
            return 0.0

    try:
        assert SimilarityCheckerFactory.is_registered("dummy-decorated")
        # Decorator must return the class unchanged (name binding intact)
        assert _Decorated.name == "dummy-decorated"
        engine = SimilarityCheckerFactory.create("dummy-decorated")
        assert isinstance(engine, _Decorated)
    finally:
        SimilarityCheckerFactory.unregister("dummy-decorated")
