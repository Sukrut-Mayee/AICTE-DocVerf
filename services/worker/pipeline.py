"""Live pipeline (TRD §7): every application end to end, written as contract-B JSON.

    python -m services.worker.pipeline data/synthetic --out data/out/pipeline [--apps app009,app017]

Per application, in app-id order, with one duplicate HashIndex shared across applications:
provenance -> extraction -> forensics -> issuer lookup -> run_reasoning + aggregate -> audit log
(+ anchor when a node is configured and reachable) -> <out>/appNNN.json, validated with the
officer API's PipelineRepository before it replaces the old file. One application failing is
logged and the run continues; the exit code is 1 if any failed.

Documents are listed by the `documents` manifest in each ground_truth.json (doc_id, doc_type,
path, TRD §13.1). `true_fields` and `injected_defects` are never read.

Extraction adapter (no change to docverf.extraction): digital PDF pages feed their text-layer
word boxes to the rules extractor; only pages without a text layer go through OCR (`run_ocr`,
engine per OCR_ENGINE). Lab photos use the real `extract()`. The path each document took is in
`meta.extraction`.

Needs: the mock issuer (started here if MOCK_ISSUER_URL is not answering) and the ledger database
(DATABASE_URL; for local dev `DATABASE_URL=sqlite:///data/ledger.db`).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import fitz  # PyMuPDF
import httpx
from docverf.config import get_settings
from docverf.extraction import vlm
from docverf.extraction.extract import _merge_fields, extract
from docverf.extraction.layout import detect_regions
from docverf.extraction.ocr import run_ocr
from docverf.extraction.rules_extractor import rules_extract
from docverf.forensics.ai_gen import ai_gen
from docverf.forensics.copy_move import detect_copy_move
from docverf.forensics.ela import run_ela
from docverf.forensics.noise import noise_inconsistency
from docverf.ledger.anchor import anchor_root
from docverf.ledger.audit_log import AuditLog
from docverf.provenance.duplicates import HashIndex, check_duplicates
from docverf.provenance.hashing import hash_file
from docverf.provenance.metadata import extract_metadata
from docverf.provenance.pdf_signature import check_pdf_signature
from docverf.provenance.qr import decode_qr
from docverf.reasoning.cross_institution import check_cross_institution, load_prior
from docverf.reasoning.run import aggregate, run_reasoning
from docverf.schemas import (
    CheckResult,
    CheckStatus,
    DocType,
    ExtractionResult,
    GroundTruthDoc,
    Region,
)
from docverf.verification import lookup

from services.api.pipeline import PipelineRepository

logger = logging.getLogger("pipeline")

RENDER_DPI = 150  # the synthetic scans are embedded at ~150 DPI; rendering higher only upscales
ISSUER_START_WAIT_S = 20


def _manifest(app_dir: Path) -> list[GroundTruthDoc]:
    raw = json.loads((app_dir / "ground_truth.json").read_text("utf-8"))
    return [GroundTruthDoc.model_validate(d) for d in raw["documents"]]


def _add_to_index(index: HashIndex, app_id: str, doc_id: str, hashes: dict[str, str]) -> None:
    for value in filter(None, hashes.values()):  # PDFs have no pHash: hash_file gives ""
        index.setdefault(value, []).append((app_id, doc_id))


def _render(pdf: Path, out_dir: Path, doc_id: str) -> list[tuple[int, Path, bool]]:
    """(1-based page, PNG path, page has a text layer) for every page."""
    pages = []
    with fitz.open(pdf) as doc:
        for n, page in enumerate(doc, 1):
            img = out_dir / f"{doc_id}_p{n}.png"
            page.get_pixmap(dpi=RENDER_DPI).save(img)
            pages.append((n, img, bool(page.get_text().strip())))
    return pages


def _text_layer_words(pdf: Path, page_no: int) -> list[dict[str, Any]]:
    """Word boxes in run_ocr's shape (text, confidence, bbox 0..1 top-left) from the text layer."""
    with fitz.open(pdf) as doc:
        page = doc[page_no - 1]
        w, h = page.rect.width, page.rect.height
        return [
            {
                "text": text,
                "confidence": 1.0,
                "bbox": [max(0.0, x0 / w), max(0.0, y0 / h), min(1.0, x1 / w), min(1.0, y1 / h)],
                "page": page_no,
            }
            for x0, y0, x1, y1, text, *_ in page.get_text("words")
        ]


