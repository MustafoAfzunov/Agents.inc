from __future__ import annotations

from django.urls import path

from apps.articles.api.views import ArticleIngestView, RescanView

urlpatterns = [
    path("articles/", ArticleIngestView.as_view(), name="articles-ingest"),
    path("rescan/", RescanView.as_view(), name="articles-rescan"),
]
