"""OpenAI implementation of :class:`BaseLLMProvider`.

Imported lazily so the project still works (and tests still run) when the
``openai`` package isn't installed or no API key is configured.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

from apps.common.exceptions import ExtractionError
from apps.ingestion.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        cfg = getattr(settings, "NEWS_GRAPH", {})
        self.api_key = api_key or cfg.get("OPENAI_API_KEY", "")
        self.model = model or cfg.get("OPENAI_MODEL", "gpt-4o-mini")
        if not self.api_key:
            raise ExtractionError(
                "OPENAI_API_KEY is not configured; cannot use OpenAIProvider."
            )

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            from openai import OpenAI  # local import to keep import cost off the hot path
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ExtractionError("openai package is not installed") from exc

        client = OpenAI(api_key=self.api_key)
        try:
            response = client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:  # pragma: no cover - network call
            logger.exception("OpenAI request failed")
            raise ExtractionError(f"OpenAI request failed: {exc}") from exc

        try:
            return response.choices[0].message.content or ""
        except (AttributeError, IndexError) as exc:  # pragma: no cover - defensive
            raise ExtractionError("Malformed OpenAI response") from exc
