#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase B：断点续跑 e2e（中断 → 续跑复用缓存 → 全到齐 → 清 checkpoint）。

验证 ObservableFacade.run_full_pipeline 的 checkpoint 行为：
- 取消/中断时已评学生落盘 _checkpoint/<学号>.json + batch_checkpoint.json(status=interrupted)；
- 续跑(resume_completed_ids)时跳过已完成、复用缓存、新评其余，最终全到齐；
- 成功完成后清掉 _checkpoint/。
"""

import types
from pathlib import Path
from unittest.mock import MagicMock

from tools.auto_grading import batch_checkpoint
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


def _make_of(facade, cancel_fn):
    of = object.__new__(ObservableFacade)
    of.config = facade.config
    of.stage_started = _Sig()
    of.stage_progress = _Sig()
    of.stage_completed = _Sig()
    of.log_message = _Sig()
    of.is_cancelled = cancel_fn
    of._cancel_event = None
    of.facade = facade
    return of


def _stub_facade(tmp_path, submissions, state):
    fac = MagicMock()
    engine = MagicMock()
    engine.rubric = {"experiment_name": "测"}
    engine.rubric_path = Path("rubric.json")
    engine.build_checker = MagicMock()
    fac._make_engine.return_value = engine

    def _grade(sub):
        state["graded"] += 1
        return GradingResult(student_id=sub.student_id, name=sub.name, class_name="C1")
    engine.grade_submission.side_effect = _grade
    engine.generate_class_report.return_value = {"average_score": 80.0, "grade_distribution": {"B": 2}}
    fac.processor.process_class_submissions.return_value = submissions
    fac.config = MagicMock()
    fac.config.get_output_dir.return_value = tmp_path
    fac.config.teaching_dir = tmp_path
    fac.config.semester = "2026-春季"
    return fac


def _patch_dedupe_roster(monkeypatch):
    import tools.auto_grading.grading_engine as ge_mod
    import tools.auto_grading.roster_check as rc_mod
    monkeypatch.setattr(ge_mod, "dedupe_team_members", lambda results, rubric=None: results)
    monkeypatch.setattr(rc_mod, "load_id_roster", lambda *a, **k: None)


def test_interrupt_then_resume(tmp_path, monkeypatch):
    """评 2 份后中断 → 续跑复用缓存 + 新评余下 → 全 4 份到齐 → checkpoint 清除。"""
    _patch_dedupe_roster(monkeypatch)
    subs = [_submission("001", "甲"), _submission("002", "乙"),
            _submission("003", "丙"), _submission("004", "丁")]
    state = {"graded": 0, "cancel_after": 2}

    # Run 1：评完 2 份后中断
    fac1 = _stub_facade(tmp_path, subs, state)
    of1 = _make_of(fac1, cancel_fn=lambda: state["graded"] >= state["cancel_after"])
    r1 = of1.run_full_pipeline(Path("z.zip"), "C1", "exp1", skip_organization=True)

    assert len(r1.grading_results) == 2  # 评了 2 份就被取消
    meta = batch_checkpoint.load_meta(tmp_path)
    assert meta is not None and meta["status"] == "interrupted"
    assert set(meta["completed_ids"]) == {"001", "002"}
    assert batch_checkpoint.load_result_cache(tmp_path, "001") is not None
    assert batch_checkpoint.load_result_cache(tmp_path, "002") is not None
    assert batch_checkpoint.load_result_cache(tmp_path, "003") is None  # 未评到

    # Run 2：续跑（001/002 复用缓存），不再取消
    state["cancel_after"] = 99
    fac2 = _stub_facade(tmp_path, subs, state)
    of2 = _make_of(fac2, cancel_fn=lambda: state["graded"] >= state["cancel_after"])
    r2 = of2.run_full_pipeline(
        Path("z.zip"), "C1", "exp1", skip_organization=True,
        resume_completed_ids={"001", "002"})

    assert len(r2.grading_results) == 4  # 2 缓存 + 2 新评
    assert {x.student_id for x in r2.grading_results} == {"001", "002", "003", "004"}
    # 成功完成 → checkpoint 清除
    assert batch_checkpoint.load_meta(tmp_path) is None
    assert batch_checkpoint.load_result_cache(tmp_path, "001") is None


def test_fresh_start_does_not_resume(tmp_path, monkeypatch):
    """全新开始（resume_completed_ids=None）即使有旧 checkpoint 也清掉、全量重评。"""
    _patch_dedupe_roster(monkeypatch)
    # 预置一个"中断"的旧 checkpoint（含一个缓存结果）
    batch_checkpoint.write_result_cache(
        tmp_path, GradingResult(student_id="001", name="旧甲", class_name="C1"))
    _meta = batch_checkpoint.new_meta("C1", "exp1", "2026-春季", 1)
    _meta["completed_ids"] = ["001"]
    batch_checkpoint.write_meta(tmp_path, _meta)
    assert batch_checkpoint.load_meta(tmp_path) is not None  # 旧 checkpoint 在

    subs = [_submission("001", "甲")]  # 同学号，全新应重评
    state = {"graded": 0, "cancel_after": 99}
    fac = _stub_facade(tmp_path, subs, state)
    of = _make_of(fac, cancel_fn=lambda: False)
    r = of.run_full_pipeline(Path("z.zip"), "C1", "exp1", skip_organization=True)  # resume=None

    # 全新开始：重评了 001（graded=1），且完成后清 checkpoint
    assert len(r.grading_results) == 1
    assert state["graded"] == 1  # 确实重评了（没走缓存跳过）
    assert batch_checkpoint.load_meta(tmp_path) is None


def test_resume_missing_cache_falls_through(tmp_path, monkeypatch):
    """续跑时某学号声称已完成但缓存缺失/损坏 → 落到正常重评，不丢学生。"""
    _patch_dedupe_roster(monkeypatch)
    subs = [_submission("001", "甲"), _submission("002", "乙")]
    state = {"graded": 0, "cancel_after": 99}
    fac = _stub_facade(tmp_path, subs, state)
    of = _make_of(fac, cancel_fn=lambda: False)
    # 声称 001 已完成，但没写 001 的缓存
    r = of.run_full_pipeline(
        Path("z.zip"), "C1", "exp1", skip_organization=True,
        resume_completed_ids={"001"})

    assert len(r.grading_results) == 2  # 001 缓存缺失→重评；002 正常评
    assert {x.student_id for x in r.grading_results} == {"001", "002"}
