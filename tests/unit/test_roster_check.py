# -*- coding: utf-8 -*-
"""
roster_check 单元测试 —— 教务花名册身份核验 + 公平性区分。

教师 2026-06-28 口径：
- 学号填错撞别人 → 按姓名反查真实学号 re-key。
  · **本人提交却填错学号**(源码目录含己学号，如 陈乐莹 102→202) → 自己的错 → 记 0 分。
  · **仅被队友在团队表填错、本人未提交**(源码目录是组长的，如 安晓童 210→211、申凯丽 108→107)
    → 队友的错 → 更正学号、保留组内继承分、仅警告（公平性：不连累被别人填错的当事人）。
- 同人异写(畅邵坤/畅绍坤、聂志聪/聂智聪) → 仅警告不扣分。
"""

import sys
from pathlib import Path

sys.path.insert(0, "src")

from tools.auto_grading.grading_engine import GradingResult
from tools.auto_grading.build_checker import BuildResult, BuildStatus
from tools.auto_grading.roster_check import validate_identities, load_id_roster


ROSTER = {
    "by_id": {
        "23071140210": "王倩倩", "23071140211": "安晓童",
        "23071140108": "张丽娟", "23071140107": "申凯丽",
        "23071140102": "杨凯辉", "23071140202": "陈乐莹",
        "23071140119": "畅绍坤", "23071140134": "聂智聪",
    },
    "by_name": {
        "王倩倩": ["23071140210"], "安晓童": ["23071140211"],
        "张丽娟": ["23071140108"], "申凯丽": ["23071140107"],
        "杨凯辉": ["23071140102"], "陈乐莹": ["23071140202"],
        "畅绍坤": ["23071140119"], "聂智聪": ["23071140134"],
    },
}


def _r(sid, name, score=80.0, gk="", leader=False, src=None):
    """构造 GradingResult。src=源码目录名(含学号→判定本人提交)；不传则无源码(组员展开态)。"""
    r = GradingResult(
        student_id=sid, name=name, class_name="汽服2302B班",
        total_score=score, max_score=100.0, bonus_total=5.0 if leader else 0.0,
        grade="C", group_key=gk, group_members=[], issues=[],
        is_team_leader=leader, leader_bonus_granted=5.0 if leader else 0.0,
    )
    if src:
        r.compilation_result = BuildResult(
            status=BuildStatus.SKIPPED, project_name=f"{sid}-{name}",
            project_path=Path(src), success=False)
    return r


def _id_issues(r):
    return [i for i in r.issues if i.get("category") == "身份核验"]


