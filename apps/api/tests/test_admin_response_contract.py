"""The admin API's responses must match the frontend's declared types.

The admin app consumed every response as `any`. That is how two defects reached
production without a single failing check:

  * the run summary read `articles_ingested` at the top level of stage metadata,
    a key that has never appeared there for any stage, so every successful run
    rendered "Completed (no actions)"
  * `STATUS_CONFIG` had no `completed` entry, so 1,128 stage runs rendered with
    no icon and no colour

`apps/admin/src/lib/api-types.ts` now declares those shapes. Hand-written types
drift, so these tests parse that file and check it against what the endpoints
actually build. Adding a field to a response without declaring it, or renaming
one the UI reads, fails here rather than silently rendering `undefined`.

Only endpoints returning plain dicts are covered. The 22 endpoints with a
`response_model` are already checked by FastAPI itself.
"""

import re
from pathlib import Path

import pytest

TYPES_FILE = (
    Path(__file__).resolve().parents[2]
    / "admin"
    / "src"
    / "app"
    / ".."
    / ".."
    / "src"
    / "lib"
    / "api-types.ts"
).resolve()

# The path above collapses to apps/admin/src/lib/api-types.ts; resolve plainly.
TYPES_FILE = Path(__file__).resolve().parents[2] / "admin" / "src" / "lib" / "api-types.ts"

pytestmark = pytest.mark.skipif(not TYPES_FILE.exists(), reason="admin app not present")


def _interface_fields(name: str) -> set[str]:
    """Field names declared on a TypeScript interface."""
    text = TYPES_FILE.read_text(encoding="utf-8")
    match = re.search(rf"export interface {name} \{{(.*?)^\}}", text, re.S | re.M)
    assert match, f"interface {name} not found in api-types.ts"

    body = match.group(1)
    # Strip block comments so commented-out names are not counted as fields.
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"//.*", "", body)

    fields = set()
    for line in body.splitlines():
        line = line.strip()
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\??:", line)
        if m:
            fields.add(m.group(1))
    return fields


def _top_level_return_keys(func) -> set[str]:
    """Keys of the final `return { ... }` dict, ignoring nested payloads.

    A flat regex over the source would also collect keys belonging to nested
    objects — `input_tokens` from the LLM trace payload, `avg_latency_ms` from
    the aggregate block — and compare them against the wrong interface.
    """
    import inspect

    src = inspect.getsource(func)
    # Anchor on the first object literal after the final return. That handles
    # both `return {...}` and `return [ {...} for r in rows ]` — in the latter
    # the dict inside the comprehension is the response element.
    start = src.rindex("return ")
    i = src.index("{", start)
    depth = 0
    keys: set[str] = set()
    body = src[i:]
    for match in re.finditer(r'[{}\[\]]|"([a-z_]+)":', body):
        token = match.group(0)
        if token in "{[":
            depth += 1
        elif token in "}]":
            depth -= 1
            if depth == 0:
                break
        elif depth == 1 and match.group(1):
            keys.add(match.group(1))
    assert keys, "no top-level keys found"
    return keys


def _union_members(name: str) -> set[str]:
    text = TYPES_FILE.read_text(encoding="utf-8")
    match = re.search(rf"export type {name} =(.*?);", text, re.S)
    assert match, f"type {name} not found"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


# ── stage detail ──────────────────────────────────────────────────────────────


def test_stage_detail_declares_every_key_the_endpoint_returns():
    """The aggregate fields are what make a 2,079-attempt stage readable."""
    from app.api.v1 import admin

    returned = _top_level_return_keys(admin.get_stage_run_details)
    declared = _interface_fields("StageDetail")

    missing = returned - declared
    assert not missing, (
        f"the endpoint returns fields the frontend has not declared: {sorted(missing)}"
    )


def test_stage_detail_declares_the_aggregate_contract():
    declared = _interface_fields("StageDetail")
    for field in ("attempt_count", "status_counts", "is_aggregated", "aggregate", "attempts"):
        assert field in declared, f"StageDetail must declare {field}"


def test_aggregate_block_matches():
    import inspect

    from app.api.v1 import admin

    src = inspect.getsource(admin.get_stage_run_details)
    block = src[src.index('"aggregate": {') : src.index('"attempts": [')]
    returned = set(re.findall(r'"([a-z_]+)":', block))
    declared = _interface_fields("StageAggregate")
    missing = returned - declared - {"aggregate"}
    assert not missing, f"StageAggregate is missing: {sorted(missing)}"


# ── run list ──────────────────────────────────────────────────────────────────


def test_run_summary_declares_every_key_the_endpoint_returns():
    from app.api.v1 import admin

    returned = _top_level_return_keys(admin.list_pipeline_runs)
    declared = _interface_fields("PipelineRunSummary")

    missing = returned - declared
    assert not missing, (
        f"the run list returns fields the frontend has not declared: {sorted(missing)}"
    )


# ── lineage ───────────────────────────────────────────────────────────────────


def test_article_lineage_declares_its_top_level_keys():
    import inspect

    from app.api.v1 import admin

    src = inspect.getsource(admin.get_article_trace)
    declared = _interface_fields("ArticleLineage")
    for key in ("article", "story", "stages", "story_stages", "llm_traces"):
        assert f'"{key}":' in src, f"endpoint no longer returns {key}"
        assert key in declared, f"ArticleLineage must declare {key}"


# ── status vocabulary ─────────────────────────────────────────────────────────


def test_stage_status_union_covers_every_value_the_backend_writes():
    """`completed` still exists on 1,128 historical rows and must stay handled."""
    from app.core.trace import StageStatus

    declared = _union_members("StageStatus")
    written = {s.value for s in StageStatus}

    missing = written - declared
    assert not missing, f"StageStatus union is missing values the backend writes: {sorted(missing)}"
    assert "completed" in declared, (
        "the historical `completed` value must remain in the union — dropping it "
        "would leave 1,128 rows rendering with no icon and no colour again"
    )


def test_frontend_status_config_handles_every_declared_status():
    """A declared status with no STATUS_CONFIG entry renders unstyled."""
    page = TYPES_FILE.parent.parent / "app" / "admin" / "pipeline" / "page.tsx"
    if not page.exists():
        pytest.skip("pipeline page not present")

    text = page.read_text(encoding="utf-8")
    config = re.search(r"const STATUS_CONFIG[^=]*= \{(.*?)^\};", text, re.S | re.M)
    assert config, "STATUS_CONFIG not found"
    mapped = set(re.findall(r"^\s+([a-z_]+):\s*\{", config.group(1), re.M))

    for status in ("success", "completed", "failed", "running", "skipped"):
        assert status in mapped, f"STATUS_CONFIG does not handle '{status}'"
