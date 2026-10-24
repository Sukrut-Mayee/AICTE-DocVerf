"""Application queue, summary, documents, findings and decision routes."""

from __future__ import annotations

from typing import Any

from docverf.schemas import Decision, Severity
from fastapi import APIRouter, HTTPException, Query, Request

from ..documents import build_documents, build_findings, build_queue, build_summary
from ..models import DecisionRequest
from ..pipeline import ApplicationNotFound, InvalidPipeline, is_valid_app_id
from ..settings import ApiSettings
from ..store import OfficerStore

router = APIRouter(tags=["applications"])


def _settings(request: Request) -> ApiSettings:
    return request.app.state.settings


def _store(request: Request) -> OfficerStore:
    return request.app.state.store


def _load(request: Request, app_id: str):
    repository = request.app.state.pipelines
    if not is_valid_app_id(app_id):
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        return repository.load(app_id)
    except ApplicationNotFound as exc:
        raise HTTPException(status_code=404, detail="Application not found") from exc
    except InvalidPipeline as exc:
        raise HTTPException(
            status_code=500, detail="The pipeline output for this application is invalid"
        ) from exc


@router.get("/applications")
def list_applications(
    request: Request, status: str | None = Query(default=None)
) -> list[dict[str, Any]]:
    repository = request.app.state.pipelines
    queue = build_queue(repository.load_all(), _store(request))
    if status:
        queue = [item for item in queue if item["status"] == status]
    return queue


@router.get("/applications/{app_id}")
def get_application(request: Request, app_id: str) -> dict[str, Any]:
    application = _load(request, app_id)
    return build_summary(application, _store(request))


@router.get("/applications/{app_id}/documents")
def get_documents(request: Request, app_id: str) -> list[dict[str, Any]]:
    application = _load(request, app_id)
    return build_documents(application, _settings(request), _store(request))


@router.get("/applications/{app_id}/findings")
def get_findings(request: Request, app_id: str) -> list[dict[str, Any]]:
    application = _load(request, app_id)
    return build_findings(application, _store(request))


@router.post("/applications/{app_id}/decision")
def record_decision(request: Request, app_id: str, payload: DecisionRequest) -> dict[str, Any]:
    application = _load(request, app_id)
    store = _store(request)
    actions = store.latest_actions_for_app(app_id)
    pending = [
        finding.finding_id
        for finding in application.data.findings
        if finding.severity == Severity.HIGH and finding.finding_id not in actions
    ]
    if pending:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Every high-severity finding must be confirmed or dismissed "
                    "before a decision is recorded."
                ),
                "finding_ids": pending,
            },
        )
    if payload.decision == Decision.REJECT and not payload.reason:
        raise HTTPException(
            status_code=400,
            detail="A reason is required when rejecting an application.",
        )
    return store.record_decision(
        app_id=app_id,
        decision=payload.decision.value,
        reason=payload.reason,
        deficiencies=payload.deficiencies,
    )
