"""spaCy-based offline extraction provider.

Unlike the regex ``MockLLMProvider``, this uses spaCy's statistical NER to
detect ``PERSON`` entities, so places / products / orgs ("Bay Area",
"Big Tech", "Baillie Gifford") are filtered out by an actual language model
rather than a hand-maintained blocklist — all without any API key.

Relationships are still derived heuristically: two people appearing in the
same sentence become an edge, typed by a relationship verb when one is
present. This is deliberately simple (the brief asks us not to over-engineer
extraction); the value here is dramatically cleaner *people* detection.

The model (``en_core_web_sm``) is loaded lazily and cached. If spaCy or the
model isn't available, the provider factory falls back to the mock provider.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Iterable

from apps.common.exceptions import ExtractionError
from apps.common.utils.text import is_probable_person_name
from apps.ingestion.providers.base import BaseLLMProvider
from apps.ingestion.providers.mock_provider import _RELATIONSHIP_VERBS
from apps.ingestion.providers.prompt_utils import split_prompt

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "en_core_web_sm"


@lru_cache(maxsize=2)
def _load_model(model_name: str = DEFAULT_MODEL):
    """Load and cache the spaCy pipeline (NER components only)."""

    import spacy  # local import so the dependency stays optional

    # Disable components we don't need to keep it fast.
    return spacy.load(model_name, disable=["lemmatizer", "textcat"])


def _clean_person(text: str) -> str:
    """Normalise a spaCy PERSON span into a comparable surface form."""

    return " ".join(text.replace("\n", " ").split()).strip(" '\"")


class SpacyNERProvider(BaseLLMProvider):
    name = "spacy"

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        try:
            self._nlp = _load_model(model_name)
        except Exception as exc:  # pragma: no cover - depends on env
            raise ExtractionError(
                f"Could not load spaCy model {model_name!r}: {exc}. "
                "Install it with: python -m spacy download en_core_web_sm"
            ) from exc

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        title, author, content = split_prompt(user_prompt)
        body = f"{title}. {content}" if title else content

        doc = self._nlp(body)

        people: list[str] = []
        seen: set[str] = set()

        def _register(name: str) -> str | None:
            cleaned = _clean_person(name)
            if not cleaned or not is_probable_person_name(cleaned):
                return None
            if cleaned not in seen:
                seen.add(cleaned)
                people.append(cleaned)
            return cleaned

        # Author is a known person; include them up front.
        if author:
            _register(author)

        relationships: list[dict] = []
        for sent in doc.sents:
            sent_people: list[str] = []
            for ent in sent.ents:
                if ent.label_ != "PERSON":
                    continue
                registered = _register(ent.text)
                if registered and registered not in sent_people:
                    sent_people.append(registered)

            if len(sent_people) < 2:
                continue

            sentence_text = sent.text.strip()
            lowered = f" {sentence_text.lower()} "
            verb_hit = next((v for v in _RELATIONSHIP_VERBS if f" {v} " in lowered), None)
            rel_type = verb_hit or "mentioned with"
            confidence = 0.5 if verb_hit else 0.25

            for i in range(len(sent_people) - 1):
                relationships.append(
                    {
                        "source": sent_people[i],
                        "target": sent_people[i + 1],
                        "type": rel_type,
                        "explanation": sentence_text,
                        "evidence_sentence": sentence_text,
                        "confidence": confidence,
                    }
                )

        return json.dumps({"people": people, "relationships": relationships})
