"""SQLite persistence for officer finding actions and application decisions.

Pipeline JSON remains the authoritative source for findings and documents.  This module
stores only the human review trail, keyed by stable `finding_id` / `app_id` values so a
changed JSON file cannot silently attach an action to a different list position.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACTOR = "officer-demo"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _action_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "finding_id": row["finding_id"],
        "app_id": row["app_id"],
        "action": row["action"],
        "reason": row["reason"],
        "actor": row["actor"],
        "created_at": row["created_at"],
    }


def _decision_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        deficiencies = json.loads(row["deficiencies"])
    except json.JSONDecodeError:
        deficiencies = []
    return {
        "app_id": row["app_id"],
        "decision": row["decision"],
        "reason": row["reason"],
        "deficiencies": deficiencies,
        "actor": row["actor"],
        "created_at": row["created_at"],
    }


class OfficerStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout=5000")
            yield connection
        finally:
            connection.close()

    def init_db(self) -> None:
        with self._connect() as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS finding_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    finding_id TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    action TEXT NOT NULL CHECK (action IN ('confirm', 'dismiss')),
                    reason TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_actions_finding ON finding_actions (finding_id, id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_actions_app ON finding_actions (app_id, id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK (
                        decision IN (
                            'approve',
                            'approve_with_deficiencies',
                            'request_rectification',
                            'site_inspection',
                            'reject'
                        )
                    ),
                    reason TEXT NOT NULL,
                    deficiencies TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_decisions_app ON decisions (app_id, id)"
            )

    def record_action(
        self, *, finding_id: str, app_id: str, action: str, reason: str
    ) -> dict[str, Any]:
        created_at = _now()
        with self._connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO finding_actions
                    (finding_id, app_id, action, reason, actor, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (finding_id, app_id, action, reason, ACTOR, created_at),
            )
        return {
            "finding_id": finding_id,
            "app_id": app_id,
            "action": action,
            "reason": reason,
            "actor": ACTOR,
            "created_at": created_at,
        }

    def latest_action_for_finding(self, finding_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM finding_actions WHERE finding_id = ? ORDER BY id DESC LIMIT 1",
                (finding_id,),
            ).fetchone()
        return _action_row(row) if row else None

    def latest_actions_for_app(self, app_id: str) -> dict[str, dict[str, Any]]:
        """Latest action per finding for one application."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT action_rows.*
                FROM finding_actions AS action_rows
                JOIN (
                    SELECT finding_id, MAX(id) AS latest_id
                    FROM finding_actions
                    WHERE app_id = ?
                    GROUP BY finding_id
                ) AS latest ON latest.latest_id = action_rows.id
                """,
                (app_id,),
            ).fetchall()
        return {row["finding_id"]: _action_row(row) for row in rows}

    def record_decision(
        self,
        *,
        app_id: str,
        decision: str,
        reason: str,
        deficiencies: list[str],
    ) -> dict[str, Any]:
        created_at = _now()
        deficiencies_json = json.dumps(deficiencies, ensure_ascii=False)
        with self._connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO decisions
                    (app_id, decision, reason, deficiencies, actor, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (app_id, decision, reason, deficiencies_json, ACTOR, created_at),
            )
        return {
            "app_id": app_id,
            "decision": decision,
            "reason": reason,
            "deficiencies": deficiencies,
            "actor": ACTOR,
            "created_at": created_at,
        }

    def latest_decision(self, app_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM decisions WHERE app_id = ? ORDER BY id DESC LIMIT 1",
                (app_id,),
            ).fetchone()
        return _decision_row(row) if row else None
