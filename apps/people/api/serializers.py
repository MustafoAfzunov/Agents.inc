"""DRF serializers for the people read APIs."""
from __future__ import annotations

from rest_framework import serializers

from apps.people.models import Person
from apps.relationships.models import Relationship


class PersonListSerializer(serializers.ModelSerializer):
    outgoing_count = serializers.IntegerField(read_only=True)
    incoming_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Person
        fields = (
            "id",
            "canonical_name",
            "aliases",
            "mention_count",
            "outgoing_count",
            "incoming_count",
            "created_at",
        )


class _RelationshipArticleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    url = serializers.URLField()
    title = serializers.CharField()


class _RelationshipEdgeSerializer(serializers.Serializer):
    """Generic edge serializer used for both directions.

    Direction is injected on the instance by the parent serializer; we use
    ``SerializerMethodField`` rather than a model field because direction is
    not part of the underlying row — it's a view-time concept.
    """

    id = serializers.IntegerField()
    relationship_type = serializers.CharField()
    explanation = serializers.CharField()
    evidence_sentence = serializers.CharField()
    confidence = serializers.FloatField()
    direction = serializers.SerializerMethodField()
    other_person = serializers.SerializerMethodField()
    article = serializers.SerializerMethodField()

    def get_direction(self, obj: Relationship) -> str:
        return getattr(obj, "_direction", "outgoing")

    def get_other_person(self, obj: Relationship) -> dict:
        person = obj.target_person if self.get_direction(obj) == "outgoing" else obj.source_person
        return {"id": person.id, "canonical_name": person.canonical_name}

    def get_article(self, obj: Relationship) -> dict:
        return {
            "id": obj.article_id,
            "url": obj.article.url,
            "title": obj.article.title,
        }


class PersonDetailSerializer(serializers.ModelSerializer):
    relationships = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = (
            "id",
            "canonical_name",
            "aliases",
            "mention_count",
            "created_at",
            "updated_at",
            "relationships",
        )

    def get_relationships(self, person: Person) -> list[dict]:
        edges: list[Relationship] = []
        for rel in person.outgoing_relationships.all():
            rel._direction = "outgoing"
            edges.append(rel)
        for rel in person.incoming_relationships.all():
            rel._direction = "incoming"
            edges.append(rel)
        edges.sort(key=lambda r: r.created_at, reverse=True)
        return _RelationshipEdgeSerializer(edges, many=True).data
