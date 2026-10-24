import json
import threading
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from docverf.config import get_settings
from docverf.schemas import CheckStatus, VerificationStatus
from docverf.verification.connectors import mock as connector_module
from docverf.verification.connectors.mock import MockIssuerConnector
from services.mock_issuer import main as issuer


def _make_app(root, app_id, true_fields, defects=()):
    app_dir = root / app_id
    app_dir.mkdir(parents=True)
    (app_dir / "ground_truth.json").write_text(
        json.dumps(
            {
                "app_id": app_id,
                "true_fields": true_fields,
                "injected_defects": [
                    {
                        "defect": defect,
                        "doc_id": f"{app_id}_noc",
                        "detail": "Synthetic test",
                    }
                    for defect in defects
                ],
            }
        ),
        encoding="utf-8",
    )


def test_aicte_record_and_payment_routes(tmp_path, monkeypatch):
    _make_app(
        tmp_path,
        "app001",
        {
            "app001_application_form": {
                "aicte_permanent_id": "1-1000001",
                "ter_txn_id": "TER202700001",
                "programs": [{"name": "Computer Engineering", "intake": 60}],
                "academic_year": "2025-26",
                "paid": False,
                "amount": 12000,
                "payment_date": "2026-08-15",
            }
        },
    )
    monkeypatch.setattr(issuer, "BASE_DIR", tmp_path)
    client = TestClient(issuer.app)

    record = client.get("/aicte/records/1-1000001")
    assert record.status_code == 200
    assert record.json()["approved"] is True
    assert record.json()["application_id"] == "app001"
    assert record.json()["programs"] == [
        {"name": "Computer Engineering", "intake": 60}
    ]
    assert record.json()["academic_year"] == "2025-26"
    assert client.get("/aicte/records/unknown").status_code == 404

    payment = client.get("/aicte/payments/TER202700001")
    assert payment.status_code == 200
    assert payment.json()["paid"] is False
    assert payment.json()["amount"] == 12000
    assert payment.json()["date"] == "2026-08-15"
    assert client.get("/aicte/payments/unknown").status_code == 404


def test_aicte_routes_use_documented_defaults_when_optional_data_is_absent(
    tmp_path, monkeypatch
):
    _make_app(
        tmp_path,
        "app002",
        {
            "app002_application_form": {
                "aicte_permanent_id": "1-1000002",
                "ter_txn_id": "TER202700002",
            }
        },
    )
    monkeypatch.setattr(issuer, "BASE_DIR", tmp_path)
    client = TestClient(issuer.app)
    current_year = date.today().year

    record = client.get("/aicte/records/1-1000002")
    assert record.status_code == 200
    assert record.json()["programs"] == []
    assert record.json()["academic_year"] == (
        f"{current_year - 1}-{str(current_year)[-2:]}"
    )

    payment = client.get("/aicte/payments/TER202700002")
    assert payment.status_code == 200
    assert payment.json()["date"] == date.today().isoformat()


@pytest.mark.parametrize(
    ("verification_status", "check_status"),
    [
        (VerificationStatus.VERIFIED, CheckStatus.VERIFIED),
        (VerificationStatus.MISMATCH_DETECTED, CheckStatus.MISMATCH),
        (VerificationStatus.EXPIRED, CheckStatus.MISMATCH),
        (VerificationStatus.VERIFICATION_PENDING, CheckStatus.NOT_APPLICABLE),
        (VerificationStatus.SOURCE_UNAVAILABLE, CheckStatus.ERROR),
        (VerificationStatus.MANUAL_REVIEW_REQUIRED, CheckStatus.SUSPICIOUS),
    ],
)
def test_connector_maps_all_verification_statuses(
    monkeypatch, verification_status, check_status
):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "doc_id": "app001_noc",
                "verification_status": verification_status.value,
                "status": CheckStatus.ERROR.value,
                "reason": "Synthetic test response",
                "source": "test",
            }

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, _url):
            return FakeResponse()

    monkeypatch.setattr(
        connector_module.httpx, "Client", lambda **_kwargs: FakeClient()
    )
    before = datetime.now().astimezone()
    result = MockIssuerConnector().lookup("FIRE/MH/2026/100001", {})
    after = datetime.now().astimezone()

    assert result.verification_status == verification_status
    assert result.status == check_status
    assert before <= result.checked_at <= after


