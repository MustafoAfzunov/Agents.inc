"""Tests for OpenAI → spaCy adaptive fallback."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.common.exceptions import ExtractionError
from apps.ingestion.providers.fallback_provider import (
    AdaptiveLLMProvider,
    _should_fallback_to_spacy,
    reset_active_backend,
)


@pytest.fixture(autouse=True)
def _clear_sticky_backend():
    reset_active_backend()
    yield
    reset_active_backend()


@pytest.mark.parametrize(
    "message,expect",
    [
        ("insufficient_quota: you exceeded your current quota", True),
        ("Invalid API key provided", True),
        ("OpenAI request failed: 401 Unauthorized", True),
        ("connection reset by peer", False),
    ],
)
def test_should_fallback_heuristic(message: str, expect: bool):
    assert _should_fallback_to_spacy(ExtractionError(message)) is expect


@patch("apps.ingestion.providers.openai_provider.OpenAIProvider")
def test_openai_quota_error_switches_to_spacy(mock_openai_cls, settings):
    settings.NEWS_GRAPH = {
        **settings.NEWS_GRAPH,
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test",
    }

    mock_openai = MagicMock()
    mock_openai.name = "openai"
    mock_openai.complete_json.side_effect = ExtractionError(
        "OpenAI request failed: insufficient_quota"
    )
    mock_openai_cls.return_value = mock_openai

    spacy_mock = MagicMock()
    spacy_mock.name = "spacy"
    spacy_mock.complete_json.return_value = '{"people": [], "relationships": []}'

    with patch(
        "apps.ingestion.providers.spacy_provider.SpacyNERProvider",
        return_value=spacy_mock,
    ):
        provider = AdaptiveLLMProvider()
        out = provider.complete_json(system_prompt="s", user_prompt="u")

    assert out == '{"people": [], "relationships": []}'
    assert provider.active_name == "spacy"
    spacy_mock.complete_json.assert_called_once()
    # Second call should not hit OpenAI again (sticky per worker).
    provider.complete_json(system_prompt="s", user_prompt="u2")
    assert mock_openai.complete_json.call_count == 1
    assert spacy_mock.complete_json.call_count == 2


@patch("apps.ingestion.providers.openai_provider.OpenAIProvider")
def test_no_api_key_uses_spacy_without_calling_openai(mock_openai_cls, settings):
    settings.NEWS_GRAPH = {**settings.NEWS_GRAPH, "OPENAI_API_KEY": ""}

    spacy_mock = MagicMock()
    spacy_mock.name = "spacy"
    spacy_mock.complete_json.return_value = '{"people": ["Ada Lovelace"], "relationships": []}'

    with patch(
        "apps.ingestion.providers.spacy_provider.SpacyNERProvider",
        return_value=spacy_mock,
    ):
        provider = AdaptiveLLMProvider()
        provider.complete_json(system_prompt="s", user_prompt="u")

    mock_openai_cls.assert_not_called()
    assert provider.active_name == "spacy"
