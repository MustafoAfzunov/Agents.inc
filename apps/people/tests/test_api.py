"""Tests for the people read APIs."""
from __future__ import annotations

import pytest

from apps.articles.models import Article
from apps.people.models import Person
from apps.relationships.models import Relationship


@pytest.fixture
def graph_fixture(db):
    article = Article.objects.create(
        url="https://techcrunch.com/2025/01/15/x/",
        title="Sample article",
        content="...",
        source="techcrunch",
    )
    altman = Person.objects.create(canonical_name="Sam Altman", normalized_name="sam altman")
    musk = Person.objects.create(canonical_name="Elon Musk", normalized_name="elon musk")
    Relationship.objects.create(
        source_person=altman,
        target_person=musk,
        relationship_type="criticizes",
        explanation="Altman criticized Musk.",
        evidence_sentence="Altman criticized Musk over xAI.",
        article=article,
        confidence=0.8,
    )
    return {"article": article, "altman": altman, "musk": musk}


@pytest.mark.django_db
def test_list_people_is_paginated(api_client, graph_fixture):
    response = api_client.get("/people/?page_size=1")
    assert response.status_code == 200
    body = response.json()
    assert "results" in body and "count" in body
    assert body["count"] == 2
    assert len(body["results"]) == 1


@pytest.mark.django_db
def test_person_detail_returns_relationships_with_provenance(api_client, graph_fixture):
    altman = graph_fixture["altman"]
    response = api_client.get(f"/people/{altman.id}/")
    assert response.status_code == 200
    body = response.json()
    assert body["canonical_name"] == "Sam Altman"
    assert len(body["relationships"]) == 1
    edge = body["relationships"][0]
    assert edge["relationship_type"] == "criticizes"
    assert edge["evidence_sentence"]
    assert edge["article"]["url"].startswith("https://techcrunch.com/")


@pytest.mark.django_db
def test_person_detail_404(api_client):
    response = api_client.get("/people/9999/")
    assert response.status_code == 404
