# News → People Knowledge Graph

A small production-style ingestion platform that turns a TechCrunch topic
feed into a queryable graph of *people* and *the relationships between
them*. Articles are crawled, parsed, fed through a pluggable extraction
provider (regex **mock**, offline **spaCy NER**, or **OpenAI**), resolved
into canonical entities, and served over a REST API **plus** a small
server-rendered web UI.

The codebase is structured the way I would lay out a real ingestion
service rather than a one-file script: each pipeline stage is a separate,
substitutable module, persistence sits behind repositories, and HTTP views
are thin wrappers around application services.

**Highlights**

- Pluggable extraction: `mock` (offline regex), `spacy` (offline NER, no
  API key), `openai` (real LLM) — selected by one env var, with automatic
  fallback.
- Idempotent rescans enforced by DB constraints, not ad-hoc checks.
- Canonical entity resolution with alias tracking.
- Every relationship carries an explanation + exact evidence sentence +
  source article (provenance).
- REST API (paginated) and a Django-template dashboard at `/ui/`
  (browse people, relationships, articles; run rescans/ingest).
- 51 tests, fully offline and deterministic.

---

## 1. Architecture

```
                 ┌─────────────────────────────────────────────────────┐
HTTP client ───► │  REST API  (apps/.../api/views.py — thin)           │
                 └────────────────────┬────────────────────────────────┘
                                      ▼
                 ┌─────────────────────────────────────────────────────┐
                 │  Application services                               │
                 │  (apps/articles/services/*.py)                      │
                 │  – ArticleIngestService                             │
                 │  – RescanService                                    │
                 └────────────────────┬────────────────────────────────┘
                                      ▼
                 ┌─────────────────────────────────────────────────────┐
                 │  Pipelines                                          │
                 │  (apps/ingestion/pipelines/*.py)                    │
                 │  – ArticleIngestionPipeline                         │
                 │  – RescanPipeline                                   │
                 └────────────────────┬────────────────────────────────┘
                                      ▼
   ┌──────────────┬─────────────┬──────────────┬─────────────┬──────────────┐
   │  Crawlers    │  Parsers    │  Extractors  │  Resolvers  │  Repositories │
   │  (sources)   │ (trafilatura│  (LLM)       │ (canonical  │  (idempotent  │
   │              │  + bs4)     │  + provider  │  Person)    │   upserts)    │
   └──────────────┴─────────────┴──────────────┴─────────────┴──────┬───────┘
                                                                    ▼
                                                  Articles · People · Relationships
                                                              (Django ORM)
```

### Why this shape?

- **Thin views.** `apps/*/api/views.py` only validate input, call a
  service and serialise the result. Business policy never leaks into HTTP
  code.
- **Pipeline orchestration is data-only.** The pipeline owns *no* HTTP,
  *no* parsing logic, *no* LLM logic — those are injected. That keeps it
  trivial to unit-test (every test in `apps/ingestion/tests/test_pipeline.py`
  swaps in stubs without touching any private state).
- **Provider abstraction.** `BaseLLMProvider` has concrete impls
  (`MockLLMProvider`, `SpacyNERProvider`, `OpenAIProvider`) plus
  `AdaptiveLLMProvider` when `LLM_PROVIDER=openai`: OpenAI first, then
  **automatic sticky fallback to spaCy** if the key or quota fails. Tests
  default to `mock` (offline); `spacy` is offline NER; `openai`/`auto` use
  the adaptive path in production.
- **Crawler abstraction.** Adding The Verge or NYTimes is a new
  `ListingCrawler` subclass — nothing else in the pipeline changes.
- **Repositories own writes.** Idempotency (the most important property
  on rescans) is enforced in `ArticleRepository.upsert_from_parsed` and
  `RelationshipRepository.upsert`, not by ad-hoc checks in views.

### Project layout

