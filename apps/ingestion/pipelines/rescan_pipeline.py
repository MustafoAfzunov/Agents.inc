"""Multi-page topic rescan pipeline.

Walks N listing pages of a single crawler, ingests every article through
the article pipeline and aggregates the per-article reports.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from apps.common.exceptions import CrawlError, ParseError
from apps.ingestion.crawlers.base import ListingCrawler
from apps.ingestion.crawlers.techcrunch import TechCrunchCrawler
from apps.ingestion.dto import RescanReport
from apps.ingestion.pipelines.article_pipeline import ArticleIngestionPipeline

logger = logging.getLogger(__name__)


@dataclass
class RescanPipeline:
    crawler: ListingCrawler = field(default_factory=TechCrunchCrawler)
    article_pipeline: ArticleIngestionPipeline = field(default_factory=ArticleIngestionPipeline)

    def run(self, *, pages: int) -> RescanReport:
        report = RescanReport(pages_scanned=pages)
        try:
            listings = self.crawler.crawl_pages(pages)
        except CrawlError as exc:
            logger.error("Listing crawl failed: %s", exc)
            report.errors.append(f"crawl_failed: {exc}")
            return report

        report.articles_seen = len(listings)
        logger.info("Rescan discovered %s article URLs", len(listings))

        for listing in listings:
            try:
                article_report = self.article_pipeline.ingest_url(listing.url)
            except ParseError as exc:
                logger.warning("Skipping %s: %s", listing.url, exc)
                report.articles_skipped += 1
                report.errors.append(f"parse_failed:{listing.url}:{exc}")
                continue
            except Exception as exc:  # noqa: BLE001 - keep rescan going
                logger.exception("Unexpected failure for %s", listing.url)
                report.articles_skipped += 1
                report.errors.append(f"unexpected:{listing.url}:{exc}")
                continue

            report.articles_ingested += 1
            report.people_created += article_report.people_created
            report.relationships_created += article_report.relationships_created
            report.errors.extend(article_report.errors)
        return report
