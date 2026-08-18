"""One-off remediation for the fail-open contradiction validator.

Context
-------
ContradictionService generated candidate mismatches with deliberately loose
heuristics (disjoint actor sets, any location string that is not a substring of
the other, a >10% numeric gap) and used an LLM to gate the false positives. Its
own docstring says so: the LLM is there "to ensure high precision".

That gate failed *open*. When no model could be reached it returned
is_contradiction=True, confidence=0.70, and the raw candidate as its
description. Gemini's free tier was exhausted for most of the window measured
(29,524 of 30,170 calls returned RESOURCE_EXHAUSTED), so the gate was almost
never closed.

Result: 3,748 of 3,988 rows (94%) were published as contradictions that no
model ever adjudicated. They render on the story page and are emitted into
JSON-LD, so the product was making machine-readable claims that two named
publishers contradicted each other on evidence nothing had examined. Their
descriptions are raw Python reprs, e.g.

    Mismatch on target: Business Standard reports '['Accused individuals
    (8 named + unidentified)', ...

Selector
--------
confidence = 0.70 AND description LIKE 'Mismatch on %'

Both signatures are produced only by the removed fallback. Measured in
production they agree exactly — 3,748 rows match either condition and 3,748
match both, with zero disagreement — so no LLM-validated row is caught.

story_differences carries copies
--------------------------------
SourceComparisonService joined every StoryContradiction.description into the
per-source `contradictions` column, so the fabricated text was snapshotted
into a second table. Its own deterministic fallback also published the raw
heuristic strings ("unique actors: …" / "omitted actors: …") whenever the LLM
was unreachable — 56-66% of all rows. Each signature is handled at the COLUMN
level, with its provenance:

  contradictions       LIKE 'Mismatch on %'  → fail-open fallback copy  → NULL
  unique_information   LIKE 'unique %'       → raw heuristic passthrough → NULL
  missing_information  LIKE 'omitted %'      → raw heuristic passthrough → NULL

A column an LLM actually wrote never matches these prefixes (validated output
is prose or NULL). Rows where all three columns end up NULL are deleted, and
their coverage rows go with them — a coverage row whose difference row was
pure fallback was produced by the same unvalidated run.

What this does NOT do
---------------------
It does not re-run validation. Stories left with no contradictions or
comparison are correct: absence of an adjudicated claim is the honest state.
Synthesis will re-derive them, now against a chain that can reach Bedrock
when Gemini is spent, with a validator prompt and fail-closed writes.

Usage
-----
    python -m app.scripts.purge_unvalidated_contradictions            # dry run
    python -m app.scripts.purge_unvalidated_contradictions --execute
"""

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.core.database import async_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("purge_unvalidated_contradictions")

# The signature of the removed heuristic fallback. Both halves are required:
# either alone would be a heuristic, together they are the fallback's exact
# and unique output.
_SELECTOR = "confidence = 0.70 AND description LIKE 'Mismatch on %'"

_COUNTS = {
    "story_contradictions (total)": "SELECT count(*) FROM story_contradictions",
    "unvalidated (to delete)": f"SELECT count(*) FROM story_contradictions WHERE {_SELECTOR}",
    "validated (to keep)": f"SELECT count(*) FROM story_contradictions WHERE NOT ({_SELECTOR})",
    "stories affected": (
        f"SELECT count(DISTINCT story_id) FROM story_contradictions WHERE {_SELECTOR}"
    ),
    "stories keeping >=1 validated row": (
        f"SELECT count(DISTINCT story_id) FROM story_contradictions WHERE NOT ({_SELECTOR})"
    ),
}

# Column-level signatures of unvalidated content in story_differences, each
# with its provenance. The LLM never wrote text with these prefixes; only the
# removed fallbacks did.
_DIFF_COLUMNS = {
    "contradictions": (
        "contradictions LIKE 'Mismatch on %'",
        "copies of the fail-open contradiction fallback",
    ),
    "unique_information": (
        "unique_information LIKE 'unique %'",
        "raw heuristic passthrough (deterministic fallback)",
    ),
    "missing_information": (
        "missing_information LIKE 'omitted %'",
        "raw heuristic passthrough (deterministic fallback)",
    ),
}