```
news_graph/
├── config/                  # Django project (settings split base/dev/test/prod)
├── apps/
│   ├── common/              # shared base models, utils (incl. person-name validator),
│   │                        #   exceptions, pagination
│   ├── articles/            # Article model + ingest/rescan services + API
│   ├── people/              # Person model + selectors + read API
│   ├── relationships/       # Relationship model + repository
│   ├── ingestion/           # the pipeline:
│   │   ├── crawlers/        #   sources (TechCrunch today, future Verge/NYT…)
│   │   ├── parsers/         #   HTML → ParsedArticle (trafilatura + bs4)
│   │   ├── extractors/      #   provider-driven people + relationships
│   │   ├── providers/       #   BaseLLMProvider + Mock / Spacy / OpenAI + factory
│   │   ├── resolvers/       #   canonical-Person resolver
│   │   ├── pipelines/       #   orchestration (article + rescan)
│   │   └── management/      #   `manage.py rescan` command
│   └── dashboard/           # server-rendered web UI (`/ui/`)
├── docker/                  # Dockerfile + docker-compose (Postgres)
├── requirements/            # base.txt / dev.txt
├── pytest.ini
└── manage.py
```

---

## 2. Data flow

1. **`POST /rescan`** (or `manage.py rescan --pages N`) → `RescanService.run`
2. `RescanPipeline` calls `TechCrunchCrawler.crawl_pages(N)`. For each
   page it fetches HTML and parses anchors matching
   `^https?://techcrunch\.com/\d{4}/\d{2}/\d{2}/<slug>/$`, dedupes them and
   yields `ArticleListing`s.
3. For each listing URL the `ArticleIngestionPipeline` runs:
   `ArticleParser` (trafilatura → BeautifulSoup fallback) → `ParsedArticle`.
4. `LLMRelationshipExtractor` calls the active `BaseLLMProvider` with the
   prompt in `apps/ingestion/extractors/prompts.py`, parses JSON, and
   returns `ExtractionResult(people=[...], relationships=[...])`.
5. `PersonResolver.resolve_many` maps every surface form to a canonical
   `Person` row (creating new rows as needed and recording aliases).
6. `RelationshipRepository.upsert` writes each edge with provenance. The
   unique constraint
   `(source, target, relationship_type, article, evidence_sentence)`
   guarantees a rescan never duplicates edges.
7. `ArticleRepository.mark_ingested` stamps `last_ingested_at`.

---

## 3. Entity resolution strategy

The brief explicitly asks for the **simplest working approach**. The
resolver (`apps/ingestion/resolvers/person_resolver.py`) does, in order:

1. **Normalize.** Lower-case, strip accents/punctuation, drop honorifics
   (`Mr.`, `Dr.`, …), role titles (`CEO`, `CTO`, …) and possessive tokens
   (`OpenAI's`, `Tesla's`). Result: a deterministic dedup key.
2. **Exact match** on `Person.normalized_name`.
3. **Intra-article surname match.** If the new name is a single token
   (e.g. `"Altman"`), look in the per-article cache for an existing
   multi-token person whose last token matches. This is what handles the
   classic "Sam Altman ... Altman said today ..." pattern.
4. **Global unique-surname match.** Same idea, but across the whole DB —
   we only merge if exactly one person in the database has that surname.
   If two people share the surname (`Sam Altman`, `Jack Altman`), the bare
   `"Altman"` becomes its own row rather than risk a false merge.
5. **Create.** Otherwise insert a new `Person` row.

Whenever an existing person is matched, the new surface form is appended
to `aliases` (without duplicates), giving full provenance over how the
canonical entity was named in the wild.

### Limits I knowingly accepted

- No coreference resolution beyond surname matching. `"the CEO"` alone
  cannot be linked.
- No transliteration / fuzzy matching (`"Altmann"` ≠ `"Altman"`).
- Two genuinely different people with identical names will collide. With
  2 pages of TechCrunch this is acceptable; a real system would need a
  disambiguation signal (org, role, photo, Wikipedia link, …).

---

## 4. Relationship extraction strategy

The extractor sends each article body to an LLM with a small JSON-mode
prompt (`apps/ingestion/extractors/prompts.py`). The model returns:

