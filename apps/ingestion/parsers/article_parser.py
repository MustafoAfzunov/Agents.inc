"""Turn a fetched HTML article into a structured ``ParsedArticle``.

We use **trafilatura** as the primary extractor (it handles boilerplate and
metadata well) and fall back to a small BeautifulSoup heuristic so the
parser keeps working even on pages trafilatura misclassifies.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import trafilatura
from bs4 import BeautifulSoup
from django.conf import settings

from apps.common.exceptions import CrawlError, ParseError
from apps.common.utils.http import HttpClient
from apps.ingestion.dto import ParsedArticle

logger = logging.getLogger(__name__)


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class ArticleParser:
    """Fetch + parse a single article URL into a :class:`ParsedArticle`."""

    def __init__(
        self,
        *,
        http_client: Optional[HttpClient] = None,
        source: str = "techcrunch",
    ) -> None:
        self.http = http_client or HttpClient()
        self.source = source

    # -- public API ------------------------------------------------------

    def fetch_and_parse(self, url: str) -> ParsedArticle:
        try:
            html = self.http.get(url).text
        except CrawlError as exc:
            raise ParseError(f"Cannot fetch {url}: {exc}") from exc
        return self.parse(url, html)

    def parse(self, url: str, html: str) -> ParsedArticle:
        if not html or not html.strip():
            raise ParseError(f"Empty HTML for {url}")

        title = ""
        author = ""
        published_at: Optional[datetime] = None
        content = ""
        summary = ""

        # 1. Trafilatura with metadata. Best signal when it works.
        try:
            tjson = trafilatura.extract(
                html,
                url=url,
                output_format="json",
                with_metadata=True,
                include_comments=False,
                favor_recall=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("trafilatura crashed on %s: %s", url, exc)
            tjson = None

        if tjson:
            try:
                meta = json.loads(tjson)
            except json.JSONDecodeError:
                meta = {}
            title = (meta.get("title") or "").strip()
            author = (meta.get("author") or "").strip()
            content = (meta.get("text") or "").strip()
            summary = (meta.get("description") or "").strip()
            published_at = _parse_iso_datetime(meta.get("date"))

        # 2. BeautifulSoup fallback / fill-in.
        soup = BeautifulSoup(html, "html.parser")
        if not title:
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            else:
                og = soup.find("meta", attrs={"property": "og:title"})
                if og and og.get("content"):
                    title = og["content"].strip()
        if not author:
            meta_author = soup.find("meta", attrs={"name": "author"})
            if meta_author and meta_author.get("content"):
                author = meta_author["content"].strip()
        if published_at is None:
            meta_time = soup.find("meta", attrs={"property": "article:published_time"})
            if meta_time and meta_time.get("content"):
                published_at = _parse_iso_datetime(meta_time["content"])
        if not content:
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            content = "\n\n".join(p for p in paragraphs if p)

        if not content or not title:
            raise ParseError(f"Could not extract title/content for {url}")

        cfg = getattr(settings, "NEWS_GRAPH", {})
        max_chars = cfg.get("EXTRACTION_MAX_CHARS", 12000)
        if len(content) > max_chars:
            content = content[:max_chars]

        return ParsedArticle(
            url=url,
            title=title,
            content=content,
            author_name=author,
            published_at=published_at,
            summary=summary,
            source=self.source,
        )
