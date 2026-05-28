"""DRF serializers for the articles/rescan endpoints."""
from __future__ import annotations

from rest_framework import serializers


class ArticleIngestRequestSerializer(serializers.Serializer):
    url = serializers.URLField()


class RescanRequestSerializer(serializers.Serializer):
    pages = serializers.IntegerField(required=False, min_value=1, max_value=25)


class IngestionReportSerializer(serializers.Serializer):
    article_url = serializers.CharField()
    created_article = serializers.BooleanField()
    people_created = serializers.IntegerField()
    people_matched = serializers.IntegerField()
    relationships_created = serializers.IntegerField()
    relationships_skipped = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.CharField(), default=list)


class RescanReportSerializer(serializers.Serializer):
    pages_scanned = serializers.IntegerField()
    articles_seen = serializers.IntegerField()
    articles_ingested = serializers.IntegerField()
    articles_skipped = serializers.IntegerField()
    people_created = serializers.IntegerField()
    relationships_created = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.CharField(), default=list)