```json
{
  "people": ["Sam Altman", "Elon Musk", "Jane Reporter"],
  "relationships": [
    {
      "source": "Sam Altman",
      "target": "Elon Musk",
      "type": "criticizes",
      "explanation": "Altman publicly pushed back against Musk's xAI claims.",
      "evidence_sentence": "Sam Altman criticized Elon Musk after Musk launched xAI.",
      "confidence": 0.82
    }
  ]
}
```

Every edge therefore carries:

- the **type** of relationship (free verb phrase, e.g. `criticizes`,
  `partners with`, `reports on`),
- a short natural-language **explanation**,
- the **exact evidence sentence** copied verbatim from the article,
- the **article** it came from (FK + URL).

The author of every article is always materialised as a `Person` even
when the LLM forgets to include them — that's enforced in
`ArticleIngestionPipeline._merge_into_graph`.

### Provider abstraction

```python
class BaseLLMProvider(ABC):
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> str: ...
```

- `OpenAIProvider` (chat completions, `response_format=json_object`,
  `temperature=0`).
- `SpacyNERProvider` — offline statistical `PERSON` NER (`en_core_web_sm`).
  Filters out places/products/orgs a regex can't, with no API key.
- `MockLLMProvider` — offline, deterministic, regex-based. Default in
  dev/test. **No API key required** to run the whole pipeline end-to-end.
- `AdaptiveLLMProvider` — used when `LLM_PROVIDER=openai` or `auto`.
  Calls OpenAI while the key and quota work; on billing/auth/quota errors
  logs a warning and **sticks to spaCy for the rest of that worker process**
  so rescans are not aborted mid-run. The dashboard header shows the active
  backend (`openai` vs `spacy` after fallback).

| `LLM_PROVIDER` | Behaviour |
|----------------|-----------|
| `mock` | Regex only (tests / quick local runs) |
| `spacy` | spaCy NER only |
| `openai` / `auto` | OpenAI → spaCy on quota/key failure → mock if spaCy missing |

Set `OPENAI_API_KEY` for production; install spaCy model with
`python -m spacy download en_core_web_sm` (Render `build.sh` does this
automatically).

A shared `is_probable_person_name()` validator runs on **every** provider's
output as a final safety net (rejects single tokens, dates, sentence-leading
stopwords, org/product tokens, and the prompt placeholder).

---

## 5. REST API

| Method | Path             | Description                                                                                                                                                            |
| -----: | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  POST  | `/articles/`     | Ingest a single TechCrunch article URL. Body: `{"url": "..."}`. Returns an `IngestionReport`.                                                                          |
|  POST  | `/rescan/`       | Re-crawl the topic listing. Body: `{"pages": 2}` (optional, defaults to `DEFAULT_RESCAN_PAGES`). Returns a `RescanReport`. Idempotent: existing articles are skipped from duplication. |
|  GET   | `/people/`       | Paginated list of canonical people (`?page=`, `?page_size=` up to 200).                                                                                                |
|  GET   | `/people/{id}/`  | One person with full relationship graph (outgoing + incoming), each edge carrying provenance.                                                                          |
|  GET   | `/health/`       | Trivial liveness probe.                                                                                                                                                |

### Example: `POST /articles/`

```bash
curl -X POST http://localhost:8000/articles/ \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://techcrunch.com/2025/01/15/example/"}'
```

Response (201 if new, 200 if it already existed):

```json
{
  "article_url": "https://techcrunch.com/2025/01/15/example/",
  "created_article": true,
  "people_created": 3,
  "people_matched": 0,
  "relationships_created": 2,
  "relationships_skipped": 0,
  "errors": []
}
```

### Example: `GET /people/{id}/`

