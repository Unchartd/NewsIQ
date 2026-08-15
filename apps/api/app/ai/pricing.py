"""Single source of truth for LLM token pricing.

There used to be two tables. `PRICING_TABLE` in app/ai/gateway.py carried the
models actually in production; `LLM_PRICING` in app/core/trace.py carried only
gemini-2.x, which this deployment has never run. The gateway computed the right
cost and assigned it to the trace, and then track_llm_call's `finally` block
recomputed it from the stale table and threw the correct value away.

Result: cost_usd was 0.00 on 17,333 of 17,333 llm_traces rows — every LLM call
ever made — and the entire cost dashboard read zero. The silent
`.get(model, {"input": 0.0, "output": 0.0})` default is what let it go unnoticed
for that long, so unknown models are now reported rather than priced at nothing.

Both modules import from here. This module imports neither, so there is no cycle.

Rates are USD per million tokens.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

PRICING_TABLE: dict[str, dict[str, float]] = {
    # ── Gemini (current) ──────────────────────────────────────────────────────
    "gemini-3.1-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-3.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-embedding-001": {"input": 0.025, "output": 0.0},
    "gemini-embedding-2": {"input": 0.025, "output": 0.0},
    # ── Gemini (legacy — retained so historical traces still price) ───────────
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    # ── OpenAI ────────────────────────────────────────────────────────────────
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "openai/text-embedding-3-small": {"input": 0.02, "output": 0.0},
    # ── NVIDIA / DeepSeek ─────────────────────────────────────────────────────
    "deepseek-ai/deepseek-v4-flash": {"input": 0.14, "output": 0.28},
    "deepseek-ai/deepseek-v4-pro": {"input": 0.55, "output": 2.19},
    "nvidia/llama-3.2-nv-embedqa-4b-v1": {"input": 0.0, "output": 0.0},
    # ── OpenRouter ────────────────────────────────────────────────────────────
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    "qwen/qwen-2.5-72b-instruct": {"input": 0.40, "output": 0.40},
    "nomic/nomic-embed-text-v1.5": {"input": 0.0, "output": 0.0},
    "sentence-transformers/all-mpnet-base-v2": {"input": 0.005, "output": 0.0},
    "qwen/qwen3-embedding-8b": {"input": 0.01, "output": 0.0},
    "baai/bge-m3": {"input": 0.01, "output": 0.0},
}

# Models seen in production whose rate has not been confirmed against an invoice.
#
# These are live on Bedrock (225 and 127 calls, 2.3M tokens between them) and
# were in neither of the old tables. They are listed rather than priced because
# a guessed rate produces confidently wrong cost reporting, which is the failure
# this module exists to end. Add them to PRICING_TABLE once the rate is known;
# until then their cost reports as unknown rather than as zero.
UNPRICED_MODELS: frozenset[str] = frozenset(
    {
        "qwen.qwen3-vl-235b-a22b-instruct",
        "deepseek.v3.2",
    }
)

# Models already reported, so the warning fires once per model rather than per call.
_reported_unknown: set[str] = set()


def is_priced(model: str) -> bool:
    """True when a real rate exists for *model*."""
    return model in PRICING_TABLE


def calculate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Cost in USD for a call, or None when the model has no confirmed rate.

    Returning None rather than 0.0 for an unknown model is deliberate: a zero is
    indistinguishable from a free call and reads as authoritative on a dashboard.
    Callers that need a number should treat None as "unknown" and say so.
    """
    pricing = PRICING_TABLE.get(model)
    if pricing is None:
        if model not in _reported_unknown:
            _reported_unknown.add(model)
            logger.warning(
                "No pricing for model %r — its cost will be reported as unknown, not zero. "
                "Add it to app/ai/pricing.PRICING_TABLE once the rate is confirmed.",
                model,
            )
        return None

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 8)
