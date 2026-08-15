#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""persistence 层单测（P4b-2：SQLAlchemy ER 落地）。

内存 SQLite 全链路建摸/写入/查询：课程→班级→学生、教师→任务书、
版本化提交、一对一评分、相似度自引用、存证日志；唯一约束与外键
（PRAGMA foreign_keys=ON）实测生效；默认库路径指向 database/ 且不落盘。
"""

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from persistence import (
    Assignment,
    Clazz,
    Course,
    EvidenceLog,
    Grading,
    Student,
    Submission,
    Teacher,
    get_engine,
    get_session,
    init_db,
)


@pytest.fixture()
def engine():
    eng = get_engine("sqlite://")      # in-memory
    init_db(eng)
    return eng


def _seed_full_chain(engine):
    """course→clazz→student + teacher→assignment + submission/grading/evidence."""
    with get_session(engine) as s:
        teacher = Teacher(name="王老师", username="wang")
        course = Course(code="MCU407", name="单片机原理及应用",
                        semester="2026-春季")
        clazz = Clazz(course=course, name="汽服2301B班", head_teacher=teacher)
        student = Student(clazz=clazz, student_no="23071140102", name="杨凯辉")
        assignment = Assignment(
            course=course, teacher=teacher, title="汽车档位模拟器",
            week_no=8, deadline="2026-05-08T23:59:59",
            hex_required=True, params_json='{"freq_hz": 1000}')
        submission = Submission(
            assignment=assignment, student=student, submit_no=1,
            code_snapshot_path="data/teaching/.../source/",
            report_path="data/teaching/.../reports/x.docx",
            code_text_snapshot="int main(void){}",
            hex_path="out.hex", hex_md5="d41d8cd98f00b204e980",
            submitted_at=datetime(2026, 5, 7, 20, 0, 0), status="received")
        grading = Grading(
            submission=submission, report_score=25.0, code_score=60.0,
            total_score=85.0, similarity_pct=12.5,
            deduction_notes="报告缺调试章节",
            graded_by=teacher.id if teacher.id else None,
            graded_at=datetime(2026, 5, 8, 10, 0, 0))
        s.add_all([teacher, course, clazz, student, assignment,
                   submission, grading])
        s.flush()
        # 相似对手（另一学生 + 提交），评分自引用
        other = Student(clazz=clazz, student_no="23071140103", name="刘同学")
        other_sub = Submission(assignment=assignment, student=other,
                               submit_no=1)
        grading.similarity_submission = other_sub
        evidence = EvidenceLog(
            student=student, assignment=assignment,
            artifact_path="out.hex", artifact_md5="d41d8cd98f00b204e980",
            artifact_sha256="e3b0c44298fc1c149afbf4c8996fb924",
            device_sn="ATK-XISP-001", operation="burn",
            logged_at=datetime(2026, 5, 7, 21, 0, 0))
        s.add_all([other, other_sub, evidence])
    return student.id, submission.id, other_sub.id


# ------------------------------------------------------------------- chain

def test_full_chain_roundtrip(engine):
    student_id, submission_id, other_sub_id = _seed_full_chain(engine)
    with get_session(engine) as s:
        student = s.get(Student, student_id)
        assert student.name == "杨凯辉"
        assert student.clazz.name == "汽服2301B班"
        assert student.clazz.course.code == "MCU407"

        sub = s.get(Submission, submission_id)
        assert sub.submit_no == 1 and sub.hex_md5
        assert sub.assignment.title == "汽车档位模拟器"
        # 一对一评分
        assert sub.grading.total_score == 85.0
        # 相似度自引用
        assert sub.grading.similarity_submission_id == other_sub_id
        # 存证链
        assert [e.operation for e in student.evidence_logs] == ["burn"]


def test_versioned_resubmission(engine):
    student_id, _, _ = _seed_full_chain(engine)
    with get_session(engine) as s:
        student = s.get(Student, student_id)
        s.add(Submission(assignment=student.submissions[0].assignment,
                         student=student, submit_no=2, status="received"))
    with get_session(engine) as s:
        assert s.query(Submission).count() == 3   # 2 (seed) + 1 resubmit


# ------------------------------------------------------------- constraints

def test_student_no_unique_within_clazz(engine):
    with get_session(engine) as s:
        course = Course(code="C1", semester="2026-春季")
        clazz = Clazz(course=course, name="汽服2301B班")
        s.add(Student(clazz=clazz, student_no="001", name="甲"))
    with pytest.raises(IntegrityError), get_session(engine) as s:
        s.add(Student(clazz_id=1, student_no="001", name="乙"))


def test_same_student_no_different_clazz_allowed(engine):
    with get_session(engine) as s:
        course = Course(code="C1", semester="2026-春季")
        c1 = Clazz(course=course, name="汽服2301B班")
        c2 = Clazz(course=course, name="汽服2302B班")
        s.add(Student(clazz=c1, student_no="001", name="甲"))
        s.add(Student(clazz=c2, student_no="001", name="乙"))
    with get_session(engine) as s:
        assert s.query(Student).count() == 2


def test_submission_unique_per_version(engine):
    student_id, submission_id, _ = _seed_full_chain(engine)
    with get_session(engine) as s:
        sub = s.get(Submission, submission_id)
        assignment_id, student_id = sub.assignment_id, sub.student_id
    with pytest.raises(IntegrityError), get_session(engine) as s:
        s.add(Submission(assignment_id=assignment_id,
                         student_id=student_id, submit_no=1))


def test_grading_one_to_one(engine):
    _, submission_id, _ = _seed_full_chain(engine)
    with pytest.raises(IntegrityError), get_session(engine) as s:
        s.add(Grading(submission_id=submission_id, total_score=50.0))


def test_foreign_keys_enforced_on_sqlite(engine):
    """PRAGMA foreign_keys=ON：伪造外键直接拒绝。"""
    with pytest.raises(IntegrityError), get_session(engine) as s:
        s.add(Submission(assignment_id=9999, student_id=9999))


def test_self_similarity_rejected(engine):
    _, submission_id, _ = _seed_full_chain(engine)
    with get_session(engine) as s:
        s.query(Grading).filter(
            Grading.submission_id == submission_id).delete()
    with pytest.raises(IntegrityError), get_session(engine) as s:
        s.add(Grading(submission_id=submission_id,
                      similarity_submission_id=submission_id))


def test_similarity_pct_range_checked(engine):
    _, submission_id, _ = _seed_full_chain(engine)
    with get_session(engine) as s:
        s.query(Grading).filter(
            Grading.submission_id == submission_id).delete()
    with pytest.raises(IntegrityError), get_session(engine) as s:
        s.add(Grading(submission_id=submission_id, similarity_pct=120.0))
    # 合法区间可写入
    with get_session(engine) as s:
        s.add(Grading(submission_id=submission_id, similarity_pct=99.5))


# ------------------------------------------------------------- engine wiring

def test_default_url_points_into_database_dir():
    from persistence.database import DEFAULT_DATABASE_PATH, DEFAULT_URL
    assert DEFAULT_DATABASE_PATH == Path(
        DEFAULT_URL.replace("sqlite:///", "", 1))
    assert DEFAULT_DATABASE_PATH.parent.name == "database"
    assert DEFAULT_DATABASE_PATH.name == "teaching.sqlite"


def test_init_db_idempotent(engine):
    init_db(engine)          # second call must not raise
    with get_session(engine) as s:
        assert s.query(Course).count() == 0


def test_file_sqlite_engine_creates_parent_dir(tmp_path):
    """sqlite 拒开无父目录的库文件——get_engine 负责建目录（真实 dry-run
    踩到的 OperationalError 回归）。"""
    db_file = tmp_path / "deep" / "nested" / "x.sqlite"
    eng = get_engine("sqlite:///" + str(db_file))
    init_db(eng)             # connects -> must not raise
    assert db_file.is_file()
