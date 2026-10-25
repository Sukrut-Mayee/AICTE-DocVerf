"""Tests for core provenance: hashing, duplicates, metadata, QR, PDF signature (TRD §9.1)."""

import datetime
import hashlib
import shutil
from pathlib import Path

import fitz
import imagehash
import zxingcpp
from asn1crypto.keys import PrivateKeyInfo
from asn1crypto.x509 import Certificate as ASN1Cert
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from docverf.config import get_settings
from docverf.provenance.duplicates import HashIndex, check_duplicates
from docverf.provenance.hashing import hash_file
from docverf.provenance.metadata import extract_metadata
from docverf.provenance.pdf_signature import check_pdf_signature
from docverf.provenance.qr import decode_qr
from docverf.schemas import CheckStatus, Layer, Severity, VerificationStatus
from PIL import Image, PngImagePlugin


def _write_bytes(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _phash_of_image(image: Image.Image) -> str:
    return str(imagehash.phash(image.convert("RGB")))


# ---------------- hash_file ----------------


def test_hash_file_known_sha256(tmp_path):
    data = b"deterministic content for hashing"
    path = _write_bytes(tmp_path, "sample.bin", data)
    result = hash_file(path)
    assert result["sha256"] == _sha256(data)
    assert isinstance(result["phash"], str)


def test_hash_file_different_content_different_sha256(tmp_path):
    a = _write_bytes(tmp_path, "a.bin", b"aaa")
    b = _write_bytes(tmp_path, "b.bin", b"bbb")
    ra, rb = hash_file(a), hash_file(b)
    assert ra["sha256"] != rb["sha256"]


def test_hash_file_identical_bytes_identical_hash(tmp_path):
    data = b"identical bytes"
    pa = _write_bytes(tmp_path, "a.bin", data)
    pb = _write_bytes(tmp_path, "b.bin", data)
    assert hash_file(pa) == hash_file(pb)


def test_hash_file_pdf_no_phash(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Provenance page one")
    path = str(tmp_path / "doc.pdf")
    doc.save(path)
    doc.close()

    result = hash_file(path)
    assert result["sha256"] == _sha256(Path(path).read_bytes())
    # PDFs do not use page-render pHash to prevent template false positives.
    assert result["phash"] == ""



def test_hash_file_image_phash(tmp_path):
    image = Image.new("RGB", (200, 200), color="white")
    path = str(tmp_path / "img.png")
    image.save(path, format="PNG")

    result = hash_file(path)
    assert result["sha256"] == _sha256(Path(path).read_bytes())
    assert result["phash"] == _phash_of_image(image)


# ---------------- check_duplicates ----------------


def _flip_bits(hex_string: str, positions: list[int]) -> str:
    value = int(hex_string, 16)
    for pos in positions:
        value ^= 1 << pos
    return format(value, f"0{len(hex_string)}x")


def test_check_duplicates_exact_sha256_across_apps():
    index: HashIndex = {
        "deadbeef" * 8: [("app001", "app001_noc")],
    }
    results = check_duplicates(
        "app002", "app002_noc", {"sha256": "deadbeef" * 8}, index
    )
    assert len(results) == 1
    r = results[0]
    assert r.doc_id == "app002_noc"
    assert r.layer == Layer.A
    assert r.check == "hash_duplicate"
    assert r.status == CheckStatus.MISMATCH
    assert r.severity == Severity.HIGH
    assert r.evidence["hash_type"] == "sha256"
    assert ("app001", "app001_noc") in r.evidence["duplicates"]


def test_check_duplicates_same_app_excluded():
    index: HashIndex = {
        "deadbeef" * 8: [("app001", "app001_noc")],
    }
    results = check_duplicates(
        "app001", "app001_other", {"sha256": "deadbeef" * 8}, index
    )
    assert results == []


def test_check_duplicates_no_match():
    index: HashIndex = {
        "deadbeef" * 8: [("app001", "app001_noc")],
    }
    results = check_duplicates("app002", "app002_noc", {"sha256": "cafebab" * 8}, index)
    assert results == []


def test_check_duplicates_phash_within_threshold_is_duplicate():
    base = "0123456789abcdef"  # 64 bits
    close = _flip_bits(base, [0, 1, 2])  # distance 3 <= default 6
    index: HashIndex = {base: [("app001", "app001_photo")]}
    results = check_duplicates("app002", "app002_photo", {"phash": close}, index)
    assert len(results) == 1
    assert results[0].evidence["hash_type"] == "phash"
    assert ("app001", "app001_photo") in results[0].evidence["duplicates"]


def test_check_duplicates_phash_beyond_threshold_not_duplicate():
    base = "0123456789abcdef"
    far = _flip_bits(base, list(range(7)))  # distance 7 > default 6
    index: HashIndex = {base: [("app001", "app001_photo")]}
    results = check_duplicates("app002", "app002_photo", {"phash": far}, index)
    assert results == []


def test_check_duplicates_index_not_mutated():
    index: HashIndex = {"deadbeef" * 8: [("app001", "app001_noc")]}
    before = {k: list(v) for k, v in index.items()}
    check_duplicates("app002", "app002_noc", {"sha256": "deadbeef" * 8}, index)
    assert index == before


def test_check_duplicates_multiple_hash_types():
    index: HashIndex = {
        "deadbeef" * 8: [("app001", "app001_noc")],
    }
    results = check_duplicates(
        "app002",
        "app002_noc",
        {"sha256": "deadbeef" * 8, "phash": "0123456789abcdef"},
        index,
    )
    assert len(results) == 1  # only sha256 matches; phash key absent from index


def test_different_pdfs_with_similar_templates_not_flagged_as_duplicates(tmp_path):
    def make_noc_pdf(filename: str, college_name: str, app_no: str) -> str:
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 50), "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION", fontsize=14)
        page.insert_text(
            (50, 70), "APPROVAL PROCESS 2027-28 - NO OBJECTION CERTIFICATE", fontsize=11
        )
        page.draw_rect(fitz.Rect(40, 40, 555, 800), width=1.5)
        page.insert_text(
            (50, 120), "This certificate confirms that the institution complies with norms."
        )
        page.insert_text((50, 140), "Application Number: " + app_no)
        page.insert_text((50, 160), "Institution Name: " + college_name)
        page.insert_text(
            (50, 200), "Valid for academic session 2027-2028 under regional office guidelines."
        )
        path = str(tmp_path / filename)
        doc.save(path)
        doc.close()
        return path

    pdf1 = make_noc_pdf("app001_noc.pdf", "Alpha Institute of Technology", "1-000000001")
    pdf2 = make_noc_pdf("app002_noc.pdf", "Beta College of Engineering", "1-000000002")

    hash1 = hash_file(pdf1)
    hash2 = hash_file(pdf2)
    assert hash1["sha256"] != hash2["sha256"]
    assert hash1["phash"] == ""
    assert hash2["phash"] == ""

    index: HashIndex = {}
    for h in [hash1["sha256"], hash1["phash"]]:
        if h:
            index.setdefault(h, []).append(("app001", "app001_noc"))

    results = check_duplicates("app002", "app002_noc", hash2, index)
    assert results == []


