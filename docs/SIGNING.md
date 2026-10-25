# Document Signing Workflow Guide (TRD §9.1, §13.1, §13.2)

This guide documents the reproducible signing workflow, mock CA setup, explicit tampering workflow for `app018`, and signature verification.

> [!IMPORTANT]
> **Safety Notice:**
> - Never sign, regenerate, or modify documents in the canonical dataset repository directly.
> - Always perform signing on a dedicated dataset copy (e.g. `data/synthetic_signed_copy`).
> - **Never regenerate PDFs after signing**: generating or converting HTML to PDF after signing overwrites the PDF and wipes out the digital signature dictionary. Signing must always be the final step on existing rendered PDFs.
> - Private keys (`*.key`) and certificates (`*.pem`) are gitignored; never commit secrets.

---

## 1. Prerequisites

Ensure Python dependencies are installed in your virtual environment:

```bash
uv pip install -r requirements/provenance.txt
```

This installs `pyhanko`, `cryptography`, `asn1crypto`, `pymupdf`, and associated cryptographic tools.

---

## 2. Configuration & Mock CA

The mock CA configuration lives in [`infra/pki/ca_config.json`](file:///infra/pki/ca_config.json):
- **CA Common Name**: `Mock Fire Dept CA`
- **Signer Common Name**: `Mock Fire Dept Signer`
- **Validity**: 365 days
- **Trust Directory**: `infra/pki/trust_roots`
- **Target Files**:
  - `infra/pki/trust_roots/mock_fire_ca.pem` (Root CA cert, loaded by `check_pdf_signature`)
  - `infra/pki/ca.key` (CA private key, gitignored)
  - `infra/pki/signer.pem` (Signer leaf certificate, gitignored)
  - `infra/pki/signer.key` (Signer private key, gitignored)

To generate the mock CA and signing credentials, run:

```bash
python scripts/sign_documents.py init-ca
```

Output:
- Places `mock_fire_ca.pem` inside `infra/pki/trust_roots/` where the provenance engine loads it via `TRUST_ROOTS_DIR`.
- Saves private keys with restricted permissions (`0600`).

---

## 3. Dataset Signing Workflow

### Step 3.1: Prepare your Dataset Copy

Create a working copy of the dataset so the original remains unmodified:

```bash
# Example copy (PowerShell)
Copy-Item -Recurse data/synthetic_dataset data/synthetic_signed_copy
```

### Step 3.2: Sign Target Documents

Run the signing script on your dataset copy. By default, this signs `noc.pdf` for all clean applications (`app001` through `app008`) and the clean target document for `app018`:

```bash
python scripts/sign_documents.py sign-dataset --data-dir data/synthetic_signed_copy
```

*Optional flags:*
- `--target-doc <filename>`: default is `noc.pdf`
- `--apps app001 app002 app018`: specify subset of applications
- `--out-dir <path>`: write signed outputs to a separate destination rather than in-place

### Step 3.3: Separate Explicit Step — Tamper app018

`app018` represents the `SIGNED_THEN_EDITED` defect (TRD §13.2).
After signing the clean `noc.pdf` in Step 3.2, tamper it as an explicit, separate action:

```bash
python scripts/sign_documents.py tamper-app --data-dir data/synthetic_signed_copy --app app018
```

This modifies bytes within the signed byte range and immediately verifies that `check_pdf_signature` reports `CheckStatus.MISMATCH` and `intact=False`.

---

## 4. Verification

Verify any signed or tampered document:

```bash
# Verify a clean signed application:
python scripts/sign_documents.py verify data/synthetic_signed_copy/app001/noc.pdf
# -> Status: verified, Verification Status: verified, intact: True, trusted: True

# Verify the tampered application:
python scripts/sign_documents.py verify data/synthetic_signed_copy/app018/noc.pdf
# -> Status: mismatch, Verification Status: mismatch_detected, intact: False
```

Or verify directly in Python:
```python
from docverf.provenance.pdf_signature import check_pdf_signature

res = check_pdf_signature("data/synthetic_signed_copy/app001/noc.pdf", "app001_noc")
assert res.status.value == "verified"
```