class TestValidateIdentities:
    def test_valid_passes_unchanged(self):
        r = _r("23071140210", "王倩倩", score=92.1)
        out = validate_identities([r], ROSTER)
        assert out[0].total_score == 92.1 and out[0].student_id == "23071140210"
        assert _id_issues(out[0]) == []

    # ---- 学号填错：本人提交 → 记0分 ----
    def test_wrong_id_self_submitted_zeroed(self):
        """陈乐莹 本人提交但学号填 102(实202) → 记0分、re-key 202。"""
        r = _r("23071140102", "陈乐莹", score=88.0,
               src="汽服2302B班-23071140102-陈乐莹-源代码")  # 源码含 102 → 本人提交
        out = validate_identities([r], ROSTER)
        assert out[0].student_id == "23071140202"
        assert out[0].total_score == 0.0 and out[0].grade == "F"
        ie = _id_issues(out[0])
        assert ie[0]["severity"] == "error" and ie[0]["criterion"] == "学号错误"

    # ---- 学号填错：仅被队友填报、本人未提交 → 更正学号、保留分、仅警告（公平性）----
    def test_wrong_id_teammember_corrected_keeps_score(self):
        """安晓童 从刘烊宏报告展开(源码是刘烊宏的)、本人未提交 → re-key 211、保留 76.5、警告。"""
        r = _r("23071140210", "安晓童", score=76.5, gk="23071140206",
               src="汽服2302B班-23071140237-刘烊宏-源代码")  # 源码不含 210 → 非本人提交
        out = validate_identities([r], ROSTER)
        assert out[0].student_id == "23071140211"     # re-key 防撞号
        assert out[0].total_score == 76.5             # 保留组内继承分，不记0
        assert out[0].grade == "C"                    # 等级不动
        ie = _id_issues(out[0])
        assert ie[0]["severity"] == "warning"         # 仅警告
        assert "23071140211" in ie[0]["message"]

    def test_wrong_id_shenkaili_teammember_corrected(self):
        """申凯丽 仅作为组员被填 108(实107)、本人未提交 → re-key 107、保留分、警告。"""
        r = _r("23071140108", "申凯丽", score=70.0)   # 无源码 → 非本人提交
        out = validate_identities([r], ROSTER)
        assert out[0].student_id == "23071140107"
        assert out[0].total_score == 70.0             # 不记0
        assert _id_issues(out[0])[0]["severity"] == "warning"

    # ---- 同人异写：仅 info 警告，不扣分 ----
    def test_variant_name_only_warned(self):
        r = _r("23071140119", "畅邵坤", score=80.0,
               src="汽服2301B班-23071140119-畅邵坤-源代码")
        out = validate_identities([r], ROSTER)
        assert out[0].total_score == 80.0 and out[0].student_id == "23071140119"
        ie = _id_issues(out[0])
        assert len(ie) == 1 and ie[0]["severity"] == "info"

    def test_variant_zhizong_only_warned(self):
        r = _r("23071140134", "聂志聪", score=74.1)
        out = validate_identities([r], ROSTER)
        assert out[0].total_score == 74.1
        assert _id_issues(out[0])[0]["severity"] == "info"

    # ---- 其他罕见情况：仍记0分 ----
    def test_name_wrong_id_in_roster_name_absent(self):
        """学号在册属别人、姓名花名册查无 → 姓名错误、记0分。"""
        r = _r("23071140210", "编造的姓名", score=60.0)
        out = validate_identities([r], ROSTER)
        assert out[0].total_score == 0.0 and out[0].student_id == "23071140210"
        assert _id_issues(out[0])[0]["criterion"] == "姓名错误"

    def test_both_absent_unknown(self):
        r = _r("99999999999", "陌生人", score=50.0)
        out = validate_identities([r], ROSTER)
        assert out[0].total_score == 0.0
        assert _id_issues(out[0])[0]["criterion"] == "身份未识别"

    def test_name_ambiguity_not_rekeyed(self):
        roster = {
            "by_id": {"23071140210": "王倩倩"},
            "by_name": {"王倩倩": ["23071140210", "23071140999"]},
        }
        r = _r("23071140108", "王倩倩", score=70.0)
        out = validate_identities([r], roster)
        assert out[0].total_score == 0.0 and out[0].student_id == "23071140108"

    def test_self_submitted_zero_clears_leader_bonus(self):
        """本人提交填错学号被记0分 → 取消组长加分（防 dedupe 复算）。"""
        r = _r("23071140102", "陈乐莹", score=88.0, leader=True,
               src="汽服2302B班-23071140102-陈乐莹-源代码")
        out = validate_identities([r], ROSTER)
        assert out[0].is_team_leader is False
        assert out[0].bonus_total == 0.0 and out[0].leader_bonus_granted == 0.0

    def test_no_roster_passthrough(self):
        r = _r("23071140210", "王倩倩", score=92.1)
        out = validate_identities([r], None)
        assert out[0].total_score == 92.1 and _id_issues(out[0]) == []


class TestLoadIdRoster:
    def test_loads_real_roster(self):
        """真实 .xls 花名册：80 人，关键学号-姓名映射正确。"""
        roster = load_id_roster(Path("data/teaching/2026-春季"))
        assert roster is not None
        by_id = roster["by_id"]
        assert len(by_id) >= 80
        assert by_id["23071140210"] == "王倩倩"
        assert by_id["23071140211"] == "安晓童"
        assert by_id["23071140107"] == "申凯丽"
        assert by_id["23071140108"] == "张丽娟"
        assert roster["by_name"]["安晓童"] == ["23071140211"]

    def test_returns_none_when_no_roster(self, tmp_path):
        assert load_id_roster(tmp_path) is None