def _vlm_status() -> dict[str, Any]:
    """Whether Ollama answers and has the VLM model; probed once per run."""
    settings, model = get_settings(), vlm._model_name()
    try:
        tags = httpx.get(f"{settings.OLLAMA_URL.rstrip('/')}/api/tags", timeout=3).json()
    except (httpx.HTTPError, ValueError) as exc:
        return {"available": False, "model": model, "reason": f"Ollama unreachable: {exc}"}
    names = {m.get("name") for m in tags.get("models", [])}
    if model not in names:
        return {"available": False, "model": model, "reason": "model not pulled in Ollama"}
    return {"available": True, "model": model}


def _extract_pdf(
    path: Path, doc: GroundTruthDoc, app_id: str, pages: list[tuple[int, Path, bool]], vlm_ok: bool
) -> tuple[ExtractionResult, str]:
    """The adapter: text layer (or OCR for pages without one) -> rules extractor [-> VLM merge]."""
    words: list[dict[str, Any]] = []
    regions: list[Region] = []
    warnings: list[str] = []
    engines: dict[str, str] = {}
    ocr_engine = get_settings().OCR_ENGINE
    for n, img, has_text in pages:
        if has_text:
            words += _text_layer_words(path, n)
            engines["text"] = "pymupdf_text_layer"
        else:
            try:
                words += [{**w, "page": n} for w in run_ocr(img)]
                engines["ocr"] = ocr_engine
            except ImportError as exc:
                warnings.append(f"page {n}: OCR engine '{ocr_engine}' not installed: {exc}")
        regions += [r.model_copy(update={"page": n}) for r in detect_regions(img)]
    fields = rules_extract(words, doc.doc_type)
    if vlm_ok:
        try:
            fields = _merge_fields(fields, vlm.vlm_extract(pages[0][1], doc.doc_type))
            engines["vlm"] = vlm._model_name()
        except (ConnectionError, ValueError) as exc:
            warnings.append(f"VLM extraction failed: {exc}")
    else:
        warnings.append("VLM unavailable: rules extractor only, agreement factor not applied")
    text_pages = sum(has_text for _, _, has_text in pages)
    route = {len(pages): "text_layer", 0: "ocr"}.get(text_pages, "text_layer+ocr")
    result = ExtractionResult(
        doc_id=doc.doc_id,
        app_id=app_id,
        doc_type=doc.doc_type,
        fields=fields,
        regions=regions,
        page_count=len(pages),
        engines=engines,
        warnings=warnings,
    )
    return result, route


def _forensics(doc_id: str, image: Path, regions: list[Region]) -> list[CheckResult]:
    return [
        run_ela(str(image), doc_id, regions),
        detect_copy_move(str(image), doc_id, regions),
        noise_inconsistency(str(image), doc_id, regions),
        ai_gen(str(image), doc_id),
    ]


