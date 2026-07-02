"""两项评分修正的回归测试

1. 思考题检测：识别散文式「问…答：…」作答与「思考题N」编号。
   此前只认 Q1/问题1/1.，把逐题作答的报告误报为「0 个题号/未作答」。
2. 未交源码硬性 0 分：not_submitted（及损坏/嵌套/空/纯Keil）一律判 FAILED 计入基数，
   不再走 SKIPPED 排除→rescale 白送约 5 分。仅「有工程但本机缺工具链」才排除（非学生责任）。
"""

import json
from pathlib import Path

import pytest

from tools.auto_grading.grading_engine import AutoGradingEngine, _UNASSESSABLE_BUILD_STATES
from tools.auto_grading.build_checker import BuildStatus
from tools.auto_grading.source_state import (
    SourceState,
    STATE_NOT_SUBMITTED, STATE_EMPTY, STATE_CORRUPTED,
    STATE_NESTED_PROJECT, STATE_KEIL_ONLY,
)
from tools.auto_grading.submission_processor import ProcessedSubmission
from tools.auto_grading.submission_validator import SubmissionValidator, ValidationReport

RUBRIC_PATH = Path(__file__).resolve().parents[2] / "data" / "rubrics" / "final-project.json"


# ----------------------------- Fix 1: 思考题检测 -----------------------------

def _run_thinking(sections_text):
    """直接驱动 _rule_thinking_questions（sections 已切好），返回 ValidationReport。"""
    v = SubmissionValidator()
    v._rubric = {'thinking_check': True,
                 'reference_answers': {'thinking_question_ids': ['Q1', 'Q2', 'Q3']}}
    v._thinking_check = True
    report = ValidationReport()
    v._rule_thinking_questions(None, {'七、思考题': sections_text}, report)
    return report


class TestThinkingQuestionDetection:
    def test_prose_qa_with_answer_markers_is_detected(self):
        """散文式作答（无题号、用「答：」逐题回答）不应被误报为未作答。"""
        text = (
            "通用思考题\n"
            "如果需要增加记忆模式功能，应如何实现？\n"
            "答：使用 RTC 后备寄存器或 Flash 保存当前模式。\n"
            "如何用信号量理解状态切换？\n"
            "答：把每个模式当作事件标志位。\n"
            "任务二专属思考题\n"
            "45℃临界点波动如何避免频繁切换？\n"
            "答：滞回比较，48℃报警、42℃恢复。"
        )
        report = _run_thinking(text)
        assert report.missing_questions == []                      # 三题均已作答
        assert not any(i.rule == 'thinking_questions' for i in report.issues)  # 不再误报

    def test_thinking_header_numbering_is_detected(self):
        """「思考题1/思考题2」等标题式编号应被识别。"""
        text = (
            "思考题1：记忆模式用 RTC BKP 实现。\n"
            "思考题2：信号量即事件标志位。\n"
            "思考题3：滞回比较 48/42℃。"
        )
        report = _run_thinking(text)
        assert report.missing_questions == []

    def test_q_prefix_numbering_still_works(self):
        """回归：Q1/Q2/Q3 显式编号仍正常识别。"""
        text = "Q1 答：RTC。\nQ2 答：事件标志。\nQ3 答：滞回。"
        report = _run_thinking(text)
        assert report.missing_questions == []

    def test_truly_unanswered_reports_missing(self):
        """确未作答时仍如实报缺题。"""
        text = "七、思考题\n（本题选做，略）"   # 无题号、无「答：」
        report = _run_thinking(text)
        assert set(report.missing_questions) == {'Q1', 'Q2', 'Q3'}

    def test_answer_marker_count_capped_at_expected(self):
        """答：标记数超过期望题数时按期望数封顶，不夸大。"""
        text = "答：一\n答：二\n答：三\n答：四\n答：五"   # 5 个「答：」但只期望 3 题
        report = _run_thinking(text)
        assert report.missing_questions == []


# ----------------------------- Fix 2: 未交源码硬性 0 -----------------------------

def _submission_with_state(state):
    """构造一个无可编译工程的提交（source_path/project_info 为空，source_state=给定状态）。"""
    ss = SourceState(
        state=state,
        is_machine_buildable=False,
        feedback_reason="测试原因",
        feedback_fix="测试改进",
    )
    return ProcessedSubmission(
        student_id='23071140212', name='吕艳军', class_name='汽服2302B班',
        report_text='实验报告', source_state=ss,
    )


@pytest.fixture(scope='module')
def rubric():
    return json.loads(RUBRIC_PATH.read_text(encoding='utf-8'))


class TestCompilationHardZeroForStudentFault:
    """学生提交层面的问题（未提交/损坏/嵌套/空/纯Keil）一律 FAILED 计入基数。"""

    @pytest.mark.parametrize('state', [
        STATE_NOT_SUBMITTED, STATE_EMPTY, STATE_CORRUPTED,
        STATE_NESTED_PROJECT, STATE_KEIL_ONLY,
    ])
    def test_student_fault_states_are_failed_not_excluded(self, state):
        engine = AutoGradingEngine()
        sub = _submission_with_state(state)
        cat = {'id': 'compilation', 'name': '编译检查', 'points': 10, 'grading_method': 'build'}
        cs = engine._grade_compilation(sub, cat)
        br = cs.details[0]['build_result']
        assert br.status == BuildStatus.FAILED          # 计入基数，不排除、不 rescale
        assert cs.earned_points == 0
        assert cs.details[0]['source_state'] == state   # 反馈仍带具体状态原因

    def test_failed_not_in_unassessable_set(self):
        """护栏：FAILED 编译永远不会被排除出基数（否则 rescale 复活）。"""
        assert BuildStatus.FAILED not in _UNASSESSABLE_BUILD_STATES


class TestNoRescaleForNotSubmitted:
    """端到端：未交源码的学生不再因 rescale 被白送约 5 分。"""

    def test_not_submitted_evaluation_not_inflated(self, rubric):
        engine = AutoGradingEngine()
        engine.rubric = rubric
        sub = _submission_with_state(STATE_NOT_SUBMITTED)
        # 命中任务二关键词的报告，让报告类拿到非零分（贴近真实 49.8 场景）。
        sub.report_text = (
            "任务二 温度报警系统。实验目的：掌握 ADC、状态机、非阻塞延时。"
            "状态转换图：手动/报警。模块划分 led/key/temp/main。关键算法：ADC 滞回 45℃。"
            "调试过程：示波器排查问题。功能测试结果与现象：截图演示。"
            "收获心得总结体会，改进不足。"
        )
        result = engine.grade_submission(sub)

        # (1) 编译项判 FAILED（计入基数、不排除）
        comp = next(c for c in result.category_scores if c.category_id == 'compilation')
        assert comp.details[0]['build_result'].status == BuildStatus.FAILED

        # (2) 关键不变量：无 rescale → eval = 原始 base + 组长加分，未被 rescale 拉高。
        #     若旧逻辑（SKIPPED→排除 10 分→rescale）复现，eval 会显著大于 base+bonus。
        base = round(sum(c.earned_points for c in result.category_scores), 1)
        granted = getattr(result, 'leader_bonus_granted', 0.0)
        assert result.evaluation_score == round(min(100.0, base + granted), 1)
        # (3) total = eval × 难度系数
        assert result.total_score == round(result.evaluation_score * result.difficulty_ratio, 1)
