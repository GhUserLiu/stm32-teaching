#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Declarative ORM for the teaching platform (SQLAlchemy 2.x style).

ER adopted 2026-08 (diagnosis 第二部分 2.4, user-approved):

    teacher 1──N assignment N──1 course 1──N clazz 1──N student
    student 1──N submission N──1 assignment   (submit_no = version)
    submission 1──1 grading
    submission N──1 submission (self-FK: similarity counterpart)
    student 1──N evidence_log (hex burn / tamper-evidence trail)

Portability: plain INTEGER/TEXT/REAL columns only -- no SQLite-specific
types, so the same models run on PostgreSQL unchanged. Chinese business
terms are kept in column comments (English identifiers, per repo style).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all teaching-platform models."""


class Teacher(Base):
    """教师."""

    __tablename__ = "teacher"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    username: Mapped[Optional[str]] = mapped_column(unique=True)

    assignments: Mapped[List["Assignment"]] = relationship(back_populates="teacher")


class Course(Base):
    """课程（如：单片机原理及应用）."""

    __tablename__ = "course"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[Optional[str]]
    semester: Mapped[str] = mapped_column(nullable=False)  # e.g. 2026-春季

    clazzes: Mapped[List["Clazz"]] = relationship(back_populates="course")
    assignments: Mapped[List["Assignment"]] = relationship(back_populates="course")


class Clazz(Base):
    """班级（class 为 SQL 保留字，沿用 ER 设计中的 clazz）."""

    __tablename__ = "clazz"
    __table_args__ = (UniqueConstraint("course_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)          # e.g. 汽服2301B班
    head_teacher_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teacher.id"))

    course: Mapped["Course"] = relationship(back_populates="clazzes")
    head_teacher: Mapped[Optional["Teacher"]] = relationship(
        foreign_keys=[head_teacher_id])
    students: Mapped[List["Student"]] = relationship(back_populates="clazz")


class Student(Base):
    """学生；同一班级内学号唯一（真实身份的唯一锚点）."""

    __tablename__ = "student"
    __table_args__ = (UniqueConstraint("clazz_id", "student_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    clazz_id: Mapped[int] = mapped_column(ForeignKey("clazz.id"), nullable=False)
    student_no: Mapped[str] = mapped_column(nullable=False)    # 学号
    name: Mapped[str] = mapped_column(nullable=False)

    clazz: Mapped["Clazz"] = relationship(back_populates="students")
    submissions: Mapped[List["Submission"]] = relationship(back_populates="student")
    evidence_logs: Mapped[List["EvidenceLog"]] = relationship(back_populates="student")


class Assignment(Base):
    """实践任务书（deadline/交付物要求/按班级周次生成的参数）."""

    __tablename__ = "assignment"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    teacher_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teacher.id"))
    title: Mapped[str] = mapped_column(nullable=False)
    week_no: Mapped[Optional[int]]                    # 周次 → 模板动态填充参数
    task_doc_path: Mapped[Optional[str]]              # 下发的任务书文档
    deadline: Mapped[Optional[str]]                   # ISO 时间字符串
    hex_required: Mapped[bool] = mapped_column(default=False)
    report_required: Mapped[bool] = mapped_column(default=True)
    params_json: Mapped[Optional[str]]                # 按班级/周次生成的实验参数

    course: Mapped["Course"] = relationship(back_populates="assignments")
    teacher: Mapped[Optional["Teacher"]] = relationship(back_populates="assignments")
    submissions: Mapped[List["Submission"]] = relationship(back_populates="assignment")


class Submission(Base):
    """学生提交（submit_no 承载多次提交的版本语义）."""

    __tablename__ = "submission"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", "submit_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignment.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student.id"), nullable=False)
    submit_no: Mapped[int] = mapped_column(default=1)
    code_snapshot_path: Mapped[Optional[str]]         # 解包源码树
    report_path: Mapped[Optional[str]]                # 报告 docx/pdf
    code_text_snapshot: Mapped[Optional[str]]         # 用户代码文本（查重锚定）
    hex_path: Mapped[Optional[str]]                   # 烧录产物
    hex_md5: Mapped[Optional[str]]                    # 防篡改指纹
    submitted_at: Mapped[Optional[datetime]]
    status: Mapped[Optional[str]]                     # e.g. received/graded

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    student: Mapped["Student"] = relationship(back_populates="submissions")
    grading: Mapped[Optional["Grading"]] = relationship(
        back_populates="submission", uselist=False,
        foreign_keys="Grading.submission_id")
    similar_to_gradings: Mapped[List["Grading"]] = relationship(
        back_populates="similarity_submission",
        foreign_keys="Grading.similarity_submission_id")


class Grading(Base):
    """评分记录（与 submission 一对一；含查重相似度与扣分备注）.

    NOTE（对抗审查记录的语义边界）：删除作为"相似对手"的 submission
    会成功并把 similarity_submission_id 静默置 NULL（无级联删除是有意
    的，但指针断链无信号）——删除操作目前无调用方；未来的 service 层
    若提供删除，须先守卫此指针。
    """

    __tablename__ = "grading"
    __table_args__ = (
        # schema 级 fail-fast（SQLite/PG 均支持）：不得自相似；相似度 0-100
        CheckConstraint(
            "similarity_submission_id IS NULL "
            "OR similarity_submission_id != submission_id",
            name="ck_grading_no_self_similarity"),
        CheckConstraint(
            "similarity_pct IS NULL "
            "OR (similarity_pct >= 0 AND similarity_pct <= 100)",
            name="ck_grading_similarity_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submission.id"), unique=True, nullable=False)
    report_score: Mapped[Optional[float]]
    code_score: Mapped[Optional[float]]
    total_score: Mapped[Optional[float]]
    similarity_pct: Mapped[Optional[float]]           # 查重相似度百分比
    similarity_submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submission.id"))                  # 与哪份提交相似
    deduction_notes: Mapped[Optional[str]]            # 扣分备注
    graded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("teacher.id"))
    graded_at: Mapped[Optional[datetime]]

    submission: Mapped["Submission"] = relationship(
        back_populates="grading", foreign_keys=[submission_id])
    similarity_submission: Mapped[Optional["Submission"]] = relationship(
        back_populates="similar_to_gradings",
        foreign_keys=[similarity_submission_id])


class EvidenceLog(Base):
    """过程性存证：hex 烧录版本/实验箱操作（防篡改指纹链）."""

    __tablename__ = "evidence_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)
    assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("assignment.id"))
    artifact_path: Mapped[Optional[str]]
    artifact_md5: Mapped[Optional[str]]
    artifact_sha256: Mapped[Optional[str]]
    device_sn: Mapped[Optional[str]]                  # 实验箱/烧录器序列号
    operation: Mapped[Optional[str]]                  # e.g. burn/flash/log
    logged_at: Mapped[Optional[datetime]]

    student: Mapped["Student"] = relationship(back_populates="evidence_logs")
    assignment: Mapped[Optional["Assignment"]] = relationship(
        foreign_keys=[assignment_id])
