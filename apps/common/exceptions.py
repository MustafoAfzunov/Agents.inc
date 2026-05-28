"""Domain-level exceptions used across the ingestion stack."""
from __future__ import annotations


class NewsGraphError(Exception):
    """Base class for any domain error raised by this project."""


class CrawlError(NewsGraphError):
    """Raised when fetching a remote page fails after retries."""


class ParseError(NewsGraphError):
    """Raised when an HTML page cannot be parsed into an Article."""


class ExtractionError(NewsGraphError):
    """Raised when the LLM extraction step fails or returns invalid output."""


class ResolutionError(NewsGraphError):
    """Raised by the entity resolver for unrecoverable resolution issues."""
