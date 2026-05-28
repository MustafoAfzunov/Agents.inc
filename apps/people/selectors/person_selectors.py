"""Read-only optimized query helpers for People.

Selectors exist so views/services never sprinkle ``select_related`` /
``prefetch_related`` calls everywhere. One place to optimise.
"""
from __future__ import annotations

from typing import Optional

from django.db.models import Count, Prefetch, QuerySet

from apps.people.models import Person
from apps.relationships.models import Relationship


def list_people() -> QuerySet[Person]:
    """All people, annotated with relationship counts for cheap list views."""

    return (
        Person.objects.all()
        .annotate(
            outgoing_count=Count("outgoing_relationships", distinct=True),
            incoming_count=Count("incoming_relationships", distinct=True),
        )
        .order_by("canonical_name")
    )


def get_person_with_graph(person_id: int) -> Optional[Person]:
    """Fetch a single person with both relationship directions prefetched."""

    outgoing_qs = (
        Relationship.objects.select_related("target_person", "article")
        .order_by("-created_at")
    )
    incoming_qs = (
        Relationship.objects.select_related("source_person", "article")
        .order_by("-created_at")
    )
    return (
        Person.objects.prefetch_related(
            Prefetch("outgoing_relationships", queryset=outgoing_qs),
            Prefetch("incoming_relationships", queryset=incoming_qs),
        )
        .filter(pk=person_id)
        .first()
    )
