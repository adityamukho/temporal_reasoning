---
title: Rename project to Vulcan
date: 2026-04-14
status: approved
---

# Vulcan Rename — Design Spec

## Background

The project was originally named "temporal-reasoning" — descriptive but forgettable. After a competitive analysis session comparing it against Graphify, LLM Wiki, Engraph, Memex, Clairvoyance, and similar tools, the project was renamed to **Vulcan** to reflect its identity: perfect memory, exact reasoning, and complete history — capabilities that no other tool in the space provides.

The name choice is intentional: Vulcans are known for pure logic, eidetic memory, and precise causal reasoning — an accurate metaphor for a deterministic bi-temporal Datalog engine.

## Brand

**Name:** Vulcan

**Tagline:** Perfect memory. Exact reasoning. Complete history.

**One-liner:**
> Vulcan gives AI coding agents bi-temporal graph memory: query any past state, traverse live dependency graphs, and correlate architectural decisions with structural change — all with deterministic Datalog, no fuzzy retrieval.

**Core messaging principle:** Lead with what Vulcan can answer that nothing else can. No abstract claims — only concrete queries that would be impossible with git log, vector search, or key-value memory.

Example questions only Vulcan can answer:
- "What did the dependency graph look like before the auth refactor?"
- "When did service-A first depend on service-B — and what decision caused it?"
- "Which modules changed after we decided to switch databases?"
- "Give me a brief history of how this project's architecture evolved."

## File Changes

### Renames

| Old | New |
|-----|-----|
| `minigraf_tool.py` | `vulcan.py` |
| `tests/test_minigraf_tool.py` | `tests/test_vulcan.py` |
| `skills/temporal-reasoning/` | `skills/vulcan/` |
| `.opencode/skills/temporal_reasoning/` | `.opencode/skills/vulcan/` |

### Tool name changes

Everywhere `minigraf_query`, `minigraf_transact`, `minigraf_retract` appear in tool schemas, skill files, prompts, and docs:

| Old | New |
|-----|-----|
| `minigraf_query` | `vulcan_query` |
| `minigraf_transact` | `vulcan_transact` |
| `minigraf_retract` | `vulcan_retract` |

### Python imports

All `from minigraf_tool import` → `from vulcan import` in:
- `install.py`
- `report_issue.py`
- `tests/conftest.py`
- `tests/test_harness.py`
- `tests/test_advanced.py`
- `CLAUDE.md`
- `AGENTS.md`

### Package name

`pyproject.toml`: package name `temporal-reasoning` → `vulcan`

### Plugin/marketplace files

`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: name and description updated to reflect Vulcan brand and new messaging.

### Docs updated

- `README.md` — full rebrand: new title, tagline, hero messaging, architecture diagram, all tool/import references
- `ROADMAP.md` — title and any name references
- `SKILL.md` — skill name, description, all tool references
- `skill.json` — name and description
- `tools/query.json`, `tools/transact.json`, `tools/retract.json`, `tools/report_issue.json` — tool names
- `prompts/system.txt`, `prompts/fewshots.txt` — tool name references
- `CLAUDE.md` — import examples, project description
- `AGENTS.md` — any references

### Left unchanged

`temporal-reasoning-workspace/` eval history is left as-is. It is benchmark evidence committed to git history; renaming would break references in `evals/benchmark.md` and obscure the eval provenance. Internal references to `minigraf_query` inside eval files are historical records, not live code.

## GitHub

Rename the remote repository:

```bash
gh repo rename vulcan
```

Update the remote URL locally after rename.

## Differentiation (preserved in ROADMAP.md)

The rename was accompanied by a competitive analysis establishing why this project is not replaceable by simply reading git history:

- **Cross-cutting semantic queries** — git is indexed by commit; Vulcan is indexed by entity. Querying when a dependency first appeared requires O(commits × parse time) with git, one Datalog query with Vulcan.
- **Semantic structure survives text changes** — git sees line diffs; Vulcan stores entity-addressed edges that survive renames and moves.
- **Agent-authored facts** — decisions and constraints logged by agents but never committed to files have no representation in git.
- **Cross-layer joins** — no way to ask git "what structural changes happened after we decided to switch databases?" Both facts live in Vulcan as datoms; a single join connects them.
