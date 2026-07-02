#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
反馈/报告生成器
Feedback & Report Generators

两类输出：
1) 学生反馈（直击式）：置顶提交校验 → 成绩 → 必须修正的问题（逐条缺失/错误 +
   正确答案）→ 代码与编译问题 → 思考题核对 → 提升一级的具体动作。
   目的：让学生据此把作业"拔高一个层次"。
2) 教师分析报告：班级成绩统计、等级分布、各维度薄弱分析、排名、高频具体失分。

均以纯文本/Markdown 生成，便于写 .md 与 .docx。
"""

import re
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional


def _safe_rate(earned: float, mx: float) -> float:
    return (earned / mx) if mx > 0 else 0.0


# ============================================================
# 提交校验渲染（advisory，置顶）
# ============================================================
_SEV_LABEL = {'error': '错误', 'warning': '警告', 'info': '提示'}
_SEV_ORDER = {'error': 0, 'warning': 1, 'info': 2}


def _render_validation(v: Optional[Dict]) -> List[str]:
    """渲染提交校验结果。无问题返回空列表（不显示该块）。"""
    if not v:
        return []
    issues = v.get('issues') or []
    if not issues:
        return []
    lines = ["【提交校验】（格式/完整性问题，先于内容修正；不影响本次评分）"]
    for it in sorted(issues, key=lambda x: _SEV_ORDER.get(x.get('severity', 'info'), 3)):
        sev = _SEV_LABEL.get(it.get('severity', 'info'), '提示')
        lines.append(f"- [{sev}] {it.get('message', '')}")
        if it.get('fix'):
            lines.append(f"    修正：{it['fix']}")
    return lines


# ============================================================
# 学生反馈（直击式）
# ============================================================
def build_student_feedback(
    report: Dict,
    class_name: str = "",
    experiment_id: str = "",
    include_strengths: bool = True,
    include_weaknesses: bool = True,
    include_suggestions: bool = True,
    concise: bool = False,
) -> str:
    """生成单个学生的直击式反馈：直指错误/不完美，给出正确答案与可提升动作。"""
    name = report.get("name", "同学")
    sid = report.get("student_id", "")
    total = report.get("total_score", 0)
    max_score = report.get("max_score", 100)
    bonus = report.get("bonus_total", 0) or 0
    grade = report.get("grade", "N/A")
    cat_scores = report.get("category_scores", []) or []
    issues = report.get("issues", []) or []
    thinking = report.get("thinking_check", []) or []
    validation = report.get("validation_report")

    overall_rate = _safe_rate(total, max_score)

    lines: List[str] = []
    lines.append(f"{name} 同学（学号 {sid}，{class_name}）：")
    lines.append("")
    lines.append(f"本次实验「{experiment_id}」批阅完成。下面直接指出失分点与不完美之处，"
                 "并给出正确答案和提升方向，请逐项对照修改。")
    lines.append("")

    # 0. 提交校验（置顶）
    val_block = _render_validation(validation)
    if val_block:
        lines.extend(val_block)
        lines.append("")

    # 1. 成绩
    lines.append("【成绩与定级】")
    # 任务感知（final-project）：评价/100 × 难度系数 = 期末最终
    eval_score = report.get("evaluation_score")
    task_name = report.get("detected_task_name")
    ratio = report.get("difficulty_ratio")
    if task_name and eval_score is not None and ratio is not None:
        lines.append(f"识别任务：{task_name}（难度系数 ×{ratio}，来源：{report.get('detected_task_source','')}）")
        lines.append(f"评价分：{eval_score:.1f}/100　→　期末最终：{total:.1f}/{max_score:.0f}，等级：{grade}")
        # 任务判定不权威（无显式声明且信号混杂/回退到源码或默认）→ 提示学生核对、给出建议
        if report.get("detected_task_ambiguous"):
            lines.append(
                f"⚠【请核对任务】报告未见明确的「选择任务X」声明、且多个任务的特征信号并存，"
                f"系统暂按「{task_name}」（×{ratio}）评分。若与你们实际完成的任务不符，请在报告"
                "「所选任务及理由」处明确写出所选任务号（如「选择任务一」），或由教师在评分中调整任务归属与系数。"
            )
    else:
        lines.append(f"总分：{total}/{max_score}（{overall_rate*100:.1f}%），等级：{grade}")
    if bonus:
        lines.append(f"含基础分外加分：{bonus:.0f} 分（如组长加分）")
    lines.append("")

    # 简洁版
    if concise:
        must_fix = [i for i in issues if i.get('type') in ('criterion', 'build')
                    and i.get('points_lost', 0) > 0]
        for it in sorted(must_fix, key=lambda x: -x.get('points_lost', 0))[:2]:
            kw = f"（缺：{'、'.join(it.get('missing_keywords', []))}）" if it.get('missing_keywords') else ""
            lines.append(f"- 必改：[{it.get('category', '')}] {it.get('criterion', '')}{kw}"
                         f"，影响 {it.get('points_lost', 0)} 分")
            if it.get('expected'):
                lines.append(f"  正确应为：{it['expected']}")
        lines.append("")
        lines.append(_closing(overall_rate))
        return "\n".join(lines)

    # 2. 各部分得分
    if cat_scores:
        lines.append("【各部分得分】")
        for cs in cat_scores:
            cname = cs.get("category_name") or cs.get("category_id", "")
            e = float(cs.get("earned_points", 0) or 0)
            m = float(cs.get("max_points", 0) or 0)
            # 编译类"无法评估"（已跳过/无 Makefile/工具链缺失等）：不计入总分，
            # 单独标注，避免显示误导性的"0/15 ⚠失分较多"。
            details = cs.get("details") or []
            d0 = details[0] if isinstance(details, list) and details else {}
            br = d0.get("build_result") if isinstance(d0, dict) else None
            bstatus = (br.get("status") or "").lower() if isinstance(br, dict) else ""
            fb_txt = d0.get("feedback", "") if isinstance(d0, dict) else ""
            if bstatus in ("skipped", "not_found", "error", "timeout") or "已跳过" in fb_txt:
                lines.append(f"- {cname}：已跳过（未提取到可编译工程，不计入总分）")
                continue
            # 功能预测 / 态度：非失分项，标注来源（机器预测 / 教师可调）
            is_predicted = bool(d0.get("predicted")) if isinstance(d0, dict) else False
            is_manual = bool(d0.get("manual")) if isinstance(d0, dict) else False
            rate = _safe_rate(e, m)
            tag = ""
            if is_predicted:
                tag = " （机器预测，教师实测可覆盖）"
            elif is_manual:
                tag = "（默认，教师可调）"
            flag = "" if (rate >= 0.6 or is_predicted or is_manual) else "  ⚠失分较多"
            lines.append(f"- {cname}：{e}/{m}（{rate*100:.0f}%）{flag}{tag}")
        lines.append("")

    # 3. 必须修正的问题（逐条：缺失关键词 + 正确答案 + 影响分值）
    must_fix = [i for i in issues if i.get('type') in ('criterion', 'build')]
    if must_fix:
        lines.append("【必须修正的问题】")
        for it in sorted(must_fix, key=lambda x: -x.get('points_lost', 0)):
            head = f"- [{it.get('category', '')}] {it.get('criterion', '')}"
            if it.get('missing_keywords'):
                head += f"：未体现「{'、'.join(it['missing_keywords'])}」"
            elif it.get('message'):
                head += f"：{it['message']}"
            head += f"（影响 {it.get('points_lost', 0)} 分）"
            lines.append(head)
            if it.get('expected'):
                lines.append(f"    ▶ 正确应为：{it['expected']}")
            if it.get('fix'):
                lines.append(f"    ▶ 怎么改：{it['fix']}")
        lines.append("")

    # 4. 代码与编译问题
    code_issues = [i for i in issues if i.get('type') == 'code']
    build_issue = next((i for i in issues if i.get('type') == 'build'
                        and i.get('severity') in ('error', 'warning')), None)
    if code_issues or build_issue:
        lines.append("【代码与编译问题】")
        if build_issue:
            lines.append(f"- 编译：{build_issue.get('message', '未通过')}"
                         + (f"（{build_issue.get('detail', '')}）" if build_issue.get('detail') else ""))
            if build_issue.get('fix'):
                lines.append(f"    ▶ {build_issue['fix']}")
        for it in code_issues:
            sev = (it.get('severity', 'info') or 'info').upper()
            loc = f"@行{it['line']}" if it.get('line') else ""
            lines.append(f"- [{sev}{loc}] {it.get('message', '')}")
            if it.get('fix'):
                lines.append(f"    ▶ 建议：{it['fix']}")
        lines.append("")

    # 5. 思考题核对
    if thinking:
        unanswered = [q for q in thinking if not q.get('answered')]
        lines.append("【思考题核对】")
        if unanswered:
            lines.append(f"未作答：{', '.join(q['id'] for q in unanswered)}（参考下方方向补答）")
        for q in thinking:
            mark = "✓" if q.get('answered') else "✗"
            lines.append(f"- {q.get('id')} {mark}")
            if q.get('expected'):
                lines.append(f"    参考方向：{q['expected']}")
        lines.append("")

    # 6. 提升一级的具体动作（quick-wins，按可回收分值排序）
    quickwins = [i for i in issues if i.get('type') == 'criterion' and i.get('points_lost', 0) > 0]
    if quickwins:
        total_recoverable = sum(i.get('points_lost', 0) for i in quickwins)
        lines.append("【提升一级的具体动作】（按可回收分值排序）")
        lines.append(f"理论上修正这些问题可回收约 {total_recoverable:.0f} 分：")
        for it in sorted(quickwins, key=lambda x: -x.get('points_lost', 0))[:6]:
            lines.append(f"- 补强「{it.get('criterion', '')}」→ 可回收 {it.get('points_lost', 0)} 分"
                         + (f"（对照：{it['expected']}）" if it.get('expected') else ""))
        lines.append("")

    # 收尾（简短、导向行动，不堆表扬）
    lines.append(_closing(overall_rate))
    return "\n".join(lines)


def _closing(overall_rate: float) -> str:
    """按总得分率给出一句简短、导向行动的收尾。"""
    if overall_rate >= 0.85:
        return "整体扎实。按上面少量待改进项打磨即可冲击更高等级。"
    if overall_rate >= 0.6:
        return "按「必须修正的问题」与「提升一级的具体动作」逐项落实，下次可显著提分。"
    return "待改进项较多，请优先完成「提交校验」与失分最大的几项，循序渐进。"


# ============================================================
# 小组反馈（每组生成 1 份；正文取组长那份为代表）
# ============================================================

# 其得分由各成员「各自被归因的源码」决定的分项 id；用来判断同组是否真共用一份源码。
_CODE_CATEGORY_IDS = ("compilation", "non_blocking", "code_quality", "functionality")


def _members_share_source(member_reports: List[Dict]) -> bool:
    """判断同组是否真的共用同一份源码工程（决定反馈措辞）。

    每位成员的编译 / 非阻塞 / 代码质量 / 功能分项都源自其各自被归因的源码；这些分项
    在全体成员间完全一致，才视为共用同一份源码——此时正文失分点对全组适用。只要有一
    人不同（各成员分别上传了不同源码），就判定为「未共用」，正文不再声称代码部分对
    全组适用。单人组（个人实验）无此问题，返回 True。

    以分项得分为信号比 ``compilation_result.project_path`` 更稳：源码解压失败时后者
    为空，但分项仍能反映各自的归因差异（见 ``dedupe_team_members`` 的自评归因）。
    """
    if len(member_reports) <= 1:
        return True

    def _code_sig(r: Dict) -> tuple:
        scores = {c.get("category_id"): c.get("earned_points")
                  for c in (r.get("category_scores") or [])}
        return tuple(scores.get(cid) for cid in _CODE_CATEGORY_IDS)

    return len({_code_sig(r) for r in member_reports}) == 1


def _distinct_submitters(member_reports: List[Dict]) -> int:
    """同组「各自提交了源码」的去重人数（用于"同组只交一份"提醒）。

    优先用批阅时盖章的 ``group_submitter_count``（组内应一致，取 max 容错）；
    缺失（旧数据 / 未重跑批阅）则回退：从各成员 compilation 类目的
    ``build_result.project_name`` 解析学号前缀去重计数——project_name 形如
    ``23071140125-靳皓杰``，自我归因后指向该生本人提交的源码，故去重数即提交人数。
    无法判定（无 compilation 类目 / 无 project_name）返回 0，反馈层据此不声称。
    """
    known = [int(r.get("group_submitter_count") or 0) for r in member_reports]
    pos = [c for c in known if c > 0]
    if pos:
        return max(pos)

    owners: set = set()
    for r in member_reports:
        comp = next((c for c in (r.get("category_scores") or [])
                     if c.get("category_id") == "compilation"), None)
        if not comp:
            continue
        details = comp.get("details") or []
        br = (details[0].get("build_result") if details else None) or {}
        m = re.match(r"(\d{6,})", br.get("project_name") or "")
        if m:
            owners.add(m.group(1))
    return len(owners)


def _distinct_reporters(member_reports: List[Dict]) -> int:
    """同组「各自上传了报告」的去重人数（报告维度）。读批阅时盖章的 ``group_reporter_count``
    （组内一致，取 max 容错）；缺失（旧数据 / 未重跑）返回 0。与源码维度的
    :func:`_distinct_submitters` 互补：源码只交一份但报告各交各的（如 闫建铭/李全：
    两份报告、一份源码）也能据此检出 ≥2，从而触发"同组只交一份"提醒。
    """
    known = [int(r.get("group_reporter_count") or 0) for r in member_reports]
    pos = [c for c in known if c > 0]
    return max(pos) if pos else 0


def pick_group_leader(member_reports: List[Dict]) -> Dict:
    """从同组多份报告里选出代表整组的那份（作为反馈正文基准）。

    优先 ``is_team_leader``；否则学号 == ``group_key``（报告文件名解析出的组长）；
    都没有则取组员名册最全的一份。每一档内部都用「组员名册最全」做 tie-breaker——
    名册越全，越可能含全体组员的心得/分工，避免"先少后全"提交时取到只含一人心得
    的简版报告作为全组反馈正文。正文以该代表份为准；同组成员若各自提交源码，代码类
    分项会不同（见 :func:`_members_share_source`），但报告正文内容通常一致。
    """
    if not member_reports:
        return {}

    def _fulness(r: Dict) -> int:
        return len(r.get('group_members') or [])

    leaders = [r for r in member_reports if r.get('is_team_leader')]
    if leaders:
        return max(leaders, key=_fulness)
    gk = member_reports[0].get('group_key')
    if gk:
        gk_matches = [r for r in member_reports if r.get('student_id') == gk]
        if gk_matches:
            return max(gk_matches, key=_fulness)
    # 都没有：取组员名册最全的那份，而非简单第一份
    return max(member_reports, key=_fulness)


def build_group_feedback(
    member_reports: List[Dict],
    class_name: str = "",
    experiment_id: str = "",
    include_strengths: bool = True,
    include_weaknesses: bool = True,
    include_suggestions: bool = True,
    concise: bool = False,
) -> str:
    """生成一份**小组**反馈：组员名册表（各自总分/等级/组长标记）+ 批阅正文。

    正文取组长那份（代表整组工作）。若各成员分别提交了源码（代码类分项不一致，
    见 :func:`_members_share_source`），仅报告部分对全组适用——措辞会相应调整，
    不再笼统声称「共用同一份工程/对全组适用」，以免反馈与本人提交不符。
    """
    if not member_reports:
        return ""
    leader = pick_group_leader(member_reports)
    roster = sorted(member_reports, key=lambda r: r.get('student_id', ''))
    shared = _members_share_source(roster)
    submitter_count = _distinct_submitters(roster)   # 源码维度
    reporter_count = _distinct_reporters(roster)     # 报告维度（互补：报告各交各的也能检出）
    shown_count = max(submitter_count, reporter_count)
    multi_submit = shown_count >= 2

    lines: List[str] = []
    lines.append(f"小组反馈（组长：{leader.get('name', '')}，学号 {leader.get('student_id', '')}）")
    lines.append(f"班级：{class_name}　实验：{experiment_id}　组员 {len(roster)} 人")
    lines.append("")
    # ≥2 人各自提交（报告或源码）：置顶提醒"重复提交会导致评分不准确，同组只交一份"
    if multi_submit:
        lines.append(
            f"【提交提醒】检测到本组有 {shown_count} 人各自上传了作业（报告/源码，学习通「按人导出」）。"
            "这种重复提交会让机器归因混乱，**可能导致本次评分不准确**（如本人分数被算到队友那份上、"
            "源码归因错位、反馈与本人提交不符等）。"
        )
        lines.append(
            "▶ 下次只需由组长一人提交一份报告 + 一份源码即可，组员不必重复上传。"
            "若本次分数与预期不符，请由组长按「一人一份」重新提交后联系教师重评。"
        )
        lines.append("")
        lines.append(
            "【组员与成绩】（本组多人提交，已自动归并；重复提交可能致评分偏差；组长另计组长加分）"
        )
    elif shared:
        lines.append("【组员与成绩】（本组共用同一份工程与报告；组长额外计组长加分）")
    else:
        lines.append(
            "【组员与成绩】（本组报告内容一致；各成员分别提交了源码，代码类分项"
            "（编译/非阻塞/代码质量/功能）按各自提交评定，故总分可能不同；组长另计组长加分）"
        )
    lines.append("| 学号 | 姓名 | 总分 | 等级 | 组长加分 | 角色 |")
    lines.append("|---|---|---|---|---|---|")
    for r in roster:
        is_lead = bool(r.get('is_team_leader'))
        role = "组长" if is_lead else "组员"
        bonus = float(r.get('bonus_total', 0) or 0)
        mx = r.get('max_score', 100)
        lines.append(
            f"| {r.get('student_id', '')} | {r.get('name', '')} | "
            f"{r.get('total_score', 0)}/{mx} | {r.get('grade', '')} | "
            f"{bonus:.0f} | {role} |"
        )
    lines.append("")
    # 身份核验：学号/姓名与教务花名册不符。分两类提示——
    #  error(记0分)：本人提交却填错学号/姓名，自己的错；
    #  warning(已更正)：仅被队友在团队表填错、本人未提交，已按花名册更正、保留组内分。
    _id_errors, _id_corrected = [], []
    for _r in roster:
        for _i in (_r.get('issues') or []):
            if _i.get('category') != '身份核验':
                continue
            sev = _i.get('severity')
            tup = (_r.get('name', ''), _r.get('student_id', ''), _i)
            if sev == 'error':
                _id_errors.append(tup)
            elif sev == 'warning':
                _id_corrected.append(tup)
            break
    if _id_corrected:
        lines.append("ℹ【学号已按花名册更正】以下成员的学号系团队信息表中填报有误，已按教务系统花名册自动更正，本次按组内共享分评定、不影响成绩：")
        for _nm, _sid, _i in _id_corrected:
            lines.append(f"- {_nm}（{_sid}）：{_i.get('message', '')}")
        lines.append("")
    if _id_errors:
        lines.append("⚠【身份核验未通过 · 记 0 分】以下成员的学号/姓名与教务系统花名册不符，本次按规则记 0 分：")
        for _nm, _sid, _i in _id_errors:
            lines.append(f"- {_nm}（{_sid}）：{_i.get('message', '')}")
        lines.append("请相关同学按花名册更正学号/姓名后重新提交，并联系教师重评。")
        lines.append("")
    # 名册声明但未生成独立评分的成员 → 点名提示，避免「少人」无声发生。
    # 典型成因：该成员学号与别组同学重号（去重时被并掉），或本轮未单独提交。
    # 注意：身份核验会把填错学号者 re-key 到真实学号，故匹配时"学号与姓名都不在
    # 幸存成员中"才算缺失，避免把已 re-key 的人（如 210→211）误报为少人。
    _declared: Dict[str, str] = {}
    for _m in (leader.get('group_members') or []):
        _msid = _m[0] if isinstance(_m, (list, tuple)) else _m.get('student_id')
        _mname = _m[1] if isinstance(_m, (list, tuple)) else _m.get('name')
        if _msid:
            _declared.setdefault(str(_msid), _mname or '')
    _survived_ids = {str(r.get('student_id', '')) for r in roster}
    _survived_names = {(r.get('name') or '').strip() for r in roster}
    _missing = [(sid, nm) for sid, nm in _declared.items()
                if sid not in _survived_ids and (nm or '').strip() not in _survived_names]
    if _missing:
        _names_str = "、".join((f"{nm}({sid})" if nm else sid) for sid, nm in _missing)
        lines.append(
            f"⚠【学号/提交核对】本组名册声明 {len(_declared)} 人，实际生成独立评分 {len(roster)} 人；"
            f"另有 {len(_missing)} 名成员（{_names_str}）未生成独立评分。常见原因是该成员学号与别组同学"
            f"**重号**（去重时被并掉）或本轮未单独提交，**可能导致分数异常**。请该成员联系教师核对学号归属。"
        )
        lines.append("")
    if multi_submit:
        lines.append(
            "以下批阅反馈以组长那份为代表：报告部分（概述/设计/代码说明/调试/总结）对全组基本适用；"
            "但因多人各自提交，代码与编译部分仅反映组长提交的源码，组员请结合上表本人的代码类分项"
            "与「必须修正的问题」对照查看。"
        )
    elif shared:
        lines.append("以下为该组共享工程/报告的批阅反馈（失分点与改进方向对全组适用）：")
    else:
        lines.append(
            "以下批阅反馈以组长那份为代表：报告部分（概述/设计/代码说明/调试/总结）对全组适用；"
            "代码与编译部分仅反映组长提交的源码，组员请结合上表本人的代码类分项与「必须修正的问题」对照查看。"
        )
    lines.append("")

    # 正文复用单生反馈：去掉开头个人称呼段，从首个【块开始拼接
    full = build_student_feedback(
        leader, class_name, experiment_id,
        include_strengths, include_weaknesses, include_suggestions, concise,
    )
    idx = full.find("\n【")
    body = full[idx + 1:] if idx != -1 else full
    lines.append(body)
    return "\n".join(lines)


# ============================================================
# 教师分析报告（消费 class_analysis.ClassAnalysis，不重复计算）
# ============================================================
def build_teacher_report(
    class_name: str,
    experiment_id: str,
    reports: List[Dict],
) -> str:
    """生成班级教师分析报告。统计/分布/维度/排名来自 class_analysis.analyze()；
    另从个人报告的 issues 聚合「高频具体失分」。"""
    from tools.teaching_management_gui.class_analysis import analyze
    a = analyze(reports, class_name, experiment_id)

    lines: List[str] = []
    lines.append(f"# 教学分析报告 — {class_name}")
    lines.append(f"实验：{experiment_id}　|　生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    if a.n == 0:
        lines.append("（无可用批阅数据）")
        return "\n".join(lines)

    lines.append("## 一、成绩统计")
    lines.append(f"- 参评学生：{a.n}")
    lines.append(f"- 平均分：{a.avg:.1f}")
    lines.append(f"- 中位数：{a.median:.1f}")
    lines.append(f"- 最高 / 最低：{a.max_score:.1f} / {a.min_score:.1f}")
    lines.append(f"- 标准差：{a.std:.1f}")
    lines.append(f"- 及格率（≥60%）：{a.pass_rate:.1f}%")
    lines.append("")

    lines.append("## 二、等级分布")
    for g in sorted(a.grade_distribution.keys()):
        c = a.grade_distribution[g]
        bar = "█" * round(c / a.n * 20)
        lines.append(f"- {g}：{c} 人（{c / a.n * 100:.1f}%） {bar}")
    lines.append("")

    if a.category_analysis:
        lines.append("## 三、各评分维度分析（按平均得分率升序，薄弱在前）")
        for r in a.category_analysis:
            lines.append(
                f"- {r['name']}：{r['avg_earned']:.1f}/{r['avg_max']:.1f}"
                f"（{r['rate'] * 100:.0f}%）"
            )
        weakest = a.category_analysis[0]
        lines.append("")
        lines.append(f"**全班最薄弱维度**：「{weakest['name']}」（{weakest['rate'] * 100:.0f}%），建议在后续教学中重点强化。")
        lines.append("")

    # 高频具体失分（从 issues 聚合，比含糊的"维度薄弱"更可操作）
    freq = _aggregate_issues(a.reports)
    if freq:
        lines.append("## 四、高频具体失分（按出现人数）")
        for msg, c in freq:
            lines.append(f"- {msg}（{c} 人）")
        lines.append("")

    lines.append("## 五、成绩排名")
    lines.append("| 排名 | 学号 | 姓名 | 总分 | 等级 |")
    lines.append("|---|---|---|---|---|")
    for i, r in enumerate(a.ranking, 1):
        lines.append(f"| {i} | {r.get('student_id', '')} | {r.get('name', '')} | "
                     f"{float(r.get('total_score', 0)):.1f} | {r.get('grade', '')} |")
    lines.append("")

    lines.append("## 六、共性薄弱点与亮点")
    if a.common_weaknesses:
        lines.append("**高频薄弱点：**")
        lines.extend(f"- {t}" for t in a.common_weaknesses)
    else:
        lines.append("**高频薄弱点：** （无聚合数据，详见各维度得分率）")
    if a.common_strengths:
        lines.append("**高频亮点：**")
        lines.extend(f"- {t}" for t in a.common_strengths)
    lines.append("")

    lines.append("## 七、教学建议")
    for r in a.category_analysis[:2]:
        if r["rate"] < 0.7:
            lines.append(f"- 「{r['name']}」全班平均仅 {r['rate'] * 100:.0f}%，建议增加相关讲解与练习。")
    if a.pass_rate < 60:
        lines.append(f"- 及格率仅 {a.pass_rate:.0f}%，整体偏弱，建议组织专项辅导。")
    if a.std > 20:
        lines.append(f"- 成绩标准差 {a.std:.0f}，两极分化明显，建议分层辅导。")
    lines.append("")
    return "\n".join(lines)


def _aggregate_issues(reports: List[Dict], top_n: int = 8) -> List[tuple]:
    """从个人报告 issues 聚合高频具体失分条目。返回 [(描述, 人数), ...]。"""
    counter: Counter = Counter()
    for r in reports:
        seen = set()
        for it in (r.get("issues") or []):
            if it.get("type") not in ("criterion", "build"):
                continue
            key = f"[{it.get('category', '')}] {it.get('criterion', '')}"
            if key not in seen:
                seen.add(key)
                counter[key] += 1
    return counter.most_common(top_n)
