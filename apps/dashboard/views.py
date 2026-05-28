"""Server-rendered UI for the knowledge graph.

Thin template views that delegate to the same services/selectors as the
REST API — no duplicate business logic.
"""
from __future__ import annotations

import time
from dataclasses import asdict

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.articles.models import Article
from apps.articles.services.ingest_service import ArticleIngestService, InvalidArticleUrl
from apps.articles.services.rescan_service import InvalidRescanRequest, RescanService
from apps.common.exceptions import ParseError
from apps.people.models import Person
from apps.people.selectors.person_selectors import get_person_with_graph, list_people
from apps.relationships.models import Relationship


def _graph_stats() -> dict[str, int]:
    return {
        "article_count": Article.objects.count(),
        "person_count": Person.objects.count(),
        "relationship_count": Relationship.objects.count(),
    }


def _llm_provider() -> str:
    return getattr(settings, "NEWS_GRAPH", {}).get("LLM_PROVIDER", "mock")


@require_http_methods(["GET", "POST"])
def dashboard(request: HttpRequest) -> HttpResponse:
    cfg = getattr(settings, "NEWS_GRAPH", {})
    default_pages = cfg.get("DEFAULT_RESCAN_PAGES", 2)
    llm_provider = cfg.get("LLM_PROVIDER", "mock")

    rescan_report = None
    ingest_report = None
    rescan_elapsed = None
    ingest_elapsed = None
    error_message = None

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "rescan":
                pages = int(request.POST.get("pages", default_pages))
                started = time.monotonic()
                rescan_report = RescanService().run(pages=pages)
                rescan_elapsed = round(time.monotonic() - started, 2)
            elif action == "ingest":
                url = request.POST.get("url", "").strip()
                started = time.monotonic()
                ingest_report = ArticleIngestService().ingest(url)
                ingest_elapsed = round(time.monotonic() - started, 2)
            else:
                error_message = "Unknown action."
        except (InvalidRescanRequest, InvalidArticleUrl, ValueError) as exc:
            error_message = str(exc)
        except ParseError as exc:
            error_message = f"Could not parse article: {exc}"

    return render(
        request,
        "dashboard/home.html",
        {
            "nav": "home",
            "stats": _graph_stats(),
            "default_pages": default_pages,
            "llm_provider": llm_provider,
            "rescan_report": asdict(rescan_report) if rescan_report else None,
            "ingest_report": asdict(ingest_report) if ingest_report else None,
            "rescan_elapsed": rescan_elapsed,
            "ingest_elapsed": ingest_elapsed,
            "error_message": error_message,
        },
    )


def _safe_int(value: str | None, default: int, *, lo: int, hi: int) -> int:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


@require_http_methods(["GET"])
def people_list(request: HttpRequest) -> HttpResponse:
    page_size = _safe_int(request.GET.get("page_size"), 25, lo=5, hi=200)
    query = (request.GET.get("q") or "").strip()

    queryset = list_people()
    if query:
        queryset = queryset.filter(
            Q(canonical_name__icontains=query) | Q(aliases__icontains=query)
        )

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "dashboard/people_list.html",
        {
            "nav": "people",
            "stats": _graph_stats(),
            "llm_provider": _llm_provider(),
            "page_obj": page_obj,
            "paginator": paginator,
            "query": query,
            "page_size": page_size,
        },
    )


@require_http_methods(["GET"])
def relationships_list(request: HttpRequest) -> HttpResponse:
    page_size = _safe_int(request.GET.get("page_size"), 25, lo=5, hi=200)
    query = (request.GET.get("q") or "").strip()

    queryset = (
        Relationship.objects.select_related("source_person", "target_person", "article")
        .order_by("-created_at")
    )
    if query:
        queryset = queryset.filter(
            Q(relationship_type__icontains=query)
            | Q(source_person__canonical_name__icontains=query)
            | Q(target_person__canonical_name__icontains=query)
        )

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "dashboard/relationships_list.html",
        {
            "nav": "relationships",
            "stats": _graph_stats(),
            "llm_provider": _llm_provider(),
            "page_obj": page_obj,
            "paginator": paginator,
            "query": query,
            "page_size": page_size,
        },
    )


@require_http_methods(["GET"])
def articles_list(request: HttpRequest) -> HttpResponse:
    page_size = _safe_int(request.GET.get("page_size"), 25, lo=5, hi=200)
    query = (request.GET.get("q") or "").strip()

    queryset = (
        Article.objects.annotate(relationship_count=Count("relationships", distinct=True))
        .order_by("-published_at", "-crawled_at")
    )
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) | Q(author_name__icontains=query) | Q(url__icontains=query)
        )

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "dashboard/articles_list.html",
        {
            "nav": "articles",
            "stats": _graph_stats(),
            "llm_provider": _llm_provider(),
            "page_obj": page_obj,
            "paginator": paginator,
            "query": query,
            "page_size": page_size,
        },
    )


def _relationship_rows(person: Person) -> list[dict]:
    rows: list[dict] = []
    for rel in person.outgoing_relationships.all():
        rows.append(
            {
                "id": rel.id,
                "direction": "outgoing",
                "direction_label": "→",
                "relationship_type": rel.relationship_type,
                "explanation": rel.explanation,
                "evidence_sentence": rel.evidence_sentence,
                "confidence": rel.confidence,
                "other_person": rel.target_person,
                "article": rel.article,
            }
        )
    for rel in person.incoming_relationships.all():
        rows.append(
            {
                "id": rel.id,
                "direction": "incoming",
                "direction_label": "←",
                "relationship_type": rel.relationship_type,
                "explanation": rel.explanation,
                "evidence_sentence": rel.evidence_sentence,
                "confidence": rel.confidence,
                "other_person": rel.source_person,
                "article": rel.article,
            }
        )
    rows.sort(key=lambda r: r["article"].published_at or r["article"].created_at, reverse=True)
    return rows


@require_http_methods(["GET"])
def person_detail(request: HttpRequest, pk: int) -> HttpResponse:
    person = get_person_with_graph(pk)
    if person is None:
        return render(
            request,
            "dashboard/person_not_found.html",
            {"pk": pk, "stats": _graph_stats(), "llm_provider": _llm_provider()},
            status=404,
        )

    rows = _relationship_rows(person)
    outgoing = [r for r in rows if r["direction"] == "outgoing"]
    incoming = [r for r in rows if r["direction"] == "incoming"]

    return render(
        request,
        "dashboard/person_detail.html",
        {
            "nav": "people",
            "stats": _graph_stats(),
            "llm_provider": _llm_provider(),
            "person": person,
            "relationships": rows,
            "outgoing": outgoing,
            "incoming": incoming,
        },
    )
