"""Tiny text helpers used by the resolver and parsers.

Kept dependency-free on purpose so they remain trivial to unit-test.
"""
from __future__ import annotations

import re
import unicodedata

# Honorifics / role prefixes we strip when normalizing names. The resolver
# uses these so "OpenAI's CEO Sam Altman" reduces nicely toward "sam altman".
_NAME_PREFIXES = {
    "mr", "mrs", "ms", "miss", "mx", "dr", "prof", "sir", "dame",
    "ceo", "cto", "cfo", "coo", "president", "vp", "founder", "co-founder",
}

_NON_NAME_CHARS = re.compile(r"[^\w\s'-]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")
# Possessive tokens like "openai's" or "twitter's" — common in org-prefixed
# references ("OpenAI's CEO Sam Altman"). Drop them outright.
_POSSESSIVE_RE = re.compile(r".+'s$")


def strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def normalize_name(name: str) -> str:
    """Return a lower-case, accent-stripped, prefix-free version of *name*.

    The result is suitable as a deterministic hash key for entity resolution.
    """

    if not name:
        return ""
    cleaned = strip_accents(name).lower()
    cleaned = _NON_NAME_CHARS.sub(" ", cleaned)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    tokens = [
        t
        for t in cleaned.split(" ")
        if t and t not in _NAME_PREFIXES and not _POSSESSIVE_RE.match(t)
    ]
    return " ".join(tokens)


def name_tokens(name: str) -> list[str]:
    """Return the normalized tokens of *name* (e.g. ["sam", "altman"])."""

    normalized = normalize_name(name)
    return normalized.split(" ") if normalized else []


def short_hash(value: str, length: int = 12) -> str:
    """Stable short hash for logging and de-duplication keys."""

    import hashlib

    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]
