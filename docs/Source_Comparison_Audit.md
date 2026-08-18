# Source Comparison & Coverage Audit

**Date:** 2026-08-18
**Scope:** `SourceComparisonService`, `source_comparison.yaml` (system prompt),
`story_source_coverage` / `story_differences` tables, and the "Source Coverage" /
"Where sources differ" story-page sections.
**Trigger:** a production story where `Colombian government` vs
`Colombian Government` was published as a unique fact, an omission, *and* a
contradiction — simultaneously.

Every number below is measured against production (1,171 rows in each table).

---

## Executive summary

The "AI Comparative Analysis" shown to users is, in the majority of rows,
**neither AI nor analysis**. It is a case-sensitive string set-difference over
free-text event fields, passed through a fallback that publishes the raw
heuristic output verbatim when the LLM is unreachable — which, given the quota
situation fixed in #136, was most of the time. The one thing the system prompt
asks the LLM to do when it *is* reachable — "synthesize a clean analysis" —
launders that noise into confident prose instead of filtering it.

```text
story_differences rows                            : 1,171
  unique_information  = raw heuristic string      :   660  (56%)
  missing_information = raw heuristic string      :   770  (66%)
  contradictions      = 'Mismatch on %' template  :   702  (60%)
  Python repr leakage ("['...")                   :   605
  sampled rows where a "unique" item is ALSO
    "missing" once lowercased                     :   196 / 400  (49%)

story_source_coverage rows                        : 1,171
  published_at NULL                               : 1,089  (93%)
  published_at >1h from the article's publish time:    85 / 86 joined (99%)
  focus_area = "Focused on other details."        :   454  (39%)
  multi-source stories with IDENTICAL focus text
    for every source                              :   135 / 289  (47%)
```

---

## Defect chain, in pipeline order

### 1. The heuristic compares un-normalized free text — CONFIRMED

`compare_sources_and_save` builds per-source sets from `event.actors`,
`event.targets`, `event.location`, `event.numbers` — free-text strings produced
by per-article LLM extraction — and takes **verbatim, case-sensitive set
differences** (`source_comparison_service.py:330-338`).

Different articles never phrase entities identically, so nearly everything is
"different":

* `Colombian government` vs `Colombian Government` → unique + missing + disjoint
* `civilian population` vs `Civilians` → same
* `western Colombia` vs `Colombia (Cali, Pereira, ...)` → location "mismatch"

In a 400-row sample, **49% of rows contain at least one item listed as unique
that also appears in that same row's "missing" list once lowercased** — the
same fact, counted as both present and absent. This is the noise floor before
any model is consulted.

The same un-normalized disjoint-set test feeds `ContradictionService`'s
candidates, which is why the pasted story shows actor lists that are obvious
paraphrases of each other flagged as factual contradictions. The canonical
entity layer (`canonical_entity_id`, wikidata IDs, aliases) exists in this
codebase and is not consulted here.

### 2. The system prompt asks the LLM to prettify, not validate — CONFIRMED

`source_comparison.yaml` in full effect:

> "For 'unique_information', 'missing_information', and 'contradictions':
> provide concise, readable descriptions. If none, return empty string."
> … "Synthesize a clean analysis."

