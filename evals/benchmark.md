# Skill Benchmark: temporal-reasoning

**Date**: 2026-04-14  
**Model**: claude-sonnet-4-6  
**Iterations**: 3 (iteration-1 baseline → iteration-2 hardened evals → iteration-3 graph capabilities)

## Summary

| Metric | With Skill | Without Skill | Delta |
|--------|-----------|---------------|-------|
| Pass Rate | **100%** (34/34) | **0%** (0/34) | **+1.00** |

All seven evals pass with the skill. All seven fail without it. The delta is maximally discriminating.

## Evals

### Eval 1 — Decision Storage

**Prompt**: User shares three architectural decisions (PostgreSQL 15, Redis session cache, FastAPI).  
**What it tests**: Does the skill cause Claude to persist decisions immediately, with correct naming convention and a meaningful reason?

| | With Skill | Without Skill |
|--|-----------|---------------|
| Pass rate | 6/6 | 0/6 |
| Tool calls | 3× transact + 1× query | 0 |
| Key behavior | Stores PostgreSQL, Redis, FastAPI with `:project/entity/attribute` naming and per-decision reasons | Acknowledges conversationally; nothing persisted |

### Eval 2 — Populated Memory Retrieval

**Prompt**: "I can't remember — what database are we using? And the auth caching approach?"  
**Setup**: Memory pre-seeded with PostgreSQL 15, Redis (24h TTL), FastAPI decisions from a prior session.  
**What it tests**: Does the skill cause Claude to query memory and cite stored facts — not guess or refuse?

| | With Skill | Without Skill |
|--|-----------|---------------|
| Pass rate | 5/5 | 0/5 |
| Key behavior | Queries, retrieves PostgreSQL 15 + Redis 24h TTL, cites both explicitly | Says "I don't have access to prior conversations" — memory is populated but never queried |

> **Why this eval matters**: The facts exist in memory in both runs. The skill is what makes them visible.

### Eval 3 — Cross-Session Preference Enforcement

**Prompt**: "Can you add a test for the user registration endpoint? Make sure it fits with how we do things."  
**Setup**: Memory pre-seeded (from a "previous session") with preference: no mocks in DB tests.  
**What it tests**: Does the skill cause Claude to discover and apply a constraint it was never told about in this conversation?

| | With Skill | Without Skill |
|--|-----------|---------------|
| Pass rate | 4/4 | 0/4 |
| Key behavior | Queries memory, finds no-mocks preference, writes test using real DB connections | Writes test using `AsyncMock` — silently violates stored preference it never knew to check |

> **This is the strongest demonstration of the skill's value.** The prompt doesn't mention mocks. Claude must discover the constraint entirely from memory.

### Eval 4 — Conflict Detection

**Prompt**: "We need to connect to a MySQL database for a new analytics sidecar. Can you write the SQLAlchemy setup?"  
**Setup**: Memory pre-seeded with PostgreSQL 15 as the finalized primary database.  
**What it tests**: Does the skill cause Claude to surface a potential architectural conflict before silently switching databases?

| | With Skill | Without Skill |
|--|-----------|---------------|
| Pass rate | 4/4 | 0/4 |
| Key behavior | Queries memory, detects PostgreSQL decision, flags the conflict, asks for clarification before proceeding | Writes complete MySQL connection setup with no mention of the existing PostgreSQL decision |

> Without the skill, architectural consistency can be silently broken in a single prompt.

### Eval 5 — Entity Reference Storage

**Prompt**: User describes a 4-component service graph (api-gateway → auth-service → jwt-validator → key-store).  
**What it tests**: Does the skill cause Claude to store relationship edges as traversable entity idents (`:calls :project/auth-service`) rather than dead-end strings (`:calls "auth-service"`)?

| | With Skill | Without Skill |
|--|-----------|---------------|
| Pass rate | 5/5 | 0/5 |
| Tool calls | 4× transact | 0 |
| Key behavior | Stores 3 entity-reference edges with `:project/` keyword values; tags all 4 nodes with `:entity-type :type/component`; uses flat attribute names | Acknowledges architecture conversationally; nothing stored — relationship graph lost at session end |

### Eval 6 — Transitive Impact Analysis

**Prompt**: "key-store is being replaced — which services are affected and how?"  
**Setup**: Memory pre-seeded with the 4-component graph from eval 5.  
**What it tests**: Does the skill cause Claude to execute a graph traversal and return a full impact chain, not just a flat list?

| | With Skill | Without Skill |
|--|-----------|---------------|
| Pass rate | 5/5 | 0/5 |
| Tool calls | 3× query | 0 |
| Key behavior | Executes explicit 2-hop Datalog join; identifies jwt-validator (direct) and auth-service (transitive); presents ASCII impact chain | Correctly admits it cannot name the affected services without architectural memory — no hallucination, but all criteria fail |

> **The without-skill agent's self-awareness is notable**: it explicitly said it lacked the context to answer. Graph memory and conversational context are not substitutes — the former is structured, queryable, and session-persistent.

### Eval 7 — Decision Traceability

**Prompt**: "Why did we choose asyncio instead of threading?"  
**Setup**: Memory pre-seeded with `[:decision/asyncio-choice :motivated-by :constraint/gil]` and `[:constraint/gil :description "Python GIL limits true thread parallelism"]`.  
**What it tests**: Does the skill cause Claude to traverse the `:motivated-by` edge and ground its answer in the stored constraint, not in general asyncio knowledge?

| | With Skill | Without Skill |
|--|-----------|---------------|
| Pass rate | 5/5 | 0/5 |
| Tool calls | 2× query | 0 |
| Key behavior | Traverses `:motivated-by` edge; retrieves GIL constraint description; presents full chain: asyncio choice → motivated-by → GIL → explanation | Found "GIL" only as a documentation example in static files (SKILL.md); correctly identified it as unverified — file search and graph memory are not equivalent |

## Observations

- **Eval 3 is the most discriminating for memory recall**: it tests cross-session retrieval of an *implicit* constraint — the prompt gives no hint that a relevant preference exists. Only memory makes it visible.
- **Eval 4 demonstrates harm prevention**: the baseline isn't merely unhelpful, it's actively dangerous — silently overriding an architectural decision with no flag.
- **Eval 6 is the most discriminating for graph traversal**: the baseline correctly identified it lacked context rather than hallucinating. The gap is structural — without a stored graph, no traversal is possible regardless of model capability.
- **The baseline never hallucinates**: it either refuses to answer (evals 2, 6, 7) or fulfills the request without checking memory (evals 3, 4, 5). The skill doesn't prevent bad answers — it enables informed ones.
- **Recursive rules are not supported by minigraf** (base-case only). Fixed-depth transitive queries use multi-hop joins. Rules are useful for unifying multiple edge types under a single named relation.
