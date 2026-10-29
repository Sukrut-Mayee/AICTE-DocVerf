"""Entities shared between applications: the officer console's network view."""

from __future__ import annotations

from typing import Any

from docverf.reasoning.cross_institution import shared_entities
from docverf.schemas import FindingType
from fastapi import APIRouter, Request

router = APIRouter(tags=["network"])


@router.get("/network")
def get_network(request: Request) -> dict[str, Any]:
    """Land parcels and trust registrations claimed by different institutes, and lab photos that
    appear in more than one application (from the `duplicate` findings)."""
    applications = request.app.state.pipelines.load_all()
    names = {a.app_id: _institute_name(a.data.extractions) for a in applications}
    entities = shared_entities([a.data.extractions for a in applications])

    photos: dict[str, dict[str, dict[str, str]]] = {}
    for application in applications:
        for finding in application.data.findings:
            origin = finding.evidence.get("duplicate_of")
            if finding.type is not FindingType.DUPLICATE or not origin:
                continue
            members = photos.setdefault(origin["doc_id"], {})
            members[origin["app_id"]] = {"app_id": origin["app_id"], "doc_id": origin["doc_id"]}
            members[application.app_id] = {
                "app_id": application.app_id,
                "doc_id": finding.doc_ids[0],
            }
    for doc_id, members in photos.items():
        entities.append(
            {
                "id": f"photo:{doc_id}",
                "kind": "photo",
                "value": doc_id,
                "applications": [
                    {**m, "institute_name": names.get(m["app_id"], "")} for m in members.values()
                ],
            }
        )
    return {"entities": entities}


def _institute_name(extractions: list[Any]) -> str:
    for extraction in extractions:
        field = extraction.fields.get("institute_name")
        if field is not None and field.value:
            return str(field.value)
    return ""
