"""Reproducible PDF document signing and mock CA workflow (TRD §9.1, §13.1, §13.2).

Provides:
- Mock CA and Signer key/cert generation using safe defaults or infra/pki/ca_config.json.
- Digital PDF signing using pyHanko and SimpleSigner with standard CMS/PKCS#7 signatures.
- Separate explicit step for document tampering (e.g. app018 SIGNED_THEN_EDITED defect).
- Seamless integration with docverf.provenance.pdf_signature.check_pdf_signature.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from asn1crypto.keys import PrivateKeyInfo
from asn1crypto.x509 import Certificate as ASN1Cert
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import PdfSignatureMetadata, SimpleSigner, sign_pdf
from pyhanko.sign.fields import SigFieldSpec
from pyhanko_certvalidator.registry import SimpleCertificateStore

from docverf.provenance.pdf_signature import check_pdf_signature
from docverf.schemas import CheckStatus

logger = logging.getLogger(__name__)


@dataclass
class CAConfig:
    ca_common_name: str = "Mock Fire Dept CA"
    ca_organization: str = "Maharashtra Fire Services"
    signer_common_name: str = "Mock Fire Dept Signer"
    signer_organization: str = "Maharashtra Fire Services"
    validity_days: int = 365
    key_size: int = 2048
    trust_roots_dir: Path = Path("infra/pki/trust_roots")
    ca_cert_filename: str = "mock_fire_ca.pem"
    ca_key_filename: str = "ca.key"
    signer_cert_filename: str = "signer.pem"
    signer_key_filename: str = "signer.key"

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> CAConfig:
        """Load configuration from JSON if present, otherwise return defaults."""
        if config_path is None:
            config_path = Path("infra/pki/ca_config.json")
        p = Path(config_path)
        if not p.is_file():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return cls(
                ca_common_name=data.get("ca_common_name", "Mock Fire Dept CA"),
                ca_organization=data.get("ca_organization", "Maharashtra Fire Services"),
                signer_common_name=data.get("signer_common_name", "Mock Fire Dept Signer"),
                signer_organization=data.get("signer_organization", "Maharashtra Fire Services"),
                validity_days=int(data.get("validity_days", 365)),
                key_size=int(data.get("key_size", 2048)),
                trust_roots_dir=Path(data.get("trust_roots_dir", "infra/pki/trust_roots")),
                ca_cert_filename=data.get("ca_cert_filename", "mock_fire_ca.pem"),
                ca_key_filename=data.get("ca_key_filename", "ca.key"),
                signer_cert_filename=data.get("signer_cert_filename", "signer.pem"),
                signer_key_filename=data.get("signer_key_filename", "signer.key"),
            )
        except Exception as exc:
            logger.warning("Failed to load ca_config.json (%s), using defaults", exc)
            return cls()


def generate_mock_ca(
    config: CAConfig | None = None,
    base_dir: Path | str | None = None,
) -> dict[str, Path]:
    """Generate self-signed mock CA and signer leaf credentials.

    Writes:
      - ca_key: base_dir / config.ca_key_filename
      - ca_cert: trust_roots_dir / config.ca_cert_filename
      - signer_key: base_dir / config.signer_key_filename
      - signer_cert: base_dir / config.signer_cert_filename

    Returns a dict with paths to all generated files.
    """
    if config is None:
        config = CAConfig.load()
    root_dir = Path(base_dir) if base_dir else Path("infra/pki")
    trust_dir = (root_dir / "trust_roots") if base_dir else config.trust_roots_dir

    root_dir.mkdir(parents=True, exist_ok=True)
    trust_dir.mkdir(parents=True, exist_ok=True)

    # 1. CA key & cert
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=config.key_size)
    ca_subj = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, config.ca_common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, config.ca_organization),
        ]
    )
    now = datetime.datetime.now(datetime.UTC)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subj)
        .issuer_name(ca_subj)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=config.validity_days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # 2. Leaf Signer key & cert
    signer_key = rsa.generate_private_key(public_exponent=65537, key_size=config.key_size)
    signer_subj = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, config.signer_common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, config.signer_organization),
        ]
    )
    signer_cert = (
        x509.CertificateBuilder()
        .subject_name(signer_subj)
        .issuer_name(ca_cert.subject)
        .public_key(signer_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=config.validity_days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    ca_key_path = root_dir / config.ca_key_filename
    ca_cert_path = trust_dir / config.ca_cert_filename
    signer_key_path = root_dir / config.signer_key_filename
    signer_cert_path = root_dir / config.signer_cert_filename

    ca_key_path.write_bytes(
        ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    ca_cert_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))

    signer_key_path.write_bytes(
        signer_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    signer_cert_path.write_bytes(signer_cert.public_bytes(serialization.Encoding.PEM))

    # Secure file permissions where supported
    for key_file in (ca_key_path, signer_key_path):
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass

    return {
        "ca_key": ca_key_path,
        "ca_cert": ca_cert_path,
        "signer_key": signer_key_path,
        "signer_cert": signer_cert_path,
        "trust_roots_dir": trust_dir,
    }


def load_signer(cert_path: Path | str, key_path: Path | str) -> SimpleSigner:
    """Load a pyHanko SimpleSigner from certificate and private key PEM files."""
    cert_bytes = Path(cert_path).read_bytes()
    key_bytes = Path(key_path).read_bytes()

    x509_cert = x509.load_pem_x509_certificate(cert_bytes)
    leaf_asn1 = ASN1Cert.load(x509_cert.public_bytes(serialization.Encoding.DER))

    priv_key = serialization.load_pem_private_key(key_bytes, password=None)
    leaf_key_info = PrivateKeyInfo.load(
        priv_key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    return SimpleSigner(
        signing_cert=leaf_asn1,
        signing_key=leaf_key_info,
        cert_registry=SimpleCertificateStore(),
    )


def sign_pdf_file(
    input_path: Path | str,
    output_path: Path | str,
    cert_path: Path | str,
    key_path: Path | str,
    field_name: str = "Sig1",
) -> Path:
    """Sign a single PDF using pyHanko and write to output_path.

    Never regenerates or alters layout; applies an incremental cryptographic signature.
    """
    inp = Path(input_path)
    out = Path(output_path)
    if not inp.is_file():
        raise FileNotFoundError(f"Input PDF not found: {inp}")

    signer = load_signer(cert_path, key_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(inp, "rb") as inf, open(out, "wb") as outf:
        w = IncrementalPdfFileWriter(inf)
        meta = PdfSignatureMetadata(field_name=field_name)
        sign_pdf(
            w,
            meta,
            signer,
            new_field_spec=SigFieldSpec(field_name),
            output=outf,
        )

    return out


def tamper_pdf_file(
    signed_pdf_path: Path | str,
    output_path: Path | str | None = None,
) -> Path:
    """Tamper a signed PDF by altering bytes covered by the signature digest.

    If output_path is provided, creates a modified copy; otherwise modifies in-place.
    Guarantees that check_pdf_signature detects modification (intact=False).
    """
    src = Path(signed_pdf_path)
    if not src.is_file():
        raise FileNotFoundError(f"Signed PDF not found: {src}")

    dst = Path(output_path) if output_path else src
    if dst != src:
        shutil.copy(src, dst)

    # Flip byte at offset 100 (part of initial PDF body preceding signature dictionary)
    with open(dst, "r+b") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        target_offset = min(100, max(0, size // 4))
        fh.seek(target_offset)
        orig = fh.read(1)
        if not orig:
            raise ValueError(f"PDF too small to tamper: {dst}")
        fh.seek(target_offset)
        fh.write(bytes([orig[0] ^ 0xFF]))

    return dst


def sign_dataset(
    dataset_dir: Path | str,
    cert_path: Path | str,
    key_path: Path | str,
    target_doc: str = "noc.pdf",
    apps: list[str] | None = None,
    out_dir: Path | str | None = None,
) -> list[Path]:
    """Sign target document across applications in a dataset copy.

    By default, signs apps with index 1..8 (clean applications in synthetic dataset)
    and app018 (which will subsequently be tampered in a separate explicit step).
    """
    data_path = Path(dataset_dir)
    if not data_path.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {data_path}")

    # Default application set if not specified: clean apps + app018
    if apps is None:
        clean_apps = [f"app{i:03d}" for i in range(1, 9)]
        apps = [*clean_apps, "app018"]

    signed_files: list[Path] = []
    for app_id in apps:
        doc_path = data_path / app_id / target_doc
        if not doc_path.is_file():
            logger.info("Skipping %s: %s not found", app_id, target_doc)
            continue

        if out_dir is not None:
            dest_path = Path(out_dir) / app_id / target_doc
        else:
            # In-place on user's dataset copy: write to temp and replace
            dest_path = doc_path.with_suffix(".signed.pdf")

        sign_pdf_file(doc_path, dest_path, cert_path, key_path)
        if out_dir is None:
            dest_path.replace(doc_path)
            signed_files.append(doc_path)
        else:
            signed_files.append(dest_path)

    return signed_files


def tamper_app_document(
    dataset_dir: Path | str,
    app_id: str = "app018",
    target_doc: str = "noc.pdf",
    out_dir: Path | str | None = None,
) -> Path:
    """Explicit separate step to tamper an application's signed target document.

    Edits the document post-signing, then verifies that check_pdf_signature detects it.
    """
    data_path = Path(out_dir) if out_dir else Path(dataset_dir)
    doc_path = data_path / app_id / target_doc
    if not doc_path.is_file():
        raise FileNotFoundError(f"Target document to tamper not found: {doc_path}")

    # Verify document was signed prior to tampering
    initial_check = check_pdf_signature(str(doc_path), f"{app_id}_{Path(target_doc).stem}")
    if not initial_check.evidence.get("signed"):
        logger.warning("Document %s is not signed; tampering unsigned file", doc_path)

    tamper_pdf_file(doc_path)

    # Post-tamper verification check
    post_check = check_pdf_signature(str(doc_path), f"{app_id}_{Path(target_doc).stem}")
    if post_check.status == CheckStatus.VERIFIED or post_check.evidence.get("intact"):
        raise RuntimeError(f"Tamper failed: document {doc_path} was still reported verified/intact")

    return doc_path
