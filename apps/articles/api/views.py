"""HTTP views for article ingestion + topic rescan.

Both views delegate immediately to their service, never to the pipeline
directly — this is the boundary mentioned in the README.
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.articles.api.serializers import (
    ArticleIngestRequestSerializer,
    IngestionReportSerializer,
    RescanReportSerializer,
    RescanRequestSerializer,
)
from apps.articles.services.ingest_service import (
    ArticleIngestService,
    InvalidArticleUrl,
)
from apps.articles.services.rescan_service import (
    InvalidRescanRequest,
    RescanService,
)
from apps.common.exceptions import ParseError

logger = logging.getLogger(__name__)


class ArticleIngestView(APIView):
    """``POST /articles``: ingest one article by URL."""

    service_cls = ArticleIngestService

    def post(self, request):
        serializer = ArticleIngestRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = serializer.validated_data["url"]
        service = self.service_cls()
        try:
            report = service.ingest(url)
        except InvalidArticleUrl as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ParseError as exc:
            return Response(
                {"detail": f"Could not parse article: {exc}"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        body = IngestionReportSerializer(asdict(report)).data
        http_status = status.HTTP_201_CREATED if report.created_article else status.HTTP_200_OK
        return Response(body, status=http_status)


class RescanView(APIView):
    """``POST /rescan``: re-crawl the topic listing for N pages."""

    service_cls = RescanService

    def post(self, request):
        serializer = RescanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pages = serializer.validated_data.get("pages")
        service = self.service_cls()
        try:
            report = service.run(pages=pages)
        except InvalidRescanRequest as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RescanReportSerializer(asdict(report)).data)
