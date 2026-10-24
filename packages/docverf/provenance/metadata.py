"""File metadata checks (TRD §9.1)."""

from datetime import datetime

from PIL import ExifTags, Image

from docverf.schemas import CheckResult, CheckStatus, Layer, Severity

IMAGE_EDITING_PRODUCERS = (
    "photoshop",
    "gimp",
    "paint.net",
    "affinity",
    "corel",
    "imagemagick",
    "acdsee",
)


def _read_producer(path: str) -> str | None:
    """Return producer string from metadata, or None when unavailable.

    pyexiftool is used when available (it requires the exiftool system binary, which is not
    guaranteed on every platform). PIL is the fallback. Missing metadata or an unavailable
    tool degrades gracefully to None.
    """
    # Try pyexiftool first.
    try:
        import pyexiftool  # type: ignore

        with pyexiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(path)[0]
        for key in ("Producer", "EXIF:Producer", "XMP:Producer", "PDF:Producer"):
            value = metadata.get(key)
            if value:
                return str(value)
    except Exception:
        pass

    # Fallback: PIL embedded info / exif.
    try:
        with Image.open(path) as img:
            producer = (
                img.info.get("Producer")
                or img.info.get("producer")
                or img.info.get("Software")
                or img.info.get("software")
            )
            if producer:
                return str(producer)
            exif = img.getexif()
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                if isinstance(tag, str) and tag.lower() in ("software", "producer"):
                    return str(value)
    except Exception:
        pass

    return None


def _is_image_editing(producer: str | None) -> bool:
    if not producer:
        return False
    lowered = producer.lower()
    return any(tool in lowered for tool in IMAGE_EDITING_PRODUCERS)


def extract_metadata(path: str, doc_id: str) -> CheckResult:
    """Flag (low) if the producer is image-editing software.

    Limitation (TRD §9.1): the spec also asks to flag when the creation date is more than 30
    days after the document's printed date, but this function receives no printed-date
    argument and the public signature is frozen (§19 Q1). That comparison is intentionally not
    performed here; it must be reported to the lead before changing the signature.
    """
    producer = _read_producer(path)
    edited = _is_image_editing(producer)

    limitation_note = {
        "note": "creation-date vs printed-date check not available: no printed-date argument"
    }

    if edited:
        return CheckResult(
            doc_id=doc_id,
            layer=Layer.D,
            check="metadata",
            status=CheckStatus.SUSPICIOUS,
            severity=Severity.LOW,
            reason="Producer metadata indicates image-editing software",
            evidence={
                "producer": producer,
                "flag": True,
                "details": limitation_note,
            },
            checked_at=datetime.now(),
        )

    return CheckResult(
        doc_id=doc_id,
        layer=Layer.D,
        check="metadata",
        status=CheckStatus.CLEAN,
        severity=Severity.INFO,
        reason="no image-editing producer metadata detected",
        evidence={
            "producer": producer,
            "flag": False,
            "details": limitation_note,
        },
        checked_at=datetime.now(),
    )
