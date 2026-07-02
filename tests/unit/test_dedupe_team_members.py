# -*- coding: utf-8 -*-
"""
dedupe_team_members 单元测试

覆盖：
- 自评归因优先（学号命中源码目录名）——不被队友源码覆盖
- 无自评时回退最高分（共享组长源码）
- 同组勿重复提交提醒（关联>1个不同源码目录才触发）
- 个人实验（无重复）为空操作
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "src")

from tools.auto_grading.grading_engine import (
    dedupe_team_members,
    GradingResult,
)
from tools.auto_grading.build_checker import BuildResult, BuildStatus


def _make_result(sid, name, source_dir_name, score, bonus=0.0, issues=None,
                 group_key="", group_members=None):
    """构造一个 GradingResult，compilation_result.project_path 指向给定源码目录名。

    source_dir_name=None 表示无源码（compilation_result 置空，模拟 not_submitted）。
    group_key/group_members 用于测试组级 group_submitter_count 盖章。
    """
    r = GradingResult(
        student_id=sid,
        name=name,
        class_name="汽服2301B班",
        total_score=score,
        max_score=100.0,
        bonus_total=bonus,
        grade="N/A",
        group_key=group_key,
        group_members=list(group_members or []),
        issues=list(issues or []),
    )
    # project_path.name 即源码目录名（模拟 organizer 产出的 ...-源代码 目录）
    if source_dir_name is not None:
        r.compilation_result = BuildResult(
            status=BuildStatus.SKIPPED,
            project_name=f"{sid}-{name}",
            project_path=Path(source_dir_name),
            success=False,
        )
    return r


class TestSelfSourcedPreference:
    def test_prefers_self_over_higher_scoring_teammate(self):
        """138 自评(keil,低分) vs 134 报告里的 138(嵌套,高分) → 保留自评。"""
        self_src = "汽服2301B班-23071140138-范才兴-源代码"
        mate_src = "汽服2301B班-23071140134-聂智聪-源代码"
        # 自评低分、队友源码(在134报告里)高分
        r_self = _make_result("23071140138", "范才兴", self_src, score=40.0)
        r_mate = _make_result("23071140138", "范才兴", mate_src, score=80.0)
        out = dedupe_team_members([r_self, r_mate])
        assert len(out) == 1
        # 即使队友那条分数更高，也保留自评
        assert out[0].total_score == 40.0
        assert Path(out[0].compilation_result.project_path).name == self_src

    def test_falls_back_to_max_when_no_self(self):
        """该生仅作为组员出现(无自评) → 取最高分。"""
        a = _make_result("23071140140", "张磊", "汽服2301B班-23071140134-聂智聪-源代码", 60.0)
        b = _make_result("23071140140", "张磊", "汽服2301B班-23071140138-范才兴-源代码", 80.0)
        out = dedupe_team_members([a, b])
        assert len(out) == 1
        assert out[0].total_score == 80.0

    def test_single_result_passthrough(self):
        r = _make_result("23071140141", "李全", "汽服2301B班-23071140141-李全-源代码", 50.0)
        out = dedupe_team_members([r])
        assert out == [r]


class TestDuplicateSubmissionReminder:
    def test_reminder_added_when_multiple_distinct_sources(self):
        """关联>1个不同源码目录 → 追加「同组勿重复提交」提醒。"""
        self_src = "汽服2301B班-23071140138-范才兴-源代码"
        r_self = _make_result("23071140138", "范才兴", self_src, 40.0)
        r_mate = _make_result("23071140138", "范才兴", "汽服2301B班-23071140134-聂智聪-源代码", 80.0)
        out = dedupe_team_members([r_self, r_mate])
        reminders = [i for i in out[0].issues if i.get("criterion") == "同组勿重复提交"]
        assert len(reminders) == 1
        assert reminders[0]["severity"] == "info"
        assert reminders[0]["points_lost"] == 0

    def test_no_reminder_when_same_source_only(self):
        """多份结果但同一源码目录(同一份被多次上传) → 不提醒。"""
        src = "汽服2301B班-23071140134-聂智聪-源代码"
        # 同一源码目录、不同分数（模拟同一份报告被多次处理）
        r1 = _make_result("23071140134", "聂智聪", src, 70.0)
        r2 = _make_result("23071140134", "聂智聪", src, 75.0)
        out = dedupe_team_members([r1, r2])
        reminders = [i for i in out[0].issues if i.get("criterion") == "同组勿重复提交"]
        assert reminders == []

    def test_no_reminder_for_single_result(self):
        r = _make_result("23071140141", "李全", "汽服2301B班-23071140141-李全-源代码", 50.0)
        out = dedupe_team_members([r])
        assert out[0].issues == []


class TestOrderPreservation:
    def test_output_preserves_first_appearance_order(self):
        r_b = _make_result("23071140140", "张磊", "汽服2301B班-23071140140-张磊-源代码", 50.0)
        r_a = _make_result("23071140138", "范才兴", "汽服2301B班-23071140138-范才兴-源代码", 60.0)
        out = dedupe_team_members([r_b, r_a])
        # 按首次出现顺序：张磊 在前
        assert out[0].student_id == "23071140140"
        assert out[1].student_id == "23071140138"


class TestSubmitterCount:
    """group_submitter_count：本组「各自提交源码」的去重人数（≥2 触发重复提交提醒）。"""

    GK = "23071140125"
    MEMBERS = [("23071140125", "靳皓杰"), ("23071140135", "薛松涛"), ("23071140136", "李志飞")]

    def test_count_three_when_all_members_self_submit(self):
        """3 人各自提交（每人源码目录含本人学号）→ count=3，全组同值。"""
        out = dedupe_team_members([
            _make_result("23071140125", "靳皓杰", "汽服2301B班-23071140125-靳皓杰-源代码", 81.9,
                         group_key=self.GK, group_members=self.MEMBERS),
            _make_result("23071140135", "薛松涛", "汽服2301B班-23071140135-薛松涛-源代码", 65.0,
                         group_key=self.GK, group_members=self.MEMBERS),
            _make_result("23071140136", "李志飞", "汽服2301B班-23071140136-李志飞-源代码", 76.9,
                         group_key=self.GK, group_members=self.MEMBERS),
        ])
        assert {r.group_submitter_count for r in out} == {3}

    def test_count_one_when_only_leader_submits(self):
        """仅组长提交，组员回退到组长源码（学号不命中）→ count=1。"""
        leader_src = "汽服2301B班-23071140125-靳皓杰-源代码"
        out = dedupe_team_members([
            _make_result("23071140125", "靳皓杰", leader_src, 81.9,
                         group_key=self.GK, group_members=self.MEMBERS),
            _make_result("23071140135", "薛松涛", leader_src, 81.9,
                         group_key=self.GK, group_members=self.MEMBERS),
            _make_result("23071140136", "李志飞", leader_src, 81.9,
                         group_key=self.GK, group_members=self.MEMBERS),
        ])
        assert {r.group_submitter_count for r in out} == {1}

    def test_count_two_when_two_of_three_submit(self):
        """组长 + 一名组员各自提交，另一组员回退到组长源码 → count=2。"""
        out = dedupe_team_members([
            _make_result("23071140125", "靳皓杰", "汽服2301B班-23071140125-靳皓杰-源代码", 81.9,
                         group_key=self.GK, group_members=self.MEMBERS),
            _make_result("23071140135", "薛松涛", "汽服2301B班-23071140135-薛松涛-源代码", 65.0,
                         group_key=self.GK, group_members=self.MEMBERS),
            _make_result("23071140136", "李志飞", "汽服2301B班-23071140125-靳皓杰-源代码", 81.9,
                         group_key=self.GK, group_members=self.MEMBERS),
        ])
        assert {r.group_submitter_count for r in out} == {2}

    def test_count_zero_when_no_source(self):
        """全组均无源码 → count=0（不误触发提醒）。"""
        out = dedupe_team_members([
            _make_result("23071140125", "靳皓杰", None, 50.0,
                         group_key=self.GK, group_members=self.MEMBERS),
            _make_result("23071140135", "薛松涛", None, 50.0,
                         group_key=self.GK, group_members=self.MEMBERS),
        ])
        assert {r.group_submitter_count for r in out} == {0}

    def test_count_not_set_for_individual_experiment(self):
        """个人实验（无 group_key）→ 不盖章，保持默认 0。"""
        r = _make_result("23071140141", "李全", "汽服2301B班-23071140141-李全-源代码", 50.0)
        out = dedupe_team_members([r])
        assert out[0].group_submitter_count == 0


class TestLeaderBonusReconciliation:
    """组长加分按组人数校正：多组长 ⌈5/组长人数⌉ 平摊；无组长(member_count>=2) 全员平摊。"""

    RUBRIC = {'leader_bonus': 5, 'grading_scale': {
        'A': {'min': 90, 'max': 100}, 'B': {'min': 80, 'max': 89.9},
        'C': {'min': 70, 'max': 79.9}, 'D': {'min': 60, 'max': 69.9},
        'F': {'min': 0, 'max': 59.9}}}
    MEMBERS3 = [('1', '甲'), ('2', '乙'), ('3', '丙')]

    def _gresult(self, sid, name, leader, eval_pre=70.0, ratio=0.9, gk='G1', members=None):
        """模拟 grade_submission 产出：is_leader 时先发临时全额 leader_bonus(=5)。"""
        granted = round(min(5, max(100 - eval_pre, 0.0)), 1) if leader else 0.0
        return GradingResult(
            student_id=sid, name=name, class_name="汽服2302B班",
            evaluation_score=round(eval_pre + granted, 1),
            difficulty_ratio=ratio,
            total_score=round((eval_pre + granted) * ratio, 1),
            max_score=100.0, bonus_total=granted,
            is_team_leader=leader, leader_bonus_granted=granted,
            group_key=gk, group_members=list(members or []), grade="N/A",
        )

    def test_two_leaders_of_three_get_3_each(self):
        """3 人 2 组长 → 各 ⌈5/2⌉=3；非组长组员不加。"""
        out = dedupe_team_members([
            self._gresult("1", "甲", True, members=self.MEMBERS3),
            self._gresult("2", "乙", True, members=self.MEMBERS3),
            self._gresult("3", "丙", False, members=self.MEMBERS3),
        ], rubric=self.RUBRIC)
        by_name = {r.name: r for r in out}
        assert by_name["甲"].bonus_total == 3.0
        assert by_name["乙"].bonus_total == 3.0
        assert by_name["甲"].leader_bonus_granted == 3.0
        assert by_name["丙"].bonus_total == 0.0   # 非组长不动

    def test_three_leaders_get_2_each(self):
        """3 人全组长 → 各 ⌈5/3⌉=2。"""
        out = dedupe_team_members([
            self._gresult("1", "甲", True, members=self.MEMBERS3),
            self._gresult("2", "乙", True, members=self.MEMBERS3),
            self._gresult("3", "丙", True, members=self.MEMBERS3),
        ], rubric=self.RUBRIC)
        assert {r.bonus_total for r in out} == {2.0}

    def test_no_leader_group_all_members_share(self):
        """3 人无人声明组长 → 视作全员组长，各 ⌈5/3⌉=2。"""
        out = dedupe_team_members([
            self._gresult("1", "甲", False, members=self.MEMBERS3),
            self._gresult("2", "乙", False, members=self.MEMBERS3),
            self._gresult("3", "丙", False, members=self.MEMBERS3),
        ], rubric=self.RUBRIC)
        assert {r.bonus_total for r in out} == {2.0}

    def test_two_member_no_leader_get_3_each(self):
        """2 人无人声明组长 → 各 ⌈5/2⌉=3。"""
        mem = [('1', '甲'), ('2', '乙')]
        out = dedupe_team_members([
            self._gresult("1", "甲", False, gk='G2', members=mem),
            self._gresult("2", "乙", False, gk='G2', members=mem),
        ], rubric=self.RUBRIC)
        assert {r.bonus_total for r in out} == {3.0}

    def test_single_leader_unchanged(self):
        """唯一组长 → 临时全额 +5 即正确，不校正。"""
        out = dedupe_team_members([
            self._gresult("1", "甲", True, members=self.MEMBERS3),
            self._gresult("2", "乙", False, members=self.MEMBERS3),
            self._gresult("3", "丙", False, members=self.MEMBERS3),
        ], rubric=self.RUBRIC)
        assert [r for r in out if r.is_team_leader][0].bonus_total == 5.0

    def test_solo_no_leader_gets_5(self):
        """单人组无人声明组长 → 视作自身组长，⌈5/1⌉=5（规则对单人组同样适用）。"""
        solo = [('1', '甲')]
        out = dedupe_team_members(
            [self._gresult("1", "甲", False, gk='S', members=solo)], rubric=self.RUBRIC)
        assert out[0].bonus_total == 5.0
        assert out[0].leader_bonus_granted == 5.0
        assert out[0].is_team_leader is False   # 标志位不改（仅加分按规则发放）

    def test_solo_leader_gets_5(self):
        """单人组组长 → ⌈5/1⌉=5，不校正。"""
        solo = [('1', '甲')]
        out = dedupe_team_members(
            [self._gresult("1", "甲", True, gk='S', members=solo)], rubric=self.RUBRIC)
        assert out[0].bonus_total == 5.0

    def test_total_and_grade_recomputed(self):
        """校正后评价分/总分/等级同步重算：2 组长 eval_pre=70 → +3 → eval73→total65.7→D。"""
        out = dedupe_team_members([
            self._gresult("1", "甲", True, eval_pre=70.0, members=self.MEMBERS3),
            self._gresult("2", "乙", True, eval_pre=70.0, members=self.MEMBERS3),
            self._gresult("3", "丙", False, eval_pre=70.0, members=self.MEMBERS3),
        ], rubric=self.RUBRIC)
        a = next(r for r in out if r.name == "甲")
        assert a.evaluation_score == 73.0
        assert a.total_score == round(73.0 * 0.9, 1)
        assert a.grade == "D"

    def test_headroom_capped(self):
        """评价分接近满分时按 headroom 封顶：eval_pre=98 old=2；2 组长 per_leader=3 但 headroom=2 → +2。"""
        out = dedupe_team_members([
            self._gresult("1", "甲", True, eval_pre=98.0, members=self.MEMBERS3),
            self._gresult("2", "乙", True, eval_pre=70.0, members=self.MEMBERS3),
            self._gresult("3", "丙", False, eval_pre=70.0, members=self.MEMBERS3),
        ], rubric=self.RUBRIC)
        a = next(r for r in out if r.name == "甲")
        assert a.bonus_total == 2.0          # headroom 限制
        assert a.evaluation_score == 100.0

    def test_backward_compat_without_rubric(self):
        """不传 rubric（自检/单提交路径）→ 不校正，保留临时全额 +5。"""
        out = dedupe_team_members([
            self._gresult("1", "甲", True, members=self.MEMBERS3),
            self._gresult("2", "乙", True, members=self.MEMBERS3),
            self._gresult("3", "丙", True, members=self.MEMBERS3),
        ])  # 不传 rubric
        assert {r.bonus_total for r in out} == {5.0}

    def test_multi_leader_advisory_issue_added(self):
        """多组长校正后追加说明性 issue（machine/teacher 可读）。"""
        out = dedupe_team_members([
            self._gresult("1", "甲", True, members=self.MEMBERS3),
            self._gresult("2", "乙", True, members=self.MEMBERS3),
            self._gresult("3", "丙", False, members=self.MEMBERS3),
        ], rubric=self.RUBRIC)
        a = next(r for r in out if r.name == "甲")
        adv = [i for i in a.issues if i.get("criterion") == "同组组长加分平摊"]
        assert len(adv) == 1
        assert adv[0]["points_lost"] == 0


class TestReporterCount:
    """group_reporter_count：同组「各自上传报告」的去重人数（报告维度）。
    = 组内结果数 ÷ 组员数（每份报告展开为 组员数 条）。≥2 触发"同组只交一份"提醒。"""

    GK = "G1"
    MEMBERS = [("1", "甲"), ("2", "乙")]

    def test_two_reporters_when_both_members_upload(self):
        """甲、乙各交一份报告(各展开成甲+乙) = 4 条结果 / 2 组员 → reporter=2。"""
        out = dedupe_team_members([
            _make_result("1", "甲", None, 80.0, group_key=self.GK, group_members=self.MEMBERS),
            _make_result("2", "乙", None, 80.0, group_key=self.GK, group_members=self.MEMBERS),
            _make_result("1", "甲", None, 80.0, group_key=self.GK, group_members=self.MEMBERS),
            _make_result("2", "乙", None, 80.0, group_key=self.GK, group_members=self.MEMBERS),
        ])
        assert {r.group_reporter_count for r in out} == {2}

    def test_one_reporter_when_only_leader_uploads(self):
        """仅组长一份报告，展开成甲+乙 = 2 条 / 2 组员 → reporter=1（不触发提醒）。"""
        out = dedupe_team_members([
            _make_result("1", "甲", None, 80.0, group_key=self.GK, group_members=self.MEMBERS),
            _make_result("2", "乙", None, 80.0, group_key=self.GK, group_members=self.MEMBERS),
        ])
        assert {r.group_reporter_count for r in out} == {1}

    def test_individual_experiment_no_stamp(self):
        """个人实验（无 group_key）→ 不盖章，保持默认 0。"""
        out = dedupe_team_members([_make_result("1", "甲", None, 50.0)])
        assert out[0].group_reporter_count == 0


class TestIdCollision:
    """学号重号检测：同一学号关联 ≥2 个不同姓名(非同名异写) → 幸存 best[sid] 盖告警；不改去重行为。"""

    def test_real_collision_raises_advisory(self):
        """210 王倩倩/安晓童(无共同汉字)→ 幸存者 issues 含「学号重号」告警，输出仍 1 条。"""
        out = dedupe_team_members([
            _make_result("23071140210", "王倩倩", "汽服2302B班-23071140210-王倩倩-源代码", 92.1),
            _make_result("23071140210", "安晓童", "汽服2302B班-23071140237-刘烊宏-源代码", 76.5),
        ])
        assert len(out) == 1                      # 去重行为不变
        adv = [i for i in out[0].issues if i.get("category") == "学号重号"]
        assert len(adv) == 1
        assert adv[0]["severity"] == "warning"
        assert adv[0]["points_lost"] == 0
        assert "王倩倩" in adv[0]["message"] and "安晓童" in adv[0]["message"]

    def test_advisory_on_surviving_best_not_dropped(self):
        """告警盖在幸存(自评/高分)那条上，不随被并掉的低分那条消失。"""
        out = dedupe_team_members([
            _make_result("23071140210", "王倩倩", "汽服2302B班-23071140210-王倩倩-源代码", 92.1),
            _make_result("23071140210", "安晓童", "汽服2302B班-23071140237-刘烊宏-源代码", 50.0),
        ])
        assert out[0].name == "王倩倩"            # 王倩倩自评命中 → 幸存
        assert any(i.get("category") == "学号重号" for i in out[0].issues)

    def test_variant_names_no_false_alarm(self):
        """119 畅邵坤/畅绍坤(差1字,同人)→ 不告警。"""
        out = dedupe_team_members([
            _make_result("23071140119", "畅邵坤", "汽服2301B班-23071140119-畅邵坤-源代码", 80.0),
            _make_result("23071140119", "畅绍坤", "汽服2301B班-23071140119-畅绍坤-源代码", 80.0),
        ])
        assert not any(i.get("category") == "学号重号" for i in out[0].issues)

    def test_variant_zhizong_no_false_alarm(self):
        """134 聂智聪/聂志聪(队友写错,同人)→ 不告警。"""
        out = dedupe_team_members([
            _make_result("23071140134", "聂智聪", "汽服2301B班-23071140134-聂智聪-源代码", 74.1),
            _make_result("23071140134", "聂志聪", "汽服2301B班-23071140138-范才兴-源代码", 60.0),
        ])
        assert not any(i.get("category") == "学号重号" for i in out[0].issues)

    def test_same_name_uploads_no_collision(self):
        """同 sid + 同姓名(纯重复上传)→ 不触发重号告警(由「同组勿重复提交」另覆盖)。"""
        out = dedupe_team_members([
            _make_result("23071140141", "李全", "汽服2301B班-23071140141-李全-源代码", 70.0),
            _make_result("23071140141", "李全", "汽服2301B班-23071140141-李全-源代码", 75.0),
        ])
        assert not any(i.get("category") == "学号重号" for i in out[0].issues)

    def test_single_result_no_advisory(self):
        """单结果 → 无重号告警（回归保护）。"""
        out = dedupe_team_members([_make_result("23071140141", "李全", "x", 50.0)])
        assert not any(i.get("category") == "学号重号" for i in out[0].issues)
