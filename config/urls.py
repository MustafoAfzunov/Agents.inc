"""Root URL configuration.

Each domain app owns its own ``api/urls.py``. We just mount them here so the
root file stays tiny and the apps remain independently routable.
"""
from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthcheck(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", healthcheck, name="health"),
    path("", include("apps.articles.api.urls")),
    path("", include("apps.people.api.urls")),
]
