"""Tests for shared utility helpers."""
from __future__ import annotations

from apps.common.utils.text import name_tokens, normalize_name


def test_normalize_name_lowercases_and_strips_punctuation():
    assert normalize_name("Sam Altman") == "sam altman"
    assert normalize_name(" Sam  Altman ") == "sam altman"
    assert normalize_name("Sam-Altman") == "sam-altman"


def test_normalize_name_drops_honorifics_and_roles():
    assert normalize_name("Mr. Sam Altman") == "sam altman"
    # Possessive org prefix + role title both collapse away.
    assert normalize_name("OpenAI's CEO Sam Altman") == "sam altman"


def test_normalize_name_handles_accents():
    assert normalize_name("Émile Zola") == "emile zola"


def test_name_tokens():
    assert name_tokens("Sam Altman") == ["sam", "altman"]
    assert name_tokens("") == []
