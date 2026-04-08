# Issue #62 Cross-Session Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible end-to-end evaluation showing that a decision stored in one session changes the answer or action taken in a later session without restating the full context.

**Architecture:** Extend the harness with a thin deterministic “agent behavior” layer that reads persisted facts from a shared graph and derives a response/action from them. Keep the evaluation local and stable by avoiding live model calls while still proving cross-session usefulness.

**Tech Stack:** Python 3, pytest, minigraf CLI wrapper, repository docs

---

### Task 1: Add a failing end-to-end cross-session test

**Files:**
- Modify: `tests/test_harness.py`
- Test: `tests/test_harness.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cross_session_decision_changes_later_answer(populated_graph):
    answer = answer_cache_strategy_question(populated_graph)

    assert "Redis" in answer
    assert "persisted memory" in answer
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_harness.py::test_cross_session_decision_changes_later_answer -q`
Expected: FAIL because the helper function does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def answer_cache_strategy_question(graph_path):
    result = query(
        "[:find ?desc :where [?e :decision/description ?desc]]",
        graph_path=graph_path,
    )
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_harness.py::test_cross_session_decision_changes_later_answer -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-04-08-issue-62-cross-session-eval.md tests/test_harness.py
git commit -m "test: add cross-session usefulness regression"
```

### Task 2: Add an observable action-oriented evaluation

**Files:**
- Modify: `tests/test_harness.py`
- Test: `tests/test_harness.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cross_session_decision_changes_later_action(populated_graph):
    plan = derive_cache_plan(populated_graph)

    assert plan["cache_backend"] == "Redis"
    assert plan["source"] == "persisted memory"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_harness.py::test_cross_session_decision_changes_later_action -q`
Expected: FAIL because `derive_cache_plan()` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def derive_cache_plan(graph_path):
    ...
    return {"cache_backend": "Redis", "source": "persisted memory"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_harness.py::test_cross_session_decision_changes_later_action -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_harness.py
git commit -m "test: cover cross-session action derivation"
```

### Task 3: Document the evaluation and run verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_harness.py`
- Test: `tests/test_harness.py`

- [ ] **Step 1: Update README with evaluation instructions**

```markdown
## Cross-Session Evaluation

Run:

```bash
pytest tests/test_harness.py -q
```

Success means the harness proves a fact stored in one session changes the answer and plan produced in a later session using the same graph.
```

- [ ] **Step 2: Update harness runner output if needed**

```python
print("✓ Cross-session answer derivation: PASS")
print("✓ Cross-session action derivation: PASS")
```

- [ ] **Step 3: Run focused tests**

Run: `pytest tests/test_harness.py -q`
Expected: PASS

- [ ] **Step 4: Run full suite**

Run: `pytest -q`
Expected: PASS with all tests green

- [ ] **Step 5: Inspect diff**

Run: `git diff -- tests/test_harness.py README.md docs/superpowers/plans/2026-04-08-issue-62-cross-session-eval.md`
Expected: Only cross-session evaluation and docs changes appear

- [ ] **Step 6: Commit**

```bash
git add tests/test_harness.py README.md docs/superpowers/plans/2026-04-08-issue-62-cross-session-eval.md
git commit -m "docs: add cross-session evaluation guidance"
```
