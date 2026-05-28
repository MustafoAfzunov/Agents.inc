"""Application service for the ``POST /articles`` endpoint.

The view does *nothing* but validate input and call this. All policy
(deciding what counts as a valid TechCrunch URL, what default pipeline to
use, etc.) lives here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from apps.common.exceptions import NewsGraphError
from apps.ingestion.dto import IngestionReport
from apps.ingestion.pipelines.article_pipeline import ArticleIngestionPipeline

logger = logging.getLogger(__name__)


class InvalidArticleUrl(NewsGraphError):
    """Raised when the URL is missing/malformed."""


@dataclass
class ArticleIngestService:
    pipeline: ArticleIngestionPipeline = field(default_factory=ArticleIngestionPipeline)

    def ingest(self, url: str) -> IngestionReport:
        url = (url or "").strip()
        if not url:
            raise InvalidArticleUrl("url is required")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidArticleUrl(f"not a valid http(s) URL: {url!r}")
        logger.info("Ingesting article %s", url)
        return self.pipeline.ingest_url(url)
