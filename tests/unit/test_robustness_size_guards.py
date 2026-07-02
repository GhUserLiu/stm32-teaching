#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""健壮性：无界读尺寸护栏（防超大学生文件导致 OOM）。

审计 confirmed：_read_report 把整篇 docx read() 进内存后才做尺寸校验、
_makefile_c_sources / 主文件读取无前置尺寸校验——一个超大 docx/Makefile/main.c
就能让批阅进程 OOM 崩溃。这批测试锁定三处 stat() 预检护栏生效。
"""

import tools.auto_grading.grading_engine as ge
from tools.auto_grading.submission_processor import SubmissionProcessor
from tools.security.zip_validator import ZipLimits


def test_read_report_skips_oversize_docx(tmp_path, monkeypatch):
    """_read_report 对超过 max_inner_size 的 docx 先 stat 预检、不 read() 进内存。"""
    monkeypatch.setattr(ZipLimits, "max_inner_size", 100)
    docx = tmp_path / "report.docx"
    docx.write_bytes(b"x" * 200)  # 200 > 100 上限

    proc = SubmissionProcessor(tmp_path)
    assert proc._read_report(docx) == ""  # 跳过，未触发 read()


def test_read_report_allows_normal_size(tmp_path, monkeypatch):
    """正常小 docx 不被预检误拦（走到 safe_extract，返回 str 不崩溃）。"""
    monkeypatch.setattr(ZipLimits, "max_inner_size", 10 * 1024)
    docx = tmp_path / "report.docx"
    docx.write_bytes(b"PK\x03\x04" + b"\x00" * 50)  # 小文件、内容为伪 docx

    proc = SubmissionProcessor(tmp_path)
    result = proc._read_report(docx)
    assert isinstance(result, str)  # 未被 OOM 预检拦截


def test_makefile_c_sources_skips_oversize(tmp_path, monkeypatch):
    """_makefile_c_sources 对超大 Makefile 直接返回空集，不 read_text。"""
    monkeypatch.setattr(ge, "MAX_FILE_BYTES", 50)
    (tmp_path / "Makefile").write_bytes(b"M := 1\n" * 20)  # 100 bytes > 50

    assert ge._makefile_c_sources(tmp_path) == set()


def test_makefile_c_sources_parses_normal(tmp_path, monkeypatch):
    """正常 Makefile 仍能解析出 C_SOURCES（护栏不破坏正常解析）。"""
    monkeypatch.setattr(ge, "MAX_FILE_BYTES", 50)
    (tmp_path / "Makefile").write_text(
        "C_SOURCES += \\\n  Core/foo.c \\\n  Drivers/bar.c\n", encoding="utf-8")

    srcs = ge._makefile_c_sources(tmp_path)
    assert "Core/foo.c" in srcs
    assert "Drivers/bar.c" in srcs
