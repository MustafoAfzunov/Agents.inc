"""Base Django settings shared by every environment.

The project intentionally splits configuration into ``base``, ``dev`` and
``prod`` modules so we can keep production-only knobs (Postgres, Sentry,
allowed hosts, ...) clearly separated from local development defaults.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env", override=False)


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.common",
    "apps.articles",
    "apps.people",
    "apps.relationships",
    "apps.ingestion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Default to SQLite for friction-free local dev / CI; production swaps to
# Postgres via DATABASE_URL-style env vars in ``prod.py``.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# Ingestion configuration ------------------------------------------------
NEWS_GRAPH = {
    "TECHCRUNCH_TOPIC_URL": env(
        "TECHCRUNCH_TOPIC_URL", "https://techcrunch.com/tag/openai/"
    ),
    "DEFAULT_RESCAN_PAGES": env_int("DEFAULT_RESCAN_PAGES", 2),
    "HTTP_TIMEOUT_SECONDS": env_int("HTTP_TIMEOUT_SECONDS", 20),
    "USER_AGENT": env(
        "HTTP_USER_AGENT",
        "news-graph-bot/1.0 (+https://example.com/bot)",
    ),
    # Which LLM provider to use. ``mock`` is deterministic + offline and is the
    # default so tests and local runs never need an API key. Set ``LLM_PROVIDER=openai``
    # together with ``OPENAI_API_KEY`` for real extraction.
    "LLM_PROVIDER": env("LLM_PROVIDER", "mock"),
    "OPENAI_API_KEY": env("OPENAI_API_KEY", ""),
    "OPENAI_MODEL": env("OPENAI_MODEL", "gpt-4o-mini"),
    "EXTRACTION_MAX_CHARS": env_int("EXTRACTION_MAX_CHARS", 12000),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
