"""Deterministic offline provider.

Used as the default in dev/test so the pipeline can be exercised end-to-end
without an API key. It performs a lightweight regex/heuristic pass to find
capitalised name-like spans plus a few hard-coded relationship verbs around
those spans. It will never be as good as a real LLM — that's the point: it
exists so we can test plumbing, not to compete on extraction quality.
"""
from __future__ import annotations

import json
import re
from typing import Iterable

from apps.common.utils.text import is_probable_person_name
from apps.ingestion.providers.base import BaseLLMProvider

# A small set of relationship cues. The exact verb in the sentence becomes
# the ``relationship_type`` of the resulting edge, which keeps the output
# realistic even if not exhaustive.
_RELATIONSHIP_VERBS = (
    "criticizes",
    "criticized",
    "partners",
    "partnered",
    "sued",
    "sues",
    "praised",
    "praises",
    "founded",
    "co-founded",
    "left",
    "joined",
    "replaced",
    "supports",
    "supported",
    "backs",
    "backed",
    "met",
    "called",
    "accused",
)

_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _extract_names(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for match in _NAME_RE.finditer(text):
        name = match.group(1).strip()
        # Use the shared validator so dates, org names and sentence-leading
        # stopwords are rejected here, before they ever become a Person.
        if not is_probable_person_name(name):
            continue
        if name in seen:
            continue
        seen.add(name)
        candidates.append(name)
    return candidates


def _split_prompt(user_prompt: str) -> tuple[str, str, str]:
    """Split the rendered prompt into ``(title, author, content)``.

    The extractor builds the prompt from a fixed template:

        Article URL: ...
        TITLE: <title>
        AUTHOR: <author>

        CONTENT:
        <content>

        Return JSON with exactly this shape:
        { ... }

    We pull out each region separately so (a) the JSON-shape example never
    leaks into extraction, and (b) the header labels / author line cannot be
    mistaken for article sentences (which previously produced polluted
    evidence sentences and spurious author edges).
    """

    text = user_prompt
    marker = "Return JSON with exactly this shape:"
    if marker in text:
        text = text.split(marker, 1)[0]

    title = ""
    author = ""
    title_match = re.search(r"^TITLE:\s*(.+)$", text, flags=re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    author_match = re.search(r"^AUTHOR:\s*(.+)$", text, flags=re.MULTILINE)
    if author_match:
        author = author_match.group(1).strip()

    content = ""
    content_match = re.search(r"CONTENT:\s*(.*)$", text, flags=re.DOTALL)
    if content_match:
        content = content_match.group(1).strip()

    return title, author, content


def _find_relationships(sentences: Iterable[str]) -> list[dict]:
    rels: list[dict] = []
    for sentence in sentences:
        names = _extract_names(sentence)
        if len(names) < 2:
            continue
        lowered = sentence.lower()
        verb_hit = next((v for v in _RELATIONSHIP_VERBS if f" {v} " in f" {lowered} "), None)
        rel_type = verb_hit or "mentioned with"
        # Pair every two consecutive names within the sentence.
        for i in range(len(names) - 1):
            rels.append(
                {
                    "source": names[i],
                    "target": names[i + 1],
                    "type": rel_type,
                    "explanation": sentence.strip(),
                    "evidence_sentence": sentence.strip(),
                    "confidence": 0.4 if verb_hit else 0.2,
                }
            )
    return rels


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        title, author, content = _split_prompt(user_prompt)

        # Relationships and evidence sentences come from the article body and
        # title only — never the header labels — so quotes stay clean.
        body = f"{title}. {content}" if title else content
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(body) if s.strip()]

        people = list({name for s in sentences for name in _extract_names(s)})
        if author and is_probable_person_name(author) and author not in people:
            people.append(author)

        relationships = _find_relationships(sentences)
        return json.dumps({"people": people, "relationships": relationships})
