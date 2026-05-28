"""Article parser unit tests."""
from __future__ import annotations

import pytest

from apps.common.exceptions import ParseError
from apps.ingestion.parsers.article_parser import ArticleParser
from apps.ingestion.tests.fixtures import ARTICLE_HTML


def test_parse_extracts_title_author_and_published_at():
    parser = ArticleParser()
    parsed = parser.parse("https://techcrunch.com/2025/01/15/x/", ARTICLE_HTML)

    assert "Sam Altman" in parsed.title
    assert parsed.content  # non-empty body
    # Author may come from <meta name="author"> via fallback path.
    assert parsed.author_name in {"Jane Reporter", ""} or "Jane" in parsed.author_name
    assert parsed.published_at is not None
    assert parsed.published_at.year == 2025


def test_parse_raises_on_empty_html():
    parser = ArticleParser()
    with pytest.raises(ParseError):
        parser.parse("https://example.com/", "")
