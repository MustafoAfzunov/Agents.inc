"""End-to-end tests for the article pipeline using the deterministic mock LLM.

These confirm that:
- A clean ingest creates the article + people + relationships.
- A second ingest of the same URL is fully idempotent.
- The author is always materialised as a Person.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.articles.models import Article
from apps.ingestion.dto import ParsedArticle
from apps.ingestion.pipelines.article_pipeline import ArticleIngestionPipeline
from apps.people.models import Person
from apps.relationships.models import Relationship


def _make_parsed() -> ParsedArticle:
    return ParsedArticle(
        url="https://techcrunch.com/2025/01/15/openai-criticism/",
        title="Sam Altman criticizes Elon Musk over xAI strategy",
        content=(
            "Sam Altman criticizes Elon Musk after Musk launched a new xAI initiative. "
            "Sam Altman partners with Satya Nadella to expand Azure investments. "
            "Altman declined to comment further."
        ),
        author_name="Jane Reporter",
        source="techcrunch",
    )


@pytest.mark.django_db
def test_pipeline_creates_full_graph_first_time():
    parsed = _make_parsed()
    pipeline = ArticleIngestionPipeline()
    # Skip the network parse — feed the parsed object directly.
    report = pipeline.ingest_parsed(parsed)

    assert report.created_article is True
    assert Article.objects.filter(url=parsed.url).count() == 1
    assert Person.objects.count() >= 3  # Altman, Musk, Nadella, (+ author)
    assert Relationship.objects.count() >= 1
    assert any(p.canonical_name == "Jane Reporter" for p in Person.objects.all())


@pytest.mark.django_db
def test_pipeline_is_idempotent_on_reingest():
    parsed = _make_parsed()
    pipeline = ArticleIngestionPipeline()
    first = pipeline.ingest_parsed(parsed)
    second = pipeline.ingest_parsed(parsed)

    assert first.created_article is True
    assert second.created_article is False
    # Nothing new should be created on the second pass.
    assert second.relationships_created == 0
    assert Article.objects.count() == 1
    # Person count must not double.
    person_count = Person.objects.count()
    pipeline.ingest_parsed(parsed)
    assert Person.objects.count() == person_count


@pytest.mark.django_db
def test_pipeline_collapses_surface_forms_into_one_person():
    parsed = _make_parsed()
    pipeline = ArticleIngestionPipeline()
    pipeline.ingest_parsed(parsed)
    altmans = Person.objects.filter(normalized_name="sam altman")
    assert altmans.count() == 1
