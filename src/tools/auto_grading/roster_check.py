# -*- coding: utf-8 -*-
"""教务花名册身份核验。

以教务系统导出的花名册(.xls/.xlsx)为 ground truth，核验每份评分结果的
``(学号, 姓名)``。目的：根治"学号撞号挤掉别人"——学生填错学号撞到他人头上时，
按姓名反查其真实学号并把记录 re-key 过去，撞号自然消失；同时按教师口径对身份
错误记 0 分并给出严肃提醒。

核验规则（教师 2026-06-28 拍板）：

- 学号在册且姓名一致 → 放行。
- 学号在册但姓名不符、且二者像「同一人的异写」(如 畅邵坤/畅绍坤) → **仅警告不扣分**（从宽）。
- 学号是别人的 / 学号不在册 → 按姓名反查真实学号 → **re-key 到真实学号 + 记 0 分 + 严肃警告**。
- 学号属他人且姓名也查无 / 学号姓名均不在册 → **记 0 分 + 严肃警告**。

只在批阅、``dedupe_team_members`` 之前调用一次；re-key 发生在去重之前，故撞号两人
（如 安晓童 210→211 与 王倩倩 210）各自落到不同学号，不再被去重并掉。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional


def _normalize_sid(value: Any) -> str:
    """学号归一化：xlrd 可能把数字单元格读成 float（如 23071140210.0），统一成纯数字串。"""
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.replace(" ", "")


def _read_rows(path: Path) -> List[List[Any]]:
    """读取 .xls(xlrd) / .xlsx(openpyxl) 首个工作表，返回二维列表。"""
    suffix = path.suffix.lower()
    if suffix == ".xls":
        import xlrd  # 延迟导入：仅在有花名册时才需要
        sh = xlrd.open_workbook(str(path)).sheet_by_index(0)
        return [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
    # .xlsx
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    ws = wb.active
    return [list(row) for row in ws.iter_rows(values_only=True)]


def load_id_roster(semester_dir: Any) -> Optional[Dict[str, Any]]:
    """从学期目录顶层发现教务花名册，返回 ``{by_id, by_name, source}`` 或 None。

    识别条件：表头行（前 5 行内）同时含「学号」「姓名」两列。多份花名册合并
    （学号在全校唯一）。非花名册的 .xls(xlsx)（如成绩册无姓名列）自动跳过。
    """
    semester_dir = Path(semester_dir)
    if not semester_dir.is_dir():
        return None

    by_id: Dict[str, str] = {}
    by_name: Dict[str, List[str]] = {}
    sources: List[str] = []
    for pattern in ("*.xls", "*.xlsx"):
        for fp in sorted(semester_dir.glob(pattern)):
            try:
                rows = _read_rows(fp)
            except Exception:
                continue  # 无法解析（可能是被 Excel 锁定等），跳过
            sid_col = name_col = header_row = None
            for r, row in enumerate(rows[:5]):
                cells = [str(c).strip() for c in row]
                if "学号" in cells and "姓名" in cells:
                    sid_col, name_col, header_row = cells.index("学号"), cells.index("姓名"), r
                    break
            if sid_col is None:
                continue  # 不是花名册
            for row in rows[header_row + 1:]:
                sid = _normalize_sid(row[sid_col]) if sid_col < len(row) else ""
                name = str(row[name_col]).strip() if name_col < len(row) else ""
                if sid and name:
                    by_id.setdefault(sid, name)
                    by_name.setdefault(name, [])
                    if sid not in by_name[name]:
                        by_name[name].append(sid)
                    if str(fp) not in sources:
                        sources.append(str(fp))
    if not by_id:
        return None
    return {"by_id": by_id, "by_name": by_name, "source": sources}


def _add_identity_issue(result, severity: str, criterion: str, points_lost: float, message: str) -> None:
    result.issues.append({
        "type": "submission",
        "category": "身份核验",
        "criterion": criterion,
        "points_lost": points_lost,
        "severity": severity,
        "message": message,
        "fix": "请按教务系统花名册更正学号/姓名后重新提交，并联系教师重评。",
        "expected": "学号、姓名与教务系统花名册完全一致",
    })


def _zero_for_identity_error(result, criterion: str, message: str, real_sid: str) -> None:
    """身份核验未通过 → 记 0 分、取消组长加分、re-key 到真实学号、追加 error 级 issue。"""
    lost = float(getattr(result, "total_score", 0.0) or 0.0)
    result.total_score = 0.0
    result.max_score = getattr(result, "max_score", 100.0) or 100.0
    result.bonus_total = 0.0
    if hasattr(result, "leader_bonus_granted"):
        result.leader_bonus_granted = 0.0
    result.is_team_leader = False
    result.grade = "F"
    if real_sid:
        result.student_id = real_sid  # re-key 到真实学号，避免与他人撞号被去重并掉
    _add_identity_issue(result, "error", criterion, round(lost, 1), message)


def _is_self_submitted(result) -> bool:
    """该结果是否来自**本人提交**（源码目录名含其学号）。

    用于公平性区分（教师 2026-06-28 拍板）：
    - 本人提交但学号填错（源码目录是自己的，如 陈乐莹 102）→ 自己的错 → 记 0 分；
    - 仅作为组员被队友在团队表里填错学号、本人未提交（源码目录是组长的，如 安晓童/申凯丽）
      → 队友的错 → 更正学号、保留组内继承分、仅警告。
    判据：组员展开结果的 source_path 指向组长源码目录，不含该组员学号 → 非本人提交。
    """
    sid = (getattr(result, "student_id", "") or "").strip()
    cr = getattr(result, "compilation_result", None)
    pp = getattr(cr, "project_path", None) if cr else None
    try:
        token = Path(pp).name if pp else ""
    except Exception:
        token = ""
    return bool(sid) and sid in token


def _correct_member_id_only(result, real_sid: str, message: str) -> None:
    """仅作为组员被队友填错学号（本人未提交）→ 更正学号、保留组内继承分、仅 warning。

    不记 0 分：错号责任在填报团队表的队友，不在该生本人。re-key 到真实学号避免撞号；
    分数沿用该生从组长报告展开继承的组内共享分。
    """
    if real_sid:
        result.student_id = real_sid
    _add_identity_issue(result, "warning", "学号错误（队友填报，已更正）", 0.0, message)


def validate_identities(results: List[Any], roster: Optional[Dict[str, Any]]) -> List[Any]:
    """按花名册逐条核验 ``(学号, 姓名)``，就地修改并返回 results。无花名册则原样返回。"""
    if not roster:
        return results
    # 延迟导入以避免与 grading_engine 的循环引用
    from .grading_engine import _names_look_like_same_person

    by_id = roster.get("by_id") or {}
    by_name = roster.get("by_name") or {}

    for r in results:
        sid = (getattr(r, "student_id", "") or "").strip()
        name = (getattr(r, "name", "") or "").strip()
        roster_name = by_id.get(sid)

        # 1) 学号在册且姓名一致 → 放行
        if roster_name is not None and roster_name == name:
            continue

        # 2) 学号在册但姓名不符
        if roster_name is not None:
            if _names_look_like_same_person(name, roster_name):
                # 同人异写：仅警告，不扣分（教师口径：从宽）
                _add_identity_issue(
                    r, "info", "姓名与花名册略有出入", 0.0,
                    f"姓名「{name}」与教务花名册「{roster_name}」（学号 {sid}）略有出入，"
                    f"判定为同一人，本次不影响评分；请今后严格按花名册填写姓名。")
                continue
            # 否则：学号是别人的号 → 落到反查姓名分支

        # 3) 学号不在册 / 学号是别人的：按姓名反查真实学号
        real_ids = by_name.get(name) or []
        if len(real_ids) == 1 and real_ids[0] != sid:
            real = real_ids[0]
            # 公平性区分：本人提交但学号填错→记0分(自己的错)；仅被队友在团队表填错、
            # 本人未提交→更正学号、保留组内继承分、仅警告(队友的错)。
            if _is_self_submitted(r):
                _zero_for_identity_error(
                    r, "学号错误",
                    f"学号「{sid}」有误——教务花名册中「{name}」的真实学号为「{real}」。"
                    f"本次按规则记 0 分。请将学号更正为 {real} 后重新提交，并联系教师重评。", real)
            else:
                _correct_member_id_only(
                    r, real,
                    f"原填学号「{sid}」有误（疑似队友在团队信息表中所填），教务花名册中「{name}」"
                    f"的真实学号为「{real}」，已自动更正；本次按组内共享分评定，不影响成绩。"
                    f"请下次确保团队表学号准确。")
        elif roster_name is not None:
            # 学号在册属别人、且姓名在册中查无 → 姓名错误
            _zero_for_identity_error(
                r, "姓名错误",
                f"学号「{sid}」在花名册中为「{roster_name}」，与所填姓名「{name}」不符，"
                f"且花名册中查无「{name}」。本次按规则记 0 分。请核对该生学号/姓名后重新提交。", sid)
        else:
            # 学号不在册、姓名也不在册
            _zero_for_identity_error(
                r, "身份未识别",
                f"学号「{sid}」与姓名「{name}」均不在教务花名册中。本次按规则记 0 分。"
                f"请核对该生是否选课、学号/姓名是否正确，必要时联系教师。", sid)
    return results
