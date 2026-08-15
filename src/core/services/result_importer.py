#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill existing JSON grading/plagiarism artifacts into the database.

P4b-3: the persistence layer exists but has no live data yet -- this importer
is the wiring step. It reads ONLY the artifacts the current pipeline already
produces (no behavior change anywhere upstream):

  data/teaching/<semester>/<class>/<experiment>/results/grading/个人报告/
      <student_no>-<name>-评分.json      (per-student grading; fields as
                                          written by facade._save_reports)
  data/teaching/<semester>/<class>/<experiment>/results/plagiarism/
      plagiarism_results.json            (payload from plagiarism_worker)
  data/teaching/<semester>/_跨班级比对/plagiarism/
      plagiarism_results.json            (cross-class pairs, applied LAST
                                          so students from both classes exist)

Mapping (deliberately conservative):
  course    <- (course_code, semester); clazz <- directory name;
  student   <- <student_no> + <name> from the filename/JSON;
  assignment<- experiment directory name (title); submissions are version-1
  anchors (file paths unknown from these artifacts -> left NULL);
  grading   <- upsert total_score/grade/deduction_notes/graded_at;
  similarity<- suspicious pairs only: similarity_pct = pair overall,
              similarity_submission_id = counterpart's submission.

Idempotent: every entity is get-or-create by natural key; re-running updates
scores (latest wins) and never duplicates rows. Unknown/malformed files are
skipped and counted, never fatal.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from persistence import (
    Assignment,
    Clazz,
    Course,
    Grading,
    Student,
    Submission,
    get_engine,
    init_db,
)

_FILENAME_RE = re.compile(r"^(?P<sid>\d+)-(?P<name>.+)-评分\.json$")


@dataclass
class ImportStats:
    """Counters for one import run (created counts; updates counted too)."""

    clazzes: int = 0
    students: int = 0
    assignments: int = 0
    submissions: int = 0
    gradings_created: int = 0
    gradings_updated: int = 0
    similarity_links: int = 0
    skipped_files: int = 0
    skipped_pairs: int = 0
    notes: List[str] = field(default_factory=list)

    def summary_line(self) -> str:
        return (
            "backfill: 班级+%d 学生+%d 任务+%d 提交+%d 评分(新建%d/更新%d) "
            "相似链接%d 跳过(文件%d/配对%d)" % (
                self.clazzes, self.students, self.assignments,
                self.submissions, self.gradings_created, self.gradings_updated,
                self.similarity_links, self.skipped_files, self.skipped_pairs))


