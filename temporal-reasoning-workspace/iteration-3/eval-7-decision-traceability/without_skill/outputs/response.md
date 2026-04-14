# Why asyncio? — Tracing the Decision

## Short Answer

I cannot trace the reasoning from memory — I have no prior context about why asyncio was chosen for this project.

## What the Codebase Shows

Looking at the code directly, I can find references to the asyncio decision scattered across the repository, but there is no authoritative, dated decision record I can point to.

Here is what I found:

**In `SKILL.md` (line 265):**
> "We chose asyncio over threading because of the GIL."

This appears as an *example* of how to record a decision in the memory graph, not as an actual recorded decision. The example shows a `motivated-by` edge from the decision to a constraint called `gil-constraint`, whose description is `"Python GIL limits true thread parallelism"`.

**In `tests/test_harness.py` and `temporal-reasoning-workspace/seed_eval7.py`:**
The test fixtures and seed scripts populate a graph with these facts:
- `:rules/gil-constraint` — description: `"Python GIL limits true thread parallelism"`, entity-type: `:type/constraint`
- `:project/asyncio-choice` — description: `"use asyncio over threading for concurrency"`, entity-type: `:type/decision`, `motivated-by: :rules/gil-constraint`

## The Problem

These are *test fixtures* and *documentation examples*, not actual memory entries from a live decision session. The `seed_eval7.py` file resets the graph and repopulates it with synthetic data for evaluation purposes. I cannot confirm:

- When the asyncio decision was actually made
- Who made it
- What alternatives were evaluated
- Whether there were secondary motivations beyond the GIL (e.g., I/O-bound workload profile, ecosystem fit, existing team familiarity)

## What the Code Itself Suggests

The current implementation in `minigraf_tool.py` uses `subprocess.run()` — a synchronous, blocking call. There is no asyncio in the actual implementation at all. This means either:

1. The asyncio decision applies to a *consumer* of this library (not this library itself), or
2. The decision was discussed but not yet implemented, or
3. The "decision" recorded in the memory graph is a hypothetical example rather than a real project decision

## Honest Assessment

Without a persistent memory store that was actually written to during the session when this decision was made, I cannot trace the reasoning. The codebase contains a canonical *example* of how such traceability would work (the `motivated-by` edge pattern in SKILL.md), but the actual decision record does not appear to have been persisted across sessions.

If you need to recover this reasoning, I would suggest:
1. Checking git history and PR discussions for the original threading vs. asyncio debate
2. Asking whoever made the decision to re-record it in the memory graph
3. Looking at any architecture decision records (ADRs) outside this repository