```json
{
  "id": 7,
  "canonical_name": "Sam Altman",
  "aliases": ["Altman", "OpenAI's CEO Sam Altman"],
  "mention_count": 4,
  "relationships": [
    {
      "id": 12,
      "direction": "outgoing",
      "relationship_type": "criticizes",
      "explanation": "Altman publicly pushed back against Musk's xAI claims.",
      "evidence_sentence": "Sam Altman criticized Elon Musk after Musk launched xAI.",
      "confidence": 0.82,
      "other_person": {"id": 8, "canonical_name": "Elon Musk"},
      "article": {
        "id": 3,
        "url": "https://techcrunch.com/2025/01/15/example/",
        "title": "Sam Altman criticizes Elon Musk over xAI strategy"
      }
    }
  ]
}
```

---

## 6. Tradeoffs & assumptions

- **SQLite by default, Postgres ready.** `config/settings/dev.py` uses
  SQLite for one-command local runs; `config/settings/prod.py` swaps to
  Postgres via `POSTGRES_*` envs. The schema and queries are Postgres-safe
  (no SQLite-only idioms).
- **Synchronous ingestion.** A real platform would push each article URL
  into a queue (Celery / RQ / SQS). I kept it synchronous because the
  brief is explicit about not over-engineering, and because two pages of
  TechCrunch is well within request-time budget. The shape of the code
  (`RescanPipeline.run` is a pure function over the crawler + per-article
  pipeline) makes the move to async a 20-line refactor.
- **Resolver heuristics, not embeddings.** Vector matching would catch
  more aliasing patterns but introduces a model + index dependency. The
  brief asks for "the simplest working approach that correctly handles
  the articles from 2 pages" — the heuristic resolver does that and is
  trivially explainable.
- **Author always becomes a Person.** Even when the LLM omits them. This
  guarantees the "Author —reports on→ Subject" edge family stays
  expressible.
- **Edges keep one evidence sentence each.** If a model proposes the same
  edge from two different sentences in the same article, we store both
  rows: that's intentional — it's two pieces of evidence, not a dupe.
- **Lightweight UI, not a SPA.** The brief de-emphasises UI work, so the
  dashboard is intentionally server-rendered Django templates (no build
  step, no JS framework) that reuse the exact same services/selectors as
  the API. It exists for demoing and manual QA, not as a product surface.
- **No retry queue, but HTTP retries.** `HttpClient` does exponential
  backoff for transient failures, and the rescan pipeline never lets a
  single bad article kill the whole run — it logs it into
  `RescanReport.errors` and moves on.

---

## 7. Evaluation methodology

Relationship extraction is open-ended. Here's how I would measure quality
if/when the system goes beyond a take-home:

### Entity resolution quality

- **False-merge rate.** Take N random `Person` rows, manually check
  whether all aliases truly belong to the same human.
- **Missed-merge rate.** Cluster `Person` rows by surname; for clusters
  of size > 1, manually inspect whether they should have been merged.
- **Stability under reruns.** Run `POST /rescan` twice and assert the
  counts of `Person` and `Relationship` are unchanged (the test suite
  covers this for the happy path; the prod check would be a daily metric).

### Relationship precision

- Sample ~50 random edges, label each as ✅/❌ based on whether the
  evidence sentence actually supports the relationship type.
- Track precision per `relationship_type`. Some types (`criticizes`) tend
  to be harder than others (`co-founded`); knowing which is invaluable
  for prompt tuning.

### Graph consistency

- No `Person` with duplicate `normalized_name` (enforced by unique
  constraint).
- No `Relationship` violating the unique-provenance constraint
  (enforced by the DB).
- No self-loops (DB check constraint).
- Every `Relationship` has a non-empty `evidence_sentence` and a valid
  `article_id`.

### Coverage

- Articles per page that produced **zero** people / relationships.
- Topic-page articles **not yet** ingested.
- Per-source success rate (only `techcrunch` today; built so new sources
  can be measured side-by-side).

---

## 8. Future improvements

- **Background queue** (Celery) for `POST /rescan` so the HTTP call
  returns a job id and a status endpoint streams progress.
- **More sources.** Drop in `VergeCrawler`, `NYTimesCrawler` — the rest
  of the pipeline is already source-agnostic.
- **Better resolver.** Hybrid: heuristic resolver as today, plus an
  embedding tie-breaker for ambiguous surnames.
