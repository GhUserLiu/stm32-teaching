#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase B：GradingResult 全保真 round-trip + checkpoint 读写。

关键：dedupe 的 ``_source_token`` 读 ``compilation_result.project_path``，既有
``serialize_details`` 会丢弃它。这里验证 batch_checkpoint 的独立 round-trip 能完整还原
（含 project_path、嵌套 BuildResult 的 details、ValidationReport.sections 等）。
"""

from pathlib import Path
from datetime import datetime

from tools.auto_grading.batch_checkpoint import (
    serialize_result, deserialize_result,
    write_result_cache, load_result_cache, clear_checkpoint, checkpoint_dir,
    write_meta, load_meta, new_meta, is_interrupted,
)
from tools.auto_grading.grading_engine import GradingResult, CategoryScore
from tools.auto_grading.build_checker import BuildResult, BuildStatus, BuildIssue
from tools.auto_grading.submission_validator import ValidationReport, ValidationIssue


def _sample_result() -> GradingResult:
    r = GradingResult(student_id="23071140108", name="张三", class_name="汽服2302B班")
    r.total_score = 78.5
    r.max_score = 100.0
    r.grade = "B"
    r.group_key = "23071140108"
    r.group_members = [("23071140108", "张三"), ("23071140109", "李四")]
    r.detected_task = "task1"
    r.difficulty_ratio = 0.8
    r.compilation_result = BuildResult(
        status=BuildStatus.SUCCESS,
        project_name="01-turn-signal",
        project_path=Path("data/teaching/2026-春季/汽服2302B班/final-project/source/23071140108"),
        success=True, duration=12.3, error_count=0, warning_count=2,
        issues=[BuildIssue(severity="warning", file="main.c", line=10, column=3, message="unused variable")],
        output="Build complete", error_message="",
    )
    r.category_scores = [
        CategoryScore(category_id="compilation", category_name="编译", max_points=10, earned_points=10.0,
                      details=[{"build_result": r.compilation_result, "note": "ok"}]),
        CategoryScore(category_id="code_quality", category_name="代码质量", max_points=15, earned_points=12.0, details=[]),
    ]
    r.validation_report = ValidationReport(
        passed=False,
        issues=[ValidationIssue(rule="R1", severity="warning", section="章节", message="缺思考题", fix="补")],
        sections={"摘要": "..."}, missing_questions=["Q3"],
    )
    r.issues = [{"type": "submission", "message": "x"}]
    r.thinking_check = [{"id": "Q1", "answered": True}]
    r.strengths = ["优点1"]
    r.weaknesses = ["缺点1"]
    r.graded_at = datetime(2026, 6, 30, 12, 0, 0)
    return r


def test_roundtrip_preserves_fields():
    r = _sample_result()
    r2 = deserialize_result(serialize_result(r))
    assert r2 is not None
    assert r2.student_id == r.student_id
    assert r2.total_score == r.total_score
    assert r2.grade == r.grade
    # tuple→list（JSON 无 tuple），但内容等价
    assert [list(t) for t in r.group_members] == r2.group_members
    assert r2.detected_task == r.detected_task
    assert r2.difficulty_ratio == r.difficulty_ratio
    # compilation_result 全保真（含 project_path —— _source_token 的关键依赖）
    assert r2.compilation_result is not None
    assert r2.compilation_result.project_path == r.compilation_result.project_path
    assert r2.compilation_result.status == BuildStatus.SUCCESS
    assert r2.compilation_result.issues[0].message == "unused variable"
    # category_scores.details 里嵌套的 BuildResult 也能还原
    cs0 = r2.category_scores[0]
    assert cs0.details[0]["note"] == "ok"
    assert isinstance(cs0.details[0]["build_result"], BuildResult)
    # validation_report 全保真（既有 to_dict 会丢 sections，这里不能丢）
    assert r2.validation_report is not None
    assert r2.validation_report.sections == {"摘要": "..."}
    assert r2.validation_report.missing_questions == ["Q3"]
    assert r2.graded_at == r.graded_at


def test_source_token_equivalent_after_roundtrip():
    """dedupe._source_token 读 compilation_result.project_path.name——round-trip 后必须等价。"""
    r = _sample_result()

    def token(rr):
        pp = getattr(rr.compilation_result, "project_path", None) if rr.compilation_result else None
        return Path(pp).name if pp else ""

    r2 = deserialize_result(serialize_result(r))
    assert token(r) == token(r2) == "23071140108"


def test_cache_write_load_clear(tmp_path):
    r = _sample_result()
    write_result_cache(tmp_path, r)

    loaded = load_result_cache(tmp_path, r.student_id)
    assert loaded is not None
    assert loaded.student_id == r.student_id
    assert loaded.compilation_result.project_path == r.compilation_result.project_path

    assert load_result_cache(tmp_path, "nonexistent") is None  # 未缓存
    assert checkpoint_dir(tmp_path).exists()

    clear_checkpoint(tmp_path)
    assert not checkpoint_dir(tmp_path).exists()
    assert load_result_cache(tmp_path, r.student_id) is None


def test_corrupt_cache_returns_none(tmp_path):
    """损坏的缓存文件不应崩，当作未缓存（调用方重批）。"""
    import json
    cp = checkpoint_dir(tmp_path) / "bad.json"
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text("not a json {", encoding="utf-8")
    assert load_result_cache(tmp_path, "bad") is None


def test_meta_interrupted_semantics(tmp_path):
    m = new_meta("C1", "exp1", "2026-春季", 40)
    assert is_interrupted(m) is False  # completed_ids 为空 → 不算可续
    m["completed_ids"].append("001")
    write_meta(tmp_path, m)
    loaded = load_meta(tmp_path)
    assert loaded is not None
    assert loaded["completed_ids"] == ["001"]
    assert is_interrupted(loaded) is True
    # 标记 completed 后不再算 interrupted
    m["status"] = "completed"
    assert is_interrupted(m) is False