class Run:
    """State shared across applications: the duplicate index, the audit log, run-level meta."""

    def __init__(self, synthetic_dir: Path, out_dir: Path, issuer: dict[str, Any]) -> None:
        self.synthetic_dir, self.out_dir = synthetic_dir, out_dir
        self.index: HashIndex = {}
        self.audit = AuditLog()
        self.vlm = _vlm_status()
        self.issuer = issuer

    def index_only(self, app_id: str) -> None:
        """Hash an earlier application that is not being processed, so duplicates still match."""
        app_dir = self.synthetic_dir / app_id
        for doc in _manifest(app_dir):
            path = app_dir / doc.path
            _add_to_index(self.index, app_id, doc.doc_id, hash_file(str(path)))

    def process(self, app_id: str) -> dict[str, float]:
        app_dir = self.synthetic_dir / app_id
        docs = _manifest(app_dir)
        timing: dict[str, float] = {}
        start = time.perf_counter()

        @contextmanager
        def stage(name: str) -> Iterator[None]:
            t = time.perf_counter()
            yield
            timing[name] = round(time.perf_counter() - t, 2)

        checks: list[CheckResult] = []
        extractions: list[ExtractionResult] = []
        routes: dict[str, str] = {}
        with tempfile.TemporaryDirectory(prefix=f"docverf-{app_id}-") as tmp:
            pages: dict[str, list[tuple[int, Path, bool]]] = {}
            with stage("provenance"):
                for doc in docs:
                    path = app_dir / doc.path
                    hashes = hash_file(str(path))
                    checks += check_duplicates(app_id, doc.doc_id, hashes, self.index)
                    _add_to_index(self.index, app_id, doc.doc_id, hashes)
                    if doc.doc_type is DocType.APPLICATION_FORM:
                        continue  # structured portal data: hashed only
                    if path.suffix.lower() == ".pdf":
                        pages[doc.doc_id] = _render(path, Path(tmp), doc.doc_id)
                        checks.append(check_pdf_signature(str(path), doc.doc_id))
                        qr_image = pages[doc.doc_id][0][1]  # decode_qr cannot open a PDF
                    else:
                        qr_image = path
                    checks.append(extract_metadata(str(path), doc.doc_id))
                    checks.append(decode_qr(str(qr_image), doc.doc_id))

            with stage("extraction"):
                for doc in docs:
                    path = app_dir / doc.path
                    if doc.doc_type is DocType.APPLICATION_FORM:
                        extraction = ExtractionResult.model_validate_json(path.read_text("utf-8"))
                        route = "portal_json"
                    elif doc.doc_id in pages:
                        extraction, route = _extract_pdf(
                            path, doc, app_id, pages[doc.doc_id], self.vlm["available"]
                        )
                    else:
                        extraction = extract(str(path), doc.doc_id, app_id, doc.doc_type)
                        route = "extract"
                    extractions.append(extraction)
                    routes[doc.doc_id] = route

            with stage("forensics"):
                verified = {
                    c.doc_id
                    for c in checks
                    if c.check == "pdf_signature" and c.status is CheckStatus.VERIFIED
                }
                for e in extractions:
                    if e.doc_id in verified:
                        continue
                    if e.doc_type is DocType.LAB_PHOTO:
                        image = app_dir / next(d.path for d in docs if d.doc_id == e.doc_id)
                        checks += _forensics(e.doc_id, image, e.regions)
                    for n, img, has_text in pages.get(e.doc_id, []):
                        if not has_text:  # a scanned page
                            on_page = [r for r in e.regions if r.page == n]
                            checks += _forensics(e.doc_id, img, on_page)

        with stage("issuer"):
            checks += [lookup(e) for e in extractions if e.doc_type is DocType.NOC]

        with stage("reasoning"):
            findings = run_reasoning(app_id, extractions, checks)
            # after the per-application rules: the earlier applications' outputs are on disk
            findings += check_cross_institution(
                app_id, extractions, load_prior(self.out_dir, app_id)
            )
            documents, priority = aggregate(
                app_id, findings, checks, doc_ids=[d.doc_id for d in docs]
            )

        meta: dict[str, Any] = {
            "source": "pipeline",
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "extraction": routes,
            "ocr_engine": get_settings().OCR_ENGINE,
            "vlm": self.vlm,
            "issuer": self.issuer,
        }
        with stage("audit"):
            audit = self._audit(app_id, checks, findings, meta)

        timing["total"] = round(time.perf_counter() - start, 2)
        meta["timing_s"] = timing
        output = {
            "app_id": app_id,
            "extractions": [e.model_dump(mode="json") for e in extractions],
            "checks": [c.model_dump(mode="json") for c in checks],
            "findings": [f.model_dump(mode="json") for f in findings],
            "documents": [d.model_dump(mode="json") for d in documents],
            "priority": priority,
            "audit": audit,
            "meta": meta,
        }
        self._write(app_id, output)
        return timing

    def _audit(
        self, app_id: str, checks: list[CheckResult], findings: list[Any], meta: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Append every check and finding to the hash chain; anchor the head if possible."""
        try:
            entries = [
                self.audit.append("check_result", {"app_id": app_id, **c.model_dump(mode="json")})
                for c in checks
            ] + [
                self.audit.append(
                    "finding_created", {"app_id": app_id, **f.model_dump(mode="json")}
                )
                for f in findings
            ]
        except Exception as exc:  # ledger unreachable: the application is still reported
            meta["audit_error"] = f"{type(exc).__name__}: {exc}"
            return None
        if not entries:
            return None
        head = entries[-1]
        try:
            tx: str | None = anchor_root(head.seq, head.hash)
            meta["anchor"] = {"anchored": True}
        except Exception as exc:  # never a made-up transaction hash
            tx = None
            meta["anchor"] = {"anchored": False, "reason": str(exc)}
        return {"seq": head.seq, "hash": head.hash, "tx": tx}

    def _write(self, app_id: str, output: dict[str, Any]) -> None:
        """Stage, validate with the officer API's loader, then replace the old file."""
        staging = self.out_dir / ".staging"
        staging.mkdir(parents=True, exist_ok=True)
        staged = staging / f"{app_id}.json"
        staged.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            PipelineRepository(staging).load(app_id)
        except Exception:
            staged.unlink(missing_ok=True)
            raise
        os.replace(staged, self.out_dir / f"{app_id}.json")


def _issuer_up(url: str) -> bool:
    try:
        return httpx.get(f"{url.rstrip('/')}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def start_issuer(synthetic_dir: Path) -> tuple[subprocess.Popen[bytes] | None, dict[str, Any]]:
    """Start services/mock_issuer on MOCK_ISSUER_URL's port unless something already answers."""
    url = get_settings().MOCK_ISSUER_URL
    if _issuer_up(url):
        return None, {"url": url, "reachable": True, "started_by_pipeline": False}
    port = str(urlparse(url).port or 8100)
    cmd = [sys.executable, "-m", "uvicorn", "services.mock_issuer.main:app", "--port", port]
    env = {**os.environ, "MOCK_ISSUER_DATASET_DIR": str(synthetic_dir.resolve())}
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + ISSUER_START_WAIT_S
    while time.monotonic() < deadline and proc.poll() is None:
        if _issuer_up(url):
            return proc, {"url": url, "reachable": True, "started_by_pipeline": True}
        time.sleep(0.5)
    proc.terminate()
    return None, {"url": url, "reachable": False, "started_by_pipeline": False}


def run(
    synthetic_dir: Path,
    out_dir: Path,
    apps: list[str] | None = None,
    issuer: dict[str, Any] | None = None,
) -> int:
    """Process `apps` (default: all) in app-id order. Returns the number of failed applications."""
    all_apps = sorted(p.parent.name for p in synthetic_dir.glob("app*/ground_truth.json"))
    unknown = sorted(set(apps or []) - set(all_apps))
    if unknown:
        raise SystemExit(f"unknown application(s): {', '.join(unknown)}")
    selected = set(apps or all_apps)
    out_dir.mkdir(parents=True, exist_ok=True)
    state = Run(synthetic_dir, out_dir, issuer or {"started_by_pipeline": False})
    if not state.vlm["available"]:
        print(f"VLM off ({state.vlm['reason']}): running without it")

    failed = []
    for app_id in [a for a in all_apps if a <= max(selected)]:
        if app_id not in selected:
            state.index_only(app_id)
            continue
        try:
            timing = state.process(app_id)
        except Exception:
            failed.append(app_id)
            logger.error("%s failed:\n%s", app_id, traceback.format_exc())
            print(f"{app_id}  FAILED")
            continue
        stages = "  ".join(f"{k} {v:.1f}s" for k, v in timing.items() if k != "total")
        print(f"{app_id}  {timing['total']:6.1f}s  ({stages})")
    try:
        (out_dir / ".staging").rmdir()
    except OSError:
        pass
    print(f"{len(selected) - len(failed)}/{len(selected)} applications written to {out_dir}")
    return len(failed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m services.worker.pipeline", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("synthetic_dir", type=Path, help="folder of appNNN/ application folders")
    parser.add_argument("--out", type=Path, default=Path("data/out/pipeline"))
    parser.add_argument("--apps", help="comma-separated subset, e.g. app009,app017")
    args = parser.parse_args(argv)
    if not args.synthetic_dir.is_dir():
        parser.error(f"not a folder: {args.synthetic_dir}")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    apps = [a.strip() for a in args.apps.split(",") if a.strip()] if args.apps else None

    proc, issuer = start_issuer(args.synthetic_dir)
    if not issuer["reachable"]:
        print(f"mock issuer not reachable at {issuer['url']}: lookups will be source_unavailable")
    try:
        failed = run(args.synthetic_dir, args.out, apps, issuer)
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait(timeout=10)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
