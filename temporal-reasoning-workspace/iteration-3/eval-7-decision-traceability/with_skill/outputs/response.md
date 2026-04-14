# Eval 7 — With Skill Response

## Response to user

Let me check memory to trace the reasoning behind the asyncio decision.

Memory has a full decision record with a `:motivated-by` edge. Here's the reasoning chain:

**Decision:** use asyncio over threading for concurrency  
**Motivated by:** Python GIL limits true thread parallelism

The GIL (Global Interpreter Lock) prevents multiple Python threads from executing Python bytecode simultaneously. In a threading model, concurrent tasks still effectively serialize at the Python level — you get context switching overhead without true parallelism. Asyncio sidesteps this by using cooperative concurrency on a single thread: I/O-bound tasks yield control voluntarily, avoiding GIL contention entirely while keeping the codebase reasoning about one execution context at a time.

So the decision wasn't preference — it was a direct consequence of the GIL constraint. Threads were ruled out because they don't deliver parallelism for Python-level work; asyncio was chosen because it delivers concurrency where it matters (I/O waits) without fighting the GIL.

I've stored that in memory.

## Minigraf tool calls

### Seed
```bash
MINIGRAF_GRAPH_PATH=/tmp/eval7_with_skill.graph python seed_eval7.py
```
Output: `Seeded eval 7 graph at /tmp/eval7_with_skill.graph`

### Query 1 — traverse :motivated-by edge
```python
query('''[:find ?reason
          :where [?d :description "use asyncio over threading for concurrency"]
                 [?d :motivated-by ?c]
                 [?c :description ?reason]]''')
```
Output: `[['Python GIL limits true thread parallelism']]`

### Query 2 — full decision entity facts
```python
query('[:find ?a ?v :where [:project/asyncio-choice ?a ?v]]')
```
Output:
```
:entity-type    :type/decision
:motivated-by   :rules/gil-constraint
:description    "use asyncio over threading for concurrency"
```
