import pytest

from app.services.prompt_registry import prompt_registry


def test_prompt_registry_registered_stages():
    stages = prompt_registry.list_stages()
    expected = [
        "event_extraction",
        "contradiction_detection",
        "source_comparison",
        "summary_generation",
        "summary_reflection",
        "cluster_verification",
    ]
    for stage in expected:
        assert stage in stages


def test_prompt_template_message_generation():
    prompt = prompt_registry.get("event_extraction")
    assert prompt.version is not None
    assert prompt.system is not None

    system_msg = prompt.system_message()
    assert system_msg["role"] == "system"
    assert system_msg["content"] == prompt.system

    user_msg = prompt.user_message(
        title="Test Article",
        source_name="Reuters",
        published_at="2026-06-29T12:00:00Z",
        content="This is a test article body.",
    )
    assert user_msg["role"] == "user"
    assert "Test Article" in user_msg["content"]
    assert "Reuters" in user_msg["content"]
    assert "This is a test article body." in user_msg["content"]

    messages = prompt.messages(
        title="Test Article",
        source_name="Reuters",
        published_at="2026-06-29T12:00:00Z",
        content="This is a test article body.",
    )
    assert len(messages) == 2
    assert messages[0] == system_msg
    assert messages[1] == user_msg


def test_prompt_template_missing_placeholder():
    prompt = prompt_registry.get("event_extraction")
    with pytest.raises(KeyError):
        prompt.user_message(title="Only Title Provided")