async def run(execute: bool) -> None:
    async with async_session_factory() as session:
        logger.info("--- scope ---")
        for name, sql in _COUNTS.items():
            n = (await session.execute(text(sql))).scalar()
            logger.info("%-38s %s", name, n)

        # Guard against a selector that has drifted into matching real rows.
        # If the two halves ever disagree, the assumption behind this script no
        # longer holds and it must not run.
        by_conf = (
            await session.execute(
                text("SELECT count(*) FROM story_contradictions WHERE confidence = 0.70")
            )
        ).scalar()
        by_desc = (
            await session.execute(
                text(
                    "SELECT count(*) FROM story_contradictions "
                    "WHERE description LIKE 'Mismatch on %'"
                )
            )
        ).scalar()
        by_both = (
            await session.execute(
                text(f"SELECT count(*) FROM story_contradictions WHERE {_SELECTOR}")
            )
        ).scalar()

        if by_conf != by_both or by_desc != by_both:
            logger.error(
                "Selector halves disagree (confidence=0.70: %s, description: %s, both: %s). "
                "An LLM-validated row may now share a signature with the fallback. "
                "Refusing to delete — re-derive the selector before running this.",
                by_conf,
                by_desc,
                by_both,
            )
            return

        logger.info("selector halves agree exactly (%s rows); no validated row is caught", by_both)

        logger.info("--- story_differences scope (column-level) ---")
        for column, (predicate, provenance) in _DIFF_COLUMNS.items():
            n = (
                await session.execute(
                    text(f"SELECT count(*) FROM story_differences WHERE {predicate}")  # noqa: S608
                )
            ).scalar()
            logger.info("%-22s %-6s -> NULL   (%s)", column, n, provenance)

        all_null_pred = " AND ".join(
            f"({pred} OR {col} IS NULL)" for col, (pred, _) in _DIFF_COLUMNS.items()
        )
        fully_unvalidated = (
            await session.execute(
                text(f"SELECT count(*) FROM story_differences WHERE {all_null_pred}")  # noqa: S608
            )
        ).scalar()
        logger.info("difference rows fully unvalidated (to delete): %s", fully_unvalidated)

        if not execute:
            logger.info("DRY RUN — nothing changed. Re-run with --execute to apply.")
            return

        res = await session.execute(
            text(f"DELETE FROM story_contradictions WHERE {_SELECTOR}")  # noqa: S608 — fixed literal
        )
        logger.info("deleted %s unvalidated contradictions", getattr(res, "rowcount", 0))

        # Difference rows that are entirely fallback output disappear with
        # their coverage rows (same unvalidated run produced both); rows with
        # any validated column keep it and only lose the fallback columns.
        # The unqualified column names in the predicate exist only on
        # story_differences, so they bind to `d` here.
        res = await session.execute(
            text(
                "DELETE FROM story_source_coverage sc USING story_differences d "  # noqa: S608
                "WHERE d.story_id = sc.story_id AND d.source_id = sc.source_id "
                f"AND {all_null_pred}"
            )
        )
        logger.info(
            "deleted %s coverage rows from fully-unvalidated runs", getattr(res, "rowcount", 0)
        )

        res = await session.execute(
            text(f"DELETE FROM story_differences WHERE {all_null_pred}")  # noqa: S608
        )
        logger.info("deleted %s fully-unvalidated difference rows", getattr(res, "rowcount", 0))

        for column, (predicate, _) in _DIFF_COLUMNS.items():
            res = await session.execute(
                text(f"UPDATE story_differences SET {column} = NULL WHERE {predicate}")  # noqa: S608
            )
            logger.info("nulled %-22s on %s rows", column, getattr(res, "rowcount", 0))

        await session.commit()
        logger.info("REMEDIATION COMMITTED.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Apply changes (default: dry run).")
    args = parser.parse_args()
    asyncio.run(run(args.execute))


if __name__ == "__main__":
    main()
