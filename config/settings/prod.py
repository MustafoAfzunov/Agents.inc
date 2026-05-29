"""Production settings.

Reads configuration from environment variables and tightens a few defaults.
Designed to run on a PaaS such as Render: it understands ``DATABASE_URL`` and
the ``RENDER_EXTERNAL_HOSTNAME`` injected by the platform, serves static files
with WhiteNoise, and keeps everything else minimal on purpose.
"""
from __future__ import annotations

import os

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE  # noqa: F401

DEBUG = False

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

# Render injects the public hostname here; trust it automatically so the app
# works out of the box without hard-coding the generated *.onrender.com host.
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# The dashboard performs POST requests (rescan / ingest), so every HTTPS origin
# we answer on must be a trusted CSRF origin.
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host not in {"*", ""}]

# Database -----------------------------------------------------------------
# Prefer a single DATABASE_URL (Render, Heroku, ...); fall back to discrete
# POSTGRES_* vars used by the local docker-compose stack.
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL, conn_max_age=60, ssl_require=True
        )
    }
elif os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }

# Static files -------------------------------------------------------------
# WhiteNoise serves collected static assets directly from the web process,
# which is all this app needs (no separate CDN / object store).
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Security -----------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
