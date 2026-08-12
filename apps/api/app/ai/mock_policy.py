"""Single decision point for whether mock LLM output may be served.

The mock provider fabricates plausible-looking structured output. Where a real
provider fails, the mock SUCCEEDS — so any code path that can reach it converts
provider failure into silently fabricated data that downstream stages persist
as real. A historic incident wrote 6,584 identical template events (86% of the
event table), which later fused hundreds of unrelated articles into single
stories.

Policy: mock is allowed only in test runs or under an explicit settings opt-in.
Both the llm_gateway fallback chain and the ai capability router consult this
one function, so the rule cannot drift between stacks again.
"""

import sys

from app.core.config import settings


def in_test_run() -> bool:
    """True when executing under pytest/unittest (test doubles are expected)."""
    return "pytest" in sys.modules or any("pytest" in arg or "unittest" in arg for arg in sys.argv)


def mock_allowed() -> bool:
    """True when the mock provider may serve requests at all."""
    return in_test_run() or bool(getattr(settings, "LLM_ALLOW_MOCK", False))
