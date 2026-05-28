from __future__ import annotations

from django.urls import path

from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("articles/", views.articles_list, name="articles-list"),
    path("relationships/", views.relationships_list, name="relationships-list"),
    path("people/", views.people_list, name="people-list"),
    path("people/<int:pk>/", views.person_detail, name="person-detail"),
]
