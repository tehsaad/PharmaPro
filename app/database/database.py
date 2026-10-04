"""SQLite engine/session management.

All writes go through :meth:`Database.session`, which wraps the work in a single
transaction: either everything commits, or everything is rolled back.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine | None = None
        self._factory: sessionmaker | None = None
        self.connect()

    # ------------------------------------------------------------------ setup
    def connect(self) -> None:
        engine = create_engine(f"sqlite:///{self.path}", future=True)

        @event.listens_for(engine, "connect")
        def _on_connect(dbapi_conn, _record):
            # Let SQLAlchemy control transactions explicitly (pysqlite quirk).
            dbapi_conn.isolation_level = None
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA synchronous=FULL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

        @event.listens_for(engine, "begin")
        def _on_begin(conn):
            # IMMEDIATE takes the write lock up front, so stock checks and the
            # stock deduction that follows them can never interleave.
            conn.exec_driver_sql("BEGIN IMMEDIATE")

        self.engine = engine
        self._factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    def init_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.exec_driver_sql(f"PRAGMA user_version={SCHEMA_VERSION}")
        log.info("Database ready at %s", self.path)

    def dispose(self) -> None:
        if self.engine is not None:
            self.engine.dispose()

    def reconnect(self) -> None:
        self.dispose()
        self.connect()
        self.init_schema()

    def is_valid_schema(self) -> bool:
        names = set(inspect(self.engine).get_table_names())
        return {"medicines", "batches", "sales", "sale_items"}.issubset(names)

    # -------------------------------------------------------------- sessions
    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transactional scope: commit on success, roll back on any error."""
        s = self._factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    @contextmanager
    def read(self) -> Iterator[Session]:
        """Read-only scope (still a transaction, for a consistent snapshot)."""
        s = self._factory()
        try:
            yield s
        finally:
            # Detach first so loaded objects stay usable after the session ends.
            s.expunge_all()
            s.rollback()
            s.close()

    def integrity_ok(self) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(text("PRAGMA integrity_check")).scalar() == "ok"
