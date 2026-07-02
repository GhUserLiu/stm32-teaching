# -*- coding: utf-8 -*-
"""
detect_task 单元测试 —— 任务识别（显式声明优先 + 正文砍思考题 + 否定豁免 + 混杂信号标记）。

覆盖回归点：
- 显式声明"选择了任务一"压过任务清单里的列举词"任务三"（陈星彤/靳皓杰类 bug）
- 否定"不选择任务一…所选任务为任务二"→ task2（组0109 真实案例）
- 思考题段里的"选择任务三"不污染（砍尾段）
- 无显式声明时按 report_declare 关键字回退
- 多任务关键字并存 → ambiguous=True（聂智聪组：需在反馈提示核对）
- 单任务关键字主导 → ambiguous=False
- 真任务三的显式声明保持 task3
"""

import sys
from types import SimpleNamespace

sys.path.insert(0, "src")

from tools.auto_grading.grading_engine import detect_task  # noqa: E402

RUBRIC = {
    "task_detection": {
        "priority": ["task3", "task2", "task1"],
        "report_declare": {
            "task1": ["任务一", "任务1", "转向灯", "双闪", "迎宾模式", "灯光系统"],
            "task2": ["任务二", "任务2", "温度报警", "温度采集", "高温报警"],
            "task3": ["任务三", "任务3", "定时迎宾", "RTC闹钟", "闹钟触发", "查询闹钟"],
        },
        "code_signals": {"task3": ["HAL_RTC"], "task2": ["HAL_ADC"]},
        "fallback": "task1",
    }
}


def _sub(text):
    return SimpleNamespace(report_text=text, source_path=None, project_info=None)


class TestExplicitDeclaration:
    def test_explicit_task1_wins_over_listing(self):
        """'在任务一/二/三中选择了实验任务一'→ task1（列举词'任务三'不再误判）。"""
        t = ("本次实验，团队讨论在任务一，任务二，任务三中选择了实验任务一，"
             "实现转向灯、双闪功能。")
        assert detect_task(_sub(t), RUBRIC, {}) == ("task1", "report", False)

    def test_negation_does_not_match(self):
        """'不选择任务一…所选任务为任务二'→ task2（否定豁免，组0109 真实案例）。"""
        t = "结果：最终不选择任务一，任务三，所选任务为任务二 温度报警与灯光联动系统。"
        assert detect_task(_sub(t), RUBRIC, {}) == ("task2", "report", False)

    def test_explicit_task3_preserved(self):
        """真任务三的显式声明 → task3。"""
        t = "经讨论，本组选择任务三，基于 RTC 实现定时迎宾灯。"
        assert detect_task(_sub(t), RUBRIC, {}) == ("task3", "report", False)

    def test_digit_form_declaration(self):
        """数字形式'选择任务2'也能识别。"""
        t = "我们选择任务2，做温度采集。"
        assert detect_task(_sub(t), RUBRIC, {}) == ("task2", "report", False)


class TestThinkingQuestionCut:
    def test_thinking_question_mentions_do_not_pollute(self):
        """思考题里'如果选择任务三…'不把 task1 误判成 task3（砍尾段）。"""
        t = (
            "本次实验选择任务一，实现转向灯系统。\n"            # 正文声明 task1
            + ("正文" * 60) + "\n"                            # 撑长正文 > 200 字
            "七、思考题\n"
            "如果选择任务三应该怎么做？我会用 RTC 闹钟。\n"    # 思考题提及 任务三
        )
        assert detect_task(_sub(t), RUBRIC, {}) == ("task1", "report", False)


class TestAmbiguousFlag:
    def test_mixed_signals_flagged_ambiguous(self):
        """无显式声明 + 多任务关键字并存 → ambiguous=True（聂智聪组类情形）。"""
        t = "本系统实现转向灯、双闪功能，同时也参考了任务三的 RTC闹钟 与定时迎宾设计。"
        # task1(转向灯/双闪) 与 task3(任务三/RTC闹钟/定时迎宾) 都命中 → ambiguous
        task, src, amb = detect_task(_sub(t), RUBRIC, {})
        assert amb is True
        assert src == "report"

    def test_single_task_keywords_not_ambiguous(self):
        """无显式声明但仅一个任务的关键字命中 → 不 ambiguous（确信）。"""
        t = "本系统基于 RTC闹钟 与定时迎宾实现，未涉及其他任务。"
        task, src, amb = detect_task(_sub(t), RUBRIC, {})
        assert (task, src, amb) == ("task3", "report", False)

    def test_default_is_ambiguous(self):
        """无任何信号 → fallback，ambiguous=True。"""
        t = "本次实验完成了 GPIO 配置与串口通信。"
        assert detect_task(_sub(t), RUBRIC, {}) == ("task1", "default", True)

    def test_empty_report_ambiguous(self):
        assert detect_task(_sub(""), RUBRIC, {}) == ("task1", "default", True)


class TestKeywordFallback:
    def test_keyword_task1_when_no_explicit(self):
        """无显式声明、正文仅 task1 关键字 → task1，不 ambiguous。"""
        t = "本实验实现转向灯与双闪功能，使用 GPIO 控制灯光。"
        assert detect_task(_sub(t), RUBRIC, {}) == ("task1", "report", False)
