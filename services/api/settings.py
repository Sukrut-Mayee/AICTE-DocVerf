"""Runtime paths for the officer API.

The frozen `docverf.config` module only describes pipeline/configuration values.  The
officer API needs a few service-local paths (pipeline output, synthetic documents and
the officer SQLite database), so they live here and remain overrideable for tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


@dataclass(frozen=True)
class ApiSettings:
    """Filesystem locations and CORS origins used by the officer API."""

    pipeline_dir: Path = field(default_factory=lambda: REPO_ROOT / "data" / "out" / "pipeline")
    synthetic_dir: Path = field(default_factory=lambda: REPO_ROOT / "data" / "synthetic")
    db_path: Path = field(default_factory=lambda: REPO_ROOT / "data" / "officer.db")
    web_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")

    @classmethod
    def from_env(cls) -> ApiSettings:
        origins_raw = os.environ.get(
            "DOCVERF_WEB_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        )
        origins = tuple(origin.strip() for origin in origins_raw.split(",") if origin.strip())
        return cls(
            pipeline_dir=_path_from_env(
                "DOCVERF_PIPELINE_DIR", REPO_ROOT / "data" / "out" / "pipeline"
            ),
            synthetic_dir=_path_from_env("DOCVERF_SYNTHETIC_DIR", REPO_ROOT / "data" / "synthetic"),
            db_path=_path_from_env("DOCVERF_OFFICER_DB", REPO_ROOT / "data" / "officer.db"),
            web_origins=origins,
        )
