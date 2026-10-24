"""Mock issuer API backed by the local synthetic dataset (TRD §13.3)."""

import asyncio
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from docverf.schemas.enums import CheckStatus, Layer, VerificationStatus
from docverf.schemas.models import CheckResult

app = FastAPI(title="Mock Issuer API", version="1.0.0")

BASE_DIR = Path(
    os.environ.get(
        "MOCK_ISSUER_DATASET_DIR",
        str(Path(__file__).resolve().parents[2] / "data" / "synthetic"),
    )
)
SLOW_RESPONSE_DELAY_S = float(os.environ.get("MOCK_ISSUER_SLOW_RESPONSE_DELAY_S", "6"))
ISSUER_RECORD = "Maharashtra Fire Services"
MISMATCHED_ISSUER_RECORD = "Synthetic Regional Fire Authority"


def _load_app_ground_truths() -> list[tuple[Path, dict[str, Any]]]:
    if not BASE_DIR.exists():
        return []

    results = []
    for app_dir in sorted(BASE_DIR.glob("app[0-9][0-9][0-9]")):
        gt_path = app_dir / "ground_truth.json"
        if not gt_path.is_file():
            continue
        try:
            gt = json.loads(gt_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Could not read synthetic ground truth for {app_dir.name}: {exc}",
            ) from exc
        results.append((app_dir, gt))
    return results


def _find_app_by_field(field_name: str, value: str) -> tuple[str, dict, dict] | None:
    for app_dir, gt in _load_app_ground_truths():
        for fields in gt.get("true_fields", {}).values():
            if isinstance(fields, dict) and fields.get(field_name) == value:
                return app_dir.name, gt, fields
    return None


def _application_fields(app_id: str, gt: dict[str, Any]) -> dict[str, Any]:
    fields = gt.get("true_fields", {}).get(f"{app_id}_application_form", {})
    return fields if isinstance(fields, dict) else {}


def _defect_codes(gt: dict[str, Any]) -> set[str]:
    return {
        defect.get("defect")
        for defect in gt.get("injected_defects", [])
        if isinstance(defect, dict)
    }


def _check_status(verification_status: VerificationStatus) -> CheckStatus:
    if verification_status == VerificationStatus.VERIFIED:
        return CheckStatus.VERIFIED
    if verification_status in {
        VerificationStatus.MISMATCH_DETECTED,
        VerificationStatus.EXPIRED,
    }:
        return CheckStatus.MISMATCH
    if verification_status == VerificationStatus.MANUAL_REVIEW_REQUIRED:
        return CheckStatus.SUSPICIOUS
    if verification_status == VerificationStatus.VERIFICATION_PENDING:
        return CheckStatus.NOT_APPLICABLE
    return CheckStatus.ERROR


@app.get("/noc/{ref_no:path}", response_model=CheckResult)
async def noc_lookup(ref_no: str):
    """Look up a generated NOC reference, including explicit defect scenarios."""
    found = _find_app_by_field("ref_no", ref_no)
    if found is None:
        raise HTTPException(status_code=404, detail=f"NOC reference {ref_no} not found")

    app_id, gt, fields = found
    defects = _defect_codes(gt)
    if "ISSUER_TIMEOUT" in defects:
        await asyncio.sleep(SLOW_RESPONSE_DELAY_S)

    valid_until = fields.get("valid_until")
    verification_status = VerificationStatus.VERIFIED
    if valid_until:
        try:
            if date.fromisoformat(str(valid_until)) < date.today():
                verification_status = VerificationStatus.EXPIRED
        except ValueError:
            verification_status = VerificationStatus.MANUAL_REVIEW_REQUIRED

    document_issuer = fields.get("issuer", ISSUER_RECORD)
    issuer_record = (
        MISMATCHED_ISSUER_RECORD
        if "ISSUER_MISMATCH" in defects
        else document_issuer
    )
    if "ISSUER_MISMATCH" in defects or (
        document_issuer and document_issuer != issuer_record
    ):
        verification_status = VerificationStatus.MISMATCH_DETECTED

    evidence = {
        "ref_no": ref_no,
        "issue_date": fields.get("issue_date"),
        "valid_until": valid_until,
        "document_issuer": document_issuer,
        "issuer_record": issuer_record,
        "app_id": app_id,
    }
    result = CheckResult(
        doc_id=f"{app_id}_noc",
        layer=Layer.A,
        check="issuer_lookup",
        status=_check_status(verification_status),
        severity=(
            "high"
            if verification_status == VerificationStatus.MISMATCH_DETECTED
            else "info"
        ),
        reason=f"Mock issuer lookup for NOC reference {ref_no}",
        evidence=evidence,
        verification_status=verification_status,
        source=f"synthetic_dataset_{app_id}",
        checked_at=datetime.now().astimezone(),
    )
    return JSONResponse(content=result.model_dump(mode="json"))


@app.get("/aicte/records/{record_id}")
async def aicte_record_lookup(record_id: str):
    """Return the deterministic approved intake record for a known AICTE ID."""
    found = _find_app_by_field("aicte_permanent_id", record_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"AICTE record {record_id} not found")
    app_id, gt, _ = found
    application_fields = _application_fields(app_id, gt)
    programs = application_fields.get("programs", [])
    if not isinstance(programs, list):
        raise HTTPException(
            status_code=500,
            detail=f"AICTE programs for {app_id} must be a list",
        )
    current_year = date.today().year
    academic_year = application_fields.get(
        "academic_year", f"{current_year - 1}-{str(current_year)[-2:]}"
    )
    return JSONResponse(
        {
            "aicte_permanent_id": record_id,
            "application_id": app_id,
            "approved": True,
            "academic_year": academic_year,
            "programs": programs,
            "source": "synthetic_mock_aicte",
        }
    )


@app.get("/aicte/payments/{txn}")
async def aicte_payment_lookup(txn: str):
    """Return a deterministic fee payment for a known transaction ID."""
    found = _find_app_by_field("ter_txn_id", txn)
    if found is None:
        raise HTTPException(status_code=404, detail=f"Payment transaction {txn} not found")
    app_id, gt, _ = found
    application_fields = _application_fields(app_id, gt)
    return JSONResponse(
        {
            "transaction_id": txn,
            "application_id": app_id,
            "paid": application_fields.get("paid", True),
            "amount": application_fields.get("amount", 10000),
            "date": application_fields.get("payment_date", date.today().isoformat()),
            "source": "synthetic_mock_aicte",
        }
    )


@app.get("/health", include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8100)
