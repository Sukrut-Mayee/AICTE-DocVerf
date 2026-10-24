# AICTE DocVerf

Decision-support layer for AICTE Extension-of-Approval applications: provenance checks, extraction,
cross-document reasoning, forensics, and a hash-chained audit log anchored on a blockchain.
**It never approves or rejects; an officer decides.** Docs: [`docs/PRD.md`](docs/PRD.md) (what/why),
[`docs/TRD.md`](docs/TRD.md) (how; the technical source of truth).

## Status: scaffold
| Real code | Stubs (typed signatures, raise `NotImplementedError`) | Empty placeholders |
|---|---|---|
| `packages/docverf/schemas` (TRD §5), `packages/docverf/config.py` (TRD §15), `rules/` YAML, `tests/fixtures` | every other `packages/docverf/*` module and its `__main__` CLI, `eval/` | `services/*`, `blockchain/`, `apps/*`, `infra/docker-compose.yml` |

## Setup (Python 3.11 with uv)
The project targets **Python 3.11**. Use [uv](https://docs.astral.sh/uv/) so everyone gets the same
interpreter without touching the system Python.

```bash
# 1. install uv (any one of these)
pip install --user uv            # or: curl -LsSf https://astral.sh/uv/install.sh | sh
#    Windows PowerShell:  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. get Python 3.11 and a venv
uv python install 3.11
uv venv --python 3.11 .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. install the package and the groups you need (see requirements/)
uv pip install -e . -r requirements/dev.txt
uv pip install -r requirements/reasoning.txt        # add your module's group

cp .env.example .env             # then edit; .env is gitignored
pytest -m "not slow"
```
`make setup` installs every group except the OCR engines. Versions in `requirements/*.txt` are not pinned yet.

**Windows.** Prefer **WSL2** (Ubuntu) for extraction, provenance and synthetic work: PaddleOCR,
WeasyPrint and ExifTool are painful natively (TRD §3). Playwright works natively. If the repo sits on
`/mnt/c` and you use both WSL and Windows, give each its own venv (e.g. `.venv` and `.venv-win`):
a Linux venv cannot be used from Windows.
**System packages:** `exiftool` (pyexiftool) and `libzbar0` (pyzbar fallback) for provenance.
**OCR engines** are separate files because their dependency stacks conflict: install either
`requirements/extraction-paddle.txt` or `requirements/extraction-surya.txt`, in its own venv, matching `OCR_ENGINE`.

## Running a module on its own
Every module has a CLI that reads a file or folder and writes schema-valid JSON to `data/out/<module>/`
(currently they raise `NotImplementedError`):
```bash
python -m docverf.provenance  data/synthetic/app001/noc.pdf
python -m docverf.extraction  data/synthetic/app001/
python -m docverf.forensics   data/synthetic/app001/
python -m docverf.reasoning   tests/fixtures/apps/app_conflict/     # runs on ExtractionResult JSON, no OCR
python -m docverf.verification | ledger  <path>
python -m docverf.synthetic --out data/synthetic --n 20      # needs Chrome or Edge for the PDFs
python -m eval data/synthetic
```

## Starting work on your module (TRD §18)
1. Read `docs/TRD.md` §1 and §5, plus the section for your module (e.g. §10 extraction, §8 reasoning).
2. Work only in your module and its test (`tests/test_<module>.py`). Replace the placeholder test and the
   `NotImplementedError` bodies. Do not change schemas; if a contract is unclear, leave `TODO(question):`.
3. Develop against `tests/fixtures/apps/app_conflict` and `app_clean` (TRD Appendix A) until synthetic data exists.
4. Add any new dependency to your `requirements/<group>.txt` and mention it in the PR.
5. `ruff check . && pytest -m "not slow"` before pushing. **Never run `ruff format` on `docs/`**
   (it is excluded in `pyproject.toml`; ruff would reformat Python blocks inside the TRD).

## Not done yet (scaffold scope)
Pinned versions, Docker Compose stack (Postgres, Redis, MinIO, MailHog, Besu), FastAPI / Celery / mock-issuer
code, Next.js app, Hardhat project and `AuditAnchor.sol`, pre-commit, GitHub Actions CI.
