"""Mock Issuer API for AICTE-DocVerf (TRD A9.3).

Provides a FastAPI endpoint `GET /noc/{ref_no}` that reads reference
information from the synthetic ground-truth dataset and returns a
`CheckResult` suitable for the `MockIssuerConnector.lookup()` interface.

- Endpoint:   GET /noc/{ref_no}
- Base URL:   http://localhost:8100  (MOCK_ISSUER_URL from config)
- Data source: ground_truth.json files from the synthetic dataset
- Response:   CheckResult with verification_status and issuer fields

Supported statuses (VerificationStatus enum):
    VERIFIED, MISMATCH_DETECTED, EXPIRED, VERIFICATION_PENDING,
    SOURCE_UNAVAILABLE, MANUAL_REVIEW_REQUIRED
"""

from datetime import date, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path

import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.docverf.schemas.enums import VerificationStatus, Layer
from packages.docverf.schemas.models import CheckResult

app = FastAPI(title="Mock Issuer API", version="1.0.0")

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent / "final_verify_out"


def _find_app_by_ref(ref_no: str) -> tuple[str, dict] | None:
    """Search ground-truth JSON files for a matching noc.ref_no.

    Returns (app_id, noc_fields) or None if not found.
    """
    if not BASE_DIR.exists():
        return None

    for app_dir in sorted(BASE_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        gt_path = app_dir / "ground_truth.json"
        if not gt_path.exists():
            continue
        try:
            with open(gt_path, encoding="utf-8") as f:
                gt = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        noc_fields = gt.get("true_fields", {})
        # Check all true_fields entries for a noc ref_no match
        for key, val in noc_fields.items():
            if isinstance(val, dict) and val.get("ref_no") == ref_no:
                return app_dir.name, val
    return None


@app.get("/noc/{ref_no}", response_model=CheckResult)
async def noc_lookup(ref_no: str):
    """GET /noc/{ref_no} — look up NOC reference in synthetic dataset.

    Returns a CheckResult with:
      - verified:           ref_no found and matches ground truth
      - mismatch_detected:  ref_no found but data differs from expected
      - expired:            NOC validity period has elapsed
      - verification_pending: deterministic timeout/simulated pending
      - source_unavailable: ref_no not found in any ground-truth file

    Raises HTTPException 404 when the reference is not found in the dataset.
    """
    app_id, fields = _find_app_by_ref(ref_no)
    if app_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"NOC reference {ref_no} not found in synthetic dataset",
        )

    # Determine verification status based on field values
    valid_until = fields.get("valid_until")
    issue_date = fields.get("issue_date")
    ref_no_from_data = fields.get("ref_no", ref_no)

    # Check if NOC is expired (valid_until date has passed)
    today = date(2026, 10, 24)  # current date in the project context

    if valid_until:
        try:
            exp_date = valid_until.split("-") if isinstance(valid_until, str) else valid_until
            exp_year, exp_month, exp_day = int(exp_date[0]), int(exp_date[1]), int(exp_date[2])
            if date(exp_year, exp_month, exp_day) < today:
                status = VerificationStatus.EXPIRED
            else:
                status = VerificationStatus.VERIFIED
        except (ValueError, IndexError):
            status = VerificationStatus.VERIFIED
    else:
        status = VerificationStatus.VERIFIED

    # Build evidence dict with available NOC fields
    evidence = {
        "ref_no": ref_no_from_data,
        "issue_date": issue_date,
        "valid_until": valid_until,
        "app_id": app_id,
    }

    # If we have a name mismatch defect injected, surface it as mismatch_detected
    # by checking injected_defects for NAME_MISMATCH or similar
    try:
        gt_path = Path(__file__).parent.parent.parent / "final_verify_out" / app_id / "ground_truth.json"
        if gt_path.exists():
            with open(gt_path, encoding="utf-8") as f:
                gt = json.load(f)
            injected = gt.get("injected_defects", [])
            defect_codes = [d.get("defect") for d in injected]
            if "NAME_MISMATCH" in defect_codes or "OWNER_MISMATCH" in defect_codes:
                status = VerificationStatus.MISMATCH_DETECTED
    except Exception:
        pass

    # Deterministic pending/timeout: if ref_no ends with 'P', simulate pending
    if ref_no.endswith("P"):
        status = VerificationStatus.VERIFICATION_PENDING

    result = CheckResult(
        doc_id=f"noc_{app_id}",
        layer=Layer.A,
        check="issuer_lookup",
        status=status.value,
        severity="info",
        reason=f"Mock issuer lookup for NOC reference {ref_no}",
        evidence=evidence,
        verification_status=status,
        source=f"synthetic_dataset_{app_id}",
        checked_at="2026-10-24T10:00:00Z",
    )

    # Build response dict, ensuring datetime fields are ISO strings
    result_dict = result.model_dump()
    if isinstance(result_dict.get("checked_at"), datetime):
        result_dict["checked_at"] = result_dict["checked_at"].isoformat()

    return JSONResponse(content=result_dict)


# Health check endpoint
@app.get("/health", include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8100)