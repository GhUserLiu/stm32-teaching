# -*- coding: utf-8 -*-
"""
源码工程状态分类器单元测试
Source State Classifier Unit Tests

每种格式问题必须给出**具体原因 + 具体改进方法**，且原因/改进不含空串。
"""

import sys

import pytest

sys.path.insert(0, "src")

from tools.auto_grading.source_state import (
    SourceStateClassifier as SC,
    SourceState,
    STATE_OK, STATE_KEIL_ONLY, STATE_EMPTY, STATE_NOT_SUBMITTED,
    STATE_CORRUPTED, STATE_NESTED_ARCHIVE,
)


def _make_gcc_project(d):
    d.mkdir(parents=True, exist_ok=True)
    (d / "Makefile").write_text("all:\n", encoding="utf-8")
    (d / "Core").mkdir()
    return d


def _make_keil_project(d):
    d.mkdir(parents=True, exist_ok=True)
    (d / "MDK-ARM").mkdir()
    (d / "MDK-ARM" / "proj.uvprojx").write_text("x", encoding="utf-8")
    (d / "Core").mkdir()
    return d


class TestClassifyStates:
    def test_ok_gcc_project(self, tmp_path):
        _make_gcc_project(tmp_path)
        s = SC.classify(tmp_path)
        assert s.state == STATE_OK
        assert s.is_machine_buildable is True
        assert s.is_format_problem is False

    def test_keil_only(self, tmp_path):
        _make_keil_project(tmp_path)
        s = SC.classify(tmp_path)
        assert s.state == STATE_KEIL_ONLY
        assert s.is_machine_buildable is False
        # 判 0（FAILED，计入）的关键改进方法必须具体：提到 CubeMX / Makefile
        assert "CubeMX" in s.feedback_fix or "Makefile" in s.feedback_fix

    def test_empty_dir(self, tmp_path):
        s = SC.classify(tmp_path)  # 空目录
        assert s.state == STATE_EMPTY
        assert s.is_machine_buildable is False

    def test_not_submitted_missing_dir(self, tmp_path):
        s = SC.classify(tmp_path / "nope")
        assert s.state == STATE_NOT_SUBMITTED

    def test_none_path(self):
        s = SC.classify(None)
        assert s.state == STATE_NOT_SUBMITTED

    def test_corrupted_from_extraction_error(self, tmp_path):
        s = SC.classify(tmp_path, extraction_error="ZIP验证失败: File is not a zip file")
        assert s.state == STATE_CORRUPTED
        assert s.is_machine_buildable is False

    def test_corrupted_7z_renamed(self, tmp_path):
        s = SC.classify(tmp_path, extraction_error="解压 7z 失败: ...")
        assert s.state == STATE_CORRUPTED

    def test_nested_archive_dir_contains_only_zip(self, tmp_path):
        # 解压出来仍是压缩包（zip 套 7z 的结果）
        (tmp_path / "inner.7z").write_text("x", encoding="utf-8")
        s = SC.classify(tmp_path)
        assert s.state == STATE_NESTED_ARCHIVE

    def test_gcc_project_wins_over_archives_when_mixed(self, tmp_path):
        # 顶层既有 Makefile 又有别的文件 → 仍判 ok
        _make_gcc_project(tmp_path)
        (tmp_path / "README.md").write_text("x", encoding="utf-8")
        s = SC.classify(tmp_path)
        assert s.state == STATE_OK


class TestFeedbackNonEmpty:
    """所有格式问题状态必须有非空、具体的原因与改进方法。"""

    def _check(self, s):
        assert s.is_format_problem
        assert s.feedback_reason.strip(), f"原因空: state={s.state}"
        assert s.feedback_fix.strip(), f"改进方法空: state={s.state}"
        assert len(s.feedback_fix) > 10, f"改进方法太短(不够具体): {s.feedback_fix}"

    def test_keil_feedback(self, tmp_path):
        _make_keil_project(tmp_path)
        self._check(SC.classify(tmp_path))

    def test_empty_feedback(self, tmp_path):
        # tmp_path 是空目录
        self._check(SC.classify(tmp_path))

    def test_corrupted_feedback(self, tmp_path):
        self._check(SC.classify(tmp_path, extraction_error="File is not a zip file"))

    def test_nested_feedback(self, tmp_path):
        (tmp_path / "inner.7z").write_text("x", encoding="utf-8")
        self._check(SC.classify(tmp_path))

    def test_not_submitted_feedback(self, tmp_path):
        self._check(SC.classify(tmp_path / "nope"))

    def test_keil_fix_mentions_concrete_steps(self, tmp_path):
        _make_keil_project(tmp_path)
        s = SC.classify(tmp_path)
        assert "CubeMX" in s.feedback_fix
        assert "Makefile" in s.feedback_fix
