# -*- coding: utf-8 -*-
"""批阅断点续跑：checkpoint 读写 + GradingResult 全保真 round-trip。

落盘位置 ``results/grading/_checkpoint/``：
- ``batch_checkpoint.json`` —— 批次元数据：``{class, experiment, semester, total,
  completed_ids:[...], failed_ids:[...], status: interrupted|completed, started_at, updated_at}``
- ``<学号>.json`` —— 该生 ``GradingResult`` 的全保真序列化（**含 compilation_result.project_path**，
  供 ``dedupe_team_members._source_token`` 复用——既有 ``serialize_details`` 会丢弃 project_path，
  故这里独立实现 round-trip）。

成功完成批阅后由 ``facade._save_reports`` 调 ``clear_checkpoint`` 清掉整个 ``_checkpoint/`` 目录，
保持 ``results/grading/`` 干净。崩溃/取消时 ``status=interrupted`` 落盘，下次「开始批阅」检测到后
提示续跑。

序列化用 type-tagged dict（``__type__``/``__path__``/``__buildstatus__``/``__datetime__``）递归处理
嵌套 ``BuildResult``/``BuildIssue``/``CategoryScore``/``ValidationReport``/``ValidationIssue`` +
``Path``/``Enum``/``datetime``。``from_dict`` 对未知字段容错（代码版本演进后旧 checkpoint 不崩，
fallback 由调用方重新批阅）。
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from tools.common import atomic_write_json
from .build_checker import BuildIssue, BuildResult, BuildStatus
from .grading_engine import CategoryScore, GradingResult
from .submission_validator import ValidationIssue, ValidationReport

CHECKPOINT_DIRNAME = "_checkpoint"
CHECKPOINT_META = "batch_checkpoint.json"

# GradingResult 需 round-trip 的字段（与 grading_engine.GratingResult 声明保持一致）
_RESULT_FIELDS = (
    "student_id", "name", "class_name",
    "total_score", "max_score", "bonus_total", "is_team_leader", "leader_bonus_granted", "grade",
    "group_key", "group_members", "group_submitter_count", "group_reporter_count",
    "detected_task", "detected_task_name", "detected_task_source", "detected_task_ambiguous",
    "evaluation_score", "difficulty_ratio", "task_full_marks",
    "category_scores", "compilation_result", "code_analysis", "report_analysis",
    "validation_report", "issues", "thinking_check",
    "strengths", "weaknesses", "suggestions", "graded_at",
)


def checkpoint_dir(grading_dir: Any) -> Path:
    return Path(grading_dir) / CHECKPOINT_DIRNAME


# ---------------- 全保真序列化 ----------------
def _ser(v: Any) -> Any:
    """递归把评分对象转 JSON-safe 结构（type-tagged，可完整还原）。"""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, Path):
        return {"__path__": str(v)}
    if isinstance(v, BuildStatus):
        return {"__buildstatus__": v.name}
    if isinstance(v, datetime):
        return {"__datetime__": v.isoformat()}
    if isinstance(v, BuildIssue):
        return {"__type__": "BuildIssue",
                **{k: _ser(getattr(v, k)) for k in ("severity", "file", "line", "column", "message")}}
    if isinstance(v, BuildResult):
        return {"__type__": "BuildResult", **{k: _ser(getattr(v, k)) for k in (
            "status", "project_name", "project_path", "success", "duration",
            "error_count", "warning_count", "issues", "output", "error_message")}}
    if isinstance(v, CategoryScore):
        return {"__type__": "CategoryScore", **{k: _ser(getattr(v, k)) for k in (
            "category_id", "category_name", "max_points", "earned_points", "details")}}
    if isinstance(v, ValidationIssue):
        return {"__type__": "ValidationIssue", **{k: _ser(getattr(v, k)) for k in (
            "rule", "severity", "section", "message", "fix")}}
    if isinstance(v, ValidationReport):
        return {"__type__": "ValidationReport", **{k: _ser(getattr(v, k)) for k in (
            "passed", "issues", "sections", "missing_questions")}}
    if isinstance(v, GradingResult):
        return {"__type__": "GradingResult", **{k: _ser(getattr(v, k)) for k in _RESULT_FIELDS}}
    if isinstance(v, dict):
        return {k: _ser(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_ser(x) for x in v]
    return v  # 兜底：其它原样（数字/字符串已在上面拦截）


def _deser(v: Any) -> Any:
    """``_ser`` 的逆操作。未知 __type__ / 缺字段 → 回退为原值或跳过，调用方据此重批。"""
    if isinstance(v, dict):
        if "__path__" in v:
            return Path(v["__path__"])
        if "__buildstatus__" in v:
            try:
                return BuildStatus[v["__buildstatus__"]]
            except KeyError:
                return None
        if "__datetime__" in v:
            try:
                return datetime.fromisoformat(v["__datetime__"])
            except Exception:
                return None
        t = v.get("__type__")
        if t == "BuildIssue":
            return BuildIssue(**{k: _deser(v[k]) for k in ("severity", "file", "line", "column", "message")})
        if t == "BuildResult":
            return BuildResult(**{k: _deser(v[k]) for k in (
                "status", "project_name", "project_path", "success", "duration",
                "error_count", "warning_count", "issues", "output", "error_message")})
        if t == "CategoryScore":
            return CategoryScore(**{k: _deser(v[k]) for k in (
                "category_id", "category_name", "max_points", "earned_points", "details")})
        if t == "ValidationIssue":
            return ValidationIssue(**{k: _deser(v[k]) for k in ("rule", "severity", "section", "message", "fix")})
        if t == "ValidationReport":
            return ValidationReport(**{k: _deser(v[k]) for k in ("passed", "issues", "sections", "missing_questions")})
        if t == "GradingResult":
            kw = {k: _deser(v[k]) for k in v if k != "__type__"}
            try:
                return GradingResult(**kw)
            except TypeError:
                return None  # 字段不匹配（版本演进）→ 调用方重批
        return {k: _deser(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_deser(x) for x in v]
    return v


def serialize_result(result: GradingResult) -> Dict[str, Any]:
    return _ser(result)


def deserialize_result(data: Dict[str, Any]) -> Optional[GradingResult]:
    r = _deser(data)
    return r if isinstance(r, GradingResult) else None


# ---------------- per-student 结果缓存 ----------------
def write_result_cache(grading_dir: Any, result: GradingResult) -> None:
    """增量写一个学生的 GradingResult 到 _checkpoint/<学号>.json（原子写）。"""
    p = checkpoint_dir(grading_dir) / f"{result.student_id}.json"
    atomic_write_json(p, serialize_result(result), ensure_ascii=False)


def load_result_cache(grading_dir: Any, student_id: str) -> Optional[GradingResult]:
    p = checkpoint_dir(grading_dir) / f"{student_id}.json"
    if not p.exists():
        return None
    try:
        return deserialize_result(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return None  # 损坏缓存 → 当作未缓存，重批


# ---------------- 批次元数据 ----------------
def new_meta(class_name: str, experiment_id: str, semester: str, total: int) -> Dict[str, Any]:
    return {
        "class_name": class_name, "experiment_id": experiment_id, "semester": semester,
        "total": total, "completed_ids": [], "failed_ids": [],
        "status": "interrupted", "started_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def write_meta(grading_dir: Any, meta: Dict[str, Any]) -> None:
    meta = dict(meta)
    meta["updated_at"] = datetime.now().isoformat()
    atomic_write_json(checkpoint_dir(grading_dir) / CHECKPOINT_META, meta, ensure_ascii=False)


def load_meta(grading_dir: Any) -> Optional[Dict[str, Any]]:
    p = checkpoint_dir(grading_dir) / CHECKPOINT_META
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_checkpoint(grading_dir: Any) -> None:
    """成功完成批阅后清除整个 _checkpoint/ 目录。"""
    d = checkpoint_dir(grading_dir)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def is_interrupted(meta: Optional[Dict[str, Any]]) -> bool:
    return bool(meta) and meta.get("status") == "interrupted" and bool(meta.get("completed_ids"))
