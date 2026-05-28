"""LLM-driven relationship extractor.

The extractor's only job is: (parsed article) → (structured ExtractionResult).
It is decoupled from persistence (the resolver/merger do that) and from the
LLM vendor (any :class:`BaseLLMProvider` works).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from apps.common.exceptions import ExtractionError
from apps.common.utils.text import is_probable_person_name
from apps.ingestion.dto import (
    ExtractedRelationship,
    ExtractionResult,
    ParsedArticle,
)
from apps.ingestion.extractors.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from apps.ingestion.providers.base import BaseLLMProvider
from apps.ingestion.providers.factory import build_llm_provider

logger = logging.getLogger(__name__)


class LLMRelationshipExtractor:
    """Turn a :class:`ParsedArticle` into an :class:`ExtractionResult`."""

    def __init__(self, provider: Optional[BaseLLMProvider] = None) -> None:
        self.provider = provider or build_llm_provider()

    def extract(self, article: ParsedArticle) -> ExtractionResult:
        prompt = USER_PROMPT_TEMPLATE.format(
            url=article.url,
            title=article.title,
            author=article.author_name or "",
            content=article.content,
        )
        try:
            raw = self.provider.complete_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
            )
        except ExtractionError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise ExtractionError(f"LLM call failed: {exc}") from exc

        return self._parse(raw)

    # -- internals -------------------------------------------------------

    def _parse(self, raw: str) -> ExtractionResult:
        if not raw:
            raise ExtractionError("Empty LLM response")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            # One retry on a trivial wrapping issue (e.g. ```json ... ```)
            cleaned = raw.strip().strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                payload = json.loads(cleaned)
            except json.JSONDecodeError:
                raise ExtractionError(f"LLM did not return valid JSON: {exc}") from exc

        # Filter the people list down to probable personal names. This is the
        # cheap safety net that keeps dates / org names / sentence fragments
        # out of the graph regardless of which provider produced the output.
        people = [
            str(p).strip()
            for p in payload.get("people", [])
            if str(p).strip() and is_probable_person_name(str(p).strip())
        ]
        valid_people = set(people)

        rels_raw = payload.get("relationships") or []
        relationships: list[ExtractedRelationship] = []
        for item in rels_raw:
            try:
                rel = ExtractedRelationship(
                    source=str(item["source"]).strip(),
                    target=str(item["target"]).strip(),
                    relationship_type=str(item.get("type") or item.get("relationship_type") or "").strip(),
                    explanation=str(item.get("explanation") or "").strip(),
                    evidence_sentence=str(item.get("evidence_sentence") or "").strip(),
                    confidence=float(item.get("confidence") or 0.0),
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping malformed relationship %r: %s", item, exc)
                continue
            if not rel.source or not rel.target or rel.source == rel.target:
                continue
            if not rel.relationship_type:
                continue
            # Drop edges whose endpoints aren't probable people.
            if not is_probable_person_name(rel.source) or not is_probable_person_name(rel.target):
                continue
            relationships.append(rel)

        # Ensure every (valid) relationship endpoint is in the people list.
        for rel in relationships:
            for name in (rel.source, rel.target):
                if name not in valid_people:
                    people.append(name)
                    valid_people.add(name)

        return ExtractionResult(people=people, relationships=relationships)
