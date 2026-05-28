from __future__ import annotations

from django.urls import path

from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("people/", views.people_list, name="people-list"),
    path("people/<int:pk>/", views.person_detail, name="person-detail"),
]
