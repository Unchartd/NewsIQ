"""A span must persist ids it only learns part-way through its body.

StageSpan inserts its row at entry, before the work has run, and the update on
exit rewrote status, latency, error and metadata — but not article_id or
story_id. Anything the span learned *during* its body was therefore dropped.

The crawl span is the case that matters: it only knows which article it produced
at the very end, and tagging it is what makes /admin/articles/{id}/trace return
a journey instead of a single stage repeated. Measured over 15 hours of
production after that tagging shipped:

    crawl outcomes : SUCCESS 1,486 · EXTRACTION_FAILED 1,552 · BUDGET_EXCEEDED 404
    articles created                      : 1,618
    crawl spans carrying an article_id    : 0 of 3,896

The tagging code was correct; the persistence path silently discarded it. Which
is why this is tested against behaviour — the assignment existing in the source
proved nothing.
"""

from pathlib import Path

import app.core.trace as trace_module

# conftest replaces StageSpan._persist_db_status with an AsyncMock so the suite
# never writes to a database, which makes inspect.getsource unusable here. The
# source is read from the file instead, so this test does not depend on which
# attributes conftest has swapped out.
TRACE_SRC = Path(trace_module.__file__).read_text(encoding="utf-8")


def _persist_source() -> str:
    start = TRACE_SRC.index("async def _persist_db_status")
    end = TRACE_SRC.index("\n    def ", start)
    return TRACE_SRC[start:end]


def _update_branch() -> str:
    """The branch taken when the row already exists (i.e. every span exit)."""
    src = _persist_source()
    # The else: following `if not stage_run:` is the update path.
    idx = src.index("if not stage_run:")
    return src[src.index("else:", idx) :]


def test_update_path_persists_a_late_bound_article_id():
    branch = _update_branch()
    assert "stage_run.article_id" in branch, (
        "the crawl span learns its article_id at the end of its body; without "
        "this the assignment is silently discarded and lineage has no entry point"
    )


def test_update_path_persists_a_late_bound_story_id():
    assert "stage_run.story_id" in _update_branch()


def test_late_ids_are_only_ever_set_never_cleared():
    """A later None must not wipe an id an earlier assignment established."""
    branch = _update_branch()
    assert "if self.article_id:" in branch, "article_id must be written conditionally"
    assert "if self.story_id:" in branch, "story_id must be written conditionally"


def test_insert_path_still_seeds_from_context():
    """A span that knows its ids up front must keep working unchanged."""
    src = _persist_source()
    insert_branch = src[
        src.index("if not stage_run:") : src.index("else:", src.index("if not stage_run:"))
    ]
    assert "article_id=" in insert_branch
    assert "article_id_ctx" in insert_branch, (
        "the insert path falls back to the context var; that behaviour is unchanged"
    )
