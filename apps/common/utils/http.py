"""Thin wrapper around ``requests`` with retries and a sensible UA.

Centralising HTTP here means every crawler/fetcher gets the same retry,
timeout and user-agent treatment without duplicating logic.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings

from apps.common.exceptions import CrawlError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HttpResponse:
    url: str
    status_code: int
    text: str


class HttpClient:
    """Small, retrying HTTP GET client used by all crawlers/fetchers."""

    def __init__(
        self,
        *,
        timeout: Optional[float] = None,
        user_agent: Optional[str] = None,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        session: Optional[requests.Session] = None,
    ) -> None:
        cfg = getattr(settings, "NEWS_GRAPH", {})
        self.timeout = timeout or cfg.get("HTTP_TIMEOUT_SECONDS", 20)
        self.user_agent = user_agent or cfg.get("USER_AGENT", "news-graph-bot/1.0")
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._session = session or requests.Session()

    def get(self, url: str) -> HttpResponse:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug("GET %s (attempt %s)", url, attempt + 1)
                response = self._session.get(
                    url,
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                )
                if response.status_code >= 500:
                    raise CrawlError(f"Server error {response.status_code} for {url}")
                response.raise_for_status()
                return HttpResponse(url=url, status_code=response.status_code, text=response.text)
            except (requests.RequestException, CrawlError) as exc:
                last_exc = exc
                logger.warning("GET %s failed (attempt %s): %s", url, attempt + 1, exc)
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (2 ** attempt))
        raise CrawlError(f"Failed to GET {url}: {last_exc}") from last_exc
