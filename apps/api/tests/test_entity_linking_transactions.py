"""Regression tests for the event-extraction batch collapse.

Two production traces (80d9cf55, 0895abe6) lost entire 20-article batches:

    cannot call PreparedStatement.fetch(): the underlying connection is closed
    [SQL: UPDATE articles SET event_extraction_status=$1 WHERE articles.id = $2]

    This Session's transaction has been rolled back due to a previous exception
    during flush. ... Can't reconnect until invalid transaction is rolled back.

Stage duration 71s and 114s for 20 articles.

Cause: link_entity opens a transaction with its lookup SELECTs, then performs
network I/O — a Wikidata HTTP round-trip and, on low confidence, an LLM
disambiguation call — with that transaction still open, repeated for up to 20
entities per article. Postgres kills a backend idle in transaction after 30s
(production setting), so the connection died mid-loop.

Amplifier: the per-article handler called commit() on the already-poisoned
session without rolling back first. That raised again from inside the handler,
escaped the per-article try, and destroyed the rest of the batch — which is why
both traces show output.json = {} despite the first article succeeding.
"""

import inspect


def test_entity_linking_releases_its_transaction_before_network_calls():
    """A DB transaction must not be held across Wikidata/LLM round-trips."""
    from app.services.entity_linker import entity_linker

    src = inspect.getsource(entity_linker.link_entity)

    commit_idx = src.index("await session.commit()")
    wikidata_idx = src.index("_query_wikidata_multi")
    llm_idx = src.index("_disambiguate_with_llm")

    assert commit_idx < wikidata_idx, (
        "the read transaction is still open during the Wikidata call — "
        "idle_in_transaction_session_timeout will kill the connection"
    )
    assert commit_idx < llm_idx, "the read transaction is still open during LLM disambiguation"


def test_extraction_failure_rolls_back_before_recording_status():
    """One bad article must not take the remaining batch with it."""
    from app.workers import tasks

    src = inspect.getsource(tasks.extract_events_task)
    failure_idx = src.index('article.event_extraction_status = "failed"')
    preceding = src[:failure_idx]

    # A rollback must occur between entering the handler and touching the DB.
    handler_idx = preceding.rindex("except Exception as e:")
    assert "await session.rollback()" in preceding[handler_idx:], (
        "commit() on a poisoned session raises again from inside the handler "
        "and destroys the rest of the batch"
    )


def test_status_write_failure_is_contained():
    """If the status write itself fails, the loop must continue.

    The article stays 'processing' and is picked up by
    recover_stuck_embeddings_task — recoverable, unlike losing the batch.
    """
    from app.workers import tasks

    src = inspect.getsource(tasks.extract_events_task)
    assert "Could not record failed status for article" in src, (
        "a failing status write must be caught, not allowed to escape"
    )
    assert "recover_stuck_embeddings_task" in src or "recovered by" in src.lower()
