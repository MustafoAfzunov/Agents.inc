from __future__ import annotations

from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "published_at", "crawled_at")
    list_filter = ("source",)
    search_fields = ("title", "url", "author_name")
    readonly_fields = ("crawled_at", "last_ingested_at")
