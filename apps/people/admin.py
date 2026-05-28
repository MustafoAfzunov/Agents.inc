from __future__ import annotations

from django.contrib import admin

from .models import Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("canonical_name", "mention_count", "created_at")
    search_fields = ("canonical_name", "normalized_name")
    readonly_fields = ("created_at", "updated_at", "normalized_name")
