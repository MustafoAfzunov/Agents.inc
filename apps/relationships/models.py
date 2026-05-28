"""Graph edge model.

Every ``Relationship`` row is a directed edge between two ``Person`` nodes.
Edges always carry provenance (which article, which sentence) so consumers
can verify why we believe a particular relationship exists.

The unique constraint enforces edge-level idempotency: re-ingesting the same
article (a rescan) cannot produce a duplicate edge.
"""
from __future__ import annotations

from django.db import models

from apps.common.constants import MAX_RELATIONSHIP_TYPE_LENGTH
from apps.common.models import TimeStampedModel


class Relationship(TimeStampedModel):
    source_person = models.ForeignKey(
        "people.Person",
        related_name="outgoing_relationships",
        on_delete=models.CASCADE,
    )
    target_person = models.ForeignKey(
        "people.Person",
        related_name="incoming_relationships",
        on_delete=models.CASCADE,
    )
    relationship_type = models.CharField(max_length=MAX_RELATIONSHIP_TYPE_LENGTH)
    explanation = models.TextField(blank=True, default="")
    evidence_sentence = models.TextField(blank=True, default="")
    article = models.ForeignKey(
        "articles.Article",
        related_name="relationships",
        on_delete=models.CASCADE,
    )
    confidence = models.FloatField(default=0.0)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_person",
                    "target_person",
                    "relationship_type",
                    "article",
                    "evidence_sentence",
                ],
                name="uniq_relationship_provenance",
            ),
            models.CheckConstraint(
                check=~models.Q(source_person=models.F("target_person")),
                name="relationship_no_self_loop",
            ),
        ]
        indexes = [
            models.Index(fields=["relationship_type"]),
            models.Index(fields=["source_person", "target_person"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return (
            f"{self.source_person_id} -{self.relationship_type}-> {self.target_person_id}"
        )
