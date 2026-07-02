#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回归 / characterization 测试 —— 抄袭自动扣分核心链路。

被测: tools.plagiarism.grading.grading
  - PlagiarismThresholds (dataclass)
  - apply_plagiarism_penalty(result, similarity_info, thresholds=None, grading_scale=None)

目的: 锁定【当前实际行为】，给后续重构（拆 grade_submission 巨函数、改阈值/正则/单位）
装安全网。任何静默漂移都能被抓住。

运行:
    PYTHONPATH=src python -m pytest tests/unit/test_plagiarism_penalty.py -q
"""

import pytest

from tools.plagiarism.grading.grading import (
    GradingResult,
    PlagiarismInfo,
    PlagiarismThresholds,
    apply_plagiarism_penalty,
)


# ---------------------------------------------------------------------------
# 夹具 / 辅助
# ---------------------------------------------------------------------------

def _make_result(total_score=80.0, total_possible=100.0, grade='B',
                 percentage=80.0, auto_confidence=0.85,
                 grading_scale_attr=None, weaknesses=None):
    """造一个干净的 GradingResult。默认 80/100，B 等，置信度 0.85。"""
    r = GradingResult(
        student_id='S001',
        name='张三',
        total_score=total_score,
        total_possible=total_possible,
        percentage=percentage,
        grade=grade,
        category_scores={},
        auto_confidence=auto_confidence,
        weaknesses=list(weaknesses) if weaknesses else [],
    )
    if grading_scale_attr is not None:
        r.grading_scale = grading_scale_attr
    return r


def _sim_info(max_similarity, similar_to='李四', is_cross_group=False,
              shared_count=3):
    return {
        'max_similarity': max_similarity,
        'similar_to': similar_to,
        'is_cross_group': is_cross_group,
        'shared_count': shared_count,
    }


# ---------------------------------------------------------------------------
# ① 阈值边界：warning(80) / severe(85) / critical(90) 的精确判定
#    审计点名 >90 vs >=90 边界分叉——这里锁死 89.9 与 90.0 各自的精确结果。
#    当前实现：比较一律用 >= 。90.0 命中 critical(记0)，89.9 只命中 severe(扣30)。
# ---------------------------------------------------------------------------

class TestThresholdBoundaries:
    """边界用 >= ，恰好等于阈值即命中本档。"""

    def test_sim_exactly_80_hits_warning_penalty10(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(80.0))
        # 80.0 命中 warning（>=80）
        assert out.total_score == 70.0            # 80 - 10
        assert out.plagiarism_info.risk_level == 'warning'
        assert out.plagiarism_info.penalty_applied == 10.0

    def test_sim_849_below_severe_still_warning(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(84.9))
        assert out.total_score == 70.0            # 仍 warning，扣10
        assert out.plagiarism_info.risk_level == 'warning'
        assert out.plagiarism_info.penalty_applied == 10.0

    def test_sim_exactly_85_hits_severe_penalty30(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(85.0))
        # 85.0 命中 severe（>=85）
        assert out.total_score == 50.0            # 80 - 30
        assert out.plagiarism_info.risk_level == 'severe'
        assert out.plagiarism_info.penalty_applied == 30.0

    def test_sim_exactly_90_hits_critical_zero(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(90.0))
        # 90.0 命中 critical（>=90）→ 直接置 0，grade F
        assert out.total_score == 0.0
        assert out.grade == 'F'
        assert out.plagiarism_info.risk_level == 'critical'
        assert out.plagiarism_info.penalty_applied == 100.0  # critical_penalty

    def test_audit_flagship_boundary_899_vs_900(self):
        """审计点名的 >90 vs >=90 边界分叉，逐点锁死当前口径。"""
        # 89.9 → severe，扣 30，total=50（不归零）
        r1 = _make_result(total_score=80.0)
        out_899 = apply_plagiarism_penalty(r1, _sim_info(89.9))
        assert out_899.plagiarism_info.risk_level == 'severe'
        assert out_899.total_score == 50.0
        assert out_899.plagiarism_info.penalty_applied == 30.0

        # 90.0 → critical，直接归零
        r2 = _make_result(total_score=80.0)
        out_900 = apply_plagiarism_penalty(r2, _sim_info(90.0))
        assert out_900.plagiarism_info.risk_level == 'critical'
        assert out_900.total_score == 0.0
        assert out_900.plagiarism_info.penalty_applied == 100.0
        assert out_900.grade == 'F'

    def test_sim_95_well_above_critical_still_critical(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(95.0))
        assert out.total_score == 0.0
        assert out.grade == 'F'
        assert out.plagiarism_info.risk_level == 'critical'


# ---------------------------------------------------------------------------
# ② 扣分是【绝对分】不是比例
# ---------------------------------------------------------------------------

class TestAbsoluteNotProportional:

    def test_warning_is_absolute_minus_10(self):
        # 若是比例，80% 相似会扣 80*0.x；实际固定扣 10
        r = _make_result(total_score=90.0)
        out = apply_plagiarism_penalty(r, _sim_info(80.0))
        assert out.total_score == 80.0           # 90 - 10，不是比例

    def test_severe_is_absolute_minus_30(self):
        r = _make_result(total_score=95.0)
        out = apply_plagiarism_penalty(r, _sim_info(87.0))
        assert out.total_score == 65.0           # 95 - 30，固定绝对值

    def test_penalty_same_regardless_of_base_score(self):
        # 同样 sim=82，从 100 扣到 90；从 30 扣到 20 —— 扣的【绝对值】恒为 10
        out_high = apply_plagiarism_penalty(_make_result(total_score=100.0),
                                            _sim_info(82.0))
        out_low = apply_plagiarism_penalty(_make_result(total_score=30.0),
                                           _sim_info(82.0))
        assert out_high.total_score == 90.0
        assert out_low.total_score == 20.0
        # 扣的绝对值都等于 warning_penalty，与 base 分无关
        assert out_high.plagiarism_info.penalty_applied == 10.0
        assert out_low.plagiarism_info.penalty_applied == 10.0


# ---------------------------------------------------------------------------
# ③ 低于 warning（且非跨组）不扣
# ---------------------------------------------------------------------------

class TestBelowWarningNoPenalty:

    def test_sim_79_no_penalty_risk_none(self):
        r = _make_result(total_score=80.0, grade='B')
        out = apply_plagiarism_penalty(r, _sim_info(79.0))
        assert out.total_score == 80.0           # 不变
        assert out.plagiarism_info.penalty_applied == 0.0
        assert out.plagiarism_info.risk_level == 'none'
        # grade 不应被改动
        assert out.grade == 'B'
        # auto_confidence 不降低（无扣分）
        assert out.auto_confidence == 0.85

    def test_sim_0_no_penalty(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(0.0))
        assert out.total_score == 80.0
        assert out.plagiarism_info.risk_level == 'none'
        assert out.plagiarism_info.penalty_applied == 0.0

    def test_no_penalty_does_not_append_weakness(self):
        r = _make_result(total_score=80.0, weaknesses=['原始缺点'])
        out = apply_plagiarism_penalty(r, _sim_info(50.0))
        # weaknesses 不应被追加任何抄袭条目
        assert out.weaknesses == ['原始缺点']


# ---------------------------------------------------------------------------
# ④ 扣后是否 floor 到 0 / 是否可能负数
#    warning/severe 走 max(0, score-penalty) —— floor 到 0，不会负。
#    critical 直接 total_score=0。
# ---------------------------------------------------------------------------

class TestFloorToZero:

    def test_severe_underflow_floored_to_zero(self):
        # 80 - 85%，原分 25，扣 30 → 数学上 -5，实际 floor 到 0
        r = _make_result(total_score=25.0)
        out = apply_plagiarism_penalty(r, _sim_info(86.0))
        assert out.total_score == 0.0
        assert out.plagiarism_info.risk_level == 'severe'
        # penalty_applied 仍记录原始扣分值 30，不是 25
        assert out.plagiarism_info.penalty_applied == 30.0

    def test_warning_underflow_floored_to_zero(self):
        r = _make_result(total_score=5.0)
        out = apply_plagiarism_penalty(r, _sim_info(81.0))
        assert out.total_score == 0.0
        assert out.plagiarism_info.risk_level == 'warning'
        assert out.plagiarism_info.penalty_applied == 10.0

    def test_critical_sets_zero_regardless_of_high_base(self):
        r = _make_result(total_score=99.0, grade='A')
        out = apply_plagiarism_penalty(r, _sim_info(95.0))
        # critical 分支直接 total_score=0，不计算减法
        assert out.total_score == 0.0
        assert out.grade == 'F'

    def test_total_score_never_negative(self):
        # 极端：原分 0，仍触发 severe —— floor 保证不出现负数
        r = _make_result(total_score=0.0)
        out = apply_plagiarism_penalty(r, _sim_info(88.0))
        assert out.total_score == 0.0
        assert out.total_score >= 0

    def test_critical_branch_keeps_stale_percentage(self):
        # critical 分支只置 total_score=0 / grade='F'，【不重算 percentage】
        # —— 这是当前实际行为（与 warning/severe 不同），锁死以防误改成重算。
        r = _make_result(total_score=80.0, percentage=77.0, grade='B')
        out = apply_plagiarism_penalty(r, _sim_info(92.0))
        assert out.total_score == 0.0
        assert out.grade == 'F'
        assert out.percentage == 77.0          # 未被改写，仍是原值


# ---------------------------------------------------------------------------
# ⑤ 默认阈值 与 自定义阈值 各覆盖一组
# ---------------------------------------------------------------------------

class TestDefaultVsCustomThresholds:

    def test_default_thresholds_solo_call(self):
        # 不传 thresholds，默认 warning=80/severe=85/critical=90
        r = _make_result(total_score=70.0)
        out = apply_plagiarism_penalty(r, _sim_info(80.0))
        assert out.total_score == 60.0           # 70 - 10 (默认 warning_penalty)

    def test_custom_thresholds_move_boundary(self):
        # 自定义：warning=50/severe=70/critical=90，对应扣分也改
        custom = PlagiarismThresholds(
            warning=50.0, severe=70.0, critical=90.0,
            warning_penalty=15.0, severe_penalty=40.0, critical_penalty=100.0,
        )
        # sim=60 在自定义下命中 warning（>=50），扣自定义 15
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(60.0), thresholds=custom)
        assert out.plagiarism_info.risk_level == 'warning'
        assert out.total_score == 65.0           # 80 - 15
        assert out.plagiarism_info.penalty_applied == 15.0

    def test_custom_thresholds_severe_boundary(self):
        custom = PlagiarismThresholds(
            warning=50.0, severe=70.0, critical=90.0,
            warning_penalty=15.0, severe_penalty=40.0, critical_penalty=100.0,
        )
        # sim=70 恰好命中自定义 severe，扣 40
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(70.0), thresholds=custom)
        assert out.plagiarism_info.risk_level == 'severe'
        assert out.total_score == 40.0           # 80 - 40

    def test_custom_critical_penalty_below_default_100(self):
        # 自定义 critical_penalty 可以不是 100，验证 critical 分支用的是配置值
        # （注意：critical 分支 total_score 恒置 0，但 penalty_applied 反映配置值）
        custom = PlagiarismThresholds(
            warning=80.0, severe=85.0, critical=90.0,
            warning_penalty=10.0, severe_penalty=30.0, critical_penalty=50.0,
        )
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(95.0), thresholds=custom)
        assert out.total_score == 0.0
        assert out.grade == 'F'
        assert out.plagiarism_info.risk_level == 'critical'
        # penalty_applied 走 thresholds.critical_penalty
        assert out.plagiarism_info.penalty_applied == 50.0


# ---------------------------------------------------------------------------
# 附加：plagiarism_info 落库、original_score、auto_confidence、weakness 文本
# ---------------------------------------------------------------------------

class TestPlagiarismInfoAndSideEffects:

    def test_original_score_saved_before_penalty(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(82.0))
        assert out.original_score == 80.0        # 原始分被保存

    def test_plagiar_info_fields_populated(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(
            r, _sim_info(82.0, similar_to='王五', is_cross_group=False,
                         shared_count=7),
        )
        info = out.plagiarism_info
        assert isinstance(info, PlagiarismInfo)
        assert info.max_similarity == 82.0
        assert info.similar_to == '王五'
        assert info.is_cross_group is False
        assert info.shared_count == 7
        assert info.risk_level == 'warning'
        assert info.penalty_applied == 10.0

    def test_auto_confidence_drops_on_penalty(self):
        r = _make_result(total_score=80.0, auto_confidence=0.85)
        out = apply_plagiarism_penalty(r, _sim_info(82.0))
        # 0.85 - 0.15 = 0.70
        assert out.auto_confidence == pytest.approx(0.70)

    def test_auto_confidence_floored_at_05(self):
        # 起始已 0.5，扣分后 max(0.5, 0.5-0.15) = 0.5，不低于 0.5
        r = _make_result(total_score=80.0, auto_confidence=0.5)
        out = apply_plagiarism_penalty(r, _sim_info(82.0))
        assert out.auto_confidence == pytest.approx(0.5)

    def test_no_penalty_keeps_auto_confidence(self):
        r = _make_result(total_score=80.0, auto_confidence=0.85)
        out = apply_plagiarism_penalty(r, _sim_info(50.0))
        assert out.auto_confidence == pytest.approx(0.85)

    def test_warning_weakness_text_exact(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(
            r, _sim_info(82.0, similar_to='李四'),
        )
        # 锁定 weakness 文本模板（含 sim 数值、扣分数）
        assert out.weaknesses[-1] == '⚡ 相似度警告: 与 李四 相似度 82.0%，扣10分'

    def test_severe_weakness_text_exact(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(
            r, _sim_info(88.0, similar_to='李四'),
        )
        assert out.weaknesses[-1] == '⚠️ 高度相似: 与 李四 相似度 88.0%，扣30分'

    def test_critical_weakness_text_exact(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(
            r, _sim_info(92.0, similar_to='李四'),
        )
        assert out.weaknesses[-1] == '🚨 严重抄袭: 与 李四 相似度 92.0%，记0分'


# ---------------------------------------------------------------------------
# ⑥ 跨组轻度扣分分支（is_cross_group && max_sim>=70）
#    以及它在 warning 之下的触发
# ---------------------------------------------------------------------------

class TestCrossGroupBranch:

    def test_cross_group_sim75_penalty5(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(
            r, _sim_info(75.0, is_cross_group=True),
        )
        assert out.total_score == 75.0           # 80 - 5
        assert out.plagiarism_info.risk_level == 'warning'
        assert out.plagiarism_info.penalty_applied == 5.0
        # 跨组分支也走 penalty>0 → auto_confidence 降 0.15（0.85→0.70）
        assert out.auto_confidence == pytest.approx(0.70)

    def test_cross_group_sim_70_boundary_penalty5(self):
        # sim 恰好 70，跨组，命中轻度分支
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(
            r, _sim_info(70.0, is_cross_group=True),
        )
        assert out.total_score == 75.0
        assert out.plagiarism_info.risk_level == 'warning'
        assert out.plagiarism_info.penalty_applied == 5.0

    def test_cross_group_weakness_text_exact(self):
        # 跨组分支有独立 weakness 文本模板（🔍 前缀 + 扣5分），
        # 与 warning/severe/critical 三档并列锁定，防止模板被改坏。
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(
            r, _sim_info(75.0, is_cross_group=True, similar_to='李四'),
        )
        assert out.weaknesses[-1] == '🔍 跨组相似: 与 李四 相似度 75.0%，扣5分'

    def test_warning_takes_precedence_over_cross_group(self):
        # sim=82 同时满足 warning(>=80) 与跨组分支，warning 优先
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(
            r, _sim_info(82.0, is_cross_group=True),
        )
        assert out.total_score == 70.0           # 扣 10（warning），不是扣 5
        assert out.plagiarism_info.penalty_applied == 10.0

    def test_cross_group_below_70_no_penalty(self):
        # 跨组但 sim<70，不触发任何扣分
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(
            r, _sim_info(65.0, is_cross_group=True),
        )
        assert out.total_score == 80.0
        assert out.plagiarism_info.risk_level == 'none'
        assert out.plagiarism_info.penalty_applied == 0.0


# ---------------------------------------------------------------------------
# ⑦ 返回值即传入对象（原地修改 + 返回同对象）；grading_scale 入参
# ---------------------------------------------------------------------------

class TestReturnIdentityAndGradingScale:

    def test_returns_same_object(self):
        r = _make_result(total_score=80.0)
        out = apply_plagiarism_penalty(r, _sim_info(82.0))
        assert out is r                            # 原地修改并返回自身

    def test_grading_scale_explicit_param_recomputes_grade(self):
        # severe 扣 30 后 80→50，50/100=50% → F
        scale = {
            'A': {'min': 90, 'max': 100},
            'B': {'min': 80, 'max': 89},
            'C': {'min': 70, 'max': 79},
            'D': {'min': 60, 'max': 69},
            'F': {'min': 0, 'max': 59},
        }
        r = _make_result(total_score=80.0, grade='B')
        out = apply_plagiarism_penalty(r, _sim_info(88.0), grading_scale=scale)
        assert out.total_score == 50.0
        assert out.percentage == 50.0
        assert out.grade == 'F'                    # 重算等级

    def test_grading_scale_none_falls_back_to_attr(self):
        # grading_scale 不传 → 取 result.grading_scale 属性
        scale = {
            'A': {'min': 90, 'max': 100},
            'B': {'min': 80, 'max': 89},
            'C': {'min': 70, 'max': 79},
            'D': {'min': 60, 'max': 69},
            'F': {'min': 0, 'max': 59},
        }
        r = _make_result(total_score=80.0, grade='B', grading_scale_attr=scale)
        out = apply_plagiarism_penalty(r, _sim_info(88.0))
        assert out.grade == 'F'

    def test_grading_scale_uses_builtin_default_when_absent(self):
        # 不传 grading_scale 且 result 无该属性 → _calculate_grade_from_percentage
        # 用内置默认 scale。80-30=50 → F
        r = _make_result(total_score=80.0, grade='B')  # 无 grading_scale 属性
        out = apply_plagiarism_penalty(r, _sim_info(88.0))
        assert out.total_score == 50.0
        assert out.grade == 'F'

    def test_percentage_recomputed_against_total_possible(self):
        # percentage 重算依赖 total_possible，不是硬编码 100。
        # total_possible=50, severe 扣 30 → total=20 → percentage=20/50*100=40 → F。
        # 锁死: 不可退化成 percentage=total_score 的捷径（仅在 total_possible==100 时成立）。
        r = _make_result(total_score=50.0, total_possible=50.0,
                         percentage=100.0, grade='A')
        out = apply_plagiarism_penalty(r, _sim_info(88.0))
        assert out.total_score == 20.0          # 50 - 30
        assert out.percentage == 40.0           # 20 / 50 * 100，不是 20
        assert out.grade == 'F'
