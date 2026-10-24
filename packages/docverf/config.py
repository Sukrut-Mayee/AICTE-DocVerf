"""Configuration from environment variables (TRD §15).

Attribute names equal the env var names, so a rule's `{config: ACADEMIC_YEAR_END}` is
`getattr(get_settings(), "ACADEMIC_YEAR_END")`. Real environment variables win over `.env`.
"""

import os
from dataclasses import dataclass, fields
from datetime import date
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str = "postgresql+psycopg://docverf:docverf@localhost:5432/docverf"
    REDIS_URL: str = "redis://localhost:6379/0"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "docverf"
    MINIO_SECRET_KEY: str = "docverf-secret"
    MINIO_BUCKET: str = "documents"
    BESU_RPC_URL: str = "http://localhost:8545"
    ANCHOR_CONTRACT_ADDRESS: str = ""
    ANCHOR_PRIVATE_KEY: str = ""  # dev key only
    OLLAMA_URL: str = "http://localhost:11434"
    VLM_MODEL: str = ""
    OCR_ENGINE: str = "paddleocr"  # paddleocr | surya
    ALLOW_CLOUD_AI: bool = False
    CONFIDENCE_THRESHOLD: float = 0.75
    NAME_MATCH_THRESHOLD: int = 90
    PHASH_MAX_DIST: int = 6
    ELA_RATIO_THRESHOLD: float = 2.0
    BLUR_THRESHOLD: float = 100
    SOURCE_TIMEOUT_S: float = 5
    MOCK_ISSUER_URL: str = "http://localhost:8100"
    PORTAL_CALLBACK_URL: str = "http://localhost:3000/api/callbacks"
    TRUST_ROOTS_DIR: Path = Path("infra/pki/trust_roots")
    ACADEMIC_YEAR_START: date = date(2027, 7, 1)  # illustrative
    ACADEMIC_YEAR_END: date = date(2028, 6, 30)  # illustrative
    APPLICATION_WINDOW_START: date = date(2026, 12, 1)  # illustrative
    APPLICATION_WINDOW_END: date = date(2027, 3, 31)  # illustrative
    RETENTION_DAYS: int = 365
    JWT_SECRET: str = "dev-secret"


def _cast(default: object, raw: str) -> object:
    raw = raw.strip()
    if isinstance(default, bool):  # before int: bool is an int subclass
        return raw.lower() in {"1", "true", "yes", "on"}
    if isinstance(default, date):
        return date.fromisoformat(raw)
    if isinstance(default, Path):
        return Path(raw)
    return type(default)(raw)


@lru_cache
def get_settings() -> Settings:
    """Load settings once. Tests can call `get_settings.cache_clear()` after patching env."""
    load_dotenv()
    defaults = Settings()
    values = {}
    for f in fields(Settings):
        raw = os.environ.get(f.name)
        if raw is not None and raw.strip() != "":
            values[f.name] = _cast(getattr(defaults, f.name), raw)
    return Settings(**values)
