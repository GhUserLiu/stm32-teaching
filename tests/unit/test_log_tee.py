#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_LogTee：log_message 信号同时 tee 到 results/grading/batch_run.log 的单元测试。"""

from pathlib import Path

from tools.teaching_management_gui.workers.grading_worker import _LogTee


class _StubSignal:
    def __init__(self):
        self.emitted = []

    def emit(self, msg):
        self.emitted.append(msg)


def test_log_tee_writes_timestamped_line_and_emits(tmp_path):
    sig = _StubSignal()
    log_path = tmp_path / "batch_run.log"
    tee = _LogTee(sig, log_path)

    tee.emit("评分 (1/3): 23071140108-张三")

    # 信号照常发出
    assert sig.emitted == ["评分 (1/3): 23071140108-张三"]
    # 文件落盘，带 [YYYY-MM-DD HH:MM:SS] 时间戳前缀，以换行结尾
    text = log_path.read_text(encoding="utf-8")
    assert "[20" in text
    assert "评分 (1/3): 23071140108-张三" in text
    assert text.endswith("\n")


def test_log_tee_appends_multiple_lines(tmp_path):
    sig = _StubSignal()
    log_path = tmp_path / "batch_run.log"
    tee = _LogTee(sig, log_path)

    tee.emit("line A")
    tee.emit("line B")

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert any("line A" in ln for ln in lines)
    assert any("line B" in ln for ln in lines)
    assert len(sig.emitted) == 2


def test_log_tee_bad_path_does_not_suppress_signal(tmp_path):
    # 日志父目录不存在（open 不 mkdir）→ 写盘失败，但信号仍必须发出：
    # 日志故障绝不能拖垮批阅主流程。
    sig = _StubSignal()
    bad_path = tmp_path / "nonexistent_subdir" / "x.log"  # 父目录缺失，open('a') 会失败
    tee = _LogTee(sig, bad_path)

    tee.emit("still emits")

    assert sig.emitted == ["still emits"]
    assert not bad_path.exists()
