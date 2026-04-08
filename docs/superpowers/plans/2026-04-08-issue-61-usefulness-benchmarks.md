# Issue #61 Usefulness Benchmarks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace vague usefulness claims with explicit behavior-consistency and prompt-compression benchmark outputs that the harness can measure and report.

**Architecture:** Keep the existing deterministic harness, but add benchmark helpers that compute structured metrics instead of only pass/fail behavior tests. Use simple local proxies for prompt compression and behavior consistency so the benchmark remains reproducible and aligned with what the repo actually proves.

**Tech Stack:** Python 3, pytest, minigraf CLI wrapper, repository docs

---

### Task 1: Add a failing benchmark test for explicit metrics

**Files:**
- Modify: `tests/test_harness.py`
- Test: `tests/test_harness.py`

- [ ] **Step 1: Write the failing test**

```python
def test_usefulness_benchmarks_report_explicit_metrics(populated_graph):
    benchmarks = collect_usefulness_benchmarks(populated_graph)

    assert benchmarks["behavior_consistency"]["passed"] is True
    assert benchmarks["prompt_compression"]["memory_prompt_tokens"] < benchmarks["prompt_compression"]["restated_prompt_tokens"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_harness.py::test_usefulness_benchmarks_report_explicit_metrics -q`
Expected: FAIL because `collect_usefulness_benchmarks()` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def collect_usefulness_benchmarks(graph_path):
    ...
    return {
        "behavior_consistency": {"passed": True, ...},
        "prompt_compression": {"memory_prompt_tokens": ..., "restated_prompt_tokens": ...},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_harness.py::test_usefulness_benchmarks_report_explicit_metrics -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-04-08-issue-61-usefulness-benchmarks.md tests/test_harness.py
git commit -m "test: add usefulness benchmark metrics"
```

### Task 2: Expose benchmark output in the harness runner

**Files:**
- Modify: `tests/test_harness.py`
- Test: `tests/test_harness.py`

- [ ] **Step 1: Write the failing test**

```python
def test_benchmark_summary_labels_metric_sections(populated_graph, capsys):
    print_benchmark_summary(populated_graph)
    captured = capsys.readouterr()

    assert "Usefulness benchmarks" in captured.out
    assert "Behavior consistency" in captured.out
    assert "Prompt compression" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_harness.py::test_benchmark_summary_labels_metric_sections -q`
Expected: FAIL because `print_benchmark_summary()` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def print_benchmark_summary(graph_path):
    benchmarks = collect_usefulness_benchmarks(graph_path)
    print("Usefulness benchmarks:")
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_harness.py::test_benchmark_summary_labels_metric_sections -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_harness.py
git commit -m "test: print usefulness benchmark summary"
```

### Task 3: Align documentation with measured claims

**Files:**
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `tests/test_harness.py`

- [ ] **Step 1: Update README benchmark methodology**

```markdown
## Usefulness Benchmarks

The harness reports:
- behavior consistency
- prompt compression proxy
```

- [ ] **Step 2: Update skill wording if needed**

Adjust any broad claims so they match what the harness actually measures.

- [ ] **Step 3: Run focused tests**

Run: `pytest tests/test_harness.py -q`
Expected: PASS

- [ ] **Step 4: Run full suite**

Run: `pytest -q`
Expected: PASS with all tests green

- [ ] **Step 5: Inspect diff**

Run: `git diff -- tests/test_harness.py README.md SKILL.md docs/superpowers/plans/2026-04-08-issue-61-usefulness-benchmarks.md`
Expected: Only benchmark and documentation alignment changes appear

- [ ] **Step 6: Commit**

```bash
git add tests/test_harness.py README.md SKILL.md docs/superpowers/plans/2026-04-08-issue-61-usefulness-benchmarks.md
git commit -m "docs: document usefulness benchmark methodology"
```
