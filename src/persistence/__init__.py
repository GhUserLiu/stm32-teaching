# -*- coding: utf-8 -*-
"""Persistence layer (P4b-2): SQLAlchemy ORM + engine/session helpers.

The eight-table ER adopted in the 2026-08 diagnosis (course -> clazz ->
student, teacher -> assignment, versioned submissions, grading with
similarity pairing, evidence log). SQLite by default under
``database/teaching.sqlite`` (gitignored); PostgreSQL-portable by design
(no SQLite-only column types).
"""

from .database import get_engine, get_session, init_db
from .orm import (
    Assignment,
    Base,
    Clazz,
    Course,
    EvidenceLog,
    Grading,
    Student,
    Submission,
    Teacher,
)

__all__ = [
    "Assignment", "Base", "Clazz", "Course", "EvidenceLog", "Grading",
    "Student", "Submission", "Teacher",
    "get_engine", "get_session", "init_db",
]
