"""Hash-chained audit log and blockchain anchoring (TRD §14). May make network calls.

Per TRD §19 Q3, `ledger/` owns its storage (the `audit_log` and `anchors` tables) through
`AuditLog(db_url=config.DATABASE_URL)`, SQLAlchemy on SQLite (local) or Postgres (Docker).
The `AuditLog` class is not scaffolded yet; the module-level stubs in `audit_log.py` predate §19.
"""
