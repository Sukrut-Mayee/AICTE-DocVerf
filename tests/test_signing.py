"""Focused tests for the reproducible document signing workflow and mock CA (TRD §9.1, §13.2)."""

from pathlib import Path

import fitz
from cryptography import x509
from docverf.config import get_settings
from docverf.provenance.pdf_signature import check_pdf_signature
from docverf.provenance.signing import (
    CAConfig,
    generate_mock_ca,
    sign_dataset,
    sign_pdf_file,
    tamper_app_document,
    tamper_pdf_file,
)
from docverf.schemas import CheckStatus, VerificationStatus

from scripts.sign_documents import main as cli_main


def _create_sample_pdf(path: Path, title: str = "Test PDF Document") -> Path:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), title, fontsize=14)
    page.insert_text((72, 120), "Sample content for cryptographic signature testing.")
    doc.save(str(path))
    doc.close()
    return path


def test_ca_config_and_generation(tmp_path):
    pki_dir = tmp_path / "pki"
    config = CAConfig(
        ca_common_name="Test Mock CA",
        ca_organization="Test Org",
        signer_common_name="Test Signer",
        signer_organization="Test Org",
        key_size=2048,
        validity_days=30,
    )
    paths = generate_mock_ca(config=config, base_dir=pki_dir)

    assert paths["ca_key"].is_file()
    assert paths["ca_cert"].is_file()
    assert paths["signer_key"].is_file()
    assert paths["signer_cert"].is_file()

    ca_cert = x509.load_pem_x509_certificate(paths["ca_cert"].read_bytes())
    ca_cn = ca_cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value
    assert ca_cn == "Test Mock CA"

    signer_cert = x509.load_pem_x509_certificate(paths["signer_cert"].read_bytes())
    signer_cn = signer_cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value
    assert signer_cn == "Test Signer"


def test_sign_pdf_file_and_verify(tmp_path, monkeypatch):
    pki_dir = tmp_path / "pki"
    paths = generate_mock_ca(base_dir=pki_dir)

    monkeypatch.setenv("TRUST_ROOTS_DIR", str(paths["trust_roots_dir"]))
    get_settings.cache_clear()

    input_pdf = _create_sample_pdf(tmp_path / "unsigned.pdf")
    output_pdf = tmp_path / "signed.pdf"

    sign_pdf_file(
        input_path=input_pdf,
        output_path=output_pdf,
        cert_path=paths["signer_cert"],
        key_path=paths["signer_key"],
    )
    assert output_pdf.is_file()

    result = check_pdf_signature(str(output_pdf), "doc001")
    assert result.status == CheckStatus.VERIFIED
    assert result.verification_status == VerificationStatus.VERIFIED
    assert result.evidence["intact"] is True
    assert result.evidence["valid"] is True
    assert result.evidence["trusted"] is True


def test_tamper_pdf_detected(tmp_path, monkeypatch):
    pki_dir = tmp_path / "pki"
    paths = generate_mock_ca(base_dir=pki_dir)

    monkeypatch.setenv("TRUST_ROOTS_DIR", str(paths["trust_roots_dir"]))
    get_settings.cache_clear()

    input_pdf = _create_sample_pdf(tmp_path / "doc.pdf")
    signed_pdf = tmp_path / "doc_signed.pdf"
    tampered_pdf = tmp_path / "doc_tampered.pdf"

    sign_pdf_file(input_pdf, signed_pdf, paths["signer_cert"], paths["signer_key"])

    tamper_pdf_file(signed_pdf, tampered_pdf)
    assert tampered_pdf.is_file()

    result = check_pdf_signature(str(tampered_pdf), "doc001")
    assert result.status == CheckStatus.MISMATCH
    assert result.verification_status == VerificationStatus.MISMATCH_DETECTED
    assert result.evidence["intact"] is False
    assert "document modified after signing" in result.evidence.get("failure_reasons", [])


def test_app018_separate_tamper_workflow(tmp_path, monkeypatch):
    """Explicit workflow: sign dataset first, then explicitly tamper app018."""
    pki_dir = tmp_path / "pki"
    paths = generate_mock_ca(base_dir=pki_dir)
    monkeypatch.setenv("TRUST_ROOTS_DIR", str(paths["trust_roots_dir"]))
    get_settings.cache_clear()

    # Create mock dataset copy with app001 (clean) and app018 (target for SIGNED_THEN_EDITED)
    dataset_dir = tmp_path / "dataset_copy"
    (dataset_dir / "app001").mkdir(parents=True)
    (dataset_dir / "app018").mkdir(parents=True)

    _create_sample_pdf(dataset_dir / "app001" / "noc.pdf", "app001 Clean NOC")
    _create_sample_pdf(dataset_dir / "app018" / "noc.pdf", "app018 Clean NOC before tamper")

    # Step 1: Sign clean documents in dataset
    signed = sign_dataset(
        dataset_dir=dataset_dir,
        cert_path=paths["signer_cert"],
        key_path=paths["signer_key"],
        apps=["app001", "app018"],
    )
    assert len(signed) == 2

    # Verify both are initially verified
    res1 = check_pdf_signature(str(dataset_dir / "app001" / "noc.pdf"), "app001_noc")
    res18_pre = check_pdf_signature(str(dataset_dir / "app018" / "noc.pdf"), "app018_noc")
    assert res1.status == CheckStatus.VERIFIED
    assert res18_pre.status == CheckStatus.VERIFIED

    # Step 2: Explicit separate step — tamper app018
    tampered_path = tamper_app_document(dataset_dir, app_id="app018", target_doc="noc.pdf")
    assert tampered_path == dataset_dir / "app018" / "noc.pdf"

    # app001 remains intact and verified
    res1_after = check_pdf_signature(str(dataset_dir / "app001" / "noc.pdf"), "app001_noc")
    assert res1_after.status == CheckStatus.VERIFIED
    assert res1_after.evidence["intact"] is True

    # app018 is now detected as tampered
    res18_post = check_pdf_signature(str(dataset_dir / "app018" / "noc.pdf"), "app018_noc")
    assert res18_post.status == CheckStatus.MISMATCH
    assert res18_post.verification_status == VerificationStatus.MISMATCH_DETECTED
    assert res18_post.evidence["intact"] is False


def test_cli_commands_smoke(tmp_path, monkeypatch, capsys):
    pki_dir = tmp_path / "pki"
    monkeypatch.setenv("TRUST_ROOTS_DIR", str(pki_dir / "trust_roots"))
    get_settings.cache_clear()

    # init-ca
    ret = cli_main(["init-ca", "--ca-dir", str(pki_dir)])
    assert ret == 0

    # sign-file
    test_pdf = _create_sample_pdf(tmp_path / "sample.pdf")
    signed_pdf = tmp_path / "sample_signed.pdf"
    ret = cli_main(
        [
            "sign-file",
            str(test_pdf),
            "--out",
            str(signed_pdf),
            "--cert",
            str(pki_dir / "signer.pem"),
            "--key",
            str(pki_dir / "signer.key"),
        ]
    )
    assert ret == 0
    assert signed_pdf.is_file()

    # verify (clean)
    ret = cli_main(["verify", str(signed_pdf), "--doc-id", "sample_noc"])
    assert ret == 0

    # tamper-file
    tampered_pdf = tmp_path / "sample_tampered.pdf"
    ret = cli_main(["tamper-file", str(signed_pdf), "--out", str(tampered_pdf)])
    assert ret == 0

    # verify (tampered -> exits with 1)
    ret = cli_main(["verify", str(tampered_pdf), "--doc-id", "sample_noc"])
    assert ret == 1
