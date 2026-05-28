"""DRF pagination defaults."""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Page-number pagination with a sane ``?page_size=`` override."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
