#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
班级成绩分析（共享计算层）
Class Analysis — shared, pure computation.

把"班级报告"对话框与"教师分析报告"重复的统计/分布/维度/排名计算集中到此处，
两个视图（GUI 对话框、文本文档）都消费同一个 ClassAnalysis，避免逻辑重复。
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


def _rate(earned: float, mx: float) -> float:
    return (earned / mx) if mx > 0 else 0.0


@dataclass
class ClassAnalysis:
    """一个班级的批阅分析结果（纯数据，供 GUI/文档两类视图消费）。"""
    class_name: str
    experiment_id: str
    n: int
    reports: List[Dict] = field(default_factory=list)          # 原始个人报告
    scores: List[float] = field(default_factory=list)          # 总分列表
    avg: float = 0.0
    median: float = 0.0
    max_score: float = 0.0
    min_score: float = 0.0
    std: float = 0.0
    pass_rate: float = 0.0          # 得分率 >= 60%
    excellent_rate: float = 0.0     # 得分率 >= 80%
    grade_distribution: Dict[str, int] = field(default_factory=dict)        # A/B/C/D/F
    score_range_distribution: Dict[str, int] = field(default_factory=dict)  # 按得分率分段
    category_analysis: List[Dict] = field(default_factory=list)  # [{id,name,avg_earned,avg_max,rate}]
    ranking: List[Dict] = field(default_factory=list)            # 按总分降序的报告
    common_weaknesses: List[str] = field(default_factory=list)
    common_strengths: List[str] = field(default_factory=list)


# 分段（按得分率百分比）
_RANGES = ["0-59", "60-69", "70-79", "80-89", "90-100"]


def _range_of(pct: float) -> str:
    if pct < 60:
        return "0-59"
    if pct < 70:
        return "60-69"
    if pct < 80:
        return "70-79"
    if pct < 90:
        return "80-89"
    return "90-100"


def _freq(items: List[str], top_n: int = 5) -> List[str]:
    cnt: Dict[str, int] = {}
    for it in items:
        it = (it or "").strip()
        if it:
            cnt[it] = cnt.get(it, 0) + 1
    return [f"{t}（{c}次）" for t, c in sorted(cnt.items(), key=lambda kv: -kv[1])[:top_n]]


def analyze(reports: List[Dict], class_name: str = "", experiment_id: str = "") -> ClassAnalysis:
    """对一组个人报告做统计分析，返回 ClassAnalysis。"""
    a = ClassAnalysis(class_name=class_name, experiment_id=experiment_id,
                      n=len(reports), reports=list(reports))
    if not reports:
        return a

    # 得分与得分率
    scores: List[float] = []
    pcts: List[float] = []
    for r in reports:
        t = float(r.get("total_score", 0) or 0)
        mx = float(r.get("max_score", 100) or 100)
        scores.append(t)
        pcts.append(_rate(t, mx) * 100)
    a.scores = scores
    a.avg = mean(scores)
    a.median = median(scores)
    a.max_score = max(scores)
    a.min_score = min(scores)
    a.std = pstdev(scores) if len(scores) > 1 else 0.0
    a.pass_rate = sum(1 for p in pcts if p >= 60) / len(pcts) * 100
    a.excellent_rate = sum(1 for p in pcts if p >= 80) / len(pcts) * 100

    # 等级分布
    grade_dist: Dict[str, int] = {}
    for r in reports:
        g = str(r.get("grade", "N/A"))
        grade_dist[g] = grade_dist.get(g, 0) + 1
    a.grade_distribution = grade_dist

    # 分段分布（按得分率）
    range_dist = {k: 0 for k in _RANGES}
    for p in pcts:
        range_dist[_range_of(p)] += 1
    a.score_range_distribution = range_dist

    # 各维度分析
    agg: Dict[str, Dict] = {}
    for r in reports:
        for cs in r.get("category_scores", []) or []:
            cid = cs.get("category_id") or cs.get("category_name", "?")
            cname = cs.get("category_name") or cid
            e = float(cs.get("earned_points", 0) or 0)
            m = float(cs.get("max_points", 0) or 0)
            d = agg.setdefault(cid, {"name": cname, "sum_e": 0.0, "sum_m": 0.0, "n": 0})
            d["sum_e"] += e
            d["sum_m"] += m
            d["n"] += 1
    rows = []
    for cid, d in agg.items():
        avg_e = d["sum_e"] / d["n"] if d["n"] else 0
        avg_m = d["sum_m"] / d["n"] if d["n"] else 0
        rows.append({"id": cid, "name": d["name"],
                     "avg_earned": avg_e, "avg_max": avg_m, "rate": _rate(avg_e, avg_m)})
    rows.sort(key=lambda x: x["rate"])  # 薄弱在前
    a.category_analysis = rows

    # 排名（按总分降序）
    a.ranking = sorted(reports, key=lambda r: float(r.get("total_score", 0)), reverse=True)

    # 共性问题/亮点
    a.common_weaknesses = _freq([w for r in reports for w in (r.get("weaknesses") or [])])
    a.common_strengths = _freq([s for r in reports for s in (r.get("strengths") or [])])
    return a


# ---------------- 共享数据加载 ----------------
def load_class_reports(class_name: str, experiment_id: str, semester: str = "2026-春季",
                       project_root: Optional[Path] = None) -> List[Dict]:
    """读取某班级某实验的所有个人报告（个人报告/*-评分.json）。

    供班级报告对话框与反馈面板共用，避免各自重复读 JSON。
    """
    from tools.teaching_management_gui.path_helper import (
        get_experiment_paths, DEFAULT_SEMESTER,
    )
    semester = semester or DEFAULT_SEMESTER
    paths = get_experiment_paths(semester, class_name, experiment_id, project_root=project_root)
    individuals = paths.grading_dir / "个人报告"
    reports: List[Dict] = []
    if not individuals.exists():
        return reports
    for f in sorted(individuals.glob("*-评分.json")):
        try:
            reports.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            # 损坏/半截写入的个人报告：记日志可见，跳过该生而不静默吞掉，
            # 避免下游统计基于缩水数据集却无任何告警。
            logger.warning("解析个人报告失败，已跳过：%s (%s)", f, e)
    return reports
