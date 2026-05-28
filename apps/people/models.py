"""Canonical Person entity.

A ``Person`` is one *node* in our knowledge graph. The same human can be
referenced many ways across articles ("Sam Altman", "Altman", "OpenAI's CEO")
and the resolver is responsible for collapsing those surface forms onto a
single row here. ``normalized_name`` is the deterministic dedup key, and
``aliases`` keeps the observed surface forms so we can surface provenance.
"""
from __future__ import annotations

from django.db import models

from apps.common.constants import MAX_PERSON_NAME_LENGTH
from apps.common.models import TimeStampedModel


class Person(TimeStampedModel):
    canonical_name = models.CharField(max_length=MAX_PERSON_NAME_LENGTH)
    normalized_name = models.CharField(
        max_length=MAX_PERSON_NAME_LENGTH,
        unique=True,
        help_text="Lower-case, accent-stripped, prefix-free version of canonical_name.",
    )
    aliases = models.JSONField(default=list, blank=True)
    mention_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("canonical_name",)
        indexes = [
            models.Index(fields=["normalized_name"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.canonical_name

    def add_alias(self, alias: str) -> bool:
        """Append *alias* to ``aliases`` if not present. Returns True if added."""

        alias = (alias or "").strip()
        if not alias or alias == self.canonical_name:
            return False
        existing = self.aliases or []
        if alias in existing:
            return False
        existing.append(alias)
        self.aliases = existing
        return True
