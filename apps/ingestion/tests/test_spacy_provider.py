"""Tests for the optional spaCy NER provider.

Skipped automatically when spaCy or the ``en_core_web_sm`` model is not
installed, so the suite still passes in minimal environments.
"""
from __future__ import annotations

import json

import pytest

spacy = pytest.importorskip("spacy")

try:  # pragma: no cover - depends on environment
    spacy.load("en_core_web_sm", disable=["lemmatizer", "textcat"])
    _MODEL_AVAILABLE = True
except Exception:  # pragma: no cover
    _MODEL_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _MODEL_AVAILABLE, reason="en_core_web_sm model not installed"
)

PROMPT = """Article URL: https://techcrunch.com/2025/01/15/x/
TITLE: Sam Altman and the Bay Area
AUTHOR: Jane Reporter

CONTENT:
Sam Altman criticized Elon Musk in the Bay Area. Big Tech firms invested heavily.
Satya Nadella praised Altman during the keynote.

Return JSON with exactly this shape:
{"people": ["Full Name"]}
"""


def test_spacy_provider_detects_people_and_filters_places():
    from apps.ingestion.providers.spacy_provider import SpacyNERProvider

    out = json.loads(SpacyNERProvider().complete_json(system_prompt="", user_prompt=PROMPT))
    people = set(out["people"])

    # Real people are detected (incl. the author).
    assert "Sam Altman" in people
    assert "Elon Musk" in people
    assert "Jane Reporter" in people

    # Places / concepts are NOT treated as people.
    assert "Bay Area" not in people
    assert "Big Tech" not in people


def test_spacy_provider_builds_typed_relationship():
    from apps.ingestion.providers.spacy_provider import SpacyNERProvider

    out = json.loads(SpacyNERProvider().complete_json(system_prompt="", user_prompt=PROMPT))
    edges = {(r["source"], r["type"], r["target"]) for r in out["relationships"]}
    assert ("Sam Altman", "criticized", "Elon Musk") in edges
