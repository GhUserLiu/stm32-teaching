#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GradingService 单元测试（P2：管线编排从 GUI worker 上提到 services 层）。

覆盖：
- build_auto_grading_config 桥接与旧默认 1:1（含 MB->bytes、semester 覆盖、根路径锚定）
- _LogTee 同时支持 .emit（旧接口，test_log_tee 依赖）与直接调用（service 内部用法）
- ObservableFacade 兼容适配器：object.__new__ 注入桩门面后 run_full_pipeline 走 service
- GradingService.run_class：正常路径经 service 直调、取消时不落盘报告
- run_batch：缺压缩包跳过、续跑元数据读取与缓存复用、取消中断循环、facade_factory 注入
"""

import types
from pathlib import Path
from unittest.mock import MagicMock

from core.services.grading_service import (
    GradingService,
    ProgressCallbacks,
    _LogTee,
    build_auto_grading_config,
)
from tools.auto_grading import AutoGradingConfig
from tools.auto_grading.grading_engine import GradingResult
from tools.teaching_management_gui.workers.grading_worker import ObservableFacade


class _Sig:
    """Record emissions, mimicking a Qt signal."""

    def __init__(self):
        self.calls = []

    def emit(self, *a):
        self.calls.append(a)


def _submission(sid, name):
    s = types.SimpleNamespace()
    s.student_id = sid
    s.name = name
    return s


def _stub_facade(tmp_path, submissions, raise_ids=()):
    fac = MagicMock()
    engine = MagicMock()
    engine.rubric = {"experiment_name": "测试"}
    engine.rubric_path = Path("rubric.json")
    fac._make_engine.return_value = engine

    def _grade(sub):
        if sub.student_id in raise_ids:
            raise RuntimeError(f"boom-{sub.student_id}")
        return GradingResult(student_id=sub.student_id, name=sub.name, class_name="C1")

    engine.grade_submission.side_effect = _grade
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
    """dedupe / roster 改 no-op，聚焦编排逻辑本身（与既有测试同款补丁）。"""
    import tools.auto_grading.grading_engine as ge_mod
    import tools.auto_grading.roster_check as rc_mod
    monkeypatch.setattr(ge_mod, "dedupe_team_members", lambda results, rubric=None: results)
    monkeypatch.setattr(rc_mod, "load_id_roster", lambda *a, **k: None)


# ------------------------------------------------------------ config bridge

def test_build_config_parity_with_legacy_defaults():
    cfg = build_auto_grading_config(semester="2026-春季")
    legacy = AutoGradingConfig(project_root=Path.cwd(), semester="2026-春季")
    assert cfg.semester == legacy.semester == "2026-春季"
    t, lt = cfg.toolchain, legacy.toolchain
    assert (t.gcc_enabled, t.make_path, t.arm_none_eabi_prefix,
            t.keil_enabled, t.keil_uv4_path, t.build_timeout) == \
           (lt.gcc_enabled, lt.make_path, lt.arm_none_eabi_prefix,
            lt.keil_enabled, lt.keil_uv4_path, lt.build_timeout)
    p, lp = cfg.project, legacy.project
    assert p.allowed_projects == lp.allowed_projects
    assert p.project_types == lp.project_types
    s, ls = cfg.security, legacy.security
    assert s.max_zip_size == ls.max_zip_size == 100 * 1024 * 1024  # MB -> bytes
    assert s.max_file_count == ls.max_file_count
    assert s.allowed_extensions == ls.allowed_extensions
    assert (s.allow_absolute_paths, s.allow_parent_references) == \
           (ls.allow_absolute_paths, ls.allow_parent_references)


def test_build_config_project_root_anchored_to_repo_root():
    from schemas.config import CONFIG_DIR
    cfg = build_auto_grading_config()
    assert cfg.project_root == CONFIG_DIR.parent


# ------------------------------------------------------------------ log tee

def test_log_tee_supports_emit_and_call(tmp_path):
    sig = _Sig()
    tee = _LogTee(sig, tmp_path / "b.log")
    tee.emit("via emit")
    tee("via call")
    assert sig.calls == [("via emit",), ("via call",)]
    text = (tmp_path / "b.log").read_text(encoding="utf-8")
    assert "via emit" in text and "via call" in text


# --------------------------------------------------- ObservableFacade adapter

def _make_adapter(facade, cancelled=False):
    """与既有单测同款装配：object.__new__ 绕过 __init__，逐属性注入。"""
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


def test_adapter_routes_through_service(tmp_path, monkeypatch):
    _patch_dedupe_and_roster(monkeypatch)
    subs = [_submission("001", "甲"), _submission("002", "乙")]
    fac = _stub_facade(tmp_path, subs)
    of = _make_adapter(fac)

    result = of.run_full_pipeline(Path("dummy.zip"), "C1", "exp1", skip_organization=True)

    assert [r.student_id for r in result.grading_results] == ["001", "002"]
    assert result.failures == []
    # 信号经适配器透传（service → callbacks → Qt 信号面）
    assert ("analyze", "评分中") in of.stage_started.calls
    assert ("analyze", "评分中") in of.stage_started.calls
    assert any("阶段4" in c[0] for c in of.log_message.calls)
    assert any(c[0] == "analyze" for c in of.stage_completed.calls)
    # 持久化日志仍落盘
    assert "=== run started" in (tmp_path / "batch_run.log").read_text(encoding="utf-8")


def test_adapter_cancelled_skips_report(tmp_path, monkeypatch):
    _patch_dedupe_and_roster(monkeypatch)
    subs = [_submission("001", "甲")]
    fac = _stub_facade(tmp_path, subs)
    of = _make_adapter(fac, cancelled=True)

    result = of.run_full_pipeline(Path("d.zip"), "C1", "exp1", skip_organization=True)

    assert result.grading_results == []
    fac._save_reports.assert_not_called()
    fac.engine.grade_submission.assert_not_called()


# --------------------------------------------------------- GradingService 直调

def test_service_direct_happy_path(tmp_path, monkeypatch):
    _patch_dedupe_and_roster(monkeypatch)
    subs = [_submission("001", "甲")]
    fac = _stub_facade(tmp_path, subs)
    logs, stages = [], []
    cb = ProgressCallbacks(
        log=logs.append,
        stage_started=lambda sid, name: stages.append((sid, name)))
    svc = GradingService(fac.config, cb, facade=fac)

    result = svc.run_class(Path("d.zip"), "C1", "exp1", skip_organization=True)

    assert len(result.grading_results) == 1
    assert ("analyze", "评分中") in stages
    assert any("批阅完成" in m for m in logs)


# ------------------------------------------------------------------- run_batch

class _Entry:
    def __init__(self, cls, exp, zip_path):
        self.class_name = cls
        self.experiment_id = exp
        self.zip_path = zip_path


def test_run_batch_missing_zip_skipped(tmp_path):
    logs, prog = [], []
    cb = ProgressCallbacks(log=logs.append,
                           stage_progress=lambda *a: prog.append(a))
    svc = GradingService(MagicMock(), cb)
    entries = [_Entry("C1", "exp1", str(tmp_path / "nope.zip"))]

    results, failures = svc.run_batch(entries)

    assert results == [] and failures == []
    assert any("压缩包不存在" in m for m in logs)
    assert ("analyze", 1, 1) in prog


def test_run_batch_resume_reuses_checkpoint_cache(tmp_path, monkeypatch):
    from tools.auto_grading import batch_checkpoint as bc
    _patch_dedupe_and_roster(monkeypatch)

    # 预置 checkpoint：001 已完成并缓存其评分结果
    fac = _stub_facade(tmp_path, [_submission("001", "甲"), _submission("002", "乙")])
    meta = bc.new_meta("C1", "exp1", "2026-春季", 2)
    meta["completed_ids"] = ["001"]
    bc.write_meta(tmp_path, meta)
    bc.write_result_cache(tmp_path, GradingResult(student_id="001", name="甲", class_name="C1"))

    logs = []
    cb = ProgressCallbacks(log=logs.append)
    svc = GradingService(fac.config, cb)
    (tmp_path / "a.zip").write_text("", encoding="utf-8")

    results, failures = svc.run_batch([_Entry("C1", "exp1", str(tmp_path / "a.zip"))],
                                      resume=True,
                                      facade_factory=lambda cfg: fac)

    assert failures == []
    assert {r.student_id for r in results} == {"001", "002"}
    # 001 复用缓存，不再调 engine
    graded_ids = {c.args[0].student_id for c in fac.engine.grade_submission.call_args_list}
    assert graded_ids == {"002"}
    assert any("跳过已完成 1 人" in m for m in logs)
    assert any("复用缓存" in m for m in logs)


def test_run_batch_cancel_stops_after_current_class(tmp_path, monkeypatch):
    _patch_dedupe_and_roster(monkeypatch)
    state = {"cancelled": False}
    made = []

    def factory(cfg):
        fac = _stub_facade(tmp_path, [])
        made.append(fac)
        state["cancelled"] = True   # 第一班跑完即取消
        return fac

    cb = ProgressCallbacks(log=lambda m: None, is_cancelled=lambda: state["cancelled"])
    svc = GradingService(MagicMock(), cb)
    (tmp_path / "a.zip").write_text("", encoding="utf-8")
    (tmp_path / "b.zip").write_text("", encoding="utf-8")
    entries = [_Entry("C1", "exp1", str(tmp_path / "a.zip")),
               _Entry("C2", "exp2", str(tmp_path / "b.zip"))]

    results, failures = svc.run_batch(entries, facade_factory=factory)

    assert len(made) == 1   # 第二班未被处理
    assert results == [] and failures == []
