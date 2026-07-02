#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生端自检报告生成器
Self-Check Report Writer

把 SelfCheckResult 渲染为 Markdown + JSON，写到
outputs/student_self_check/{学号}-{姓名}/{时间戳}/自检报告.{md,json}
（时间戳子目录防止多次自检互相覆盖）。

注意：GradingResult 含不可序列化的 BuildResult，禁止 dataclasses.asdict；
类别 details 复用 tools.auto_grading.facade.serialize_details（已处理 BuildResult）。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .self_checker import SelfCheckResult, build_status_of
from .id_card import StudentIdentity


DISCLAIMER = (
    "本结果为机器预测分，仅供参考。学习态度为教师评定项（此处为默认预测值）；"
    "组长加分由报告团队信息自动判定；最终以教师评分为准。"
)


def _safe_dir_name(identity: StudentIdentity) -> str:
    """生成安全的输出子目录名：{学号}-{姓名}。

    去除路径分隔符与非法字符，并剥离去 '.'，防止手填学号/姓名造成路径逃逸
    （学号本应为纯数字，但 UI 不强制，故在此兜底）。
    """
    bad = '\\/:*?"<>|.'

    def clean(s: str) -> str:
        s = "".join(c for c in (s or "") if c not in bad).strip()
        return s or "unknown"

    sid = clean(identity.student_id)
    name = clean(identity.name)
    return f"{sid}-{name}"


def _category_method(cat_id: str, grading) -> str:
    """从 details 启发式判断类别评定方式，供报告标注。"""
    for cs in grading.category_scores:
        if cs.category_id == cat_id:
            if cs.details and isinstance(cs.details[0], dict):
                if "build_result" in cs.details[0]:
                    return "build"
                if "analysis" in cs.details[0]:
                    return "code_analysis"
            break
    return "keyword/manual"


def result_to_dict(result: SelfCheckResult) -> Dict:
    """把 SelfCheckResult 序列化为可 JSON 化的 dict（也供 UI 复用）。"""
    g = result.grading
    v = result.validation
    identity = StudentIdentity(g.class_name, g.student_id, g.name)

    bs = build_status_of(g)
    cat_rows = []
    for cs in g.category_scores:
        method = _category_method(cs.category_id, g)
        row = {
            "id": cs.category_id,
            "name": cs.category_name,
            "earned": round(cs.earned_points, 1),
            "max": cs.max_points,
            "percentage": round(cs.earned_points / cs.max_points * 100, 1) if cs.max_points else 0.0,
            "method": method,
        }
        if cs.category_id == "compilation":
            row["build_status"] = bs.value if bs else None
            if cs.details and isinstance(cs.details[0], dict):
                row["build_message"] = cs.details[0].get("feedback") or cs.details[0].get("error_message", "")
        if cs.category_id == "attitude":
            row["note"] = "教师评定项，此处为默认预测值"
        if cs.category_id == "team_leader_bonus":
            row["note"] = "仅当报告声明担任组长时计入"
            row["is_leader"] = g.is_team_leader
        cat_rows.append(row)

    validation_dict = None
    if v is not None:
        validation_dict = {
            "passed": v.passed,
            "error_count": v.error_count,
            "warning_count": v.warning_count,
            "sections": list(v.sections.keys()),
            "missing_questions": list(v.missing_questions or []),
            "issues": [
                {"rule": i.rule, "severity": i.severity, "section": i.section,
                 "message": i.message, "fix": i.fix}
                for i in v.issues
            ],
        }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "experiment": result.experiment_code,
        "identity": {"class_name": identity.class_name, "student_id": identity.student_id, "name": identity.name},
        "files": {
            "report": str(g.student_id and result.submission.report_path or ""),
            "report_name": result.submission.report_path.name if result.submission.report_path else "",
            "source": str(result.submission.source_path or "") if result.submission.source_path else "",
            "source_kind": _source_kind_label(result),
        },
        "validation": validation_dict,
        "grading": {
            "total_score": round(g.total_score, 1),
            "max_score": g.max_score,
            "bonus_total": round(g.bonus_total, 1),
            "grade": g.grade,
            "is_team_leader": g.is_team_leader,
            "category_scores": cat_rows,
            "issues": [
                _issue_to_dict(it) for it in g.issues
            ],
            "thinking_check": [
                {"id": t.get("id"), "answered": t.get("answered", False), "expected": t.get("expected", "")}
                for t in (g.thinking_check or [])
            ],
        },
        "toolchain": result.toolchain,
        "source_state": {
            "state": result.source_state,
            "reason": result.source_state_reason,
            "fix": result.source_state_fix,
            # 仅 ok（含 Makefile）可被 make+gcc 机器编译；keil_only/empty/... 均不可
            "is_machine_buildable": result.source_state == "ok",
        },
        "warnings": list(result.warnings),
        "disclaimer": DISCLAIMER,
    }