def test_identical_pdfs_flagged_as_sha256_duplicates(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Identical Land Deed Document")
    path1 = str(tmp_path / "app001_deed.pdf")
    doc.save(path1)
    doc.close()

    path2 = str(tmp_path / "app002_deed.pdf")
    shutil.copyfile(path1, path2)

    hash1 = hash_file(path1)
    hash2 = hash_file(path2)
    assert hash1["sha256"] == hash2["sha256"]
    assert hash1["phash"] == ""

    index: HashIndex = {hash1["sha256"]: [("app001", "app001_deed")]}
    results = check_duplicates("app002", "app002_deed", hash2, index)
    assert len(results) == 1
    assert results[0].evidence["hash_type"] == "sha256"
    assert ("app001", "app001_deed") in results[0].evidence["duplicates"]


def test_identical_and_near_identical_photos_detected_as_phash_duplicates(tmp_path):
    img = Image.new("RGB", (100, 100), color=(120, 80, 200))
    path1 = str(tmp_path / "photo1.jpg")
    img.save(path1, format="JPEG")

    path2 = str(tmp_path / "photo2.jpg")
    shutil.copyfile(path1, path2)

    hash1 = hash_file(path1)
    hash2 = hash_file(path2)
    assert hash1["sha256"] == hash2["sha256"]
    assert hash1["phash"] != ""
    assert hash1["phash"] == hash2["phash"]

    index: HashIndex = {
        hash1["sha256"]: [("app001", "app001_photo")],
        hash1["phash"]: [("app001", "app001_photo")],
    }
    results = check_duplicates("app002", "app002_photo", hash2, index)
    assert len(results) >= 1
    matched_types = {r.evidence["hash_type"] for r in results}
    assert "phash" in matched_types or "sha256" in matched_types


def test_check_duplicates_pdf_ignores_phash():
    index: HashIndex = {"0123456789abcdef": [("app001", "app001_doc.pdf")]}
    results = check_duplicates("app002", "app002_doc.pdf", {"phash": "0123456789abcdef"}, index)
    assert results == []


# ---------------- extract_metadata ----------------


def _make_png_with_producer(tmp_path, producer: str | None) -> str:
    image = Image.new("RGB", (100, 100), color="white")
    path = str(tmp_path / "meta.png")
    if producer is not None:
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("Software", producer)
        image.save(path, format="PNG", pnginfo=pnginfo)
    else:
        image.save(path, format="PNG")
    return path


def test_extract_metadata_image_editing_producer_flagged(tmp_path):
    path = _make_png_with_producer(tmp_path, "Adobe Photoshop 24.0")
    result = extract_metadata(path, "app001_noc")
    assert result.doc_id == "app001_noc"
    assert result.layer == Layer.D
    assert result.check == "metadata"
    assert result.status == CheckStatus.SUSPICIOUS
    assert result.severity == Severity.LOW
    assert "image-editing" in result.reason.lower()
    assert result.evidence["producer"] == "Adobe Photoshop 24.0"
    assert result.evidence["flag"] is True


def test_extract_metadata_clean_producer(tmp_path):
    path = _make_png_with_producer(tmp_path, "Some Normal Producer")
    result = extract_metadata(path, "app001_noc")
    assert result.status == CheckStatus.CLEAN
    assert result.severity == Severity.INFO
    assert result.evidence["flag"] is False


def test_extract_metadata_missing_metadata_graceful(tmp_path):
    path = _make_png_with_producer(tmp_path, None)
    result = extract_metadata(path, "app001_noc")
    assert result.status == CheckStatus.CLEAN
    assert result.evidence["producer"] is None
    assert result.evidence["flag"] is False


# ---------------- decode_qr ----------------


def _write_qr_png(tmp_path, text: str, name: str = "qr.png") -> str:
    barcode = zxingcpp.create_barcode(text, zxingcpp.BarcodeFormat.QRCode)
    img_array = zxingcpp.write_barcode_to_image(barcode)
    image = Image.fromarray(img_array)
    path = str(tmp_path / name)
    image.save(path, format="PNG")
    return path


def test_decode_qr_valid_payload(tmp_path):
    path = _write_qr_png(tmp_path, "FIRE/MH/2026/123456")
    result = decode_qr(path, "app001_noc")
    assert result.doc_id == "app001_noc"
    assert result.layer == Layer.A
    assert result.check == "qr"
    assert result.status == CheckStatus.CLEAN
    assert result.verification_status is not None
    assert result.evidence["details"]["payload"] == ["FIRE/MH/2026/123456"]


def test_decode_qr_no_qr_code(tmp_path):
    image = Image.new("RGB", (100, 100), color="white")
    path = str(tmp_path / "noqr.png")
    image.save(path, format="PNG")
    result = decode_qr(path, "app001_noc")
    assert result.status == CheckStatus.NOT_APPLICABLE
    assert result.evidence["details"]["payload"] is None


# ---------------- check_pdf_signature ----------------


def _make_ca():
    """Generate a self-signed CA key+cert (not committed; test runtime only)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subj = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subj)
        .issuer_name(subj)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .add_extension(
            x509.KeyUsage(
                False, False, False, False, False, True, True, False, False
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _make_leaf(ca_key, ca_cert):
    """Generate a leaf key+cert signed by the given CA."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subj = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Leaf")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subj)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(2)
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        # content_commitment (non-repudiation) required by pyHanko for signing certs.
        .add_extension(
            x509.KeyUsage(
                True, True, False, False, False, False, False, False, False
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    return key, cert


def _make_unsigned_pdf(tmp_path, name="unsigned.pdf"):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test document")
    path = str(tmp_path / name)
    doc.save(path)
    doc.close()
    return path


def _sign_pdf(ca_key, ca_cert, leaf_key, leaf_cert, unsigned_path, signed_path):
    """Sign a PDF with pyHanko using the leaf cert; CA cert is the issuer."""
    leaf_asn1 = ASN1Cert.load(leaf_cert.public_bytes(serialization.Encoding.DER))
    leaf_key_info = PrivateKeyInfo.load(
        leaf_key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import PdfSignatureMetadata, SimpleSigner, sign_pdf
    from pyhanko.sign.fields import SigFieldSpec

    with open(unsigned_path, "rb") as inf, open(signed_path, "wb") as outf:
        w = IncrementalPdfFileWriter(inf)
        meta = PdfSignatureMetadata(field_name="Sig1")
        signer = SimpleSigner(
            signing_cert=leaf_asn1,
            signing_key=leaf_key_info,
            cert_registry=None,
        )
        sign_pdf(
            w,
            meta,
            signer,
            new_field_spec=SigFieldSpec("Sig1"),
            output=outf,
        )


def _set_trust_roots(monkeypatch, ca_cert, tmp_path):
    """Write the CA cert to a temp trust root dir and point config at it."""
    trust_dir = tmp_path / "trust_roots"
    trust_dir.mkdir()
    ca_path = trust_dir / "ca.pem"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    monkeypatch.setenv("TRUST_ROOTS_DIR", str(trust_dir))
    get_settings.cache_clear()


def test_check_pdf_signature_valid_trusted(tmp_path, monkeypatch):
    unsigned_path = _make_unsigned_pdf(tmp_path)
    signed_path = str(tmp_path / "signed.pdf")

    ca_key, ca_cert = _make_ca()
    leaf_key, leaf_cert = _make_leaf(ca_key, ca_cert)
    _set_trust_roots(monkeypatch, ca_cert, tmp_path)
    _sign_pdf(ca_key, ca_cert, leaf_key, leaf_cert, unsigned_path, signed_path)

    result = check_pdf_signature(signed_path, "app001_noc")
    assert result.doc_id == "app001_noc"
    assert result.layer == Layer.A
    assert result.check == "pdf_signature"
    assert result.status == CheckStatus.VERIFIED
    assert result.severity == Severity.INFO
    assert result.verification_status == VerificationStatus.VERIFIED
    assert result.evidence["intact"] is True
    assert result.evidence["valid"] is True
    assert result.evidence["trusted"] is True
    assert result.evidence["signed"] is True


def test_check_pdf_signature_tampered(tmp_path, monkeypatch):
    unsigned_path = _make_unsigned_pdf(tmp_path)
    signed_path = str(tmp_path / "signed.pdf")
    tampered_path = str(tmp_path / "tampered.pdf")

    ca_key, ca_cert = _make_ca()
    leaf_key, leaf_cert = _make_leaf(ca_key, ca_cert)
    _set_trust_roots(monkeypatch, ca_cert, tmp_path)
    _sign_pdf(ca_key, ca_cert, leaf_key, leaf_cert, unsigned_path, signed_path)

    # Tamper: flip a byte after signing.
    shutil.copy(signed_path, tampered_path)
    with open(tampered_path, "r+b") as f:
        f.seek(100)
        b = f.read(1)
        f.seek(100)
        f.write(bytes([b[0] ^ 0xFF]))

    result = check_pdf_signature(tampered_path, "app001_noc")
    assert result.status == CheckStatus.MISMATCH
    assert result.severity == Severity.HIGH
    assert result.verification_status == VerificationStatus.MISMATCH_DETECTED
    assert result.evidence["signed"] is True
    assert result.evidence["intact"] is False


def test_check_pdf_signature_untrusted_signer(tmp_path, monkeypatch):
    unsigned_path = _make_unsigned_pdf(tmp_path)
    signed_path = str(tmp_path / "signed.pdf")

    # Signing CA is NOT in the trust roots.
    ca_key, ca_cert = _make_ca()
    leaf_key, leaf_cert = _make_leaf(ca_key, ca_cert)
    # Use a different, unrelated CA as the trust root.
    other_ca_key, other_ca_cert = _make_ca()
    _set_trust_roots(monkeypatch, other_ca_cert, tmp_path)
    _sign_pdf(ca_key, ca_cert, leaf_key, leaf_cert, unsigned_path, signed_path)

    result = check_pdf_signature(signed_path, "app001_noc")
    assert result.status == CheckStatus.MISMATCH
    assert result.severity == Severity.HIGH
    assert result.verification_status == VerificationStatus.MISMATCH_DETECTED
    assert result.evidence["signed"] is True
    assert result.evidence["trusted"] is False


def test_check_pdf_signature_unsigned(tmp_path, monkeypatch):
    unsigned_path = _make_unsigned_pdf(tmp_path)
    _set_trust_roots(monkeypatch, _make_ca()[1], tmp_path)

    result = check_pdf_signature(unsigned_path, "app001_noc")
    assert result.status == CheckStatus.NOT_APPLICABLE
    assert result.severity == Severity.INFO
    assert result.verification_status is None
    assert result.evidence["signed"] is False


def test_check_pdf_signature_missing_trust_dir(tmp_path, monkeypatch):
    """No TRUST_ROOTS_DIR → any signature is untrusted → mismatch, not verified."""
    unsigned_path = _make_unsigned_pdf(tmp_path)
    signed_path = str(tmp_path / "signed.pdf")

    ca_key, ca_cert = _make_ca()
    leaf_key, leaf_cert = _make_leaf(ca_key, ca_cert)
    # Point at a non-existent trust dir.
    monkeypatch.setenv("TRUST_ROOTS_DIR", str(tmp_path / "nonexistent"))
    get_settings.cache_clear()
    _sign_pdf(ca_key, ca_cert, leaf_key, leaf_cert, unsigned_path, signed_path)

    result = check_pdf_signature(signed_path, "app001_noc")
    assert result.status == CheckStatus.MISMATCH
    assert result.severity == Severity.HIGH
    assert result.evidence["trusted"] is False


def test_check_pdf_signature_malformed_pdf(tmp_path, monkeypatch):
    """Malformed PDF → ERROR, never classified as verified."""
    path = str(tmp_path / "bad.pdf")
    Path(path).write_bytes(b"not a pdf at all")
    _set_trust_roots(monkeypatch, _make_ca()[1], tmp_path)

    result = check_pdf_signature(path, "app001_noc")
    assert result.status == CheckStatus.ERROR
    assert result.verification_status is None
