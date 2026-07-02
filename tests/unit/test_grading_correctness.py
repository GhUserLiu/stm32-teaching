"""成绩正确性回归测试

覆盖静态审查定位到的 grade-correctness 缺陷簇（均以真实 data/rubrics/rubric.json 为准）：
- grading_scale 边界缝隙（B.max=89.9 / A.min=90）→ 半开区间匹配
- batch_grade 因评分器选择/签名漂移抛 TypeError
- apply_plagiarism_penalty 独立调用读取不存在的 result.grading_scale → AttributeError
- EnhancedRubricGrader.grade 签名与父类不一致（is_leader/experience_info 丢失）

这些缺陷此前无任何测试覆盖（src/tools/plagiarism/tests/ 不在 pytest tests/ 采集范围，
且其用例还引用了不存在的 GradingSystem 与 criteria/max_points 假 schema），故能长期潜伏。
"""

import json
from pathlib import Path

import pytest

from tools.plagiarism.grading import (
    EnhancedRubricGrader,
    PlagiarismThresholds,
    _calculate_grade_from_percentage,
    apply_plagiarism_penalty,
    batch_grade,
)
from tools.auto_grading.grading_engine import detect_team_leader

RUBRIC_PATH = Path(__file__).resolve().parents[2] / "data" / "rubrics" / "rubric.json"

SAMPLE_TEXT = (
    "汽车档位模拟器设计实验报告。"
    "本实验基于 STM32F407 HAL 库，使用 GPIO 配置按键与 LED，通过状态机实现档位切换。"
    "实验原理：不同档位点亮对应 LED，按键消抖采用基于 HAL_GetTick 的非阻塞延时。"
    "代码使用 HAL_GPIO_Init 初始化引脚，主循环读取按键状态并切换档位。"
    "实验完成度：实现了 P/R/N/D 四个档位，按键响应正常，LED 指示正确。"
    "团队协作：组长负责整体设计与代码整合，组员分别负责硬件接线与报告撰写。"
    "报告含原理图、代码截图与测试照片，按时提交。"
)


@pytest.fixture(scope="module")
def rubric():
    return json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))


class TestGradingScaleBoundaries:
    """等级边界：半开区间匹配，89.9/90 之类的缝隙不再落到 F。"""

    def test_exact_boundaries(self, rubric):
        scale = rubric["grading_scale"]
        assert _calculate_grade_from_percentage(100, scale) == "A"
        assert _calculate_grade_from_percentage(90, scale) == "A"
        assert _calculate_grade_from_percentage(89.9, scale) == "B"
        assert _calculate_grade_from_percentage(80, scale) == "B"
        assert _calculate_grade_from_percentage(79.9, scale) == "C"
        assert _calculate_grade_from_percentage(70, scale) == "C"
        assert _calculate_grade_from_percentage(60, scale) == "D"
        assert _calculate_grade_from_percentage(59.9, scale) == "F"
        assert _calculate_grade_from_percentage(0, scale) == "F"

    def test_gap_value_not_f(self, rubric):
        """89.95 落在 B(<=89.9) 与 A(>=90) 的旧缝隙里，必须判 B 而非 F。"""
        scale = rubric["grading_scale"]
        assert _calculate_grade_from_percentage(89.95, scale) == "B"
        assert _calculate_grade_from_percentage(79.95, scale) == "C"
        assert _calculate_grade_from_percentage(69.95, scale) == "D"

    def test_default_scale_gap(self):
        """默认 scale（B 80-89 / A 90-100）的 89.5 缝隙也必须闭合。"""
        assert _calculate_grade_from_percentage(89.5) == "B"
        assert _calculate_grade_from_percentage(89) == "B"
        assert _calculate_grade_from_percentage(90) == "A"


