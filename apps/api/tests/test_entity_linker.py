"""Unit tests for the EntityLinker and coreference heuristics."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.entity_linker import (
    EntityResolution,
    are_coreferent_orgs,
    are_coreferent_persons,
    entity_linker,
)


def test_coreferent_persons():
    """Verify person name coreference heuristics."""
    # Match suffix / token containment
    assert are_coreferent_persons("Donald Trump", "Trump") is True
    assert are_coreferent_persons("Rahul Gandhi", "Gandhi") is True
    assert are_coreferent_persons("Gandhi", "Rahul Gandhi") is True

    # Same name is coreferent
    assert are_coreferent_persons("Rahul Gandhi", "Rahul Gandhi") is True

    # Different people with same last name should NOT merge if both have first names
    assert are_coreferent_persons("Donald Trump", "Melania Trump") is False
    assert are_coreferent_persons("Rahul Gandhi", "Sonia Gandhi") is False


def test_coreferent_orgs():
    """Verify organization/company coreference heuristics."""
    # Substring with corporate suffix removal
    assert are_coreferent_orgs("Microsoft Corp", "Microsoft") is True
    assert are_coreferent_orgs("Google Inc.", "Google") is True
    assert are_coreferent_orgs("Apple Incorporated", "Apple") is True

    # Acronyms
    assert are_coreferent_orgs("Bharatiya Janata Party", "BJP") is True
    assert are_coreferent_orgs("BJP", "Bharatiya Janata Party") is True
    assert are_coreferent_orgs("Supreme Court", "SC") is True


def test_group_entities_locally():
    """Verify grouping entities locally in a story cluster."""
    raw_entities = [
        {"value": "Donald Trump", "type": "PERSON"},
        {"value": "Trump", "type": "PERSON"},
        {"value": "BJP", "type": "ORG"},
        {"value": "Bharatiya Janata Party", "type": "ORG"},
    ]

    groups = entity_linker.group_entities_locally(raw_entities)

    # Should have 2 representatives: "Donald Trump" and "Bharatiya Janata Party" (or BJP based on length)
    assert "Donald Trump" in groups
    assert "Bharatiya Janata Party" in groups or "BJP" in groups

    # Check Trump grouping
    trump_group = groups["Donald Trump"]
    assert len(trump_group) == 2
    assert any(g["value"] == "Donald Trump" for g in trump_group)
    assert any(g["value"] == "Trump" for g in trump_group)

    # Check BJP grouping
    bjp_key = "Bharatiya Janata Party" if "Bharatiya Janata Party" in groups else "BJP"
    bjp_group = groups[bjp_key]
    assert len(bjp_group) == 2


@pytest.mark.asyncio
@patch("app.services.entity_linker.cache_service.get")
@patch("app.services.entity_linker.cache_service.set")
@patch("app.services.entity_linker.entity_linker._disambiguate_with_llm")
@patch("app.services.entity_linker.entity_linker._query_wikidata")
async def test_link_entity_new(
    mock_wikidata, mock_llm, mock_cache_set, mock_cache_get, mock_db_session
):
    """Verify resolving and linking a new entity to Wikidata and saving to DB."""
    # Setup mocks
    mock_cache_get.return_value = None  # Cache miss
    mock_llm.return_value = EntityResolution(
        canonical_name="Rahul Gandhi",
        wikidata_search_query="Rahul Gandhi politician",
        description="Indian politician",
    )
    mock_wikidata.return_value = {
        "wikidata_id": "Q981309",
        "description": "Indian politician, member of parliament",
        "label": "Rahul Gandhi",
    }

    # Mock DB execute returning no existing record
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_execute_result

    # Call linker
    res = await entity_linker.link_entity(
        name="Gandhi",
        entity_type="PERSON",
        context="Rahul Gandhi led a rally.",
        session=mock_db_session,
    )

    # Check results
    assert res.canonical_name == "Rahul Gandhi"
    assert res.wikidata_id == "Q981309"
    assert res.entity_type == "PERSON"
    assert "Gandhi" in res.aliases
    assert res.metadata_payload["description"] == "Indian politician, member of parliament"

    # Verify session.add was called
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called()

    # Verify cache write
    mock_cache_set.assert_called_once()


def test_ambiguity_checking():
    """Verify ambiguity detection on names."""
    assert entity_linker._is_name_ambiguous("Washington") is True
    assert entity_linker._is_name_ambiguous("apple") is True
    assert entity_linker._is_name_ambiguous("Jordan") is True
    assert entity_linker._is_name_ambiguous("Donald Trump") is False
    assert entity_linker._is_name_ambiguous("Supreme Court of India") is False


def test_confidence_scoring():
    """Verify confidence score calculations based on Wikidata results."""
    # High confidence: Unambiguous name + keyword match
    results_high = [{"id": "Q90", "label": "Paris", "description": "Capital city of France"}]
    conf_high = entity_linker._assess_confidence("Paris", "CITY", results_high)
    assert conf_high >= 0.8

    # Low confidence: Ambiguous name + multiple competing results
    results_low = [
        {"id": "Q312", "label": "Apple", "description": "American technology company"},
        {"id": "Q89", "label": "Apple", "description": "Edible fruit produced by an apple tree"},
    ]
    conf_low = entity_linker._assess_confidence("Apple", "COMPANY", results_low)
    assert conf_low < 0.8


@pytest.mark.asyncio
@patch("app.services.entity_linker.cache_service.get")
@patch("app.services.entity_linker.cache_service.set")
@patch("app.services.entity_linker.entity_linker._disambiguate_with_llm")
@patch("app.services.entity_linker.entity_linker._query_wikidata_multi")
@patch("app.services.entity_linker.entity_linker._query_wikidata")
async def test_link_entity_hybrid_high_conf(
    mock_query_wiki,
    mock_query_wiki_multi,
    mock_llm,
    mock_cache_set,
    mock_cache_get,
    mock_db_session,
):
    """Verify that a high-confidence entity skips LLM disambiguation in hybrid mode."""
    # Setup mocks
    mock_cache_get.return_value = None  # Cache miss
    # Mock Wikidata returning a single, high confidence result
    mock_query_wiki_multi.return_value = [
        {"id": "Q142", "label": "France", "description": "Country in Western Europe"}
    ]
    mock_query_wiki.return_value = {
        "wikidata_id": "Q142",
        "description": "Country in Western Europe",
        "label": "France",
    }

    # Mock DB execute returning no existing record
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_execute_result

    # Call linker with default "hybrid" mode
    with patch("app.services.entity_linker.settings") as mock_settings:
        mock_settings.ENTITY_LINKING_MODE = "hybrid"

        res = await entity_linker.link_entity(
            name="France",
            entity_type="COUNTRY",
            context="France is in Europe.",
            session=mock_db_session,
        )

    # Verify LLM was NOT called
    mock_llm.assert_not_called()
    assert res.canonical_name == "France"
    assert res.wikidata_id == "Q142"


@pytest.mark.asyncio
@patch("app.services.entity_linker.cache_service.get")
@patch("app.services.entity_linker.cache_service.set")
@patch("app.services.entity_linker.entity_linker._disambiguate_with_llm")
@patch("app.services.entity_linker.entity_linker._query_wikidata_multi")
@patch("app.services.entity_linker.entity_linker._query_wikidata")
async def test_link_entity_hybrid_low_conf(
    mock_query_wiki,
    mock_query_wiki_multi,
    mock_llm,
    mock_cache_set,
    mock_cache_get,
    mock_db_session,
):
    """Verify that a low-confidence entity falls back to LLM disambiguation in hybrid mode."""
    # Setup mocks
    mock_cache_get.return_value = None  # Cache miss
    # Mock Wikidata returning ambiguous results (forces confidence below 0.8)
    mock_query_wiki_multi.return_value = [
        {"id": "Q312", "label": "Apple", "description": "American technology company"},
        {"id": "Q89", "label": "Apple", "description": "Edible fruit"},
    ]
    mock_llm.return_value = EntityResolution(
        canonical_name="Apple Inc.",
        wikidata_search_query="Apple Inc. tech company",
        description="American multinational technology company",
    )
    mock_query_wiki.return_value = {
        "wikidata_id": "Q312",
        "description": "American technology company",
        "label": "Apple Inc.",
    }

    # Mock DB execute returning no existing record
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_execute_result

    # Call linker with default "hybrid" mode
    with patch("app.services.entity_linker.settings") as mock_settings:
        mock_settings.ENTITY_LINKING_MODE = "hybrid"

        res = await entity_linker.link_entity(
            name="Apple",
            entity_type="COMPANY",
            context="Apple announced a new product.",
            session=mock_db_session,
        )

    # Verify LLM WAS called due to low confidence
    mock_llm.assert_called_once()
    assert res.canonical_name == "Apple Inc."
    assert res.wikidata_id == "Q312"
