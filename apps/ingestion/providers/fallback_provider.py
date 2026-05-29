"""Adaptive provider: OpenAI first, spaCy when the API key or quota fails.

When ``LLM_PROVIDER=openai`` (the recommended production setting), ingestion
uses OpenAI for high-quality relationship extraction. If a call fails because
the key is invalid, billing/quota is exhausted, or the account cannot bill,
this provider logs a warning and **sticks** to spaCy for the rest of that
worker process so rescans are not interrupted mid-run.

Falls back to ``MockLLMProvider`` only when spaCy or its model is unavailable
(e.g. a minimal dev install without ``en_core_web_sm``).
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

from apps.common.exceptions import ExtractionError
from apps.ingestion.providers.base import BaseLLMProvider
from apps.ingestion.providers.mock_provider import MockLLMProvider

logger = logging.getLogger(__name__)

# Per-worker sticky backend after OpenAI becomes unusable (gunicorn = one process).
_active_backend: Optional[str] = None


def get_active_backend() -> Optional[str]:
    """Return the runtime backend name after a fallback, else ``None``."""

    return _active_backend


def reset_active_backend() -> None:
    """Clear sticky fallback (used in tests)."""

    global _active_backend
    _active_backend = None


def _should_fallback_to_spacy(exc: BaseException) -> bool:
    """True when OpenAI is unlikely to recover without new billing or a new key."""

    try:
        from openai import (
            APIConnectionError,
            AuthenticationError,
            PermissionDeniedError,
            RateLimitError,
        )
    except ImportError:
        openai_errors: tuple[type[BaseException], ...] = ()
    else:
        openai_errors = (
            AuthenticationError,
            PermissionDeniedError,
            APIConnectionError,
            RateLimitError,
        )

    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if openai_errors and isinstance(current, openai_errors):
            if isinstance(current, RateLimitError):
                body = getattr(current, "body", None)
                code = ""
                if isinstance(body, dict):
                    err = body.get("error") or {}
                    if isinstance(err, dict):
                        code = str(err.get("code", ""))
                if code == "insufficient_quota" or "quota" in str(current).lower():
                    return True
                # Hard rate limits during a burst are transient; do not switch backends.
                return False
            return True

        msg = str(current).lower()
        if any(
            token in msg
            for token in (
                "insufficient_quota",
                "invalid_api_key",
                "invalid api key",
                "incorrect api key",
                "authentication",
                "unauthorized",
                "billing",
                "exceeded your current quota",
                "you must add a payment method",
            )
        ):
            return True
        if " 401" in msg or msg.startswith("401"):
            return True

        current = current.__cause__ or getattr(current, "__context__", None)

    return False


class AdaptiveLLMProvider(BaseLLMProvider):
    """Try OpenAI; on billing/auth/quota failure, use spaCy for this worker."""

    name = "openai"

    def __init__(self) -> None:
        cfg = getattr(settings, "NEWS_GRAPH", {})
        self._openai: Optional[BaseLLMProvider] = None
        self._spacy: Optional[BaseLLMProvider] = None
        self._mock = MockLLMProvider()

        if cfg.get("OPENAI_API_KEY"):
            try:
                from apps.ingestion.providers.openai_provider import OpenAIProvider

                self._openai = OpenAIProvider()
            except ExtractionError as exc:
                logger.warning("OpenAI provider unavailable at startup: %s", exc)

    @property
    def active_name(self) -> str:
        """Name shown in the UI / logs (may differ from ``name`` after fallback)."""

        backend = _active_backend
        if backend:
            return backend
        if self._openai is not None:
            return "openai"
        if self._spacy_provider() is not None:
            return "spacy"
        return "mock"

    def _spacy_provider(self) -> Optional[BaseLLMProvider]:
        if self._spacy is not None:
            return self._spacy
        try:
            from apps.ingestion.providers.spacy_provider import SpacyNERProvider

            self._spacy = SpacyNERProvider()
        except ExtractionError as exc:
            logger.warning("spaCy provider unavailable: %s", exc)
            return None
        return self._spacy

    def _delegate(self, provider: BaseLLMProvider, *, system_prompt: str, user_prompt: str) -> str:
        global _active_backend
        _active_backend = provider.name
        self.name = provider.name
        return provider.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        global _active_backend

        if _active_backend == "spacy":
            spacy = self._spacy_provider()
            if spacy is not None:
                return spacy.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
            return self._delegate(self._mock, system_prompt=system_prompt, user_prompt=user_prompt)

        if _active_backend == "mock":
            return self._mock.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)

        if self._openai is None:
            logger.info("No OpenAI key configured; using spaCy or mock for extraction")
            spacy = self._spacy_provider()
            if spacy is not None:
                return self._delegate(spacy, system_prompt=system_prompt, user_prompt=user_prompt)
            return self._delegate(self._mock, system_prompt=system_prompt, user_prompt=user_prompt)

        try:
            result = self._openai.complete_json(
                system_prompt=system_prompt, user_prompt=user_prompt
            )
            _active_backend = "openai"
            self.name = "openai"
            return result
        except ExtractionError as exc:
            if not _should_fallback_to_spacy(exc):
                raise
            logger.warning(
                "OpenAI extraction failed (%s); switching to spaCy for this worker",
                exc,
            )
            spacy = self._spacy_provider()
            if spacy is None:
                logger.warning("spaCy unavailable after OpenAI failure; using mock")
                return self._delegate(self._mock, system_prompt=system_prompt, user_prompt=user_prompt)
            return self._delegate(spacy, system_prompt=system_prompt, user_prompt=user_prompt)
