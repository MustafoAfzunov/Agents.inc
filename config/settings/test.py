"""Settings used when running the test suite.

We override the database to an in-memory SQLite for speed and force the
``mock`` LLM provider so tests are deterministic and offline.
"""
from __future__ import annotations

from .base import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

NEWS_GRAPH = {**NEWS_GRAPH, "LLM_PROVIDER": "mock"}  # noqa: F405
