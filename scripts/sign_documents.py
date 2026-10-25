#!/usr/bin/env python3
"""Reproducible PDF document signing CLI (TRD §9.1, §13.1, §13.2).

Usage:
  # 1. Initialize Mock CA & Signer (generates infra/pki credentials):
  python scripts/sign_documents.py init-ca

  # 2. Sign target documents across a dataset copy (clean apps + app018):
  python scripts/sign_documents.py sign-dataset --data-dir path/to/dataset_copy

  # 3. Explicit separate step: tamper app018 to simulate SIGNED_THEN_EDITED defect:
  python scripts/sign_documents.py tamper-app --data-dir path/to/dataset_copy --app app018

  # 4. Verify any PDF signature:
  python scripts/sign_documents.py verify path/to/dataset_copy/app001/noc.pdf
  python scripts/sign_documents.py verify path/to/dataset_copy/app018/noc.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root to sys.path so docverf package is importable when executed as a script
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from docverf.provenance.pdf_signature import check_pdf_signature  # noqa: E402
from docverf.provenance.signing import (  # noqa: E402
    CAConfig,
    generate_mock_ca,
    sign_dataset,
    sign_pdf_file,
    tamper_app_document,
    tamper_pdf_file,
)
from docverf.schemas import CheckStatus  # noqa: E402


def cmd_init_ca(args: argparse.Namespace) -> int:
    config = CAConfig.load(args.config)
    paths = generate_mock_ca(config=config, base_dir=args.ca_dir)
    print("Mock CA and Signer credentials generated successfully:")
    for k, v in paths.items():
        print(f"  {k}: {v}")
    print(f"\nRoot CA placed in trust directory: {paths['trust_roots_dir']}")
    return 0


def cmd_sign_file(args: argparse.Namespace) -> int:
    out_path = args.out or Path(args.input).with_suffix(".signed.pdf")
    sign_pdf_file(
        input_path=args.input,
        output_path=out_path,
        cert_path=args.cert,
        key_path=args.key,
    )
    print(f"Signed PDF created at: {out_path}")
    return 0


def cmd_sign_dataset(args: argparse.Namespace) -> int:
    signed = sign_dataset(
        dataset_dir=args.data_dir,
        cert_path=args.cert,
        key_path=args.key,
        target_doc=args.target_doc,
        apps=args.apps,
        out_dir=args.out_dir,
    )
    print(f"Successfully signed {len(signed)} application document(s):")
    for p in signed:
        print(f"  {p}")
    return 0


def cmd_tamper_file(args: argparse.Namespace) -> int:
    out_path = tamper_pdf_file(args.input, args.out)
    print(f"Tampered PDF created at: {out_path}")
    return 0


def cmd_tamper_app(args: argparse.Namespace) -> int:
    out_path = tamper_app_document(
        dataset_dir=args.data_dir,
        app_id=args.app,
        target_doc=args.target_doc,
    )
    print(f"Explicit tampering step completed for {args.app}:")
    print(f"  Tampered target document: {out_path}")
    result = check_pdf_signature(str(out_path), f"{args.app}_{Path(args.target_doc).stem}")
    intact = result.evidence.get("intact")
    print(f"  Verification check confirms: {result.status.value} (intact={intact})")
    return 0 if result.status == CheckStatus.MISMATCH else 1


def cmd_verify(args: argparse.Namespace) -> int:
    doc_id = args.doc_id or Path(args.path).stem
    result = check_pdf_signature(args.path, doc_id)
    vs = result.verification_status.value if result.verification_status else None
    print(f"Verification result for {args.path}:")
    print(f"  Check: {result.check}")
    print(f"  Status: {result.status.value}")
    print(f"  Severity: {result.severity.value}")
    print(f"  Verification Status: {vs}")
    print(f"  Reason: {result.reason}")
    print(f"  Evidence: {result.evidence}")
    return 0 if result.status == CheckStatus.VERIFIED else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/sign_documents.py",
        description="Reproducible PDF document signing and mock CA workflow",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-ca
    p_init = subparsers.add_parser("init-ca", help="Initialize mock CA and signer credentials")
    p_init.add_argument("--config", type=Path, default=Path("infra/pki/ca_config.json"))
    p_init.add_argument("--ca-dir", type=Path, default=Path("infra/pki"))
    p_init.set_defaults(func=cmd_init_ca)

    # sign-file
    p_sign_f = subparsers.add_parser("sign-file", help="Sign an individual PDF")
    p_sign_f.add_argument("input", type=Path, help="Input PDF file path")
    p_sign_f.add_argument("--out", type=Path, default=None, help="Output PDF file path")
    p_sign_f.add_argument("--cert", type=Path, default=Path("infra/pki/signer.pem"))
    p_sign_f.add_argument("--key", type=Path, default=Path("infra/pki/signer.key"))
    p_sign_f.set_defaults(func=cmd_sign_file)

    # sign-dataset
    p_sign_d = subparsers.add_parser("sign-dataset", help="Sign documents across a dataset copy")
    p_sign_d.add_argument("--data-dir", type=Path, required=True, help="Dataset copy directory")
    p_sign_d.add_argument(
        "--out-dir", type=Path, default=None, help="Optional separate output directory"
    )
    p_sign_d.add_argument(
        "--target-doc", type=str, default="noc.pdf", help="Target document filename"
    )
    p_sign_d.add_argument(
        "--apps", nargs="+", default=None, help="Specific application IDs to sign"
    )
    p_sign_d.add_argument("--cert", type=Path, default=Path("infra/pki/signer.pem"))
    p_sign_d.add_argument("--key", type=Path, default=Path("infra/pki/signer.key"))
    p_sign_d.set_defaults(func=cmd_sign_dataset)

    # tamper-file
    p_tamp_f = subparsers.add_parser(
        "tamper-file", help="Tamper a signed PDF in-place or to a new file"
    )
    p_tamp_f.add_argument("input", type=Path, help="Signed PDF file path")
    p_tamp_f.add_argument("--out", type=Path, default=None, help="Output tampered PDF file path")
    p_tamp_f.set_defaults(func=cmd_tamper_file)

    # tamper-app
    p_tamp_a = subparsers.add_parser(
        "tamper-app",
        help="Explicit step: tamper a specific signed application document",
    )
    p_tamp_a.add_argument("--data-dir", type=Path, required=True, help="Dataset copy directory")
    p_tamp_a.add_argument(
        "--app", type=str, default="app018", help="Target application ID (default: app018)"
    )
    p_tamp_a.add_argument(
        "--target-doc", type=str, default="noc.pdf", help="Target document filename"
    )
    p_tamp_a.set_defaults(func=cmd_tamper_app)

    # verify
    p_ver = subparsers.add_parser("verify", help="Verify a PDF signature with check_pdf_signature")
    p_ver.add_argument("path", type=str, help="PDF file path to verify")
    p_ver.add_argument("--doc-id", type=str, default=None, help="Document ID for the check result")
    p_ver.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
