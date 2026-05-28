from __future__ import annotations

from django.urls import path

from apps.people.api.views import PersonDetailView, PersonListView

urlpatterns = [
    path("people/", PersonListView.as_view(), name="people-list"),
    path("people/<int:pk>/", PersonDetailView.as_view(), name="people-detail"),
]
