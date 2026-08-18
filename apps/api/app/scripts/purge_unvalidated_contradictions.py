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

What this does NOT do
---------------------
It does not re-run validation. Stories left with no contradictions are correct:
absence of an adjudicated contradiction is the honest state. Synthesis will
re-derive them, now against a chain that can reach Bedrock when Gemini is spent.

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

        if not execute:
            logger.info("DRY RUN — nothing changed. Re-run with --execute to apply.")
            return

        res = await session.execute(
            text(f"DELETE FROM story_contradictions WHERE {_SELECTOR}")  # noqa: S608 — fixed literal
        )
        logger.info("deleted %s unvalidated contradictions", getattr(res, "rowcount", 0))

        await session.commit()
        logger.info("REMEDIATION COMMITTED.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Apply changes (default: dry run).")
    args = parser.parse_args()
    asyncio.run(run(args.execute))


if __name__ == "__main__":
    main()
