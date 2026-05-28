"""Article ingestion pipeline.

Runs one parsed article through extractor → resolver → graph merger and
returns a structured :class:`IngestionReport` describing what changed.

The pipeline is intentionally pure orchestration: it owns *no* HTTP, *no*
parsing, *no* LLM logic — those are injected. That's what makes the whole
thing easy to test (see ``apps/ingestion/tests``).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from django.db import transaction

from apps.articles.models import Article
from apps.articles.repositories.article_repository import ArticleRepository
from apps.ingestion.dto import IngestionReport, ParsedArticle
from apps.ingestion.extractors.llm_extractor import LLMRelationshipExtractor
from apps.ingestion.parsers.article_parser import ArticleParser
from apps.ingestion.resolvers.person_resolver import PersonResolver
from apps.relationships.repositories.relationship_repository import (
    RelationshipRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class ArticleIngestionPipeline:
    """Orchestrates ingestion of a single article.

    All dependencies have sensible defaults but can be overridden — that's
    how the test suite swaps in a mock LLM or a deterministic parser.
    """

    parser: ArticleParser = field(default_factory=ArticleParser)
    extractor: LLMRelationshipExtractor = field(default_factory=LLMRelationshipExtractor)
    resolver: PersonResolver = field(default_factory=PersonResolver)
    article_repo: ArticleRepository = field(default_factory=ArticleRepository)
    relationship_repo: RelationshipRepository = field(default_factory=RelationshipRepository)

    # -- public API ------------------------------------------------------

    def ingest_url(self, url: str) -> IngestionReport:
        parsed = self.parser.fetch_and_parse(url)
        return self.ingest_parsed(parsed)

    def ingest_parsed(self, parsed: ParsedArticle) -> IngestionReport:
        report = IngestionReport(article_url=parsed.url)
        with transaction.atomic():
            article, created = self.article_repo.upsert_from_parsed(parsed)
            report.created_article = created

            try:
                extraction = self.extractor.extract(parsed)
            except Exception as exc:  # noqa: BLE001 - we record and bail safely
                logger.exception("Extraction failed for %s", parsed.url)
                report.errors.append(f"extraction_failed: {exc}")
                return report

            # Author always counts as a Person, even if the LLM omitted them.
            if parsed.author_name and parsed.author_name not in extraction.people:
                extraction.people.append(parsed.author_name)

            self._merge_into_graph(article, parsed, extraction, report)
            self.article_repo.mark_ingested(article)
        return report

    # -- internals -------------------------------------------------------

    def _merge_into_graph(
        self,
        article: Article,
        parsed: ParsedArticle,
        extraction,  # ExtractionResult – type kept loose to avoid cycles
        report: IngestionReport,
    ) -> None:
        self.resolver.reset_article_cache()
        before = self.resolver.stats.created, self.resolver.stats.matched
        people_by_name = self.resolver.resolve_many(extraction.people)
        after = self.resolver.stats.created, self.resolver.stats.matched
        report.people_created = after[0] - before[0]
        report.people_matched = after[1] - before[1]

        # Tag the author on the article in case the original parse missed it.
        if parsed.author_name and parsed.author_name in people_by_name:
            author_person = people_by_name[parsed.author_name]
            if not article.author_name:
                article.author_name = author_person.canonical_name
                article.save(update_fields=["author_name", "updated_at"])

        for rel in extraction.relationships:
            try:
                source = self._resolve_or_skip(rel.source, people_by_name)
                target = self._resolve_or_skip(rel.target, people_by_name)
            except _SkipRelationship as exc:
                report.relationships_skipped += 1
                report.errors.append(str(exc))
                continue
            if source.pk == target.pk:
                report.relationships_skipped += 1
                continue
            try:
                _, created = self.relationship_repo.upsert(
                    source=source,
                    target=target,
                    relationship_type=rel.relationship_type,
                    explanation=rel.explanation,
                    evidence_sentence=rel.evidence_sentence,
                    article=article,
                    confidence=rel.confidence,
                )
            except ValueError as exc:
                report.relationships_skipped += 1
                report.errors.append(str(exc))
                continue
            if created:
                report.relationships_created += 1
            else:
                report.relationships_skipped += 1

    def _resolve_or_skip(self, name: str, cache: dict) -> "Person":  # noqa: F821
        if name in cache:
            return cache[name]
        # Late resolution path: ExtractedRelationship references a name the
        # extractor didn't include in the ``people`` list.
        try:
            person = self.resolver.resolve(name)
        except ValueError as exc:
            raise _SkipRelationship(f"unresolvable_name: {name}: {exc}") from exc
        cache[name] = person
        return person


class _SkipRelationship(Exception):
    """Internal control-flow signal to skip a single malformed relationship."""
