"""The summary repair script must actually trigger synthesis.

synthesize_story short-circuits any story whose article set is unchanged:

    if is_guard_hit and trigger not in ("manual_regenerate", "replay", "admin_override"):
        logger.info("Incremental updates guard hit. Skipping synthesis ...")
        return

Repairing a summary never changes the article set, so the guard always fires.
The script passed trigger="summary_repair", which is not a bypass, so every
repair was skipped — and because the skip only logs, the script then re-read the
unchanged story and reported it as "STILL DUPLICATED", giving no hint that no
synthesis had been attempted at all.
"""

import inspect
import re

from app.services.story_synthesis_service import StorySynthesisOrchestrator


def _guard_bypass_triggers() -> set[str]:
    """The triggers synthesize_story actually honours, read from the source."""
    src = inspect.getsource(StorySynthesisOrchestrator.synthesize_story)
    match = re.search(r"trigger not in \(([^)]*)\)", src)
    assert match, "the incremental updates guard is no longer recognisable"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_repair_script_uses_a_trigger_that_bypasses_the_guard():
    from app.scripts import resynthesize_duplicate_summaries as script

    src = inspect.getsource(script.main)
    used = re.search(r'trigger="([^"]+)"', src)
    assert used, "the repair script no longer passes a trigger"

    assert used.group(1) in _guard_bypass_triggers(), (
        f"trigger {used.group(1)!r} does not bypass the incremental updates guard, "
        f"so every repair is silently skipped"
    )
