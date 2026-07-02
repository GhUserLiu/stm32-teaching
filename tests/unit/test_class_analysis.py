# -*- coding: utf-8 -*-
"""
班级分析（共享计算层）单元测试
Class Analysis Unit Tests

守护被"班级报告"对话框与"教师分析报告"共用的 analyze() 计算。
"""

from tools.teaching_management_gui.class_analysis import analyze


def _sample_reports():
    return [
        {"student_id": "001", "name": "甲", "total_score": 90, "max_score": 100, "grade": "A",
         "category_scores": [
             {"category_id": "compilation", "category_name": "编译检查", "max_points": 10, "earned_points": 10},
             {"category_id": "report_quality", "category_name": "报告质量", "max_points": 90, "earned_points": 80},
         ],
         "strengths": ["结构清晰"], "weaknesses": ["缺原理"], "suggestions": ["补原理"]},
        {"student_id": "002", "name": "乙", "total_score": 45, "max_score": 100, "grade": "F",
         "category_scores": [
             {"category_id": "compilation", "category_name": "编译检查", "max_points": 10, "earned_points": 0},
             {"category_id": "report_quality", "category_name": "报告质量", "max_points": 90, "earned_points": 45},
         ],
         "strengths": [], "weaknesses": ["未编译", "缺原理"], "suggestions": []},
    ]


def test_empty():
    a = analyze([])
    assert a.n == 0
    assert a.avg == 0.0


def test_stats():
    a = analyze(_sample_reports(), "X", "07-car-gear")
    assert a.n == 2
    assert a.avg == 67.5  # (90+45)/2
    assert a.max_score == 90 and a.min_score == 45
    assert 0 <= a.median <= 100
    assert a.std > 0
    # 及格率：90% 与 45% → 1 人 >=60% → 50%
    assert abs(a.pass_rate - 50.0) < 1e-9


def test_distributions():
    a = analyze(_sample_reports(), "X", "07")
    assert a.grade_distribution.get("A") == 1
    assert a.grade_distribution.get("F") == 1
    # 分段：90→90-100，45→0-59
    assert a.score_range_distribution["90-100"] == 1
    assert a.score_range_distribution["0-59"] == 1


def test_category_and_ranking():
    a = analyze(_sample_reports(), "X", "07")
    # 编译：平均 (10+0)/2=5 /10 = 50%；薄弱在前
    assert a.category_analysis[0]["id"] == "compilation"
    assert abs(a.category_analysis[0]["rate"] - 0.5) < 1e-9
    # 排名：90 在前
    assert a.ranking[0]["student_id"] == "001"


def test_common_issues():
    a = analyze(_sample_reports(), "X", "07")
    # "缺原理" 出现 2 次，应排在高频薄弱点最前
    assert a.common_weaknesses
    assert a.common_weaknesses[0].startswith("缺原理")