class ResultImporter:
    """Idempotent importer of existing result JSONs into the database."""

    def __init__(
        self,
        engine=None,
        teaching_dir: Optional[Path] = None,
        semester: Optional[str] = None,
        course_code: str = "STM32F407",
        course_name: str = "单片机原理及应用",
        log: Optional[Callable[[str], None]] = None,
        dry_run: bool = False,
    ):
        from schemas import get_settings
        from schemas.config import CONFIG_DIR

        settings = get_settings()
        self.engine = engine or get_engine()
        self.teaching_dir = Path(teaching_dir or (
            CONFIG_DIR.parent / "data" / "teaching"))
        self.semester = semester or settings.teaching.semester
        self.course_code = course_code
        self.course_name = course_name
        self.dry_run = dry_run
        self.last_stats: Optional[ImportStats] = None   # 失败后仍可读
        self._log = log or (lambda _msg: None)

    # ------------------------------------------------------------------ run

    def import_all(self) -> ImportStats:
        init_db(self.engine)
        stats = ImportStats()
        semester_dir = self.teaching_dir / self.semester
        if not semester_dir.is_dir():
            stats.notes.append(f"学期目录不存在: {semester_dir}")
            return stats

        # 单事务全程；dry_run 时回滚（真实"只看不写"）
        factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        session = factory()
        try:
            course = self._get_or_create_course(session)
            for class_dir in sorted(semester_dir.iterdir()):
                if not class_dir.is_dir() or class_dir.name.startswith("_"):
                    continue
                # 先探测有无评分产物：Downloads/课程档案 等非班级目录
                # 不产生空 clazz 行（对抗审查 nit）
                experiment_dirs = [
                    d for d in sorted(class_dir.iterdir())
                    if d.is_dir()
                    and (d / "results" / "grading" / "个人报告").is_dir()
                ]
                if not experiment_dirs:
                    continue
                clazz = self._get_or_create_clazz(session, course,
                                                  class_dir.name, stats)
                for experiment_dir in experiment_dirs:
                    assignment = self._get_or_create_assignment(
                        session, course, experiment_dir.name, stats)
                    self._import_grading_dir(
                        session, clazz, assignment,
                        experiment_dir / "results" / "grading" / "个人报告",
                        stats)
            # 跨班级配对最后处理（两班学生此时均已入库）；跨班产物不带
            # 实验元数据 → 按配对自带 class_a/class_b 定位学生
            cross = (semester_dir / "_跨班级比对" / "plagiarism"
                     / "plagiarism_results.json")
            if cross.is_file():
                self._import_plagiarism_file(session, cross, stats)
            # 单班级查重：配对归属本班 + 本实验（多实验时防止错挂）
            for class_dir in sorted(semester_dir.iterdir()):
                if not class_dir.is_dir() or class_dir.name.startswith("_"):
                    continue
                for experiment_dir in sorted(class_dir.iterdir()):
                    p = (experiment_dir / "results" / "plagiarism"
                         / "plagiarism_results.json")
                    if not p.is_file():
                        continue
                    assignment = session.execute(
                        select(Assignment).where(
                            Assignment.course_id == course.id,
                            Assignment.title == experiment_dir.name)
                    ).scalar_one_or_none()
                    self._import_plagiarism_file(
                        session, p, stats,
                        class_name=class_dir.name,
                        assignment_id=assignment.id if assignment else None)

            if self.dry_run:
                session.rollback()
                stats.notes.append("dry-run：已回滚全部写入")
            else:
                session.commit()
        except Exception:
            session.rollback()
            self.last_stats = stats   # CLI 可在失败后仍打印已累计统计
            raise
        finally:
            session.close()
        return stats

    # ------------------------------------------------------------ entities

    def _get_or_create_course(self, session: Session) -> Course:
        course = session.execute(
            select(Course).where(Course.code == self.course_code,
                                 Course.semester == self.semester)
        ).scalar_one_or_none()
        if course is None:
            course = Course(code=self.course_code, name=self.course_name,
                            semester=self.semester)
            session.add(course)
            session.flush()
        return course

    def _get_or_create_clazz(self, session, course, class_name,
                             stats) -> Clazz:
        clazz = session.execute(
            select(Clazz).where(Clazz.course_id == course.id,
                                Clazz.name == class_name)
        ).scalar_one_or_none()
        if clazz is None:
            clazz = Clazz(course=course, name=class_name)
            session.add(clazz)
            session.flush()
            stats.clazzes += 1
            self._log(f"班级 +{class_name}")
        return clazz

    def _get_or_create_assignment(self, session, course, experiment_id,
                                  stats) -> Assignment:
        assignment = session.execute(
            select(Assignment).where(Assignment.course_id == course.id,
                                     Assignment.title == experiment_id)
        ).scalar_one_or_none()
        if assignment is None:
            assignment = Assignment(course=course, title=experiment_id)
            session.add(assignment)
            session.flush()
            stats.assignments += 1
            self._log(f"任务 +{experiment_id}")
        return assignment

    def _get_or_create_student(self, session, clazz, student_no, name,
                               stats) -> Student:
        student = session.execute(
            select(Student).where(Student.clazz_id == clazz.id,
                                  Student.student_no == student_no)
        ).scalar_one_or_none()
        if student is None:
            student = Student(clazz=clazz, student_no=student_no, name=name)
            session.add(student)
            session.flush()
            stats.students += 1
        return student

    def _get_or_create_submission(self, session, assignment, student,
                                  stats) -> Tuple[Submission, bool]:
        submission = session.execute(
            select(Submission).where(
                Submission.assignment_id == assignment.id,
                Submission.student_id == student.id,
                Submission.submit_no == 1)
        ).scalar_one_or_none()
        created = False
        if submission is None:
            submission = Submission(assignment=assignment, student=student,
                                    submit_no=1, status="graded")
            session.add(submission)
            session.flush()
            stats.submissions += 1
            created = True
        return submission, created

    # ------------------------------------------------------------ grading

    def _import_grading_dir(self, session, clazz, assignment, grading_dir,
                            stats) -> None:
        for path in sorted(grading_dir.glob("*.json")):
            match = _FILENAME_RE.match(path.name)
            if not match:
                stats.skipped_files += 1
                stats.notes.append(f"文件名不识别: {path.name}")
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                stats.skipped_files += 1
                stats.notes.append(f"JSON 解析失败 {path.name}: {exc}")
                continue

            student = self._get_or_create_student(
                session, clazz, data.get("student_id") or match.group("sid"),
                data.get("name") or match.group("name"), stats)
            submission, _ = self._get_or_create_submission(
                session, assignment, student, stats)

            graded_at = _parse_dt(data.get("graded_at"))
            existing = submission.grading
            if existing is None:
                session.add(Grading(
                    submission=submission,
                    total_score=data.get("total_score"),
                    deduction_notes=f"等级 {data.get('grade', '?')}",
                    graded_at=graded_at))
                session.flush()
                stats.gradings_created += 1
            else:
                existing.total_score = data.get("total_score")
                existing.deduction_notes = f"等级 {data.get('grade', '?')}"
                existing.graded_at = graded_at
                stats.gradings_updated += 1

    # ------------------------------------------------------------ similarity

    def _import_plagiarism_file(self, session, path: Path, stats,
                                class_name: Optional[str] = None,
                                assignment_id: Optional[int] = None) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            stats.skipped_files += 1
            stats.notes.append(f"查重 JSON 解析失败 {path}: {exc}")
            return
        pairs = payload.get("pairs") or []
        suspicious = [p for p in pairs if p.get("suspicious")]
        self._log(f"查重 {path.parent.name}: {len(suspicious)} 可疑对 "
                  f"(共 {len(pairs)})")
        for pair in suspicious:
            # 预校验 overall：坏值跳过并计数（兑现"永不致命"承诺，
            # 不依赖 DB CHECK 在 commit 时才炸）
            try:
                overall = float(pair.get("overall") or 0.0)
            except (TypeError, ValueError):
                overall = None
            if overall is None or not 0.0 <= overall <= 100.0:
                stats.skipped_pairs += 1
                stats.notes.append(
                    f"配对 overall 非法({pair.get('overall')!r})，跳过")
                continue
            linked = self._link_similarity(
                session, pair, overall, stats,
                class_name=class_name, assignment_id=assignment_id)
            if linked:
                stats.similarity_links += 1
            else:
                stats.skipped_pairs += 1

    def _link_similarity(self, session, pair, new_pct: float, stats,
                         class_name: Optional[str] = None,
                         assignment_id: Optional[int] = None) -> bool:
        """双向设置相似度指针；多对竞争时强对胜出（不是后写者胜）。

        学生定位（对抗审查两处修复）：优先用配对自带的 class_a/class_b
        （真实数据存在两班同号不同人），回落到调用方上下文 class_name；
        单班级文件同时按 assignment_id 过滤（多实验时防止配对错挂到
        字母序第一的实验）。
        """
        sub_a = self._find_submission(
            session, pair.get("student_a"),
            class_name=pair.get("class_a") or class_name,
            assignment_id=assignment_id)
        sub_b = self._find_submission(
            session, pair.get("student_b"),
            class_name=pair.get("class_b") or class_name,
            assignment_id=assignment_id)
        if sub_a is None or sub_b is None or sub_a is sub_b:
            return False
        for mine, other in ((sub_a, sub_b), (sub_b, sub_a)):
            grading = mine.grading
            if grading is None:
                grading = Grading(submission=mine, similarity_pct=new_pct)
                session.add(grading)
                grading.similarity_submission_id = other.id
            else:
                old_pct = grading.similarity_pct or 0.0
                if new_pct >= old_pct:
                    grading.similarity_submission_id = other.id
                grading.similarity_pct = max(old_pct, new_pct)
        session.flush()
        return True

    def _find_submission(self, session, student_no,
                         class_name: Optional[str] = None,
                         assignment_id: Optional[int] = None
                         ) -> Optional[Submission]:
        if not student_no:
            return None
        stmt = (select(Submission).join(Student).join(Clazz)
                .where(Student.student_no == str(student_no),
                       Submission.submit_no == 1))
        if class_name:
            stmt = stmt.where(Clazz.name == class_name)
        if assignment_id is not None:
            stmt = stmt.where(Submission.assignment_id == assignment_id)
        return session.execute(stmt).scalars().first()


def _parse_dt(value) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
