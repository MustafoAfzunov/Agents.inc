"""Smoke tests for the template dashboard."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.people.models import Person


@pytest.mark.django_db
def test_dashboard_home(client):
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200
    assert b"Rescan topic listing" in response.content


@pytest.mark.django_db
def test_people_list_empty(client):
    response = client.get(reverse("dashboard:people-list"))
    assert response.status_code == 200
    assert b"No people yet" in response.content


@pytest.mark.django_db
def test_people_search_filters(client):
    Person.objects.create(canonical_name="Sam Altman", normalized_name="sam altman")
    Person.objects.create(canonical_name="Elon Musk", normalized_name="elon musk")
    response = client.get(reverse("dashboard:people-list"), {"q": "altman"})
    assert response.status_code == 200
    assert b"Sam Altman" in response.content
    assert b"Elon Musk" not in response.content


@pytest.mark.django_db
def test_articles_list(client):
    from apps.articles.models import Article

    Article.objects.create(
        url="https://techcrunch.com/2025/01/15/x/",
        title="An OpenAI Story",
        author_name="Jane Reporter",
        source="techcrunch",
    )
    response = client.get(reverse("dashboard:articles-list"))
    assert response.status_code == 200
    assert b"An OpenAI Story" in response.content
    assert b"Jane Reporter" in response.content


@pytest.mark.django_db
def test_articles_list_empty(client):
    response = client.get(reverse("dashboard:articles-list"))
    assert response.status_code == 200
    assert b"No articles yet" in response.content


@pytest.mark.django_db
def test_person_detail(client):
    person = Person.objects.create(
        canonical_name="Sam Altman",
        normalized_name="sam altman",
    )
    response = client.get(reverse("dashboard:person-detail", kwargs={"pk": person.pk}))
    assert response.status_code == 200
    assert b"Sam Altman" in response.content


@pytest.mark.django_db
def test_dashboard_ingest_form(client):
    url = "https://techcrunch.com/2025/01/16/example/"
    with patch("apps.dashboard.views.ArticleIngestService.ingest") as mock_ingest:
        from apps.ingestion.dto import IngestionReport

        mock_ingest.return_value = IngestionReport(
            article_url=url,
            created_article=True,
            people_created=1,
        )
        response = client.post(
            reverse("dashboard:home"),
            {"action": "ingest", "url": url},
        )
    assert response.status_code == 200
    assert b"people_created" in response.content or b"People created" in response.content
