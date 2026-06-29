import pytest

from app.core.config import settings
from app.services.context_extractor import context_extractor


def test_context_extractor_short_text():
    text = "Short text."
    res = context_extractor.extract(text, max_chars=100)
    assert res == text


def test_context_extractor_under_limit():
    paragraphs = [
        "First paragraph of the article.",
        "Second paragraph of the article.",
        "Third paragraph of the article.",
    ]
    text = "\n\n".join(paragraphs)
    res = context_extractor.extract(text, max_chars=500)
    assert res == text


def test_context_extractor_over_limit():
    paragraphs = [
        "Lead paragraph containing important actors and dates of the event.",  # 67 chars
        "Middle paragraph one with auxiliary details.",  # 44 chars
        "Middle paragraph two is extremely long and verbose and contains a lot of filler details that are not super critical for the primary extraction.",  # 146 chars
        "Concluding paragraph showing final outcome of the event.",  # 58 chars
    ]
    text = "\n\n".join(paragraphs)

    # Total length is ~320 chars.
    # Set max_chars to 250.
    # allowed_middle_chars = 250 - 67 - 58 - 50 = 75 chars.
    # Middle 1 (44 chars) fits under 75.
    # Middle 2 (146 chars) does not fit.
    res = context_extractor.extract(text, max_chars=250)

    assert "Lead paragraph" in res
    assert "Concluding paragraph" in res
    assert "Middle paragraph one" in res
    assert "Middle paragraph two" not in res
    assert "[... Content omitted for context window optimization ...]" in res


def test_context_extractor_disabled():
    paragraphs = [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]
    text = "\n\n".join(paragraphs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "CONTEXT_EXTRACTOR_ENABLED", False)
        # Should do naive truncation
        res = context_extractor.extract(text, max_chars=25)
        assert res == text[:25]
        assert len(res) == 25
