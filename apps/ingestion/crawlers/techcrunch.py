"""TechCrunch topic-page crawler.

Implements ``ListingCrawler`` for ``https://techcrunch.com/tag/<topic>/``.
The parser is intentionally permissive: TechCrunch has changed its listing
markup multiple times, so we look for any ``<a>`` whose href matches the
canonical article URL shape ``/<YYYY>/<MM>/<DD>/<slug>/``.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from django.conf import settings

from apps.common.utils.http import HttpClient
from apps.ingestion.crawlers.base import ListingCrawler
from apps.ingestion.dto import ArticleListing

logger = logging.getLogger(__name__)

ARTICLE_URL_RE = re.compile(r"^https?://techcrunch\.com/\d{4}/\d{2}/\d{2}/[^/]+/?$")


class TechCrunchCrawler(ListingCrawler):
    source = "techcrunch"

    def __init__(
        self,
        *,
        topic_url: Optional[str] = None,
        http_client: Optional[HttpClient] = None,
    ) -> None:
        cfg = getattr(settings, "NEWS_GRAPH", {})
        self.topic_url = (topic_url or cfg.get("TECHCRUNCH_TOPIC_URL", "")).rstrip("/") + "/"
        self.http = http_client or HttpClient()

    def listing_url_for_page(self, page: int) -> str:
        if page <= 1:
            return self.topic_url
        return f"{self.topic_url}page/{page}/"

    def fetch_listing_page(self, page: int) -> str:
        url = self.listing_url_for_page(page)
        logger.info("Fetching TechCrunch listing page %s -> %s", page, url)
        return self.http.get(url).text

    def parse_listing(self, html: str) -> Iterable[ArticleListing]:
        soup = BeautifulSoup(html, "html.parser")
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href:
                continue
            absolute = urljoin(self.topic_url, href)
            if not ARTICLE_URL_RE.match(absolute):
                continue
            if urlparse(absolute).path.endswith("/"):
                normalized = absolute
            else:
                normalized = absolute + "/"
            if normalized in seen:
                continue
            seen.add(normalized)
            title = (anchor.get_text() or "").strip() or None
            yield ArticleListing(url=normalized, title=title)
