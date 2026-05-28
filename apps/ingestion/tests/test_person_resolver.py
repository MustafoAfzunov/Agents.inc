"""Tests for the canonical-person resolver.

These are the most important tests in the suite — the brief explicitly
calls out entity resolution quality. We cover:
- exact-match dedup
- alias-form dedup ("OpenAI's CEO Sam Altman" -> "Sam Altman")
- intra-article surname resolution ("Altman" right after "Sam Altman")
- global surname resolution when the surname is unique across DB
- ambiguous surname -> two separate people (no false merge)
"""
from __future__ import annotations

import pytest

from apps.ingestion.resolvers.person_resolver import PersonResolver
from apps.people.models import Person


@pytest.mark.django_db
def test_exact_match_dedup_creates_one_person():
    resolver = PersonResolver()
    a = resolver.resolve("Sam Altman")
    b = resolver.resolve("Sam Altman")
    assert a.pk == b.pk
    assert Person.objects.count() == 1


@pytest.mark.django_db
def test_aliases_are_recorded():
    resolver = PersonResolver()
    p = resolver.resolve("Sam Altman")
    resolver.resolve("OpenAI's CEO Sam Altman")
    p.refresh_from_db()
    assert "OpenAI's CEO Sam Altman" in p.aliases


@pytest.mark.django_db
def test_surname_within_article_resolves_to_full_name():
    resolver = PersonResolver()
    full = resolver.resolve("Sam Altman")
    bare = resolver.resolve("Altman")
    assert bare.pk == full.pk
    assert Person.objects.count() == 1


@pytest.mark.django_db
def test_global_surname_resolves_when_unique():
    """Even across articles, a unique-surname bare reference should merge."""

    first_resolver = PersonResolver()
    full = first_resolver.resolve("Sam Altman")

    second_resolver = PersonResolver()  # new article -> fresh local cache
    bare = second_resolver.resolve("Altman")
    assert bare.pk == full.pk


@pytest.mark.django_db
def test_ambiguous_surname_creates_distinct_person():
    """Two different people share the surname -> bare ref doesn't merge."""

    resolver = PersonResolver()
    resolver.resolve("Sam Altman")
    resolver.resolve("Jack Altman")
    # Fresh cache, only the surname.
    new_resolver = PersonResolver()
    bare = new_resolver.resolve("Altman")
    assert bare.canonical_name == "Altman"
    assert Person.objects.count() == 3


@pytest.mark.django_db
def test_resolve_many_orders_long_names_first():
    resolver = PersonResolver()
    by_name = resolver.resolve_many(["Altman", "Sam Altman"])
    assert by_name["Altman"].pk == by_name["Sam Altman"].pk
    assert Person.objects.count() == 1
