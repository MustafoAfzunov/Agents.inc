"""Persistence boundary for :class:`Relationship`.

The repository's job is to make edge creation *idempotent*: calling
``upsert`` twice with the same (source, target, type, article, evidence)
must return the same row without raising.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from apps.articles.models import Article
from apps.people.models import Person
from apps.relationships.models import Relationship


@dataclass
class RelationshipRepository:
    def upsert(
        self,
        *,
        source: Person,
        target: Person,
        relationship_type: str,
        explanation: str,
        evidence_sentence: str,
        article: Article,
        confidence: float = 0.0,
    ) -> Tuple[Relationship, bool]:
        if source.pk == target.pk:
            raise ValueError("Refusing to create self-loop relationship")

        rel, created = Relationship.objects.get_or_create(
            source_person=source,
            target_person=target,
            relationship_type=relationship_type,
            article=article,
            evidence_sentence=evidence_sentence,
            defaults={
                "explanation": explanation,
                "confidence": confidence,
            },
        )
        if not created:
            update_fields: list[str] = []
            if explanation and rel.explanation != explanation:
                rel.explanation = explanation
                update_fields.append("explanation")
            if confidence and rel.confidence != confidence:
                rel.confidence = confidence
                update_fields.append("confidence")
            if update_fields:
                update_fields.append("updated_at")
                rel.save(update_fields=update_fields)
        return rel, created
