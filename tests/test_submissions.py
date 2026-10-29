"""POST /v1/submissions: the portal's multipart payload becomes a processed application.

The valid-application tests copy documents of app009 from data/synthetic (gitignored) and skip
when it is absent. The pipeline runs for real: no OCR (digital PDFs), no VLM, no issuer (their URLs
point at a closed port), ledger in a temporary SQLite file."""

import json
from pathlib import Path

import pytest
from docverf.config import get_settings
from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.settings import ApiSettings

SOURCE = Path(__file__).parents[1] / "data" / "synthetic" / "app009"
CLOSED = "http://127.0.0.1:9"
needs_data = pytest.mark.skipif(not (SOURCE / "land_deed.pdf").exists(), reason="no data/synthetic")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # ELA heatmaps go to ./data/out/forensics
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ledger.db'}")
    monkeypatch.setenv("MOCK_ISSUER_URL", CLOSED)
    monkeypatch.setenv("OLLAMA_URL", CLOSED)
    monkeypatch.setenv("ANCHOR_CONTRACT_ADDRESS", "")
    get_settings.cache_clear()
    settings = ApiSettings(
        pipeline_dir=tmp_path / "pipeline",
        synthetic_dir=tmp_path / "synthetic",
        db_path=tmp_path / "officer.db",
    )
    yield TestClient(create_app(settings)), settings
    get_settings.cache_clear()


def submit(client, institute_id, name, survey="66/8"):
    form = {
        "institute_name": name,
        "application_no": f"1-{institute_id}",
        "aicte_permanent_id": institute_id,
        "address": "Pune",
        "land_survey_no": survey,
    }
    names = [("land_deed", "land_deed.pdf"), ("noc", "noc.pdf"), ("affidavit", "affidavit.pdf")]
    names.append(("lab_photo", "lab_photo_1.jpg"))
    files = [("files", (n, (SOURCE / n).read_bytes())) for _, n in names]
    data = {"form": json.dumps(form), "doc_types": json.dumps([t for t, _ in names])}
    return client.post("/v1/submissions", data=data, files=files)


@needs_data
def test_land_deed_copied_from_another_institute_is_reused_across_institutions(client):
    api, settings = client
    first = submit(api, "1-1000001", "First Institute")
    assert first.status_code == 200, first.text
    assert first.json()["app_id"] == "app001" and first.json()["status"] == "review_pending"

    second = submit(api, "1-2000002", "Second Institute")
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["app_id"] == "app002" and body["findings_count"] > 0 and body["priority"] >= 100

    findings = api.get("/v1/applications/app002/findings").json()
    reuse = [f for f in findings if f["rule_id"] == "CROSS_INSTITUTION_LAND"]
    assert len(reuse) == 1 and reuse[0]["severity"] == "high"
    assert reuse[0]["evidence"]["also_claimed_by"][0]["app_id"] == "app001"
    # The first application was processed before the second existed.
    first_findings = api.get("/v1/applications/app001/findings").json()
    assert not [f for f in first_findings if f["rule_id"] == "CROSS_INSTITUTION_LAND"]
    # The same photo in two applications is a duplicate; the network view lists both.
    kinds = {e["kind"] for e in api.get("/v1/network").json()["entities"]}
    assert {"land_parcel", "photo", "document"} <= kinds
    # Saved as new folders next to the existing ones; the manifest is a valid dataset entry.
    assert (settings.synthetic_dir / "app002" / "ground_truth.json").is_file()
    assert (settings.pipeline_dir / "app002.json").is_file()


@needs_data
def test_same_institute_resubmitting_is_not_flagged(client):
    api, _ = client
    assert submit(api, "1-1000001", "First Institute").status_code == 200
    again = submit(api, "1-1000001", "First Institute")
    findings = api.get(f"/v1/applications/{again.json()['app_id']}/findings").json()
    assert not [f for f in findings if f["rule_id"] == "CROSS_INSTITUTION_LAND"]


def test_invalid_payloads_are_rejected_and_create_nothing(client):
    api, settings = client
    pdf = ("files", ("noc.pdf", b"%PDF-1.4"))
    form = json.dumps({"institute_name": "X"})
    bad = [
        {"form": "not json", "doc_types": '["noc"]'},
        {"form": form, "doc_types": '["passport"]'},
        {"form": form, "doc_types": '["noc", "noc"]'},
        {"form": json.dumps({}), "doc_types": '["noc"]'},
    ]
    for data in bad:
        assert api.post("/v1/submissions", data=data, files=[pdf]).status_code == 422
    exe = ("files", ("noc.exe", b"MZ"))
    response = api.post("/v1/submissions", data={"form": form, "doc_types": '["noc"]'}, files=[exe])
    assert response.status_code == 422
    assert not settings.synthetic_dir.exists() or not list(settings.synthetic_dir.iterdir())


def test_a_failing_pipeline_is_reported_not_faked(client, monkeypatch):
    api, settings = client
    import services.worker.pipeline as pipeline

    monkeypatch.setattr(pipeline, "run", lambda *a, **k: 1)
    files = [("files", ("noc.pdf", b"%PDF-1.4"))]
    data = {"form": json.dumps({"institute_name": "X"}), "doc_types": '["noc"]'}
    response = api.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 500 and "failed" in response.json()["detail"]
    assert not (settings.pipeline_dir / "app001.json").exists()
    # The files are kept, but the folder is no longer part of the dataset.
    assert not (settings.synthetic_dir / "app001" / "ground_truth.json").exists()
