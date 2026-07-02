# -*- coding: utf-8 -*-
"""
feedback_reports 单元测试 —— 聚焦「同组多人重复提交」提醒：

- _distinct_submitters：新字段优先 + project_name 兜底
- build_group_feedback：≥2 人各自提交时置顶提醒，并修正"共用同一份报告"的虚假措辞；
  单提交者保持原有"共用同一份"行为（回归保护）。
"""

import sys

sys.path.insert(0, "src")

from tools.teaching_management_gui.feedback_reports import (  # noqa: E402
    build_group_feedback,
    _distinct_submitters,
)


MEMBERS = [("23071140125", "靳皓杰"), ("23071140135", "薛松涛"), ("23071140136", "李志飞")]
MEMBERS_TWO = [("23071140128", "闫建铭"), ("23071140141", "李全")]


def _report(sid, name, *, total=80.0, leader=False, gk="23071140125",
            comp_earned=0.0, project_name=None, submitter_count=None,
            reporter_count=None, members=None):
    """构造一份最小可渲染的个人报告 dict。

    project_name 模拟 compilation 类目 build_result.project_name（自我归因后指向本人源码），
    供 _distinct_submitters 兜底；submitter_count 模拟批阅时盖章的新字段（源码维度）；
    reporter_count 模拟 group_reporter_count（报告维度）。
    代码类分项默认全一致 → _members_share_source 返回 True（用于复现靳组 shared=True 的场景）。
    """
    comp_details = ([{"build_result": {"project_name": project_name, "status": "failed"}}]
                    if project_name is not None else [])
    cat = [
        {"category_id": "compilation", "category_name": "编译检查", "max_points": 10,
         "earned_points": comp_earned, "details": comp_details},
        {"category_id": "non_blocking", "category_name": "非阻塞", "max_points": 10,
         "earned_points": 10.0, "details": []},
        {"category_id": "code_quality", "category_name": "代码质量", "max_points": 15,
         "earned_points": 14.7, "details": []},
        {"category_id": "functionality", "category_name": "功能实现", "max_points": 10,
         "earned_points": 6.6, "details": []},
    ]
    r = {
        "student_id": sid, "name": name, "class_name": "汽服2301B班",
        "total_score": total, "max_score": 100.0, "grade": "C",
        "bonus_total": 5.0 if leader else 0.0, "is_team_leader": leader,
        "group_key": gk, "group_members": members or [],
        "category_scores": cat, "issues": [], "thinking_check": [],
        "validation_report": None,
    }
    if submitter_count is not None:
        r["group_submitter_count"] = submitter_count
    if reporter_count is not None:
        r["group_reporter_count"] = reporter_count
    return r


class TestDistinctSubmitters:
    def test_uses_new_field_when_present(self):
        reps = [_report("23071140125", "靳皓杰", submitter_count=3, members=MEMBERS)]
        assert _distinct_submitters(reps) == 3

    def test_field_overrides_project_name(self):
        """有新字段时优先用字段，忽略 project_name 兜底。"""
        reps = [_report("23071140125", "靳皓杰", submitter_count=1,
                        project_name="23071140125-靳皓杰", members=MEMBERS)]
        assert _distinct_submitters(reps) == 1

    def test_fallback_project_name_counts_distinct_owners(self):
        reps = [
            _report("23071140125", "靳皓杰", project_name="23071140125-靳皓杰", members=MEMBERS),
            _report("23071140135", "薛松涛", project_name="23071140135-薛松涛", members=MEMBERS),
            _report("23071140136", "李志飞", project_name="23071140136-李志飞", members=MEMBERS),
        ]
        assert _distinct_submitters(reps) == 3

    def test_fallback_dedupes_same_owner(self):
        """多人均回退到组长源码（同 project_name）→ 计为 1。"""
        reps = [
            _report("23071140125", "靳皓杰", project_name="23071140125-靳皓杰", members=MEMBERS),
            _report("23071140135", "薛松涛", project_name="23071140125-靳皓杰", members=MEMBERS),
            _report("23071140136", "李志飞", project_name="23071140125-靳皓杰", members=MEMBERS),
        ]
        assert _distinct_submitters(reps) == 1

    def test_fallback_single_member(self):
        reps = [_report("23071140121", "成安旭", project_name="23071140121-成安旭")]
        assert _distinct_submitters(reps) == 1

    def test_fallback_no_compilation_returns_zero(self):
        reps = [
            _report("23071140125", "靳皓杰", project_name=None, members=MEMBERS),
            _report("23071140135", "薛松涛", project_name=None, members=MEMBERS),
        ]
        assert _distinct_submitters(reps) == 0


