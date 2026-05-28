"""Crawler abstraction.

A *crawler* is responsible for walking a publisher's topic/listing pages
and yielding article URLs. Adding a new news source means writing a new
``ListingCrawler`` subclass — nothing else in the pipeline changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from apps.ingestion.dto import ArticleListing


class ListingCrawler(ABC):
    """Walks a topic/listing page and produces article references."""

    #: Stable identifier used to tag stored articles (e.g. ``"techcrunch"``).
    source: str = "generic"

    @abstractmethod
    def fetch_listing_page(self, page: int) -> str:
        """Return the raw HTML of *page* of the listing."""

    @abstractmethod
    def parse_listing(self, html: str) -> Iterable[ArticleListing]:
        """Extract article URLs from a listing-page HTML document."""

    def crawl_pages(self, pages: int) -> list[ArticleListing]:
        """Crawl ``pages`` listing pages and return a de-duplicated list.

        Concrete crawlers should rarely need to override this — the loop is
        identical regardless of source.
        """

        seen: set[str] = set()
        results: list[ArticleListing] = []
        for page in range(1, max(1, pages) + 1):
            html = self.fetch_listing_page(page)
            for item in self.parse_listing(html):
                if item.url not in seen:
                    seen.add(item.url)
                    results.append(item)
        return results
