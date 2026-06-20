"""Unit tests for the EntityLinker and coreference heuristics."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.models import CanonicalEntity
from app.services.entity_linker import (
    entity_linker,
    are_coreferent_persons,
    are_coreferent_orgs,
    EntityResolution,
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
