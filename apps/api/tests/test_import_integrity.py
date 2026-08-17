"""The application entrypoint must be importable in a cold interpreter.

This is not hypothetical. The pricing consolidation put
`from app.ai.pricing import ...` inside app/core/trace.py's module body.
app/ai/__init__.py imports the gateway, and the gateway imports app.core.trace —
so importing anything under app.ai from trace triggered a circular import and
`import app.main` failed outright:

    ImportError: cannot import name 'track_llm_call' from partially initialized
    module 'app.core.trace' (most likely due to a circular import)

The whole suite still passed, because conftest imports app.services.* first and
that warms app.ai before app.core.trace is reached. So every test was green
while the deployable artifact could not start — the same shape as two earlier
production outages in this codebase, both caused by import-time behaviour that
tests never exercised.

These tests must run in a fresh subprocess. Inside pytest the module graph is
already warm, which is precisely what hides the bug.
"""

import subprocess
import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]

# Entry points that must each stand alone. Anything a container, migration, or
# CLI actually starts from belongs here.
ENTRYPOINTS = [
    "app.main",
    "app.workers.celery_app",
    "app.workers.tasks",
    "app.core.trace",
    "app.ai.gateway",
    "app.core.llm_pricing",
]


def _import_in_fresh_interpreter(module: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=APP_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.parametrize("module", ENTRYPOINTS)
def test_module_imports_standalone(module: str):
    """Each entry point must import with nothing else already loaded."""
    result = _import_in_fresh_interpreter(module)
    assert result.returncode == 0, (
        f"`import {module}` fails in a cold interpreter — the deployable artifact "
        f"cannot start even though the test suite passes.\n"
        f"{result.stderr[-1500:]}"
    )


def test_pricing_does_not_live_under_app_ai():
    """app/ai/__init__.py imports the gateway, which imports app.core.trace.

    Any pricing module under app.ai therefore cannot be imported from trace
    without re-entering a half-initialised module.
    """
    assert not (APP_ROOT / "app" / "ai" / "pricing.py").exists(), (
        "pricing under app.ai reintroduces the circular import; it belongs in a "
        "leaf package such as app/core"
    )


def test_trace_imports_no_app_ai_modules_at_module_level():
    """A module-level app.ai import from trace is the exact defect."""
    source = (APP_ROOT / "app" / "core" / "trace.py").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in source.splitlines()
        # Module level only: indented imports are deferred and therefore safe.
        if (line.startswith("from app.ai") or line.startswith("import app.ai"))
    ]
    assert not offenders, f"app.core.trace must not import app.ai at module level: {offenders}"
