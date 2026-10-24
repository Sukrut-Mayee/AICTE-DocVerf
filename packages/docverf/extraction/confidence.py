"""Field confidence (TRD §10)."""


def field_confidence(ocr_conf: float, extractors_agree: bool | None, format_valid: bool) -> float:
    """ocr_conf x agreement_factor x format_factor.

    agreement_factor: 1.0 both extractors agree after normalization (True), 0.6 only one produced
    a value (None), 0.4 they disagree (False). format_factor: 1.0 valid, 0.5 invalid.
    """
    if extractors_agree is True:
        agreement_factor = 1.0
    elif extractors_agree is None:
        agreement_factor = 0.6
    else:
        agreement_factor = 0.4

    format_factor = 1.0 if format_valid else 0.5

    # Clamp OCR confidence to [0, 1] before calculating.
    clamped_conf = min(1.0, max(0.0, float(ocr_conf)))

    result = clamped_conf * agreement_factor * format_factor
    return min(1.0, max(0.0, result))
