"""
SQLite-backed evidence adapter.

Intended for the runner's own tests and for small reference deployments.
Production deployments should use the BigQuery adapter or implement
their own against Postgres / Snowflake / etc.

Note on parameter binding: callers pass named parameters as ":name" in
the SQL string and bind via a dict. SQLite supports ":name" natively so
no translation is needed.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .base import EvidenceAdapter


class SqliteAdapter(EvidenceAdapter):
    """
    SQLite adapter. Pass the path to a .db file (or ":memory:") in
    config.evidence_store.path.
    """

    def __init__(self, path: str) -> None:
        # SQLite returns native types for INT/REAL/TEXT; date-time stays as
        # ISO 8601 strings to match the rest of the GATE evidence model.
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row

    @classmethod
    def from_config(cls, evidence_store: dict[str, Any]) -> "SqliteAdapter":
        path = evidence_store.get("path", ":memory:")
        if path != ":memory:":
            # Eagerly fail if the file is missing - clearer error than
            # SQLite's "unable to open database file".
            p = Path(path)
            if not p.exists():
                raise FileNotFoundError(
                    f"SQLite evidence store not found: {p.resolve()}"
                )
        return cls(path)

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        cur = self._conn.execute(sql, params or {})
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def scalar(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        cur = self._conn.execute(sql, params or {})
        row = cur.fetchone()
        if row is None:
            return None
        return row[0]

    def execute_script(self, sql: str) -> None:
        """Load fixture SQL. Used by the runner's own tests, not by checks."""
        self._conn.executescript(sql)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
