"""Article persistence model.

Each crawled URL becomes exactly one ``Article`` row; the ``url`` field is the
natural unique key and is what makes rescans idempotent.
"""
from __future__ import annotations

from django.db import models

from apps.common.constants import (
    MAX_ARTICLE_TITLE_LENGTH,
    MAX_AUTHOR_NAME_LENGTH,
)
from apps.common.models import TimeStampedModel


class Article(TimeStampedModel):
    url = models.URLField(max_length=1000, unique=True)
    title = models.CharField(max_length=MAX_ARTICLE_TITLE_LENGTH)
    content = models.TextField(blank=True, default="")
    summary = models.TextField(blank=True, default="")
    author_name = models.CharField(max_length=MAX_AUTHOR_NAME_LENGTH, blank=True, default="")
    source = models.CharField(
        max_length=64,
        default="techcrunch",
        help_text="Identifier of the crawler/source that produced this article.",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    crawled_at = models.DateTimeField(auto_now_add=True)
    last_ingested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-published_at", "-created_at")
        indexes = [
            models.Index(fields=["source"]),
            models.Index(fields=["published_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.title} <{self.url}>"
