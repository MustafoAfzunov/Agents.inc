"""Crawler unit tests.

We don't hit the network; instead we feed canned HTML into ``parse_listing``
and assert that only canonical article URLs survive.
"""
from __future__ import annotations

from apps.ingestion.crawlers.techcrunch import TechCrunchCrawler
from apps.ingestion.tests.fixtures import LISTING_HTML


def test_parse_listing_filters_to_article_urls():
    crawler = TechCrunchCrawler(topic_url="https://techcrunch.com/tag/openai/")
    results = list(crawler.parse_listing(LISTING_HTML))

    urls = [r.url for r in results]
    assert "https://techcrunch.com/2025/01/15/openai-launches-new-feature/" in urls
    assert "https://techcrunch.com/2025/01/16/altman-talks-future/" in urls
    # Listing-only URLs must not slip through.
    assert all("/category/" not in u and "/events/" not in u for u in urls)
    # And duplicates are collapsed.
    assert len(urls) == len(set(urls)) == 2


def test_listing_url_for_page():
    crawler = TechCrunchCrawler(topic_url="https://techcrunch.com/tag/openai/")
    assert crawler.listing_url_for_page(1) == "https://techcrunch.com/tag/openai/"
    assert crawler.listing_url_for_page(2) == "https://techcrunch.com/tag/openai/page/2/"
