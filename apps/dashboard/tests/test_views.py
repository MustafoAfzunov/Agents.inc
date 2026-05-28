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
