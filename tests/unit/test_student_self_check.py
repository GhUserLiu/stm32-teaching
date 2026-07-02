# -*- coding: utf-8 -*-
"""
学生端自检编排单元测试
Student Self-Check Unit Tests

覆盖本次更新的接线（G3 / G5 / G1-2）：
- G3：SelfChecker.run 必须把 source_state 喂给引擎——纯 Keil 工程判定为 keil_only 且
      编译走 FAILED（修复前因未传 source_state，引擎落入「兼容旧调用」分支一律 SKIPPED，
      学生误以为通过）。keil_only / not_submitted 两条路径都不调用 make，结果与工具链无关。
- G1/G2：非规范报告文件名 → warnings 含改名建议；规范名不报警。
- G5：_source_kind_label 按真实后缀区分 7z / zip（旧实现一律标 zip）。
"""

import sys
import types
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, "src")

from tools.auto_grading.build_checker import BuildStatus
from tools.student_submission_gui.self_checker import SelfChecker, build_status_of
from tools.student_submission_gui.self_check_report import _source_kind_label, result_to_dict
from tools.student_submission_gui.id_card import StudentIdentity


REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTITY = StudentIdentity(class_name="汽服2302B班", student_id="20230000001", name="张三")


# ---------------- 固件构造 ----------------

def _make_docx(path: Path, text: str = "实验报告占位内容。"):
    """用 python-docx 生成最小可读 .docx（未装 docx 则跳过调用方测试）。"""
    docx = pytest.importorskip("docx")
    doc = docx.Document()
    doc.add_paragraph(text)
    doc.save(str(path))


def _write_zip(path: Path, entries: dict) -> None:
    """entries: {压缩包内相对路径: 文本内容}。"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in entries.items():
            z.writestr(name, body)


def _keil_entries() -> dict:
    """纯 Keil 工程：有 MDK-ARM/.uvprojx，无 Makefile → keil_only。"""
    return {
        "proj/MDK-ARM/proj.uvprojx": "<Project/>",
        "proj/Core/main.c": "int main(void){return 0;}\n",
    }


@pytest.fixture
def checker(monkeypatch):
    """固定 bundle_root 到仓库根，保证 rubric 可解析（07-car-gear 回退 rubric.json）。"""
    monkeypatch.setattr(
        "tools.student_submission_gui.self_checker.bundle_root",
        lambda: REPO_ROOT,
    )
    return SelfChecker()


class _StubResult:
    """_source_kind_label 的最小桩：只读 submission.source_path / temp_dirs / archive_suffix。"""

    def __init__(self, source_path, temp_dirs, archive_suffix):
        self.submission = types.SimpleNamespace(source_path=source_path)
        self.temp_dirs = temp_dirs
        self.archive_suffix = archive_suffix


# ---------------- G3：source_state 接线 ----------------

class TestSourceStateWiring:

    def test_keil_only_classified_and_failed(self, tmp_path, checker):
        report = tmp_path / "汽服2302B班-20230000001-张三-实验报告.docx"
        _make_docx(report)
        src = tmp_path / "keil.zip"
        _write_zip(src, _keil_entries())

        try:
            result = checker.run(report, src, IDENTITY, "07-car-gear")

            assert result.source_state == "keil_only"
            assert result.archive_suffix == ".zip"
            assert result.source_state_reason.strip()
            assert "CubeMX" in result.source_state_fix or "Makefile" in result.source_state_fix
            # 引擎走真实分支：keil_only → FAILED（修复前会是 SKIPPED）。该分支不调用 make。
            assert build_status_of(result.grading) == BuildStatus.FAILED
        finally:
            SelfChecker.cleanup(result.temp_dirs)

    def test_no_source_is_not_submitted(self, tmp_path, checker):
        report = tmp_path / "汽服2302B班-20230000001-张三-实验报告.docx"
        _make_docx(report)

        result = checker.run(report, None, IDENTITY, "07-car-gear")
        try:
            assert result.source_state == "not_submitted"
            # 无源码 → FAILED（学生提交责任，0 分计入基数，不排除/不 rescale）。
            # 仅"有工程但本机缺工具链"才 SKIPPED（排除出总分，非学生责任）。
            assert build_status_of(result.grading) == BuildStatus.FAILED
        finally:
            SelfChecker.cleanup(result.temp_dirs)

    def test_result_dict_carries_source_state_and_warnings(self, tmp_path, checker):
        report = tmp_path / "汽服2302B班-20230000001-张三-实验报告.docx"
        _make_docx(report)
        src = tmp_path / "keil.zip"
        _write_zip(src, _keil_entries())

        result = checker.run(report, src, IDENTITY, "07-car-gear")
        try:
            d = result_to_dict(result)
            assert d["source_state"]["state"] == "keil_only"
            assert d["source_state"]["is_machine_buildable"] is False
            assert isinstance(d["warnings"], list)
        finally:
            SelfChecker.cleanup(result.temp_dirs)


# ---------------- G1/G2：报告文件名规范提示 ----------------

class TestFilenameWarning:

    def test_non_canonical_name_warns_with_suggestion(self, tmp_path, checker):
        report = tmp_path / "实验报告.docx"  # 非规范
        _make_docx(report)
        src = tmp_path / "keil.zip"
        _write_zip(src, _keil_entries())

        result = checker.run(report, src, IDENTITY, "07-car-gear")
        try:
            joined = "\n".join(result.warnings)
            assert "不符合提交规范" in joined
            assert "建议改名为" in joined
            assert "汽服2302B班-20230000001-张三-实验报告.docx" in joined
        finally:
            SelfChecker.cleanup(result.temp_dirs)

    def test_canonical_name_emits_no_filename_warning(self, tmp_path, checker):
        report = tmp_path / "汽服2302B班-20230000001-张三-实验报告.docx"
        _make_docx(report)
        src = tmp_path / "keil.zip"
        _write_zip(src, _keil_entries())

        result = checker.run(report, src, IDENTITY, "07-car-gear")
        try:
            assert not any("不符合提交规范" in w for w in result.warnings)
        finally:
            SelfChecker.cleanup(result.temp_dirs)


# ---------------- G5：7z / zip 标签 ----------------

class TestSourceKindLabel:

    def test_7z_label(self):
        r = _StubResult(Path("x.7z"), [Path("/tmp")], ".7z")
        assert _source_kind_label(r) == "7z（已解压）"

    def test_zip_label(self):
        r = _StubResult(Path("x.zip"), [Path("/tmp")], ".zip")
        assert _source_kind_label(r) == "zip（已解压）"

    def test_directory_label(self):
        r = _StubResult(Path("proj"), [], "")
        assert _source_kind_label(r) == "目录"

    def test_none_label(self):
        r = _StubResult(None, [], "")
        assert _source_kind_label(r) == "未提供"
