import pytest
from unittest.mock import AsyncMock, patch
from agno.run.agent import RunOutput

from app.agents.cluster_verification_agent import verify_cluster_decision, ClusterVerificationSchema
from app.agents.entity_disambiguation_agent import disambiguate_entity, EntityDisambiguationSchema
from app.agents.contradiction_agent import check_contradiction, ContradictionSchema
from app.agents.reflection_agent import reflect_on_summary, ReflectionSchema
from app.agents.judge_agent import resolve_disagreement, JudgeSchema

@pytest.mark.asyncio
@patch("app.agents.cluster_verification_agent.run_agent_with_observability")
async def test_cluster_verification_agent(mock_run):
    schema_instance = ClusterVerificationSchema(
        same_event=True,
        confidence=0.95,
        explanation="Both describe the same event."
    )
    
    mock_run_output = RunOutput(
        content=schema_instance,
        metrics=None
    )
    mock_run.return_value = mock_run_output
    
    res = await verify_cluster_decision(
        article_a_title="Title A",
        article_a_event={"type": "ATTACK"},
        article_b_title="Title B",
        article_b_event={"type": "ATTACK"},
        similarity_score=0.85
    )
    
    assert res.same_event is True
    assert res.confidence == 0.95
    assert "same event" in res.explanation
    mock_run.assert_called_once()

@pytest.mark.asyncio
@patch("app.agents.entity_disambiguation_agent.run_agent_with_observability")
async def test_entity_disambiguation_agent(mock_run):
    schema_instance = EntityDisambiguationSchema(
        canonical_name="Donald Trump",
        wikidata_id="Q22686",
        entity_type="PERSON",
        explanation="Standardized Trump to Donald Trump."
    )
    
    mock_run_output = RunOutput(
        content=schema_instance,
        metrics=None
    )
    mock_run.return_value = mock_run_output
    
    res = await disambiguate_entity(
        entity_value="Trump",
        entity_type="PERSON",
        context="President Trump gave a speech."
    )
    
    assert res.canonical_name == "Donald Trump"
    assert res.wikidata_id == "Q22686"
    assert res.entity_type == "PERSON"
    mock_run.assert_called_once()

@pytest.mark.asyncio
@patch("app.agents.contradiction_agent.run_agent_with_observability")
async def test_contradiction_agent(mock_run):
    schema_instance = ContradictionSchema(
        contradiction=True,
        field="event_time",
        confidence=0.95,
        explanation="One source says 2 PM and another says 3 PM."
    )
    
    mock_run_output = RunOutput(
        content=schema_instance,
        metrics=None
    )
    mock_run.return_value = mock_run_output
    
    res = await check_contradiction(
        fact_type="event_time",
        val1="2 PM",
        val2="3 PM",
        source1_name="BBC",
        source2_name="TOI"
    )
    
    assert res.contradiction is True
    assert res.field == "event_time"
    assert res.confidence == 0.95
    mock_run.assert_called_once()

@pytest.mark.asyncio
@patch("app.agents.reflection_agent.run_agent_with_observability")
async def test_reflection_agent(mock_run):
    schema_instance = ReflectionSchema(
        has_hallucinations=False,
        invented_facts=[],
        omitted_critical_facts=[],
        contradicts_graph=False,
        explanation="Summary is well grounded."
    )
    
    mock_run_output = RunOutput(
        content=schema_instance,
        metrics=None
    )
    mock_run.return_value = mock_run_output
    
    res = await reflect_on_summary(
        summary_text="Summary text",
        timeline=[{"description": "Event 1"}],
        kg_nodes=[{"id": "node_1"}]
    )
    
    assert res.has_hallucinations is False
    assert res.contradicts_graph is False
    mock_run.assert_called_once()

@pytest.mark.asyncio
@patch("app.agents.judge_agent.run_agent_with_observability")
async def test_judge_agent(mock_run):
    schema_instance = JudgeSchema(
        final_decision=True,
        chosen_provider="gemini",
        explanation="Gemini's reasoning was more detailed."
    )
    
    mock_run_output = RunOutput(
        content=schema_instance,
        metrics=None
    )
    mock_run.return_value = mock_run_output
    
    res = await resolve_disagreement(
        task_description="Verify event merge",
        provider_a_name="gemini",
        provider_a_output={"same_event": True},
        provider_b_name="openai",
        provider_b_output={"same_event": False}
    )
    
    assert res.final_decision is True
    assert res.chosen_provider == "gemini"
    mock_run.assert_called_once()
