"""config.py must cover every variable in .env.example (generated from TRD §15)."""

from dataclasses import fields
from datetime import date
from pathlib import Path

import pytest
from docverf.config import Settings, _cast, get_settings
from dotenv import dotenv_values

ENV_EXAMPLE = Path(__file__).parent.parent / ".env.example"


def test_settings_match_env_example_keys():
    assert set(dotenv_values(ENV_EXAMPLE)) == {f.name for f in fields(Settings)}


def test_defaults_match_env_example_values():
    defaults = Settings()
    for key, raw in dotenv_values(ENV_EXAMPLE).items():
        if raw:  # blank entries (ANCHOR_*, VLM_MODEL) default to ""
            assert _cast(getattr(defaults, key), raw) == getattr(defaults, key), key
        else:
            assert getattr(defaults, key) == "", key


def test_env_overrides_and_types(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.9")
    monkeypatch.setenv("ALLOW_CLOUD_AI", "true")
    monkeypatch.setenv("ACADEMIC_YEAR_END", "2029-06-30")
    monkeypatch.setenv("PHASH_MAX_DIST", "")  # empty means unset
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.CONFIDENCE_THRESHOLD == 0.9
        assert s.ALLOW_CLOUD_AI is True
        assert s.ACADEMIC_YEAR_END == date(2029, 6, 30)
        assert s.PHASH_MAX_DIST == 6
    finally:
        get_settings.cache_clear()


def test_rules_can_look_up_config_by_name():
    assert getattr(Settings(), "ACADEMIC_YEAR_END") == date(2028, 6, 30)  # noqa: B009


@pytest.mark.parametrize("raw", ["maybe", "2"])
def test_bool_is_false_unless_truthy(raw):
    assert _cast(False, raw) is False