Compare `contradiction_detection.yaml`, which at least has rules ("subset
relationships are NOT contradictions… Be conservative"). The source-comparison
prompt has **no validation instruction at all**: nothing says case variants,
synonyms, or paraphrases are not differences; nothing tells the model it may
*reject* the heuristic input; nothing tells it to cross-check the "differences"
against the article context it is given. The heuristic output is presented as
"Differences detected by heuristic engines" — established fact to be
summarized. So even the successful LLM calls dress set-diff noise in
professional-sounding prose.

### 3. The fallback publishes the raw heuristic verbatim — CONFIRMED

`_generate_deterministic_comparison` (`source_comparison_service.py:164`) puts
the un-filtered heuristic strings straight into the columns the UI renders.
That is where the visible `unique actors: …; unique targets: …` strings and
the 605 rows of Python repr (`'['Accused individuals (8 named + …`) come from.

Same violation as the contradiction fallback fixed in #136: a model failure is
replaced by fallback output that *looks* like analysis, with no marker
distinguishing it. 56–66% of all rows are this fallback. The UI labels every
row "AI Comparative Analysis… compiled using AI models" — for the majority of
rows, false.

### 4. Fabricated contradictions were copied into `story_differences` — CONFIRMED

`compare_sources_and_save` step 6 joins **every** `StoryContradiction.description`
involving the source into `contradictions_summary` — including the 3,748
fail-open fabrications. 702 difference rows (60%) carry the `Mismatch on %`
template text.

**Remediation gap:** `purge_unvalidated_contradictions.py` (#136) cleans
`story_contradictions` only. The copies in `story_differences.contradictions`
are snapshots in a separate table and will **survive the purge**. They also
get re-written identically for every source in the story (the pasted example
shows both rows carrying the same three contradictions), so a story's
contradiction list is duplicated N times.

### 5. Structural redundancy: unique(A) ≡ missing(B) — CONFIRMED

With two sources, one source's "unique" list is by construction the other's
"missing" list. 87 of 127 two-source stories are exact mechanical mirrors
(and the non-mirrors differ only because an LLM call reworded one side). The
UI therefore shows the same information four times per two-source story, plus
the duplicated contradictions column — the pasted table is one fact-set
rendered six ways.

### 6. `published_at` is never the publish date — CONFIRMED

Two writers, both wrong:

* `SourceComparisonService` sets `published_at=datetime.now(UTC)` — synthesis
  time. Of 86 coverage rows joinable to their article, **85 are >1h off** from
  the article's actual `published_at`.
* `story_synthesis_service.py:902` re-creates coverage rows from the
  comparison payload and **omits `published_at` entirely** → NULL on 1,089 of
  1,171 rows (93%). This writer wins most of the time, which is why the UI's
  "Published" column renders "—" on nearly every story.

The article's real publish date is sitting one join away
(`articles.published_at`), already loaded by the same service.

### 7. `focus_area` degrades to a template — CONFIRMED

When the LLM is unreachable, focus becomes
`"Focused on {event_type} details."` — and 39% of all rows are
`"Focused on other details."` because the dominant canonical event type is
`other`. In 135 of 289 multi-source stories (47%), **every source carries
byte-identical focus text**, making the column's premise (how coverage
*differs*) vacuous. The pasted story shows exactly this: two publishers, one
identical "Focused on natural disaster details."

### 8. Inherited mechanical defects from the same template — CONFIRMED

The service shares `ContradictionService`'s pre-#136 anatomy:

* cache key includes `context[:1000]`, so it changes whenever any article
  joins the story — the cache almost never hits (#136 fixed this for
  contradictions only);
* wholesale delete-then-insert per story, so a degraded run replaces good
  rows with fallback junk;
* `tenacity` retry on a method whose body already swallows every exception,
  so the retry never fires.

---

## What good output would require (in dependency order)

1. **Normalize before comparing.** Casefold + strip at minimum; better, map
   actors/targets through the existing canonical-entity layer and compare
   canonical IDs, not prose. This alone removes ~half the false differences
   before any LLM spend.
2. **Reframe the prompt as a validator.** Give it the same rule structure as
   `contradiction_detection`: paraphrases/case/subsets are NOT differences;
   return empty when nothing survives; justify each surviving item from the
   article context. Today's prompt guarantees confident noise.
3. **Fail closed, like #136.** No LLM → no published "analysis". Store nothing
   (or a marked "comparison unavailable") rather than raw set-diff output
   under an "AI Comparative Analysis" banner.
4. **Stop duplicating.** Store the story's contradiction list once; derive
   per-source views at read time. Collapse unique/missing mirrors for
   two-source stories.
5. **Fix `published_at`** to the source's article publish date in both writers.
6. **Extend remediation** to `story_differences`: rows with
   `contradictions LIKE 'Mismatch on %'` (702) and raw-heuristic
   unique/missing strings are the same fabrication class as the purged
   contradictions and survive the #136 purge.
7. Mechanical: cache key without volatile context; conditional reconcile
   instead of delete-then-insert; drop the dead retry decorator.

Items 1–3 change what the product claims to users and are the substance;
4–7 are hygiene that falls out of the same edit.

---

## Relationship to prior findings

#136 fixed the *source* of the fabricated contradiction rows and the quota
amplification that starved every validator. This audit shows the same
fail-open pattern has a second instance (`SourceComparisonService`), that the
fabricated text was copied into a second table the #136 purge does not touch,
and that the comparison feature's noise floor is upstream of both services —
in the un-normalized set comparison both use for candidates.

---

## Implementation status (2026-08-18, same day)

Fixes 1–3 and 5–7 are implemented; the architectural principle applied
throughout is **heuristics generate candidates; validators confirm them; only
confirmed facts reach the user**.

| # | Fix | Where |
|---|---|---|
| 1 | Normalization + canonical-entity resolution before set-difference; shared by comparison and contradiction candidates | `app/services/fact_normalization.py` |
| 2 | Prompt reframed as validator (v3.0.0): reject case variants / aliases / paraphrases / subsets, `rejected_candidates` recorded for audit | `source_comparison.yaml`, new response schema |
| 3 | Fail closed: no validator → existing rows untouched, nothing published; counted by `newsiq_comparison_unavailable_total`. Deterministic fallback deleted | `source_comparison_service.py` |
| 5 | `published_at` = the source's article publish time, carried through all three writers (service, synthesis payload round-trip, admin republish) | service + `story_synthesis_service.py` + `admin.py` |
| 6 | Remediation extended to `story_differences` at column level with provenance, plus coverage rows from fully-unvalidated runs; dry-run verified against production (702 / 660 / 770 columns, 768 full rows) | `purge_unvalidated_contradictions.py` |
| 7 | Cache key without volatile context; dead `tenacity` retry removed; conflicting numbers routed to the validator as contradiction candidates | service |

**Deferred — fix 4 (data model).** Collapsing unique(A)/missing(B) mirrors and
storing the contradiction list once with per-source views derived at read time
is a schema + API + frontend change. The validator already removes most of the
mechanical mirroring (a case-variant pair no longer produces four cells of
noise), so the remaining duplication is cosmetic rather than fabricated.
Tracked for a follow-up.

The Gemini-only chain that starved this stage's validator was already fixed in
#136 (Bedrock fallbacks on all four affected stages).
