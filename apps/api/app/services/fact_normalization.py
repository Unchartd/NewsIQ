"""Normalization for cross-source fact comparison.

Event fields (actors, targets, locations) are free text produced by
per-article LLM extraction, and no two articles phrase an entity identically.
Comparing them verbatim made nearly everything a "difference": measured in
production, 49% of sampled story_differences rows listed at least one item as
unique to a source that also appeared in that same row's "missing" list once
lowercased — `Colombian government` vs `Colombian Government` published as a
unique fact, an omission, and a contradiction simultaneously.

Comparison happens in two tiers:

1. **Canonical identity.** Where the entity-linking layer has resolved a
   surface form to a canonical entity, two mentions are the same fact iff they
   share a canonical id — `casefold` never has to be right about "US" vs
   "United States" because wikidata already is.
2. **Normalized text.** Everything else compares casefolded, punctuation- and
   whitespace-normalized, with containment folding ("Colombia" adds nothing
   next to "western Colombia").

This module is deliberately deterministic and cheap: it removes the false
differences that no model should ever be asked about. Genuine paraphrases
("Civilians" vs "civilian population") survive it and are the LLM validator's
job to reject.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# Leading articles carry no identity: "the Colombian government" is
# "Colombian government".
_LEADING_ARTICLES = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)
# Periods and apostrophes glue abbreviations together ("U.S." is "US",
# "gov't" is "govt") — delete them. Everything else punctuation-like
# separates words ("Cali, Pereira") — turn it into a space.
_PUNCT_DELETE = re.compile(r"[.'’]")
_PUNCT_SPACE = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")

# Containment folding needs enough signal that "US" does not swallow
# "USA Today" — short fragments only merge on exact equality.
_MIN_CONTAINMENT_LEN = 5

# Spelling-drift tier: high enough that "north korea" vs "south korea"
# (~0.82) stays apart; "dimaagi naxals" vs "dimagi naxals" is 0.96.
_FUZZY_RATIO = 0.90
_HAS_DIGIT = re.compile(r"\d")


def normalize_fact(text: str) -> str:
    """Reduce a free-text fact to a comparison key.

    NFKC-fold unicode, casefold, drop leading articles, strip punctuation,
    collapse whitespace. Returns "" for empty/whitespace input.
    """
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", text).casefold().strip()
    norm = _LEADING_ARTICLES.sub("", norm)
    norm = _PUNCT_DELETE.sub("", norm)
    norm = _PUNCT_SPACE.sub(" ", norm)
    return _WS.sub(" ", norm).strip()


def facts_equivalent(a: str, b: str) -> bool:
    """True when two free-text facts are the same fact, not merely similar.

    Four tiers, all replayed against the production story that motivated them
    ("dimaagi Naxals", 6 sources, 19 false contradiction candidates):

    1. Equality after normalization.
    2. Containment, when both sides are long enough for containment to mean
       specialization rather than coincidence ("western colombia" ⊃
       "colombia" — same place, one more specific).
    3. Token subset: "Red Fort, Delhi, India" and "Red Fort, New Delhi,
       India" share no substring relationship, but one's word set contains
       the other's — same place, one extra word. Guarded by the same length
       floor so "US" cannot swallow "USA Today".
    4. Spelling drift: "Dimaagi Naxals" vs "dimagi Naxals" is a
       transliteration variant, not two facts. SequenceMatcher at >=0.9,
       only when NEITHER side contains a digit — "15 dead" vs "50 dead"
       scores 0.86 on the same scale and must never merge, so numeric facts
       are excluded from this tier outright.

    What deliberately stays non-equivalent here: person aliases ("PM Modi" vs
    "Narendra Modi") and rephrasings ("Government of India" vs "Indian
    Government"). Those need identity knowledge or semantics — the canonical
    entity layer and the LLM validator own them, per the pipeline's ownership
    rules. A text tier that guessed at them would merge "Lalit Modi" into
    "Narendra Modi" eventually.
    """
    na, nb = normalize_fact(a), normalize_fact(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if len(na) < _MIN_CONTAINMENT_LEN or len(nb) < _MIN_CONTAINMENT_LEN:
        return False
    if na in nb or nb in na:
        return True

    # issubset, not `<=`: subset is a partial order, so this is NOT the
    # tautology `x <= y or y <= x` would be for numbers — {red, fort, delhi}
    # vs {red, fort, agra} fails both directions. The method form says so.
    ta, tb = set(na.split()), set(nb.split())
    if ta.issubset(tb) or tb.issubset(ta):
        return True

    if not _HAS_DIGIT.search(na) and not _HAS_DIGIT.search(nb):
        if SequenceMatcher(None, na, nb).ratio() >= _FUZZY_RATIO:
            return True
    return False


@dataclass
class CanonicalResolver:
    """Maps normalized surface forms to canonical entity ids.

    Built from the story's article_entities (surface form → canonical id) plus
    the canonical entities' own names and aliases, so "US", "United States"
    and "U.S." all resolve to one id when entity linking has done its work.
    """

    _by_surface: dict[str, uuid.UUID] = field(default_factory=dict)

    def add(self, surface: str, canonical_id: uuid.UUID | None) -> None:
        if not canonical_id:
            return
        key = normalize_fact(surface)
        if key:
            # First mapping wins: entity rows arrive ordered by confidence
            # where the caller cares, and a stable answer beats a flapping one.
            self._by_surface.setdefault(key, canonical_id)

    def resolve(self, text: str) -> uuid.UUID | None:
        return self._by_surface.get(normalize_fact(text))

    def __len__(self) -> int:
        return len(self._by_surface)


def partition_unique(
    src_items: set[str],
    other_items: set[str],
    resolver: CanonicalResolver | None = None,
) -> set[str]:
    """Items in *src_items* that state a fact absent from *other_items*.

    An item is NOT unique when the other side has an equivalent: the same
    canonical entity, an equal normalized form, or a containment match. The
    surviving originals are returned verbatim so downstream text keeps the
    source's own words.
    """
    resolver = resolver or CanonicalResolver()
    other_canon = {c for c in (resolver.resolve(o) for o in other_items) if c}
    unique: set[str] = set()

    for item in src_items:
        canon = resolver.resolve(item)
        if canon and canon in other_canon:
            continue
        if any(facts_equivalent(item, other) for other in other_items):
            continue
        unique.add(item)
    return unique


def sets_share_a_fact(
    a_items: set[str],
    b_items: set[str],
    resolver: CanonicalResolver | None = None,
) -> bool:
    """True when any fact in *a_items* is equivalent to any in *b_items*.

    The candidate heuristics treat fully disjoint actor/target sets as a
    contradiction signal. Verbatim disjointness fired on pure case variants;
    this is the check they should have been making.
    """
    resolver = resolver or CanonicalResolver()
    b_canon = {c for c in (resolver.resolve(b) for b in b_items) if c}
    for a in a_items:
        canon = resolver.resolve(a)
        if canon and canon in b_canon:
            return True
        if any(facts_equivalent(a, b) for b in b_items):
            return True
    return False


def normalize_number_key(key: str) -> str:
    return normalize_fact(key)


def numbers_conflict(v1: object, v2: object) -> bool:
    """True when two numeric claims genuinely disagree.

    Mirrors the batch heuristic (>10% relative AND >1 absolute), so
    "15" vs "15.0" or 100 vs 101 never become candidates. Non-numeric values
    conflict only when their normalized text differs.
    """
    try:
        f1, f2 = float(v1), float(v2)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return normalize_fact(str(v1)) != normalize_fact(str(v2))
    if abs(f1 - f2) <= 1:
        return False
    biggest = max(abs(f1), abs(f2))
    return biggest > 0 and abs(f1 - f2) / biggest > 0.10
