"""Application service for ``POST /rescan``."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings

from apps.common.exceptions import NewsGraphError
from apps.ingestion.dto import RescanReport
from apps.ingestion.pipelines.rescan_pipeline import RescanPipeline

logger = logging.getLogger(__name__)


class InvalidRescanRequest(NewsGraphError):
    """Raised when the caller sends a bad ``pages`` value."""


@dataclass
class RescanService:
    pipeline: RescanPipeline = field(default_factory=RescanPipeline)
    max_pages: int = 25

    def run(self, *, pages: Optional[int] = None) -> RescanReport:
        cfg = getattr(settings, "NEWS_GRAPH", {})
        if pages is None:
            pages = cfg.get("DEFAULT_RESCAN_PAGES", 2)
        if not isinstance(pages, int) or pages <= 0:
            raise InvalidRescanRequest("pages must be a positive integer")
        if pages > self.max_pages:
            raise InvalidRescanRequest(f"pages must be <= {self.max_pages}")
        logger.info("Rescan starting for %s pages", pages)
        return self.pipeline.run(pages=pages)
