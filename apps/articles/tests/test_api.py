"""API-level tests for the article + rescan endpoints.

We patch the pipeline's internal parsing/crawling so no HTTP hits the wire.
The view's job is only validation + delegation; this test pins that contract.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.ingestion.dto import ArticleListing, ParsedArticle


def _stub_parsed(url: str) -> ParsedArticle:
    return ParsedArticle(
        url=url,
        title="Sam Altman meets Satya Nadella",
        content=(
            "Sam Altman meets Satya Nadella at a press event. "
            "Altman announced new Azure investments."
        ),
        author_name="Jane Reporter",
        source="techcrunch",
    )


@pytest.mark.django_db
def test_post_articles_happy_path(api_client):
    url = "https://techcrunch.com/2025/01/16/altman-nadella/"
    with patch(
        "apps.ingestion.parsers.article_parser.ArticleParser.fetch_and_parse",
        return_value=_stub_parsed(url),
    ):
        response = api_client.post("/articles/", {"url": url}, format="json")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["article_url"] == url
    assert body["created_article"] is True
    assert body["people_created"] >= 2


@pytest.mark.django_db
def test_post_articles_rejects_bad_url(api_client):
    response = api_client.post("/articles/", {"url": "not-a-url"}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_rescan_runs_with_mocked_crawler(api_client):
    url = "https://techcrunch.com/2025/01/17/openai-roundup/"
    with patch(
        "apps.ingestion.crawlers.techcrunch.TechCrunchCrawler.crawl_pages",
        return_value=[ArticleListing(url=url, title="OpenAI roundup")],
    ), patch(
        "apps.ingestion.parsers.article_parser.ArticleParser.fetch_and_parse",
        return_value=_stub_parsed(url),
    ):
        response = api_client.post("/rescan/", {"pages": 2}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["pages_scanned"] == 2
    assert body["articles_seen"] == 1
    assert body["articles_ingested"] == 1


@pytest.mark.django_db
def test_post_rescan_rejects_bad_pages(api_client):
    response = api_client.post("/rescan/", {"pages": 0}, format="json")
    assert response.status_code == 400