@pytest.mark.parametrize(
    ("status_code", "check_status"),
    [
        (404, CheckStatus.ERROR),
        (503, CheckStatus.ERROR),
    ],
)
def test_connector_http_errors_are_source_unavailable(
    monkeypatch, status_code, check_status
):
    class FakeResponse:
        def __init__(self, code):
            self.status_code = code

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, _url):
            return FakeResponse(status_code)

    monkeypatch.setattr(
        connector_module.httpx, "Client", lambda **_kwargs: FakeClient()
    )
    result = MockIssuerConnector().lookup("missing", {})
    assert result.verification_status == VerificationStatus.SOURCE_UNAVAILABLE
    assert result.status == check_status
    assert result.checked_at.tzinfo is not None


def test_connector_connection_error_maps_to_source_unavailable(monkeypatch):
    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, _url):
            raise connector_module.httpx.ConnectError("connection refused")

    monkeypatch.setattr(
        connector_module.httpx, "Client", lambda **_kwargs: FakeClient()
    )
    result = MockIssuerConnector().lookup("unreachable", {})
    assert result.verification_status == VerificationStatus.SOURCE_UNAVAILABLE
    assert result.status == CheckStatus.ERROR
    assert result.checked_at.tzinfo is not None


def test_noc_lookup_reports_issuer_mismatch(tmp_path, monkeypatch):
    _make_app(
        tmp_path,
        "app003",
        {
            "app003_noc": {
                "ref_no": "FIRE/MH/2026/100003",
                "issuer": "Maharashtra Fire Services",
                "issue_date": "2026-01-01",
                "valid_until": "2028-12-31",
            }
        },
        ("ISSUER_MISMATCH",),
    )
    monkeypatch.setattr(issuer, "BASE_DIR", tmp_path)
    response = TestClient(issuer.app).get("/noc/FIRE/MH/2026/100003")

    assert response.status_code == 200
    assert (
        response.json()["verification_status"]
        == VerificationStatus.MISMATCH_DETECTED
    )
    assert (
        response.json()["evidence"]["document_issuer"]
        != response.json()["evidence"]["issuer_record"]
    )


def test_timeout_defect_delays_mock_endpoint(tmp_path, monkeypatch):
    _make_app(
        tmp_path,
        "app004",
        {
            "app004_noc": {
                "ref_no": "FIRE/MH/2026/100004",
                "issuer": "Maharashtra Fire Services",
                "issue_date": "2026-01-01",
                "valid_until": "2028-12-31",
            }
        },
        ("ISSUER_TIMEOUT",),
    )
    monkeypatch.setattr(issuer, "BASE_DIR", tmp_path)
    monkeypatch.setattr(issuer, "SLOW_RESPONSE_DELAY_S", 0.05)
    started = time.monotonic()
    response = TestClient(issuer.app).get("/noc/FIRE/MH/2026/100004")

    assert response.status_code == 200
    assert time.monotonic() - started >= 0.04


def test_connector_timeout_maps_to_pending(monkeypatch):
    class SlowHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(1.3)
            body = b"{}"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("MOCK_ISSUER_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("SOURCE_TIMEOUT_S", "1")
    get_settings.cache_clear()
    try:
        result = MockIssuerConnector().lookup("slow", {})
        assert result.verification_status == VerificationStatus.VERIFICATION_PENDING
        assert result.status == CheckStatus.NOT_APPLICABLE
        assert result.checked_at.tzinfo is not None
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        get_settings.cache_clear()
