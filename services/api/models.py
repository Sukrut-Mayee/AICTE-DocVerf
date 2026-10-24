"""Request models for officer actions and decisions (TRD §11).

The frozen TRD §5 models describe pipeline data.  These are API-only payloads.
"""

from __future__ import annotations

from typing import Literal

from docverf.schemas import Decision
from pydantic import BaseModel, Field, field_validator


class FindingActionRequest(BaseModel):
    action: Literal["confirm", "dismiss"]
    reason: str = Field(max_length=4000)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("a reason is required to confirm or dismiss a finding")
        return cleaned


class DecisionRequest(BaseModel):
    decision: Decision
    reason: str = Field(default="", max_length=4000)
    deficiencies: list[str] = Field(default_factory=list)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        return value.strip()

    @field_validator("deficiencies")
    @classmethod
    def trim_deficiencies(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = value.strip()
            if text:
                cleaned.append(text)
        return cleaned
