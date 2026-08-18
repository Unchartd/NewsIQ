"""The normalization layer that keeps false differences out of candidates.

Measured before it existed (docs/Source_Comparison_Audit.md): 49% of sampled
story_differences rows listed a fact as unique to a source that also appeared
in the same row's "missing" list once lowercased. `Colombian government` vs
`Colombian Government` was published as a unique fact, an omission, and a
contradiction simultaneously — the trigger case is pinned here verbatim.
"""

import uuid

from app.services.fact_normalization import (
    CanonicalResolver,
    facts_equivalent,
    normalize_fact,
    numbers_conflict,
    partition_unique,
    sets_share_a_fact,
)

# ── The production trigger case ──────────────────────────────────────────────

HERALD = ["Colombian government", "El Salvador", "Mexico", "US", "international aid agencies"]
HUFFPOST = [
    "Colombian Government",
    "International Aid Organizations",
    "Regional Partners",
    "Rescue Teams",
]


def test_case_variants_are_the_same_fact():
    assert facts_equivalent("Colombian government", "Colombian Government")


def test_the_trigger_story_sets_are_not_disjoint():
    """Both actor lists name the Colombian government; the disjoint-set
    contradiction candidate must not fire."""
    assert sets_share_a_fact(set(HERALD), set(HUFFPOST))


def test_case_variant_is_neither_unique_nor_missing():
    unique = partition_unique(set(HERALD), set(HUFFPOST))
    assert "Colombian government" not in unique
    missing = partition_unique(set(HUFFPOST), set(HERALD))
    assert "Colombian Government" not in missing


def test_genuinely_unique_facts_survive():
    unique = partition_unique(set(HERALD), set(HUFFPOST))
    assert "El Salvador" in unique
    assert "Mexico" in unique


# ── normalize_fact ───────────────────────────────────────────────────────────


def test_normalization_folds_case_punctuation_articles_whitespace():
    assert normalize_fact("The  Colombian   Government.") == "colombian government"
    assert normalize_fact("U.S.") == normalize_fact("US")
    assert normalize_fact("  ") == ""
    assert normalize_fact("") == ""


# ── facts_equivalent ─────────────────────────────────────────────────────────


def test_containment_means_specialization():
    """'western Colombia' is 'Colombia', one more specific — same place."""
    assert facts_equivalent("western Colombia", "Colombia")
    assert facts_equivalent("Colombia (Cali, Pereira)", "Cali, Pereira")


def test_short_fragments_do_not_merge_by_containment():
    """'US' must not swallow 'USA Today' — short strings need exact equality."""
    assert not facts_equivalent("US", "USA Today")


def test_different_facts_stay_different():
    assert not facts_equivalent("Russia", "Ukraine")
    assert not facts_equivalent("15 dead", "50 dead")


# ── CanonicalResolver ────────────────────────────────────────────────────────


def test_canonical_identity_beats_text_dissimilarity():
    """'US' and 'United States' share no text, but entity linking knows they
    are one entity — the resolver must make them compare equal."""
    us = uuid.uuid4()
    resolver = CanonicalResolver()
    resolver.add("US", us)
    resolver.add("United States", us)

    unique = partition_unique({"US"}, {"United States"}, resolver)
    assert unique == set()
    assert sets_share_a_fact({"US"}, {"United States"}, resolver)


def test_unresolved_text_still_compares_textually():
    resolver = CanonicalResolver()
    resolver.add("US", uuid.uuid4())
    unique = partition_unique({"Colombian government"}, {"Colombian Government"}, resolver)
    assert unique == set()


# ── numbers_conflict ─────────────────────────────────────────────────────────


def test_formatting_variants_of_a_number_do_not_conflict():
    """The incremental path used bare !=, so '15' vs '15.0' was a candidate."""
    assert not numbers_conflict("15", "15.0")
    assert not numbers_conflict(15, 15.0)
    assert not numbers_conflict(100, 101)  # <=1 absolute


def test_within_ten_percent_does_not_conflict():
    assert not numbers_conflict(100, 108)


def test_genuine_numeric_disagreement_conflicts():
    assert numbers_conflict(15, 50)
    assert numbers_conflict("10", "50")


def test_non_numeric_values_compare_normalized():
    assert not numbers_conflict("Two Dozen", "two dozen")
    assert numbers_conflict("two dozen", "three dozen")


# ── The "dimaagi Naxals" story (6 sources, replayed from production) ─────────
# Each example is owned by a specific layer; the text tier takes exactly the
# ones that need no identity knowledge or semantics.


def test_alternative_geographic_representations_merge():
    """'Red Fort, Delhi, India' vs 'Red Fort, New Delhi, India': no substring
    relationship, but one word set contains the other — same place."""
    assert facts_equivalent("Red Fort, Delhi, India", "Red Fort, New Delhi, India")


def test_transliteration_spelling_drift_merges():
    """'Dimaagi' vs 'dimagi' is one Hindi word romanized two ways."""
    assert facts_equivalent("Dimaagi Naxals", "dimagi Naxals")
    assert facts_equivalent(
        "ideological Naxalism (dimagi Naxalism)", "ideological Naxalism (dimaagi Naxalism)"
    )


def test_person_aliases_are_not_the_text_tiers_call():
    """'PM Modi' vs 'Narendra Modi' is identity knowledge — the canonical
    entity layer and validator own it. A text tier that guessed would merge
    'Lalit Modi' into 'Narendra Modi' eventually."""
    assert not facts_equivalent("PM Modi", "Narendra Modi")
    assert not facts_equivalent("Lalit Modi", "Narendra Modi")


def test_fuzzy_tier_never_touches_numeric_facts():
    """'15 dead' vs '50 dead' scores 0.86 on SequenceMatcher — close enough
    to be dangerous, which is why digits opt out of the fuzzy tier."""
    assert not facts_equivalent("15 dead", "50 dead")
    assert not facts_equivalent("2 PM", "3 PM")


def test_fuzzy_tier_keeps_near_miss_entities_apart():
    assert not facts_equivalent("north korea", "south korea")
    assert not facts_equivalent("Intellectual Naxals", "Intellectual critics")
