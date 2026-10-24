"""Confirm/dismiss actions for pipeline findings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..models import FindingActionRequest
from ..pipeline import ApplicationNotFound

router = APIRouter(tags=["findings"])


@router.post("/findings/{finding_id}/action")
def record_finding_action(
    request: Request, finding_id: str, payload: FindingActionRequest
) -> dict[str, Any]:
    repository = request.app.state.pipelines
    try:
        application, finding = repository.find_finding(finding_id)
    except ApplicationNotFound as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc

    return request.app.state.store.record_action(
        finding_id=finding.finding_id,
        app_id=application.data.app_id,
        action=payload.action,
        reason=payload.reason,
    )