- **Stronger NER.** The `spacy` provider uses the small `en_core_web_sm`
  model; a larger model (`en_core_web_trf`) or OpenAI would further reduce
  the few org/fund names (e.g. "Baillie Gifford") that still slip through
  the `PERSON` classifier.
- **Edge merging.** When the LLM proposes very similar edges with
  different verbs (`criticizes` vs `attacks`), cluster them under a
  canonical relationship type.
- **Evaluation dashboard.** Persist labelling decisions, surface
  precision per relationship type in the admin.
- **Versioned ingestion.** Re-running with a newer LLM produces a new
  `Extraction` row instead of mutating in-place, so we can A/B old vs new.

---

## 9. How to run

### Local (SQLite, mock LLM, no API key required)

```bash
cd news_graph
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

### Web UI (Django templates)

Open **http://127.0.0.1:8000/** (redirects to `/ui/`) for a small server-rendered dashboard:

| Page | URL | What it shows |
|------|-----|----------------|
| Dashboard | http://127.0.0.1:8000/ui/ | Live stats + rescan / ingest forms (with a loading overlay and elapsed time), provider badge |
| People (paginated, searchable) | http://127.0.0.1:8000/ui/people/ | Canonical people with alias + edge counts |
| Person detail | http://127.0.0.1:8000/ui/people/{id}/ | Outgoing/incoming relationships, each with evidence quote + source article |
| Relationships (paginated, searchable) | http://127.0.0.1:8000/ui/relationships/ | Every edge as `source → target`, type, evidence, article |
| Articles (paginated, searchable) | http://127.0.0.1:8000/ui/articles/ | Ingested articles with author, date, source, edge count, link |

The UI calls the same `RescanService` / `ArticleIngestService` / selectors as the REST API — no duplicated business logic. People, Relationships and Articles lists support `?q=` search and `?page_size=`. The header shows the active LLM provider so you always know which extractor produced the data.

Then in another shell:

```bash
curl -X POST http://localhost:8000/rescan/ -H 'Content-Type: application/json' \
  -d '{"pages": 2}'
curl http://localhost:8000/people/
```

Or use the CLI:

```bash
python manage.py rescan --pages 2
```

### With offline spaCy NER (cleaner people, no API key)

The default `mock` provider is a regex and over-captures non-people
(places, products, orgs). The `spacy` provider uses real `PERSON` NER and
cuts that noise dramatically (on a 2-page rescan, distinct people dropped
from ~430 to ~145) without any API key. `spaCy` itself is already in
`requirements/base.txt`; you only need to download the model:

```bash
python -m spacy download en_core_web_sm
echo 'LLM_PROVIDER=spacy' >> .env
python manage.py rescan --pages 2
```

If spaCy or the model isn't installed, the provider factory automatically
falls back to `mock`. **Note:** changing `.env` requires restarting
`runserver` for the new provider to take effect.

### With OpenAI extraction (recommended) + automatic spaCy fallback

Production default: use OpenAI for typed relationships; when the key is
invalid or quota is spent, ingestion **switches to spaCy** for that worker
without changing `.env`.

```bash
echo 'LLM_PROVIDER=openai'  >> .env   # or LLM_PROVIDER=auto
echo 'OPENAI_API_KEY=sk-...' >> .env
python -m spacy download en_core_web_sm   # required for fallback
python manage.py rescan --pages 2
```

After fallback, the UI badge shows `LLM: spacy` instead of `openai`. Restart
the server (or redeploy) to try OpenAI again after topping up billing.

### With Postgres (Docker)

```bash
cd news_graph
docker compose -f docker/docker-compose.yml up --build
```

### Tests

```bash
pytest -q
```

**57 tests** cover the crawler, parser, person-name validator, the resolver,
OpenAI→spaCy adaptive fallback,
(including the ambiguous-surname case that must *not* merge), pipeline
idempotency, the REST API, and the dashboard views. The suite is fully
offline and deterministic (forces the `mock` provider) and runs in ~1s.
The two spaCy provider tests auto-skip if the `en_core_web_sm` model isn't
installed.
