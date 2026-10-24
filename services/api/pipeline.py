"""Read and validate pipeline output files (shared contract B).

`run_pipeline("data/synthetic/app001")` writes `data/out/pipeline/app001.json` with
`app_id`, `extractions[]`, `checks[]`, `findings[]`, `documents[]`, `priority` and
`audit`.  The dashboard never re-runs extraction or reasoning; it only reads these
files, so the real pipeline can replace the seeded mock output without a code change.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docverf.schemas import (
    CheckResult,
    DocumentStatus,
    ExtractionResult,
    Finding,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)

APP_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class PipelineError(Exception):
    """Base class for pipeline file problems."""


class ApplicationNotFound(PipelineError):
    """No pipeline output exists for the requested application."""


class InvalidPipeline(PipelineError):
    """The pipeline output exists but cannot be trusted."""


class AuditRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    seq: int = 0
    hash: str | None = None
    tx: str | None = None


class PipelineOutput(BaseModel):
    """Contract B, with tolerant extras so additive pipeline fields are not lost."""

    model_config = ConfigDict(extra="allow")

    app_id: str
    extractions: list[ExtractionResult] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    documents: list[DocumentStatus] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0)
    audit: AuditRef | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class LoadedApplication:
    data: PipelineOutput
    path: Path

    @property
    def app_id(self) -> str:
        return self.data.app_id


def is_valid_app_id(app_id: str) -> bool:
    """Reject path separators and odd IDs before they reach the filesystem."""

    return bool(APP_ID_PATTERN.fullmatch(app_id))


class PipelineRepository:
    """Load pipeline JSON on demand; no stale in-process cache."""

    def __init__(self, pipeline_dir: Path) -> None:
        self.pipeline_dir = pipeline_dir

    def output_path(self, app_id: str) -> Path:
        if not is_valid_app_id(app_id):
            raise ApplicationNotFound(app_id)
        return self.pipeline_dir / f"{app_id}.json"

    def exists(self, app_id: str) -> bool:
        try:
            return self.output_path(app_id).is_file()
        except ApplicationNotFound:
            return False

    def load(self, app_id: str) -> LoadedApplication:
        path = self.output_path(app_id)
        if not path.is_file():
            raise ApplicationNotFound(app_id)
        data = self._read(path)
        if data.app_id != app_id:
            raise InvalidPipeline(
                f"pipeline file {path.name} declares app_id {data.app_id!r}, not {app_id!r}"
            )
        return LoadedApplication(data=data, path=path)

    def load_all(self) -> list[LoadedApplication]:
        """Return every valid application. Invalid files are logged and skipped."""

        if not self.pipeline_dir.is_dir():
            return []
        loaded: list[LoadedApplication] = []
        for path in sorted(self.pipeline_dir.glob("*.json")):
            app_id = path.stem
            if not is_valid_app_id(app_id):
                logger.warning("Skipping pipeline file with invalid app id: %s", path.name)
                continue
            try:
                loaded.append(self.load(app_id))
            except (ApplicationNotFound, InvalidPipeline) as exc:
                logger.warning("Skipping unreadable pipeline file %s: %s", path.name, exc)
        return loaded

    def find_finding(self, finding_id: str) -> tuple[LoadedApplication, Finding]:
        for application in self.load_all():
            for finding in application.data.findings:
                if finding.finding_id == finding_id:
                    return application, finding
        raise ApplicationNotFound(finding_id)

    def _read(self, path: Path) -> PipelineOutput:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidPipeline("pipeline output is not readable JSON") from exc
        if not isinstance(raw, dict):
            raise InvalidPipeline("pipeline output must be a JSON object")
        try:
            data = PipelineOutput.model_validate(raw)
        except ValidationError as exc:
            raise InvalidPipeline("pipeline output does not match the shared contract") from exc

        for extraction in data.extractions:
            if extraction.app_id != data.app_id:
                raise InvalidPipeline("an extraction belongs to a different application")
        for finding in data.findings:
            if finding.app_id != data.app_id:
                raise InvalidPipeline("a finding belongs to a different application")
        return data
