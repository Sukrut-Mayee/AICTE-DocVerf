# AICTE DocVerf: agent guide

Read before coding: **docs/TRD.md §1** (rules for AI coding agents) and **§5** (frozen data contracts).
`docs/PRD.md` says what and why; the TRD says how. If they conflict, or something is missing,
leave a `TODO(question):` comment and tell the human. Do not invent contracts or parameter values.

Key rules (full list in TRD §1): schemas in `packages/docverf/schemas/` are frozen; stay inside
your module; lean code; no silent new dependencies (add to `requirements/*.txt`); config via
`docverf.config`; never call external AI APIs unless `ALLOW_CLOUD_AI=true`; never write
"forged" or "fake" (use "suspicious", "conflict", "preliminary indicator").

## Module ownership (TRD §18)
| Owner | Module |
|---|---|
| Lead (Sukrut) | repo, schemas, config, api, worker DAG, integration |
| Person A | `synthetic/`, `services/mock_issuer` |
| Person B | `extraction/` |
| Person C | `provenance/`, `forensics/`, `ledger/`, `blockchain/` |
| Person D | `reasoning/` (rule engine + graph checks first) |
| Later | `apps/web`, digital twin, impact sim UI, eval |

## Commands (Python 3.11 via uv, see README)
```
pytest -m "not slow"          # tests
ruff check . && ruff format --check .   # lint (docs/ is excluded on purpose)
mypy packages                 # types (lenient)
python -m docverf.<module> <path> [--out data/out/<module>]
#   <module> = provenance | extraction | forensics | reasoning | verification | ledger | synthetic
python -m eval <synthetic_dir>
```
Do not run `ruff format` on `docs/`: ruff reformats Python blocks inside Markdown and would alter the TRD.
