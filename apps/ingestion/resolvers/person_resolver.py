"""Canonical-person resolution.

The resolver collapses surface forms (e.g. ``"Sam Altman"``, ``"Altman"``,
``"OpenAI's CEO Sam Altman"``) onto a single :class:`Person` row.

Strategy (deliberately simple, in line with the brief — "the simplest
working approach that correctly handles the articles from 2 pages"):

1. Normalize the incoming name (lower-case, strip accents/honorifics).
2. Exact match on ``normalized_name``  → existing person, register alias.
3. Otherwise look at the **cache of already-resolved names within the
   same article**. A bare surname like "Altman" that follows a full name
   like "Sam Altman" in the same article resolves to that person.
4. Otherwise look at the *global* set of people. A single-token name is
   linked to an existing multi-token person if and only if the token is
   that person's last name and no other person has the same last name.
5. Fall back to creating a new :class:`Person`.

The resolver keeps a per-article ``_local_cache`` so resolution within an
article is consistent and stable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

from apps.common.utils.text import name_tokens, normalize_name
from apps.people.models import Person

logger = logging.getLogger(__name__)


@dataclass
class _ResolutionStats:
    created: int = 0
    matched: int = 0
    aliases_added: int = 0


@dataclass
class PersonResolver:
    """Resolve a series of surface-form names into canonical ``Person`` rows."""

    _local_cache: Dict[str, Person] = field(default_factory=dict)
    stats: _ResolutionStats = field(default_factory=_ResolutionStats)

    # -- public API ------------------------------------------------------

    def reset_article_cache(self) -> None:
        """Clear the per-article cache. Call this before each new article."""

        self._local_cache.clear()

    def resolve_many(self, names: Iterable[str]) -> Dict[str, Person]:
        """Resolve all *names*, prioritising multi-token names first.

        Resolving longer (more specific) names first means the local cache is
        populated with "Sam Altman" before a later bare "Altman" is processed.
        """

        ordered = sorted({n.strip() for n in names if n and n.strip()}, key=lambda n: -len(name_tokens(n)))
        result: Dict[str, Person] = {}
        for name in ordered:
            result[name] = self.resolve(name)
        return result

    def resolve(self, name: str) -> Person:
        normalized = normalize_name(name)
        if not normalized:
            raise ValueError(f"Cannot resolve empty name from {name!r}")

        if normalized in self._local_cache:
            person = self._local_cache[normalized]
            if person.add_alias(name):
                person.save(update_fields=["aliases", "updated_at"])
                self.stats.aliases_added += 1
            return person

        person = self._lookup_exact(normalized)
        if person is None:
            person = self._lookup_by_surname_in_cache(normalized)
        if person is None:
            person = self._lookup_by_global_surname(normalized)

        if person is None:
            person = Person.objects.create(
                canonical_name=name.strip(),
                normalized_name=normalized,
                aliases=[],
            )
            self.stats.created += 1
        else:
            if person.add_alias(name):
                self.stats.aliases_added += 1
            person.mention_count += 1
            person.save(update_fields=["aliases", "mention_count", "updated_at"])
            self.stats.matched += 1

        self._local_cache[normalized] = person
        return person

    # -- lookups ---------------------------------------------------------

    def _lookup_exact(self, normalized: str) -> Optional[Person]:
        return Person.objects.filter(normalized_name=normalized).first()

    def _lookup_by_surname_in_cache(self, normalized: str) -> Optional[Person]:
        tokens = normalized.split(" ")
        if len(tokens) != 1:
            return None
        surname = tokens[0]
        candidates = [
            person
            for cached_norm, person in self._local_cache.items()
            if cached_norm.split(" ")[-1] == surname and " " in cached_norm
        ]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _lookup_by_global_surname(self, normalized: str) -> Optional[Person]:
        tokens = normalized.split(" ")
        if len(tokens) != 1:
            return None
        surname = tokens[0]
        matches = list(
            Person.objects.filter(normalized_name__endswith=f" {surname}")
            .only("id", "canonical_name", "normalized_name", "aliases", "mention_count")
        )
        if len(matches) == 1:
            return matches[0]
        return None
