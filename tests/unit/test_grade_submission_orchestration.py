#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""grade_submission 编排特征测试（#6 拆巨函数的安全网）。

#2 的 golden 测试覆盖的是**子函数**（编译反馈/源码识别/惩罚/相似度），但
``grade_submission`` 的 7 阶段**编排**（任务路由 → 各类派发 → 汇总 → 难度缩放 →
组长加分 → 等级）此前无 e2e 锚点。这里用 mock 的 build_checker（SUCCESS）避开真实
arm-none-eabi-gcc toolchain，跑通"有源码 + 编译过 + 任务一报告"的完整路径，
锁定编排不变量——#6 重构 grade_submission 任何回归都会被抓住。

断言刻意用**关系不变量**（scaling/边界/路由）而非精确分数，避免 rubric 微调误伤。
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.auto_grading.grading_engine import AutoGradingEngine
from tools.auto_grading.build_checker import BuildResult, BuildStatus
from tools.auto_grading.submission_processor import ProcessedSubmission, ProjectInfo

RUBRIC_PATH = Path(__file__).resolve().parents[2] / "data" / "rubrics" / "final-project.json"


@pytest.fixture(scope="module")
def rubric():
    return json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))


def _stub_build_success(source_path):
    """check_build 恒为 SUCCESS 的 build_checker，避开真实 make。"""
    bc = MagicMock()
    bc.check_build.return_value = BuildResult(
        status=BuildStatus.SUCCESS,
        project_name="test-proj",
        project_path=Path(source_path),
        success=True, duration=1.0, error_count=0, warning_count=0,
        output="Build OK", error_message="",
    )
    bc.set_cancel_event = MagicMock()
    return bc


def _submission(tmp_path, report_text, student_id="23071140108", name="张三"):
    src_dir = tmp_path / "source" / student_id
    src_dir.mkdir(parents=True, exist_ok=True)
    main_c = src_dir / "main.c"
    # 无 HAL_Delay，过非阻塞检测；最小可读 .c
    main_c.write_text("int main(void){ while(1){} return 0; }\n", encoding="utf-8")
    pi = ProjectInfo(
        project_path=src_dir, project_type="simple",
        main_files=[main_c], header_files=[], source_files=[main_c],
        has_makefile=True, has_uvprojx=False,
    )
    sub = ProcessedSubmission(
        student_id=student_id, name=name, class_name="汽服2302B班",
        report_text=report_text, source_path=str(src_dir), project_info=pi,
    )
    sub.group_key = student_id
    sub.group_members = [(student_id, name)]
    return sub, src_dir


# 报告含「我选择任务一」显式声明（命中 _DECLARE_RE）+ 任务一关键词
TASK1_REPORT = (
    "本次实验我选择任务一，多功能灯光系统。"
    "实验目的：掌握 GPIO、按键、状态机、非阻塞延时。"
    "状态转换图：常亮/闪烁/呼吸。模块划分 led/key/main。"
    "关键算法：状态机 + 非阻塞延时。调试过程：示波器排查。"
    "功能测试结果与现象：截图演示。收获心得总结体会，改进不足。"
)


class TestGradeSubmissionOrchestration:
    def test_full_path_scaling_invariants(self, tmp_path, rubric):
        """有源码 + build SUCCESS + 任务一 → 锁编排不变量。"""
        engine = AutoGradingEngine()
        engine.rubric = rubric
        sub, src_dir = _submission(tmp_path, TASK1_REPORT)
        engine.build_checker = _stub_build_success(src_dir)

        result = engine.grade_submission(sub)

        # 任务路由：显式声明任务一
        assert result.detected_task == "task1"
        # 难度系数：task1 = 0.8（rubric 事实）
        assert result.difficulty_ratio == pytest.approx(0.8)
        # 编译项：build SUCCESS → 满分
        comp = next(c for c in result.category_scores if c.category_id == "compilation")
        assert comp.earned_points == comp.max_points
        # **核心 scaling 不变量**：total = eval × 难度系数（#6 重构若改坏汇总会被抓住）
        assert result.total_score == round(result.evaluation_score * result.difficulty_ratio, 1)
        # 边界
        assert 0 <= result.evaluation_score <= 100
        assert result.total_score <= result.evaluation_score  # 难度系数 ≤ 1
        assert result.max_score == 100.0
        # 等级合法
        assert result.grade in ("A", "B", "C", "D", "F")
        # 未声明组长 → 不发组长加分
        assert result.leader_bonus_granted == 0
        assert len(result.category_scores) >= 1

    def test_max_score_100_and_eval_bounded(self, tmp_path, rubric):
        """另一份报告也满足 eval∈[0,100]、total=eval×ratio、max_score=100 的不变量。"""
        engine = AutoGradingEngine()
        engine.rubric = rubric
        report = TASK1_REPORT.replace("任务一", "任务三").replace("多功能灯光系统", "定时迎宾灯系统")
        sub, src_dir = _submission(tmp_path, report, student_id="23071140200", name="李四")
        engine.build_checker = _stub_build_success(src_dir)

        result = engine.grade_submission(sub)

        assert result.detected_task == "task3"
        assert result.difficulty_ratio == pytest.approx(1.0)
        assert result.total_score == round(result.evaluation_score * result.difficulty_ratio, 1)
        assert 0 <= result.evaluation_score <= 100
        assert result.max_score == 100.0
        assert result.grade in ("A", "B", "C", "D", "F")
