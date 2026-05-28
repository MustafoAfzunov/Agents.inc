"""``manage.py rescan`` — run the topic rescan from the CLI.

Handy for ops/cron and to verify pipelines without curl-ing the HTTP API.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from django.core.management.base import BaseCommand

from apps.articles.services.rescan_service import RescanService


class Command(BaseCommand):
    help = "Rescan the configured topic listing for N pages."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--pages",
            type=int,
            default=None,
            help="Number of listing pages to scan (defaults to settings.NEWS_GRAPH['DEFAULT_RESCAN_PAGES']).",
        )

    def handle(self, *args, **options) -> None:
        service = RescanService()
        report = service.run(pages=options.get("pages"))
        self.stdout.write(json.dumps(asdict(report), indent=2))
