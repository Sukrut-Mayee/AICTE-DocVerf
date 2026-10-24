"""Frozen contract check: docverf.schemas must match the TRD §5 code blocks exactly."""

import ast
import enum
import re
from pathlib import Path

import pytest
from docverf import schemas
from pydantic import BaseModel, ValidationError

TRD = Path(__file__).parent.parent / "docs" / "TRD.md"


def _trd_classes() -> dict[str, ast.ClassDef]:
    section = TRD.read_text(encoding="utf-8").split("## 5. Data contracts")[1].split("## 6.")[0]
    classes = {}
    for block in re.findall(r"```python\n(.*?)```", section, re.S):
        for node in ast.parse(block).body:
            if isinstance(node, ast.ClassDef):
                classes[node.name] = node
    return classes


def _fields(cls_node: ast.ClassDef) -> dict[str, tuple[str, str | None]]:
    """field name -> (annotation source, default source) from a class body."""
    return {
        stmt.target.id: (
            ast.unparse(stmt.annotation),
            ast.unparse(stmt.value) if stmt.value else None,
        )
        for stmt in cls_node.body
        if isinstance(stmt, ast.AnnAssign)
    }


TRD_CLASSES = _trd_classes()


def _bases(c: ast.ClassDef) -> list[str]:
    return [ast.unparse(b) for b in c.bases]


ENUMS = [n for n, c in TRD_CLASSES.items() if "Enum" in _bases(c)]
MODELS = [n for n, c in TRD_CLASSES.items() if "BaseModel" in _bases(c)]
OURS = {
    n.name: n
    for n in ast.parse(Path(schemas.models.__file__).read_text(encoding="utf-8")).body
    if isinstance(n, ast.ClassDef)
}


def test_every_trd_class_is_exported():
    assert len(ENUMS) == 10 and len(MODELS) == 11
    assert set(TRD_CLASSES) <= set(schemas.__all__)


@pytest.mark.parametrize("name", ENUMS)
def test_enum_members_match_trd(name):
    expected = {
        stmt.targets[0].id: ast.literal_eval(stmt.value)
        for stmt in TRD_CLASSES[name].body
        if isinstance(stmt, ast.Assign)
    }
    cls = getattr(schemas, name)
    assert issubclass(cls, str) and issubclass(cls, enum.Enum)
    assert {m.name: m.value for m in cls} == expected


@pytest.mark.parametrize("name", MODELS)
def test_model_fields_match_trd(name):
    """Same field names, order, annotations and defaults as the TRD §5.2 code."""
    assert issubclass(getattr(schemas, name), BaseModel)
    assert _fields(OURS[name]) == _fields(TRD_CLASSES[name])


def test_field_value_confidence_is_bounded():
    for bad in (1.5, -0.1):
        with pytest.raises(ValidationError):
            schemas.FieldValue(value=1, confidence=bad)
    schemas.FieldValue(value=1, confidence=0)
    schemas.FieldValue(value=1, confidence=1)
