#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生端「打包预处理」单测
"""

import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

from tools.auto_grading.submission_processor import ProcessedSubmission
from tools.auto_grading.submission_validator import ValidationReport
from tools.auto_grading.grading_engine import GradingResult
from tools.student_submission_gui.self_checker import SelfCheckResult
from tools.student_submission_gui.id_card import StudentIdentity
from tools.student_submission_gui.submission_packager import (
    assess_gate, package_submission, PackagingError, outer_zip_has_clean_structure,
)


IDENT = StudentIdentity("汽服2302B班", "23071140224", "刘涛")


def _docx(path: Path, text: str = "实验目的 任务三 RTC 闹钟 状态机"):
    """最小合法 .docx：detect_report_format 只看前 8 字节(PK\x03\x04) → 'docx'。"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", f"<w:body><w:p>{text}</w:p></w:body>")
        zf.writestr("[Content_Types].xml", "<Types xmlns='x'/>")


def _pdf(path: Path):
    path.write_bytes(b"%PDF-1.4\n%test\n")


def _result(report_path, source_path=None, source_state="ok",
            source_state_reason="", warnings=None, validation=None) -> SelfCheckResult:
    sub = ProcessedSubmission(
        student_id=IDENT.student_id, name=IDENT.name, class_name=IDENT.class_name,
        report_path=report_path, source_path=source_path,
    )
    return SelfCheckResult(
        submission=sub,
        validation=validation or ValidationReport(),
        grading=GradingResult(student_id=IDENT.student_id, name=IDENT.name,
                              class_name=IDENT.class_name),
        warnings=warnings or [],
        source_state=source_state,
        source_state_reason=source_state_reason,
        source_state_fix="",
    )


# ---- 闸门 ----

def test_blocks_no_source(tmp_path):
    rep = tmp_path / "r.docx"; _docx(rep)
    r = _result(rep, source_path=None, source_state="not_submitted",
                source_state_reason="未找到源码工程（提交包里没有源码压缩包）")
    ok, blockers, _w = assess_gate(r, IDENT)
    assert not ok
    assert any("源码" in b for b in blockers)


def test_blocks_non_docx(tmp_path):
    rep = tmp_path / "r.pdf"; _pdf(rep)
    src = tmp_path / "src"; src.mkdir(); (src / "main.c").write_text("int main(){}")
    r = _result(rep, source_path=src, source_state="ok")
    ok, blockers, _w = assess_gate(r, IDENT)
    assert not ok
    assert any(".docx" in b for b in blockers)


def test_blocks_9digit_team_ids(tmp_path):
    rep = tmp_path / "r.docx"; _docx(rep)
    src = tmp_path / "src"; src.mkdir(); (src / "main.c").write_text("int main(){}")
    r = _result(rep, source_path=src, source_state="ok",
                warnings=["团队成员表里的学号位数不规范（检测到 230711402），应为 11 位。"])
    ok, blockers, _w = assess_gate(r, IDENT)
    assert not ok
    assert any("学号位数不规范" in b for b in blockers)


def test_passes_keil_only_with_warning(tmp_path):
    rep = tmp_path / "r.docx"; _docx(rep)
    src = tmp_path / "src"; src.mkdir(); (src / "main.c").write_text("int main(){}")
    r = _result(rep, source_path=src, source_state="keil_only", source_state_reason="纯Keil")
    ok, blockers, warnings = assess_gate(r, IDENT)
    assert ok and not blockers
    assert any("Keil" in w for w in warnings)


# ---- 打包 ----

def test_package_structure_flattens_nested(tmp_path):
    """聂智聪场景：源码包套两层包装目录 → 内层 source zip 应单层、Makefile 在根。"""
    rep = tmp_path / "r.docx"; _docx(rep)
    src = tmp_path / "src"
    proj = src / "QIMO" / "QIMO"          # 两层包装 + 真正工程根
    proj.mkdir(parents=True)
    (proj / "Makefile").write_text("all:\n\tarm-none-eabi-gcc\n")
    (proj / "Core" / "Src").mkdir(parents=True)
    (proj / "Core" / "Src" / "main.c").write_text("int main(void){return 0;}")
    r = _result(rep, source_path=src, source_state="ok")

    out = tmp_path / "out"
    zip_path = package_submission(r, IDENT, project_root=tmp_path, out_dir=out)

    # 外层恰 2 文件
    ok, issues = outer_zip_has_clean_structure(zip_path)
    assert ok, issues

    # 内层 source zip 解开后 Makefile 在根、无 QIMO/QIMO 嵌套
    with zipfile.ZipFile(zip_path) as zf:
        inner = [n for n in zf.namelist() if "源代码" in n and n.endswith(".zip")][0]
        zf.extract(inner, tmp_path / "extracted")
    with zipfile.ZipFile(tmp_path / "extracted" / inner) as zi:
        names = zi.namelist()
    assert any(n == "Makefile" for n in names), f"Makefile 未在根: {names}"
    assert not any("QIMO/QIMO" in n for n in names), f"嵌套未扁平化: {names}"


def test_rejects_after_cleanup(tmp_path):
    """source_path 被清理后再打包 → PackagingError（B6）。"""
    rep = tmp_path / "r.docx"; _docx(rep)
    src = Path(tempfile.mkdtemp())
    (src / "main.c").write_text("int main(){}")
    r = _result(rep, source_path=src, source_state="ok")
    ok, _b, _w = assess_gate(r, IDENT)
    assert ok                       # 清理前闸门通过
    shutil.rmtree(src, ignore_errors=True)
    with pytest.raises(PackagingError):
        package_submission(r, IDENT, project_root=tmp_path, out_dir=tmp_path / "out")
