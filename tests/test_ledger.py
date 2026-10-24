"""Tests for the hash-chained audit ledger (TRD §14, §19 Q3).

Uses temporary SQLite databases so no database server is required.
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime

import pytest
from docverf.config import get_settings
from docverf.ledger.audit_log import ZERO_HASH, AuditLog
from docverf.schemas import AuditEntry
from sqlalchemy import create_engine, text


@pytest.fixture
def tmp_db_url():
    """Provide a temporary SQLite database URL, cleaned up after the test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite:///{path}"
    yield url
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------- empty ledger ----------------


def test_empty_ledger_verify_chain_true(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    assert log.verify_chain() is True
    assert log.get_entries() == []


# ---------------- sequential appends ----------------


def test_append_sequential_seq(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    e1 = log.append("finding_created", {"doc_id": "app001_noc"})
    e2 = log.append("finding_created", {"doc_id": "app001_land_deed"})
    e3 = log.append("decision", {"decision": "approve"})

    assert e1.seq == 0
    assert e2.seq == 1
    assert e3.seq == 2
    assert e1.prev_hash == ZERO_HASH
    assert e2.prev_hash == e1.hash
    assert e3.prev_hash == e2.hash


def test_append_seq_zero_prev_hash_is_zero(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    entry = log.append("check_result", {"check": "pdf_signature"})
    assert entry.seq == 0
    assert entry.prev_hash == ZERO_HASH


# ---------------- exact hash formula ----------------


def test_append_hash_matches_trd_formula(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    payload = {"doc_id": "app001_noc", "check": "qr"}
    event_type = "check_result"
    entry = log.append(event_type, payload)

    # Canonical JSON: sort_keys=True, separators=(",", ":")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected_payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert entry.payload_hash == expected_payload_hash

    # TRD §5.2 formula:
    # sha256(prev_hash + str(seq) + ts.isoformat() + event_type + payload_hash)
    expected_hash = hashlib.sha256(
        (
            entry.prev_hash
            + str(entry.seq)
            + entry.ts.isoformat()
            + event_type
            + entry.payload_hash
        ).encode("utf-8")
    ).hexdigest()
    assert entry.hash == expected_hash


# ---------------- canonical payload hashing ----------------


def test_append_payload_hash_is_deterministic(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    payload_a = {"b": 2, "a": 1}
    payload_b = {"a": 1, "b": 2}
    e1 = log.append("event", payload_a)
    e2 = log.append("event", payload_b)
    assert e1.payload_hash == e2.payload_hash  # key order does not matter


# ---------------- valid chain ----------------


def test_verify_chain_valid_after_multiple_appends(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    for i in range(10):
        log.append("check_result", {"index": i})
    assert log.verify_chain() is True


# ---------------- tampering detection ----------------


def test_verify_chain_detects_payload_tampering(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    log.append("check_result", {"doc_id": "app001_noc"})
    log.append("check_result", {"doc_id": "app001_land_deed"})

    engine = create_engine(log._db_url)
    with engine.connect() as conn:
        # Tamper with the payload_hash of seq 0.
        conn.execute(
            text("UPDATE audit_log SET payload_hash = 'tampered' WHERE seq = 0")
        )
        conn.commit()

    assert log.verify_chain() is False


def test_verify_chain_detects_hash_tampering(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    log.append("check_result", {"doc_id": "app001_noc"})

    engine = create_engine(log._db_url)
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE audit_log SET hash = 'tampered_hash' WHERE seq = 0")
        )
        conn.commit()

    assert log.verify_chain() is False


def test_verify_chain_detects_prev_hash_tampering(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    log.append("check_result", {"doc_id": "app001_noc"})
    log.append("check_result", {"doc_id": "app001_land_deed"})

    engine = create_engine(log._db_url)
    with engine.connect() as conn:
        # Tamper with seq 1's prev_hash so it no longer links to seq 0's hash.
        conn.execute(
            text("UPDATE audit_log SET prev_hash = 'tampered_prev' WHERE seq = 1")
        )
        conn.commit()

    assert log.verify_chain() is False


def test_verify_chain_detects_deleted_entry(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    log.append("check_result", {"doc_id": "a"})
    log.append("check_result", {"doc_id": "b"})
    log.append("check_result", {"doc_id": "c"})

    engine = create_engine(log._db_url)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM audit_log WHERE seq = 1"))
        conn.commit()

    assert log.verify_chain() is False


# ---------------- AuditEntry schema conformance ----------------


def test_append_returns_audit_entry(tmp_db_url):
    log = AuditLog(db_url=tmp_db_url)
    entry = log.append("finding_created", {"doc_id": "app001_noc"})
    assert isinstance(entry, AuditEntry)
    assert isinstance(entry.seq, int)
    assert isinstance(entry.ts, datetime)
    assert isinstance(entry.event_type, str)
    assert isinstance(entry.payload_hash, str)
    assert isinstance(entry.prev_hash, str)
    assert isinstance(entry.hash, str)
    assert len(entry.hash) == 64
    assert len(entry.payload_hash) == 64
    assert len(entry.prev_hash) == 64


# ---------------- module-level wrappers ----------------


def test_module_level_append_and_verify_chain(monkeypatch, tmp_db_url):

    # Point the module-level default log at a temp SQLite DB.
    monkeypatch.setenv("DATABASE_URL", tmp_db_url)
    get_settings.cache_clear()

    from docverf.ledger.audit_log import append as module_append
    from docverf.ledger.audit_log import verify_chain as module_verify_chain

    e = module_append("decision", {"decision": "reject"})
    assert isinstance(e, AuditEntry)
    assert e.seq == 0
    assert module_verify_chain() is True

    get_settings.cache_clear()
