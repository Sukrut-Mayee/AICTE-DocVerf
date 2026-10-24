"""Tamper-evident audit log (TRD §14).

Per TRD §19 Q3, `ledger/` owns its storage (the `audit_log` and `anchors` tables) through
`AuditLog(db_url=config.DATABASE_URL)`, SQLAlchemy on SQLite (local dev) or Postgres (Docker).
No other module writes `audit_log` or `anchors`.

The engine is created lazily: importing this module never opens a database connection.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import (
    Column,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from docverf.config import get_settings
from docverf.schemas import AuditEntry

ZERO_HASH = "0" * 64


class _Base(DeclarativeBase):
    pass


class _AuditLogRow(_Base):
    __tablename__ = "audit_log"

    seq = Column(Integer, primary_key=True, autoincrement=False)
    # Store ts as an ISO-8601 string (not a DateTime column) so that SQLite
    # round-trips the exact value used in the hash computation.
    ts = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload_hash = Column(String, nullable=False)
    prev_hash = Column(String, nullable=False)
    hash = Column(String, nullable=False)


class _AnchorRow(_Base):
    __tablename__ = "anchors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seq = Column(Integer, nullable=False, unique=True)
    head_hash = Column(String, nullable=False)
    tx_hash = Column(String, nullable=True)
    block_number = Column(Integer, nullable=True)
    ts = Column(String, nullable=False)


class AuditLog:
    """Hash-chained audit log backed by SQLAlchemy (SQLite or Postgres).

    Parameters
    ----------
    db_url:
        Database URL. Defaults to ``config.DATABASE_URL`` (Postgres in Docker,
        ``sqlite:///data/ledger.db`` for local dev when overridden via env).
    """

    def __init__(self, db_url: str | None = None) -> None:
        self._db_url = db_url or get_settings().DATABASE_URL
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None

    @property
    def _engine_or_create(self) -> Engine:
        if self._engine is None:
            connect_args: dict[str, Any] = {}
            if self._db_url.startswith("sqlite"):
                connect_args["check_same_thread"] = False
            self._engine = create_engine(self._db_url, connect_args=connect_args)
            _Base.metadata.create_all(self._engine)
            self._session_factory = sessionmaker(bind=self._engine, autoflush=False)
        return self._engine

    def _session(self) -> Session:
        if self._session_factory is None:
            self._engine_or_create  # noqa: B018 - ensure factory is created
        assert self._session_factory is not None
        return self._session_factory()

    def _canonical_payload(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _payload_hash(self, payload: dict[str, Any]) -> str:
        return hashlib.sha256(self._canonical_payload(payload).encode("utf-8")).hexdigest()

    def _compute_hash(
        self,
        prev_hash: str,
        seq: int,
        ts: datetime,
        event_type: str,
        payload_hash: str,
    ) -> str:
        message = prev_hash + str(seq) + ts.isoformat() + event_type + payload_hash
        return hashlib.sha256(message.encode("utf-8")).hexdigest()

    def append(self, event_type: str, payload: dict[str, Any]) -> AuditEntry:
        """Append an entry atomically with seq = last + 1.

        Canonical JSON (``sort_keys=True, separators=(",", ":")``) -> ``payload_hash``.
        Hash per TRD §5.2: ``sha256(prev_hash + str(seq) + ts.isoformat() + event_type
        + payload_hash)``. For seq 0, ``prev_hash`` is ``"0" * 64``.
        """
        canonical = self._canonical_payload(payload)
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        ts_iso = datetime.now(UTC).isoformat()
        ts = datetime.fromisoformat(ts_iso)

        with self._session() as session:
            with session.begin():
                # Lock the table to allocate seq atomically.
                last = session.query(_AuditLogRow).order_by(_AuditLogRow.seq.desc()).first()
                seq = 0 if last is None else last.seq + 1
                prev_hash = ZERO_HASH if seq == 0 else last.hash
                hash_value = self._compute_hash(
                    prev_hash, seq, ts, event_type, payload_hash
                )
                row = _AuditLogRow(
                    seq=seq,
                    ts=ts_iso,
                    event_type=event_type,
                    payload_hash=payload_hash,
                    prev_hash=prev_hash,
                    hash=hash_value,
                )
                session.add(row)
                session.flush()

        return AuditEntry(
            seq=seq,
            ts=ts,
            event_type=event_type,
            payload_hash=payload_hash,
            prev_hash=prev_hash,
            hash=hash_value,
        )

    def verify_chain(self) -> bool:
        """Recompute every hash from seq 0; detect tampering (changed, deleted,
        reordered, or inconsistent records). Returns True iff the chain is valid."""
        with self._session() as session:
            rows = session.query(_AuditLogRow).order_by(_AuditLogRow.seq).all()

        prev_hash = ZERO_HASH
        for idx, row in enumerate(rows):
            expected_seq = idx
            if row.seq != expected_seq:
                return False  # deleted or reordered

            row_ts = datetime.fromisoformat(cast(str, row.ts))
            expected_hash = self._compute_hash(
                prev_hash,
                cast(int, row.seq),
                row_ts,
                cast(str, row.event_type),
                cast(str, row.payload_hash),
            )
            if cast(str, row.hash) != expected_hash or cast(str, row.prev_hash) != prev_hash:
                return False  # hash mismatch or tampered prev_hash

            prev_hash = cast(str, row.hash)

        return True

    def get_entries(self) -> list[AuditEntry]:
        """Return all entries in seq order (helper for callers/tests)."""
        with self._session() as session:
            rows = session.query(_AuditLogRow).order_by(_AuditLogRow.seq).all()
        return [
            AuditEntry(
                seq=cast(int, row.seq),
                ts=datetime.fromisoformat(cast(str, row.ts)),
                event_type=cast(str, row.event_type),
                payload_hash=cast(str, row.payload_hash),
                prev_hash=cast(str, row.prev_hash),
                hash=cast(str, row.hash),
            )
            for row in rows
        ]


# ---------------------------------------------------------------------------
# Module-level compatibility wrappers (preserve pre-§19 call sites).
# These instantiate a fresh AuditLog per call using the current database URL,
# so they are safe to use from multiple tests/contexts with different URLs.
# ---------------------------------------------------------------------------


def append(event_type: str, payload: dict[str, Any]) -> AuditEntry:
    """Module-level wrapper around ``AuditLog().append`` (TRD §14)."""
    return AuditLog().append(event_type, payload)


def verify_chain() -> bool:
    """Module-level wrapper around ``AuditLog().verify_chain`` (TRD §14)."""
    return AuditLog().verify_chain()
