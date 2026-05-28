"""Persistence boundary for :class:`Article`.

Everything that writes/reads articles for the pipeline goes through this
class so the service layer never builds raw ORM queries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from django.utils import timezone

from apps.articles.models import Article
from apps.ingestion.dto import ParsedArticle


@dataclass
class ArticleRepository:
    def get_by_url(self, url: str) -> Optional[Article]:
        return Article.objects.filter(url=url).first()

    def upsert_from_parsed(self, parsed: ParsedArticle) -> Tuple[Article, bool]:
        """Create or update an Article from a :class:`ParsedArticle`.

        Returns ``(article, created)``.
        """

        defaults = {
            "title": parsed.title,
            "content": parsed.content,
            "summary": parsed.summary,
            "author_name": parsed.author_name,
            "source": parsed.source,
            "published_at": parsed.published_at,
            "last_ingested_at": timezone.now(),
        }
        article, created = Article.objects.update_or_create(
            url=parsed.url,
            defaults=defaults,
        )
        return article, created

    def mark_ingested(self, article: Article, when: Optional[datetime] = None) -> None:
        article.last_ingested_at = when or timezone.now()
        article.save(update_fields=["last_ingested_at", "updated_at"])
