#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Engine/session helpers for the teaching-platform database.

Defaults: SQLite at ``<repo>/database/teaching.sqlite`` (already
gitignored via the ``database/*.sqlite`` rule). Override with an explicit
SQLAlchemy URL (PostgreSQL etc.) -- the ORM models are portable.

SQLite quirk handled here: foreign keys are OFF by default; an engine
event turns ``PRAGMA foreign_keys=ON`` on for every new connection, so
referential integrity behaves like a real database.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .orm import Base

# <repo>/database/teaching.sqlite (schemas.config.CONFIG_DIR is <repo>/config)
from schemas.config import CONFIG_DIR

DEFAULT_DATABASE_PATH = CONFIG_DIR.parent / "database" / "teaching.sqlite"
DEFAULT_URL = "sqlite:///" + str(DEFAULT_DATABASE_PATH)


def get_engine(url: Optional[str] = None, *, echo: bool = False) -> Engine:
    """Create an engine; SQLite connections get FK enforcement on.

    File-backed SQLite URLs get their parent directory created -- sqlite
    refuses to open a database file whose directory does not exist (the
    default ``database/`` dir is not in the repo by design).
    """
    engine = create_engine(url or DEFAULT_URL, echo=echo, future=True)
    if engine.url.get_backend_name() == "sqlite":
        if engine.url.database:   # in-memory ('' / None) has no directory
            Path(engine.url.database).parent.mkdir(parents=True,
                                                   exist_ok=True)

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fk(dbapi_connection, _record):  # pragma: no cover
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    """Create all tables (idempotent -- CREATE IF NOT EXISTS semantics)."""
    Base.metadata.create_all(engine)


@contextlib.contextmanager
def get_session(engine: Engine) -> Iterator[Session]:
    """Session context manager: commit on success, rollback on error."""
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
