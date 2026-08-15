#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SimilarityService 单测（P3 收官：分引擎编排）。

核心断言：文字与代码分引擎分阈值（同报告不同代码 → 文字命中/代码不命中；
不同报告同代码 → 代码命中 plagiarism 级）；同代码且该代码恰为模板时
（engine_options 注入 template_code）不再命中；输出形状与 legacy
detect 三元组兼容；阈值全部来自统一配置层；verdict 边界精确。
"""

import pytest

from core.services.similarity_service import (
    SimilarityService,
    verdict_for,
)
from schemas import get_settings
from tools.plagiarism.core.detector import SimilarityResult

REPORT_A = ("基于STM32F407单片机的汽车档位模拟器设计实验报告。"
            "本文介绍了系统的总体方案，包括硬件电路设计与软件程序设计两大部分，"
            "并给出了调试过程与结果分析。")
REPORT_A2 = ("基于STM32F407单片机的汽车档位模拟器设计实验总结。"
             "本文说明了系统的总体方案，涵盖硬件电路设计与软件程序设计两大部分，"
             "并附有调试过程与结果分析。")     # 近重复（改写若干词）
REPORT_B = "今天校园里的桂花开了，我们组织了一次班级秋游活动，大家玩得很开心。"
REPORT_C = "微波炉是一种常见的家用电器，其工作原理是利用微波使食物分子振动发热。"

CODE_X = """
int main(void)
{
    HAL_Init();
    while (1) { HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5); HAL_Delay(500); }
}
"""

CODE_Y = """
int main(void)
{
    HAL_Init();
    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_0)) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);
    }
}
"""

# S3/S4 共享的第三种实现（与 X/Y 都不同；夹具早期版本误用 CODE_X 导致
# S1/S3 成为同代码对——已修正，S1/S3 现在才是真正的"互不相关"对）
CODE_Z = """
void UART_SendString(const char *s)
{
    while (*s) {
        while (!(USART1->SR & USART_SR_TXE)) { }
        USART1->DR = (uint8_t)(*s++);
    }
}
"""

SUBS = {
    "S1": {"name": "甲", "text": REPORT_A, "code": CODE_X, "class": "C1"},
    "S2": {"name": "乙", "text": REPORT_A2, "code": CODE_Y, "class": "C1"},
    "S3": {"name": "丙", "text": REPORT_B, "code": CODE_Z, "class": "C2"},
    "S4": {"name": "丁", "text": REPORT_C, "code": CODE_Z, "class": "C2"},
}


def _pair(all_results, a, b):
    for r in all_results.get(a, []):
        if {r.student_id, r.similar_to} == {a, b}:
            return r
    return None


# ------------------------------------------------------------- verdict bands

def test_verdict_boundaries_exact():
    bands = [("plagiarism", 85), ("high", 70), ("suspicious", 60)]
    assert verdict_for(59.99, bands) is None
    assert verdict_for(60.0, bands) == "suspicious"
    assert verdict_for(69.99, bands) == "suspicious"
    assert verdict_for(70.0, bands) == "high"
    assert verdict_for(84.99, bands) == "high"
    assert verdict_for(85.0, bands) == "plagiarism"
    assert verdict_for(100.0, bands) == "plagiarism"


def test_bands_come_from_settings():
    service = SimilarityService()
    t = get_settings().plagiarism.thresholds
    assert service.text_bands == [("plagiarism", t.plagiarism),
                                  ("high", t.high_similarity),
                                  ("suspicious", t.suspicious)]
    assert service.code_bands == [("plagiarism", t.code_similar),
                                  ("suspicious", t.high_similarity)]


# ----------------------------------------------------------------- shapes

def test_detect_returns_legacy_compatible_shapes():
    service = SimilarityService()
    all_results, suspicious, report = service.detect(SUBS)

    assert set(all_results) == set(SUBS)
    assert all(isinstance(r, SimilarityResult)
               for rs in all_results.values() for r in rs)
    # 同一对出现在两个学生的列表里（payload 构建方按 frozenset 去重）
    for a, b in (("S1", "S2"), ("S3", "S4"), ("S1", "S3")):
        assert _pair(all_results, a, b) is not None
        assert _pair(all_results, b, a) is not None
    assert all(r.is_suspicious for r in suspicious)
    assert report["mode"] == "split-engines"
    assert report["pairs_total"] == len(SUBS) * (len(SUBS) - 1) // 2


# ------------------------------------------------------------- modality split

def test_same_report_different_code_flags_text_only():
    all_results, _, _ = SimilarityService().detect(SUBS)
    r = _pair(all_results, "S1", "S2")
    assert r.text_similarity > 70.0          # near-duplicate reports
    # X/Y 共享 main 脚手架，token 重叠实测 ~69：真实但低于代码可疑线(70)
    assert r.code_similarity < 70.0
    assert r.metadata["text_verdict"] is not None
    assert r.metadata["code_verdict"] is None
    assert r.is_suspicious
    assert r.overall_similarity == max(r.text_similarity, r.code_similarity)


def test_different_report_same_code_flags_code_plagiarism():
    all_results, _, _ = SimilarityService().detect(SUBS)
    r = _pair(all_results, "S3", "S4")
    assert r.code_similarity == 100.0        # identical code
    assert r.text_similarity < 40.0          # unrelated reports
    # code band: >= code_similar(85) -> plagiarism
    assert r.metadata["code_verdict"] == "plagiarism"
    assert r.metadata["text_verdict"] is None


def test_unrelated_pair_not_flagged():
    all_results, suspicious, _ = SimilarityService().detect(SUBS)
    r = _pair(all_results, "S1", "S3")
    assert r.overall_similarity < 60.0
    assert not r.is_suspicious
    assert r not in suspicious


def test_shared_template_code_is_not_plagiarism():
    """S3/S4 共享的代码恰为任务书模板时，注入 template_code 后不再命中。"""
    service = SimilarityService(
        engine_options={"code": {"template_code": CODE_Z}})
    all_results, suspicious, _ = service.detect(SUBS)
    r = _pair(all_results, "S3", "S4")
    assert r.code_similarity == 0.0          # template removed on both sides
    assert r.metadata["code_verdict"] is None
    assert not r.is_suspicious
    # 其余不受影响：S1/S2 的文字命中仍在
    assert _pair(all_results, "S1", "S2").is_suspicious


def test_fewer_than_two_submissions_returns_empty():
    all_results, suspicious, report = SimilarityService().detect(
        {"S1": SUBS["S1"]})
    assert all_results == {"S1": []}
    assert suspicious == []
    assert report["pairs_total"] == 0


def test_empty_modality_handled():
    subs = {"S1": {"name": "甲", "text": "", "code": CODE_X},
            "S2": {"name": "乙", "text": "", "code": CODE_X}}
    all_results, _, _ = SimilarityService().detect(subs)
    r = _pair(all_results, "S1", "S2")
    assert r.code_similarity == 100.0
    assert r.text_similarity == 0.0


# ------------------------------------------------------------- GUI wiring

def test_method_map_split_entry():
    from tools.teaching_management_gui.workers.plagiarism_worker import METHOD_MAP
    assert METHOD_MAP["分引擎检测（beta）"] is None   # None 哨兵 -> 服务路径
    assert METHOD_MAP["综合检测（推荐）"].value == "hybrid"
    assert len(METHOD_MAP) == 5


# ------------------------------------------------------------- settings guard

def test_settings_reject_inverted_code_thresholds():
    """code_similar < high_similarity 会让服务的代码阈值带乱序——拒绝。"""
    from pydantic import ValidationError
    from schemas.config import AppSettings
    with pytest.raises(ValidationError, match="code_similar"):
        AppSettings.model_validate({
            "teaching": {"semester": "2026-春季"},
            "plagiarism": {"thresholds": {"code_similar": 50}},
        })