class TestGroupFeedbackNotice:
    def test_multi_submit_shows_notice_and_drops_false_claim(self):
        """3 人各自提交（3 个不同 project_name）→ 出现提醒，且不再声称共用同一份报告。"""
        reps = [
            _report("23071140125", "靳皓杰", leader=True, total=81.9,
                    project_name="23071140125-靳皓杰", members=MEMBERS),
            _report("23071140135", "薛松涛", total=65.0,
                    project_name="23071140135-薛松涛", members=MEMBERS),
            _report("23071140136", "李志飞", total=76.9,
                    project_name="23071140136-李志飞", members=MEMBERS),
        ]
        text = build_group_feedback(reps, "汽服2301B班", "final-project")
        assert "本组有 3 人各自上传" in text
        assert "提交提醒" in text
        assert "只需由组长一人提交一份" in text
        assert "共用同一份工程与报告" not in text

    def test_multi_submit_overrides_shared_true(self):
        """代码类分项全一致（shared=True）但 3 人各自提交 → 仍触发提醒（靳组真实场景）。"""
        reps = [
            _report("23071140125", "靳皓杰", leader=True,
                    project_name="23071140125-靳皓杰", members=MEMBERS),
            _report("23071140135", "薛松涛",
                    project_name="23071140135-薛松涛", members=MEMBERS),
            _report("23071140136", "李志飞",
                    project_name="23071140136-李志飞", members=MEMBERS),
        ]
        text = build_group_feedback(reps, "汽服2301B班", "final-project")
        assert "本组有 3 人各自上传" in text
        assert "共用同一份工程与报告" not in text

    def test_explicit_field_drives_notice(self):
        """新字段 group_submitter_count=2 → 触发（即便无 project_name 兜底数据）。"""
        reps = [
            _report("23071140125", "靳皓杰", leader=True, submitter_count=2, members=MEMBERS),
            _report("23071140135", "薛松涛", submitter_count=2, members=MEMBERS),
        ]
        text = build_group_feedback(reps, "汽服2301B班", "final-project")
        assert "本组有 2 人各自上传" in text
        assert "共用同一份工程与报告" not in text

    def test_report_multi_submit_fires_even_with_one_source(self):
        """闫建铭/李全场景：两人各交一份报告(reporter=2)但只有一份源码(submitter=1)
        → 报告维度仍触发"同组只交一份"提醒（源码维度漏检，报告维度补上）。"""
        reps = [
            _report("23071140128", "闫建铭", leader=False,
                    reporter_count=2, submitter_count=1,
                    project_name="23071140141-李全", members=MEMBERS_TWO),
            _report("23071140141", "李全", leader=True,
                    reporter_count=2, submitter_count=1,
                    project_name="23071140141-李全", members=MEMBERS_TWO),
        ]
        text = build_group_feedback(reps, "汽服2301B班", "final-project")
        assert "本组有 2 人各自上传" in text
        assert "提交提醒" in text

    def test_single_submitter_keeps_shared_claim(self):
        """仅组长提交（他人 project_name 均回退到组长）→ 不触发、保留'共用同一份'（回归保护）。"""
        reps = [
            _report("23071140125", "靳皓杰", leader=True,
                    project_name="23071140125-靳皓杰", members=MEMBERS),
            _report("23071140135", "薛松涛",
                    project_name="23071140125-靳皓杰", members=MEMBERS),
            _report("23071140136", "李志飞",
                    project_name="23071140125-靳皓杰", members=MEMBERS),
        ]
        text = build_group_feedback(reps, "汽服2301B班", "final-project")
        assert "各自上传" not in text
        assert "提交提醒" not in text
        assert "共用同一份工程与报告" in text


class TestMissingMemberNotice:
    """名册声明但未生成独立评分的成员（典型：学号与别组重号被并掉）→ 反馈点名提示。"""

    def test_notes_missing_member_with_id_and_name(self):
        """刘烊宏组：名册声明 3 人(237/206/210安晓童)，roster 只有 237/206
        （210 安晓童因学号与王倩倩重号被去重并掉）→ 反馈点出安晓童(210) 未评分。"""
        members = [("23071140237", "刘烊宏"), ("23071140206", "王晨露"), ("23071140210", "安晓童")]
        reps = [
            _report("23071140237", "刘烊宏", leader=True, gk="23071140206", members=members),
            _report("23071140206", "王晨露", gk="23071140206", members=members),
            # 注意：没有 23071140210 那份——安晓童被并掉了
        ]
        text = build_group_feedback(reps, "汽服2302B班", "final-project")
        assert "安晓童" in text and "23071140210" in text
        assert "未生成独立评分" in text
        assert "可能导致分数异常" in text

    def test_no_notice_when_roster_complete(self):
        """名册全员都有结果 → 不提示缺人（回归保护）。"""
        members = [("1", "甲"), ("2", "乙")]
        reps = [
            _report("1", "甲", leader=True, gk="G", members=members),
            _report("2", "乙", gk="G", members=members),
        ]
        text = build_group_feedback(reps, "汽服2301B班", "final-project")
        assert "未生成独立评分" not in text


class TestIdentityCheckNotice:
    """身份核验提示：error(记0分) 与 warning(已更正、保留分) 分别渲染。"""

    def _rep_with_issue(self, sid, name, total, leader, issue):
        r = _report(sid, name, leader=leader, gk="G", total=total,
                    members=[(sid, name)])
        r["issues"] = [issue]
        return r

    def test_zeroed_member_shown_in_zero_block(self):
        """本人提交填错学号(severity=error) → 进『身份核验未通过·记0分』段。"""
        reps = [self._rep_with_issue("23071140202", "陈乐莹", 0.0, False, {
            "type": "submission", "category": "身份核验", "criterion": "学号错误",
            "severity": "error", "points_lost": 88.0,
            "message": "学号102有误，真实学号202，记0分。"})]
        text = build_group_feedback(reps, "汽服2302B班", "final-project")
        assert "身份核验未通过" in text and "记 0 分" in text
        assert "陈乐莹" in text and "23071140202" in text

    def test_corrected_member_shown_in_corrected_block_not_zero(self):
        """被队友填错(severity=warning, 已更正) → 进『学号已按花名册更正』段，不进记0分段。"""
        reps = [self._rep_with_issue("23071140211", "安晓童", 76.5, False, {
            "type": "submission", "category": "身份核验", "criterion": "学号错误（队友填报，已更正）",
            "severity": "warning", "points_lost": 0.0,
            "message": "原填210有误(队友所填)，真实211，已更正；按组内共享分评定。"})]
        text = build_group_feedback(reps, "汽服2302B班", "final-project")
        assert "学号已按花名册更正" in text
        assert "安晓童" in text and "23071140211" in text
        assert "记 0 分" not in text  # 保留分数，不应出现记0分段
