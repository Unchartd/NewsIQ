"""Pull the JSON object out of a model reply."""

import json


def extract_json_text(content: str) -> str:
    """Return the first JSON object in ``content``, without what surrounds it.

    Models asked for "only one JSON object" do not always stop there. One
    OpenRouter host for DeepSeek V4 Flash appends its end-of-sequence token
    after a complete, valid object — ``{...}<｜end▁of▁sentence｜>`` — and
    ``json.loads`` rejects the whole reply with "Extra data". That happened to
    190 billed replies in one day, each followed by a paid retry that often
    reached the same host and failed the same way. Markdown fences and a
    leading sentence are the same problem from other models.

    Decoding from the first ``{`` and stopping where the object ends accepts
    the answer the model actually gave. Content with no decodable object is
    returned stripped, so the caller's own parse fails and reports it.
    """
    text = content.strip()
    start = text.find("{")
    if start == -1:
        return text
    try:
        _, end = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError:
        return text
    return text[start:end]
