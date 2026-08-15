#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ResultImporter 单测（P4b-3：JSON 产物回填数据库）。

对抗审查修复的回归重点：
- 多实验配对归属（08-led 的对必须落在 08-led 的提交，不得错挂 07-car-gear）；
- 跨班同号学生按 class_a/class_b 定位（真实数据存在两班同号不同人）；
- 坏 overall 值跳过不致命（兑现"永不致命"承诺）；
- 非班级目录（Downloads/）不产生空 clazz 行。
其余：全链路落库、强对胜出指针、幂等重跑、dry-run 真回滚、坏 JSON 跳过。
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from core.services.result_importer import ResultImporter
from persistence import (
    Assignment,
    Clazz,
    Course,
    Grading,
    Student,
    Submission,
    get_engine,
    get_session,
    init_db,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _grading_json(student_no: str, name: str, total: float,
                  grade: str = "A") -> str:
    return json.dumps({
        "student_id": student_no, "name": name, "class_name": "汽服2301B班",
        "total_score": total, "max_score": 100.0, "grade": grade,
        "graded_at": "2026-05-08T10:00:00",
    }, ensure_ascii=False)


@pytest.fixture()
def teaching_tree(tmp_path: Path) -> Path:
    base = tmp_path / "teaching" / "2026-春季"

    # 2301B：两个实验（001/002 各有两次提交——多实验错挂场景的土壤）
    for exp, scores in (("07-car-gear", (("001", "甲", 85.0),
                                         ("002", "乙", 72.0))),
                        ("08-led", (("001", "甲", 80.0),
                                    ("002", "乙", 70.0)))):
        reports = base / "汽服2301B班" / exp / "results" / "grading" / "个人报告"
        for sid, name, total in scores:
            _write(reports / f"{sid}-{name}-评分.json",
                   _grading_json(sid, name, total))

    # 2302B：一个实验 + 与 2301B 同号(555)的不同学生
    reports = base / "汽服2302B班" / "07-car-gear" / "results" / "grading" / "个人报告"
    for sid, name, total in (("101", "丙", 90.0), ("102", "丁", 66.0),
                             ("555", "李四", 60.0)):
        _write(reports / f"{sid}-{name}-评分.json",
               _grading_json(sid, name, total))
    _write(base / "汽服2301B班" / "07-car-gear" / "results" / "grading"
           / "个人报告" / "555-张三-评分.json",
           _grading_json("555", "张三", 75.0))

    # 单班级查重（07-car-gear / 2301B）：班内可疑对 001-002 88.5
    _write(base / "汽服2301B班" / "07-car-gear" / "results" / "plagiarism"
           / "plagiarism_results.json", json.dumps({
               "method": "hybrid", "threshold": 60,
               "pairs": [
                   {"student_a": "001", "student_b": "002",
                    "class_a": "汽服2301B班", "class_b": "汽服2301B班",
                    "overall": 88.5, "suspicious": True},
                   {"student_a": "001", "student_b": "102",
                    "overall": 30.0, "suspicious": False},
               ]}, ensure_ascii=False))
    # 单班级查重（08-led / 2301B）：含一条坏 overall（120.0）——跳过不致命
    _write(base / "汽服2301B班" / "08-led" / "results" / "plagiarism"
           / "plagiarism_results.json", json.dumps({
               "pairs": [
                   {"student_a": "001", "student_b": "002",
                    "class_a": "汽服2301B班", "class_b": "汽服2301B班",
                    "overall": 77.0, "suspicious": True},
                   {"student_a": "001", "student_b": "002",
                    "class_a": "汽服2301B班", "class_b": "汽服2301B班",
                    "overall": 120.0, "suspicious": True},
               ]}, ensure_ascii=False))
    # 跨班级：强对 002-101（93.2）+ 同号 555 跨班对（80.0，class 指明归属）
    _write(base / "_跨班级比对" / "plagiarism" / "plagiarism_results.json",
           json.dumps({
               "pairs": [
                   {"student_a": "002", "student_b": "101",
                    "class_a": "汽服2301B班", "class_b": "汽服2302B班",
                    "overall": 93.2, "suspicious": True},
                   {"student_a": "555", "student_b": "102",
                    "class_a": "汽服2301B班", "class_b": "汽服2302B班",
                    "overall": 80.0, "suspicious": True},
               ]}, ensure_ascii=False))
    # 非班级目录：不产生空 clazz 行
    _write(base / "Downloads" / "readme.txt", "junk")
    # 一份坏评分文件：跳过不致命
    _write(base / "汽服2301B班" / "07-car-gear" / "results" / "grading"
           / "个人报告" / "not-a-grade.txt", "junk")
    return tmp_path / "teaching"


@pytest.fixture()
def engine():
    eng = get_engine("sqlite://")
    init_db(eng)
    return eng


def _importer(engine, teaching_tree, **kwargs) -> ResultImporter:
    return ResultImporter(engine=engine, teaching_dir=teaching_tree,
                          semester="2026-春季", **kwargs)


def _sub(engine, student_no, exp, clazz):
    with get_session(engine) as s:
        # joinedload: 会话关闭后测试仍可访问 .grading（无懒加载）
        return s.execute(
            select(Submission)
            .options(joinedload(Submission.grading))
            .join(Student).join(Clazz).join(Assignment)
            .where(Student.student_no == student_no,
                   Clazz.name == clazz,
                   Assignment.title == exp,
                   Submission.submit_no == 1)
        ).scalar_one()


# ------------------------------------------------------------------ import

def test_import_full_chain(engine, teaching_tree):
    stats = _importer(engine, teaching_tree).import_all()

    assert stats.clazzes == 2 and stats.students == 6
    assert stats.assignments == 2 and stats.submissions == 8
    assert stats.gradings_created == 8
    with get_session(engine) as s:
        course = s.query(Course).one()
        assert course.code == "STM32F407" and course.semester == "2026-春季"
        # 非班级目录不产生空 clazz 行（Downloads 缺席）
        assert {c.name for c in course.clazzes} == {"汽服2301B班",
                                                    "汽服2302B班"}
        student = (s.query(Student)
                   .filter(Student.student_no == "001").one())
        assert student.name == "甲"
        grading = student.submissions[0].grading
        assert grading.total_score in (85.0, 80.0)
        assert "A" in grading.deduction_notes
        assert grading.graded_at is not None


def test_multi_experiment_pairs_attributed_correctly(engine, teaching_tree):
    """D1 回归：08-led 的配对必须落在 08-led 的提交上。"""
    _importer(engine, teaching_tree).import_all()
    sub07 = _sub(engine, "001", "07-car-gear", "汽服2301B班")
    sub08 = _sub(engine, "001", "08-led", "汽服2301B班")
    other07 = _sub(engine, "002", "07-car-gear", "汽服2301B班")
    other08 = _sub(engine, "002", "08-led", "汽服2301B班")

    assert sub07.grading.similarity_pct == 88.5
    assert sub07.grading.similarity_submission_id == other07.id
    assert sub08.grading.similarity_pct == 77.0
    assert sub08.grading.similarity_submission_id == other08.id
    # 坏 overall(120) 被跳过，未污染任何分数
    assert sub08.grading.similarity_pct == 77.0


def test_cross_class_same_student_no_resolved_by_class(engine, teaching_tree):
    """R2 回归：两班同号(555)不同人，按 class_a/class_b 各归其主。"""
    _importer(engine, teaching_tree).import_all()
    zhang = _sub(engine, "555", "07-car-gear", "汽服2301B班")   # 张三
    li = _sub(engine, "555", "07-car-gear", "汽服2302B班")      # 李四

    assert zhang.grading.similarity_pct == 80.0                  # 与 102 成对
    assert zhang.grading.similarity_submission_id == _sub(
        engine, "102", "07-car-gear", "汽服2302B班").id
    assert li.grading.similarity_pct is None                     # 不受牵连


def test_strongest_pair_wins_for_pointer(engine, teaching_tree):
    _importer(engine, teaching_tree).import_all()
    sub002 = _sub(engine, "002", "07-car-gear", "汽服2301B班")
    sub101 = _sub(engine, "101", "07-car-gear", "汽服2302B班")
    # 跨班强对 93.2 胜过班内 88.5：002 的指针指向 101
    assert sub002.grading.similarity_submission_id == sub101.id
    assert sub002.grading.similarity_pct == 93.2
    assert sub101.grading.similarity_pct == 93.2


def test_bad_overall_skipped_not_fatal(engine, teaching_tree):
    stats = _importer(engine, teaching_tree).import_all()
    assert stats.skipped_pairs >= 1
    assert any("overall" in n for n in stats.notes)
    # 整体导入仍然成功（库有数据）
    with get_session(engine) as s:
        assert s.query(Submission).count() == 8


def test_idempotent_rerun(engine, teaching_tree):
    first = _importer(engine, teaching_tree).import_all()

    reports = (teaching_tree / "2026-春季" / "汽服2301B班" / "07-car-gear"
               / "results" / "grading" / "个人报告")
    _write(reports / "001-甲-评分.json", _grading_json("001", "甲", 88.0, "A"))

    second = _importer(engine, teaching_tree).import_all()
    assert second.clazzes == 0 and second.students == 0
    assert second.submissions == 0 and second.gradings_created == 0
    assert second.gradings_updated == 8
    with get_session(engine) as s:
        assert s.query(Submission).count() == first.submissions
        # 相似度字段不被评分重跑清掉
        sub002 = _sub(engine, "002", "07-car-gear", "汽服2301B班")
        assert sub002.grading.similarity_pct == 93.2


def test_dry_run_rolls_back_everything(engine, teaching_tree):
    stats = _importer(engine, teaching_tree, dry_run=True).import_all()
    assert stats.submissions == 8
    assert any("回滚" in n for n in stats.notes)
    with get_session(engine) as s:
        assert s.query(Student).count() == 0
        assert s.query(Submission).count() == 0


def test_missing_semester_dir_is_note_not_error(engine, tmp_path):
    stats = _importer(engine, tmp_path).import_all()
    assert stats.submissions == 0
    assert any("学期目录不存在" in n for n in stats.notes)


def test_malformed_json_skipped_not_fatal(engine, teaching_tree):
    bad = (teaching_tree / "2026-春季" / "汽服2301B班" / "07-car-gear"
           / "results" / "grading" / "个人报告" / "003-戊-评分.json")
    _write(bad, "{not json")
    stats = _importer(engine, teaching_tree).import_all()
    assert stats.skipped_files >= 1
    assert any("003" in n for n in stats.notes)
    with get_session(engine) as s:
        assert s.query(Student).filter(
            Student.student_no == "003").count() == 0
