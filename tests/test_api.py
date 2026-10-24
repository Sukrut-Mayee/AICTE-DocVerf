"""Officer API tests: queue, evidence, safe files, actions and decision locking."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.pipeline import PipelineRepository
from services.api.settings import ApiSettings

FIXTURE_JSON = Path(__file__).parent / "fixtures" / "pipeline" / "app001.json"
HIGH_FINDING_IDS = ["f_1a2b3c4d", "f_2b3c4d5e", "f_3c4d5e6f", "f_4d5e6f70"]

CLEAN_APP = {
    "app_id": "app002",
    "extractions": [],
    "checks": [],
    "findings": [],
    "documents": [
        {
            "doc_id": "app002_noc",
            "overall": "no_issues",
            "verification": "verified",
            "note": "No issues found.",
            "finding_ids": [],
        }
    ],
    "priority": 0,
    "audit": {"seq": 0, "hash": "0" * 64, "tx": None},
}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    shutil.copyfile(FIXTURE_JSON, pipeline_dir / "app001.json")
    (pipeline_dir / "app002.json").write_text(json.dumps(CLEAN_APP), encoding="utf-8")

    app_dir = tmp_path / "synthetic" / "app001"
    app_dir.mkdir(parents=True)
    (app_dir / "land_deed.pdf").write_bytes(b"%PDF-1.4\n% demo land deed\n")
    (app_dir / "noc.pdf").write_bytes(b"%PDF-1.4\n% demo noc\n")
    (app_dir / "affidavit.pdf").write_bytes(b"%PDF-1.4\n% demo affidavit\n")
    (app_dir / "application_form.json").write_text("{}", encoding="utf-8")
    (app_dir / ".env").write_text("SECRET=do-not-serve", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside", encoding="utf-8")

    clean_dir = tmp_path / "synthetic" / "app002"
    clean_dir.mkdir(parents=True)
    (clean_dir / "noc.pdf").write_bytes(b"%PDF-1.4\n% clean\n")
    return tmp_path


def make_settings(workspace: Path) -> ApiSettings:
    return ApiSettings(
        pipeline_dir=workspace / "pipeline",
        synthetic_dir=workspace / "synthetic",
        db_path=workspace / "officer.db",
        web_origins=(),
    )


@pytest.fixture
def client(workspace: Path):
    app = create_app(make_settings(workspace))
    with TestClient(app) as test_client:
        yield test_client


def _handle_high_findings(client: TestClient) -> None:
    for finding_id in HIGH_FINDING_IDS:
        response = client.post(
            f"/v1/findings/{finding_id}/action",
            json={"action": "confirm", "reason": "Checked against the source document."},
        )
        assert response.status_code == 200, response.text


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_queue_is_sorted_by_priority_and_has_counts(client: TestClient):
    response = client.get("/v1/applications")
    assert response.status_code == 200
    queue = response.json()
    assert [item["app_id"] for item in queue] == ["app001", "app002"]

    first = queue[0]
    assert first["priority"] == 401
    assert first["institute_name"] == "Shree Vidya Institute of Technology"
    assert first["finding_counts"] == {
        "total": 5,
        "high": 4,
        "medium": 0,
        "low": 1,
        "info": 0,
    }
    assert first["document_counts"] == {
        "total": 4,
        "flagged": 3,
        "manual_review": 1,
        "no_issues": 0,
    }
    assert first["high_pending"] == 4
    assert first["decision_allowed"] is False
    assert first["meta"]["source"] == "mock_fixture"

    second = queue[1]
    assert second["priority"] == 0
    assert second["finding_counts"]["total"] == 0
    assert second["decision_allowed"] is True


def test_queue_status_filter(client: TestClient):
    response = client.get("/v1/applications", params={"status": "decided"})
    assert response.status_code == 200
    assert response.json() == []
    response = client.get("/v1/applications", params={"status": "review_pending"})
    assert {item["app_id"] for item in response.json()} == {"app001", "app002"}


def test_unknown_application_returns_404(client: TestClient):
    for path in (
        "/v1/applications/missing",
        "/v1/applications/missing/documents",
        "/v1/applications/missing/findings",
    ):
        response = client.get(path)
        assert response.status_code == 404


def test_documents_are_flagged_first_and_resolve_files(client: TestClient):
    response = client.get("/v1/applications/app001/documents")
    assert response.status_code == 200
    documents = response.json()
    assert len(documents) == 4
    overalls = [document["overall"] for document in documents]
    assert overalls.index("manual_review_required") > max(
        index for index, value in enumerate(overalls) if value == "flagged"
    )

    deed = next(document for document in documents if document["doc_id"] == "app001_land_deed")
    assert deed["doc_type"] == "land_deed"
    assert deed["filename"] == "land_deed.pdf"
    assert deed["file_url"] == "/v1/files/app001/land_deed.pdf"
    assert deed["previewable"] is True
    assert deed["high_findings"] == 2
    assert deed["max_severity"] == "high"

    form = next(
        document for document in documents if document["doc_id"] == "app001_application_form"
    )
    assert form["doc_type"] == "application_form"
    assert form["filename"] == "application_form.json"
    assert form["previewable"] is False
    assert form["file_url"] == "/v1/files/app001/application_form.json"


def test_findings_preserve_evidence_and_action_state(client: TestClient):
    response = client.get("/v1/applications/app001/findings")
    assert response.status_code == 200
    findings = response.json()
    assert len(findings) == 5
    assert [finding["severity"] for finding in findings].count("high") == 4

    area = next(finding for finding in findings if finding["finding_id"] == "f_1a2b3c4d")
    assert area["rule_id"] == "LAND_AREA_AGREE"
    assert area["claims"][1]["bbox"] == [0.12, 0.41, 0.35, 0.44]
    assert area["claims"][1]["page"] == 1
    assert area["officer_action"] is None

    action = client.post(
        "/v1/findings/f_1a2b3c4d/action",
        json={"action": "confirm", "reason": "Values match the reviewed documents."},
    )
    assert action.status_code == 200
    refreshed = client.get("/v1/applications/app001/findings").json()
    area_after = next(item for item in refreshed if item["finding_id"] == "f_1a2b3c4d")
    assert area_after["officer_action"]["action"] == "confirm"
    assert area_after["officer_action"]["reason"] == "Values match the reviewed documents."


def test_serves_allowed_pdf_inline(client: TestClient):
    response = client.get("/v1/files/app001/land_deed.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-1.4")


@pytest.mark.parametrize(
    "path",
    [
        "/v1/files/app001/.env",
        "/v1/files/app001/../.env",
        "/v1/files/app001/..%2Fsecret.txt",
        "/v1/files/app001/%2e%2e%2f%2e%2e%2fsecret.txt",
        "/v1/files/app001/C:%5CWindows%5Cwin.ini",
        "/v1/files/app001/ground_truth.json",
        "/v1/files/app001/missing.pdf",
        "/v1/files/missing/noc.pdf",
    ],
)
def test_file_endpoint_blocks_unsafe_paths(client: TestClient, path: str):
    response = client.get(path)
    assert response.status_code in {400, 404}, response.text
    assert response.content != b"outside"
    assert b"SECRET" not in response.content


def test_invalid_pipeline_is_skipped_in_queue_and_errors_on_detail(
    client: TestClient, workspace: Path
):
    (workspace / "pipeline" / "app003.json").write_text("{not valid json", encoding="utf-8")

    queue = client.get("/v1/applications")
    assert queue.status_code == 200
    assert {item["app_id"] for item in queue.json()} == {"app001", "app002"}

    detail = client.get("/v1/applications/app003")
    assert detail.status_code == 500
    assert "not valid json" not in detail.text
    assert str(workspace) not in detail.text


def test_invalid_action_and_reason_are_rejected(client: TestClient):
    invalid_action = client.post(
        "/v1/findings/f_1a2b3c4d/action",
        json={"action": "ignore", "reason": "because"},
    )
    assert invalid_action.status_code == 422

    blank_reason = client.post(
        "/v1/findings/f_1a2b3c4d/action",
        json={"action": "confirm", "reason": "   "},
    )
    assert blank_reason.status_code == 422

    unknown = client.post(
        "/v1/findings/f_doesnotexist/action",
        json={"action": "confirm", "reason": "because"},
    )
    assert unknown.status_code == 404


def test_decision_is_locked_while_high_findings_are_unhandled(client: TestClient):
    response = client.post(
        "/v1/applications/app001/decision",
        json={"decision": "approve", "reason": "Looks complete."},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert set(detail["finding_ids"]) == set(HIGH_FINDING_IDS)
    assert "high-severity" in detail["message"]

    summary = client.get("/v1/applications/app001").json()
    assert summary["status"] == "review_pending"
    assert summary["decision"] is None


def test_decision_unlocks_after_all_high_findings_have_actions(client: TestClient):
    _handle_high_findings(client)

    summary = client.get("/v1/applications/app001").json()
    assert summary["high_pending"] == 0
    assert summary["decision_allowed"] is True

    response = client.post(
        "/v1/applications/app001/decision",
        json={
            "decision": "approve_with_deficiencies",
            "reason": "High findings reviewed; confirm the NOC validity.",
            "deficiencies": ["Provide a NOC valid through the academic year."],
        },
    )
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["decision"] == "approve_with_deficiencies"
    assert record["deficiencies"] == ["Provide a NOC valid through the academic year."]

    refreshed = client.get("/v1/applications/app001").json()
    assert refreshed["status"] == "decided"
    assert refreshed["decision"]["decision"] == "approve_with_deficiencies"
    assert refreshed["decision"]["reason"].startswith("High findings reviewed")


def test_rejection_requires_a_nonblank_reason(client: TestClient):
    _handle_high_findings(client)

    blank = client.post(
        "/v1/applications/app001/decision",
        json={"decision": "reject", "reason": "   "},
    )
    assert blank.status_code == 400
    assert "reason" in blank.json()["detail"].lower()

    rejected = client.post(
        "/v1/applications/app001/decision",
        json={"decision": "reject", "reason": "Land ownership cannot be established."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["decision"] == "reject"


def test_invalid_decision_value_is_rejected(client: TestClient):
    response = client.post(
        "/v1/applications/app001/decision",
        json={"decision": "auto_approve", "reason": "nope"},
    )
    assert response.status_code == 422


def test_latest_action_and_decision_survive_a_new_app_instance(client: TestClient, workspace: Path):
    _handle_high_findings(client)
    client.post(
        "/v1/findings/f_1a2b3c4d/action",
        json={"action": "dismiss", "reason": "First review."},
    )
    client.post(
        "/v1/findings/f_1a2b3c4d/action",
        json={"action": "confirm", "reason": "Second review."},
    )
    client.post(
        "/v1/applications/app001/decision",
        json={"decision": "site_inspection", "reason": "Verify the parcel on site."},
    )

    restarted = create_app(make_settings(workspace))
    with TestClient(restarted) as second_client:
        findings = second_client.get("/v1/applications/app001/findings").json()
        area = next(item for item in findings if item["finding_id"] == "f_1a2b3c4d")
        assert area["officer_action"]["action"] == "confirm"
        assert area["officer_action"]["reason"] == "Second review."

        summary = second_client.get("/v1/applications/app001").json()
        assert summary["decision"]["decision"] == "site_inspection"
        assert summary["status"] == "decided"


def test_committed_mock_fixture_matches_the_contract():
    repository = PipelineRepository(FIXTURE_JSON.parent)
    application = repository.load("app001")
    assert application.data.priority == 401
    assert len(application.data.documents) == 4
    assert sum(1 for finding in application.data.findings if finding.severity.value == "high") == 4
    assert application.data.meta["source"] == "mock_fixture"
    assert any(claim.bbox for finding in application.data.findings for claim in finding.claims)