class TestBatchGradeNoCrash:
    """batch_grade 不再因评分器选择/签名问题抛 TypeError。"""

    def test_batch_grade_runs_base(self, rubric):
        submissions = {"2023001": {"name": "张三", "text": SAMPLE_TEXT}}
        results = batch_grade(submissions, rubric, enable_nlp=False)
        assert len(results) == 1
        r = results[0]
        assert r.student_id == "2023001"
        assert 0 <= r.total_score <= rubric["total_points"]

    def test_batch_grade_runs_enhanced(self, rubric):
        submissions = {"2023001": {"name": "张三", "text": SAMPLE_TEXT, "is_leader": True}}
        results = batch_grade(submissions, rubric, enable_nlp=True)
        assert len(results) == 1
        # is_leader 在 5 参签名下必须被正确透传（旧 EnhancedRubricGrader.grade 会 TypeError）
        assert results[0].is_team_leader is True

    def test_enhanced_grader_accepts_leader_kwargs(self, rubric):
        """EnhancedRubricGrader.grade 签名须与父类一致。"""
        grader = EnhancedRubricGrader(rubric)
        r = grader.grade(
            "2023001", "张三", SAMPLE_TEXT,
            is_leader=True, experience_info={"quality": "良好"},
        )
        assert r.is_team_leader is True


class TestApplyPlagiarismPenaltyStandalone:
    """apply_plagiarism_penalty 独立调用不再因 result.grading_scale 缺失而 AttributeError。"""

    def test_severe_penalty_no_crash(self, rubric):
        submissions = {"2023001": {"name": "张三", "text": SAMPLE_TEXT}}
        [result] = batch_grade(submissions, rubric, enable_nlp=False)
        before = result.total_score

        apply_plagiarism_penalty(
            result,
            {"max_similarity": 88.0, "similar_to": "2023002", "is_cross_group": False, "shared_count": 3},
            PlagiarismThresholds(),
            grading_scale=rubric["grading_scale"],
        )
        assert result.total_score <= before
        assert result.plagiarism_info.risk_level == "severe"

    def test_penalty_without_explicit_scale_uses_default(self, rubric):
        """不传 grading_scale 也不应崩溃（回退默认 scale）。"""
        submissions = {"2023001": {"name": "张三", "text": SAMPLE_TEXT}}
        [result] = batch_grade(submissions, rubric, enable_nlp=False)
        apply_plagiarism_penalty(
            result,
            {"max_similarity": 82.0, "similar_to": "2023002", "is_cross_group": False, "shared_count": 1},
        )
        assert result.plagiarism_info.risk_level == "warning"
        assert result.grade in {"A", "B", "C", "D", "F"}


class TestTeamLeaderDetection:
    """组长判定：从报告文本提取；未声明则该组无组长（不加分）。

    批阅按团队展开，组员**共享同一份报告文本**（submission_processor 的 expand_team：
    一份报告 → 每位成员一条提交、report_text 相同）。故第一人称自称（"我是/本人担任/
    作为组长"）无法归因到具体成员——共享报告里此句只出现一次却会被全组成员命中，会把
    全组都判成组长、扰乱组长加分。因此 detect_team_leader 在「提供了姓名」时只认姓名
    特异性写法（"组长：张三"/"张三（组长）"），第一人称自称一律 False；仅在「无姓名
    （单作者报告）」退化路径下才用自称判定（_LEADER_SELF_PATTERNS）。
    """

    @pytest.mark.parametrize("text,name,expect", [
        # 姓名特异性：姓名被声明为组长 → True
        ("组长：张三", "张三", True),
        ("张三（组长）", "张三", True),
        # 声明他人为组长 / 完全未声明 → False
        ("组长：李四，我负责硬件接线。", "张三", False),   # 声明他人为组长
        ("李四（组长），本人负责硬件。", "张三", False),
        ("本实验基于 STM32F407 HAL 库。", "张三", False),  # 完全未声明
        ("", "张三", False),
        # 第一人称自称 + 有姓名：无法归因到具体成员 → False（防共享报告全组命中）
        ("本人担任组长，负责总体设计。", "张三", False),
        ("我是组长，负责整合代码。", "张三", False),
        ("作为组长，我协调组员分工。", "张三", False),
        # 同样的自称在「无姓名（单作者报告）」退化路径下 → True（_LEADER_SELF_PATTERNS）
        ("本人担任组长，负责总体设计。", "", True),
        ("我是组长，负责整合代码。", "", True),
        ("作为组长，我协调组员分工。", "", True),
    ])
    def test_detect(self, text, name, expect):
        assert detect_team_leader(text, name) is expect

