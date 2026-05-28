from __future__ import annotations

from django.contrib import admin

from .models import Relationship


@admin.register(Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = (
        "source_person",
        "relationship_type",
        "target_person",
        "article",
        "created_at",
    )
    list_filter = ("relationship_type",)
    search_fields = (
        "source_person__canonical_name",
        "target_person__canonical_name",
        "evidence_sentence",
    )
    autocomplete_fields = ("source_person", "target_person", "article")
