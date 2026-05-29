"""Factory that picks the right :class:`BaseLLMProvider` at runtime."""
from __future__ import annotations

import logging

from django.conf import settings

from apps.ingestion.providers.base import BaseLLMProvider
from apps.ingestion.providers.mock_provider import MockLLMProvider

logger = logging.getLogger(__name__)


def build_llm_provider() -> BaseLLMProvider:
    """Return a provider based on settings.NEWS_GRAPH['LLM_PROVIDER']."""

    cfg = getattr(settings, "NEWS_GRAPH", {})
    name = (cfg.get("LLM_PROVIDER") or "mock").lower()

    if name in {"openai", "auto"}:
        # OpenAI when the key works; sticky fallback to spaCy on quota/auth errors.
        from apps.ingestion.providers.fallback_provider import AdaptiveLLMProvider

        return AdaptiveLLMProvider()
    if name == "spacy":
        try:
            from apps.ingestion.providers.spacy_provider import SpacyNERProvider

            return SpacyNERProvider()
        except Exception as exc:
            logger.warning("spaCy provider unavailable, falling back to MockLLMProvider: %s", exc)
            return MockLLMProvider()
    if name == "mock":
        return MockLLMProvider()

    logger.warning("Unknown LLM_PROVIDER=%r, falling back to mock", name)
    return MockLLMProvider()