def _source_kind_label(result: SelfCheckResult) -> str:
    sub = result.submission
    if not sub.source_path:
        return "未提供"
    if result.temp_dirs:
        # 按真实后缀区分 7z / zip（旧实现一律标 zip，对 .7z 误导）
        sfx = (result.archive_suffix or "").lower()
        if sfx == ".7z":
            return "7z（已解压）"
        return "zip（已解压）"
    return "目录"


def _issue_to_dict(it) -> Dict:
    """结构化失分项 → dict。"""
    return {
        "type": it.get("type", ""),
        "category": it.get("category", ""),
        "criterion": it.get("criterion", ""),
        "missing_keywords": list(it.get("missing_keywords", []) or []),
        "points_lost": it.get("points_lost", 0),
        "severity": it.get("severity", ""),
        "message": it.get("message", ""),
        "expected": it.get("expected", ""),
        "fix": it.get("fix", ""),
    }


def render_markdown(d: Dict) -> str:
    """从 result_to_dict 的产物渲染 Markdown 报告。"""
    ident = d["identity"]
    lines: List[str] = []
    lines.append("# 作业自检报告")
    lines.append("")
    lines.append(f"- **学号**：{ident['student_id']}")
    lines.append(f"- **姓名**：{ident['name']}")
    lines.append(f"- **班级**：{ident['class_name']}")
    lines.append(f"- **实验**：{d['experiment']}")
    lines.append(f"- **生成时间**：{d['generated_at']}")
    lines.append("")
    lines.append(f"> ⚠️ {DISCLAIMER}")
    lines.append("")
    lines.append("---")

    # 提交概览
    files = d["files"]
    lines.append("")
    lines.append("## 一、提交概览")
    lines.append(f"- 报告文件：`{files['report_name'] or '—'}`")
    lines.append(f"- 源代码：{files['source_kind']}" + (f"（`{files['source']}`）" if files['source'] else ""))

    # 源码工程状态（ok 不显示；其余给出具体原因 + 改进方法）
    ss = d.get("source_state") or {}
    if ss.get("state") and ss.get("state") != "ok":
        _state_label = {
            "keil_only": "纯 Keil 工程（无 Makefile，机器编译判 0）",
            "empty": "源码为空",
            "corrupted": "源码包损坏或格式异常",
            "nested_archive": "压缩包嵌套（未解包到底）",
            "not_submitted": "未提交源码",
        }
        lines.append("")
        lines.append("## 二、源码工程状态")
        lines.append(f"- **状态**：{_state_label.get(ss['state'], ss['state'])}")
        if ss.get("reason"):
            lines.append(f"- **原因**：{ss['reason']}")
        if ss.get("fix"):
            lines.append(f"- **改进**：{ss['fix']}")

    # 提交检测
    lines.append("")
    lines.append("## 三、提交检测")
    v = d["validation"]
    if v:
        badge = "✅ 通过" if v["passed"] else "❌ 存在问题"
        lines.append(f"- **检测结果**：{badge}")
        lines.append(f"- 错误 {v['error_count']} 项 / 警告 {v['warning_count']} 项")
        if v["issues"]:
            lines.append("")
            lines.append("| 严重度 | 规则 | 章节 | 描述 | 修正建议 |")
            lines.append("|---|---|---|---|---|")
            for i in v["issues"]:
                lines.append(
                    f"| {i['severity']} | {i['rule']} | {i['section']} "
                    f"| {i['message'].replace('|', '/')} | {(i['fix'] or '').replace('|', '/')} |"
                )
        if v["missing_questions"]:
            lines.append("")
            lines.append(f"- **思考题未检测到题号**：{', '.join(v['missing_questions'])}")
    else:
        lines.append("- 未生成校验报告。")

    # 自评结果
    lines.append("")
    lines.append("## 四、自评结果")
    g = d["grading"]
    lines.append(f"- **总分**：**{g['total_score']} / {g['max_score']}**")
    lines.append(f"- **等级**：**{g['grade']}**")
    lines.append(f"- **基础分外加分**：{g['bonus_total']}")
    lines.append("")
    lines.append("| 类别 | 得分 | 满分 | 得分率 | 方式 | 备注 |")
    lines.append("|---|---|---|---|---|---|")
    for c in g["category_scores"]:
        note = c.get("note", "")
        if c["id"] == "compilation":
            note = c.get("build_message", "") or note
        lines.append(
            f"| {c['name']} | {c['earned']} | {c['max']} | {c['percentage']}% "
            f"| {c['method']} | {note} |"
        )

    # 失分与改进
    lines.append("")
    lines.append("## 五、失分与改进建议")
    if g["issues"]:
        grouped: Dict[str, List] = {}
        for it in g["issues"]:
            grouped.setdefault(it["category"], []).append(it)
        for cat, items in grouped.items():
            lines.append("")
            lines.append(f"### {cat}")
            for it in items:
                lines.append(f"- **{it['criterion'] or it['message']}**"
                             + (f"（失 {it['points_lost']} 分）" if it.get("points_lost") else ""))
                if it.get("missing_keywords"):
                    lines.append(f"  - 缺失关键词：{', '.join(it['missing_keywords'])}")
                if it.get("expected"):
                    lines.append(f"  - 参考方向：{it['expected']}")
                if it.get("fix"):
                    lines.append(f"  - 建议：{it['fix']}")
    else:
        lines.append("- 暂无结构化失分项。")

    # 思考题核对
    lines.append("")
    lines.append("## 六、思考题核对")
    for t in g["thinking_check"]:
        mark = "✅" if t["answered"] else "❌"
        lines.append(f"- {mark} **{t['id']}**：{t['expected'] or '（无参考答案）'}")

    # 工具链
    lines.append("")
    lines.append("## 七、工具链")
    tc = d["toolchain"]
    lines.append(f"- make：{'已安装' if tc.get('make') else '未安装'}")
    lines.append(f"- arm-none-eabi-gcc：{'已安装' if tc.get('gcc') else '未安装'}")
    lines.append(
        "- 若工具链未安装，含 Makefile 的可编译工程其编译项会记 0 分但状态为「已跳过」，"
        "不代表代码无法编译；纯 Keil 工程无论工具链是否安装都判 0 分（见「源码工程状态」）。"
    )

    # 自检提示（文件名不规范等非致命警告）
    warnings = d.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("## 自检提示")
        for w in warnings:
            lines.append(f"- {w}")

    lines.append("")
    return "\n".join(lines)


def write_report(result: SelfCheckResult, project_root: Path) -> Path:
    """写出自检报告（md + json），返回时间戳输出目录。"""
    root = Path(project_root) / "outputs" / "student_self_check"
    student_dir = root / _safe_dir_name(StudentIdentity(
        result.grading.class_name, result.grading.student_id, result.grading.name
    ))
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = student_dir / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    data = result_to_dict(result)
    (out_dir / "自检报告.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "自检报告.md").write_text(render_markdown(data), encoding="utf-8")
    return out_dir
