"""Field confidence (TRD §10)."""


def field_confidence(ocr_conf: float, extractors_agree: bool | None, format_valid: bool) -> float:
    """ocr_conf x agreement_factor x format_factor.

    agreement_factor: 1.0 both extractors agree after normalization (True), 0.6 only one produced
    a value (None), 0.4 they disagree (False). format_factor: 1.0 valid, 0.5 invalid.
    """
    raise NotImplementedError
