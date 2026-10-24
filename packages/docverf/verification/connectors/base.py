"""Issuer connector interface (TRD §9.3)."""

from typing import Protocol

from docverf.schemas import CheckResult, DocType, FieldValue


class IssuerConnector(Protocol):
    name: str
    doc_types: set[DocType]

    def lookup(self, ref_no: str, fields: dict[str, FieldValue]) -> CheckResult: ...
