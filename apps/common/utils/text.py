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

# --- Person-name validation -------------------------------------------------
# Heuristics that filter out the most common non-person noise produced by a
# naive extractor (sentence-leading capitalised words, dates, org names). This
# runs on EVERY provider's output (mock and OpenAI) as a cheap safety net.

# Words that frequently start a sentence and get mis-captured as a first name.
_LEADING_STOPWORDS = {
    "the", "a", "an", "after", "before", "on", "in", "at", "and", "but", "or",
    "so", "as", "if", "when", "while", "then", "this", "that", "these", "those",
    "his", "her", "their", "its", "our", "your", "my", "is", "was", "were",
    "for", "to", "of", "with", "by", "from", "during", "since", "until",
    "meanwhile", "however", "instead", "also", "now", "today", "yesterday",
    "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "january", "february", "march", "april", "may",
    "june", "july", "august", "september", "october", "november", "december",
}

# Tokens that strongly indicate an organisation / product, not a person.
_ORG_TOKENS = {
    "inc", "corp", "corporation", "llc", "ltd", "co", "company", "group",
    "capital", "ventures", "partners", "management", "holdings", "fund",
    "bank", "university", "institute", "labs", "lab", "systems", "services",
    "technologies", "technology", "ai", "openai", "google", "microsoft",
    "amazon", "apple", "meta", "tesla", "spacex", "anthropic", "nvidia",
    "store", "marketplace", "security", "account", "wave", "global", "news",
    "times", "journal", "post", "press", "media", "studios", "foundation",
    "association", "department", "agency", "commission", "court", "senate",
    # Common places + publications + products that a naive extractor captures.
    "york", "yorker", "francisco", "valley", "angeles", "diego", "jose",
    "insider", "verge", "bloomberg", "reuters", "axios", "wired", "forbes",
    "claude", "gemini", "copilot", "chatgpt", "gpt", "code", "opus", "sonnet",
    "street", "wall", "silicon",
}


def is_probable_person_name(name: str) -> bool:
    """Return True if *name* looks like a real personal name.

    Deliberately conservative: it rejects obvious non-people (dates,
    sentence-leading stopwords, organisation/product names, single tokens,
    embedded newlines) while keeping normal 2–4 token human names.
    """

    if not name:
        return False
    raw = name.strip()
    # Multi-line spans (e.g. "Amazon\nIs") are never names.
    if "\n" in raw or "\r" in raw:
        return False
    # The example placeholder from the extraction prompt.
    if raw.lower() in {"full name", "first last", "john doe"}:
        return False

    tokens = raw.split()
    if not (2 <= len(tokens) <= 4):
        return False

    lowered = [t.lower().strip(".,'\"") for t in tokens]

    if lowered[0] in _LEADING_STOPWORDS:
        return False
    if any(tok in _ORG_TOKENS for tok in lowered):
        return False

    # Every token must start with an uppercase letter (allow internal
    # apostrophes / hyphens, e.g. O'Brien, Jean-Luc).
    for tok in tokens:
        if not tok[:1].isupper():
            return False
        if not re.match(r"^[A-Z][A-Za-z'’\-]*$", tok):
            return False
    return True


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
