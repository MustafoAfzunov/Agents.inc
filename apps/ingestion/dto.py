"""Data-transfer objects used between pipeline stages.

These are plain dataclasses — explicitly *not* Django models — because each
stage of the pipeline (crawler → parser → extractor → resolver → merger)
should stay independent of persistence. That separation keeps every stage
unit-testable without touching the database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class ArticleListing:
    """A single article reference scraped from a topic listing page."""

    url: str
    title: Optional[str] = None


@dataclass
class ParsedArticle:
    """Result of fetching + parsing a single article URL."""

    url: str
    title: str
    content: str
    author_name: str = ""
    published_at: Optional[datetime] = None
    summary: str = ""
    source: str = "techcrunch"


@dataclass(frozen=True)
class ExtractedRelationship:
    source: str
    target: str
    relationship_type: str
    explanation: str
    evidence_sentence: str
    confidence: float = 0.0


@dataclass
class ExtractionResult:
    """Structured LLM output for one article."""

    people: List[str] = field(default_factory=list)
    relationships: List[ExtractedRelationship] = field(default_factory=list)


@dataclass
class IngestionReport:
    """Summary of what the pipeline did for a single article."""

    article_url: str
    created_article: bool = False
    people_created: int = 0
    people_matched: int = 0
    relationships_created: int = 0
    relationships_skipped: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class RescanReport:
    """Aggregated outcome of a multi-page rescan."""

    pages_scanned: int = 0
    articles_seen: int = 0
    articles_ingested: int = 0
    articles_skipped: int = 0
    people_created: int = 0
    relationships_created: int = 0
    errors: List[str] = field(default_factory=list)
