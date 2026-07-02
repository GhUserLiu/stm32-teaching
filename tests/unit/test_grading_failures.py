#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ObservableFacade.run_full_pipeline 的 per-student 失败收集（修「静默丢学生」）。

验证：单生评分异常时，该生被收集进 PipelineResult.failures（含学号/姓名/原因），
其余学生继续评分、不中断整批。
"""

import types
from pathlib import Path
from unittest.mock import MagicMock

from tools.auto_grading.grading_engine import GradingResult
from tools.teaching_management_gui.workers.grading_worker import ObservableFacade


class _Sig:
    def __init__(self):
        self.calls = []

    def emit(self, *a):
        self.calls.append(a)


def _submission(sid, name):
    s = types.SimpleNamespace()
    s.student_id = sid
    s.name = name
    return s


def _make_of(facade, cancelled=False):
    """绕过 __init__（避免构造真实 AutoGradingFacade），直接装一个 ObservableFacade。"""
    of = object.__new__(ObservableFacade)
    of.config = facade.config
    of.stage_started = _Sig()
    of.stage_progress = _Sig()
    of.stage_completed = _Sig()
    of.log_message = _Sig()
    of.is_cancelled = lambda: cancelled
    of._cancel_event = None
    of.facade = facade
    return of


def _stub_facade(tmp_path, submissions, raise_ids):
    fac = MagicMock()
    engine = MagicMock()
    engine.rubric = {"experiment_name": "测试"}
    engine.rubric_path = Path("rubric.json")
    engine.build_checker = MagicMock()
    fac._make_engine.return_value = engine

    def _grade(sub):
        if sub.student_id in raise_ids:
            raise RuntimeError(f"boom-{sub.student_id}")
        return GradingResult(student_id=sub.student_id, name=sub.name, class_name="C1")

    engine.grade_submission.side_effect = _grade
    # generate_class_report 返回真实 dict（run_full_pipeline 会对 average_score 取 :.1f）
    engine.generate_class_report.return_value = {
        "average_score": 80.0,
        "grade_distribution": {"B": 2},
    }
    fac.processor.process_class_submissions.return_value = submissions
    fac.config = MagicMock()
    fac.config.get_output_dir.return_value = tmp_path
    fac.config.teaching_dir = tmp_path
    fac.config.semester = "2026-春季"
    return fac


def _patch_dedupe_and_roster(monkeypatch):
    """dedupe / roster 改 no-op，聚焦失败收集逻辑本身。"""
    import tools.auto_grading.grading_engine as ge_mod
    import tools.auto_grading.roster_check as rc_mod
    monkeypatch.setattr(ge_mod, "dedupe_team_members", lambda results, rubric=None: results)
    monkeypatch.setattr(rc_mod, "load_id_roster", lambda *a, **k: None)


def test_failures_collected_not_dropped(tmp_path, monkeypatch):
    _patch_dedupe_and_roster(monkeypatch)
    subs = [_submission("001", "甲"), _submission("002", "乙"), _submission("003", "丙")]
    fac = _stub_facade(tmp_path, subs, raise_ids={"002"})
    of = _make_of(fac)

    result = of.run_full_pipeline(Path("dummy.zip"), "C1", "exp1", skip_organization=True)

    # 失败的那生被收集进 failures（不再静默丢失）
    assert len(result.failures) == 1
    f = result.failures[0]
    assert f["student_id"] == "002"
    assert f["name"] == "乙"
    assert f["class_name"] == "C1"
    assert f["experiment_id"] == "exp1"
    assert "boom-002" in f["error"]
    assert f["stage"] == "analyze"
    # 另外两生正常评分，整批未被异常中断
    assert len(result.grading_results) == 2
    assert {r.student_id for r in result.grading_results} == {"001", "003"}


def test_multiple_failures_all_collected(tmp_path, monkeypatch):
    _patch_dedupe_and_roster(monkeypatch)
    subs = [_submission("001", "甲"), _submission("002", "乙"), _submission("003", "丙"), _submission("004", "丁")]
    fac = _stub_facade(tmp_path, subs, raise_ids={"002", "004"})
    of = _make_of(fac)

    result = of.run_full_pipeline(Path("dummy.zip"), "C1", "exp1", skip_organization=True)

    assert len(result.failures) == 2
    failed_ids = {f["student_id"] for f in result.failures}
    assert failed_ids == {"002", "004"}
    assert len(result.grading_results) == 2
    assert {r.student_id for r in result.grading_results} == {"001", "003"}


def test_no_failures_when_all_succeed(tmp_path, monkeypatch):
    _patch_dedupe_and_roster(monkeypatch)
    subs = [_submission("001", "甲"), _submission("002", "乙")]
    fac = _stub_facade(tmp_path, subs, raise_ids=set())
    of = _make_of(fac)

    result = of.run_full_pipeline(Path("dummy.zip"), "C1", "exp1", skip_organization=True)

    assert result.failures == []
    assert len(result.grading_results) == 2


def test_persistent_log_written(tmp_path, monkeypatch):
    """run_full_pipeline 同时把日志 tee 到 results/grading/batch_run.log（A3）。"""
    _patch_dedupe_and_roster(monkeypatch)
    subs = [_submission("001", "甲"), _submission("002", "乙")]
    fac = _stub_facade(tmp_path, subs, raise_ids={"002"})
    of = _make_of(fac)

    of.run_full_pipeline(Path("dummy.zip"), "C1", "exp1", skip_organization=True)

    log = (tmp_path / "batch_run.log").read_text(encoding="utf-8")
    assert "=== run started" in log and "C1 / exp1" in log
    assert "评分" in log
    assert "boom-002" in log  # 失败原因落盘
